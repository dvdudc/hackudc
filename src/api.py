import os
import shutil
import mimetypes
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import tempfile

from backend.ingest import ingest_file, DuplicateError, get_ingest_queue, IngestResult
from backend.search import search as search_docs
from backend.db import get_item, get_chunks_for_item
from backend.connections import get_connections

app = FastAPI(title="Black Vault API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DocumentResult(BaseModel):
    id: str
    title: str
    summary: str
    tags: List[str]
    snippet: str
    score: Optional[float] = None

class DocumentDetail(DocumentResult):
    fullText: str
    connections: List[DocumentResult]

class IngestResponse(BaseModel):
    success: bool
    message: str
    documentId: str

class BatchIngestItemResponse(BaseModel):
    filename: str
    success: bool
    message: str
    documentId: Optional[str] = None

class BatchIngestResponse(BaseModel):
    total: int
    ingested: int
    duplicates: int
    errors: int
    results: List[BatchIngestItemResponse]

@app.get("/search", response_model=List[DocumentResult])
def api_search(q: str):
    if not q.strip():
        return []
    
    results = search_docs(q, limit=10)
    docs = []
    for r in results:
        # Some tags might be None or empty string
        tags_str = r.get("tags") or ""
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        
        docs.append(DocumentResult(
            id=str(r["item_id"]),
            title=r.get("title") or "Unknown Title",
            summary=r.get("summary") or "",
            tags=tags,
            snippet=r.get("snippet") or "",
            score=r.get("score")
        ))
    return docs

@app.post("/ingest", response_model=IngestResponse)
def api_ingest(file: UploadFile = File(...)):
    # Save to a temporary file for ingestion
    fd, temp_path = tempfile.mkstemp(suffix=f"_{file.filename}")
    try:
        with os.fdopen(fd, 'wb') as f:
            shutil.copyfileobj(file.file, f)
            
        try:
            mime, _ = mimetypes.guess_type(temp_path)
            mime = mime or "application/octet-stream"
            
            if mime.startswith("image/"):
                from backend.ocr import extract_text_from_image
                parsed_text = extract_text_from_image(temp_path)
            else:
                try:
                    parsed_text = Path(temp_path).read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    raise ValueError("File encoding error. Must be UTF-8.")
                    
            item_id = ingest_file(temp_path, parsed_text)
            return IngestResponse(
                success=True,
                message="Document successfully ingested.",
                documentId=str(item_id)
            )
        except DuplicateError as e:
            return IngestResponse(
                success=True,
                message="Document already exists.",
                documentId=str(e.existing_id)
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/ingest/batch", response_model=BatchIngestResponse)
def api_ingest_batch(files: List[UploadFile] = File(...)):
    """Ingest multiple files in parallel using the IngestQueue."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # Save all uploaded files to temp paths
    temp_paths: list[tuple[str, str]] = []  # (temp_path, original_filename)
    for uploaded in files:
        fd, temp_path = tempfile.mkstemp(suffix=f"_{uploaded.filename}")
        with os.fdopen(fd, 'wb') as f:
            shutil.copyfileobj(uploaded.file, f)
        temp_paths.append((temp_path, uploaded.filename or "unknown"))

    try:
        # Submit all to the queue and drain
        queue = get_ingest_queue()
        queue.submit_batch([tp for tp, _ in temp_paths])
        results = queue.drain()

        # Build response
        item_responses: list[BatchIngestItemResponse] = []
        ingested = duplicates = errors = 0

        for (_, orig_name), r in zip(temp_paths, results):
            if r.is_duplicate:
                duplicates += 1
                item_responses.append(BatchIngestItemResponse(
                    filename=orig_name, success=True,
                    message="Document already exists.",
                    documentId=str(r.duplicate_id),
                ))
            elif r.success:
                ingested += 1
                item_responses.append(BatchIngestItemResponse(
                    filename=orig_name, success=True,
                    message="Document successfully ingested.",
                    documentId=str(r.item_id),
                ))
            else:
                errors += 1
                item_responses.append(BatchIngestItemResponse(
                    filename=orig_name, success=False,
                    message=r.error or "Unknown error.",
                ))

        return BatchIngestResponse(
            total=len(files),
            ingested=ingested, duplicates=duplicates, errors=errors,
            results=item_responses,
        )
    finally:
        for tp, _ in temp_paths:
            if os.path.exists(tp):
                os.remove(tp)

@app.get("/document/{doc_id}", response_model=DocumentDetail)
def api_get_document(doc_id: str):
    try:
        item_id = int(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Document ID")
        
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
        
    chunks = get_chunks_for_item(item_id)
    full_text = "\n\n".join(ch["body"] for ch in chunks)
    
    conns = get_connections(item_id)
    connection_results = []
    if conns:
        for c in conns:
            connection_results.append(DocumentResult(
                id=str(c["item_id"]),
                title=c.get("title") or "Unknown Title",
                summary=c.get("summary") or "",
                tags=[], # No tags returned in connections typically
                snippet="",
                score=c.get("score")
            ))

    tags_str = item.get("tags") or ""
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    return DocumentDetail(
        id=str(item_id),
        title=item.get("title") or "Unknown Title",
        summary=item.get("summary") or "",
        tags=tags,
        snippet=item.get("summary") or "",
        score=None,
        fullText=full_text,
        connections=connection_results
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
