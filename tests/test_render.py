from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from postermaker.grid import compute_grid
from postermaker.image import center_crop_to_aspect, open_image, prepare_source
from postermaker.paper import Margins
from postermaker.pdf import pages_to_pdf
from postermaker.render import RenderOptions, render_pages


def make_image(path: Path, width: int = 1200, height: int = 800) -> Path:
    image = Image.new("RGB", (width, height), (230, 90, 50))
    draw = ImageDraw.Draw(image)
    draw.rectangle((width // 2, height // 2, width, height), fill=(40, 110, 80))
    image.save(path)
    image.close()
    return path


def test_center_crop_keeps_requested_aspect() -> None:
    image = Image.new("RGB", (1200, 800))
    cropped = center_crop_to_aspect(image, 1.0)
    assert cropped.size == (800, 800)
    cropped.close()
    image.close()


def test_open_image_flattens_transparency(tmp_path: Path) -> None:
    path = tmp_path / "alpha.png"
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    image.save(path)
    image.close()

    opened = open_image(path)
    assert opened.mode == "RGB"
    assert opened.getpixel((0, 0)) == (255, 255, 255)
    opened.close()


def test_render_pages_and_pdf(tmp_path: Path) -> None:
    source_path = make_image(tmp_path / "source.jpg")
    grid = compute_grid(
        image_width=1200,
        image_height=800,
        pages_wide=2,
        paper="a4",
        orientation="portrait",
        margins=Margins.uniform(10),
    )
    assert grid.pages_high == 1

    image = open_image(source_path)
    prepared = prepare_source(image, grid)
    assert prepared.effective_dpi > 0

    result = render_pages(
        prepared.image,
        grid,
        tmp_path / "tiles",
        RenderOptions(dpi=300, overlap_mm=6, marks=True, labels=True),
    )

    assert result.total_pages == 2
    assert result.render_dpi == pytest.approx(prepared.effective_dpi, rel=1e-6)
    assert result.page_width_px == round(210 / 25.4 * result.render_dpi)
    assert result.page_height_px == round(297 / 25.4 * result.render_dpi)

    for page_path in result.page_paths:
        page = Image.open(page_path)
        assert page.size == (result.page_width_px, result.page_height_px)
        # La esquina superior izquierda está en el margen blanco.
        assert page.getpixel((2, 2)) == (255, 255, 255)
        # La última fila no llena la hoja: el pie queda en blanco.
        assert page.getpixel((page.width // 2, page.height - 5)) == (
            255,
            255,
            255,
        )
        page.close()

    pdf_path = pages_to_pdf(result.page_paths, grid, tmp_path / "poster.pdf")
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 2
    assert float(reader.pages[0].mediabox.width) == pytest.approx(
        210 / 25.4 * 72, rel=1e-5
    )
    assert float(reader.pages[0].mediabox.height) == pytest.approx(
        297 / 25.4 * 72, rel=1e-5
    )

    prepared.close()
    image.close()


def test_color_modes() -> None:
    from postermaker.image import apply_color_mode
    img = Image.new("RGB", (100, 100), (200, 50, 100))
    # Color mantiene el pixel
    color_img = apply_color_mode(img, "color")
    assert color_img.getpixel((0, 0)) == (200, 50, 100)

    # Grayscale convierte a R=G=B
    gray_img = apply_color_mode(img, "grayscale")
    r, g, b = gray_img.getpixel((0, 0))
    assert r == g == b

    # Monochrome convierte a blanco o negro puro
    mono_img = apply_color_mode(img, "monochrome")
    mr, mg, mb = mono_img.getpixel((0, 0))
    assert mr == mg == mb
    assert mr in (0, 255)


def test_assembly_guide_and_generation(tmp_path: Path) -> None:
    from postermaker.pipeline import generate_poster
    source_path = make_image(tmp_path / "source.jpg", 1000, 1000)

    result = generate_poster(
        source_path,
        tmp_path / "poster_with_guide.pdf",
        pages_wide=2,
        paper="a4",
        orientation="portrait",
        assembly_guide=True,
        tiles_dir=tmp_path / "tiles_with_guide",
    )
    assert result.grid.pages_wide == 2
    assert result.grid.pages_high == 2
    # 4 hojas de imagen + 1 hoja de guía = 5 hojas en total
    assert len(result.page_paths) == 5
    assert result.page_paths[0].name == "page_000_guide.jpg"

    reader = PdfReader(str(result.pdf_path))
    assert len(reader.pages) == 5


def test_assembly_guide_with_partial_row() -> None:
    from postermaker.guide import render_assembly_guide
    # Imagen 1200x800 con 2 hojas de ancho en A4 portrait:
    # La 2da fila será parcial
    grid = compute_grid(
        image_width=1200,
        image_height=800,
        pages_wide=2,
        paper="a4",
        orientation="portrait",
        margins=Margins.uniform(10),
    )
    img = Image.new("RGB", (600, 400), (200, 150, 100))
    guide = render_assembly_guide(img, grid, dpi=100.0)
    assert guide.size[0] > 0
    assert guide.size[1] > 0
    guide.close()
    img.close()
