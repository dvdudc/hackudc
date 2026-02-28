from pathlib import Path
from PIL import Image
import pytesseract

from backend.config import TESSERACT_CMD

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

def extract_text_from_image(filepath: Path | str) -> str:
    """Extracts text from an image using Tesseract OCR."""
    image = Image.open(filepath)
    return pytesseract.image_to_string(image)
