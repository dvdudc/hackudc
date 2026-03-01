# Black Vault - Frontend & Shortcuts

Este documento explica cómo configurar el frontend de **Black Vault**, su arquitectura UI, los comandos CLI integrados, y los atajos de teclado globales.

---

## 🛠 Instalación y Configuración

El frontend de Black Vault está construido con **React (Vite)** y empaquetado como aplicación de escritorio usando **Electron**.

### Requisitos Previos
1. **Node.js** (recomendado v18+)
2. **NPM** o Yarn.
3. Asegurarte de que el backend de Python (`src/api.py`) tiene sus dependencias resueltas (`pip install -r src/requirements.txt`).

### Arrancar la Aplicación
Navega a la carpeta principal `web/` en la terminal:

```bash
cd web

# 1. Instalar dependencias
npm install

# 2. Iniciar en modo desarrollo
npm run dev
```
Al lanzar `npm run dev`, Electron automáticamente levantará el servidor de Backend (`api.py`) utilizando el ejecutable en `.venv`.

---

## 🚀 Arquitectura UI: El Agujero Negro

La aplicación funciona como un **Widget Transparente ("Power Toy")**. No ocupa espacio sólido en la pantalla ni aparece maximizada de primeras.

- **Modo Colapsado**: Solo se muestra el widget circular del "Agujero Negro" flotando encima del resto de ventanas, anclado a la esquina inferior derecha.
- **Modo Expandido**: Al interactuar, la aplicación se despliega hacia la izquierda revelando el panel de resultados de la Búsqueda y Detalles del documento.

---

## ⚡ Comandos CLI

El buscador principal no solo busca texto tradicional (búsqueda semántica), sino que actúa como una consola de comandos `CLI` súper potente. 

Pulsando sobre los atajos debajo de la caja grande, o tecleando directamente en el widget transparente, puedes ejecutar:

| Comando | Acción | Ejemplo de Uso |
| --- | --- | --- |
| `>n` | Crea una nota rápida `.txt` automáticamente en el Vault | `>n Esto es una idea importante` |
| `>url` | Descarga, lee, escrapea y guarda el contenido de texto de una web | `>url https://es.wikipedia.org/wiki/React` |
| `>tag` | Añade una etiqueta dinámica a un documento en la DB | `>tag 45 important` |
| `>rm` | Borra un documento del Vault (tanto DB como archivo local) | `>rm 45` |
| `>s` | Fuerza una búsqueda exacta (BM25) esquivando la búsqueda semántica | `>s Python` |

*Nota: Los comandos de gestión (`>n`, `>url`, `>tag`, `>rm`) se ejecutan en segundo plano. La interfaz **no** se desplegará interrumpiendo lo que estés haciendo.*

---

## ⌨️ Atajos de Teclado Globales

Black Vault funciona en el fondo como un asistente omnisciente. Puedes llamarlo desde cualquier programa de Windows usando estos teclados globales:

| Atajo | Función |
| --- | --- |
| **`Ctrl + Shift + B`** | **Ocultar / Mostrar Widget**: Hace desaparecer completamente el Agujero Negro si te está molestando visualmente en pantalla, y lo vuelve a invocar cuando lo necesites. |
| **`Ctrl + Shift + Espacio`** | **Búsqueda Relámpago**: Fuerza la apertura expandida del widget y pone el foco del teclado inmediatamente en la barra de búsqueda principal. Magia pura para buscar rápido. |

(En macOS, utiliza `Cmd` en lugar de `Ctrl`).
