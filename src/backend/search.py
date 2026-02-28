"""
Black Vault — Search module.
Hybrid search: Semantic (Vector) + Lexical (ILIKE).
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

from backend.config import EMBEDDING_DIM, OLLAMA_HOST, LLM_MODEL
from backend import db
from backend.ingest import get_embedding


def enrich_query(query: str) -> dict:
    """
    Asks the local Ollama LLM to analyze the user query and extract filtering rules
    and semantic synonyms to improve the search precision.
    """
    prompt = f"""
Analyze the following search query and extract any explicit filters regarding file type, tags, or dates.
Then, expand the core search intent with synonyms.
Return a JSON with exactly these keys:
- "expanded_query": A string with the core search terms and synonyms for vector/lexical search.
- "sql_filter": A valid SQL WHERE clause fragment applying ONLY to columns in the `i` (items) table (i.source_type, i.title, i.tags, i.summary). If no filters apply, return "1=1". Do NOT include the word WHERE.

User Query: "{query}"

Return ONLY valid JSON, no extra text.
"""
    url = f"http://{OLLAMA_HOST}/api/generate"
    payload = {"model": LLM_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    print(f"[DEBUG] Sending enrichment query to {url} for query: '{query}'")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_body = response.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            raw_text = resp_json.get("response", "").strip()
            
            try:
                data = json.loads(raw_text)
                return {
                    "expanded_query": data.get("expanded_query", query),
                    "sql_filter": data.get("sql_filter", "1=1")
                }
            except json.JSONDecodeError:
                return {"expanded_query": query, "sql_filter": "1=1"}
    except Exception as e:
        print(f"⚠️ Query enrichment failed: {e}")
        return {"expanded_query": query, "sql_filter": "1=1"}


def search(query: str, limit: int = 10, use_enrichment: bool = True) -> list[dict]:
    con = db.get_connection()
    
    expanded_query = query
    sql_filter = "1=1"
    
    if use_enrichment:
        enrichment = enrich_query(query)
        expanded_query = enrichment["expanded_query"]
        sql_filter = enrichment["sql_filter"]
        # Basic SQL injection mitigation for our MVP
        if ";" in sql_filter or "DROP" in sql_filter.upper():
            sql_filter = "1=1"
        
    query_vec = get_embedding(expanded_query)

    # 1. Semantic Search
    try:
        semantic_rows = con.execute(
            f"""
            SELECT e.item_id, c.body AS snippet,
                   array_cosine_similarity(e.vector, ?::FLOAT[{EMBEDDING_DIM}]) AS sem_score
            FROM embeddings e
            JOIN content c ON c.id = e.content_id
            JOIN items i ON i.id = e.item_id
            WHERE {sql_filter}
            ORDER BY sem_score DESC
            LIMIT ?;
            """,
            [query_vec, limit * 2],
        ).fetchall()
    except Exception as e:
        print(f"⚠️ Semantic search failed with filter '{sql_filter}': {e}. Falling back.")
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
    # Use DuckDB FTS extension for true TF-IDF / BM25
    try:
        lex_rows = con.execute(
            f"""
            SELECT c.item_id, c.body AS snippet, fts_main_content.match_bm25(c.id, ?) AS lex_score
            FROM content c
            JOIN items i ON i.id = c.item_id
            WHERE fts_main_content.match_bm25(c.id, ?) IS NOT NULL
              AND {sql_filter}
            ORDER BY lex_score DESC
            LIMIT ?;
            """,
            [expanded_query, expanded_query, limit * 2],
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