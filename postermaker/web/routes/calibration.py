"""Rutas para generar hojas de calibración de impresión."""

from __future__ import annotations

import io
from flask import Flask, request, send_file

from ...calibration import calibration_pdf
from ...paper import PAPERS
from ..options import _json_error


def register_calibration_routes(app: Flask) -> None:
    @app.get("/api/calibration")
    def calibration():
        paper = str(request.args.get("paper", "letter")).strip().lower()
        if paper not in PAPERS:
            return _json_error("El tamaño de papel no es válido.")
        data = calibration_pdf(paper)
        name = f"calibracion-{paper}.pdf"
        return send_file(
            io.BytesIO(data),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=name,
        )
