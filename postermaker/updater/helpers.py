"""Funciones auxiliares para el localizador de repositorios y análisis de versión."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_git_dir() -> Path | None:
    """Busca el directorio raíz de Git del proyecto si existe."""
    # 1. Variable de entorno explícita
    env_dir = os.environ.get("POSTERMAKER_REPO_DIR")
    if env_dir and (Path(env_dir) / ".git").is_dir():
        return Path(env_dir).resolve()

    # 2. Archivo persistido de configuración ~/.config/postermaker/repo_path
    cfg_path = Path.home() / ".config/postermaker/repo_path"
    if cfg_path.is_file():
        try:
            candidate = Path(cfg_path.read_text(encoding="utf-8").strip())
            if (candidate / ".git").is_dir():
                return candidate.resolve()
        except Exception:
            pass

    # 3. Directorio superior del código fuente (cuando no está empaquetado en PyInstaller)
    if not (getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")):
        try:
            source_root = Path(__file__).resolve().parent.parent.parent
            if (source_root / ".git").is_dir():
                return source_root.resolve()
        except Exception:
            pass

    # 4. Directorio de trabajo actual
    try:
        cwd = Path.cwd().resolve()
        if (cwd / ".git").is_dir():
            return cwd
    except Exception:
        pass

    # 5. Directorios comunes en el $HOME del usuario
    home = Path.home()
    for rel_path in (
        "Projects/posters",
        "Projects/postermaker",
        "postermaker",
        "src/postermaker",
        "source/postermaker",
    ):
        cand = (home / rel_path).resolve()
        if (cand / ".git").is_dir():
            return cand

    return None


def _parse_version(v: str) -> tuple[int, ...]:
    """Convierte una cadena de versión semántica (ej. '0.2.2' o 'v0.2.2') en tupla numérica."""
    try:
        clean = v.lstrip("v").strip().split("-")[0]
        return tuple(int(x) for x in clean.split("."))
    except Exception:
        return (0, 0, 0)
