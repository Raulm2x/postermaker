"""Punto de entrada para ejecución directa: python -m postermaker.web"""

from __future__ import annotations

from .server import main

if __name__ == "__main__":
    raise SystemExit(main())
