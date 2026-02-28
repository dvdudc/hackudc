"""
Black Vault — Ingestion pipeline.
Read text file → verify MIME → chunk → embed → store.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from google import genai
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import GEMINI_API_KEY, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP
from backend import db


_client: genai.Client | None = None


def _genai() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def get_embedding(text: str) -> list[float]:
    """Get the embedding vector for a single text string."""
    result = _genai().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return list(result.embeddings[0].values)


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embeddings for a batch of texts in a single API call."""
    if not texts:
        return []
    result = _genai().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
    )
    return [list(e.values) for e in result.embeddings]


def detect_mime(path: str) -> str:
    """Detect MIME type using built-in mimetypes."""
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or "application/octet-stream"


def ingest_file(path: str) -> int:
    """
    Ingest a text file into Black Vault.

    1. Verify it's a text file (MIME type text/*)
    2. Read contents
    3. Chunk with RecursiveCharacterTextSplitter
    4. Embed each chunk via Gemini
    5. Store item + content + embeddings in DuckDB
    6. Trigger enrichment & connection finding

    Returns the new item id.
    """
    filepath = Path(path).resolve()
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # ── 1. MIME check ────────────────────────────────────────────────
    mime = detect_mime(str(filepath))
    if not mime.startswith("text/"):
        raise ValueError(
            f"Unsupported file type: {mime}. "
            f"MVP only supports text/* files."
        )

    # ── 2. Read ──────────────────────────────────────────────────────
    text = filepath.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("File is empty.")

    # ── 3. Chunk ─────────────────────────────────────────────────────
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )
    chunks = splitter.split_text(text)
    print(f"📄 {filepath.name}: {len(chunks)} chunk(s)")

    # ── 4. Embed ─────────────────────────────────────────────────────
    vectors = get_embeddings_batch(chunks)

    # ── 5. Store ─────────────────────────────────────────────────────
    item_id = db.insert_item(source_path=str(filepath), source_type="text")

    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        content_id = db.insert_content(item_id=item_id, chunk_index=i, body=chunk)
        db.insert_embedding(content_id=content_id, item_id=item_id, vector=vec)

    # Rebuild HNSW index after inserting new vectors
    db.create_hnsw_index()

    print(f"✅ Stored as item #{item_id}")

    # ── 6. Enrichment & connections (inline for MVP) ─────────────────
    from backend.enrich import enrich_item
    from backend.connections import find_connections

    enrich_item(item_id)
    find_connections(item_id)

    return item_id
