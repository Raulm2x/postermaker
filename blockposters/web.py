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
from .pipeline import generate_poster, generate_posters_batch
from .updater import updater

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    for cand in (
        Path(sys._MEIPASS) / "postermaker",
        Path(sys._MEIPASS) / "blockposters",
    ):
        if cand.is_dir():
            BASE_DIR = cand
            break
    else:
        BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = Path(
    os.environ.get(
        "POSTERMAKER_OUTPUT",
        os.environ.get("BLOCKPOSTERS_OUTPUT", str(Path(tempfile.gettempdir()) / "postermaker")),
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


@app.get("/api/update/status")
def update_status():
    return jsonify(updater.get_state())


@app.post("/api/update/check")
def update_check():
    result = updater.check_and_update()
    return jsonify(result)


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

    upload_list = request.files.getlist("images") + request.files.getlist("image")
    uploads = [f for f in upload_list if f and f.filename]
    if not uploads:
        return _json_error("Selecciona al menos una imagen antes de crear el póster.")

    valid_uploads: list[tuple[str, io.BytesIO]] = []
    for u in uploads:
        payload = u.read()
        if not payload:
            continue
        if len(payload) > MAX_UPLOAD_BYTES:
            return _json_error(
                f"La imagen '{u.filename}' supera el límite de 25 MB.", 413
            )
        valid_uploads.append((u.filename, io.BytesIO(payload)))

    if not valid_uploads:
        return _json_error("La imagen está vacía.")

    try:
        options = _parse_options(request.form)
    except ValueError as exc:
        return _json_error(str(exc))

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1. Caso unitario: una sola imagen
    if len(valid_uploads) == 1:
        _, payload_stream = valid_uploads[0]
        try:
            result = generate_poster(
                payload_stream,
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
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = (
            f"poster_{grid.pages_wide}x{grid.pages_high}_"
            f"{grid.paper.key}_{grid.orientation}_{timestamp}.pdf"
        )
        total_pages = grid.total_pages + (1 if options["assembly_guide"] else 0)
        meta = {
            "filename": filename,
            "created": time.time(),
            "is_batch": False,
            "pages_wide": grid.pages_wide,
            "pages_high": grid.pages_high,
            "paper": grid.paper.key,
            "orientation": grid.orientation,
            "total_pages": total_pages,
        }
        (job_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        return jsonify(
            id=job_id,
            isBatch=False,
            downloadUrl=f"/api/download/{job_id}",
            downloadZipUrl=f"/api/download/{job_id}/zip",
            previewUrl=f"/api/preview/{job_id}",
            filename=filename,
            pagesWide=grid.pages_wide,
            pagesHigh=grid.pages_high,
            totalPages=total_pages,
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

    # 2. Caso múltiple: varias imágenes
    separate = options["separate"]
    posters_dir = job_dir / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)
    tiles_dir = job_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    if separate:
        target_path = job_dir / "posters_separados.zip"
        batch_filename = f"posters_separados_{len(valid_uploads)}_imagenes_{timestamp}.zip"
    else:
        target_path = job_dir / "poster.pdf"
        batch_filename = f"posters_combinados_{len(valid_uploads)}_imagenes_{timestamp}.pdf"

    try:
        batch_res = generate_posters_batch(
            valid_uploads,
            target_path,
            separate=separate,
            separate_dir=posters_dir,
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
            tiles_base_dir=tiles_dir,
            preview_path=job_dir / "preview.png",
        )
    except (ImageError, ValueError) as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return _json_error(str(exc), 400)
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        app.logger.exception("Error generando el lote de pósteres")
        return _json_error(
            "No se pudieron generar los pósteres. Revisa las imágenes e inténtalo de nuevo.", 500
        )

    items_meta = []
    for it in batch_res.items:
        g = it.result.grid
        item_pages = g.total_pages + (1 if options["assembly_guide"] else 0)
        items_meta.append({
            "name": it.name,
            "filename": it.pdf_path.name,
            "pagesWide": g.pages_wide,
            "pagesHigh": g.pages_high,
            "totalPages": item_pages,
            "widthCm": round(g.poster_width_cm, 1),
            "heightCm": round(g.poster_height_cm, 1),
            "sizeBytes": it.pdf_path.stat().st_size if it.pdf_path.is_file() else 0,
            "downloadUrl": f"/api/download/{job_id}/file/{it.pdf_path.name}",
        })

    meta = {
        "filename": batch_filename,
        "created": time.time(),
        "is_batch": True,
        "separate": separate,
        "poster_count": len(valid_uploads),
        "total_pages": batch_res.total_pages,
        "items": items_meta,
    }
    (job_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    first_grid = batch_res.items[0].result.grid
    return jsonify(
        id=job_id,
        isBatch=True,
        separate=separate,
        posterCount=len(valid_uploads),
        totalPages=batch_res.total_pages,
        downloadUrl=f"/api/download/{job_id}",
        downloadZipUrl=f"/api/download/{job_id}/zip",
        previewUrl=f"/api/preview/{job_id}",
        filename=batch_filename,
        sizeBytes=target_path.stat().st_size if target_path.is_file() else 0,
        items=items_meta,
        pagesWide=first_grid.pages_wide,
        pagesHigh=first_grid.pages_high,
        widthCm=round(first_grid.poster_width_cm, 1),
        heightCm=round(first_grid.poster_height_cm, 1),
        paperName=first_grid.paper.name,
        orientation=first_grid.orientation,
    )


@app.get("/api/download/<job_id>")
def download(job_id: str):
    job_dir = _job_dir(job_id)
    pdf_path = job_dir / "poster.pdf"
    zip_path = job_dir / "posters_separados.zip"
    if pdf_path.is_file():
        path = pdf_path
        mimetype = "application/pdf"
    elif zip_path.is_file():
        path = zip_path
        mimetype = "application/zip"
    else:
        abort(404)

    meta = _read_meta(job_dir)
    filename = meta.get("filename") or path.name
    return send_file(
        path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )


@app.get("/api/download/<job_id>/file/<path:filename>")
def download_file(job_id: str, filename: str):
    job_dir = _job_dir(job_id)
    posters_dir = (job_dir / "posters").resolve()
    target_file = (posters_dir / filename).resolve()
    if not target_file.is_file() or posters_dir not in target_file.parents:
        abort(404)
    return send_file(
        target_file,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=target_file.name,
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
            for p in sorted(tiles_dir.rglob("*.jpg")):
                arcname = p.relative_to(tiles_dir).as_posix()
                zf.write(p, arcname=arcname)
            readme = (
                f"PosterMaker Local - Piezas individuales del póster\n"
                f"Archivos procesados: {meta.get('poster_count', 1)}\n"
                f"Total de páginas: {meta.get('total_pages', meta.get('pages_wide', 1) * meta.get('pages_high', 1))}\n\n"
                f"Instrucciones de impresión:\n"
                f"1. Imprime cada archivo JPG a tamaño real (100% de escala, sin ajustar a página).\n"
                f"2. Recorta los bordes blancos siguiendo las marcas de corte.\n"
                f"3. Ensambla las hojas de izquierda a derecha y de arriba a abajo.\n"
            )
            zf.writestr("INSTRUCCIONES_MONTAJE.txt", readme)

    meta = _read_meta(job_dir)
    raw_filename = meta.get("filename", "poster.pdf")
    zip_name = raw_filename.removesuffix(".pdf").removesuffix(".zip") + "_piezas.zip"
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


_is_blockposters_running = _is_postermaker_running


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
    for port in range(start_port, max_port + 1):
        if _is_port_available(host, port):
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
    parser = argparse.ArgumentParser(
        prog="postermaker-web",
        description="Servidor local para crear pósteres imprimibles.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Puerto inicial de escucha (por defecto 8000; si está ocupado, prueba con los siguientes hasta encontrar uno libre).",
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
        default=900,
        help="Segundos de inactividad antes de liberar memoria y cerrar el servidor (por defecto 900s / 15m; 0 para desactivar).",
    )
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Desactivar la comprobación automática de actualizaciones al iniciar.",
    )
    args = parser.parse_args(argv)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    inactivity_manager.timeout = args.idle_timeout
    inactivity_manager.start()

    if not args.no_update:
        threading.Thread(target=updater.check_and_update, daemon=True).start()

    target_port = args.port

    # 1. Si PosterMaker ya está corriendo (comprobando el puerto inicial o los siguientes cercanos):
    for p in range(target_port, min(target_port + 50, 65535 + 1)):
        if _is_postermaker_running(args.host, p):
            url = f"http://{args.host}:{p}"
            print(f"PosterMaker ya está en ejecución en: {url}")
            if args.open:
                _open_in_browser(url)
            return 0

    # 2. Si el puerto inicial no está libre, intentar con los siguientes hasta encontrar uno disponible:
    free_port = _find_available_port(args.host, target_port)
    if free_port != target_port:
        print(f"Puerto {target_port} no disponible. Probando con los siguientes... asignado puerto {free_port}")
        target_port = free_port

    url = f"http://{args.host}:{target_port}"
    print(f"PosterMaker local: {url}")

    import atexit
    from .service import write_server_info, remove_server_info

    write_server_info(args.host, target_port, os.getpid())
    atexit.register(remove_server_info)

    if args.open:
        def _deferred_open():
            deadline = time.time() + 4.0
            opened = False
            while time.time() < deadline:
                if _is_postermaker_running(args.host, target_port):
                    _open_in_browser(url)
                    opened = True
                    break
                time.sleep(0.1)
            if not opened:
                _open_in_browser(url)

        threading.Thread(target=_deferred_open, daemon=True).start()

    try:
        app.run(host=args.host, port=target_port, debug=args.debug)
    finally:
        remove_server_info()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
