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
    """Return (or create) the DuckDB connection and ensure VSS and FTS are loaded."""
    global _con
    if _con is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        
        _con = duckdb.connect(DB_PATH)
        _con.execute("INSTALL vss; LOAD vss;")
        _con.execute("INSTALL fts; LOAD fts;")
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

    # MODIFICADO: Se añade file_hash
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY DEFAULT nextval('item_seq'),
            source_path TEXT,
            source_type TEXT DEFAULT 'text',
            file_hash   TEXT,
            title       TEXT,
            tags        TEXT,
            summary     TEXT,
            file_mtime  TIMESTAMP,
            created_at  TIMESTAMP DEFAULT now(),
            enriched    BOOLEAN DEFAULT FALSE
        );
    """)

    # Migración: Si la tabla ya existía, intentamos añadir las columnas nuevas.
    for col_def in [
        "ADD COLUMN file_hash TEXT",
        "ADD COLUMN file_mtime TIMESTAMP",
        "ADD COLUMN created_at TIMESTAMP DEFAULT now()",
        "ADD COLUMN enriched BOOLEAN DEFAULT FALSE",
    ]:
        try:
            con.execute(f"ALTER TABLE items {col_def};")
        except Exception:
            pass

    con.execute(f"""
        CREATE TABLE IF NOT EXISTS item_embeddings (
            item_id INTEGER PRIMARY KEY REFERENCES items(id),
            metadata_vector FLOAT[{EMBEDDING_DIM}]
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

    con.execute("CREATE SEQUENCE IF NOT EXISTS meta_seq START 1;")
    con.execute("""
        CREATE TABLE IF NOT EXISTS chunk_metadata (
            id               INTEGER PRIMARY KEY DEFAULT nextval('meta_seq'),
            content_id       INTEGER REFERENCES content(id),
            titulo           TEXT,
            resumen          TEXT,
            tipo_contenido   TEXT,
            idioma           TEXT,
            tags             JSON,
            terminos_clave   JSON,
            densidad         FLOAT,
            score_relevancia FLOAT,
            entidades        JSON,
            preguntas        JSON,
            contexto         TEXT,
            posicion         TEXT
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

    con.execute("CREATE SEQUENCE IF NOT EXISTS session_seq START 1;")
    con.execute("""
        CREATE TABLE IF NOT EXISTS session_history (
            id        INTEGER PRIMARY KEY DEFAULT nextval('session_seq'),
            item_id   INTEGER REFERENCES items(id),
            viewed_at TIMESTAMP DEFAULT now()
        );
    """)


def create_hnsw_index(con: duckdb.DuckDBPyConnection | None = None, force_rebuild: bool = False) -> None:
    """Create the HNSW index on embeddings."""
    if con is None:
        con = get_connection()
    if force_rebuild:
        try:
            con.execute("DROP INDEX IF EXISTS emb_idx;")
        except Exception:
            pass
    try:
        con.execute(
            "CREATE INDEX IF NOT EXISTS emb_idx "
            "ON embeddings USING HNSW(vector) WITH (metric = 'cosine');"
        )
    except duckdb.CatalogException:
        pass  # index already exists


def create_fts_index(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """Create or recreate the FTS index on content."""
    if con is None:
        con = get_connection()
    try:
        con.execute("PRAGMA drop_fts_index('content');")
    except Exception:
        pass
    con.execute("PRAGMA create_fts_index('content', 'id', 'body');")


# ── CRUD helpers ─────────────────────────────────────────────────────

def insert_item(source_path: str, source_type: str = "text", file_hash: str = None, file_mtime: float = None) -> int:
    """Insert a new item and return its id."""
    con = get_connection()
    if file_mtime is not None:
        result = con.execute(
            "INSERT INTO items (source_path, source_type, file_hash, file_mtime) VALUES (?, ?, ?, to_timestamp(?)) RETURNING id;",
            [source_path, source_type, file_hash, file_mtime],
        ).fetchone()
    else:
        result = con.execute(
            "INSERT INTO items (source_path, source_type, file_hash) VALUES (?, ?, ?) RETURNING id;",
            [source_path, source_type, file_hash],
        ).fetchone()
    return result[0]


def get_item_by_hash(file_hash: str) -> dict | None:
    """Fetch a single item by its hash."""
    con = get_connection()
    row = con.execute("SELECT * FROM items WHERE file_hash = ?;", [file_hash]).fetchone()
    if row is None:
        return None
    return _row_to_dict(con, row)


def insert_content(item_id: int, chunk_index: int, body: str) -> int:
    """Insert a content chunk and return its id."""
    con = get_connection()
    result = con.execute(
        "INSERT INTO content (item_id, chunk_index, body) VALUES (?, ?, ?) RETURNING id;",
        [item_id, chunk_index, body],
    ).fetchone()
    return result[0]


def insert_embedding(content_id: int, item_id: int, vector: list[float]) -> int:
    """Insert an embedding and return its id. Includes self-healing for HNSW index corruption."""
    con = get_connection()
    try:
        result = con.execute(
            "INSERT INTO embeddings (content_id, item_id, vector) VALUES (?, ?, ?) RETURNING id;",
            [content_id, item_id, vector],
        ).fetchone()
        return result[0]
    except Exception as e:
        if "Duplicate keys" in str(e) or "HNSW" in str(e) or "Constraint Error" in str(e):
            print("Detected HNSW index corruption during insertion. Auto-rebuilding index and retrying...")
            create_hnsw_index(con, force_rebuild=True)
            result = con.execute(
                "INSERT INTO embeddings (content_id, item_id, vector) VALUES (?, ?, ?) RETURNING id;",
                [content_id, item_id, vector],
            ).fetchone()
            return result[0]
        raise e

def insert_chunk_metadata(content_id: int, meta: dict) -> None:
    """Insert JSON metadata parsed from LLM for a specific chunk."""
    con = get_connection()
    import json
    con.execute(
        """
        INSERT INTO chunk_metadata (
            content_id, titulo, resumen, tipo_contenido, idioma,
            tags, terminos_clave, densidad, score_relevancia,
            entidades, preguntas, contexto, posicion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            content_id,
            meta.get("titulo"),
            meta.get("resumen"),
            meta.get("tipo_contenido"),
            meta.get("idioma"),
            json.dumps(meta.get("tags", [])),
            json.dumps(meta.get("terminos_clave_ponderados", {})),
            meta.get("densidad_tematica"),
            meta.get("score_relevancia_chunk"),
            json.dumps(meta.get("entidades", {})),
            json.dumps(meta.get("preguntas_que_responde", [])),
            meta.get("contexto_necesario"),
            meta.get("chunk_posicion")
        ]
    )


def insert_connection(item_a: int, item_b: int, score: float) -> None:
    """Insert or update a connection between two items."""
    con = get_connection()
    a, b = min(item_a, item_b), max(item_a, item_b)
    con.execute(
        """
        INSERT INTO connections (item_a, item_b, score) VALUES (?, ?, ?)
        ON CONFLICT (item_a, item_b) DO UPDATE SET score = EXCLUDED.score;
        """,
        [a, b, score],
    )


def update_item_enrichment(item_id: int, title: str, tags: str, summary: str, metadata_vector: list[float] | None = None) -> None:
    """Update an item with LLM-generated enrichment data."""
    con = get_connection()
    if metadata_vector:
        con.execute(
            """
            INSERT INTO item_embeddings (item_id, metadata_vector) 
            VALUES (?, ?) 
            ON CONFLICT (item_id) DO UPDATE SET metadata_vector = EXCLUDED.metadata_vector;
            """,
            [item_id, metadata_vector]
        )
    con.execute(
        "UPDATE items SET title = ?, tags = ?, summary = ?, enriched = TRUE WHERE id = ?;",
        [title, tags, summary, item_id],
    )

def add_tag_to_item(item_id: int, new_tag: str) -> bool:
    """Append a tag to an item's tags column."""
    con = get_connection()
    try:
        item = get_item(item_id)
        if not item:
            return False
            
        current_tags = item.get("tags") or ""
        tag_list = [t.strip() for t in current_tags.split(",") if t.strip()]
        if new_tag not in tag_list:
            tag_list.append(new_tag)
            
        new_tags_str = ", ".join(tag_list)
        con.execute("UPDATE items SET tags = ? WHERE id = ?;", [new_tags_str, item_id])
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

def delete_item(item_id: int) -> bool:
    """Delete an item and all its associated data from the database."""
    con = get_connection()
    try:
        # Delete dependencies first
        con.execute("DELETE FROM session_history WHERE item_id = ?;", [item_id])
        con.execute("DELETE FROM item_embeddings WHERE item_id = ?;", [item_id])
        con.execute("DELETE FROM connections WHERE item_a = ? OR item_b = ?;", [item_id, item_id])
        
        # We need content_ids to delete embeddings and chunk_metadata
        content_ids = [r[0] for r in con.execute("SELECT id FROM content WHERE item_id = ?;", [item_id]).fetchall()]
        if content_ids:
            placeholders = ",".join(["?"] * len(content_ids))
            con.execute(f"DELETE FROM embeddings WHERE content_id IN ({placeholders});", content_ids)
            con.execute(f"DELETE FROM chunk_metadata WHERE content_id IN ({placeholders});", content_ids)
            
        con.execute("DELETE FROM content WHERE item_id = ?;", [item_id])
        
        # Delete item itself
        result = con.execute("DELETE FROM items WHERE id = ?;", [item_id])
        deleted = result.rowcount > 0
        
        # Rebuild indexes since content was removed
        if deleted:
            create_hnsw_index(con, force_rebuild=True)
            create_fts_index(con)
            
        return deleted
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False

def _row_to_dict(cursor, row: tuple) -> dict:
    """Convert a single duckdb row to a dict using cursor description."""
    if row is None:
        return {}
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


def _rows_to_dicts(cursor, rows: list[tuple]) -> list[dict]:
    """Convert multiple duckdb rows to a list of dicts using cursor description."""
    if not rows:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def get_item(item_id: int) -> dict | None:
    """Fetch a single item by id."""
    con = get_connection()
    row = con.execute("SELECT * FROM items WHERE id = ?;", [item_id]).fetchone()
    if row is None:
        return None
    return _row_to_dict(con, row)


def get_items_by_ids(item_ids: list[int]) -> list[dict]:
    """Fetch multiple items by their ids."""
    if not item_ids:
        return []
    con = get_connection()
    placeholders = ",".join(["?"] * len(item_ids))
    rows = con.execute(f"SELECT * FROM items WHERE id IN ({placeholders});", item_ids).fetchall()
    return _rows_to_dicts(con, rows)


def get_all_items() -> list[dict]:
    """List all items."""
    con = get_connection()
    rows = con.execute("SELECT * FROM items ORDER BY created_at DESC;").fetchall()
    return _rows_to_dicts(con, rows)


def get_chunks_for_item(item_id: int) -> list[dict]:
    """Return all text chunks for an item, ordered by chunk_index, including metadata if any."""
    con = get_connection()
    rows = con.execute(
        """
        SELECT c.*, m.titulo, m.resumen, m.score_relevancia
        FROM content c
        LEFT JOIN chunk_metadata m ON m.content_id = c.id
        WHERE c.item_id = ?
        ORDER BY c.chunk_index;
        """,
        [item_id],
    ).fetchall()
    return _rows_to_dicts(con, rows)


def get_embeddings_for_item(item_id: int) -> list[list[float]]:
    """Return all embedding vectors for an item."""
    con = get_connection()
    rows = con.execute(
        "SELECT vector FROM embeddings WHERE item_id = ?;", [item_id]
    ).fetchall()
    return [list(r[0]) for r in rows]


def log_item_view(item_id: int) -> None:
    """Log an item view to the session history."""
    con = get_connection()
    con.execute("INSERT INTO session_history (item_id) VALUES (?);", [item_id])

def get_recent_session_vector(limit: int = 5) -> list[float] | None:
    """Retrieve an average normalized metadata vector for the most recently viewed items."""
    con = get_connection()
    rows = con.execute(
        f"""
        SELECT ie.metadata_vector
        FROM session_history sh
        JOIN item_embeddings ie ON ie.item_id = sh.item_id
        WHERE ie.metadata_vector IS NOT NULL
        ORDER BY sh.viewed_at DESC
        LIMIT {limit};
        """
    ).fetchall()
    
    if not rows:
        return None
        
    vecs = [r[0] for r in rows]
    n = len(vecs)
    dim = len(vecs[0])
    avg_vec = [sum(vec[i] for vec in vecs) / n for i in range(dim)]
    
    import math
    norm = math.sqrt(sum(v * v for v in avg_vec))
    if norm > 0:
        avg_vec = [v / norm for v in avg_vec]
    return avg_vec