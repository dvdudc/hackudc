"""
Black Vault — Search module.
Hybrid search: Semantic (Vector) + Lexical (FTS/BM25).
"""
from __future__ import annotations
import time
import re
import logging

import json
import urllib.request
import urllib.error

from backend.config import EMBEDDING_DIM, OLLAMA_HOST, LLM_MODEL
from backend import db
from backend.ingest import get_embedding


# ── Allowed columns and values for SQL filter validation ─────────────
_ALLOWED_FILTER_COLS = {"i.source_type", "i.title", "i.tags", "i.summary"}
_DANGEROUS_KEYWORDS = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|EXEC|UNION|--|;)\b",
    re.IGNORECASE,
)


def _validate_sql_filter(sql_filter: str) -> str:
    """Sanitise the LLM-generated SQL filter. Return '1=1' if anything looks wrong."""
    if not sql_filter or not sql_filter.strip():
        return "1=1"

    # Basic injection / destructive keyword check
    if _DANGEROUS_KEYWORDS.search(sql_filter):
        logging.warning(f"Rejected dangerous SQL filter from LLM: {sql_filter}")
        return "1=1"

    # Only allow filters that reference permitted columns
    # Extract identifiers that look like "i.<col>"
    col_refs = re.findall(r"\bi\.\w+", sql_filter)
    for col in col_refs:
        if col not in _ALLOWED_FILTER_COLS:
            logging.warning(f"Rejected SQL filter referencing unknown column '{col}': {sql_filter}")
            return "1=1"

    # Validate the filter actually executes against the real DB
    try:
        con = db.get_connection()
        con.execute(
            f"SELECT 1 FROM items i WHERE {sql_filter} LIMIT 0"
        )
    except Exception as e:
        logging.warning(f"SQL filter from LLM is invalid ({e}): {sql_filter}")
        return "1=1"

    return sql_filter


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
- "sql_filter": A valid SQL WHERE clause fragment applying ONLY to columns in the `i` (items) table.
  Allowed columns: i.source_type (values: 'text' or 'image'), i.title, i.tags, i.summary.
  Use ILIKE for text matching. If no filters apply, return "1=1". Do NOT include the word WHERE.

User Query: "{query}"

Return ONLY valid JSON, no extra text.
"""
    url = f"http://{OLLAMA_HOST}/api/generate"
    payload = {"model": LLM_MODEL, "prompt": prompt, "stream": False, "format": "json"}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_body = response.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            raw_text = resp_json.get("response", "").strip()

            try:
                data = json.loads(raw_text)
                expanded = data.get("expanded_query", query)
                # Ollama sometimes returns a list of terms instead of a string
                if isinstance(expanded, list):
                    expanded = " ".join(str(x) for x in expanded)
                expanded = expanded.strip() if isinstance(expanded, str) else query
                if not expanded:
                    expanded = query
                raw_filter = data.get("sql_filter", "1=1") or "1=1"
                safe_filter = _validate_sql_filter(raw_filter)
                return {
                    "expanded_query": expanded,
                    "sql_filter": safe_filter,
                }
            except json.JSONDecodeError:
                return {"expanded_query": query, "sql_filter": "1=1"}
    except Exception as e:
        logging.warning(f"Query enrichment failed: {e}")
        return {"expanded_query": query, "sql_filter": "1=1"}


def search(query: str, limit: int = 10, use_enrichment: bool = True) -> list[dict]:
    con = db.get_connection()

    expanded_query = query
    sql_filter = "1=1"

    if use_enrichment:
        enrichment = enrich_query(query)
        expanded_query = enrichment["expanded_query"]
        sql_filter = enrichment["sql_filter"]

    # ── 1. Generate query embedding ──────────────────────────────────
    query_vec = get_embedding(expanded_query)

    # ── 2. Semantic Search (Vector / HNSW) ───────────────────────────
    vector_str = "[" + ", ".join(map(str, query_vec)) + "]"

    try:
        if sql_filter.strip() == "1=1":
            semantic_rows = con.execute(
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
        else:
            semantic_rows = con.execute(
                f"""
                WITH filtered_embeddings AS (
                    SELECT e.item_id, e.content_id, e.vector
                    FROM embeddings e
                    JOIN items i ON i.id = e.item_id
                    WHERE {sql_filter}
                ),
                top_embeddings AS (
                    SELECT item_id, content_id,
                           array_cosine_distance(vector, {vector_str}::FLOAT[{EMBEDDING_DIM}]) AS dist
                    FROM filtered_embeddings
                    ORDER BY array_cosine_distance(vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])
                    LIMIT {limit * 2}
                )
                SELECT t.item_id, c.body AS snippet, (1.0 - t.dist) AS sem_score
                FROM top_embeddings t
                JOIN content c ON c.id = t.content_id
                """
            ).fetchall()
    except Exception as e:
        logging.warning(f"Semantic search failed with filter '{sql_filter}': {e}. Falling back.")
        semantic_rows = con.execute(
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

    # ── 3. Lexical Search (FTS / BM25) ───────────────────────────────
    safe_query = expanded_query.replace("'", "''")
    try:
        if sql_filter.strip() == "1=1":
            lex_rows = con.execute(
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
        else:
            lex_rows = con.execute(
                f"""
                SELECT c.item_id, c.body AS snippet,
                       fts_main_content.match_bm25(c.id, '{safe_query}') AS lex_score
                FROM content c
                JOIN items i ON i.id = c.item_id
                WHERE fts_main_content.match_bm25(c.id, '{safe_query}') IS NOT NULL
                  AND {sql_filter}
                ORDER BY lex_score DESC
                LIMIT ?;
                """,
                [limit * 2],
            ).fetchall()
    except Exception as e:
        logging.warning(f"FTS Search failed: {e}")
        lex_rows = []

    # ── 4. Deduplicate per item_id ───────────────────────────────────
    semantic: dict[int, dict] = {}
    for item_id, snippet, score in semantic_rows:
        if item_id not in semantic or score > semantic[item_id]["sem_score"]:
            semantic[item_id] = {"snippet": snippet, "sem_score": score}

    lexical: dict[int, dict] = {}
    for item_id, snippet, lex_score in lex_rows:
        if item_id not in lexical or lex_score > lexical[item_id]["lex_score"]:
            lexical[item_id] = {"snippet": snippet, "lex_score": lex_score}

    # ── 5. Merge & Rank ──────────────────────────────────────────────
    all_ids = set(semantic.keys()) | set(lexical.keys())
    results = []

    # Normalise BM25 scores to [0, 1] — BM25 can be negative
    if lexical:
        lex_values = [v["lex_score"] for v in lexical.values()]
        min_lex = min(lex_values)
        max_lex = max(lex_values)
        lex_range = max_lex - min_lex if max_lex != min_lex else 1.0
    else:
        min_lex, max_lex, lex_range = 0.0, 1.0, 1.0

    for item_id in all_ids:
        sem = semantic.get(item_id, {}).get("sem_score", 0.0)
        raw_lex = lexical.get(item_id, {}).get("lex_score", 0.0)
        # Min-max normalisation into [0, 1]
        norm_lex = (raw_lex - min_lex) / lex_range if lexical else 0.0

        # Weighted combination: 70% semantic, 30% lexical
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

    # ── 6. Attach Metadata (Batched) ─────────────────────────────────
    if results:
        item_ids = [r["item_id"] for r in results]
        items_dict = {item["id"]: item for item in db.get_items_by_ids(item_ids)}

        for r in results:
            item = items_dict.get(r["item_id"])
            if item:
                r["title"] = item.get("title") or "(Sin título)"
                r["tags"] = item.get("tags", "")
                r["summary"] = item.get("summary", "")

    return results