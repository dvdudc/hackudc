from pathlib import Path
import easyocr
import torch
import warnings

# Intentar usar GPU si está disponible
use_gpu = torch.cuda.is_available()

# Si no hay GPU, eliminamos la advertencia del pin_memory que tira PyTorch
if not use_gpu:
    warnings.filterwarnings("ignore", category=UserWarning, module="torch.utils.data.dataloader")

# Inicializar EasyOCR a nivel global para que no cargue el modelo en cada llamada
# verbose=False quita el warning "Using CPU. Note: This module is much faster with a GPU."
reader = easyocr.Reader(['es', 'en'], gpu=use_gpu, verbose=False)

def extract_text_from_image(filepath: Path | str) -> str:
    """Extracts text from an image using EasyOCR."""
    # detail=0 devuelve solo una lista de strings (el texto detectado)
    result = reader.readtext(str(filepath), detail=0)
    return ' '.join(result)