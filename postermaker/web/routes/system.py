"""Rutas del sistema, ciclo de vida, salud y manejadores de error HTTP."""

from __future__ import annotations

import sys
import threading
import time
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from ... import __version__
from ..config import STATIC_DIR, get_app_env, is_local_mode
from ..inactivity import inactivity_manager
from ..options import _json_error


def _is_local() -> bool:
    """Permite acceder dinámicamente a is_local_mode si se monkeypatchea en postermaker.web."""
    web_mod = sys.modules.get("postermaker.web")
    if web_mod and hasattr(web_mod, "is_local_mode"):
        return bool(getattr(web_mod, "is_local_mode")())
    return is_local_mode()


def _app_env() -> str:
    """Permite acceder dinámicamente a get_app_env si se monkeypatchea en postermaker.web."""
    web_mod = sys.modules.get("postermaker.web")
    if web_mod and hasattr(web_mod, "get_app_env"):
        return str(getattr(web_mod, "get_app_env")())
    return get_app_env()


def register_system_routes(app: Flask) -> None:
    @app.before_request
    def _track_request_activity():
        if _is_local():
            inactivity_manager.touch()

    @app.get("/")
    def index():
        if _is_local():
            return send_from_directory(STATIC_DIR, "index.html")

        # En modo nube, inyectamos data-env="cloud" directamente en el body del HTML
        # para que el CSS oculte los botones inmediatamente sin parpadeo.
        index_file = STATIC_DIR / "index.html"
        html = index_file.read_text(encoding="utf-8")
        html = html.replace("<body", '<body data-env="cloud"', 1)
        return app.response_class(html, mimetype="text/html")

    @app.get("/api/config")
    def api_config():
        local = _is_local()
        return jsonify(
            is_local=local,
            env=_app_env(),
            version=__version__,
            updates_enabled=local,
            shutdown_enabled=local,
        )

    @app.get("/api/health")
    def health():
        return jsonify(ok=True)

    @app.post("/api/heartbeat")
    def heartbeat():
        if _is_local():
            inactivity_manager.heartbeat()
        return jsonify(ok=True)

    @app.post("/api/tab-closed")
    def tab_closed():
        if _is_local():
            inactivity_manager.tab_closed()
        return jsonify(ok=True)

    @app.post("/api/shutdown")
    def api_shutdown():
        if not _is_local():
            return _json_error("El apagado del servidor no está permitido en modo nube.", 403)

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
