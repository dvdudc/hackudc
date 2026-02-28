import hashlib
import magic

def get_info(ruta):
    # Calcula hash MD5
    hash_val = hashlib.md5(open(ruta, 'rb').read()).hexdigest()
    # Detecta tipo MIME real (no depende de la extensión .txt)
    mime_val = magic.from_file(ruta, mime=True)
    return hash_val, mime_val

# Tus archivos
f1 = 'documentos/texto_igual1.txt'
f2 = 'documentos/texto_igual2.txt'
f3 = 'documentos/texto_distinto.txt'

# Obtener información
h1, m1 = get_info(f1)
h2, m2 = get_info(f2)
h3, m3 = get_info(f3)

# Prints con nombre, hash y tipo MIME
print(f"{f1} | MIME: {m1} |")
print(f"{f2} | MIME: {m2} |")
print(f"{f3} | MIME: {m3} |")

# Comparativa de duplicados
print("\n--- Duplicados ---")
print(f"{f1} vs {f2}: {'DUPLICADOS' if h1 == h2 else 'DIFERENTES'}")
print(f"{f1} vs {f3}: {'DUPLICADOS' if h1 == h3 else 'DIFERENTES'}")
print(f"{f2} vs {f3}: {'DUPLICADOS' if h2 == h3 else 'DIFERENTES'}")