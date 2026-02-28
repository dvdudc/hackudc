"""
Black Vault — Ingestion pipeline.
Read text file → verify MIME → check duplicate → chunk → embed → store.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
from pathlib import Path
import time
import logging
from google import genai
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import GEMINI_API_KEY, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP
from backend import db



class DuplicateError(Exception):
    """Excepción personalizada para indicar que el archivo ya existe."""
    def __init__(self, message, existing_id):
        super().__init__(message)
        self.existing_id = existing_id

from backend.llm import get_client


def get_embedding(text: str) -> list[float]:
    result = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return list(result.embeddings[0].values)


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    result = get_client().models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
    )
    return [list(e.values) for e in result.embeddings]


def detect_mime(path: str) -> str:
    """Detect MIME type using built-in mimetypes library."""
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type or "application/octet-stream"


def calculate_md5(path: Path) -> str:
    """Calcula hash MD5 eficiente."""
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def ingest_file(path: str) -> int:
    start_time = time.time()
    filepath = Path(path).resolve()
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    # 1. Calcular Hash
    file_hash = calculate_md5(filepath)
    
    # 2. Check Duplicados (Early Exit)
    existing_item = db.get_item_by_hash(file_hash)
    if existing_item:
        msg = f"Duplicate detected: {filepath.name} already exists as Item #{existing_item['id']}"
        print(f"⚠️  {msg}")
        # LANZAMOS LA EXCEPCIÓN EN LUGAR DE RETORNAR SILENCIOSAMENTE
        raise DuplicateError(msg, existing_item['id'])
    

    #print('hola')

    # 3. MIME Check
    mime = detect_mime(str(filepath))
    if not mime.startswith("text/"):
        raise ValueError(f"Unsupported file type: {mime}. Only text/* supported.")

    # 4. Read
    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError("File encoding error. Must be UTF-8.")
        
    if not text.strip():
        raise ValueError("File is empty.")

    # 5. Chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )
    chunks = splitter.split_text(text)
    print(f"📄 {filepath.name}: {len(chunks)} chunks generated.")

    # 6. Embed
    print("🧠 Generating embeddings...")
    vectors = get_embeddings_batch(chunks)

    # ── 5. Store ─────────────────────────────────────────────────────
    mtime = os.path.getmtime(str(filepath))
    item_id = db.insert_item(source_path=str(filepath), source_type="text", file_hash=file_hash, file_mtime=mtime)

    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        content_id = db.insert_content(item_id=item_id, chunk_index=i, body=chunk)
        db.insert_embedding(content_id=content_id, item_id=item_id, vector=vec)

    # Rebuild indexes after inserting new data
    db.create_hnsw_index()
    db.create_fts_index()

    # 8. Enrichment & Connections
    from backend.enrich import enrich_item
    from backend.connections import find_connections

    print("🤖 Running AI enrichment & connection finding...")
    enrich_item(item_id)
    find_connections(item_id)

    elapsed_time = time.time() - start_time
    print(f"⏱️  Ingestion finished in {elapsed_time:.2f} seconds.")
    logging.info(f"Ingested {filepath.name} in {elapsed_time:.2f} seconds.")

    return item_id