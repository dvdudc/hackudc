"""
Black Vault — Query Intent Router
Replaces raw SQL generation by using the LLM to safely parse user intent 
into structured Pydantic models.
"""

import json
import logging
import urllib.request
from typing import Literal
from pydantic import BaseModel, Field

from backend.config import OLLAMA_HOST, LLM_MODEL

class Filters(BaseModel):
    created_after: str | None = Field(default=None, description="Date in YYYY-MM-DD format if the user asks for files created after a certain date")
    file_type: str | None = Field(default=None, description="Either 'text' or 'image' if the user asks for a specific file type")
    tags: list[str] = Field(default_factory=list, description="List of tags the user is searching for")

class QueryIntent(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    semantic_query: str = Field(..., description="The core search terms extracted from the query, without the metadata filters")
    lexical_synonyms: list[str] = Field(default_factory=list, description="A list of 2-3 specific synonyms or related terms to expand the BM25 search recall. DO NOT include the original terms.")
    intent: Literal["metadata_filter", "semantic_search"] = Field(..., description="Classification of the query intent")

def parse_intent(query: str) -> QueryIntent:
    """Parses a natural language query into a structured QueryIntent using Ollama."""
    import datetime
    today = datetime.date.today().isoformat()
    prompt = f"""
You are an intelligent query parser for Black Vault.
Extract the core semantic search terms and any explicit metadata filters from the user query.

Intent Rules:
- "metadata_filter": explicit request for file types (text/image), dates, or specific tags.
- "semantic_search": general conceptual search without metadata constraints.

Filters Rules:
- created_after: Date in YYYY-MM-DD (Today is {today}). Parse "today", "yesterday", etc.
- file_type: ONLY "text" or "image" (e.g. "imágenes", "fotos" -> "image"; "documento", "texto" -> "text").
- tags: Array of strings if explicitly asked for tags/labels (e.g. "etiquetado trabajo" -> ["trabajo"]).

Semantic Query Rule:
- The actual searchable topic/concept. If the query is "imágenes de gatitos", semantic_query is "gatitos", file_type is "image".

Lexical Synonyms Rule:
- Provide 2-3 related terms or synonyms to expand text search recall (e.g. "gatitos" -> ["gatos", "felinos"]). Do NOT repeat the main semantic_query words.

Return EXACTLY this JSON schema:
{{
  "filters": {{
    "created_after": "YYYY-MM-DD" or null,
    "file_type": "text" or "image" or null,
    "tags": ["tag1"] or []
  }},
  "semantic_query": "string",
  "lexical_synonyms": ["synonym1", "synonym2"],
  "intent": "metadata_filter" or "semantic_search"
}}

User Query: "{query}"

Return ONLY valid JSON. No markdown formatting.
"""
    url = f"http://{OLLAMA_HOST}/api/generate"
    payload = {"model": LLM_MODEL, "prompt": prompt, "stream": False, "format": "json"}
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_body = response.read().decode("utf-8")
            resp_json = json.loads(resp_body)
            raw_text = resp_json.get("response", "").strip()
            return QueryIntent.model_validate_json(raw_text)
    except Exception as e:
        logging.warning(f"Intent parsing failed: {e}. Falling back to default.")
        return QueryIntent(
            filters=Filters(),
            semantic_query=query,
            lexical_synonyms=[],
            intent="semantic_search"
        )
