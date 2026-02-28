import os
import sys

# Ensure dependencies are installed
try:
    import pytesseract
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing missing dependencies (pytesseract, Pillow)...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pytesseract", "Pillow"])
    import pytesseract
    from PIL import Image, ImageDraw, ImageFont

# Set Tesseract path if it exists on standard Windows location
tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    os.environ["TESSERACT_CMD"] = tesseract_path
else:
    print("ℹ️ Tesseract not found in default C:\\Program Files\\Tesseract-OCR\\. Depending on PATH or .env")

# Add src to pythonpath so imports work
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from backend import ingest
from backend import search

def create_test_image(path):
    # Create an image with text
    img = Image.new('RGB', (600, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    text = "EL TESORO ESCONDIDO DE LA HACKATHON ESTA EN EL SOTANO 42"
    
    # Simple default font
    try:
        # Try a slightly larger default if possible, otherwise just use default
        font = ImageFont.load_default()
    except:
        font = None

    if font:
        d.text((20, 80), text, fill=(0, 0, 0), font=font)
    else:
        d.text((20, 80), text, fill=(0, 0, 0))
        
    img.save(path)
    print(f"✅ Generated test image at: {path}")
    return text

def test_ocr_pipeline():
    img_path = os.path.join(src_dir, "test_ocr_image.png")
    expected_text = create_test_image(img_path)
    
    print("\n🚀 Testing Ingestion...")
    try:
        from backend.ocr import extract_text_from_image
        parsed_text = extract_text_from_image(img_path)
        item_id = ingest.ingest_file(img_path, parsed_text)
        print(f"✅ Ingested successfully. Item ID: {item_id}")
    except ingest.DuplicateError as e:
        print(f"ℹ️ File already ingested. Item ID: {e.existing_id}")
        item_id = e.existing_id
    except ValueError as e:
        if "tesseract is not installed" in str(e).lower() or "tesseract is not in your path" in str(e).lower():
            print(f"❌ Tesseract OCR is not installed or not in PATH. Error: {e}")
            return False
        else:
            raise e
            
    print("\n🔍 Testing Search...")
    query = "SOTANO 42"
    results = search.search(query, limit=5)
    
    print(f"Found {len(results)} results for query '{query}':")
    found_in_results = False
    for r in results:
        snippet = r.get('snippet', '').replace('\n', ' ')
        print(f"  - Item: {r['item_id']} | Score: {r['score']} | Snippet: {snippet[:80]}...")
        if r['item_id'] == item_id:
            found_in_results = True
            
    if found_in_results:
        print("\n✅ SUCCESS: The ingested image was found in the search results!")
        return True
    else:
        print("\n❌ FAILURE: The ingested image was NOT found in the search results.")
        return False

if __name__ == "__main__":
    test_ocr_pipeline()
