"""Flujo completo: imagen de entrada -> PDF multipágina."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .grid import Grid, compute_grid
from .image import PreparedSource, open_image, prepare_source
from .paper import Margins
from .pdf import pages_to_pdf
from .render import RenderOptions, render_pages, render_preview


@dataclass
class PosterResult:
    grid: Grid
    pdf_path: Path
    effective_dpi: float
    render_dpi: float
    page_paths: list[Path]
    preview_path: Path | None = None


def generate_poster(
    source: str | Path | BinaryIO,
    output_pdf: str | Path,
    *,
    pages_wide: int | None = 3,
    pages_high: int | None = None,
    paper: str = "letter",
    orientation: str = "portrait",
    margins: Margins | None = None,
    dpi: int = 300,
    overlap_mm: float = 0.0,
    marks: bool = False,
    labels: bool = False,
    color_mode: str = "color",
    assembly_guide: bool = False,
    tiles_dir: str | Path | None = None,
    preview_path: str | Path | None = None,
) -> PosterResult:
    """Genera el póster completo y devuelve los datos del resultado."""

    margins = margins or Margins.uniform(3.0)
    options = RenderOptions(
        dpi=dpi,
        overlap_mm=overlap_mm,
        marks=marks,
        labels=labels,
        assembly_guide=assembly_guide,
    )

    image = open_image(source)
    prepared: PreparedSource | None = None

    try:
        grid = compute_grid(
            image_width=image.width,
            image_height=image.height,
            pages_wide=pages_wide,
            pages_high=pages_high,
            paper=paper,
            orientation=orientation,
            margins=margins,
        )
        prepared = prepare_source(image, grid, color_mode=color_mode)

        with tempfile.TemporaryDirectory(prefix="postermaker-") as tmp:
            tile_output = Path(tiles_dir) if tiles_dir else Path(tmp) / "tiles"
            render = render_pages(prepared.image, grid, tile_output, options)
            pdf_path = pages_to_pdf(
                render.page_paths,
                grid,
                output_pdf,
                title=f"Póster {grid.pages_wide}×{grid.pages_high} · {grid.paper.name}",
            )

            preview = None
            if preview_path:
                preview = render_preview(prepared.image, grid, preview_path)

            # Si las hojas se han guardado en una carpeta temporal, se
            # eliminan al salir del contexto; si el usuario pidió conservarlas,
            # se quedan en tiles_dir.
            return PosterResult(
                grid=grid,
                pdf_path=pdf_path,
                effective_dpi=prepared.effective_dpi,
                render_dpi=render.render_dpi,
                page_paths=render.page_paths if tiles_dir else [],
                preview_path=preview,
            )
    finally:
        if prepared is not None:
            prepared.close()
        if prepared is None or prepared.image is not image:
            image.close()
