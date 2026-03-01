"""
PDF Processing module using pdfplumber.
Extracts standard text and formats tabular data from PDF files.
"""
import logging
from pathlib import Path

import pdfplumber

_logger = logging.getLogger(__name__)

def extract_text_from_pdf(filepath: Path | str) -> str:
    """
    Extrae el texto y las tablas de un archivo PDF utilizando pdfplumber.
    Combina las celdas de las tablas en un formato de texto legible para 
    que pueda ser procesado semánticamente (RAG).

    Args:
        filepath: Ruta al archivo PDF.

    Returns:
        Texto transcrito como string (texto plano + tablas representadas en texto).

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el archivo no es un PDF válido o está corrupto.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    results: list[str] = []

    try:
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = []

                # Extraer texto normal
                text = page.extract_text()
                if text:
                    page_text.append(text.strip())

                # Extraer y formatear tablas (si las hay)
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    
                    page_text.append("\n[TABLA EXTRAÍDA]")
                    for row in table:
                        # Filtrar celdas nulas o vacías y unirlas con un separador |
                        clean_row = [str(cell).strip().replace("\n", " ") if cell else "" for cell in row]
                        # Solo añadir la fila si no está completamente vacía
                        if any(clean_row):
                            page_text.append(" | ".join(clean_row))

                if page_text:
                    results.append(f"--- PÁGINA {i + 1} ---")
                    results.append("\n".join(page_text))
                    results.append("\n")

    except Exception as e:
        _logger.error(f"Error procesando PDF '{filepath}': {e}")
        raise ValueError(f"No se pudo procesar el archivo PDF: {filepath}. Error: {e}") from e

    return "\n".join(results).strip()
