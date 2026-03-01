"""
Black Vault — Note Consolidation Module.
Groups small textual notes and uses LLM to merge them into coherent documents.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from backend import db
from backend.llm import get_client
from backend.ingest import ingest_file

def fetch_small_notes(max_length: int = 300) -> list[dict[str, Any]]:
    """Retrieve items whose total text length is <= max_length."""
    con = db.get_connection()
    # Find items where the sum of chunk lengths is <= max_length
    # and they are text type
    query = """
    SELECT i.id as item_id, i.title
    FROM items i
    JOIN content c ON i.id = c.item_id
    WHERE i.source_type = 'text'
    GROUP BY i.id, i.title
    HAVING SUM(LENGTH(c.body)) <= ? AND SUM(LENGTH(c.body)) > 0
    """
    rows = con.execute(query, [max_length]).fetchall()
    
    notes = []
    for r in rows:
        item_id = r[0]
        # Get actual text and embeddings for similarity later
        chunks = db.get_chunks_for_item(item_id)
        full_text = "\n".join(c["body"] for c in chunks)
        embeddings = db.get_embeddings_for_item(item_id)
        
        if embeddings:
            notes.append({
                "item_id": item_id,
                "text": full_text,
                "embedding": embeddings[0] # use first chunk embedding
            })
            
    return notes

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def cluster_notes(notes: list[dict[str, Any]], similarity_threshold: float = 0.70) -> list[list[dict[str, Any]]]:
    """Group notes based on cosine similarity."""
    clusters = []
    visited = set()
    
    for i, note_a in enumerate(notes):
        if note_a["item_id"] in visited:
            continue
            
        current_cluster = [note_a]
        visited.add(note_a["item_id"])
        
        for j in range(i + 1, len(notes)):
            note_b = notes[j]
            if note_b["item_id"] in visited:
                continue
                
            sim = cosine_similarity(note_a["embedding"], note_b["embedding"])
            if sim >= similarity_threshold:
                current_cluster.append(note_b)
                visited.add(note_b["item_id"])
                
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
            
    return clusters

def consolidate_cluster(cluster: list[dict[str, Any]]) -> tuple[str, str]:
    """Call LLM to merge texts and generate a title."""
    client = get_client()
    
    texts = [n["text"] for n in cluster]
    combined_text = "\n---\n".join(texts)
    
    prompt = f"""You are an assistant that consolidates short notes into a single coherent document.
Here are several short notes that are semantically related:

{combined_text}

Task 1: Combine the information from these notes into a single, well-structured text. Remove redundancies.
Task 2: Generate a short, descriptive title for the consolidated text.

Format your response exactly as follows:
TITLE: [Your short title]
CONTENT:
[Your consolidated text]
"""
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    output = response.text
    title = "Consolidated Note"
    content = output
    
    if "TITLE:" in output and "CONTENT:" in output:
        parts = output.split("CONTENT:")
        title_part = parts[0].replace("TITLE:", "").strip()
        if title_part:
            title = title_part
        content = parts[1].strip()
        
    return title, content

def run_consolidation() -> list[dict[str, Any]]:
    """Orchestrator for the consolidation process."""
    logging.info("Starting note consolidation process...")
    notes = fetch_small_notes()
    if len(notes) < 2:
        logging.info("Not enough small notes to consolidate.")
        return []
        
    clusters = cluster_notes(notes)
    if not clusters:
        logging.info("No similar notes found to cluster.")
        return []
        
    results = []
    
    out_dir = Path("consolidated_notes")
    out_dir.mkdir(exist_ok=True)
    
    for i, cluster in enumerate(clusters):
        title, new_text = consolidate_cluster(cluster)
        
        # Save to file
        safe_title = "".join(c if c.isalnum() else "_" for c in title)
        filepath = out_dir / f"{safe_title}_{i}.txt"
        filepath.write_text(new_text, encoding="utf-8")
        
        # Ingest new
        try:
            new_id = ingest_file(str(filepath), new_text)
            
            # Delete old
            deleted_ids = []
            for note in cluster:
                # delete_item logic handles all cleanup
                db.delete_item(note["item_id"])
                deleted_ids.append(note["item_id"])
                
            results.append({
                "title": title,
                "new_id": new_id,
                "merged_count": len(cluster),
                "deleted_ids": deleted_ids
            })
            logging.info(f"Consolidated {len(cluster)} notes into '{title}' (ID: {new_id})")
        except Exception as e:
            logging.error(f"Error during ingestion of consolidated note: {e}")
            
    return results
