from __future__ import annotations

import os
from pathlib import Path
import pytest

from postermaker import installer
from postermaker.cli import main as cli_main


def test_resolve_paths() -> None:
    paths = installer._resolve_paths()
    assert "bin" in paths
    assert "apps" in paths
    assert "icons" in paths
    assert "pixmaps" in paths


def test_get_icon_bytes() -> None:
    data = installer._get_icon_bytes()
    assert b"<svg" in data
    assert b"</svg>" in data


def test_install_and_uninstall_desktop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_paths = {
        "bin": tmp_path / "bin",
        "apps": tmp_path / "applications",
        "icons": tmp_path / "icons",
        "pixmaps": tmp_path / "pixmaps",
    }
    monkeypatch.setattr(installer, "_resolve_paths", lambda: test_paths)

    # 1. Probar instalación
    code = installer.install_desktop()
    assert code == 0

    dest_bin = test_paths["bin"] / "postermaker"
    alias_bin = test_paths["bin"] / "blockposters"
    dest_desktop = test_paths["apps"] / "postermaker.desktop"
    dest_icon = test_paths["icons"] / "postermaker.svg"
    dest_pixmap = test_paths["pixmaps"] / "postermaker.svg"

    assert dest_bin.is_file()
    assert os.access(dest_bin, os.X_OK)
    assert alias_bin.is_symlink()
    assert dest_desktop.is_file()
    assert dest_icon.is_file()
    assert dest_pixmap.is_file()

    # Verificar contenido del archivo .desktop
    content = dest_desktop.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in content
    assert "Name=PosterMaker" in content
    assert "Icon=postermaker" in content
    assert "Exec=" in content

    # 2. Probar desinstalación
    code_un = installer.uninstall_desktop()
    assert code_un == 0

    assert not dest_bin.is_file()
    assert not alias_bin.is_file()
    assert not dest_desktop.is_file()
    assert not dest_icon.is_file()
    assert not dest_pixmap.is_file()


def test_cli_install_uninstall_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_paths = {
        "bin": tmp_path / "bin",
        "apps": tmp_path / "applications",
        "icons": tmp_path / "icons",
        "pixmaps": tmp_path / "pixmaps",
    }
    monkeypatch.setattr(installer, "_resolve_paths", lambda: test_paths)

    assert cli_main(["--install"]) == 0
    assert (test_paths["bin"] / "postermaker").is_file()

    assert cli_main(["--uninstall"]) == 0
    assert not (test_paths["bin"] / "postermaker").is_file()
