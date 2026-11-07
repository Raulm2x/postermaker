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


@dataclass
class BatchPosterItem:
    index: int
    name: str
    result: PosterResult
    pdf_path: Path


@dataclass
class BatchPosterResult:
    items: list[BatchPosterItem]
    combined_pdf: Path | None = None
    separate_pdfs: list[Path] | None = None
    total_pages: int = 0


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


def generate_posters_batch(
    sources: list[str | Path | BinaryIO | tuple[str, str | Path | BinaryIO]],
    output_target: str | Path,
    *,
    separate: bool = False,
    separate_dir: str | Path | None = None,
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
    tiles_base_dir: str | Path | None = None,
    preview_path: str | Path | None = None,
) -> BatchPosterResult:
    """Procesa múltiples imágenes en lote.

    Por defecto (separate=False) genera un único PDF combinado que reúne todos
    los pósteres generados secuencialmente.
    Si separate=True, genera cada póster como un PDF independiente (o en un ZIP).
    """
    if not sources:
        raise ValueError("No se han proporcionado imágenes para procesar.")

    items: list[BatchPosterItem] = []
    all_page_paths: list[Path] = []
    separate_pdfs: list[Path] = []
    out_target = Path(output_target)
    is_zip = out_target.suffix.lower() == ".zip"

    with tempfile.TemporaryDirectory(prefix="postermaker-batch-") as tmp:
        tmp_dir = Path(tmp)

        if separate:
            if separate_dir:
                sep_target_dir = Path(separate_dir)
                sep_target_dir.mkdir(parents=True, exist_ok=True)
            elif is_zip:
                sep_target_dir = tmp_dir / "individual"
                sep_target_dir.mkdir(parents=True, exist_ok=True)
            elif out_target.suffix.lower() == ".pdf":
                sep_target_dir = out_target.parent
                sep_target_dir.mkdir(parents=True, exist_ok=True)
            else:
                sep_target_dir = out_target
                sep_target_dir.mkdir(parents=True, exist_ok=True)
        else:
            sep_target_dir = Path(separate_dir) if separate_dir else tmp_dir

        for idx, item in enumerate(sources, 1):
            if isinstance(item, tuple):
                name, src = item
            elif hasattr(item, "filename") and getattr(item, "filename", None):
                src = item
                name = Path(item.filename).stem
            elif hasattr(item, "name") and item.name:
                src = item
                name = Path(item.name).stem
            else:
                src = item
                name = Path(str(item)).stem if isinstance(item, (str, Path)) else f"imagen_{idx}"

            clean_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip() or f"img_{idx}"

            sub_tiles = Path(tiles_base_dir) / f"img_{idx:02d}_{clean_name}" if tiles_base_dir else tmp_dir / f"tiles_{idx:02d}"
            sub_tiles.mkdir(parents=True, exist_ok=True)

            if separate:
                individual_pdf = sep_target_dir / f"poster_{idx:02d}_{clean_name}.pdf"
            else:
                individual_pdf = sep_target_dir / f"poster_{idx:02d}_{clean_name}.pdf"

            item_preview = preview_path if idx == 1 else None

            res = generate_poster(
                src,
                individual_pdf,
                pages_wide=pages_wide,
                pages_high=pages_high,
                paper=paper,
                orientation=orientation,
                margins=margins,
                dpi=dpi,
                overlap_mm=overlap_mm,
                marks=marks,
                labels=labels,
                color_mode=color_mode,
                assembly_guide=assembly_guide,
                tiles_dir=sub_tiles,
                preview_path=item_preview,
            )
            items.append(BatchPosterItem(index=idx, name=clean_name, result=res, pdf_path=individual_pdf))
            all_page_paths.extend(res.page_paths)
            if separate:
                separate_pdfs.append(individual_pdf)

        combined_pdf: Path | None = None
        if not separate:
            # Por defecto: genera un único PDF combinado
            first_grid = items[0].result.grid
            all_same_size = all(
                (it.result.grid.page_width_mm, it.result.grid.page_height_mm)
                == (first_grid.page_width_mm, first_grid.page_height_mm)
                for it in items
            )
            combined_pdf = pages_to_pdf(
                all_page_paths,
                grid=first_grid if all_same_size else None,
                output_path=out_target,
                title=f"Pósteres combinados ({len(items)} imágenes)",
            )
        elif is_zip:
            import zipfile
            out_target.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out_target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for pdf_file in separate_pdfs:
                    zf.write(pdf_file, arcname=pdf_file.name)

        return BatchPosterResult(
            items=items,
            combined_pdf=combined_pdf,
            separate_pdfs=separate_pdfs,
            total_pages=len(all_page_paths),
        )
