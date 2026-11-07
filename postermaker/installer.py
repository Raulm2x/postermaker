"""Instalador y desinstalador de escritorio para cualquier distribución Linux."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_paths() -> dict[str, Path]:
    is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False
    if is_root:
        bin_dir = Path("/usr/local/bin")
        apps_dir = Path("/usr/local/share/applications")
        icons_dir = Path("/usr/local/share/icons/hicolor/scalable/apps")
        pixmaps_dir = Path("/usr/share/pixmaps")
    else:
        home = Path.home()
        bin_dir = home / ".local/bin"
        apps_dir = home / ".local/share/applications"
        icons_dir = home / ".local/share/icons/hicolor/scalable/apps"
        pixmaps_dir = home / ".local/share/pixmaps"

    return {
        "bin": bin_dir,
        "apps": apps_dir,
        "icons": icons_dir,
        "pixmaps": pixmaps_dir,
    }


def _get_icon_bytes() -> bytes:
    """Busca el SVG del icono en la instalación congelada o en el código fuente."""

    # 1. Empaquetado congelado en sys._MEIPASS
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        for cand in (
            Path(sys._MEIPASS) / "postermaker/static/favicon.svg",
            Path(sys._MEIPASS) / "blockposters/static/favicon.svg",
            Path(sys._MEIPASS) / "static/favicon.svg",
            Path(sys._MEIPASS) / "postermaker.svg",
            Path(sys._MEIPASS) / "blockposters.svg",
        ):
            if cand.is_file():
                return cand.read_bytes()

    # 2. Junto al ejecutable
    exe_dir = Path(sys.executable).resolve().parent
    for cand in (
        exe_dir / "postermaker.svg",
        exe_dir / "blockposters.svg",
        exe_dir / "favicon.svg",
    ):
        if cand.is_file():
            return cand.read_bytes()

    # 3. Código fuente del proyecto
    pkg_dir = Path(__file__).resolve().parent
    for cand in (
        pkg_dir.parent / "postermaker.svg",
        pkg_dir.parent / "blockposters.svg",
        pkg_dir / "static/favicon.svg",
    ):
        if cand.is_file():
            return cand.read_bytes()

    # Fallback embebido mínimo
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        b'<rect width="64" height="64" rx="14" fill="#fffdf8"/>'
        b'<rect x="13" y="13" width="16" height="16" rx="2" fill="#17211f"/>'
        b'<rect x="35" y="13" width="16" height="16" rx="2" fill="#e4572e"/>'
        b'<rect x="13" y="35" width="16" height="16" rx="2" fill="#e4572e"/>'
        b'<rect x="35" y="35" width="16" height="16" rx="2" fill="#17211f"/>'
        b"</svg>"
    )


def install_desktop() -> int:
    """Instala el binario, el icono SVG y el archivo .desktop de PosterMaker en el sistema."""

    paths = _resolve_paths()
    bin_dir = paths["bin"]
    apps_dir = paths["apps"]
    icons_dir = paths["icons"]
    pixmaps_dir = paths["pixmaps"]

    for d in (bin_dir, apps_dir, icons_dir, pixmaps_dir):
        d.mkdir(parents=True, exist_ok=True)

    dest_bin = bin_dir / "postermaker"
    alias_bin = bin_dir / "blockposters"

    # 1. Instalar binario o wrapper
    if getattr(sys, "frozen", False):
        current_exe = Path(sys.executable).resolve()
        if current_exe != dest_bin.resolve():
            if dest_bin.is_file() or dest_bin.is_symlink():
                try:
                    dest_bin.unlink()
                except OSError:
                    pass
            shutil.copy2(current_exe, dest_bin)
    else:
        # Wrapper bash para ejecutar el módulo de Python actual
        py_bin = sys.executable
        wrapper = (
            "#!/bin/sh\n"
            f'exec "{py_bin}" -m postermaker "$@"\n'
        )
        dest_bin.write_text(wrapper, encoding="utf-8")

    dest_bin.chmod(0o755)

    # Crear enlace simbólico de compatibilidad para blockposters
    try:
        if alias_bin.is_symlink() or alias_bin.is_file():
            alias_bin.unlink()
        alias_bin.symlink_to(dest_bin.name)
    except Exception:
        pass

    # 2. Instalar icono en hicolor y pixmaps
    icon_data = _get_icon_bytes()
    (icons_dir / "postermaker.svg").write_bytes(icon_data)
    (pixmaps_dir / "postermaker.svg").write_bytes(icon_data)

    # 3. Instalar archivo .desktop
    desktop_content = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Application\n"
        "Name=PosterMaker\n"
        "GenericName=Pósteres Imprimibles\n"
        "Comment=Convierte imágenes en pósteres imprimibles divididos en hojas\n"
        f'Exec="{dest_bin}" --web --open\n'
        "Icon=postermaker\n"
        "Terminal=false\n"
        "Categories=Graphics;Publishing;\n"
        "Keywords=poster;print;mural;postermaker;pdf;\n"
        "StartupNotify=false\n"
    )
    dest_desktop = apps_dir / "postermaker.desktop"
    dest_desktop.write_text(desktop_content, encoding="utf-8")
    dest_desktop.chmod(0o644)

    # Limpiar el viejo lanzador blockposters.desktop si existía
    old_desktop = apps_dir / "blockposters.desktop"
    if old_desktop.is_file():
        try:
            old_desktop.unlink()
        except OSError:
            pass

    # 4. Actualizar bases de datos de escritorio de Linux
    try:
        subprocess.run(["update-desktop-database", str(apps_dir)], capture_output=True, check=False)
    except Exception:
        pass

    try:
        theme_dir = icons_dir.parents[2]
        subprocess.run(["gtk-update-icon-cache", "-q", "-t", str(theme_dir)], capture_output=True, check=False)
    except Exception:
        pass

    print("=== Instalación de PosterMaker completada con éxito ===")
    print(f"Ejecutable: {dest_bin}")
    print(f"Acceso directo: {dest_desktop}")
    print(f"Icono: {icons_dir / 'postermaker.svg'}")
    print("")
    print("Ya puedes abrir 'PosterMaker' desde tu lanzador de aplicaciones")
    print("o ejecutar 'postermaker' en tu terminal.")

    # Advertencia si ~/.local/bin no está en PATH
    path_env = os.environ.get("PATH", "").split(os.pathsep)
    if str(bin_dir) not in path_env and not (os.geteuid() == 0 if hasattr(os, "geteuid") else False):
        print("")
        print(f"Nota: Recuerda asegurarte de que '{bin_dir}' esté en tu variable $PATH:")
        print(f'  export PATH="{bin_dir}:$PATH"')

    return 0


def uninstall_desktop() -> int:
    """Elimina el binario, el icono y el archivo .desktop del sistema."""

    paths = _resolve_paths()
    removed = []

    targets = [
        paths["bin"] / "postermaker",
        paths["bin"] / "blockposters",
        paths["apps"] / "postermaker.desktop",
        paths["apps"] / "blockposters.desktop",
        paths["icons"] / "postermaker.svg",
        paths["icons"] / "blockposters.svg",
        paths["pixmaps"] / "postermaker.svg",
        paths["pixmaps"] / "blockposters.svg",
    ]

    for target in targets:
        if target.is_file() or target.is_symlink():
            try:
                target.unlink()
                removed.append(str(target))
            except OSError as exc:
                print(f"No se pudo eliminar {target}: {exc}", file=sys.stderr)

    try:
        subprocess.run(["update-desktop-database", str(paths["apps"])], capture_output=True, check=False)
    except Exception:
        pass

    if removed:
        print("=== Desinstalación completada ===")
        print("Se han eliminado los siguientes elementos:")
        for r in removed:
            print(f"  - {r}")
    else:
        print("No se encontraron archivos de PosterMaker instalados en las rutas estándar.")

    return 0
