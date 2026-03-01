"""
Speech-to-Text module using Vosk and ffmpeg.
"""
import json
import logging
import shutil
import subprocess
import threading
from pathlib import Path

from vosk import Model, KaldiRecognizer

_logger = logging.getLogger(__name__)

# Supported audio formats
SUPPORTED_EXTENSIONS = {".wav", ".ogg", ".mp3", ".m4a", ".flac", ".aac", ".wma"}

_model = None
try:
    import vosk
    vosk.SetLogLevel(-1)
    _model = Model(lang="es")
except Exception as e:
    _logger.warning(f"No se pudo cargar el modelo Vosk. El STT no funcionará: {e}")


def _find_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        # Fallback a ffmpeg del sistema si imageio-ffmpeg no está
        found = shutil.which("ffmpeg")
        if found:
            return found
        raise FileNotFoundError(
            "ffmpeg no encontrado. Instala imageio-ffmpeg: pip install imageio-ffmpeg"
        )


def extract_text_from_audio(filepath: Path | str) -> str:
    """
    Extrae el texto de un archivo de audio utilizando Vosk.

    Convierte internamente el audio a PCM mono 16kHz usando ffmpeg,
    por lo que acepta cualquier formato soportado por ffmpeg
    (.wav, .mp3, .ogg, .m4a, .flac, etc.).

    Args:
        filepath: Ruta al archivo de audio.

    Returns:
        Texto transcrito como string (puede ser vacío si no hay voz).

    Raises:
        RuntimeError: Si el modelo Vosk no está inicializado o ffmpeg no se encuentra.
        ValueError: Si ffmpeg no puede procesar el archivo.
        FileNotFoundError: Si el archivo no existe.
    """
    if _model is None:
        raise RuntimeError("El modelo Vosk no está inicializado.")

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    ext = filepath.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        _logger.warning(
            f"Extensión '{ext}' no está en la lista de soportadas {SUPPORTED_EXTENSIONS}. "
            "Se intentará procesar de todas formas con ffmpeg."
        )

    try:
        ffmpeg_cmd = _find_ffmpeg()
    except FileNotFoundError as e:
        raise RuntimeError(str(e)) from e

    command = [
        ffmpeg_cmd,
        "-v", "quiet",        # Sin logs de ffmpeg en stderr (salvo errores reales)
        "-i", str(filepath),  # Entrada
        "-ar", "16000",       # Sample rate requerido por Vosk
        "-ac", "1",           # Mono
        "-f", "s16le",        # PCM 16-bit little-endian sin cabecera
        "-",                  # Salida a stdout
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"No se pudo ejecutar ffmpeg: {e}") from e

    # Leemos stderr en un hilo aparte para evitar deadlocks cuando el
    # buffer interno de stderr se llena mientras leemos stdout.
    stderr_lines: list[bytes] = []

    def _read_stderr():
        for line in process.stderr:
            stderr_lines.append(line)

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    rec = KaldiRecognizer(_model, 16000)
    rec.SetWords(False)

    results: list[str] = []
    chunk_size = 4000  # bytes (~125 ms a 16kHz mono 16-bit)

    try:
        while True:
            data = process.stdout.read(chunk_size)
            if not data:
                break
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                text = res.get("text", "").strip()
                if text:
                    results.append(text)
    finally:
        process.stdout.close()
        stderr_thread.join(timeout=5)
        process.wait()

    # Capturar el fragmento final que Vosk aún no ha emitido
    final_res = json.loads(rec.FinalResult())
    final_text = final_res.get("text", "").strip()
    if final_text:
        results.append(final_text)

    # Revisar código de salida de ffmpeg
    if process.returncode != 0:
        err = b"".join(stderr_lines).decode("utf-8", errors="replace").strip()
        _logger.error(f"ffmpeg terminó con código {process.returncode}: {err}")
        if not results:
            raise ValueError(
                f"No se pudo procesar '{filepath.name}' con ffmpeg "
                f"(código {process.returncode}). ¿Es un archivo de audio válido?\n{err}"
            )
        # Si ya tenemos texto parcial, lo devolvemos con una advertencia
        _logger.warning("ffmpeg reportó error pero se obtuvo transcripción parcial.")

    return " ".join(results)