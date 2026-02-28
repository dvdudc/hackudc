"""
Black Vault — Search module.
Hybrid search: Semantic (Vector) + Lexical (ILIKE).
"""
from __future__ import annotations

from backend.config import EMBEDDING_DIM
from backend import db
from backend.ingest import get_embedding


def search(query: str, limit: int = 10) -> list[dict]:
    con = db.get_connection()
    query_vec = get_embedding(query)

    # 1. Semantic Search
    semantic_rows = con.execute(
        f"""
        SELECT e.item_id, c.body AS snippet,
               array_cosine_similarity(e.vector, ?::FLOAT[{EMBEDDING_DIM}]) AS sem_score
        FROM embeddings e
        JOIN content c ON c.id = e.content_id
        ORDER BY sem_score DESC
        LIMIT ?;
        """,
        [query_vec, limit * 2],
    ).fetchall()

    semantic: dict[int, dict] = {}
    for item_id, snippet, score in semantic_rows:
        if item_id not in semantic or score > semantic[item_id]["sem_score"]:
            semantic[item_id] = {"snippet": snippet, "sem_score": score}

    # ── 3. Lexical search (TF-IDF / BM25) ────────────────────────────
    lexical: dict[int, dict] = {}
    
    # Use DuckDB FTS extension for true TF-IDF / BM25
    try:
        lex_rows = con.execute(
            """
            SELECT item_id, body AS snippet, fts_main_content.match_bm25(id, ?) AS lex_score
            FROM content
            WHERE fts_main_content.match_bm25(id, ?) IS NOT NULL
            ORDER BY lex_score DESC
            LIMIT ?;
            """,
            [query, query, limit * 2],
        ).fetchall()

        for item_id, snippet, lex_score in lex_rows:
            if item_id not in lexical or lex_score > lexical[item_id]["lex_score"]:
                lexical[item_id] = {"snippet": snippet, "lex_score": lex_score}
    except Exception as e:
        print(f"FTS Search failed: {e}")

    # 3. Merge & Rank
    all_ids = set(semantic.keys()) | set(lexical.keys())
    results = []

    max_lex = max([v["lex_score"] for v in lexical.values()]) if lexical else 1.0

    for item_id in all_ids:
        sem = semantic.get(item_id, {}).get("sem_score", 0.0)
        raw_lex = lexical.get(item_id, {}).get("lex_score", 0.0)
        
        # Normalize BM25 score to 0..1 scale roughly
        norm_lex = (raw_lex / max_lex) if max_lex > 0 else 0.0

        # Weighted combination: 70 % semantic, 30 % lexical
        combined = 0.7 * sem + 0.3 * norm_lex

        snippet = (
            semantic.get(item_id, {}).get("snippet")
            or lexical.get(item_id, {}).get("snippet", "")
        )

        results.append({
            "item_id": item_id,
            "snippet": snippet[:200],
            "score": round(combined, 4),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    results = results[:limit]

    # 4. Attach Metadata
    for r in results:
        item = db.get_item(r["item_id"])
        if item:
            r["title"] = item.get("title") or "(Sin título)"
            r["tags"] = item.get("tags", "")
            r["summary"] = item.get("summary", "")

    return results