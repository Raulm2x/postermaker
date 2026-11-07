"""Generación de la hoja de guía y plano de montaje para el PDF."""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

from .fonts import load_font
from .grid import Grid
from .paper import MM_PER_INCH


def _px(mm: float, dpi: float) -> int:
    return int(round(mm / MM_PER_INCH * dpi))


def _font(size_px: int):
    return load_font(max(8, int(round(size_px))))


def render_assembly_guide(
    source: Image.Image,
    grid: Grid,
    dpi: float = 150.0,
    overlap_mm: float = 0.0,
) -> Image.Image:
    """Crea una hoja con el mapa de montaje y las instrucciones de ensamblado."""

    page_w_px = max(1, _px(grid.page_width_mm, dpi))
    page_h_px = max(1, _px(grid.page_height_mm, dpi))

    page = Image.new("RGB", (page_w_px, page_h_px), (255, 255, 255))
    draw = ImageDraw.Draw(page)

    # Colores coherentes con el diseño de la aplicación
    ink = (24, 34, 34)
    muted = (105, 115, 115)
    accent = (228, 87, 46)
    border_color = (215, 222, 220)
    box_bg = (246, 248, 248)

    margin_px = _px(14.0, dpi)
    content_w = page_w_px - 2 * margin_px

    y = _px(15.0, dpi)

    # 1. Cabecera
    title_font = _font(_px(6.5, dpi))
    subtitle_font = _font(_px(3.6, dpi))
    small_font = _font(_px(2.8, dpi))
    bold_small_font = _font(_px(3.0, dpi))

    draw.text((margin_px, y), "GUÍA DE MONTAJE", font=title_font, fill=ink)
    y += _px(8.5, dpi)

    orient_str = "vertical" if grid.orientation == "portrait" else "horizontal"
    partial_row = grid.last_row_height_mm < grid.usable_height_mm - 0.5
    partial_col = grid.last_col_width_mm < grid.usable_width_mm - 0.5
    partial_notes = []
    if partial_row:
        partial_notes.append("última fila parcial")
    if partial_col:
        partial_notes.append("última columna parcial")
    extra_info = f" · {', '.join(partial_notes)}" if partial_notes else ""

    sub_text = (
        f"Póster de {grid.pages_wide} × {grid.pages_high} hojas "
        f"({grid.total_pages} páginas) · {grid.poster_width_cm:.1f} × {grid.poster_height_cm:.1f} cm"
        f"{extra_info}"
    )
    draw.text((margin_px, y), sub_text, font=subtitle_font, fill=accent)
    y += _px(6.0, dpi)

    meta_text = (
        f"Papel: {grid.paper.name} ({orient_str}) · "
        f"Margen: {grid.margins.left:.0f} mm · "
        f"Solapamiento: {overlap_mm:.0f} mm"
    )
    draw.text((margin_px, y), meta_text, font=small_font, fill=muted)
    y += _px(6.5, dpi)

    # Línea divisoria
    draw.line([(margin_px, y), (margin_px + content_w, y)], fill=border_color, width=max(1, _px(0.3, dpi)))
    y += _px(6.0, dpi)

    # 2. Espacio disponible para el diagrama y las instrucciones
    # Reservamos la parte inferior para instrucciones (~55 mm) y regla (~20 mm)
    bottom_reserved_mm = 68.0
    diagram_max_h_px = page_h_px - y - _px(bottom_reserved_mm, dpi)
    diagram_max_w_px = content_w

    if diagram_max_h_px > _px(40.0, dpi) and diagram_max_w_px > _px(40.0, dpi):
        aspect = grid.poster_width_mm / grid.poster_height_mm
        diag_w = diagram_max_w_px
        diag_h = diag_w / aspect

        if diag_h > diagram_max_h_px:
            diag_h = diagram_max_h_px
            diag_w = diag_h * aspect

        diag_w_px = max(1, int(round(diag_w)))
        diag_h_px = max(1, int(round(diag_h)))
        diag_x = margin_px + (content_w - diag_w_px) // 2
        diag_y = y + int(round((diagram_max_h_px - diag_h_px) / 2))

        # Miniatura de la imagen de fondo con opacidad suave
        try:
            thumb = source.resize((diag_w_px, diag_h_px), Image.Resampling.LANCZOS)
            light_thumb = Image.blend(
                thumb.convert("RGB"),
                Image.new("RGB", (diag_w_px, diag_h_px), (255, 255, 255)),
                alpha=0.30,
            )
            page.paste(light_thumb, (diag_x, diag_y))
            thumb.close()
            light_thumb.close()
        except Exception:
            # Si falla la miniatura, se dibuja un recuadro limpio
            draw.rectangle(
                [(diag_x, diag_y), (diag_x + diag_w_px, diag_y + diag_h_px)],
                fill=box_bg,
                outline=border_color,
                width=1,
            )

        # Líneas de corte de la cuadrícula reales (idénticas a la vista previa de la web)
        white_w = max(2, _px(0.8, dpi))
        line_w = max(1, _px(0.35, dpi))

        # Líneas verticales entre columnas útiles
        for c in range(1, grid.pages_wide):
            vx = diag_x + int(round(diag_w_px * (c * grid.usable_width_mm) / grid.poster_width_mm))
            draw.line([(vx, diag_y), (vx, diag_y + diag_h_px)], fill=(255, 255, 255), width=white_w)
            draw.line([(vx, diag_y), (vx, diag_y + diag_h_px)], fill=accent, width=line_w)

        # Líneas horizontales entre filas útiles
        for r in range(1, grid.pages_high):
            hy = diag_y + int(round(diag_h_px * (r * grid.usable_height_mm) / grid.poster_height_mm))
            draw.line([(diag_x, hy), (diag_x + diag_w_px, hy)], fill=(255, 255, 255), width=white_w)
            draw.line([(diag_x, hy), (diag_x + diag_w_px, hy)], fill=accent, width=line_w)

        # Marco exterior del póster
        draw.rectangle(
            [(diag_x, diag_y), (diag_x + diag_w_px, diag_y + diag_h_px)],
            outline=ink,
            width=max(1, _px(0.4, dpi)),
        )

        # Etiquetas de cada hoja en sus coordenadas reales
        badge_font = _font(_px(max(2.2, min(4.5, 30.0 / max(grid.pages_wide, grid.pages_high))), dpi))
        badge_subfont = _font(_px(max(1.8, min(3.0, 22.0 / max(grid.pages_wide, grid.pages_high))), dpi))

        for r in range(grid.pages_high):
            for c in range(grid.pages_wide):
                idx = r * grid.pages_wide + c + 1

                # Coordenadas proporcionales reales en mm
                x0_mm = c * grid.usable_width_mm
                x1_mm = min((c + 1) * grid.usable_width_mm, grid.poster_width_mm)
                y0_mm = r * grid.usable_height_mm
                y1_mm = min((r + 1) * grid.usable_height_mm, grid.poster_height_mm)

                cx0 = diag_x + int(round(diag_w_px * x0_mm / grid.poster_width_mm))
                cx1 = diag_x + int(round(diag_w_px * x1_mm / grid.poster_width_mm))
                cy0 = diag_y + int(round(diag_h_px * y0_mm / grid.poster_height_mm))
                cy1 = diag_y + int(round(diag_h_px * y1_mm / grid.poster_height_mm))

                cw = cx1 - cx0
                ch = cy1 - cy0

                badge_w = min(cw * 0.82, _px(26.0, dpi))
                badge_h = min(ch * 0.72, _px(13.0, dpi))

                if badge_w >= _px(7.0, dpi) and badge_h >= _px(4.0, dpi):
                    bx0 = cx0 + (cw - badge_w) / 2
                    by0 = cy0 + (ch - badge_h) / 2
                    draw.rounded_rectangle(
                        [(bx0, by0), (bx0 + badge_w, by0 + badge_h)],
                        radius=_px(1.5, dpi),
                        fill=(255, 255, 255),
                        outline=ink,
                        width=max(1, _px(0.25, dpi)),
                    )
                    if badge_h >= _px(8.5, dpi):
                        draw.text(
                            (bx0 + badge_w / 2, by0 + badge_h * 0.33),
                            f"Hoja {idx}",
                            font=badge_font,
                            fill=ink,
                            anchor="mm",
                        )
                        draw.text(
                            (bx0 + badge_w / 2, by0 + badge_h * 0.72),
                            f"F{r + 1} · C{c + 1}",
                            font=badge_subfont,
                            fill=muted,
                            anchor="mm",
                        )
                    else:
                        draw.text(
                            (bx0 + badge_w / 2, by0 + badge_h / 2),
                            f"H.{idx}",
                            font=badge_font,
                            fill=ink,
                            anchor="mm",
                        )
                elif cw >= _px(5.0, dpi) and ch >= _px(3.5, dpi):
                    draw.text(
                        (cx0 + cw / 2, cy0 + ch / 2),
                        str(idx),
                        font=badge_subfont,
                        fill=ink,
                        anchor="mm",
                    )

        y += diagram_max_h_px + _px(4.0, dpi)
    else:
        y += _px(10.0, dpi)

    # 3. Instrucciones paso a paso
    draw.line([(margin_px, y), (margin_px + content_w, y)], fill=border_color, width=max(1, _px(0.3, dpi)))
    y += _px(4.5, dpi)

    draw.text((margin_px, y), "INSTRUCCIONES DE MONTAJE:", font=bold_small_font, fill=ink)
    y += _px(4.5, dpi)

    steps = [
        "1. Impresión: Imprime todas las hojas al 100 % (sin «ajustar a la página» ni escalar).",
        "2. Recorte: Corta los márgenes blancos sobrantes siguiendo las marcas de corte.",
        "3. Montaje: Une las hojas en orden de lectura: de izquierda a derecha (C1 -> Cn) y de arriba a abajo.",
        "4. Solapamiento: Si indicaste solapamiento, monta el borde de cada hoja sobre la pestaña de su vecina.",
        "5. Ajuste final: La última fila o columna puede tener papel blanco sobrante; recórtalo al montar.",
    ]
    step_font = _font(_px(2.6, dpi))
    for step in steps:
        draw.text((margin_px, y), step, font=step_font, fill=ink)
        y += _px(3.8, dpi)

    # 4. Regla de comprobación de escala (50 mm)
    ruler_y = page_h_px - _px(13.0, dpi)
    ruler_len_px = _px(50.0, dpi)
    draw.line([(margin_px, ruler_y), (margin_px + ruler_len_px, ruler_y)], fill=ink, width=max(1, _px(0.35, dpi)))

    for mm in range(0, 51, 5):
        tick_h = _px(3.0, dpi) if mm % 10 == 0 else _px(1.8, dpi)
        tx = margin_px + _px(mm, dpi)
        draw.line([(tx, ruler_y - tick_h), (tx, ruler_y)], fill=ink, width=max(1, _px(0.25, dpi)))
        if mm % 10 == 0:
            draw.text((tx, ruler_y + _px(1.5, dpi)), str(mm), font=small_font, fill=muted, anchor="ma")

    draw.text(
        (margin_px + ruler_len_px + _px(5.0, dpi), ruler_y - _px(1.0, dpi)),
        "<- Comprobación: debe medir exactamente 50 mm al imprimir al 100 %",
        font=small_font,
        fill=accent,
        anchor="lm",
    )

    return page
