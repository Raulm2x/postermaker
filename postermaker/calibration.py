"""Hoja de calibración para medir el margen no imprimible."""

from __future__ import annotations

import tempfile
from pathlib import Path

import img2pdf
from PIL import Image, ImageDraw

from .fonts import load_font
from .paper import MM_PER_INCH, get_page_size_mm, get_paper


def _px(mm: float, dpi: int) -> int:
    return int(round(mm / MM_PER_INCH * dpi))


def _font(size_mm: float, dpi: int):
    return load_font(max(8, _px(size_mm, dpi)))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    x: int,
    y: int,
    max_width: int,
    line_height: int,
    fill: tuple[int, int, int],
) -> int:
    for line in _wrap(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def calibration_pdf(paper: str = "letter") -> bytes:
    """Genera un PDF de una página para medir la impresora."""

    paper_size = get_paper(paper)
    page_w, page_h = get_page_size_mm(paper_size, "portrait")
    dpi = 150
    width = _px(page_w, dpi)
    height = _px(page_h, dpi)

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    ink = (28, 42, 42)
    muted = (100, 108, 108)
    accent = (228, 87, 46)

    margin = _px(18, dpi)
    x = margin
    y = _px(22, dpi)
    max_width = width - 2 * margin

    title_font = _font(8.5, dpi)
    subtitle_font = _font(4.2, dpi)
    body_font = _font(3.8, dpi)
    small_font = _font(3.2, dpi)
    ruler_font = _font(3.4, dpi)

    draw.text((x, y), "Hoja de calibración", font=title_font, fill=ink)
    y += _px(13, dpi)

    draw.text(
        (x, y),
        f"Impresora y papel {paper_size.name} · imprime al 100 % de escala",
        font=subtitle_font,
        fill=accent,
    )
    y += _px(12, dpi)

    steps = [
        "1. Imprime esta página sin «ajustar a la página» ni «escalar para encajar». El papel debe ser el mismo que usarás para el póster.",
        "2. Mide con una regla la línea de 100 mm de abajo. Si no mide exactamente 100 mm, tu impresora está escalando la imagen: desactiva esa opción y vuelve a imprimir.",
        "3. Mide el borde blanco que queda en cada uno de los cuatro lados. Ese es el margen que la impresora no puede imprimir.",
        "4. Introduce el valor mayor como «margen de impresión» en la aplicación. Si tu impresora imprime sin bordes, usa 0 mm.",
    ]
    for step in steps:
        y = _draw_text_block(
            draw,
            step,
            body_font,
            x,
            y,
            max_width,
            _px(6.2, dpi),
            ink,
        )
        y += _px(2.5, dpi)

    # Regla horizontal de 100 mm
    y = max(y + _px(6, dpi), _px(118, dpi))
    ruler_x = x
    ruler_y = y
    ruler_len = _px(100, dpi)
    draw.line([(ruler_x, ruler_y), (ruler_x + ruler_len, ruler_y)], fill=ink, width=_px(0.35, dpi))
    for mm in range(0, 101, 5):
        tick = _px(4, dpi) if mm % 10 == 0 else _px(2.2, dpi)
        px = ruler_x + _px(mm, dpi)
        draw.line([(px, ruler_y - tick), (px, ruler_y)], fill=ink, width=_px(0.25, dpi))
        if mm % 20 == 0:
            label = f"{mm}"
            draw.text(
                (px, ruler_y + _px(2, dpi)),
                label,
                font=ruler_font,
                fill=muted,
                anchor="ma",
            )
    draw.text(
        (ruler_x + ruler_len / 2, ruler_y + _px(9, dpi)),
        "100 mm",
        font=small_font,
        fill=accent,
        anchor="ma",
    )

    # Regla vertical de 100 mm
    ruler_y2 = ruler_y + _px(24, dpi)
    ruler_x2 = x
    draw.line([(ruler_x2, ruler_y2), (ruler_x2, ruler_y2 + ruler_len)], fill=ink, width=_px(0.35, dpi))
    for mm in range(0, 101, 5):
        tick = _px(4, dpi) if mm % 10 == 0 else _px(2.2, dpi)
        py = ruler_y2 + _px(mm, dpi)
        draw.line([(ruler_x2, py), (ruler_x2 + tick, py)], fill=ink, width=_px(0.25, dpi))
        if mm % 20 == 0:
            draw.text(
                (ruler_x2 + _px(5.5, dpi), py),
                f"{mm}",
                font=ruler_font,
                fill=muted,
                anchor="lm",
            )
    draw.text(
        (ruler_x2 + _px(13, dpi), ruler_y2 + ruler_len / 2),
        "100 mm",
        font=small_font,
        fill=accent,
        anchor="lm",
    )

    # Cuadrícula de referencia de 10 mm
    ruler_end_x = ruler_x + ruler_len
    grid_x = width - margin - _px(55, dpi)
    if grid_x < ruler_end_x + _px(8, dpi):
        # En hojas más estrechas (ej. A5), ubicamos la cuadrícula debajo de la regla vertical
        grid_x = x
        grid_y = ruler_y2 + ruler_len + _px(8, dpi)
    else:
        grid_y = ruler_y
    cell = _px(10, dpi)
    for i in range(6):
        px = grid_x + i * cell
        draw.line([(px, grid_y), (px, grid_y + 5 * cell)], fill=(220, 220, 215), width=_px(0.2, dpi))
        py = grid_y + i * cell
        draw.line([(grid_x, py), (grid_x + 5 * cell, py)], fill=(220, 220, 215), width=_px(0.2, dpi))
    draw.text(
        (grid_x, grid_y + 5 * cell + _px(4, dpi)),
        "Cuadrícula de 10 mm",
        font=small_font,
        fill=muted,
    )

    note_y = height - _px(34, dpi)
    draw.line([(margin, note_y), (width - margin, note_y)], fill=(220, 220, 215), width=_px(0.25, dpi))
    _draw_text_block(
        draw,
        "El margen se recorta después de imprimir: no forma parte del póster. "
        "Si todas las hojas usan el mismo margen, las piezas encajan sin líneas blancas.",
        small_font,
        margin,
        note_y + _px(5, dpi),
        max_width,
        _px(5, dpi),
        muted,
    )

    with tempfile.TemporaryDirectory() as tmp:
        jpg_path = Path(tmp) / "calibracion.jpg"
        image.save(jpg_path, "JPEG", quality=95, subsampling=0, dpi=(dpi, dpi))
        layout = img2pdf.get_layout_fun(
            (img2pdf.mm_to_pt(page_w), img2pdf.mm_to_pt(page_h))
        )
        data = img2pdf.convert(
            str(jpg_path),
            layout_fun=layout,
            title=f"PosterMaker · Calibración {paper_size.name}",
        )
    image.close()
    return data
