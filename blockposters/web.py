"""Servidor web local con la interfaz para crear pósteres."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    request,
    send_file,
    send_from_directory,
)
from werkzeug.exceptions import HTTPException

from .calibration import calibration_pdf
from .image import ImageError
from .paper import PAPERS, Margins
from .pipeline import generate_poster

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    candidate = Path(sys._MEIPASS) / "blockposters"
    BASE_DIR = candidate if candidate.is_dir() else Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = Path(
    os.environ.get(
        "BLOCKPOSTERS_OUTPUT", str(Path(tempfile.gettempdir()) / "blockposters")
    )
)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
JOB_PATTERN = re.compile(r"^[0-9a-f]{32}$")
MAX_JOB_AGE_SECONDS = 6 * 60 * 60

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


class InactivityManager:
    """Gestiona el apagado automático por inactividad y la liberación de memoria/recursos."""

    def __init__(self, timeout_seconds: int = 900, tab_close_grace_seconds: int = 180):
        self.timeout = timeout_seconds
        self.tab_close_grace = tab_close_grace_seconds
        self.last_activity = time.time()
        self.active_tabs = 1
        self._lock = threading.Lock()
        self._stopped = False
        self._thread: threading.Thread | None = None

    def touch(self) -> None:
        with self._lock:
            self.last_activity = time.time()

    def heartbeat(self) -> None:
        with self._lock:
            self.last_activity = time.time()
            if self.active_tabs <= 0:
                self.active_tabs = 1

    def tab_opened(self) -> None:
        with self._lock:
            self.active_tabs += 1
            self.last_activity = time.time()

    def tab_closed(self) -> None:
        with self._lock:
            if self.active_tabs > 0:
                self.active_tabs -= 1
            self.last_activity = time.time()

    def shutdown(self, reason: str = "Inactividad") -> None:
        print(f"Liberando recursos del sistema ({reason})...")
        try:
            if OUTPUT_DIR.is_dir():
                shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        except Exception:
            pass
        import gc
        gc.collect()
        os._exit(0)

    def start(self) -> None:
        if self.timeout <= 0:
            return

        def _monitor() -> None:
            while not self._stopped:
                time.sleep(10)
                with self._lock:
                    elapsed = time.time() - self.last_activity
                    tabs = self.active_tabs

                if tabs == 0 and elapsed >= self.tab_close_grace:
                    self.shutdown(reason=f"Sin pestañas activas tras {int(elapsed)}s")
                    break

                if elapsed >= self.timeout:
                    self.shutdown(reason=f"Inactividad total tras {int(elapsed)}s")
                    break

        self._thread = threading.Thread(target=_monitor, daemon=True)
        self._thread.start()


inactivity_manager = InactivityManager()


@app.before_request
def _track_request_activity():
    inactivity_manager.touch()


def _json_error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify(error=message), status


def _parse_int(form, key: str, default: int, minimum: int, maximum: int, label: str) -> int:
    raw = form.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} no es válido.") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} debe estar entre {minimum} y {maximum}.")
    return value


def _parse_float(
    form, key: str, default: float, minimum: float, maximum: float, label: str
) -> float:
    raw = form.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} no es válido.") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} debe estar entre {minimum} y {maximum}.")
    return value


def _parse_bool(form, key: str) -> bool:
    return str(form.get(key, "false")).lower() in {"1", "true", "on", "yes"}


def _parse_options(form):
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
    margin = _parse_float(form, "margin", 10.0, 0.0, 30.0, "El margen")
    overlap = _parse_float(form, "overlap", 0.0, 0.0, 20.0, "El solapamiento")
    dpi = _parse_int(form, "dpi", 300, 72, 600, "La resolución")
    marks = _parse_bool(form, "marks")
    labels = _parse_bool(form, "labels")
    guide = _parse_bool(form, "guide") or _parse_bool(form, "assembly_guide")
    color = str(form.get("color", form.get("color_mode", "color"))).strip().lower()
    if color not in ("color", "grayscale", "monochrome"):
        color = "color"

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
    }


def _cleanup_old_jobs() -> None:
    if not OUTPUT_DIR.is_dir():
        return
    now = time.time()
    for child in OUTPUT_DIR.iterdir():
        try:
            if child.is_dir() and now - child.stat().st_mtime > MAX_JOB_AGE_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue


def _job_dir(job_id: str) -> Path:
    if not JOB_PATTERN.fullmatch(job_id):
        abort(404)
    return OUTPUT_DIR / job_id


def _read_meta(job_dir: Path) -> dict:
    try:
        return json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


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
    return jsonify(ok=True, message="Servidor apagado y recursos liberados con éxito.")


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


@app.post("/api/generate")
def generate():
    _cleanup_old_jobs()

    upload = request.files.get("image")
    if upload is None or not upload.filename:
        return _json_error("Selecciona una imagen antes de crear el póster.")

    payload = upload.read()
    if not payload:
        return _json_error("La imagen está vacía.")
    if len(payload) > MAX_UPLOAD_BYTES:
        return _json_error("La imagen supera el límite de 25 MB.", 413)

    try:
        options = _parse_options(request.form)
    except ValueError as exc:
        return _json_error(str(exc))

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = generate_poster(
            io.BytesIO(payload),
            job_dir / "poster.pdf",
            pages_wide=options["pages_wide"],
            pages_high=options["pages_high"],
            paper=options["paper"],
            orientation=options["orientation"],
            margins=options["margins"],
            dpi=options["dpi"],
            overlap_mm=options["overlap_mm"],
            marks=options["marks"],
            labels=options["labels"],
            color_mode=options["color_mode"],
            assembly_guide=options["assembly_guide"],
            tiles_dir=job_dir / "tiles",
            preview_path=job_dir / "preview.png",
        )
    except (ImageError, ValueError) as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return _json_error(str(exc), 400)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        app.logger.exception("Error generando el póster")
        return _json_error(
            "No se pudo generar el PDF. Revisa la imagen e inténtalo de nuevo.", 500
        )

    grid = result.grid
    filename = (
        f"poster_{grid.pages_wide}x{grid.pages_high}_"
        f"{grid.paper.key}_{grid.orientation}.pdf"
    )
    meta = {
        "filename": filename,
        "created": time.time(),
        "pages_wide": grid.pages_wide,
        "pages_high": grid.pages_high,
        "paper": grid.paper.key,
        "orientation": grid.orientation,
    }
    (job_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    return jsonify(
        id=job_id,
        downloadUrl=f"/api/download/{job_id}",
        downloadZipUrl=f"/api/download/{job_id}/zip",
        previewUrl=f"/api/preview/{job_id}",
        filename=filename,
        pagesWide=grid.pages_wide,
        pagesHigh=grid.pages_high,
        totalPages=grid.total_pages,
        widthCm=round(grid.poster_width_cm, 1),
        heightCm=round(grid.poster_height_cm, 1),
        widthIn=round(grid.poster_width_in, 1),
        heightIn=round(grid.poster_height_in, 1),
        pageWidthCm=round(grid.page_width_mm / 10, 1),
        pageHeightCm=round(grid.page_height_mm / 10, 1),
        paperName=grid.paper.name,
        orientation=grid.orientation,
        effectiveDpi=round(result.effective_dpi),
        renderDpi=round(result.render_dpi),
        sizeBytes=(job_dir / "poster.pdf").stat().st_size,
    )


@app.get("/api/download/<job_id>")
def download(job_id: str):
    job_dir = _job_dir(job_id)
    path = job_dir / "poster.pdf"
    if not path.is_file():
        abort(404)
    meta = _read_meta(job_dir)
    filename = meta.get("filename") or "poster.pdf"
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@app.get("/api/download/<job_id>/zip")
def download_zip(job_id: str):
    job_dir = _job_dir(job_id)
    tiles_dir = job_dir / "tiles"
    if not tiles_dir.is_dir():
        abort(404)

    zip_path = job_dir / "tiles.zip"
    if not zip_path.is_file():
        meta = _read_meta(job_dir)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(tiles_dir.glob("*.jpg")):
                zf.write(p, arcname=p.name)
            readme = (
                f"Block Posters Local - Piezas individuales del póster\n"
                f"Cuadrícula: {meta.get('pages_wide', '?')} x {meta.get('pages_high', '?')} hojas\n"
                f"Papel: {meta.get('paper', '?')} ({meta.get('orientation', '?')})\n\n"
                f"Instrucciones de impresión:\n"
                f"1. Imprime cada archivo JPG a tamaño real (100% de escala, sin ajustar a página).\n"
                f"2. Recorta los bordes blancos siguiendo las marcas de corte.\n"
                f"3. Ensambla las hojas de izquierda a derecha y de arriba a abajo.\n"
            )
            zf.writestr("INSTRUCCIONES_MONTAJE.txt", readme)

    meta = _read_meta(job_dir)
    raw_filename = meta.get("filename", "poster.pdf")
    zip_name = raw_filename.removesuffix(".pdf") + "_piezas.zip"
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )


@app.get("/api/preview/<job_id>")
def preview(job_id: str):
    job_dir = _job_dir(job_id)
    path = job_dir / "preview.png"
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/png")


@app.errorhandler(413)
def too_large(_error):
    return _json_error("La imagen supera el límite de 25 MB.", 413)


@app.errorhandler(HTTPException)
def http_error(error: HTTPException):
    if request.path.startswith("/api/"):
        return _json_error(error.description or error.name, error.code or 500)
    return error


def _is_blockposters_running(host: str, port: int) -> bool:
    """Comprueba si ya hay una instancia de Block Posters respondiendo en host:port."""
    try:
        url = f"http://{host}:{port}/api/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_available_port(host: str, start_port: int, max_attempts: int = 20) -> int:
    """Encuentra un puerto disponible comenzando en start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return start_port


def _open_in_browser(url: str) -> None:
    """Abre la URL en el navegador usando xdg-open o webbrowser."""
    # 1. Notificación de escritorio si notify-send está disponible
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(
                ["notify-send", "-a", "Block Posters", "Block Posters", f"Abriendo en {url}"],
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
    parser = argparse.ArgumentParser(
        prog="blockposters-web",
        description="Servidor local para crear pósteres imprimibles.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Abrir automáticamente la interfaz en el navegador web.",
    )
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=900,
        help="Segundos de inactividad antes de liberar memoria y cerrar el servidor (por defecto 900s / 15m; 0 para desactivar).",
    )
    args = parser.parse_args(argv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    inactivity_manager.timeout = args.idle_timeout
    inactivity_manager.start()

    target_port = args.port

    # Si ya hay una instancia de Block Posters activa en el puerto:
    if _is_blockposters_running(args.host, target_port):
        url = f"http://{args.host}:{target_port}"
        print(f"Block Posters ya está en ejecución en: {url}")
        if args.open:
            _open_in_browser(url)
        return 0

    # Si el puerto está ocupado por otro proceso, buscar el siguiente disponible
    free_port = _find_available_port(args.host, target_port)
    if free_port != target_port:
        print(f"Puerto {target_port} ocupado, usando puerto {free_port}")
        target_port = free_port

    url = f"http://{args.host}:{target_port}"
    print(f"Block Posters local: {url}")

    if args.open:
        import threading

        threading.Timer(0.3, lambda: _open_in_browser(url)).start()

    app.run(host=args.host, port=target_port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
