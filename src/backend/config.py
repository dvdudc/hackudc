"""
Black Vault — Configuration module.
Loads settings from environment variables / .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (src/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# ── API ──────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ── Database ─────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("BLACK_VAULT_DB", "black_vault.duckdb")

# ── Models ───────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = "gemini-embedding-001"
EMBEDDING_DIM: int = 3072  # dimensión por defecto de gemini-embedding-001
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Chunking ─────────────────────────────────────────────────────────
CHUNK_SIZE: int = 500
CHUNK_OVERLAP: int = 100

# ── Connections ──────────────────────────────────────────────────────
CONNECTION_THRESHOLD: float = 0.75

# ── Tesseract OCR ────────────────────────────────────────────────────
# Ruta al ejecutable de Tesseract (necesario en Windows si no está en el PATH)
# Ejemplo: r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "")
if not TESSERACT_CMD and os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
