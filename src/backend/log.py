"""
Black Vault — Logging configuration.
Manages persistent logging state and file handler setup.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Paths
_src_dir = Path(__file__).resolve().parent.parent
_log_active_marker: Path = _src_dir / ".logging_active"
_log_file: Path = _src_dir / "blackvault.log"

_logger = logging.getLogger(__name__)

# Nombre único para identificar nuestro handler y evitar duplicados
_HANDLER_NAME = "blackvault_file_handler"


def _get_existing_handler() -> RotatingFileHandler | None:
    """Returns the BlackVault file handler if it's already attached to the root logger."""
    for h in logging.getLogger().handlers:
        if getattr(h, "name", None) == _HANDLER_NAME:
            return h
    return None


def toggle_logging() -> bool:
    """
    Toggles file logging on/off via a persistent marker file.

    - If enabling: creates the marker and sets up the file handler.
    - If disabling: removes the marker, writes a stop message, and removes the handler cleanly.

    Returns:
        True if logging was just enabled, False if it was disabled.
    """
    if _log_active_marker.exists():
        # --- Disable ---
        handler = _get_existing_handler()
        if handler:
            _logger.info("=== File logging stopped ===")
            handler.flush()
            logging.getLogger().removeHandler(handler)
            handler.close()

        _log_active_marker.unlink()
        return False

    else:
        # --- Enable ---
        _log_active_marker.touch()
        _log_file.parent.mkdir(parents=True, exist_ok=True)
        setup_file_logging()
        _logger.info("=== File logging started ===")
        return True


def setup_file_logging(
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> bool:
    """
    Adds a RotatingFileHandler to the root logger if logging is active.
    Safe to call multiple times — won't add duplicate handlers.

    Args:
        level: Logging level for the file handler.
        max_bytes: Max log file size before rotation (default 5 MB).
        backup_count: Number of rotated backups to keep.

    Returns:
        True if handler was added, False otherwise.
    """
    if not _log_active_marker.exists():
        return False

    # Guard: ya existe un handler activo
    if _get_existing_handler() is not None:
        return False

    try:
        handler = RotatingFileHandler(
            _log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.name = _HANDLER_NAME  # identificador único
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logging.getLogger().addHandler(handler)
        return True

    except PermissionError as e:
        _logger.error("Could not create log file handler: %s", e)
        return False