"""Extracción y validación de parámetros de peticiones web."""

from __future__ import annotations

from typing import Any
from flask import Response, jsonify

from ..paper import PAPERS, Margins


def _json_error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify(error=message), status


def _parse_int(form: Any, key: str, default: int, minimum: int, maximum: int, label: str) -> int:
    raw = form.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} no es válido.") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} debe estar entre {minimum} y {maximum}.")
    return value


def _parse_float(
    form: Any, key: str, default: float, minimum: float, maximum: float, label: str
) -> float:
    raw = form.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} no es válido.") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} debe estar entre {minimum} y {maximum}.")
    return value


def _parse_bool(form: Any, key: str) -> bool:
    return str(form.get(key, "false")).lower() in {"1", "true", "on", "yes"}


def _parse_options(form: Any) -> dict[str, Any]:
    dim_mode = str(form.get("dimension_mode", "wide")).strip().lower()
    pages_wide = None
    pages_high = None
    if dim_mode == "high":
        pages_high = _parse_int(form, "pages_high", 3, 1, 10, "El alto en páginas")
    else:
        if "pages_wide" in form:
            pages_wide = _parse_int(form, "pages_wide", 3, 1, 10, "El ancho en páginas")
        elif "pages_high" in form:
            pages_high = _parse_int(form, "pages_high", 3, 1, 10, "El alto en páginas")
        else:
            pages_wide = 3

    paper = str(form.get("paper", "letter")).strip().lower()
    if paper not in PAPERS:
        raise ValueError("El tamaño de papel no es válido.")
    orientation = str(form.get("orientation", "portrait")).strip().lower()
    if orientation not in ("portrait", "landscape"):
        raise ValueError("La orientación no es válida.")
    margin = _parse_float(form, "margin", 3.0, 0.0, 30.0, "El margen")
    overlap = _parse_float(form, "overlap", 0.0, 0.0, 20.0, "El solapamiento")
    dpi = _parse_int(form, "dpi", 300, 72, 600, "La resolución")
    marks = _parse_bool(form, "marks")
    labels = _parse_bool(form, "labels")
    if "skip_guide" in form or "skip-guide" in form:
        guide = not (_parse_bool(form, "skip_guide") or _parse_bool(form, "skip-guide"))
    elif "guide" in form or "assembly_guide" in form:
        guide = _parse_bool(form, "guide") or _parse_bool(form, "assembly_guide")
    else:
        guide = False
    color = str(form.get("color", form.get("color_mode", "color"))).strip().lower()
    if color not in ("color", "grayscale", "monochrome"):
        color = "color"
    separate = _parse_bool(form, "separate") or _parse_bool(form, "separate_posters")

    return {
        "pages_wide": pages_wide,
        "pages_high": pages_high,
        "paper": paper,
        "orientation": orientation,
        "margins": Margins.uniform(margin),
        "overlap_mm": overlap,
        "dpi": dpi,
        "marks": marks,
        "labels": labels,
        "assembly_guide": guide,
        "color_mode": color,
        "separate": separate,
    }
