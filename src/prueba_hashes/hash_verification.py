import hashlib

def get_md5(ruta):
    # Calcula hash MD5 leyendo todo el archivo en binario
    return hashlib.md5(open(ruta, 'rb').read()).hexdigest()

# Tus archivos específicos
f1 = 'documentos/texto_igual1.txt'
f2 = 'documentos/texto_igual2.txt'
f3 = 'documentos/texto_distinto.txt'

# Calcular hashes
h1 = get_md5(f1)
h2 = get_md5(f2)
h3 = get_md5(f3)

# Comparar mostrando los nombres en el print
print(f"{f1} vs {f2}: {'DUPLICADOS' if h1 == h2 else 'DIFERENTES'}")
print(f"{f1} vs {f3}: {'DUPLICADOS' if h1 == h3 else 'DIFERENTES'}")
print(f"{f2} vs {f3}: {'DUPLICADOS' if h2 == h3 else 'DIFERENTES'}")