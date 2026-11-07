from __future__ import annotations

import math

import pytest

from postermaker.grid import compute_grid
from postermaker.paper import Margins, get_page_size_mm, get_paper


def test_page_sizes_and_orientation() -> None:
    a4 = get_paper("a4")
    assert get_page_size_mm(a4, "portrait") == (210.0, 297.0)
    assert get_page_size_mm(a4, "landscape") == (297.0, 210.0)

    letter = get_paper("letter")
    assert get_page_size_mm(letter, "portrait") == (215.9, 279.4)
    assert letter.name == "Carta"

    carta = get_paper("carta")
    assert carta.key == "letter"
    assert carta.name == "Carta"

    oficio = get_paper("oficio")
    assert oficio.key == "legal"
    assert oficio.name == "Oficio"

    tabloide = get_paper("tabloide")
    assert tabloide.key == "tabloid"
    assert tabloide.name == "Tabloide"


def test_invalid_paper_and_orientation() -> None:
    with pytest.raises(ValueError):
        get_paper("b4")
    with pytest.raises(ValueError):
        get_page_size_mm(get_paper("a4"), "diagonal")


def test_grid_uses_usable_area() -> None:
    grid = compute_grid(
        image_width=3000,
        image_height=2000,
        pages_wide=3,
        paper="a4",
        orientation="portrait",
        margins=Margins.uniform(10),
    )

    assert grid.usable_width_mm == 190.0
    assert grid.usable_height_mm == 277.0
    assert grid.poster_width_mm == 570.0
    # 570 / 1.5 = 380 mm de alto; 380 / 277 = 1.37 -> 2 filas.
    assert grid.pages_high == 2
    assert math.isclose(grid.poster_height_mm, 380.0)
    assert grid.total_pages == 6

    # La segunda fila solo ocupa 103 mm de la hoja.
    assert math.isclose(grid.last_row_height_mm, 103.0)
    assert grid.image_box_in_page_mm(0)[3] == pytest.approx(287.0)
    assert grid.image_box_in_page_mm(1)[3] == pytest.approx(113.0)


def test_grid_keeps_the_whole_image() -> None:
    grid = compute_grid(
        image_width=1000,
        image_height=1000,
        pages_wide=3,
        paper="a4",
        orientation="portrait",
        margins=Margins.uniform(0),
    )
    # Póster de 630 mm de ancho, imagen cuadrada -> 630 mm de alto.
    # 630 / 297 = 2.12 -> 3 filas, la última de 36 mm.
    assert grid.pages_high == 3
    assert math.isclose(grid.poster_height_mm, 630.0)
    assert math.isclose(grid.last_row_height_mm, 36.0)
    assert grid.total_pages == 9


def test_overlap_is_shared_between_neighbours() -> None:
    grid = compute_grid(
        image_width=1000,
        image_height=1000,
        pages_wide=3,
        paper="a4",
        orientation="portrait",
        margins=Margins.uniform(10),
    )
    # póster 570 x 630 mm (3 filas; la última de 36 mm)
    assert grid.pages_high == 3

    first = grid.tile_box_mm(0, 0, overlap_mm=10)
    second = grid.tile_box_mm(0, 1, overlap_mm=10)

    # La primera se amplía 5 mm a la derecha; la segunda 5 mm a la izquierda.
    assert first == (0.0, 0.0, 195.0, 282.0)
    assert second == (185.0, 0.0, 385.0, 282.0)
    assert first[2] - second[0] == pytest.approx(10.0)

    # El borde útil de la hoja (190 mm) debe caer en el margen izquierdo,
    # aunque la pieza empiece 5 mm antes por el solapamiento.
    paste_x, paste_y = grid.paste_offset_mm(0, 1, overlap_mm=10)
    assert paste_x + (190.0 - second[0]) == pytest.approx(grid.margins.left)
    assert paste_y + (0.0 - second[1]) == pytest.approx(grid.margins.top)


def test_overlap_is_clamped_to_a_short_last_row() -> None:
    grid = compute_grid(
        image_width=1020,
        image_height=1000,
        pages_wide=3,
        paper="a4",
        orientation="portrait",
        margins=Margins.uniform(10),
    )
    assert grid.pages_high == 3
    assert grid.last_row_height_mm < 10

    _, _, _, bottom = grid.tile_box_mm(1, 0, overlap_mm=20)
    assert bottom == pytest.approx(grid.poster_height_mm)


def test_margins_too_large() -> None:
    with pytest.raises(ValueError):
        compute_grid(
            image_width=1000,
            image_height=1000,
            pages_wide=2,
            paper="a4",
            orientation="portrait",
            margins=Margins.uniform(150),
        )


def test_too_many_pages() -> None:
    with pytest.raises(ValueError):
        compute_grid(
            image_width=100,
            image_height=4000,
            pages_wide=10,
            paper="a4",
            orientation="portrait",
            margins=Margins.uniform(0),
        )


def test_new_paper_formats() -> None:
    for key in ("a3", "a4", "a5", "letter", "legal", "tabloid"):
        p = get_paper(key)
        assert p.width_mm > 0
        assert p.height_mm > 0
        w, h = get_page_size_mm(p, "portrait")
        assert w == p.width_mm
        assert h == p.height_mm


def test_grid_by_pages_high() -> None:
    # Imagen 2000 x 1000 (aspecto 2:1 ancho:alto)
    # 2 hojas A4 portrait de alto: alto útil = 2 * (297 - 20) = 554 mm
    # ancho ideal = 554 * 2 = 1108 mm
    # ancho útil A4 = 210 - 20 = 190 mm
    # 1108 / 190 = 5.83 -> 6 hojas de ancho
    grid = compute_grid(
        image_width=2000,
        image_height=1000,
        pages_high=2,
        paper="a4",
        orientation="portrait",
        margins=Margins.uniform(10),
    )
    assert grid.pages_high == 2
    assert grid.pages_wide == 6
    assert math.isclose(grid.poster_height_mm, 554.0)
    assert math.isclose(grid.poster_width_mm, 1108.0)
    assert grid.total_pages == 12
    # Comprobar última columna parcial
    assert math.isclose(grid.last_col_width_mm, 1108.0 - 5 * 190.0)
    box_last_col = grid.image_box_in_page_mm(0, 5)
    assert box_last_col[2] == pytest.approx(10.0 + grid.last_col_width_mm)


def test_grid_requires_dimension() -> None:
    with pytest.raises(ValueError, match="pages_wide o pages_high"):
        compute_grid(
            image_width=1000,
            image_height=1000,
            paper="a4",
            orientation="portrait",
            margins=Margins.uniform(10),
        )
