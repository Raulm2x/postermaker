"""Punto de entrada unificado para CLI y Web."""

from __future__ import annotations

import sys
from pathlib import Path

# Si se ejecuta como script directo o empaquetado congelado (PyInstaller),
# __package__ es vacío y las importaciones relativas fallarían.
if not __package__:
    pkg_dir = Path(__file__).resolve().parent
    parent_dir = pkg_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    __package__ = "postermaker"

from postermaker.cli import main as cli_main
from postermaker.installer import install_desktop, uninstall_desktop
from postermaker.web import main as web_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    # Instalación / desinstalación de escritorio
    if any(a in ("--install", "install") for a in args):
        return install_desktop()

    if any(a in ("--uninstall", "uninstall") for a in args):
        return uninstall_desktop()

    # Si se invoca sin argumentos o se solicita la interfaz web:
    web_triggers = {"--web", "-w", "web", "--gui", "-g"}
    is_web = (
        not args
        or any(a in web_triggers for a in args)
        or ("--open" in args and not any(a in ("-o", "--output") for a in args))
    )

    if is_web:
        web_args = [a for a in args if a not in web_triggers]
        if "--open" not in web_args:
            web_args.append("--open")
        return web_main(web_args)

    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
