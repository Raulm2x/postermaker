"""Cálculo de la cuadrícula de hojas del póster."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .paper import (
    MM_PER_INCH,
    Margins,
    PaperSize,
    get_page_size_mm,
    get_paper,
)

MAX_PAGES_WIDE = 10
MAX_TOTAL_PAGES = 150
MIN_USABLE_MM = 10.0


@dataclass(frozen=True)
class Grid:
    """Distribución de un póster en hojas.

    El póster visible (sin bordes) mide ``poster_width_mm`` por
    ``poster_height_mm``. Cada hoja tiene el tamaño completo del papel y el
    trozo de imagen se coloca dentro, dejando los márgenes indicados.
    """

    pages_wide: int
    pages_high: int
    paper: PaperSize
    orientation: str
    margins: Margins
    page_width_mm: float
    page_height_mm: float
    usable_width_mm: float
    usable_height_mm: float
    poster_height_mm: float
    poster_width_mm: float = 0.0

    def __post_init__(self) -> None:
        if not self.poster_width_mm:
            object.__setattr__(
                self, "poster_width_mm", self.pages_wide * self.usable_width_mm
            )

    @property
    def total_pages(self) -> int:
        return self.pages_wide * self.pages_high

    @property
    def last_row_height_mm(self) -> float:
        """Alto de imagen de la última fila (puede ser menor que una hoja)."""

        return self.poster_height_mm - (self.pages_high - 1) * self.usable_height_mm

    @property
    def last_col_width_mm(self) -> float:
        """Ancho de imagen de la última columna (puede ser menor si se fijó pages_high)."""

        return self.poster_width_mm - (self.pages_wide - 1) * self.usable_width_mm

    def image_box_in_page_mm(
        self, row: int, col: int = 0
    ) -> tuple[float, float, float, float]:
        """Rectángulo de imagen dentro de una hoja, sin solapamiento."""

        if not 0 <= row < self.pages_high:
            raise IndexError(f"Fila fuera de rango: {row}")
        if not 0 <= col < self.pages_wide:
            raise IndexError(f"Columna fuera de rango: {col}")

        width = (
            self.usable_width_mm
            if col < self.pages_wide - 1
            else self.last_col_width_mm
        )
        height = (
            self.usable_height_mm
            if row < self.pages_high - 1
            else self.last_row_height_mm
        )
        return (
            self.margins.left,
            self.margins.top,
            self.margins.left + width,
            self.margins.top + height,
        )

    @property
    def poster_width_cm(self) -> float:
        return self.poster_width_mm / 10.0

    @property
    def poster_height_cm(self) -> float:
        return self.poster_height_mm / 10.0

    @property
    def poster_width_in(self) -> float:
        return self.poster_width_mm / MM_PER_INCH

    @property
    def poster_height_in(self) -> float:
        return self.poster_height_mm / MM_PER_INCH

    @property
    def page_label(self) -> str:
        return f"{self.paper.name} {'vertical' if self.orientation == 'portrait' else 'horizontal'}"

    def tile_box_mm(
        self, row: int, col: int, overlap_mm: float = 0.0
    ) -> tuple[float, float, float, float]:
        """Rectángulo de imagen (x0, y0, x1, y1) que va en una hoja.

        ``overlap_mm`` es la franja total que comparten dos hojas vecinas;
        se reparte por igual entre los dos lados del corte. En los bordes
        exteriores del póster no se amplía.
        """

        if not 0 <= row < self.pages_high:
            raise IndexError(f"Fila fuera de rango: {row}")
        if not 0 <= col < self.pages_wide:
            raise IndexError(f"Columna fuera de rango: {col}")
        if overlap_mm < 0:
            raise ValueError("El solapamiento no puede ser negativo.")

        uw = self.usable_width_mm
        uh = self.usable_height_mm
        # La mitad del solapamiento por cada lado del corte.
        overlap = min(float(overlap_mm) / 2.0, uw / 2.0, uh / 2.0)

        x0 = col * uw
        x1 = min(x0 + uw, self.poster_width_mm)
        y0 = row * uh
        y1 = min(y0 + uh, self.poster_height_mm)

        if overlap:
            if col > 0:
                x0 -= overlap
            if col < self.pages_wide - 1:
                x1 += overlap
            if row > 0:
                y0 -= overlap
            if row < self.pages_high - 1:
                y1 += overlap

        # No salir nunca del área del póster: en la última fila el
        # solapamiento puede ser mayor que el alto disponible.
        x0 = max(0.0, x0)
        y0 = max(0.0, y0)
        x1 = min(self.poster_width_mm, x1)
        y1 = min(self.poster_height_mm, y1)
        return (x0, y0, x1, y1)

    def paste_offset_mm(
        self, row: int, col: int, overlap_mm: float = 0.0
    ) -> tuple[float, float]:
        """Dónde empieza el trozo de imagen dentro de la hoja, en mm.

        Se calcula para que la coordenada del póster que coincide con el
        borde útil de la hoja caiga exactamente en el margen, aunque el
        recorte se haya ampliado por el solapamiento.
        """

        x0, y0, _, _ = self.tile_box_mm(row, col, overlap_mm)
        return (
            self.margins.left + (x0 - col * self.usable_width_mm),
            self.margins.top + (y0 - row * self.usable_height_mm),
        )


def compute_grid(
    *,
    image_width: int,
    image_height: int,
    pages_wide: int | None = None,
    pages_high: int | None = None,
    paper: PaperSize | str,
    orientation: str,
    margins: Margins,
) -> Grid:
    """Calcula cuántas hojas hacen falta para conservar el aspecto.

    Puede especificarse ``pages_wide`` (lo habitual) o bien ``pages_high``.
    La dimensión restante se deduce continuamente del aspecto de la imagen y se
    redondea hacia arriba al número entero de hojas necesario. La última fila o
    columna puede quedar parcialmente en blanco; así la imagen no se recorta
    ni se deforma.
    """

    if image_width <= 0 or image_height <= 0:
        raise ValueError("La imagen no tiene dimensiones válidas.")
    if pages_wide is None and pages_high is None:
        raise ValueError("Debes especificar pages_wide o pages_high.")
    if pages_wide is not None and pages_high is not None:
        # Si ambos se pasan, pages_wide tiene prioridad
        pages_high = None

    if pages_wide is not None:
        if not isinstance(pages_wide, int) or pages_wide < 1:
            raise ValueError("El ancho en páginas debe ser un entero mayor que cero.")
        if pages_wide > MAX_PAGES_WIDE:
            raise ValueError(
                f"El ancho máximo es {MAX_PAGES_WIDE} páginas."
            )
    if pages_high is not None:
        if not isinstance(pages_high, int) or pages_high < 1:
            raise ValueError("El alto en páginas debe ser un entero mayor que cero.")
        if pages_high > MAX_PAGES_WIDE:
            raise ValueError(
                f"El alto máximo es {MAX_PAGES_WIDE} páginas."
            )

    if not isinstance(margins, Margins):
        raise ValueError("Los márgenes deben ser un objeto Margins.")

    paper_size = get_paper(paper) if isinstance(paper, str) else paper
    page_w, page_h = get_page_size_mm(paper_size, orientation)

    usable_w = page_w - margins.horizontal
    usable_h = page_h - margins.vertical
    if usable_w < MIN_USABLE_MM or usable_h < MIN_USABLE_MM:
        raise ValueError(
            "Los márgenes son demasiado grandes para este tamaño de papel."
        )

    image_aspect = image_width / image_height

    if pages_wide is not None:
        poster_width = pages_wide * usable_w
        ideal_height = poster_width / image_aspect
        computed_pages_high = max(1, math.ceil(ideal_height / usable_h - 1e-9))
        computed_pages_wide = pages_wide
        poster_height = ideal_height
    else:
        assert pages_high is not None
        poster_height = pages_high * usable_h
        ideal_width = poster_height * image_aspect
        computed_pages_wide = max(1, math.ceil(ideal_width / usable_w - 1e-9))
        computed_pages_high = pages_high
        poster_width = ideal_width

    total = computed_pages_wide * computed_pages_high
    if total > MAX_TOTAL_PAGES:
        raise ValueError(
            f"El póster saldría con {total} hojas; el máximo es "
            f"{MAX_TOTAL_PAGES}. Reduce el tamaño o usa otra orientación."
        )

    return Grid(
        pages_wide=computed_pages_wide,
        pages_high=computed_pages_high,
        paper=paper_size,
        orientation=orientation.strip().lower(),
        margins=margins,
        page_width_mm=page_w,
        page_height_mm=page_h,
        usable_width_mm=usable_w,
        usable_height_mm=usable_h,
        poster_height_mm=poster_height,
        poster_width_mm=poster_width,
    )
