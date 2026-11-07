"""Módulo de gestión del servicio de PosterMaker y apertura fluida de la aplicación."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .web import _is_postermaker_running, _open_in_browser


def get_runtime_dir() -> Path:
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        base = Path(xdg_runtime) / "postermaker"
    else:
        base = Path.home() / ".local/state/postermaker"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base


def get_server_info_file() -> Path:
    return get_runtime_dir() / "server.json"


def read_server_info() -> dict | None:
    path = get_server_info_file()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "url" in data and "host" in data and "port" in data:
            return data
    except Exception:
        pass
    return None


def write_server_info(host: str, port: int, pid: int) -> None:
    path = get_server_info_file()
    data = {
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}",
        "pid": pid,
        "started_at": time.time(),
    }
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def remove_server_info() -> None:
    path = get_server_info_file()
    try:
        if path.is_file():
            path.unlink()
    except Exception:
        pass


def is_systemd_user_available() -> bool:
    """Verifica si systemctl --user está disponible y operativo en la sesión actual."""
    if not shutil.which("systemctl"):
        return False
    try:
        res = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True,
            timeout=1.0,
            check=False,
        )
        return res.returncode in (0, 1) and b"Failed to connect" not in res.stderr
    except Exception:
        return False


def start_systemd_service() -> bool:
    """Intenta iniciar el servicio de systemd de usuario."""
    try:
        res = subprocess.run(
            ["systemctl", "--user", "start", "postermaker.service"],
            capture_output=True,
            timeout=3.0,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def launch_or_open(argv: list[str] | None = None, web_runner=None) -> int:
    """Asegura que el servicio esté activo y abre PosterMaker en el navegador."""
    from .web import main as default_web_main

    runner = web_runner or default_web_main
    args = argv or []
    # Si el usuario pasó argumentos explícitos de configuración del servidor
    # (ej. --port, --host, --idle-timeout, --debug, --no-update):
    server_flags = {"--port", "--host", "--idle-timeout", "--debug", "--no-update"}
    if any(a in server_flags for a in args):
        if "--open" not in args:
            args.append("--open")
        return runner(args)

    # 1. Comprobar si ya hay una instancia activa (vía server.json o puertos 8000..8015)
    info = read_server_info()
    if info:
        host, port, url = info["host"], info["port"], info["url"]
        if _is_postermaker_running(host, port):
            print(f"PosterMaker ya está en ejecución en: {url}")
            _open_in_browser(url)
            return 0
        else:
            remove_server_info()

    for p in range(8000, 8016):
        if _is_postermaker_running("127.0.0.1", p):
            url = f"http://127.0.0.1:{p}"
            print(f"PosterMaker ya está en ejecución en: {url}")
            _open_in_browser(url)
            return 0

    # 2. Intentar iniciar vía servicio systemd de usuario si está disponible
    if is_systemd_user_available():
        started = start_systemd_service()
        if started:
            deadline = time.time() + 3.5
            while time.time() < deadline:
                info = read_server_info()
                if info and _is_postermaker_running(info["host"], info["port"]):
                    url = info["url"]
                    print(f"PosterMaker iniciado vía systemd en: {url}")
                    _open_in_browser(url)
                    return 0
                for p in range(8000, 8016):
                    if _is_postermaker_running("127.0.0.1", p):
                        url = f"http://127.0.0.1:{p}"
                        print(f"PosterMaker iniciado vía systemd en: {url}")
                        _open_in_browser(url)
                        return 0
                time.sleep(0.1)

    # 3. Fallback directo: iniciar el servidor web integrado en este proceso
    fallback_args = list(args)
    if "--open" not in fallback_args:
        fallback_args.append("--open")
    return runner(fallback_args)
