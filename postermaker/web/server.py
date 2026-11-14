"""Gestión de red, puertos, apertura del navegador y arranque del servidor web."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from ..updater import updater
from .config import (
    get_default_host,
    get_default_idle_timeout,
    get_default_port,
    get_output_dir,
    is_local_mode,
)
from .inactivity import inactivity_manager


def _is_postermaker_running(host: str, port: int) -> bool:
    """Comprueba si ya hay una instancia de PosterMaker respondiendo en host:port."""
    connect_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    try:
        url = f"http://{connect_host}:{port}/api/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _is_port_available(host: str, port: int) -> bool:
    """Comprueba si un puerto está libre para escuchar conexiones en host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _find_available_port(
    host: str,
    start_port: int = 8000,
    max_port: int = 65535,
) -> int:
    """Encuentra el primer puerto libre comenzando en start_port e incrementando sucesivamente."""
    mod = sys.modules.get("postermaker.web", sys.modules[__name__])
    is_avail = getattr(mod, "_is_port_available", _is_port_available)

    for port in range(start_port, max_port + 1):
        if is_avail(host, port):
            return port
    raise RuntimeError(
        f"No se encontró ningún puerto disponible para iniciar el servidor entre {start_port} y {max_port}."
    )


def _open_in_browser(url: str) -> None:
    """Abre la URL en el navegador usando xdg-open o webbrowser."""
    # 1. Notificación de escritorio si notify-send está disponible
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(
                ["notify-send", "-a", "PosterMaker", "PosterMaker", f"Abriendo en {url}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    # 2. Abrir navegador con xdg-open en proceso independiente
    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        except Exception:
            pass

    # 3. Fallback al módulo estándar de Python
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    mod = sys.modules.get("postermaker.web", sys.modules[__name__])
    is_running_fn = getattr(mod, "_is_postermaker_running", _is_postermaker_running)
    find_port_fn = getattr(mod, "_find_available_port", _find_available_port)
    open_browser_fn = getattr(mod, "_open_in_browser", _open_in_browser)
    local_fn = getattr(mod, "is_local_mode", is_local_mode)
    local = local_fn()
    app_obj = getattr(mod, "app", None)

    default_port = get_default_port()
    if "HOST" in os.environ and os.environ["HOST"].strip():
        default_host = os.environ["HOST"].strip()
    elif "POSTERMAKER_HOST" in os.environ and os.environ["POSTERMAKER_HOST"].strip():
        default_host = os.environ["POSTERMAKER_HOST"].strip()
    else:
        default_host = "127.0.0.1" if local else "0.0.0.0"

    if "IDLE_TIMEOUT" in os.environ and os.environ["IDLE_TIMEOUT"].strip():
        try:
            default_timeout = max(0, int(os.environ["IDLE_TIMEOUT"].strip()))
        except ValueError:
            default_timeout = 900 if local else 0
    else:
        default_timeout = 900 if local else 0

    parser = argparse.ArgumentParser(
        prog="postermaker-web",
        description="Servidor para crear pósteres imprimibles.",
    )
    parser.add_argument("--host", default=default_host)
    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
        help="Puerto inicial de escucha (por defecto 8000 en local o $PORT en cloud).",
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Abrir automáticamente la interfaz en el navegador web.",
    )
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=default_timeout,
        help="Segundos de inactividad antes de liberar memoria y cerrar el servidor (0 para desactivar).",
    )
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Desactivar la comprobación automática de actualizaciones al iniciar.",
    )
    args = parser.parse_args(argv)

    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    inactivity_manager.timeout = args.idle_timeout
    if args.idle_timeout > 0:
        inactivity_manager.start()

    should_check_update = (not args.no_update) and local
    if should_check_update:
        threading.Thread(target=updater.check_and_update, daemon=True).start()

    target_port = args.port

    if local:
        # 1. Si PosterMaker ya está corriendo:
        for p in range(target_port, min(target_port + 50, 65535 + 1)):
            if is_running_fn(args.host, p):
                url = f"http://{args.host}:{p}"
                print(f"PosterMaker ya está en ejecución en: {url}")
                if args.open:
                    open_browser_fn(url)
                return 0

        # 2. Si el puerto inicial no está libre, intentar con los siguientes:
        free_port = find_port_fn(args.host, target_port)
        if free_port != target_port:
            print(f"Puerto {target_port} no disponible. Probando con los siguientes... asignado puerto {free_port}")
            target_port = free_port

        url = f"http://{args.host}:{target_port}"
        print(f"PosterMaker local: {url}")

        import atexit
        from ..service import write_server_info, remove_server_info

        try:
            write_server_info(args.host, target_port, os.getpid())
            atexit.register(remove_server_info)
        except Exception:
            pass

        if args.open:
            def _deferred_open():
                deadline = time.time() + 4.0
                opened = False
                while time.time() < deadline:
                    if is_running_fn(args.host, target_port):
                        open_browser_fn(url)
                        opened = True
                        break
                    time.sleep(0.1)
                if not opened:
                    open_browser_fn(url)

            threading.Thread(target=_deferred_open, daemon=True).start()
    else:
        url = f"http://{args.host}:{target_port}"
        print(f"PosterMaker en la nube escuchando en: {url}")

    try:
        app_obj.run(host=args.host, port=target_port, debug=args.debug)
    finally:
        if local:
            try:
                from ..service import remove_server_info
                remove_server_info()
            except Exception:
                pass
    return 0
