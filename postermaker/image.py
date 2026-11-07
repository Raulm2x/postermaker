"""Carga y preparación de la imagen de origen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from .paper import MM_PER_INCH
from .grid import Grid

MAX_SOURCE_PIXELS = 80_000_000


class ImageError(ValueError):
    """Error de imagen con un mensaje apto para mostrar al usuario."""


@dataclass
class PreparedSource:
    image: Image.Image
    effective_dpi: float

    def close(self) -> None:
        self.image.close()


def open_image(source: str | Path | BinaryIO) -> Image.Image:
    """Abre una imagen, corrige la orientación EXIF y la deja en RGB."""

    try:
        image = Image.open(source)
        width, height = image.size
        if width * height > MAX_SOURCE_PIXELS:
            megapixels = width * height / 1_000_000
            raise ImageError(
                f"La imagen tiene {megapixels:.0f} MP; el máximo es "
                f"{MAX_SOURCE_PIXELS / 1_000_000:.0f} MP."
            )
        image = ImageOps.exif_transpose(image)
        image.load()
    except ImageError:
        raise
    except UnidentifiedImageError as exc:
        raise ImageError(
            "No se pudo leer la imagen. Usa un archivo JPG, PNG o WebP válido."
        ) from exc
    except OSError as exc:
        raise ImageError(f"No se pudo abrir la imagen: {exc}") from exc
    except Image.DecompressionBombError as exc:
        raise ImageError("La imagen es demasiado grande para procesarla.") from exc

    return _to_rgb(image)


def _to_rgb(image: Image.Image) -> Image.Image:
    """Convierte a RGB aplanando la transparencia sobre blanco."""

    if image.mode == "RGB":
        return image

    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        rgba.close()
        return background

    return image.convert("RGB")


def center_crop_to_aspect(image: Image.Image, aspect: float) -> Image.Image:
    """Recorta centrada la imagen al aspecto indicado (ancho / alto)."""

    if aspect <= 0:
        raise ValueError("El aspecto debe ser mayor que cero.")

    width, height = image.size
    current = width / height
    if abs(current - aspect) < 1e-6:
        return image

    if current > aspect:
        new_width = max(1, round(height * aspect))
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))

    new_height = max(1, round(width / aspect))
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


COLOR_MODES = ("color", "grayscale", "monochrome")


def apply_color_mode(image: Image.Image, mode: str = "color") -> Image.Image:
    """Aplica un modo de color a la imagen (color, grayscale o monochrome)."""

    mode = (mode or "color").strip().lower()
    if mode in ("color", "rgb"):
        return image
    if mode in ("grayscale", "bw", "bn", "gris", "grises"):
        gray = image.convert("L")
        return gray.convert("RGB")
    if mode in ("monochrome", "mono", "high_contrast", "umbral", "1bit"):
        gray = image.convert("L")
        # Umbralización limpia para blanco y negro puro
        mono = gray.point(lambda p: 255 if p > 130 else 0, mode="1")
        return mono.convert("RGB")
    disponibles = ", ".join(COLOR_MODES)
    raise ValueError(
        f"Modo de color desconocido: {mode!r}. Opciones: {disponibles}."
    )


def prepare_source(
    image: Image.Image, grid: Grid, color_mode: str = "color"
) -> PreparedSource:
    """Recorta la imagen al aspecto del póster, aplica color y calcula su DPI efectivo."""

    aspect = grid.poster_width_mm / grid.poster_height_mm
    cropped = center_crop_to_aspect(image, aspect)
    processed = apply_color_mode(cropped, color_mode)
    if processed is not cropped and cropped is not image:
        cropped.close()

    width_in = grid.poster_width_mm / MM_PER_INCH
    height_in = grid.poster_height_mm / MM_PER_INCH
    dpi_x = processed.width / width_in
    dpi_y = processed.height / height_in

    return PreparedSource(image=processed, effective_dpi=min(dpi_x, dpi_y))
