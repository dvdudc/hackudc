"""
Black Vault — Ingestion pipeline.
Read text file → verify MIME → check duplicate → chunk → embed → store.
Supports buffered parallel ingestion via IngestQueue.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import threading
import logging
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

# ── Thread-safety lock for DuckDB writes ─────────────────────────────
_db_lock = threading.Lock()


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


def ingest_file(path: str, parsed_text: str, *, _rebuild_indexes: bool = True) -> int:
    """Ingest a single file into the vault.

    Args:
        path: Path to the file to ingest.
        parsed_text: String representing the extracted/parsed text from the file (handles OCR in CLI).
        _rebuild_indexes: If True (default), rebuild HNSW and FTS indexes
            after insertion. Set to False when batch-ingesting to defer
            index rebuilding to the end.

    Returns:
        The item_id of the newly ingested item.
    """
    start_time = time.time()
    filepath = Path(path).resolve()
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    # 1. Calcular Hash
    file_hash = calculate_md5(filepath)
    
    # 2. Check Duplicados (Early Exit) — read under lock
    with _db_lock:
        existing_item = db.get_item_by_hash(file_hash)
    if existing_item:
        msg = f"Duplicate detected: {filepath.name} already exists as Item #{existing_item['id']}"
        print(f"⚠️  {msg}")
        raise DuplicateError(msg, existing_item['id'])

    # 3. MIME Check
    mime = detect_mime(str(filepath))
    if not (mime.startswith("text/") or mime.startswith("image/") or mime == "application/pdf"):
        raise ValueError(f"Unsupported file type: {mime}. Only text/*, image/* and application/pdf supported.")

    # 4. Use provided parsed text
    text = parsed_text
    if not text.strip():
        raise ValueError("File or image is empty/no text could be extracted.")

    # 5. Chunk
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )
    chunks = splitter.split_text(text)
    print(f"📄 {filepath.name}: {len(chunks)} chunks generated.")

    # 6. Embed (I/O-bound — runs outside lock)
    print("🧠 Generating embeddings...")
    vectors = get_embeddings_batch(chunks)

    # 7. Store — all DB writes under lock
    with _db_lock:
        mtime = os.path.getmtime(str(filepath))
        source_type = "pdf" if mime == "application/pdf" else "image" if mime.startswith("image/") else "text"
        item_id = db.insert_item(source_path=str(filepath), source_type=source_type, file_hash=file_hash, file_mtime=mtime)

        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            content_id = db.insert_content(item_id=item_id, chunk_index=i, body=chunk)
            db.insert_embedding(content_id=content_id, item_id=item_id, vector=vec)

        if _rebuild_indexes:
            db.create_hnsw_index()
            db.create_fts_index()

    # 8. Enrichment & Connections (I/O-bound — runs outside lock)
    from backend.enrich import enrich_item
    from backend.connections import find_connections

    print("🤖 Running AI enrichment & connection finding...")
    with _db_lock:
        enrich_item(item_id)
        find_connections(item_id)

    elapsed_time = time.time() - start_time
    print(f"⏱️  Ingestion finished in {elapsed_time:.2f} seconds.")
    logging.info(f"Ingested {filepath.name} in {elapsed_time:.2f} seconds.")

    return item_id


# ── Batch result container ───────────────────────────────────────────

@dataclass
class IngestResult:
    """Resultado de la ingesta de un solo archivo."""
    path: str
    success: bool
    item_id: int | None = None
    error: str | None = None
    is_duplicate: bool = False
    duplicate_id: int | None = None


# ── IngestQueue — buffered parallel ingestion ────────────────────────

class IngestQueue:
    """Cola de ingesta con buffer y procesamiento en paralelo.

    Usage:
        queue = IngestQueue(max_workers=4)
        futures = queue.submit_batch(["file1.txt", "file2.txt", "file3.txt"])
        results = queue.drain()   # espera a que terminen todos
        queue.shutdown()
    """

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: list[Future] = []
        self._lock = threading.Lock()

    # ── Submit methods ───────────────────────────────────────────────

    def submit(self, path: str) -> Future:
        """Encola un archivo para ingestión. Devuelve un Future."""
        future = self._executor.submit(self._safe_ingest, path)
        with self._lock:
            self._futures.append(future)
        return future

    def submit_batch(self, paths: list[str]) -> list[Future]:
        """Encola una lista de archivos. Devuelve lista de Futures."""
        futures = []
        for p in paths:
            futures.append(self.submit(p))
        return futures

    # ── Drain & shutdown ─────────────────────────────────────────────

    def drain(self) -> list[IngestResult]:
        """Espera a que todos los jobs terminen, reconstruye índices
        una sola vez, y devuelve los resultados."""
        with self._lock:
            pending = list(self._futures)
            self._futures.clear()

        results: list[IngestResult] = []
        for f in pending:
            results.append(f.result())

        # Rebuild indexes once after the full batch
        try:
            with _db_lock:
                db.create_hnsw_index()
                db.create_fts_index()
        except Exception as e:
            logging.warning(f"Index rebuild after batch failed: {e}")

        return results

    def shutdown(self):
        """Cierra el pool de forma limpia."""
        self._executor.shutdown(wait=True)

    # ── Internal ─────────────────────────────────────────────────────

    @staticmethod
    def _safe_ingest(path: str) -> IngestResult:
        """Wrapper que captura excepciones y devuelve un IngestResult."""
        try:
            # We must recreate the text extraction logic for batch processing, as the current CLI passes it in.
            import mimetypes
            mime, _ = mimetypes.guess_type(str(path))
            mime = mime or "application/octet-stream"
            
            if mime.startswith("image/"):
                from backend.ocr import extract_text_from_image
                parsed_text = extract_text_from_image(str(path))
            else:
                parsed_text = Path(path).read_text(encoding="utf-8")
                
            item_id = ingest_file(path, parsed_text=parsed_text, _rebuild_indexes=False)
            return IngestResult(path=path, success=True, item_id=item_id)
        except DuplicateError as e:
            return IngestResult(
                path=path, success=True,
                is_duplicate=True, duplicate_id=e.existing_id,
            )
        except Exception as e:
            return IngestResult(path=path, success=False, error=str(e))


# ── Module-level singleton ───────────────────────────────────────────
_ingest_queue: IngestQueue | None = None
_queue_lock = threading.Lock()


def get_ingest_queue(max_workers: int = 4) -> IngestQueue:
    """Devuelve (o crea) la instancia global de IngestQueue."""
    global _ingest_queue
    with _queue_lock:
        if _ingest_queue is None:
            _ingest_queue = IngestQueue(max_workers=max_workers)
        return _ingest_queue