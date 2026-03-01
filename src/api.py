import os
import shutil
import mimetypes
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import tempfile
import uuid

from backend.ingest import ingest_file, DuplicateError, get_ingest_queue, IngestResult, detect_mime
from backend.search import search as search_docs
from backend.db import get_item, get_chunks_for_item, delete_item, add_tag_to_item
from backend.connections import get_connections

VAULT_DIR = Path("blackvault_data/files").resolve()
VAULT_DIR.mkdir(parents=True, exist_ok=True)

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
    source_type: str
    source_path: str

class DocumentDetail(DocumentResult):
    fullText: str
    connections: List[DocumentResult]

class IngestResponse(BaseModel):
    success: bool
    message: str
    documentId: str

class UrlIngestRequest(BaseModel):
    url: str

class TagRequest(BaseModel):
    tag: str

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

class ConsolidateResultItem(BaseModel):
    title: str
    new_id: int
    merged_count: int
    deleted_ids: List[int]

class ConsolidateResponse(BaseModel):
    success: bool
    message: str
    results: List[ConsolidateResultItem]

@app.get("/search", response_model=List[DocumentResult])
def api_search(q: str, strict: bool = False):
    if not q.strip():
        return []
    
    results = search_docs(q, limit=10, strict=strict)
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
            score=r.get("score"),
            source_type=r.get("source_type", "unknown"),
            source_path=r.get("source_path", "")
        ))
    return docs

@app.post("/ingest", response_model=IngestResponse)
def api_ingest(file: UploadFile = File(...)):
    # Save to a permanent vault directory for ingestion
    import time
    raw_name = file.filename if file.filename else f"document_{int(time.time()*1000)}.txt"
    safe_filename = raw_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    vault_path = VAULT_DIR / unique_filename
    
    with open(vault_path, 'wb') as f:
        shutil.copyfileobj(file.file, f)
        
    try:
        mime = detect_mime(str(vault_path))
        
        if mime.startswith("image/"):
            from backend.ocr import extract_text_from_image
            parsed_text = extract_text_from_image(str(vault_path))
        else:
            try:
                parsed_text = vault_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise ValueError("File encoding error. Must be UTF-8.")
                
        item_id = ingest_file(str(vault_path), parsed_text)
        return IngestResponse(
            success=True,
            message="Document successfully ingested.",
            documentId=str(item_id)
        )
    except DuplicateError as e:
        if vault_path.exists():
            os.remove(vault_path)
        return IngestResponse(
            success=True,
            message="Document already exists.",
            documentId=str(e.existing_id)
        )
    except ValueError as e:
        import traceback
        traceback.print_exc()
        if vault_path.exists():
            os.remove(vault_path)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        if vault_path.exists():
            os.remove(vault_path)
        raise HTTPException(status_code=500, detail=str(e))


import urllib.request
import re

def extract_text_from_html(html_content: str) -> str:
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html_content, flags=re.IGNORECASE)
    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

@app.post("/ingest/url", response_model=IngestResponse)
def api_ingest_url(req: UrlIngestRequest):
    try:
        req_obj = urllib.request.Request(req.url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_obj, timeout=10) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
            
        parsed_text = extract_text_from_html(html_content)
        if not parsed_text:
            raise ValueError("No text found on page")
            
        import uuid
        safe_filename = req.url.split('//')[-1].replace("/", "_").replace("?", "_")[:50] + ".txt"
        unique_filename = f"url_{uuid.uuid4().hex}_{safe_filename}"
        vault_path = VAULT_DIR / unique_filename
        
        vault_path.write_text(parsed_text, encoding="utf-8")
        item_id = ingest_file(str(vault_path), parsed_text)
        
        return IngestResponse(
            success=True,
            message=f"URL {req.url} successfully ingested.",
            documentId=str(item_id)
        )
    except DuplicateError as e:
        if 'vault_path' in locals() and vault_path.exists():
            os.remove(vault_path)
        return IngestResponse(
            success=True,
            message="Document already exists.",
            documentId=str(e.existing_id)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/batch", response_model=BatchIngestResponse)
def api_ingest_batch(files: List[UploadFile] = File(...)):
    """Ingest multiple files in parallel using the IngestQueue."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # Save all uploaded files to Vault paths
    vault_paths: list[tuple[str, str]] = []  # (vault_path, original_filename)
    import uuid
    for uploaded in files:
        safe_filename = (uploaded.filename or "unknown").replace(" ", "_").replace("/", "_").replace("\\", "_")
        unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
        vault_path = VAULT_DIR / unique_filename
        
        with open(vault_path, 'wb') as f:
            shutil.copyfileobj(uploaded.file, f)
        vault_paths.append((str(vault_path), uploaded.filename or "unknown"))

    try:
        # Submit all to the queue and drain
        queue = get_ingest_queue()
        queue.submit_batch([vp for vp, _ in vault_paths])
        results = queue.drain()

        # Build response & cleanup failed/duplicate vault files
        item_responses: list[BatchIngestItemResponse] = []
        ingested = duplicates = errors = 0

        for r, (_, orig_name) in zip(results, vault_paths):
            if r.is_duplicate:
                duplicates += 1
                item_responses.append(BatchIngestItemResponse(
                    filename=orig_name, success=True,
                    message="Document already exists.",
                    documentId=str(r.duplicate_id),
                ))
                if os.path.exists(r.path):
                    os.remove(r.path)
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
                if os.path.exists(r.path):
                    os.remove(r.path)

        return BatchIngestResponse(
            total=len(files),
            ingested=ingested, duplicates=duplicates, errors=errors,
            results=item_responses,
        )
    except Exception as e:
        # For catastrophic failures, clean up everything
        for vp, _ in vault_paths:
            if os.path.exists(vp):
                os.remove(vp)
        raise HTTPException(status_code=500, detail=str(e))

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

class DeleteResponse(BaseModel):
    success: bool
    message: str

@app.delete("/document/{doc_id}", response_model=DeleteResponse)
def api_delete_document(doc_id: str):
    try:
        item_id = int(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Document ID")
        
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
        
    source_path = item.get("source_path")
    success = delete_item(item_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete document from database")
        
    # Also delete the physical Vault file if it exists
    if source_path and os.path.exists(source_path):
        try:
            os.remove(source_path)
            print(f"Removed vault file: {source_path}")
        except Exception as e:
            print(f"Warning: Could not remove file {source_path}: {e}")
            
    return DeleteResponse(success=True, message=f"Document {item_id} deleted successfully.")

@app.post("/document/{doc_id}/tags", response_model=DeleteResponse)
def api_add_tag(doc_id: str, req: TagRequest):
    try:
        item_id = int(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Document ID")
    
    success = add_tag_to_item(item_id, req.tag)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found or update failed")
        
    return DeleteResponse(success=True, message=f"Tag '{req.tag}' added to document {item_id}.")

@app.post("/consolidate", response_model=ConsolidateResponse)
def api_consolidate():
    from backend.consolidate import run_consolidation
    try:
        results = run_consolidation()
        
        if not results:
            return ConsolidateResponse(
                success=True,
                message="No notes were consolidated.",
                results=[]
            )
            
        formatted_results = [
            ConsolidateResultItem(
                title=r["title"],
                new_id=r["new_id"],
                merged_count=r["merged_count"],
                deleted_ids=r["deleted_ids"]
            ) for r in results
        ]
        
        return ConsolidateResponse(
            success=True,
            message=f"Consolidated {len(results)} groups of notes.",
            results=formatted_results
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
