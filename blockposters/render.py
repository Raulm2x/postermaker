"""Generación de las hojas del póster."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from .fonts import load_font
from .grid import Grid
from .paper import MM_PER_INCH


@dataclass(frozen=True)
class RenderOptions:
    dpi: int = 300
    overlap_mm: float = 0.0
    marks: bool = False
    labels: bool = False
    assembly_guide: bool = False
    jpeg_quality: int = 92

    def __post_init__(self) -> None:
        if not isinstance(self.dpi, int) or not 72 <= self.dpi <= 600:
            raise ValueError("El DPI debe estar entre 72 y 600.")
        if not 0 <= self.overlap_mm <= 25:
            raise ValueError("El solapamiento debe estar entre 0 y 25 mm.")
        if not 60 <= self.jpeg_quality <= 100:
            raise ValueError("La calidad JPEG debe estar entre 60 y 100.")


@dataclass
class RenderResult:
    page_paths: list[Path]
    render_dpi: float
    page_width_px: int
    page_height_px: int

    @property
    def total_pages(self) -> int:
        return len(self.page_paths)


def _px(mm: float, dpi: float) -> int:
    """Milímetros a píxeles, redondeando."""

    return int(round(mm / MM_PER_INCH * dpi))


def _size_px(mm: float, dpi: float) -> int:
    return max(1, _px(mm, dpi))


def _font(size_px: int):
    return load_font(size_px)


def _draw_crop_marks(
    draw: ImageDraw.ImageDraw, grid: Grid, dpi: float, row: int, col: int = 0
) -> None:
    """Pequeñas marcas en las esquinas del área de imagen de una hoja."""

    m = grid.margins
    left, top, right, bottom = grid.image_box_in_page_mm(row, col)
    space_right = grid.page_width_mm - right
    space_below = grid.page_height_mm - bottom

    lengths = {
        "top": min(3.0, m.top * 0.8),
        "bottom": min(3.0, space_below * 0.8),
        "left": min(3.0, m.left * 0.8),
        "right": min(3.0, space_right * 0.8),
    }
    if min(lengths.values()) < 0.6:
        return

    width = max(1, _px(0.2, dpi))
    color = (135, 135, 135)

    def line(x0: float, y0: float, x1: float, y1: float) -> None:
        draw.line(
            [(_px(x0, dpi), _px(y0, dpi)), (_px(x1, dpi), _px(y1, dpi))],
            fill=color,
            width=width,
        )

    # esquina superior izquierda
    line(left - lengths["left"], top, left, top)
    line(left, top - lengths["top"], left, top)
    # esquina superior derecha
    line(right, top, right + lengths["right"], top)
    line(right, top - lengths["top"], right, top)
    # esquina inferior izquierda
    line(left - lengths["left"], bottom, left, bottom)
    line(left, bottom, left, bottom + lengths["bottom"])
    # esquina inferior derecha
    line(right, bottom, right + lengths["right"], bottom)
    line(right, bottom, right, bottom + lengths["bottom"])


def _draw_page_label(
    draw: ImageDraw.ImageDraw,
    grid: Grid,
    dpi: float,
    page_width_px: int,
    page_height_px: int,
    index: int,
    row: int,
    col: int,
) -> None:
    if not grid.margins.bottom >= 3.0:
        return

    font_mm = min(3.6, grid.margins.bottom * 0.42)
    font = _font(max(8, _size_px(font_mm, dpi)))

    _, _, _, image_bottom = grid.image_box_in_page_mm(row)
    space_below = grid.page_height_mm - image_bottom
    if row < grid.pages_high - 1:
        label_y_mm = grid.page_height_mm - grid.margins.bottom / 2
    else:
        label_y_mm = image_bottom + min(4.0, space_below / 2)

    text = f"{index}/{grid.total_pages}  ·  F{row + 1} C{col + 1}"
    draw.text(
        (page_width_px / 2, _px(label_y_mm, dpi)),
        text,
        fill=(120, 120, 120),
        font=font,
        anchor="mm",
    )


def render_pages(
    source: Image.Image,
    grid: Grid,
    output_dir: str | Path,
    options: RenderOptions | None = None,
) -> RenderResult:
    """Divide ``source`` en hojas JPEG listas para el PDF.

    ``source`` debe estar ya recortada al aspecto del póster (ver
    ``prepare_source``). Se procesa hoja a hoja para no mantener el póster
    completo en memoria.
    """

    options = options or RenderOptions()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    source_width, source_height = source.size
    if source_width <= 0 or source_height <= 0:
        raise ValueError("La imagen de origen está vacía.")

    width_in = grid.poster_width_mm / MM_PER_INCH
    height_in = grid.poster_height_mm / MM_PER_INCH
    effective_dpi = min(source_width / width_in, source_height / height_in)

    # No ampliamos más de lo que permite la imagen; aun así, mantenemos un
    # mínimo de 72 ppp para que las marcas y el texto sean legibles.
    render_dpi = float(max(72.0, min(float(options.dpi), effective_dpi)))

    page_width_px = _size_px(grid.page_width_mm, render_dpi)
    page_height_px = _size_px(grid.page_height_mm, render_dpi)

    # Escala de la imagen de origen, en píxeles por milímetro de póster.
    src_x = source_width / grid.poster_width_mm
    src_y = source_height / grid.poster_height_mm

    page_paths: list[Path] = []
    index = 0

    if options.assembly_guide:
        from .guide import render_assembly_guide

        guide = render_assembly_guide(
            source, grid, dpi=render_dpi, overlap_mm=options.overlap_mm
        )
        guide_path = output / "page_000_guide.jpg"
        guide.save(
            guide_path,
            "JPEG",
            quality=options.jpeg_quality,
            subsampling=0,
            dpi=(round(render_dpi), round(render_dpi)),
        )
        guide.close()
        page_paths.append(guide_path)

    for row in range(grid.pages_high):
        for col in range(grid.pages_wide):
            index += 1
            x0, y0, x1, y1 = grid.tile_box_mm(row, col, options.overlap_mm)

            left = max(0, min(source_width - 1, int(round(x0 * src_x))))
            top = max(0, min(source_height - 1, int(round(y0 * src_y))))
            right = max(left + 1, min(source_width, int(round(x1 * src_x))))
            bottom = max(top + 1, min(source_height, int(round(y1 * src_y))))

            piece = source.crop((left, top, right, bottom))
            target_w = _size_px(x1 - x0, render_dpi)
            target_h = _size_px(y1 - y0, render_dpi)
            piece = piece.resize((target_w, target_h), Image.Resampling.LANCZOS)

            page = Image.new("RGB", (page_width_px, page_height_px), (255, 255, 255))
            paste_x, paste_y = grid.paste_offset_mm(row, col, options.overlap_mm)
            page.paste(piece, (_px(paste_x, render_dpi), _px(paste_y, render_dpi)))
            piece.close()

            draw = ImageDraw.Draw(page)
            if options.marks:
                _draw_crop_marks(draw, grid, render_dpi, row, col)
            if options.labels:
                _draw_page_label(
                    draw,
                    grid,
                    render_dpi,
                    page_width_px,
                    page_height_px,
                    index,
                    row,
                    col,
                )

            page_path = output / f"page_{index:03d}.jpg"
            page.save(
                page_path,
                "JPEG",
                quality=options.jpeg_quality,
                subsampling=0,
                dpi=(round(render_dpi), round(render_dpi)),
            )
            page.close()
            page_paths.append(page_path)

    return RenderResult(
        page_paths=page_paths,
        render_dpi=render_dpi,
        page_width_px=page_width_px,
        page_height_px=page_height_px,
    )


def render_preview(
    source: Image.Image,
    grid: Grid,
    output_path: str | Path,
    *,
    max_width: int = 1400,
    max_height: int = 1800,
) -> Path:
    """Vista previa con las líneas de corte, para el CLI."""

    preview = source.copy()
    preview.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(preview)
    width, height = preview.size
    line_width = max(1, round(width / 900))
    color = (228, 87, 46)

    for col in range(1, grid.pages_wide):
        x = round(width * (col * grid.usable_width_mm) / grid.poster_width_mm)
        draw.line([(x, 0), (x, height)], fill=color, width=line_width)
    for row in range(1, grid.pages_high):
        y = round(height * (row * grid.usable_height_mm) / grid.poster_height_mm)
        draw.line([(0, y), (width, y)], fill=color, width=line_width)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output)
    preview.close()
    return output
