from pathlib import Path
import easyocr

# Inicializar EasyOCR a nivel global para que no cargue el modelo en cada llamada
reader = easyocr.Reader(['es', 'en'])

def extract_text_from_image(filepath: Path | str) -> str:
    """Extracts text from an image using EasyOCR."""
    # detail=0 devuelve solo una lista de strings (el texto detectado)
    result = reader.readtext(str(filepath), detail=0)
    return ' '.join(result)
