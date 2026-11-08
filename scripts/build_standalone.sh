#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Creando binario portátil de PosterMaker para Linux ==="

# Usar el python del entorno virtual o el del sistema
PYTHON_BIN=".venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

# Comprobar que las dependencias de la aplicación están disponibles
check_deps() {
    "$PYTHON_BIN" -c "import flask, PIL, img2pdf" &>/dev/null
}

# Instalar las dependencias del proyecto si faltan (respeta pyproject.toml)
if ! check_deps; then
    echo "Instalando dependencias del proyecto..."
    if command -v uv &>/dev/null; then
        uv pip install --python "$PYTHON_BIN" -e .
    else
        "$PYTHON_BIN" -m pip install -e .
    fi
fi

# Verificación de seguridad: sin estas dependencias el binario no arrancaría
if ! check_deps; then
    echo "ERROR: faltan dependencias de la aplicación (flask, PIL o img2pdf)." >&2
    echo "Instálalas con: $PYTHON_BIN -m pip install -e ." >&2
    exit 1
fi

# Instalar PyInstaller si no está presente
if ! "$PYTHON_BIN" -c "import PyInstaller" &>/dev/null; then
    echo "Instalando PyInstaller..."
    if command -v uv &>/dev/null; then
        uv pip install --python "$PYTHON_BIN" pyinstaller
    else
        "$PYTHON_BIN" -m pip install pyinstaller
    fi
fi

echo "Compilando con PyInstaller (spec: postermaker.spec)..."
"$PYTHON_BIN" -m PyInstaller --clean postermaker.spec

# Prueba de humo: el binario debe arrancar con todas sus dependencias empaquetadas
echo "Verificando que el binario arranca..."
if ! ./dist/postermaker --help &>/dev/null; then
    echo "ERROR: dist/postermaker no arranca correctamente." >&2
    echo "Puede que falten dependencias en el paquete; ejecuta ./dist/postermaker --help para ver el error." >&2
    exit 1
fi

echo "Preparando paquete de distribución con acceso .desktop e icono..."
cp -f postermaker.desktop dist/
cp -f postermaker.svg dist/
cp -f scripts/install.sh dist/
cp -f scripts/uninstall.sh dist/

# Empaquetar tar.gz listo para distribuir
TAR_NAME="postermaker-linux-x86_64.tar.gz"
tar -czf "dist/$TAR_NAME" -C dist \
    postermaker \
    postermaker.desktop \
    postermaker.svg \
    install.sh \
    uninstall.sh

echo ""
echo "=== ¡Listo! ==="
echo "1. Ejecutable autónomo:  dist/postermaker"
echo "2. Acceso de escritorio: dist/postermaker.desktop"
echo "3. Icono de la app:      dist/postermaker.svg"
echo "4. Script de instalación: dist/install.sh"
echo "5. Paquete completo:     dist/$TAR_NAME"
echo ""
ls -lh dist/postermaker "dist/$TAR_NAME"
echo ""
echo "Instalación en cualquier distribución Linux:"
echo "  cd dist && ./install.sh           # Instala para el usuario actual"
echo "  o bien:"
echo "  ./dist/postermaker --install      # El propio ejecutable se auto-instala"
echo ""
echo "Para desinstalar en cualquier momento:"
echo "  ./dist/postermaker --uninstall"
