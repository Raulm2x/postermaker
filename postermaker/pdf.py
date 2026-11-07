"""Unión de las hojas en un PDF con tamaño de página exacto."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import img2pdf

from .grid import Grid


def pages_to_pdf(
    page_paths: Iterable[str | Path],
    grid: Grid,
    output_path: str | Path,
    *,
    title: str = "Póster para imprimir",
) -> Path:
    """Crea un PDF multipágina a partir de las hojas JPEG."""

    paths = [Path(path) for path in page_paths]
    if not paths:
        raise ValueError("No hay páginas para crear el PDF.")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"No se encuentran las páginas: {missing[:3]}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    page_size_pt = (
        img2pdf.mm_to_pt(grid.page_width_mm),
        img2pdf.mm_to_pt(grid.page_height_mm),
    )
    layout = img2pdf.get_layout_fun(page_size_pt)
    data = img2pdf.convert(
        [str(path) for path in paths],
        layout_fun=layout,
        title=title,
    )
    output.write_bytes(data)
    return output
