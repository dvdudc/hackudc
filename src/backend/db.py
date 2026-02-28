"""
Black Vault — Database layer.
Single DuckDB file with VSS extension for vector search.
Tables: items, content, embeddings, connections.
"""

from __future__ import annotations

import duckdb
from pathlib import Path
from backend.config import DB_PATH, EMBEDDING_DIM

# ── Connection singleton ─────────────────────────────────────────────
_con: duckdb.DuckDBPyConnection | None = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return (or create) the DuckDB connection and ensure VSS is loaded."""
    global _con
    if _con is None:
        _con = duckdb.connect(DB_PATH)
        _con.execute("INSTALL vss; LOAD vss;")
        _con.execute("SET hnsw_enable_experimental_persistence = true;")
        init_schema(_con)
    return _con


def close():
    """Close the connection cleanly."""
    global _con
    if _con is not None:
        _con.close()
        _con = None


# ── Schema ───────────────────────────────────────────────────────────

def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create tables and sequences if they don't exist yet."""

    con.execute("CREATE SEQUENCE IF NOT EXISTS item_seq START 1;")
    con.execute("CREATE SEQUENCE IF NOT EXISTS content_seq START 1;")
    con.execute("CREATE SEQUENCE IF NOT EXISTS emb_seq START 1;")

    con.execute(f"""
        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY DEFAULT nextval('item_seq'),
            source_path TEXT,
            source_type TEXT DEFAULT 'text',
            title       TEXT,
            tags        TEXT,
            summary     TEXT,
            created_at  TIMESTAMP DEFAULT now(),
            enriched    BOOLEAN DEFAULT FALSE
        );
    """)

    con.execute(f"""
        CREATE TABLE IF NOT EXISTS content (
            id          INTEGER PRIMARY KEY DEFAULT nextval('content_seq'),
            item_id     INTEGER REFERENCES items(id),
            chunk_index INTEGER,
            body        TEXT
        );
    """)

    con.execute(f"""
        CREATE TABLE IF NOT EXISTS embeddings (
            id         INTEGER PRIMARY KEY DEFAULT nextval('emb_seq'),
            content_id INTEGER REFERENCES content(id),
            item_id    INTEGER REFERENCES items(id),
            vector     FLOAT[{EMBEDDING_DIM}]
        );
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS connections (
            item_a INTEGER REFERENCES items(id),
            item_b INTEGER REFERENCES items(id),
            score  FLOAT,
            PRIMARY KEY (item_a, item_b)
        );
    """)


def create_hnsw_index(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """Create the HNSW index on embeddings. Safe to call multiple times."""
    if con is None:
        con = get_connection()
    try:
        con.execute(
            "CREATE INDEX IF NOT EXISTS emb_idx "
            "ON embeddings USING HNSW(vector) WITH (metric = 'cosine');"
        )
    except duckdb.CatalogException:
        pass  # index already exists


# ── CRUD helpers ─────────────────────────────────────────────────────

def insert_item(source_path: str, source_type: str = "text") -> int:
    """Insert a new item and return its id."""
    con = get_connection()
    result = con.execute(
        "INSERT INTO items (source_path, source_type) VALUES (?, ?) RETURNING id;",
        [source_path, source_type],
    ).fetchone()
    return result[0]


def insert_content(item_id: int, chunk_index: int, body: str) -> int:
    """Insert a content chunk and return its id."""
    con = get_connection()
    result = con.execute(
        "INSERT INTO content (item_id, chunk_index, body) VALUES (?, ?, ?) RETURNING id;",
        [item_id, chunk_index, body],
    ).fetchone()
    return result[0]


def insert_embedding(content_id: int, item_id: int, vector: list[float]) -> int:
    """Insert an embedding and return its id."""
    con = get_connection()
    result = con.execute(
        "INSERT INTO embeddings (content_id, item_id, vector) VALUES (?, ?, ?) RETURNING id;",
        [content_id, item_id, vector],
    ).fetchone()
    return result[0]


def insert_connection(item_a: int, item_b: int, score: float) -> None:
    """Insert or update a connection between two items."""
    con = get_connection()
    # Ensure item_a < item_b for consistency
    a, b = min(item_a, item_b), max(item_a, item_b)
    con.execute(
        """
        INSERT INTO connections (item_a, item_b, score) VALUES (?, ?, ?)
        ON CONFLICT (item_a, item_b) DO UPDATE SET score = EXCLUDED.score;
        """,
        [a, b, score],
    )


def update_item_enrichment(item_id: int, title: str, tags: str, summary: str) -> None:
    """Update an item with LLM-generated enrichment data."""
    con = get_connection()
    con.execute(
        "UPDATE items SET title = ?, tags = ?, summary = ?, enriched = TRUE WHERE id = ?;",
        [title, tags, summary, item_id],
    )


def get_item(item_id: int) -> dict | None:
    """Fetch a single item by id."""
    con = get_connection()
    row = con.execute("SELECT * FROM items WHERE id = ?;", [item_id]).fetchone()
    if row is None:
        return None
    cols = [d[0] for d in con.description]
    return dict(zip(cols, row))


def get_all_items() -> list[dict]:
    """List all items."""
    con = get_connection()
    rows = con.execute("SELECT * FROM items ORDER BY created_at DESC;").fetchall()
    cols = [d[0] for d in con.description]
    return [dict(zip(cols, r)) for r in rows]


def get_chunks_for_item(item_id: int) -> list[dict]:
    """Return all text chunks for an item, ordered by chunk_index."""
    con = get_connection()
    rows = con.execute(
        "SELECT * FROM content WHERE item_id = ? ORDER BY chunk_index;",
        [item_id],
    ).fetchall()
    cols = [d[0] for d in con.description]
    return [dict(zip(cols, r)) for r in rows]


def get_embeddings_for_item(item_id: int) -> list[list[float]]:
    """Return all embedding vectors for an item."""
    con = get_connection()
    rows = con.execute(
        "SELECT vector FROM embeddings WHERE item_id = ?;", [item_id]
    ).fetchall()
    return [list(r[0]) for r in rows]
