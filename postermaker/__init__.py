"""PosterMaker: Pósteres imprimibles divididos en varias hojas."""

from .grid import Grid, compute_grid
from .paper import Margins, PaperSize, get_page_size_mm, get_paper

__all__ = [
    "Grid",
    "Margins",
    "PaperSize",
    "compute_grid",
    "get_page_size_mm",
    "get_paper",
]

__version__ = "0.2.0"
