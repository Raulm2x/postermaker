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
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from . import __version__

GITHUB_REPO = "Raulm2x/postermaker"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _find_git_dir() -> Path | None:
    """Busca el directorio raíz de Git del proyecto si existe."""
    # 1. Variable de entorno explícita
    for var in ("POSTERMAKER_REPO_DIR", "BLOCKPOSTERS_REPO_DIR"):
        env_dir = os.environ.get(var)
        if env_dir and (Path(env_dir) / ".git").is_dir():
            return Path(env_dir).resolve()

    # 2. Archivo persistido de configuración ~/.config/postermaker/repo_path
    for app_name in ("postermaker", "blockposters"):
        cfg_path = Path.home() / f".config/{app_name}/repo_path"
        if cfg_path.is_file():
            try:
                candidate = Path(cfg_path.read_text(encoding="utf-8").strip())
                if (candidate / ".git").is_dir():
                    return candidate.resolve()
            except Exception:
                pass

    # 3. Directorio superior del código fuente (cuando no está empaquetado en PyInstaller)
    if not (getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")):
        try:
            source_root = Path(__file__).resolve().parent.parent
            if (source_root / ".git").is_dir():
                return source_root.resolve()
        except Exception:
            pass

    # 4. Directorio de trabajo actual
    try:
        cwd = Path.cwd().resolve()
        if (cwd / ".git").is_dir():
            return cwd
    except Exception:
        pass

    # 5. Directorios comunes en el $HOME del usuario
    home = Path.home()
    for rel_path in (
        "Projects/posters",
        "Projects/postermaker",
        "Projects/blockposters",
        "postermaker",
        "blockposters",
        "src/postermaker",
        "source/postermaker",
    ):
        cand = (home / rel_path).resolve()
        if (cand / ".git").is_dir():
            return cand

    return None


class AutoUpdater:
    """Gestiona la comprobación y aplicación de actualizaciones desde Git o GitHub."""

    def __init__(self) -> None:
        self.status: str = "idle"  # idle, checking, available, updating, updated, up_to_date, error
        self.message: str = "Listo"
        self.current_version: str = __version__
        self.latest_version: str = __version__
        self.has_update: bool = False
        self.error: str | None = None
        self._lock = threading.Lock()
        self._in_progress = False

        # Persistir la ruta del repositorio si se encuentra para futuros arranques
        git_root = _find_git_dir()
        if git_root:
            try:
                cfg_dir = Path.home() / ".config/postermaker"
                cfg_dir.mkdir(parents=True, exist_ok=True)
                (cfg_dir / "repo_path").write_text(str(git_root), encoding="utf-8")
            except Exception:
                pass

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

    def check_updates(self) -> dict[str, Any]:
        """Comprueba si hay actualizaciones disponibles en Git o GitHub."""
        with self._lock:
            if self._in_progress:
                return self.get_state()
            self._in_progress = True

        try:
            self._set_state(
                status="checking",
                message="Buscando actualizaciones...",
                error=None,
            )

            git_root = _find_git_dir()
            if git_root:
                return self._check_git(git_root)
            else:
                return self._check_github_release()
        finally:
            with self._lock:
                self._in_progress = False

    def check_and_update(self, auto_apply: bool = False) -> dict[str, Any]:
        """Comprueba actualizaciones y opcionalmente las aplica si auto_apply=True."""
        state = self.check_updates()
        if auto_apply and state.get("has_update"):
            return self.apply_update()
        return state

    def _check_git(self, git_root: Path) -> dict[str, Any]:
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

            fetch_proc = subprocess.run(
                ["git", "-C", str(git_root), "fetch", "origin", branch, "--quiet"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if fetch_proc.returncode != 0:
                self._set_state(
                    status="up_to_date",
                    message="Modo sin conexión o sin acceso a remoto.",
                )
                return self.get_state()

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
                tag_proc = subprocess.run(
                    ["git", "-C", str(git_root), "describe", "--tags", f"origin/{branch}"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                latest_tag = tag_proc.stdout.strip().lstrip("v") or "nueva versión"
                self._set_state(
                    status="available",
                    has_update=True,
                    latest_version=latest_tag,
                    message=f"Nueva versión disponible: {latest_tag}.",
                )
            else:
                self._set_state(
                    status="up_to_date",
                    has_update=False,
                    latest_version=self.current_version,
                    message="PosterMaker está en su versión más reciente.",
                )
        except Exception as exc:
            self._set_state(
                status="up_to_date",
                message="PosterMaker listo (comprobación remota omitida).",
                error=str(exc),
            )
        return self.get_state()

    def _check_github_release(self) -> dict[str, Any]:
        """Comprueba versión disponible desde GitHub Releases o Tags."""
        try:
            req = urllib.request.Request(
                API_URL,
                headers={"User-Agent": "PosterMaker-AutoUpdater", "Accept": "application/vnd.github.v3+json"},
            )
            tag = None
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        tag = data.get("tag_name", "").lstrip("v")
            except urllib.error.HTTPError as http_err:
                if http_err.code == 404:
                    tags_url = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
                    tags_req = urllib.request.Request(
                        tags_url,
                        headers={"User-Agent": "PosterMaker-AutoUpdater", "Accept": "application/vnd.github.v3+json"},
                    )
                    with urllib.request.urlopen(tags_req, timeout=5) as tags_resp:
                        if tags_resp.status == 200:
                            tags_data = json.loads(tags_resp.read().decode("utf-8"))
                            if tags_data and isinstance(tags_data, list):
                                tag = tags_data[0].get("name", "").lstrip("v")
                else:
                    raise

            if tag and tag != self.current_version:
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
                    latest_version=self.current_version,
                    message="PosterMaker está en su versión más reciente.",
                )
        except Exception as exc:
            self._set_state(
                status="up_to_date",
                message="PosterMaker listo (modo local/sin conexión).",
                error=str(exc),
            )
        return self.get_state()

    def apply_update(self) -> dict[str, Any]:
        """Aplica la actualización disponible descargando/fusionando cambios y reinstalando el binario."""
        with self._lock:
            if self._in_progress:
                return self.get_state()
            self._in_progress = True

        try:
            self._set_state(
                status="updating",
                message="Instalando la actualización...",
                error=None,
            )

            git_root = _find_git_dir()
            success = False

            if git_root:
                success = self._apply_git_update(git_root)
            else:
                success = self._apply_github_update()

            if success:
                self._set_state(
                    status="updated",
                    has_update=False,
                    current_version=self.latest_version,
                    message="¡PosterMaker se ha actualizado correctamente!",
                )
                self._schedule_service_restart()
            else:
                if self.status != "error":
                    self._set_state(
                        status="error",
                        error="No se pudo aplicar la actualización.",
                        message="Ocurrió un error al actualizar los archivos.",
                    )
        finally:
            with self._lock:
                self._in_progress = False

        return self.get_state()

    def _apply_git_update(self, git_root: Path) -> bool:
        """Aplica la actualización desde el repositorio local."""
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
                self._set_state(
                    status="error",
                    error=pull_proc.stderr.strip() or "Error al ejecutar git pull",
                    message="No se pudieron fusionar los cambios de Git.",
                )
                return False

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

            return True
        except Exception as exc:
            self._set_state(
                status="error",
                error=str(exc),
                message="Error inesperado al aplicar actualización desde Git.",
            )
            return False

    def _apply_github_update(self) -> bool:
        """Descarga e instala la actualización desde GitHub Releases."""
        try:
            req = urllib.request.Request(
                API_URL,
                headers={"User-Agent": "PosterMaker-AutoUpdater", "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status != 200:
                    return False
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

            installed_bin = Path.home() / ".local/bin/postermaker"
            installed_bin.parent.mkdir(parents=True, exist_ok=True)

            if download_url:
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
                            return False
                    else:
                        shutil.copy2(tmp_file, installed_bin)

                    installed_bin.chmod(0o755)
                    return True
            else:
                # Si no hay asset binario en GitHub Releases, comprobar si existe repo local
                git_root = _find_git_dir()
                if git_root:
                    return self._apply_git_update(git_root)

                self._set_state(
                    status="error",
                    error="No hay binarios precompilados en la release de GitHub.",
                    message=f"La release v{self.latest_version} no incluye binario descargable.",
                )
                return False
        except Exception as exc:
            self._set_state(
                status="error",
                error=str(exc),
                message="Error al descargar o instalar la actualización.",
            )
            return False

    def _schedule_service_restart(self) -> None:
        """Reinicia el servicio systemd de usuario en segundo plano tras una breve pausa."""
        def _restart_worker():
            time.sleep(1.2)
            if shutil.which("systemctl"):
                try:
                    subprocess.run(
                        ["systemctl", "--user", "restart", "postermaker.service"],
                        capture_output=True,
                        check=False,
                    )
                except Exception:
                    pass

        threading.Thread(target=_restart_worker, daemon=True).start()


updater = AutoUpdater()
