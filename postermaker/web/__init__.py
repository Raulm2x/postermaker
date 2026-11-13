"""Servidor web local con la interfaz para crear pósteres."""

from __future__ import annotations

from ..updater import updater
from .config import (
    BASE_DIR,
    JOB_PATTERN,
    MAX_JOB_AGE_SECONDS,
    MAX_UPLOAD_BYTES,
    OUTPUT_DIR,
    STATIC_DIR,
)
from .inactivity import InactivityManager, inactivity_manager
from .routes import app
from .server import (
    _find_available_port,
    _is_port_available,
    _is_postermaker_running,
    _open_in_browser,
    main,
)

__all__ = [
    "BASE_DIR",
    "InactivityManager",
    "JOB_PATTERN",
    "MAX_JOB_AGE_SECONDS",
    "MAX_UPLOAD_BYTES",
    "OUTPUT_DIR",
    "STATIC_DIR",
    "_find_available_port",
    "_is_port_available",
    "_is_postermaker_running",
    "_open_in_browser",
    "app",
    "inactivity_manager",
    "main",
    "updater",
]
