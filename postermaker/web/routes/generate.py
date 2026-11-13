"""Rutas de procesamiento y generación de pósteres (unitarios y en lote), y descargas."""

from __future__ import annotations

import io
import json
import shutil
import time
import uuid
from pathlib import Path
from flask import Flask, abort, jsonify, request, send_file

from ...image import ImageError
from ...pipeline import generate_poster, generate_posters_batch
from ..config import MAX_UPLOAD_BYTES, get_output_dir
from ..jobs import _cleanup_old_jobs, _job_dir, _read_meta, create_tiles_zip
from ..options import _json_error, _parse_options


def register_generate_routes(app: Flask) -> None:
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
        job_dir = get_output_dir() / job_id
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
        zip_path = create_tiles_zip(job_dir)
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
