"""Operaciones de comprobación y actualización basadas en Git local."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .helpers import _parse_version


def check_git(git_root: Path, current_version: str) -> dict[str, Any] | None:
    """Comprueba cambios remotos usando Git local."""
    try:
        branch_proc = subprocess.run(
            ["git", "-C", str(git_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        branch = branch_proc.stdout.strip() or "main"

        # 1. Fetch ligero de rama y tags remotos
        subprocess.run(
            ["git", "-C", str(git_root), "fetch", "origin", "--tags", "--quiet"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )

        # 2. Comprobar si hay un tag superior a la versión actual del ejecutable
        tags_proc = subprocess.run(
            ["git", "-C", str(git_root), "tag", "-l", "v*"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        raw_tags = [t.strip().lstrip("v") for t in tags_proc.stdout.splitlines() if t.strip()]
        latest_git_tag = max(raw_tags, key=_parse_version) if raw_tags else None

        if latest_git_tag and _parse_version(latest_git_tag) > _parse_version(current_version):
            return {
                "status": "available",
                "has_update": True,
                "latest_version": latest_git_tag,
                "message": f"Nueva versión disponible: v{latest_git_tag}.",
            }

        # 3. Comprobar diferencias de commits en la rama actual
        try:
            local_hash = (
                subprocess.check_output(
                    ["git", "-C", str(git_root), "rev-parse", "HEAD"],
                    text=True,
                    timeout=2,
                ).strip()
            )
            remote_hash = (
                subprocess.check_output(
                    ["git", "-C", str(git_root), "rev-parse", f"origin/{branch}"],
                    text=True,
                    timeout=2,
                ).strip()
            )
            if local_hash != remote_hash:
                return {
                    "status": "available",
                    "has_update": True,
                    "latest_version": latest_git_tag or "nueva versión",
                    "message": "Nuevos cambios disponibles en el repositorio.",
                }
        except Exception:
            pass

        return {
            "status": "up_to_date",
            "has_update": False,
            "latest_version": current_version,
            "message": "PosterMaker está en su versión más reciente.",
        }
    except Exception:
        return None


def apply_git_update(git_root: Path) -> tuple[bool, str | None, str | None]:
    """
    Aplica la actualización desde el repositorio local.
    Retorna (success, error_message, detailed_error).
    """
    try:
        branch_proc = subprocess.run(
            ["git", "-C", str(git_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        branch = branch_proc.stdout.strip() or "main"

        pull_proc = subprocess.run(
            ["git", "-C", str(git_root), "pull", "origin", branch],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if pull_proc.returncode != 0:
            err = pull_proc.stderr.strip() or "Error al ejecutar git pull"
            return False, "No se pudieron fusionar los cambios de Git.", err

        installed_bin = Path.home() / ".local/bin/postermaker"
        dist_bin = git_root / "dist/postermaker"
        install_script = git_root / "scripts/install.sh"
        build_script = git_root / "scripts/build_standalone.sh"
        venv_py = git_root / ".venv/bin/python"

        # 1. Si no existe dist/postermaker pero sí build_standalone.sh y venv, compilar
        if venv_py.is_file() and build_script.is_file() and not dist_bin.is_file():
            try:
                subprocess.run(
                    [str(build_script)],
                    cwd=str(git_root),
                    capture_output=True,
                    timeout=90,
                    check=False,
                )
            except Exception:
                pass

        # 2. Si dist/postermaker existe, copiarlo al destino instalado
        if dist_bin.is_file() and installed_bin.parent.is_dir():
            try:
                shutil.copy2(dist_bin, installed_bin)
                installed_bin.chmod(0o755)
            except Exception:
                pass

        # 3. Ejecutar install.sh para actualizar accesos e icono
        if install_script.is_file():
            try:
                subprocess.run(
                    [str(install_script)],
                    cwd=str(git_root),
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
            except Exception:
                pass

        return True, None, None
    except Exception as exc:
        return False, "Error inesperado al aplicar actualización desde Git.", str(exc)
