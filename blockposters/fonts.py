"""Fuentes del sistema con soporte para acentos."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# Rutas habituales en Linux, macOS y Windows. Se usa la primera disponible.
_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


@lru_cache(maxsize=1)
def _font_path() -> str | None:
    for candidate in _CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def load_font(size_px: int) -> ImageFont.ImageFont:
    """Carga una fuente con acentos; si no hay, usa la de Pillow."""

    path = _font_path()
    if path:
        try:
            return ImageFont.truetype(path, max(1, size_px))
        except OSError:
            pass

    try:
        return ImageFont.load_default(size=size_px)
    except TypeError:  # Pillow antiguo sin tamaño para la fuente por defecto
        return ImageFont.load_default()
