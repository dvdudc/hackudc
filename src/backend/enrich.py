"""
Black Vault — Enrichment module.
Uses a self-hosted Ollama instance to generate title, tags, and summary for an item.
"""

from __future__ import annotations

import json
from pydantic import BaseModel, Field

from backend.config import LLM_MODEL, GROQ_API_KEY
from backend import db
from langchain_groq import ChatGroq

class EntitiesInfo(BaseModel):
    personas: list[str] = Field(default_factory=list)
    organizaciones: list[str] = Field(default_factory=list)
    lugares: list[str] = Field(default_factory=list)
    fechas: list[str] = Field(default_factory=list)
    conceptos_tecnicos: list[str] = Field(default_factory=list)
    productos_herramientas: list[str] = Field(default_factory=list)

class ChunkEnrichment(BaseModel):
    titulo: str = Field(description="Título descriptivo y específico del chunk")
    resumen: str = Field(description="1-2 oraciones que capturen la idea central")
    tipo_contenido: str = Field(description="Uno de: tecnico, narrativo, instruccional, referencia, conceptual, codigo, datos, mixto")
    idioma: str = Field(description="Código ISO 639-1")
    tags: list[str] = Field(description="Etiquetas conceptuales centrales")
    terminos_clave_ponderados: dict[str, float] = Field(description="Términos y su importancia (0.0 a 1.0)")
    densidad_tematica: float = Field(description="Qué tan concentrado está el tema (0.0 a 1.0)")
    score_relevancia_chunk: float = Field(description="Qué tan autosuficiente y útil es")
    entidades: EntitiesInfo
    preguntas_que_responde: list[str] = Field(description="Preguntas que este texto responde")
    contexto_necesario: str = Field(description="Uno de: autosuficiente, requiere_chunks_anteriores, requiere_chunks_posteriores, requiere_ambos")
    chunk_posicion: str = Field(description="Uno de: introduccion, desarrollo, conclusion, fragmento_aislado")

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

Analiza el fragmento anterior y extrae la información real basándote en su contenido.
Devuelve un JSON rellenado con los datos extraídos, manteniendo estrictamente esta estructura. 
REEMPLAZA los valores de ejemplo de este template por los valores reales extraídos del texto.
SIN texto adicional, SIN explicaciones. Solo el JSON. Puedes usar valid JSON codeblocks (```json).

### REGLAS CRÍTICAS:
- Los `tags` deben ser términos que aparezcan SOLO si son conceptualmente centrales en ESTE chunk.
- La `densidad_tematica` mide qué tan concentrado está el tema en este chunk (0.0 a 1.0).
- El `score_relevancia_chunk` refleja qué tan autosuficiente y útil es este chunk de forma aislada.
- Los `terminos_clave_ponderados` deben reflejar importancia RELATIVA al chunk.
- RELLENA los campos de texto con contenido real analizado, NUNCA devuelvas cadenas vacías si hay información útil.

TEMPLATE JSON A LLENAR:
```json
{{
  "titulo": "Escribe aquí el título descriptivo y específico del chunk",
  "resumen": "Escribe aquí 1-2 oraciones que capturen la idea central de este fragmento",
  "tipo_contenido": "Elige estrictamente uno de: [tecnico, narrativo, instruccional, referencia, conceptual, codigo, datos, mixto]",
  "idioma": "Escribe aquí código ISO 639-1 (ej: es, en, fr)",
  "tags": [
    "tag1", "tag2", "tag3"
  ],
  "terminos_clave_ponderados": {{
    "termino_real_1": 0.95,
    "termino_real_2": 0.80
  }},
  "densidad_tematica": 0.8,
  "score_relevancia_chunk": 0.7,
  "entidades": {{
    "personas": ["persona1"],
    "organizaciones": [],
    "lugares": [],
    "fechas": [],
    "conceptos_tecnicos": [],
    "productos_herramientas": []
  }},
  "preguntas_que_responde": [
    "Escribe pregunta 1", "Escribe pregunta 2"
  ],
  "contexto_necesario": "Elige estrictamente uno de: [autosuficiente, requiere_chunks_anteriores, requiere_chunks_posteriores, requiere_ambos]",
  "chunk_posicion": "Elige estrictamente uno de: [introduccion, desarrollo, conclusion, fragmento_aislado]"
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
    
    try:
        model = ChatGroq(model=LLM_MODEL, api_key=GROQ_API_KEY, temperature=0.1)
        structured_llm = model.with_structured_output(ChunkEnrichment)
    except Exception as e:
        print(f"⚠️ Failed to initialize Groq model: {e}")
        return {}

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
        
        try:
            enriched_data = structured_llm.invoke(prompt)
            data = enriched_data.model_dump()
            
            # Store metadata
            db.insert_chunk_metadata(chunk["id"], data)
            
            # Aggregate for item-level summary
            if data.get("tags"):
                all_tags.extend(data["tags"])
            if data.get("titulo"):
                chunk_titles.append(data["titulo"])
            else:
                print(f"⚠️  No 'titulo' found in extracted JSON data. Dump: {data}")
                
            print(f" ✨ Chunk {i+1}/{total_chunks} enriched: {data.get('titulo')}")

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
    
    metadata_text = f"Tags: {tags_str}\nSummary: {final_summary}"
    try:
        from backend.ingest import get_embedding
        metadata_vector = get_embedding(metadata_text)
    except Exception as e:
        print(f"⚠️  Failed to generate metadata vector for item #{item_id}: {e}")
        metadata_vector = None

    db.update_item_enrichment(item_id, final_title, tags_str, final_summary, metadata_vector)
    print(f"🏷️  Enriched item #{item_id}: \"{final_title}\"")
    return {"title": final_title, "tags": tags_str, "summary": final_summary, "metadata_vector": metadata_vector}
