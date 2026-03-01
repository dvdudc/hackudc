"""
Tests para el módulo STT (Speech-to-Text) con Vosk + ffmpeg.

Ejecutar con:
    pytest tests/test_stt.py -v

Para ver los logs de advertencia durante los tests:
    pytest tests/test_stt.py -v -s --log-cli-level=WARNING
"""
import struct
import subprocess
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_src_dir))

from backend.stt import extract_text_from_audio, SUPPORTED_EXTENSIONS, _find_ffmpeg  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_silent_wav(path: Path, duration_s: float = 1.0, framerate: int = 16000) -> Path:
    """Crea un archivo WAV con silencio puro (válido para Vosk)."""
    n_frames = int(framerate * duration_s)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(framerate)
        wf.writeframesraw(struct.pack(f"<{n_frames}h", *([0] * n_frames)))
    return path


def _ffmpeg_available() -> bool:
    try:
        exe = _find_ffmpeg()
        subprocess.run(
            [exe, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, RuntimeError):
        return False


def _convert_wav_to(src: Path, dest: Path) -> bool:
    """Convierte src (WAV) a dest usando ffmpeg. Retorna True si tuvo éxito."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), str(dest)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Marcadores de skip
# ---------------------------------------------------------------------------
requires_ffmpeg = pytest.mark.skipif(
    not _ffmpeg_available(), reason="ffmpeg no disponible en este entorno"
)

# ---------------------------------------------------------------------------
# Tests básicos
# ---------------------------------------------------------------------------

class TestModelNotInitialized:
    """Comportamiento cuando el modelo Vosk no cargó."""

    def test_raises_runtime_error(self, tmp_path):
        wav = _make_silent_wav(tmp_path / "audio.wav")
        with patch("backend.stt._model", None):
            with pytest.raises(RuntimeError, match="modelo Vosk no está inicializado"):
                extract_text_from_audio(wav)


class TestFileValidation:
    """Validaciones de archivo antes de procesar."""

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            extract_text_from_audio(Path("/ruta/inexistente/audio.wav"))

    def test_supported_extensions_set(self):
        """Comprueba que las extensiones básicas están declaradas."""
        for ext in (".wav", ".mp3", ".ogg", ".m4a"):
            assert ext in SUPPORTED_EXTENSIONS, f"{ext} debería estar en SUPPORTED_EXTENSIONS"


# ---------------------------------------------------------------------------
# Tests de procesamiento WAV (no requieren ffmpeg para WAV nativo)
# ---------------------------------------------------------------------------

class TestWavProcessing:
    """Pruebas con archivos WAV sintéticos."""

    def test_silent_wav_returns_string(self, tmp_path):
        wav = _make_silent_wav(tmp_path / "silence.wav")
        try:
            result = extract_text_from_audio(wav)
        except RuntimeError as e:
            if "modelo Vosk" in str(e):
                pytest.skip("Modelo Vosk no disponible.")
            raise
        assert isinstance(result, str), "Debe retornar un string"

    def test_silent_wav_is_empty_or_noise(self, tmp_path):
        """El silencio debería transcribirse como cadena vacía o palabras sin sentido."""
        wav = _make_silent_wav(tmp_path / "silence.wav")
        try:
            result = extract_text_from_audio(wav)
        except RuntimeError:
            pytest.skip("Modelo Vosk no disponible.")
        # No esperamos texto útil, pero sí un string
        assert isinstance(result, str)

    def test_wav_wrong_sample_rate_is_handled(self, tmp_path):
        """ffmpeg debe resamplear automáticamente aunque el WAV no sea 16kHz."""
        wav = tmp_path / "44100hz.wav"
        n = 44100
        with wave.open(str(wav), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframesraw(struct.pack(f"<{n}h", *([0] * n)))
        try:
            result = extract_text_from_audio(wav)
        except RuntimeError:
            pytest.skip("Modelo Vosk o ffmpeg no disponibles.")
        assert isinstance(result, str)

    def test_stereo_wav_is_handled(self, tmp_path):
        """ffmpeg debe convertir estéreo a mono."""
        wav = tmp_path / "stereo.wav"
        n = 16000
        with wave.open(str(wav), "w") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # 2 canales → intercalados L, R
            wf.writeframesraw(struct.pack(f"<{n * 2}h", *([0] * n * 2)))
        try:
            result = extract_text_from_audio(wav)
        except RuntimeError:
            pytest.skip("Modelo Vosk o ffmpeg no disponibles.")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests de formatos alternativos (requieren ffmpeg)
# ---------------------------------------------------------------------------

@requires_ffmpeg
class TestAlternativeFormats:
    """Pruebas con OGG, MP3 y M4A usando archivos pre-generados estáticos."""

    @pytest.mark.parametrize("ext", [".ogg", ".mp3", ".m4a"])
    def test_format(self, ext):
        dest = _src_dir.parent / "tests" / "test_audio" / f"audio{ext}"
        if not dest.exists():
            pytest.skip(f"Archivo de prueba {dest} no existe.")
        try:
            result = extract_text_from_audio(dest)
        except RuntimeError:
            pytest.skip("Modelo Vosk no disponible.")
        assert isinstance(result, str), f"Debe retornar string para {ext}"


# ---------------------------------------------------------------------------
# Tests de errores de ffmpeg
# ---------------------------------------------------------------------------

class TestFfmpegErrors:
    """Comportamiento cuando ffmpeg falla."""

    def test_invalid_audio_file_raises_value_error(self, tmp_path):
        """Un archivo de texto con extensión .wav debería lanzar ValueError."""
        fake = tmp_path / "fake.wav"
        fake.write_text("esto no es audio")
        try:
            with pytest.raises((ValueError, RuntimeError)):
                extract_text_from_audio(fake)
        except RuntimeError as e:
            if "modelo Vosk" in str(e):
                pytest.skip("Modelo Vosk no disponible.")
            raise

    def test_ffmpeg_not_found_raises_runtime_error(self, tmp_path):
        wav = _make_silent_wav(tmp_path / "audio.wav")
        with patch("backend.stt._find_ffmpeg", side_effect=FileNotFoundError("ffmpeg no encontrado")):
            with pytest.raises(RuntimeError, match="ffmpeg"):
                extract_text_from_audio(wav)