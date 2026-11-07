"""Tamaños de papel, orientaciones y márgenes."""

from __future__ import annotations

import math
from dataclasses import dataclass

MM_PER_INCH = 25.4
PT_PER_INCH = 72.0

ORIENTATIONS = ("portrait", "landscape")


@dataclass(frozen=True)
class PaperSize:
    key: str
    name: str
    width_mm: float
    height_mm: float

    @property
    def aspect_ratio(self) -> float:
        """Alto / ancho en orientación vertical."""
        return self.height_mm / self.width_mm


CANONICAL_PAPERS: dict[str, PaperSize] = {
    "letter": PaperSize(
        key="letter", name="Carta", width_mm=215.9, height_mm=279.4
    ),
    "a4": PaperSize(key="a4", name="A4", width_mm=210.0, height_mm=297.0),
    "a3": PaperSize(key="a3", name="A3", width_mm=297.0, height_mm=420.0),
    "a5": PaperSize(key="a5", name="A5", width_mm=148.0, height_mm=210.0),
    "legal": PaperSize(
        key="legal", name="Oficio", width_mm=215.9, height_mm=355.6
    ),
    "tabloid": PaperSize(
        key="tabloid", name="Tabloide", width_mm=279.4, height_mm=431.8
    ),
}

PAPER_ALIASES: dict[str, str] = {
    "carta": "letter",
    "oficio": "legal",
    "tabloide": "tabloid",
    "doble-carta": "tabloid",
    "doble_carta": "tabloid",
    "doblecarta": "tabloid",
}

PAPERS: dict[str, PaperSize] = {
    **CANONICAL_PAPERS,
    "carta": CANONICAL_PAPERS["letter"],
    "oficio": CANONICAL_PAPERS["legal"],
    "tabloide": CANONICAL_PAPERS["tabloid"],
}


def get_paper(key: str) -> PaperSize:
    """Devuelve el papel indicado por su clave o alias en español (a4, letter, carta, oficio)."""

    normalized = key.strip().lower()
    canonical_key = PAPER_ALIASES.get(normalized, normalized)
    try:
        return CANONICAL_PAPERS[canonical_key]
    except KeyError:
        disponibles = ", ".join(sorted(set(list(CANONICAL_PAPERS) + list(PAPER_ALIASES))))
        raise ValueError(
            f"Papel desconocido: {key!r}. Opciones disponibles: {disponibles}."
        ) from None


def get_page_size_mm(paper: PaperSize, orientation: str) -> tuple[float, float]:
    """Ancho y alto de una hoja en milímetros, ya orientada."""

    orientation = orientation.strip().lower()
    if orientation == "portrait":
        return paper.width_mm, paper.height_mm
    if orientation == "landscape":
        return paper.height_mm, paper.width_mm
    raise ValueError(
        f"Orientación desconocida: {orientation!r}. "
        "Opciones: portrait, landscape."
    )


@dataclass(frozen=True)
class Margins:
    """Margen blanco por lado, en milímetros.

    Representa el borde no imprimible de la impresora (o un borde blanco
    deliberado). Se recorta antes de unir las hojas.
    """

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    def __post_init__(self) -> None:
        for nombre, valor in (
            ("top", self.top),
            ("right", self.right),
            ("bottom", self.bottom),
            ("left", self.left),
        ):
            if not isinstance(valor, (int, float)) or not math.isfinite(valor):
                raise ValueError(f"El margen {nombre} debe ser un número finito.")
            if valor < 0:
                raise ValueError(f"El margen {nombre} no puede ser negativo.")

    @classmethod
    def uniform(cls, mm: float) -> "Margins":
        """El mismo margen en los cuatro lados."""

        return cls(top=mm, right=mm, bottom=mm, left=mm)

    @property
    def horizontal(self) -> float:
        return self.left + self.right

    @property
    def vertical(self) -> float:
        return self.top + self.bottom

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.top, self.right, self.bottom, self.left)
