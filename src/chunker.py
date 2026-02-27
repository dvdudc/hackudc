import duckdb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def procesar_y_guardar(nombre_archivo, texto_completo):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        is_separator_regex=False,
    )
    
    chunks = text_splitter.split_text(texto_completo)
    print(f"Generados {len(chunks)} fragmentos para {nombre_archivo}")

    con = duckdb.connect('agujero_negro.db')
    
    con.execute("INSTALL vss; LOAD vss;")
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY,
            archivo TEXT,
            contenido TEXT,
            vector FLOAT[384] -- 384 es la dimensión de all-MiniLM-L6-v2
        )
    """)

    for i, chunk in enumerate(chunks):
        vector = model.encode(chunk).tolist()
        
        con.execute("""
            INSERT INTO documentos (archivo, contenido, vector)
            VALUES (?, ?, ?)
        """, (nombre_archivo, chunk, vector))
    
    con.close()
    print("¡Procesado completado con éxito!")

texto_ejemplo = """Aquí pondrías todo el contenido extraído de tu PDF o archivo..."""
procesar_y_guardar("factura_enero.pdf", texto_ejemplo)