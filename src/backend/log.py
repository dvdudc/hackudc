"""
Black Vault — Logging configuration.
Manages the persistent logging state and file handler setup.
"""

import logging
from pathlib import Path

# Paths
_src_dir = Path(__file__).resolve().parent.parent
_log_active_marker: Path = _src_dir / ".logging_active"
_log_file: Path = _src_dir / "blackvault.log"

def toggle_logging() -> bool:
    """
    Toggles file logging.
    Creates or removes the .logging_active marker and an empty log file.
    Returns:
        True if logging was just enabled, False if it was disabled.
    """
    if _log_active_marker.exists():
        _log_active_marker.unlink()
        return False
    else:
        _log_active_marker.touch()
        # Initialize an empty log file if it doesn't exist
        if not _log_file.exists():
            _log_file.touch()
        return True

def setup_file_logging():
    """
    Adds a FileHandler to the root logger if logging is active.
    Should be called after logging.basicConfig.
    """
    if _log_active_marker.exists():
        file_handler = logging.FileHandler(_log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)