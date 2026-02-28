# 🕳️ Black Vault

**Drop it, forget it, find it.**

Black Vault es una aplicación local donde puedes soltar cualquier archivo de texto y recuperarlo después con lenguaje natural. Sin carpetas, sin organización manual, sin fricción.

## Arquitectura

```
┌─────────────────────────┐      ┌──────────────────────────────────┐
│   Interface Layer (CLI) │─────▶│     Processor Layer (Backend)    │
│   cli.py                │      │  ingest.py  search.py  enrich.py│
└─────────────────────────┘      │  db.py      connections.py      │
                                 │  config.py                      │
                                 └──────────┬───────────────────────┘
                                            │
                                     ┌──────▼──────┐
                                     │  DuckDB+VSS │
                                     │  (single    │
                                     │  .duckdb)   │
                                     └─────────────┘
```

**Dos capas separadas:**
- **Interface Layer** — CLI (typer + rich). Puede sustituirse por Tauri/Electron.
- **Processor Layer** — Backend Python. Puede moverse a un servidor remoto detrás de una API REST.

**Almacenamiento** — Un único fichero `.duckdb` portable con 4 tablas:

| Tabla | Contenido |
|-------|-----------|
| `items` | Metadata: ruta, tipo, título, tags, resumen, fecha |
| `content` | Texto extraído troceado en chunks |
| `embeddings` | Vectores (1536-dim) con índice HNSW vía VSS |
| `connections` | Relaciones item-a-item por similitud semántica |

## Stack técnico

| Componente | Tecnología |
|------------|------------|
| Base de datos | DuckDB + extensión VSS (HNSW) |
| Embeddings | Google `gemini-embedding-001` (3072 dim) |
| Enriquecimiento | Ollama `llama3.2` (título, tags, resumen) |
| Chunking | `langchain-text-splitters` (RecursiveCharacterTextSplitter) |
| Detección de tipo | `python-magic` (libmagic) |
| CLI | `typer` + `rich` |
| Búsqueda | Híbrida: semántica (coseno HNSW) + léxica (ILIKE), peso 70/30 |
| Logging | RichHandler + File Logging (toggled via CLI) |

## Quick Start

### 1. Requisitos previos

- Python 3.10+
- `libmagic` instalado en el sistema:
  ```bash
  # Ubuntu/Debian
  sudo apt install libmagic1
  # macOS
  brew install libmagic
  ```

### 2. Instalación

```bash
cd hackudc/src
pip install -r requirements.txt
```

### 3. Configuración

```bash
cp .env.example .env
# Edita .env y añade tu GEMINI_API_KEY y OLLAMA_HOST
```

### 4. Uso

```bash
# Ingestar un fichero de texto
python cli.py ingest documento.txt

# Activar/Desactivar el logging de archivos persistente
python cli.py logstart

# Buscar con lenguaje natural (puedes usar -v para modo verbose)
python cli.py search "ideas sobre productividad"
python cli.py -v list

# Listar todos los items
python cli.py list

# Ver detalle de un item + conexiones
python cli.py show 1

# Exportar todo
python cli.py export --format json
python cli.py export --format csv
```

## Pipeline de procesamiento

```
Archivo .txt/.md
       │
       ▼
  python-magic        ← Verifica MIME type (text/*)
       │
       ▼
  Leer contenido      ← UTF-8
       │
       ▼
  Chunking            ← RecursiveCharacterTextSplitter (500 chars, 100 overlap)
       │
       ▼
  Embedding           ← Gemini gemini-embedding-001 (batch API call)
       │
       ▼
  DuckDB Store        ← items + content + embeddings
       │
       ▼
  Enriquecimiento     ← Ollama (llama3.2) via HTTP → {título, tags[], resumen}
       │
       ▼
  Conexiones          ← Cosine similarity entre mean embeddings (threshold 0.75)
```

## Búsqueda híbrida

La búsqueda combina dos estrategias:

1. **Semántica (70%)** — Embebe la query, busca vecinos más cercanos via HNSW index (coseno)
2. **Léxica (30%)** — Búsqueda por palabras clave indexadas (BM25)

Los resultados se fusionan y ordenan por score combinado.

## Estructura del proyecto

```
.
├── docs/                 # Documentación técnica
├── src/                  # Código fuente
│   ├── backend/          # Lógica del procesador y base de datos
│   ├── cli.py            # Entry point de la aplicación (Typer)
│   ├── .env.example      # Plantilla de variables de entorno
│   └── requirements.txt  # Dependencias de Python
├── tests/                # Pruebas y benchmarks de búsqueda
└── README.md             # Esta guía
```

## MVP — Limitaciones actuales

- Solo procesa archivos de texto plano (`text/*`)
- La interfaz es CLI (sin GUI)
- Enriquecimiento y conexiones se ejecutan de forma síncrona
- Sin watcher de portapapeles ni hotkeys
- Sin soporte para PDF, imágenes, audio, URLs (previsto para futuras iteraciones)