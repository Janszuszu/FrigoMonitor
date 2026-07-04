"""Tiny logger utility for MicroPython firmware."""

import time

from constants import LOG_DEBUG, LOG_ERROR, LOG_INFO, LOG_WARNING

DEBUG_ENABLED = True


def set_debug(enabled: bool) -> None:
    """Enable or disable DEBUG level logging."""
    global DEBUG_ENABLED
    DEBUG_ENABLED = enabled


def _timestamp() -> str:
    """Return a compact local timestamp when available."""
    try:
        year, month, day, hour, minute, second, _, _ = time.localtime()
        return (
            f"{year:04d}-{month:02d}-{day:02d} "
            f"{hour:02d}:{minute:02d}:{second:02d}"
        )
    except Exception:
        return "0000-00-00 00:00:00"


def _level_name(level: int) -> str:
    """Return printable log level name for a numeric level."""
    names = {
        LOG_DEBUG: "DEBUG",
        LOG_INFO: "INFO",
        LOG_WARNING: "WARNING",
        LOG_ERROR: "ERROR",
    }
    return names.get(level, "INFO")


def _log(level: int, message: str) -> None:
    """Emit a single formatted log line."""
    print(f"[{_timestamp()}] [{_level_name(level)}] {message}")


def debug(message: str) -> None:
    """Log DEBUG message when debug logging is enabled."""
    if DEBUG_ENABLED:
        _log(LOG_DEBUG, message)


def info(message: str) -> None:
    """Log INFO message."""
    _log(LOG_INFO, message)


def warning(message: str) -> None:
    """Log WARNING message."""
    _log(LOG_WARNING, message)


def error(message: str) -> None:
    """Log ERROR message."""
    _log(LOG_ERROR, message)
