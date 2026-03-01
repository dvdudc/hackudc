# Black Vault 🕳️ - Documentación de Usuario y Arquitectura

Bienvenido a Black Vault. Esta versión ha sido diseñada específicamente para funcionar en un entorno distribuido mediante VPN, manteniendo los ordenadores de los clientes ligeros mientras el procesamiento de Inteligencia Artificial pesado ocurre en el servidor remoto.

## 🏗 Arquitectura de Distribución (Opción 1 - Portable)

Black Vault se compone de dos piezas que funcionan en sincronía:
1. **El Cerebro (Backend Python)**: Escrito en FastAPI, se encarga de gestionar la base de datos vectorial local (DuckDB), leer PDFs/Imágenes, y redirigir las peticiones de razonamiento pesado hacia el modelo LLM remoto (`10.8.0.3:11434`).
2. **El Widget (Frontend Electron)**: Una interfaz transparente construida en React + Vite que actúa como un agujero negro flotante en Windows.

### 💿 Guía de Instalación para el Equipo
No necesitas instalar entornos complejos, solo seguir estos pasos:

1. **Requisito Previos**: 
   - Estar conectado a la VPN del equipo (IP del servidor IA: `10.8.0.3`).
   - Tener instalado **Python 3.10 o superior** en Windows.
   - Poner la carpeta distribuida `hackudc` en cualquier lado de tu PC (ej: `Escritorio`).

2. **Primer Inicio**:
   - Haz doble clic en el archivo `blackvault_run.bat`.
   - **Nota**: La primera vez tardará un rato. El sistema detectará automáticamente tu instalación de Python, fabricará un entorno virtual aislado (`.venv`), e instalará en secreto todas las dependencias ML gigantes (LangChain, DuckDB, FastAPI).
   
3. **Uso Diario**:
   - Una vez instaladas las dependencias, las siguientes veces que ejecutes `blackvault_run.bat` será instantáneo. Abrirá un fondo transparente y verás el Agujero Negro en la esquina inferior derecha.

---

## ⌨️ Atajos de Teclado Globales (PowerToys)

Black Vault vive en segundo plano. Puedes llamarlo desde cualquier programa en Windows (Word, Navegador, etc) usando estos atajos maestros:

- `Ctrl + Shift + Espacio`: **Invocar Comando rápido**. Expande el agujero negro y abre instantáneamente la barra de texto superior lista para que escribas un comando. Si vuelves a pulsarlo, se esconde la interfaz.
- `Ctrl + Shift + B`: **Pánico / Modo Invisible**. Oculta o Muestra absolutamente todo el widget de Black Vault de la pantalla inmediatamente.

Estos atajos funcionan a nivel de sistema operativo aunque el foco del ratón esté en otra ventana.

---

## ⚡ Comandos del TextBox

Al pulsar en el Agujero Negro, o usar `Ctrl+Shift+Espacio`, se abrirá el cuadro de entrada de comandos y búsquedas. Funciona con estos prefijos:

| Comando | Acción | Ejemplo |
| :--- | :--- | :--- |
| *(Normal)* | Búsqueda Semántica Vectorial con IA. | `¿Quién es el asesino en el caso 4?` |
| `>s ` | Búsqueda Estricta de Texo (Exact Match). | `>s matríciula 1234-ABC` |
| `>n ` | Crea una nota rápida. El título será automático (Fecha y Hora). | `>n No olvidar revisar la coartada de Juan.` |
| `>url ` | Lee la web oculta en la URL, extrae el texto y lo memoriza en la BBDD. | `>url https://es.wikipedia.org/wiki/Misterio` |
| `>rm ` | Borra permanentemente un fragmento / nota por su identificador. | `>rm d61f-450f-a35f` |
| `>tag ` | Añade una etiqueta rápida a un ID existente. | `>tag d61f-450f-a35f importante` |

Cualquier archivo de texto, imagen, o PDF puede ser ingerido simplemente **arrastrándolo encima del agujero negro**. Además, un botón con el icono de 📋 en el menú intermedio te permite **pegar texto directamente desde el portapapeles**.
