"""Módulo de actualización automática para PosterMaker."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__

GITHUB_REPO = "Raulm2x/postermaker"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _find_git_dir() -> Path | None:
    """Busca el directorio raíz de Git del proyecto si existe."""
    # 1. Variable de entorno explícita
    env_dir = os.environ.get("POSTERMAKER_REPO_DIR")
    if env_dir and (Path(env_dir) / ".git").is_dir():
        return Path(env_dir)

    # 2. Directorio superior del código fuente
    try:
        source_root = Path(__file__).resolve().parent.parent
        if (source_root / ".git").is_dir():
            return source_root
    except Exception:
        pass

    # 3. Directorio de trabajo actual
    cwd = Path.cwd()
    if (cwd / ".git").is_dir():
        return cwd

    return None


class AutoUpdater:
    """Gestiona la comprobación y aplicación de actualizaciones desde Git o GitHub."""

    def __init__(self) -> None:
        self.status: str = "idle"  # idle, checking, updating, updated, up_to_date, error
        self.message: str = "Comprobando..."
        self.current_version: str = __version__
        self.latest_version: str = __version__
        self.has_update: bool = False
        self.error: str | None = None
        self._lock = threading.Lock()
        self._in_progress = False

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "message": self.message,
                "current_version": self.current_version,
                "latest_version": self.latest_version,
                "has_update": self.has_update,
                "error": self.error,
            }

    def _set_state(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def check_and_update(self) -> dict[str, Any]:
        """Comprueba si hay actualizaciones y las aplica si están disponibles."""
        with self._lock:
            if self._in_progress:
                return self.get_state()
            self._in_progress = True

        try:
            git_root = _find_git_dir()
            if git_root:
                return self._update_from_git(git_root)
            else:
                return self._update_from_github_release()
        finally:
            with self._lock:
                self._in_progress = False

    def _update_from_git(self, git_root: Path) -> dict[str, Any]:
        """Comprueba y aplica cambios utilizando Git local."""
        self._set_state(
            status="checking",
            message="Comprobando cambios en el repositorio de GitHub...",
            error=None,
        )

        try:
            # Obtener rama actual
            branch_proc = subprocess.run(
                ["git", "-C", str(git_root), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            branch = branch_proc.stdout.strip() or "main"

            # Fetch ligero al remoto (timeout estricto para no bloquear en offline)
            fetch_proc = subprocess.run(
                ["git", "-C", str(git_root), "fetch", "origin", branch, "--quiet"],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
            )
            if fetch_proc.returncode != 0:
                self._set_state(
                    status="up_to_date",
                    message="Modo sin conexión o sin acceso a remoto.",
                )
                return self.get_state()

            # Comparar hashes locales y remotos
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
                self._set_state(
                    status="updating",
                    has_update=True,
                    message="Nuevos cambios detectados en el repositorio. Actualizando...",
                )

                # Realizar pull con avance rápido
                pull_proc = subprocess.run(
                    ["git", "-C", str(git_root), "pull", "--ff-only", "origin", branch],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )

                if pull_proc.returncode == 0:
                    # Si existe script de instalación local, actualizar los archivos instalados
                    install_script = git_root / "scripts/install.sh"
                    if install_script.is_file():
                        try:
                            subprocess.run([str(install_script)], capture_output=True, timeout=10, check=False)
                        except Exception:
                            pass

                    self._set_state(
                        status="updated",
                        has_update=True,
                        message="¡PosterMaker se ha actualizado a la última versión del repositorio!",
                    )
                else:
                    self._set_state(
                        status="error",
                        error=pull_proc.stderr.strip() or "Error al ejecutar git pull",
                        message="No se pudieron fusionar automáticamente los cambios.",
                    )
            else:
                self._set_state(
                    status="up_to_date",
                    has_update=False,
                    message="PosterMaker está al día con el repositorio.",
                )

        except (subprocess.TimeoutExpired, OSError, Exception) as exc:
            self._set_state(
                status="up_to_date",
                message="PosterMaker listo (comprobación remota omitida).",
                error=str(exc),
            )

        return self.get_state()

    def _update_from_github_release(self) -> dict[str, Any]:
        """Comprueba actualizaciones a través de la API pública de GitHub Releases."""
        self._set_state(
            status="checking",
            message="Comprobando versión en GitHub...",
            error=None,
        )

        try:
            req = urllib.request.Request(
                API_URL,
                headers={"User-Agent": "PosterMaker-AutoUpdater", "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    tag = data.get("tag_name", "").lstrip("v")
                    if tag and tag != __version__:
                        self._set_state(
                            status="available",
                            has_update=True,
                            latest_version=tag,
                            message=f"Nueva versión disponible: v{tag}.",
                        )
                    else:
                        self._set_state(
                            status="up_to_date",
                            has_update=False,
                            message="PosterMaker está en su versión más reciente.",
                        )
                else:
                    self._set_state(status="up_to_date", message="PosterMaker al día.")

        except Exception as exc:
            self._set_state(
                status="up_to_date",
                message="PosterMaker listo (modo local/sin conexión).",
                error=str(exc),
            )

        return self.get_state()


updater = AutoUpdater()
