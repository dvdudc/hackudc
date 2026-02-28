"""
Black Vault — LLM Client module.
Provides a singleton GenAI client.
"""

from __future__ import annotations
from google import genai
from backend.config import GEMINI_API_KEY

_client: genai.Client | None = None

def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client
