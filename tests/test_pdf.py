"""
Tests para el módulo PDF usando pdfplumber.
"""
import sys
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

_src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_src_dir))

from backend.pdf import extract_text_from_pdf

def _create_sample_pdf(filepath: Path):
    """Crea un PDF de prueba usando ReportLab con contenido dummy."""
    c = canvas.Canvas(str(filepath), pagesize=letter)
    # Página 1: Texto normal
    c.drawString(100, 750, "Hola Mundo")
    c.drawString(100, 730, "Este es un documento PDF de prueba.")
    c.showPage()
    
    # Página 2: Más texto 
    c.drawString(100, 750, "Datos importantes en la página 2.")
    c.showPage()
    c.save()

class TestPDFProcessing:
    """Pruebas básicas para el parseador pdfplumber."""

    def test_extract_text_valid_pdf(self, tmp_path):
        pdf_path = tmp_path / "sample.pdf"
        _create_sample_pdf(pdf_path)

        text = extract_text_from_pdf(pdf_path)

        assert "--- PÁGINA 1 ---" in text
        assert "Hola Mundo" in text
        assert "Este es un documento PDF de prueba." in text
        
        assert "--- PÁGINA 2 ---" in text
        assert "Datos importantes en la página 2." in text

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            extract_text_from_pdf("ruta_inventada_que_no_existe.pdf")

    def test_invalid_pdf(self, tmp_path):
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_text("texto falso que no es un pdf")

        with pytest.raises(ValueError, match="No se pudo procesar el archivo PDF"):
            extract_text_from_pdf(fake_pdf)
