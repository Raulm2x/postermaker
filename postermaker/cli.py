"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from .calibration import calibration_pdf
from .image import COLOR_MODES
from .paper import PAPERS, Margins
from .pipeline import generate_poster


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="postermaker",
        description=(
            "PosterMaker: Convierte una imagen en un póster imprimible dividido en varias hojas."
        ),
    )
    parser.add_argument("image", nargs="?", help="Imagen de entrada (JPG, PNG o WebP).")
    parser.add_argument(
        "-o",
        "--output",
        help="PDF de salida (por defecto: poster.pdf).",
    )
    parser.add_argument(
        "--pages-wide",
        type=int,
        default=None,
        help="Número de hojas de ancho (1-10, por defecto 3 si no se indica --pages-high).",
    )
    parser.add_argument(
        "--pages-high",
        type=int,
        default=None,
        help="Número de hojas de alto (1-10, alternativa a --pages-wide).",
    )
    parser.add_argument(
        "--paper",
        choices=sorted(PAPERS),
        default="letter",
        help="Tamaño de papel (a3, a4, a5, letter, legal, tabloid; por defecto letter).",
    )
    parser.add_argument(
        "--orientation",
        choices=("portrait", "landscape"),
        default="portrait",
        help="Orientación de las hojas (por defecto portrait).",
    )
    parser.add_argument(
        "--color",
        choices=COLOR_MODES,
        default="color",
        help="Modo de color (color, grayscale, monochrome; por defecto color).",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=10.0,
        metavar="MM",
        help="Margen blanco por lado en mm (por defecto 10).",
    )
    parser.add_argument("--margin-top", type=float, metavar="MM")
    parser.add_argument("--margin-right", type=float, metavar="MM")
    parser.add_argument("--margin-bottom", type=float, metavar="MM")
    parser.add_argument("--margin-left", type=float, metavar="MM")
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.0,
        metavar="MM",
        help="Solapamiento entre hojas para recortar y pegar (por defecto 0).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolución de salida en ppp (72-600, por defecto 300).",
    )
    parser.add_argument(
        "--marks",
        action="store_true",
        help="Añadir marcas de corte en los márgenes.",
    )
    parser.add_argument(
        "--labels",
        action="store_true",
        help="Numerar las hojas en el margen inferior.",
    )
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Incluir hoja con plano de montaje e instrucciones.",
    )
    parser.add_argument(
        "--tiles",
        metavar="DIR",
        help="Guardar también cada hoja como JPEG en esta carpeta.",
    )
    parser.add_argument(
        "--zip",
        metavar="ARCHIVO.zip",
        help="Guardar las hojas de corte comprimidas en un archivo ZIP.",
    )
    parser.add_argument(
        "--preview",
        metavar="PNG",
        help="Guardar una vista previa con las líneas de corte.",
    )
    parser.add_argument(
        "--calibration",
        choices=sorted(PAPERS),
        metavar="PAPEL",
        help="Generar una hoja de calibración para el papel indicado y salir.",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Instalar en el sistema (ejecutable, icono y acceso .desktop).",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Desinstalar del sistema eliminando acceso .desktop e icono.",
    )
    return parser


def _margins(args: argparse.Namespace) -> Margins:
    return Margins(
        top=args.margin if args.margin_top is None else args.margin_top,
        right=args.margin if args.margin_right is None else args.margin_right,
        bottom=args.margin if args.margin_bottom is None else args.margin_bottom,
        left=args.margin if args.margin_left is None else args.margin_left,
    )


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.install:
        from .installer import install_desktop
        return install_desktop()

    if args.uninstall:
        from .installer import uninstall_desktop
        return uninstall_desktop()

    if args.calibration:
        output = Path(args.output or f"calibracion-{args.calibration}.pdf")
        try:
            output.write_bytes(calibration_pdf(args.calibration))
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        print(f"Hoja de calibración: {output.resolve()} ({_human_size(output.stat().st_size)})")
        return 0

    if not args.image:
        parser.error("indica una imagen o usa --calibration")

    output = Path(args.output or "poster.pdf")
    tiles = Path(args.tiles) if args.tiles else None
    zip_path = Path(args.zip) if args.zip else None
    preview = Path(args.preview) if args.preview else None

    pages_wide = args.pages_wide
    pages_high = args.pages_high
    if pages_wide is None and pages_high is None:
        pages_wide = 3

    # Si se pide ZIP pero no tiles, usamos una carpeta temporal para los azulejos
    import tempfile
    temp_tiles_ctx = None
    if zip_path and not tiles:
        temp_tiles_ctx = tempfile.TemporaryDirectory(prefix="postermaker-cli-zip-")
        effective_tiles_dir = Path(temp_tiles_ctx.name)
    else:
        effective_tiles_dir = tiles

    try:
        result = generate_poster(
            args.image,
            output,
            pages_wide=pages_wide,
            pages_high=pages_high,
            paper=args.paper,
            orientation=args.orientation,
            margins=_margins(args),
            dpi=args.dpi,
            overlap_mm=args.overlap,
            marks=args.marks,
            labels=args.labels,
            color_mode=args.color,
            assembly_guide=args.guide,
            tiles_dir=effective_tiles_dir,
            preview_path=preview,
        )

        if zip_path:
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in result.page_paths:
                    zf.write(p, arcname=p.name)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if temp_tiles_ctx is not None:
            temp_tiles_ctx.cleanup()

    grid = result.grid
    print(f"Póster: {grid.poster_width_cm:.1f} × {grid.poster_height_cm:.1f} cm")
    print(
        f"Hojas: {grid.pages_wide} × {grid.pages_high} = "
        f"{grid.total_pages} ({grid.paper.name}, {grid.page_label})"
    )
    print(
        f"Resolución efectiva: {result.effective_dpi:.0f} ppp "
        f"(salida a {result.render_dpi:.0f} ppp)"
    )
    if result.effective_dpi < 150:
        print(
            "Aviso: la imagen tiene poca resolución para este tamaño; "
            "el póster puede verse pixelado.",
            file=sys.stderr,
        )
    size = result.pdf_path.stat().st_size
    print(f"PDF: {result.pdf_path.resolve()} ({_human_size(size)})")
    if tiles:
        print(f"Hojas sueltas: {tiles.resolve()}")
    if zip_path:
        print(f"Archivo ZIP: {zip_path.resolve()} ({_human_size(zip_path.stat().st_size)})")
    if preview:
        print(f"Vista previa: {preview.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
