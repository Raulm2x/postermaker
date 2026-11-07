from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from postermaker import web


def image_bytes(width: int = 900, height: int = 600) -> io.BytesIO:
    image = Image.new("RGB", (width, height), (210, 80, 50))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    image.close()
    buffer.seek(0)
    return buffer


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(web, "OUTPUT_DIR", tmp_path / "output")
    web.app.config.update(TESTING=True)
    with web.app.test_client() as test_client:
        yield test_client


def test_index_and_health(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert b"PosterMaker" in response.data

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_generate_download_and_preview(client) -> None:
    response = client.post(
        "/api/generate",
        data={
            "image": (image_bytes(), "foto.jpg"),
            "pages_wide": "2",
            "paper": "a4",
            "orientation": "portrait",
            "margin": "10",
            "overlap": "4",
            "dpi": "300",
            "marks": "true",
            "labels": "true",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()

    assert payload["pagesWide"] == 2
    assert payload["pagesHigh"] >= 1
    assert payload["widthCm"] > 0
    assert payload["heightCm"] > 0
    assert payload["filename"].endswith(".pdf")
    assert payload["downloadUrl"].startswith("/api/download/")
    assert payload["previewUrl"].startswith("/api/preview/")

    pdf = client.get(payload["downloadUrl"])
    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF")
    assert "attachment" in pdf.headers["Content-Disposition"]

    preview = client.get(payload["previewUrl"])
    assert preview.status_code == 200
    assert preview.data.startswith(b"\x89PNG")


def test_calibration(client) -> None:
    # Por defecto debe ser letter
    default_response = client.get("/api/calibration")
    assert default_response.status_code == 200
    assert "calibracion-letter.pdf" in default_response.headers["Content-Disposition"]

    response = client.get("/api/calibration?paper=letter")
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")
    assert "calibracion-letter.pdf" in response.headers["Content-Disposition"]

    assert client.get("/api/calibration?paper=desconocido").status_code == 400


def test_rejects_invalid_options(client) -> None:
    response = client.post(
        "/api/generate",
        data={
            "image": (image_bytes(), "foto.jpg"),
            "pages_wide": "2",
            "margin": "80",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "margen" in response.get_json()["error"].lower()


def test_rejects_invalid_image(client) -> None:
    response = client.post(
        "/api/generate",
        data={
            "image": (io.BytesIO(b"no soy una imagen"), "foto.jpg"),
            "pages_wide": "2",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "imagen" in response.get_json()["error"].lower()


def test_missing_file_returns_404(client) -> None:
    assert client.get("/api/download/" + "0" * 32).status_code == 404
    assert client.get("/api/download/../../etc/passwd").status_code in (404, 308)


def test_generate_by_pages_high_and_zip(client) -> None:
    import zipfile
    response = client.post(
        "/api/generate",
        data={
            "image": (image_bytes(1000, 1000), "cuadrado.jpg"),
            "dimension_mode": "high",
            "pages_high": "2",
            "paper": "a4",
            "orientation": "portrait",
            "color": "grayscale",
            "guide": "true",
            "margin": "10",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["pagesHigh"] == 2
    assert payload["pagesWide"] == 3
    assert "downloadZipUrl" in payload

    # Probar descarga del ZIP
    zip_resp = client.get(payload["downloadZipUrl"])
    assert zip_resp.status_code == 200
    assert "zip" in zip_resp.headers["Content-Type"]
    with zipfile.ZipFile(io.BytesIO(zip_resp.data)) as zf:
        names = zf.namelist()
        assert "INSTRUCCIONES_MONTAJE.txt" in names
        assert any(n.endswith(".jpg") for n in names)


def test_calibration_other_papers(client) -> None:
    for paper in ("a3", "a5", "tabloid", "legal", "carta", "oficio", "tabloide"):
        resp = client.get(f"/api/calibration?paper={paper}")
        assert resp.status_code == 200
        assert resp.data.startswith(b"%PDF")


def test_inactivity_and_lifecycle_endpoints(client, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Probar heartbeat
    hb_resp = client.post("/api/heartbeat")
    assert hb_resp.status_code == 200
    assert hb_resp.get_json() == {"ok": True}

    # 2. Probar cierre de pestaña
    tc_resp = client.post("/api/tab-closed")
    assert tc_resp.status_code == 200
    assert tc_resp.get_json() == {"ok": True}

    # 3. Probar shutdown
    shutdown_called = []
    monkeypatch.setattr(web.inactivity_manager, "shutdown", lambda reason: shutdown_called.append(reason))

    sd_resp = client.post("/api/shutdown")
    assert sd_resp.status_code == 200
    assert sd_resp.get_json()["ok"] is True


def test_updater_endpoints(client, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Estado inicial de actualización
    st_resp = client.get("/api/update/status")
    assert st_resp.status_code == 200
    data = st_resp.get_json()
    assert "status" in data
    assert "current_version" in data

    # 2. Comprobación mockeada
    monkeypatch.setattr(web.updater, "check_and_update", lambda: {"status": "up_to_date", "message": "Al día"})
    chk_resp = client.post("/api/update/check")
    assert chk_resp.status_code == 200
    assert chk_resp.get_json()["status"] == "up_to_date"


def test_generate_skip_guide_by_default(client) -> None:
    # Por defecto la opción en la web viene marcada como skip_guide="true"
    response = client.post(
        "/api/generate",
        data={
            "image": (image_bytes(800, 600), "foto.jpg"),
            "pages_wide": "2",
            "paper": "a4",
            "orientation": "portrait",
            "skip_guide": "true",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    expected_pages = payload["pagesWide"] * payload["pagesHigh"]

    pdf_resp = client.get(payload["downloadUrl"])
    assert pdf_resp.status_code == 200
    reader = PdfReader(io.BytesIO(pdf_resp.data))
    # No debe incluir la primera página de guía
    assert len(reader.pages) == expected_pages


def test_generate_with_assembly_guide_when_unskipped(client) -> None:
    # Cuando el usuario desmarca "Omitir plano de montaje", skip_guide="false"
    response = client.post(
        "/api/generate",
        data={
            "image": (image_bytes(800, 600), "foto.jpg"),
            "pages_wide": "2",
            "paper": "a4",
            "orientation": "portrait",
            "skip_guide": "false",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    expected_pages = payload["pagesWide"] * payload["pagesHigh"] + 1

    pdf_resp = client.get(payload["downloadUrl"])
    assert pdf_resp.status_code == 200
    reader = PdfReader(io.BytesIO(pdf_resp.data))
    # Debe incluir 1 página extra de plano de montaje al inicio
    assert len(reader.pages) == expected_pages
