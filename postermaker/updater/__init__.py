"""Módulo de actualización automática para PosterMaker."""

from __future__ import annotations

from .constants import API_URL, GITHUB_REPO
from .helpers import _find_git_dir, _parse_version
from .manager import AutoUpdater

updater = AutoUpdater()

__all__ = [
    "API_URL",
    "AutoUpdater",
    "GITHUB_REPO",
    "_find_git_dir",
    "_parse_version",
    "updater",
]
