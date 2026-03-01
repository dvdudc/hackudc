import os
import sys
from PIL import Image, ImageDraw, ImageFont

# Add src to pythonpath so imports work
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(src_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from backend.ocr import extract_text_from_image

def generate_test_images():
    output_dir = os.path.join(src_dir, "prueba_imgs")
    os.makedirs(output_dir, exist_ok=True)
    images_info = []

    try:
        font_large = ImageFont.truetype("arial.ttf", 60)
        font_small = ImageFont.truetype("arial.ttf", 14)
        font_other = ImageFont.truetype("times.ttf", 36)
    except IOError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_other = ImageFont.load_default()

    # 1. Large text
    img1_path = os.path.join(output_dir, "large_text.png")
    img1 = Image.new('RGB', (800, 200), color=(255, 255, 255))
    d1 = ImageDraw.Draw(img1)
    text1 = "TEXTO GRANDE"
    d1.text((20, 50), text1, fill=(0, 0, 0), font=font_large)
    img1.save(img1_path)
    images_info.append({"path": img1_path, "expected": text1})

    # 2. Small text
    img2_path = os.path.join(output_dir, "small_text.png")
    img2 = Image.new('RGB', (300, 100), color=(255, 255, 255))
    d2 = ImageDraw.Draw(img2)
    text2 = "texto pequeno"
    d2.text((10, 20), text2, fill=(0, 0, 0), font=font_small)
    img2.save(img2_path)
    images_info.append({"path": img2_path, "expected": text2})

    # 3. Different font
    img3_path = os.path.join(output_dir, "different_font.png")
    img3 = Image.new('RGB', (600, 150), color=(255, 255, 255))
    d3 = ImageDraw.Draw(img3)
    text3 = "FUENTE DISTINTA"
    d3.text((20, 50), text3, fill=(0, 0, 0), font=font_other)
    img3.save(img3_path)
    images_info.append({"path": img3_path, "expected": text3})

    return images_info


def run_tests():
    print("Generando imagenes de prueba en 'prueba_imgs'...")
    tests = generate_test_images()
    
    success = True
    for test in tests:
        path = test["path"]
        expected = test["expected"]
        print(f"Probando {os.path.basename(path)}...")
        try:
            result = extract_text_from_image(path)
            print(f"  Esperado: '{expected}'")
            print(f"  Obtenido: '{result}'")
            if expected.lower() in result.lower():
                print("  ✅ Exito")
            else:
                print("  ⚠️ El texto no coincide exactamente. Revisar manualmente.")
        except Exception as e:
            print(f"  ❌ Error procesando {path}: {e}")
            success = False

    if success:
        print("\n✅ Todas las pruebas de EasyOCR han concluido con exito.")
    else:
        print("\n❌ Hubo errores durante las pruebas.")

if __name__ == "__main__":
    run_tests()
