"""
Black Vault — Hybrid Search Engine
Combines semantic search (vector embeddings via DuckDB HNSW)
with lexical search (BM25 via DuckDB FTS), merging the results.
Now uses Query Intent Routing instead of raw LLM SQL generation.
"""

from __future__ import annotations

import logging

from backend.llm import get_client
from backend.config import EMBEDDING_DIM, EMBEDDING_MODEL
from backend import db
from backend.intent import parse_intent


def get_embedding(text: str) -> list[float]:
    result = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return list(result.embeddings[0].values)


def search(query: str, limit: int = 10, use_enrichment: bool = True) -> list[dict]:
    con = db.get_connection()

    semantic_query = query
    lexical_query = query
    sql_filter = "1=1"
    params = []
    
    # Session context vector
    session_vec = db.get_recent_session_vector(limit=5)
    session_vector_str = "[" + ", ".join(map(str, session_vec)) + "]" if session_vec else None

    if use_enrichment:
        try:
            intent_data = parse_intent(query)
            # Safeguard: if LLM strips the query too aggressively, keep the original
            parsed_sem = intent_data.semantic_query.strip()
            if len(parsed_sem) >= 2:
                semantic_query = parsed_sem
            # else: keep semantic_query = query (the original)
            
            # BM25 gets original query + semantic terms + synonyms for max recall
            syns = " ".join(intent_data.lexical_synonyms) if intent_data.lexical_synonyms else ""
            lexical_query = f"{query} {syns}".strip()

            # Build SQL safely
            clauses = []
            if intent_data.filters.file_type:
                clauses.append("i.source_type = ?")
                params.append(intent_data.filters.file_type)
            if intent_data.filters.created_after:
                clauses.append("i.created_at >= ?")
                params.append(f"{intent_data.filters.created_after} 00:00:00")
            if intent_data.filters.tags:
                for tag in intent_data.filters.tags:
                    clauses.append("i.tags ILIKE ?")
                    params.append(f"%{tag}%")
            
            if clauses:
                sql_filter = " AND ".join(clauses)

            # ── TEMPORAL BYPASS ──────────────────────────────────────
            # If the query has a date filter OR is purely metadata
            # (file_type/tags only, no real search content), bypass hybrid.
            has_date_filter = intent_data.filters.created_after is not None
            is_pure_metadata = (
                intent_data.intent == "metadata_filter"
                and clauses
                and (not parsed_sem or len(parsed_sem) < 3)
            )
            if has_date_filter or is_pure_metadata:
                logging.info(f"Temporal bypass: pure metadata query, skipping hybrid search.")
                rows = con.execute(
                    f"""
                    SELECT i.id AS item_id, i.title, i.tags, i.summary,
                           i.source_type, i.created_at
                    FROM items i
                    WHERE {sql_filter}
                    ORDER BY i.created_at DESC
                    LIMIT ?;
                    """,
                    params + [limit],
                ).fetchall()
                results = []
                for row in rows:
                    results.append({
                        "item_id": row[0],
                        "title": row[1] or "(sin título)",
                        "score": 1.0,
                        "snippet": f"📁 {row[4]} | 🏷️ {row[2] or '—'} | 📝 {row[3] or '—'}",
                    })
                return results

        except Exception as e:
            logging.warning(f"Intent parsing error: {e}")

    # ── 1. Generate query embedding ──────────────────────────────────
    query_vec = get_embedding(semantic_query)

    # ── 2. Semantic Search (Vector / HNSW) ───────────────────────────
    vector_str = "[" + ", ".join(map(str, query_vec)) + "]"

    try:
        if sql_filter.strip() == "1=1":
            semantic_rows = con.execute(
                f"""
                WITH top_embeddings AS (
                    SELECT e.item_id, e.content_id, ie.metadata_vector,
                           array_cosine_distance(e.vector, {vector_str}::FLOAT[{EMBEDDING_DIM}]) AS dist
                    FROM embeddings e
                    JOIN items i ON i.id = e.item_id
                    LEFT JOIN item_embeddings ie ON ie.item_id = e.item_id
                    ORDER BY array_cosine_distance(e.vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])
                    LIMIT {limit * 2}
                )
                SELECT t.item_id, c.body AS snippet, 
                       (1.0 - t.dist) AS chunk_score,
                       CASE WHEN t.metadata_vector IS NOT NULL 
                            THEN (1.0 - array_cosine_distance(t.metadata_vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])) 
                            ELSE 0.0 END AS meta_score,
                       {
                           f"CASE WHEN t.metadata_vector IS NOT NULL THEN (1.0 - array_cosine_distance(t.metadata_vector, {session_vector_str}::FLOAT[{EMBEDDING_DIM}])) ELSE 0.0 END"
                           if session_vector_str else "0.0"
                       } AS session_score
                FROM top_embeddings t
                JOIN content c ON c.id = t.content_id
                """
            ).fetchall()
        else:
            semantic_rows = con.execute(
                f"""
                WITH filtered_embeddings AS (
                    SELECT e.item_id, e.content_id, e.vector, ie.metadata_vector
                    FROM embeddings e
                    JOIN items i ON i.id = e.item_id
                    LEFT JOIN item_embeddings ie ON ie.item_id = e.item_id
                    WHERE {sql_filter}
                ),
                top_embeddings AS (
                    SELECT item_id, content_id, metadata_vector,
                           array_cosine_distance(vector, {vector_str}::FLOAT[{EMBEDDING_DIM}]) AS dist
                    FROM filtered_embeddings
                    ORDER BY array_cosine_distance(vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])
                    LIMIT {limit * 2}
                )
                SELECT t.item_id, c.body AS snippet, 
                       (1.0 - t.dist) AS chunk_score,
                       CASE WHEN t.metadata_vector IS NOT NULL 
                            THEN (1.0 - array_cosine_distance(t.metadata_vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])) 
                            ELSE 0.0 END AS meta_score,
                       {
                           f"CASE WHEN t.metadata_vector IS NOT NULL THEN (1.0 - array_cosine_distance(t.metadata_vector, {session_vector_str}::FLOAT[{EMBEDDING_DIM}])) ELSE 0.0 END"
                           if session_vector_str else "0.0"
                       } AS session_score
                FROM top_embeddings t
                JOIN content c ON c.id = t.content_id
                """, params
            ).fetchall()
    except Exception as e:
        logging.warning(f"Semantic search failed with filter '{sql_filter}': {e}. Falling back.")
        semantic_rows = con.execute(
            f"""
            WITH top_embeddings AS (
                SELECT e.item_id, e.content_id, ie.metadata_vector,
                       array_cosine_distance(e.vector, {vector_str}::FLOAT[{EMBEDDING_DIM}]) AS dist
                FROM embeddings e
                JOIN items i ON i.id = e.item_id
                LEFT JOIN item_embeddings ie ON ie.item_id = e.item_id
                ORDER BY array_cosine_distance(e.vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])
                LIMIT {limit * 2}
            )
            SELECT t.item_id, c.body AS snippet, 
                   (1.0 - t.dist) AS chunk_score,
                   CASE WHEN t.metadata_vector IS NOT NULL 
                        THEN (1.0 - array_cosine_distance(t.metadata_vector, {vector_str}::FLOAT[{EMBEDDING_DIM}])) 
                        ELSE 0.0 END AS meta_score,
                   {
                       f"CASE WHEN t.metadata_vector IS NOT NULL THEN (1.0 - array_cosine_distance(t.metadata_vector, {session_vector_str}::FLOAT[{EMBEDDING_DIM}])) ELSE 0.0 END"
                       if session_vector_str else "0.0"
                   } AS session_score
            FROM top_embeddings t
            JOIN content c ON c.id = t.content_id
            """
        ).fetchall()

    # ── 3. Lexical Search (FTS / BM25) ───────────────────────────────
    safe_query = lexical_query.replace("'", "''")
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
                params + [limit * 2],
            ).fetchall()
    except Exception as e:
        logging.warning(f"FTS Search failed: {e}")
        lex_rows = []

    # ── 4. Deduplicate per item_id ───────────────────────────────────
    semantic: dict[int, dict] = {}
    for item_id, snippet, chunk_score, meta_score, session_score in semantic_rows:
        base_sem = (chunk_score * 0.7 + meta_score * 0.3) if meta_score > 0.0 else chunk_score
        
        # Boost up to 20% if there is strong alignment with recently viewed items
        if session_score > 0.4:
            base_sem += (session_score - 0.4) * 0.4
            
        if item_id not in semantic or base_sem > semantic[item_id]["sem_score"]:
            semantic[item_id] = {"snippet": snippet, "sem_score": base_sem}

    lexical: dict[int, dict] = {}
    for item_id, snippet, lex_score in lex_rows:
        lex_score = lex_score or 0.0
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
        min_lex, lex_range = 0.0, 1.0

    for item_id in all_ids:
        s_score = semantic.get(item_id, {}).get("sem_score", 0.0)
        
        raw_l_score = lexical.get(item_id, {}).get("lex_score", 0.0)
        if lexical and raw_l_score is not None:
            l_score_norm = (raw_l_score - min_lex) / lex_range
        else:
            l_score_norm = 0.0

        # We weight semantic search slightly higher (0.6) than lexical (0.4)
        combined = (s_score * 0.6) + (l_score_norm * 0.4)

        # Pick the best snippet (prefer semantic if available, else lexical)
        snippet = semantic.get(item_id, {}).get("snippet") or lexical.get(item_id, {}).get("snippet", "")

        results.append({
            "item_id": item_id,
            "score": combined,
            "snippet": snippet
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top_results = results[:limit]

    # Fetch titles
    if top_results:
        placeholders = ",".join("?" for _ in top_results)
        ids = [r["item_id"] for r in top_results]
        titles = con.execute(f"SELECT id, title FROM items WHERE id IN ({placeholders})", ids).fetchall()
        title_map = {row[0]: row[1] for row in titles}
        for r in top_results:
            r["title"] = title_map.get(r["item_id"], "(No title)")

    return top_results