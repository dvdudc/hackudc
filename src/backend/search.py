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

    # 2. Lexical Search
    lexical: dict[int, dict] = {}
    words = [w.strip() for w in query.split() if len(w.strip()) > 2]
    if words:
        like_clauses = " OR ".join(["body ILIKE ?" for _ in words])
        like_params = [f"%{w}%" for w in words]
        lex_rows = con.execute(
            f"SELECT c.item_id, c.body AS snippet FROM content c WHERE {like_clauses} LIMIT ?;",
            like_params + [limit * 2],
        ).fetchall()
        for item_id, snippet in lex_rows:
            if item_id not in lexical:
                lexical[item_id] = {"snippet": snippet, "lex_score": 1.0}

    # 3. Merge & Rank
    all_ids = set(semantic.keys()) | set(lexical.keys())
    results = []

    for item_id in all_ids:
        sem = semantic.get(item_id, {}).get("sem_score", 0.0)
        lex = 1.0 if item_id in lexical else 0.0
        combined = 0.7 * sem + 0.3 * lex
        
        snippet = semantic.get(item_id, {}).get("snippet") or lexical.get(item_id, {}).get("snippet", "")
        
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