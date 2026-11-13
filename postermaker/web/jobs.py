"""Gestión de almacenamiento temporal, metadatos y empaquetado de trabajos."""

from __future__ import annotations

import json
import shutil
import time
import zipfile
from pathlib import Path

from flask import abort

from .config import JOB_PATTERN, MAX_JOB_AGE_SECONDS, get_output_dir


def _cleanup_old_jobs() -> None:
    output_dir = get_output_dir()
    if not output_dir.is_dir():
        return
    now = time.time()
    for child in output_dir.iterdir():
        try:
            if child.is_dir() and now - child.stat().st_mtime > MAX_JOB_AGE_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue


def _job_dir(job_id: str) -> Path:
    if not JOB_PATTERN.fullmatch(job_id):
        abort(404)
    return get_output_dir() / job_id


def _read_meta(job_dir: Path) -> dict:
    try:
        return json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def create_tiles_zip(job_dir: Path) -> Path:
    """Empaqueta los azulejos JPG en un archivo ZIP con instrucciones de montaje."""
    tiles_dir = job_dir / "tiles"
    if not tiles_dir.is_dir():
        abort(404)

    zip_path = job_dir / "tiles.zip"
    if not zip_path.is_file():
        meta = _read_meta(job_dir)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(tiles_dir.rglob("*.jpg")):
                arcname = p.relative_to(tiles_dir).as_posix()
                zf.write(p, arcname=arcname)
            readme = (
                f"PosterMaker Local - Piezas individuales del póster\n"
                f"Archivos procesados: {meta.get('poster_count', 1)}\n"
                f"Total de páginas: {meta.get('total_pages', meta.get('pages_wide', 1) * meta.get('pages_high', 1))}\n\n"
                f"Instrucciones de impresión:\n"
                f"1. Imprime cada archivo JPG a tamaño real (100% de escala, sin ajustar a página).\n"
                f"2. Recorta los bordes blancos siguiendo las marcas de corte.\n"
                f"3. Ensambla las hojas de izquierda a derecha y de arriba a abajo.\n"
            )
            zf.writestr("INSTRUCCIONES_MONTAJE.txt", readme)

    return zip_path
