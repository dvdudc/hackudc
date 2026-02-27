import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# CONFIGURACIÓN
CARPETA_DOCS = 'documentos'
ARCHIVO_QUERY = 'query.txt'

def cargar_textos(carpeta):
    textos = []
    nombres_archivos = []
    for archivo in os.listdir(carpeta):
        if archivo.endswith(".txt"):
            ruta = os.path.join(carpeta, archivo)
            with open(ruta, 'r', encoding='utf-8') as f:
                textos.append(f.read())
                nombres_archivos.append(archivo)
    return textos, nombres_archivos

def buscar_relacionados():
    # 1. Leer tu query (pregunta)
    if not os.path.exists(ARCHIVO_QUERY):
        print("Che, no encontré el archivo 'query.txt'. Crealo y escribí tu búsqueda.")
        return
    
    with open(ARCHIVO_QUERY, 'r', encoding='utf-8') as f:
        query = f.read().strip()

    # 2. Cargar todos los TXT de la carpeta
    documentos, nombres = cargar_textos(CARPETA_DOCS)
    
    if not documentos:
        print("No hay archivos .txt en la carpeta 'documentos'.")
        return

    # 3. Magia matemática (TF-IDF)
    # Convierte textos a números para poder compararlos
    vectorizer = TfidfVectorizer(stop_words=None) # Si tus textos están en inglés, cambiá a 'english'
    tfidf_matrix = vectorizer.fit_transform(documentos + [query])

    # 4. Calcular similitud
    # Compara el último elemento (tu query) contra todos los anteriores (tus docs)
    cosine_similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()

    # 5. Mostrar resultados
    resultados = list(zip(nombres, cosine_similarities))
    resultados.sort(key=lambda x: x[1], reverse=True) # Ordenar del más relacionado al menos

    print(f"\n🔎 Resultados para: '{query}'\n")
    print(f"{'Archivo':<30} | {'Coincidencia':<10}")
    print("-" * 45)
    
    for nombre, score in resultados[:5]: # Mostrá solo los top 5
        if score > 0.05: # Ignorá los que no tienen nada que ver
            print(f"{nombre:<30} | {score:.2%}")
        else:
            break # Si el score baja mucho, cortá

if __name__ == "__main__":
    buscar_relacionados()