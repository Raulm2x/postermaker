"""Operaciones de comprobación y descarga desde GitHub Releases."""

from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from .constants import API_URL, GITHUB_REPO
from .helpers import _parse_version


def check_github_release(current_version: str) -> dict[str, Any]:
    """Comprueba versión disponible desde GitHub Releases o Tags."""
    try:
        tags_found: list[str] = []

        # 1. Comprobar releases/latest
        try:
            req = urllib.request.Request(
                API_URL,
                headers={"User-Agent": "PosterMaker-AutoUpdater", "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    t = data.get("tag_name", "").lstrip("v")
                    if t:
                        tags_found.append(t)
        except Exception:
            pass

        # 2. Comprobar tags de GitHub
        try:
            tags_url = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
            tags_req = urllib.request.Request(
                tags_url,
                headers={"User-Agent": "PosterMaker-AutoUpdater", "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(tags_req, timeout=5) as tags_resp:
                if tags_resp.status == 200:
                    tags_data = json.loads(tags_resp.read().decode("utf-8"))
                    if tags_data and isinstance(tags_data, list):
                        for item in tags_data[:5]:
                            t = item.get("name", "").lstrip("v")
                            if t:
                                tags_found.append(t)
        except Exception:
            pass

        if tags_found:
            best_tag = max(tags_found, key=_parse_version)
            if _parse_version(best_tag) > _parse_version(current_version):
                return {
                    "status": "available",
                    "has_update": True,
                    "latest_version": best_tag,
                    "message": f"Nueva versión disponible: v{best_tag}.",
                }

        return {
            "status": "up_to_date",
            "has_update": False,
            "latest_version": current_version,
            "message": "PosterMaker está en su versión más reciente.",
        }
    except Exception as exc:
        return {
            "status": "up_to_date",
            "has_update": False,
            "latest_version": current_version,
            "message": "PosterMaker listo (modo local/sin conexión).",
            "error": str(exc),
        }


def apply_github_update(latest_version: str) -> tuple[bool, str | None, str | None, bool]:
    """
    Descarga e instala la actualización desde GitHub Releases.
    Retorna (success, error_message, detailed_error, needs_git_fallback).
    """
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "PosterMaker-AutoUpdater", "Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                return False, "Error al consultar la release de GitHub.", None, True
            release_data = json.loads(resp.read().decode("utf-8"))

        assets = release_data.get("assets", [])
        download_url = None
        is_archive = False

        for asset in assets:
            name = asset.get("name", "").lower()
            if "postermaker" in name:
                download_url = asset.get("browser_download_url")
                if name.endswith((".tar.gz", ".tgz", ".zip")):
                    is_archive = True
                break

        if not download_url:
            return False, f"La release v{latest_version} no incluye binario descargable.", "No hay binarios precompilados en la release de GitHub.", True

        installed_bin = Path.home() / ".local/bin/postermaker"
        installed_bin.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = Path(tmp_dir) / "downloaded_asset"
            urllib.request.urlretrieve(download_url, tmp_file)

            if is_archive:
                if tarfile.is_tarfile(tmp_file):
                    with tarfile.open(tmp_file) as tf:
                        tf.extractall(tmp_dir)
                elif zipfile.is_zipfile(tmp_file):
                    with zipfile.ZipFile(tmp_file) as zf:
                        zf.extractall(tmp_dir)

                extracted_bin = None
                for p in Path(tmp_dir).rglob("postermaker"):
                    if p.is_file() and p != tmp_file:
                        extracted_bin = p
                        break
                if extracted_bin:
                    shutil.copy2(extracted_bin, installed_bin)
                else:
                    return False, "No se encontró el ejecutable en el archivo descargado.", None, False
            else:
                shutil.copy2(tmp_file, installed_bin)

            installed_bin.chmod(0o755)
            return True, None, None, False
    except Exception as exc:
        return False, "Error al descargar o instalar la actualización.", str(exc), False
