"""
Black Vault — Connections module.
Finds semantically related items using mean embedding cosine similarity.
"""

from __future__ import annotations

import numpy as np

from backend.config import CONNECTION_THRESHOLD
from backend import db


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    """Compute the mean of a list of embedding vectors."""
    if not vectors:
        return []
    return np.mean(vectors, axis=0).tolist()


def find_connections(item_id: int, threshold: float | None = None) -> int:
    """
    Compare the new item against all existing items and store connections
    for pairs whose cosine similarity exceeds the threshold.

    Returns the number of connections created.
    """
    if threshold is None:
        threshold = CONNECTION_THRESHOLD

    vecs = db.get_embeddings_for_item(item_id)
    if not vecs:
        return 0

    mean_new = np.array(_mean_vector(vecs))

    con = db.get_connection()
    other_ids = con.execute(
        "SELECT DISTINCT item_id FROM embeddings WHERE item_id != ?;",
        [item_id],
    ).fetchall()

    count = 0
    for (other_id,) in other_ids:
        other_vecs = db.get_embeddings_for_item(other_id)
        if not other_vecs:
            continue
        mean_other = np.array(_mean_vector(other_vecs))

        # Cosine similarity
        dot = float(np.dot(mean_new, mean_other))
        norm = float(np.linalg.norm(mean_new) * np.linalg.norm(mean_other))
        if norm == 0:
            continue
        sim = dot / norm

        if sim >= threshold:
            db.insert_connection(item_id, other_id, round(sim, 4))
            count += 1

    if count:
        print(f"🔗 {count} connection(s) found for item #{item_id}")
    return count


def get_connections(item_id: int) -> list[dict]:
    """Return items connected to the given item_id."""
    con = db.get_connection()
    rows = con.execute(
        """
        SELECT
            CASE WHEN item_a = ? THEN item_b ELSE item_a END AS related_id,
            score
        FROM connections
        WHERE item_a = ? OR item_b = ?
        ORDER BY score DESC;
        """,
        [item_id, item_id, item_id],
    ).fetchall()

    results = []
    for related_id, score in rows:
        item = db.get_item(related_id)
        results.append({
            "item_id": related_id,
            "title": item.get("title", "(sin título)") if item else "(desconocido)",
            "source_path": item.get("source_path", "") if item else "",
            "score": score,
        })
    return results
