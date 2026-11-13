"""Configuración, rutas y constantes del servidor web."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    cand = Path(sys._MEIPASS) / "postermaker"
    if cand.is_dir():
        BASE_DIR = cand
    else:
        BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = Path(
    os.environ.get(
        "POSTERMAKER_OUTPUT",
        str(Path(tempfile.gettempdir()) / "postermaker"),
    )
)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
JOB_PATTERN = re.compile(r"^[0-9a-f]{32}$")
MAX_JOB_AGE_SECONDS = 6 * 60 * 60


def get_output_dir() -> Path:
    """Devuelve OUTPUT_DIR permitiendo que monkeypatch.setattr(web, 'OUTPUT_DIR', ...) funcione dinámicamente."""
    web_mod = sys.modules.get("postermaker.web")
    if web_mod and hasattr(web_mod, "OUTPUT_DIR"):
        return Path(getattr(web_mod, "OUTPUT_DIR"))
    return OUTPUT_DIR
