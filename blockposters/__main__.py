"""Compatibilidad hacia atrás: blockposters ahora es postermaker."""
from __future__ import annotations

from postermaker.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
