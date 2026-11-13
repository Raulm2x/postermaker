"""Inicialización de la aplicación Flask y registro de rutas."""

from __future__ import annotations

from flask import Flask

from ..config import MAX_UPLOAD_BYTES, STATIC_DIR
from .calibration import register_calibration_routes
from .generate import register_generate_routes
from .system import register_system_routes
from .updater import register_updater_routes


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    register_system_routes(app)
    register_calibration_routes(app)
    register_updater_routes(app)
    register_generate_routes(app)

    return app


app = create_app()
