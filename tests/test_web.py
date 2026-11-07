from __future__ import annotations

import io
import re
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
    assert re.search(r"poster_2x\d+_a4_portrait_\d{8}_\d{6}\.pdf$", payload["filename"])
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
    monkeypatch.setattr(web.updater, "check_updates", lambda: {"status": "available", "latest_version": "0.3.0", "has_update": True})
    chk_resp = client.post("/api/update/check")
    assert chk_resp.status_code == 200
    assert chk_resp.get_json()["status"] == "available"

    # 3. Aplicar actualización mockeada
    monkeypatch.setattr(web.updater, "apply_update", lambda: {"status": "updated", "latest_version": "0.3.0", "has_update": False})
    apply_resp = client.post("/api/update/apply")
    assert apply_resp.status_code == 200
    assert apply_resp.get_json()["status"] == "updated"


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


def test_find_available_port_sequential() -> None:
    import socket

    # Seleccionamos un rango de puertos efímeros para la prueba
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        base_port = probe.getsockname()[1]

    # 1. Cuando base_port está libre
    assert web._find_available_port("127.0.0.1", start_port=base_port) == base_port

    # 2. Cuando base_port y base_port+1 están ocupados
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.bind(("127.0.0.1", base_port))
    s1.listen(1)

    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.bind(("127.0.0.1", base_port + 1))
    s2.listen(1)

    try:
        # Debe saltar base_port y base_port+1 y retornar base_port+2 o superior libre
        found_port = web._find_available_port("127.0.0.1", start_port=base_port)
        assert found_port >= base_port + 2
    finally:
        s1.close()
        s2.close()


def test_main_finds_next_port_when_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(web, "_is_postermaker_running", lambda host, port: False)

    def fake_is_port_available(host: str, port: int) -> bool:
        return port != 8000

    monkeypatch.setattr(web, "_is_port_available", fake_is_port_available)
    monkeypatch.setattr(web.app, "run", lambda **kwargs: calls.append(kwargs))

    code = web.main(["--port", "8000", "--no-update"])
    assert code == 0
    assert len(calls) == 1
    assert calls[0]["port"] == 8001


def test_main_reuses_existing_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "_is_postermaker_running", lambda host, port: port == 8000)
    run_called = []
    monkeypatch.setattr(web.app, "run", lambda **kwargs: run_called.append(kwargs))

    code = web.main(["--port", "8000", "--no-update"])
    assert code == 0
    assert len(run_called) == 0


def test_generate_default_margin_3mm(client) -> None:
    # Cuando no se especifica margen, debe usar 3 mm por omisión
    response = client.post(
        "/api/generate",
        data={
            "image": (image_bytes(800, 600), "foto.jpg"),
            "pages_wide": "2",
            "paper": "a4",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert re.search(r"poster_2x\d+_a4_portrait_\d{8}_\d{6}\.pdf$", payload["filename"])


def test_generate_batch_combined_default(client) -> None:
    # Por defecto múltiples imágenes generan un único PDF combinado
    response = client.post(
        "/api/generate",
        data={
            "image": [
                (image_bytes(600, 600), "primera.jpg"),
                (image_bytes(600, 600), "segunda.jpg"),
            ],
            "pages_wide": "1",
            "paper": "letter",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isBatch"] is True
    assert payload["separate"] is False
    assert payload["posterCount"] == 2
    assert "posters_combinados_2_imagenes" in payload["filename"]
    assert payload["filename"].endswith(".pdf")

    pdf_resp = client.get(payload["downloadUrl"])
    assert pdf_resp.status_code == 200
    assert pdf_resp.data.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(pdf_resp.data))
    assert len(reader.pages) == 2


def test_generate_batch_separate_option(client) -> None:
    # Opción de generar cada póster por separado
    response = client.post(
        "/api/generate",
        data={
            "image": [
                (image_bytes(600, 600), "fotoA.jpg"),
                (image_bytes(600, 600), "fotoB.jpg"),
            ],
            "separate_posters": "true",
            "pages_wide": "1",
            "paper": "letter",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isBatch"] is True
    assert payload["separate"] is True
    assert payload["posterCount"] == 2
    assert "posters_separados_2_imagenes" in payload["filename"]
    assert payload["filename"].endswith(".zip")
    assert len(payload["items"]) == 2

    # Descarga del ZIP completo
    zip_resp = client.get(payload["downloadUrl"])
    assert zip_resp.status_code == 200
    import zipfile
    with zipfile.ZipFile(io.BytesIO(zip_resp.data), "r") as zf:
        names = zf.namelist()
        assert len(names) == 2
        assert any("fotoA" in n for n in names)
        assert any("fotoB" in n for n in names)

    # Descarga de un póster individual
    item1 = payload["items"][0]
    single_resp = client.get(item1["downloadUrl"])
    assert single_resp.status_code == 200
    assert single_resp.data.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(single_resp.data))
    assert len(reader.pages) == 1
