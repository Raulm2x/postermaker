"""Coordinador central del proceso de actualización automática."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from .. import __version__
from .git_backend import apply_git_update, check_git
from .github_backend import apply_github_update, check_github_release
from .helpers import _find_git_dir, _parse_version
from .service import schedule_service_restart


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

    def _check_git(self, git_root: Path) -> dict[str, Any]:
        state = check_git(git_root, self.current_version)
        if state:
            self._set_state(**state)
            return self.get_state()
        return self._check_github_release()

    def _check_github_release(self) -> dict[str, Any]:
        state = check_github_release(self.current_version)
        self._set_state(**state)
        return self.get_state()

    def check_updates(self) -> dict[str, Any]:
        """Comprueba si hay actualizaciones disponibles en GitHub Releases o Git."""
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

            # 1. Comprobar versiones oficiales en GitHub Releases y Tags
            gh_state = self._check_github_release()
            if gh_state.get("has_update"):
                return gh_state

            # 2. Si no hay release superior en GitHub, comprobar repositorio Git local
            git_root = _find_git_dir()
            if git_root:
                git_state = self._check_git(git_root)
                if git_state.get("has_update"):
                    return git_state

            return self.get_state()
        finally:
            with self._lock:
                self._in_progress = False

    def check_and_update(self, auto_apply: bool = False) -> dict[str, Any]:
        """Comprueba actualizaciones y opcionalmente las aplica si auto_apply=True."""
        state = self.check_updates()
        if auto_apply and state.get("has_update"):
            return self.apply_update()
        return state

    def _apply_git_update(self, git_root: Path) -> bool:
        success, msg, err = apply_git_update(git_root)
        if not success:
            self._set_state(
                status="error",
                error=err or "Error al actualizar desde Git",
                message=msg or "No se pudo actualizar.",
            )
        return success

    def _apply_github_update(self) -> bool:
        success, msg, err, needs_git = apply_github_update(self.latest_version)
        if success:
            return True
        if needs_git:
            git_root = _find_git_dir()
            if git_root:
                return self._apply_git_update(git_root)
        self._set_state(
            status="error",
            error=err or "Error al actualizar desde GitHub",
            message=msg or "No se pudo actualizar.",
        )
        return False

    def _schedule_service_restart(self) -> None:
        schedule_service_restart()

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

            success = False

            # 1. Intentar actualizar desde GitHub Releases si hay un asset descargable
            success = self._apply_github_update()

            # 2. Si no o si falló, aplicar cambios desde repositorio Git local si existe
            if not success:
                git_root = _find_git_dir()
                if git_root:
                    success = self._apply_git_update(git_root)

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
