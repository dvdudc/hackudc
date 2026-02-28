"""
Black Vault — Enrichment module.
Uses Gemini Flash to generate title, tags, and summary for an item.
"""

from __future__ import annotations

import json
from google import genai

from backend.config import GEMINI_API_KEY, LLM_MODEL
from backend import db


_client: genai.Client | None = None


def _genai() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def enrich_item(item_id: int) -> dict:
    """
    Generate title, tags, and summary for an item using Gemini Flash.

    Returns dict with keys: title, tags, summary.
    """
    chunks = db.get_chunks_for_item(item_id)
    if not chunks:
        print(f"⚠️  No content found for item #{item_id}, skipping enrichment.")
        return {}

    # Combine chunks (truncate if excessively long to stay within context)
    full_text = "\n---\n".join(c["body"] for c in chunks)
    if len(full_text) > 12_000:
        full_text = full_text[:12_000] + "\n[... truncated ...]"

    prompt = f"""Analyze the following document and return a JSON object with exactly these keys:
- "title": a concise, descriptive title (max 10 words)
- "tags": an array of 3-7 relevant tags (lowercase, single words or short phrases)
- "summary": a 2-3 sentence summary of the document content

Document:
\"\"\"
{full_text}
\"\"\"

Return ONLY valid JSON, no markdown formatting, no extra text."""

    try:
        resp = _genai().models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
        )

        raw = resp.text.strip()

        # Parse JSON (handle potential markdown code fences)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]  # remove first ``` line
            raw = raw.rsplit("```", 1)[0]  # remove last ```

        data = json.loads(raw)

        title = data.get("title", "Untitled")
        tags = ", ".join(data.get("tags", []))
        summary = data.get("summary", "")

        db.update_item_enrichment(item_id, title, tags, summary)
        print(f"🏷️  Enriched item #{item_id}: \"{title}\"")
        return {"title": title, "tags": tags, "summary": summary}

    except Exception as e:
        print(f"⚠️  Enrichment failed for item #{item_id}: {e}")
        return {}
