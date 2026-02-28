"""
Black Vault — Enrichment module.
Uses a self-hosted Ollama instance to generate title, tags, and summary for an item.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error

from backend.config import LLM_MODEL, OLLAMA_HOST
from backend import db

ENRICHMENT_PROMPT = """
Eres un analizador semántico especializado en sistemas RAG (Retrieval-Augmented Generation).
Tu objetivo es extraer metadatos de alta calidad de un fragmento de texto para optimizar 
su recuperación futura mediante búsqueda híbrida (semántica + léxica).

## FRAGMENTO A ANALIZAR
Índice del chunk: {chunk_index} de {total_chunks} (del documento completo)
Total de palabras en este chunk: {chunk_word_count}
Total de palabras en el documento completo: {doc_word_count}
```
{chunk_text}
```

## INSTRUCCIONES

Analiza el fragmento y devuelve un JSON con la siguiente estructura. 
SIN texto adicional, SIN explicaciones. Solo el JSON. Puedes usar valid JSON codeblocks (```json).

### REGLAS CRÍTICAS:
- Los `tags` deben ser términos que aparezcan SOLO si son conceptualmente centrales en ESTE chunk.
- La `densidad_tematica` mide qué tan concentrado está el tema en este chunk (0.0 a 1.0).
- El `score_relevancia_chunk` refleja qué tan autosuficiente y útil es este chunk de forma aislada.
- Los `terminos_clave_ponderados` deben reflejar importancia RELATIVA al chunk.
```json
{{
  "titulo": "string — título descriptivo y específico del chunk (no del documento completo)",
  "resumen": "string — 1-2 oraciones que capturen la idea central de ESTE fragmento",
  "tipo_contenido": "enum: [tecnico, narrativo, instruccional, referencia, conceptual, codigo, datos, mixto]",
  "idioma": "string — código ISO 639-1 (es, en, fr...)",
  "tags": [
    "string — máximo 7 tags, términos únicos y discriminativos de ESTE chunk"
  ],
  "terminos_clave_ponderados": {{
    "termino_1": 0.95,
    "termino_2": 0.80
  }},
  "densidad_tematica": 0.0,
  "score_relevancia_chunk": 0.0,
  "entidades": {{
    "personas": [],
    "organizaciones": [],
    "lugares": [],
    "fechas": [],
    "conceptos_tecnicos": [],
    "productos_herramientas": []
  }},
  "preguntas_que_responde": [
    "string — 2-4 preguntas"
  ],
  "contexto_necesario": "enum: [autosuficiente, requiere_chunks_anteriores, requiere_chunks_posteriores, requiere_ambos]",
  "chunk_posicion": "enum: [introduccion, desarrollo, conclusion, fragmento_aislado]"
}}
```
"""

def enrich_item(item_id: int) -> dict:
    """
    Generate title, tags, and summary for an item by evaluating every chunk
    and aggregating its metadata via ENRICHMENT_PROMPT, using Ollama.
    """
    chunks = db.get_chunks_for_item(item_id)
    if not chunks:
        print(f"⚠️  No content found for item #{item_id}, skipping enrichment.")
        return {}

    total_chunks = len(chunks)
    doc_word_count = sum(len(c["body"].split()) for c in chunks)
    
    all_tags = []
    chunk_titles = []
    
    url = f"http://{OLLAMA_HOST}/api/generate"

    # Process each chunk
    for i, chunk in enumerate(chunks):
        chunk_word_count = len(chunk["body"].split())
        prompt = ENRICHMENT_PROMPT.format(
            chunk_index=i + 1,
            total_chunks=total_chunks,
            chunk_word_count=chunk_word_count,
            doc_word_count=doc_word_count,
            chunk_text=chunk["body"]
        )
        
        payload = {
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req) as response:
                resp_body = response.read().decode("utf-8")
                resp_json = json.loads(resp_body)
                raw = resp_json.get("response", "").strip()
            
            # Parse JSON (handle potential markdown code fences)
            if "```json" in raw:
                raw = raw.split("```json", 1)[1]
                raw = raw.split("```", 1)[0]
            elif raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            
            data = json.loads(raw.strip())
            
            # Store metadata
            db.insert_chunk_metadata(chunk["id"], data)
            
            # Aggregate for item-level summary
            if data.get("tags"):
                all_tags.extend(data["tags"])
            if data.get("titulo"):
                chunk_titles.append(data["titulo"])
                
            print(f" ✨ Chunk {i+1}/{total_chunks} enriched: {data.get('titulo')}")

        except urllib.error.URLError as e:
            print(f"⚠️  Failed to connect to Ollama at {url}: {e}")
            break
        except Exception as e:
            print(f"⚠️  Enrichment failed for item #{item_id} chunk #{i+1}: {e}")

    # VERY basic global item aggregation (could be another LLM call if needed)
    final_title = chunk_titles[0] if chunk_titles else "Untitled Document"
    
    # Simple tag frequency to pick top 5
    from collections import Counter
    tag_counts = Counter(t.lower() for t in all_tags)
    best_tags = [t for t, _ in tag_counts.most_common(5)]
    tags_str = ", ".join(best_tags)
    
    final_summary = f"Doc aggregated from {total_chunks} chunk(s)."
    
    db.update_item_enrichment(item_id, final_title, tags_str, final_summary)
    print(f"🏷️  Enriched item #{item_id}: \"{final_title}\"")
    return {"title": final_title, "tags": tags_str, "summary": final_summary}
