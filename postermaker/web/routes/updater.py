"""Rutas para la comprobación y aplicación de actualizaciones."""

from __future__ import annotations

import sys
from flask import Flask, jsonify

from ...updater import updater as default_updater


def _get_updater():
    """Permite acceder dinámicamente al updater si es monkeypatcheado en postermaker.web.updater."""
    web_mod = sys.modules.get("postermaker.web")
    if web_mod and hasattr(web_mod, "updater"):
        return getattr(web_mod, "updater")
    return default_updater


def register_updater_routes(app: Flask) -> None:
    @app.get("/api/update/status")
    def update_status():
        return jsonify(_get_updater().get_state())

    @app.post("/api/update/check")
    def update_check():
        result = _get_updater().check_updates()
        return jsonify(result)

    @app.post("/api/update/apply")
    def update_apply():
        result = _get_updater().apply_update()
        return jsonify(result)
