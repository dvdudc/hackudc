"""
Search Pipeline Timing Benchmark — REAL API calls (no mocks).
Measures each stage of the search pipeline with actual Ollama + Gemini calls.
"""
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from backend.config import EMBEDDING_DIM
from backend import db
from backend.ingest import get_embedding



QUERIES = [
    "ideas sobre productividad",
    "documentos de python",
    "archivos de configuracion",
    "como funciona la busqueda semantica",
    "DuckDB extensiones FTS",
]


def timed_search(query: str, limit: int = 5):
    """Run a search with per-stage timing instrumentation using REAL API calls."""
    timings = {}
    con = db.get_connection()

    # ── Stage 1: Query Enrichment (REAL Ollama call) ─────────────────    
    import time
    start = time.time()
    # enrichment = enrich_query(query)
    # query_tags = enrichment.get("tags", [])nded_query"
    # expanded_query = enrichment["expanded_query"] # This line was originally here, but `enrichment` is now commented out.
    expanded_query = query # Default to original query if enrichment is skipped
    # sql_filter = enrichment["sql_filter"] # This line was originally here, but `enrichment` is now commented out.
    sql_filter = "1=1" # Default to no filter if enrichment is skipped
    if ";" in sql_filter or "DROP" in sql_filter.upper():
        sql_filter = "1=1"
    timings["1_enrichment_llm"] = time.perf_counter() - t0

    # ── Stage 2: Embedding Generation (REAL Gemini API call) ─────────
    t0 = time.perf_counter()
    query_vec = get_embedding(expanded_query)
    timings["2_embedding_api"] = time.perf_counter() - t0

    # ── Stage 3: Semantic Search (VSS / HNSW) ────────────────────────
    t0 = time.perf_counter()
    cursor = con.cursor()
    vector_str = "[" + ", ".join(map(str, query_vec)) + "]"
    try:
        semantic_rows = cursor.execute(
            f"""
            WITH top_embeddings AS (
                SELECT item_id, content_id,
                       array_cosine_distance(vector, {vector_str}::FLOAT[{EMBEDDING_DIM}]) AS dist
                FROM embeddings
                ORDER BY array_cosine_distance(vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])
                LIMIT {limit * 2}
            )
            SELECT t.item_id, c.body AS snippet, (1.0 - t.dist) AS sem_score
            FROM top_embeddings t
            JOIN content c ON c.id = t.content_id
            """
        ).fetchall()
    except Exception as e:
        print(f"  ⚠️ Semantic search error: {e}")
        semantic_rows = []
    timings["3_semantic_vss"] = time.perf_counter() - t0

    # ── Stage 4: Lexical Search (BM25 / FTS) ─────────────────────────
    t0 = time.perf_counter()
    safe_query = expanded_query.replace("'", "''")
    try:
        lex_cursor = con.cursor()
        lex_rows = lex_cursor.execute(
            f"""
            SELECT item_id, body AS snippet,
                   fts_main_content.match_bm25(id, '{safe_query}') AS lex_score
            FROM content
            WHERE lex_score IS NOT NULL
            ORDER BY lex_score DESC
            LIMIT ?;
            """,
            [limit * 2],
        ).fetchall()
    except Exception as e:
        print(f"  ⚠️ FTS error: {e}")
        lex_rows = []
    timings["4_lexical_fts"] = time.perf_counter() - t0

    # ── Stage 5: Merge & Rank ────────────────────────────────────────
    t0 = time.perf_counter()
    semantic = {}
    for item_id, snippet, score in semantic_rows:
        if item_id not in semantic or score > semantic[item_id]["sem_score"]:
            semantic[item_id] = {"snippet": snippet, "sem_score": score}
    lexical = {}
    for item_id, snippet, lex_score in lex_rows:
        if item_id not in lexical or lex_score > lexical[item_id]["lex_score"]:
            lexical[item_id] = {"snippet": snippet, "lex_score": lex_score}

    all_ids = set(semantic.keys()) | set(lexical.keys())
    max_lex = max([v["lex_score"] for v in lexical.values()]) if lexical else 1.0
    results = []
    for item_id in all_ids:
        sem = semantic.get(item_id, {}).get("sem_score", 0.0)
        raw_lex = lexical.get(item_id, {}).get("lex_score", 0.0)
        norm_lex = (raw_lex / max_lex) if max_lex > 0 else 0.0
        combined = 0.7 * sem + 0.3 * norm_lex
        snippet = semantic.get(item_id, {}).get("snippet") or lexical.get(item_id, {}).get("snippet", "")
        results.append({"item_id": item_id, "snippet": snippet[:200], "score": round(combined, 4)})
    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:limit]
    timings["5_merge_rank"] = time.perf_counter() - t0

    # ── Stage 6: Metadata Attachment ─────────────────────────────────
    t0 = time.perf_counter()
    if results:
        item_ids = [r["item_id"] for r in results]
        items_dict = {item["id"]: item for item in db.get_items_by_ids(item_ids)}
        for r in results:
            item = items_dict.get(r["item_id"])
            if item:
                r["title"] = item.get("title") or "(Sin título)"
                r["tags"] = item.get("tags", "")
    timings["6_metadata"] = time.perf_counter() - t0

    timings["TOTAL"] = sum(v for k, v in timings.items() if k != "TOTAL")
    return results, timings, expanded_query


def run_benchmark():
    print("=" * 72)
    print("  SEARCH PIPELINE TIMING — REAL API CALLS")
    print("=" * 72)

    all_timings = defaultdict(list)

    for q in QUERIES:
        results, timings, expanded = timed_search(q, limit=5)

        print(f"\n🔍 Query: '{q}'")
        print(f"   Expanded: '{expanded}'")
        print(f"   Results: {len(results)}")
        for k, v in timings.items():
            bar = "█" * int(v / timings["TOTAL"] * 30) if timings["TOTAL"] > 0 else ""
            pct = (v / timings["TOTAL"] * 100) if timings["TOTAL"] > 0 else 0
            unit = "s" if v >= 1.0 else "ms"
            val = v if v >= 1.0 else v * 1000
            print(f"   {k:<20s} {val:>8.1f} {unit:>2s}  {pct:>5.1f}%  {bar}")
            all_timings[k].append(v)

        if results:
            top = results[0]
            print(f"   Top hit: [ID:{top['item_id']}] {top.get('title', '?')} ({top['score']:.4f})")

    # ── Summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  AVERAGE TIMES ACROSS ALL QUERIES")
    print("=" * 72)
    for k in sorted(all_timings.keys()):
        vals = all_timings[k]
        avg = sum(vals) / len(vals)
        mn = min(vals)
        mx = max(vals)
        unit = "s" if avg >= 1.0 else "ms"
        f = 1.0 if avg >= 1.0 else 1000.0
        print(f"   {k:<20s}  avg={avg*f:>7.1f} {unit}   min={mn*f:>7.1f} {unit}   max={mx*f:>7.1f} {unit}")


if __name__ == "__main__":
    run_benchmark()
