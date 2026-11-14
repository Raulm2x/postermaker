"""Rutas para la comprobación y aplicación de actualizaciones."""

from __future__ import annotations

import sys
from flask import Flask, jsonify

from ...updater import updater as default_updater
from ..config import is_local_mode
from ..options import _json_error


def _is_local() -> bool:
    """Permite acceder dinámicamente a is_local_mode si se monkeypatchea en postermaker.web."""
    web_mod = sys.modules.get("postermaker.web")
    if web_mod and hasattr(web_mod, "is_local_mode"):
        return bool(getattr(web_mod, "is_local_mode")())
    return is_local_mode()


def _get_updater():
    """Permite acceder dinámicamente al updater si es monkeypatcheado en postermaker.web.updater."""
    web_mod = sys.modules.get("postermaker.web")
    if web_mod and hasattr(web_mod, "updater"):
        return getattr(web_mod, "updater")
    return default_updater


def register_updater_routes(app: Flask) -> None:
    @app.get("/api/update/status")
    def update_status():
        if not _is_local():
            return jsonify(
                status="disabled",
                has_update=False,
                enabled=False,
                message="Las actualizaciones automáticas están deshabilitadas en entorno cloud.",
            )
        return jsonify(_get_updater().get_state())

    @app.post("/api/update/check")
    def update_check():
        if not _is_local():
            return jsonify(
                ok=False,
                status="disabled",
                has_update=False,
                enabled=False,
                message="Las actualizaciones se gestionan automáticamente a través de los commits en Render.",
            )
        result = _get_updater().check_updates()
        return jsonify(result)

    @app.post("/api/update/apply")
    def update_apply():
        if not _is_local():
            return _json_error("La aplicación de actualizaciones no está permitida en entorno cloud.", 403)
        result = _get_updater().apply_update()
        return jsonify(result)
