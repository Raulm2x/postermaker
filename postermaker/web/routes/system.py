"""Rutas del sistema, ciclo de vida, salud y manejadores de error HTTP."""

from __future__ import annotations

import threading
import time
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from ..config import STATIC_DIR
from ..inactivity import inactivity_manager
from ..options import _json_error


def register_system_routes(app: Flask) -> None:
    @app.before_request
    def _track_request_activity():
        inactivity_manager.touch()

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/health")
    def health():
        return jsonify(ok=True)

    @app.post("/api/heartbeat")
    def heartbeat():
        inactivity_manager.heartbeat()
        return jsonify(ok=True)

    @app.post("/api/tab-closed")
    def tab_closed():
        inactivity_manager.tab_closed()
        return jsonify(ok=True)

    @app.post("/api/shutdown")
    def api_shutdown():
        def _do_shutdown():
            time.sleep(0.3)
            inactivity_manager.shutdown(reason="Solicitud manual desde la interfaz")

        threading.Thread(target=_do_shutdown, daemon=True).start()
        return jsonify(ok=True, message="Servidor de PosterMaker cerrado correctamente.")

    @app.errorhandler(413)
    def too_large(_error):
        return _json_error("La imagen supera el límite de 25 MB.", 413)

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        if request.path.startswith("/api/"):
            return _json_error(error.description or error.name, error.code or 500)
        return error
