from __future__ import annotations

import zipfile
from pathlib import Path
from PIL import Image
import pytest

from postermaker.cli import main


def make_test_image(path: Path) -> Path:
    img = Image.new("RGB", (600, 600), (200, 100, 50))
    img.save(path)
    img.close()
    return path


def test_cli_calibration(tmp_path: Path) -> None:
    cal_pdf = tmp_path / "cal.pdf"
    code = main(["--calibration", "a5", "-o", str(cal_pdf)])
    assert code == 0
    assert cal_pdf.is_file()
    assert cal_pdf.stat().st_size > 0


def test_cli_poster_with_options(tmp_path: Path) -> None:
    src = make_test_image(tmp_path / "src.jpg")
    out_pdf = tmp_path / "poster.pdf"
    out_zip = tmp_path / "poster.zip"
    preview = tmp_path / "preview.png"

    code = main([
        str(src),
        "-o", str(out_pdf),
        "--pages-high", "2",
        "--paper", "a4",
        "--color", "grayscale",
        "--guide",
        "--zip", str(out_zip),
        "--preview", str(preview),
    ])
    assert code == 0
    assert out_pdf.is_file()
    assert out_zip.is_file()
    assert preview.is_file()

    with zipfile.ZipFile(out_zip, "r") as zf:
        names = zf.namelist()
        assert len(names) >= 4


def test_cli_guide_and_skip_guide(tmp_path: Path) -> None:
    from pypdf import PdfReader

    src = make_test_image(tmp_path / "src.jpg")
    out_default = tmp_path / "out_default.pdf"
    out_with_guide = tmp_path / "out_with_guide.pdf"
    out_skip_guide = tmp_path / "out_skip_guide.pdf"

    # 1. Por defecto no incluye guía
    code = main([str(src), "-o", str(out_default), "--pages-high", "1"])
    assert code == 0
    pages_default = len(PdfReader(str(out_default)).pages)

    # 2. Con --guide incluye la página de guía (+1)
    code = main([str(src), "-o", str(out_with_guide), "--pages-high", "1", "--guide"])
    assert code == 0
    pages_guide = len(PdfReader(str(out_with_guide)).pages)
    assert pages_guide == pages_default + 1

    # 3. Con --skip-guide explícitamente no incluye la guía
    code = main([str(src), "-o", str(out_skip_guide), "--pages-high", "1", "--skip-guide"])
    assert code == 0
    pages_skip = len(PdfReader(str(out_skip_guide)).pages)
    assert pages_skip == pages_default


def test_main_entrypoint_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    from postermaker import __main__ as bp_main

    web_calls: list[list[str]] = []
    cli_calls: list[list[str]] = []
    install_calls: list[bool] = []

    monkeypatch.setattr(bp_main, "web_main", lambda args: web_calls.append(args) or 0)
    monkeypatch.setattr(bp_main, "cli_main", lambda args: cli_calls.append(args) or 0)
    monkeypatch.setattr(bp_main, "install_desktop", lambda: install_calls.append(True) or 0)

    # 1. Sin argumentos -> web con --open
    assert bp_main.main([]) == 0
    assert web_calls[-1] == ["--open"]

    # 2. Con --web y flags de servidor
    assert bp_main.main(["--web", "--port", "9999"]) == 0
    assert web_calls[-1] == ["--port", "9999", "--open"]

    # 3. Con --install
    assert bp_main.main(["--install"]) == 0
    assert install_calls == [True]

    # 4. CLI normal
    assert bp_main.main(["imagen.png", "-o", "out.pdf"]) == 0
    assert cli_calls[-1] == ["imagen.png", "-o", "out.pdf"]
