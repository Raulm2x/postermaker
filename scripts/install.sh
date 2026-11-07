#!/bin/sh
# Instalador de Block Posters para cualquier distribución de Linux.
# Compatible con POSIX sh (funciona en bash, zsh, dash, ash, etc.).

set -e

# Detectar si se ejecuta como root (sudo) o usuario normal
if [ "$(id -u)" -eq 0 ]; then
    BIN_DIR="/usr/local/bin"
    APPS_DIR="/usr/local/share/applications"
    ICONS_DIR="/usr/local/share/icons/hicolor/scalable/apps"
    PIXMAPS_DIR="/usr/share/pixmaps"
else
    BIN_DIR="$HOME/.local/bin"
    APPS_DIR="$HOME/.local/share/applications"
    ICONS_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
    PIXMAPS_DIR="$HOME/.local/share/pixmaps"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PARENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Buscar el ejecutable postermaker (standalone binario o en dist/)
SRC_BIN=""
if [ -f "$SCRIPT_DIR/postermaker" ]; then
    SRC_BIN="$SCRIPT_DIR/postermaker"
elif [ -f "$PARENT_DIR/dist/postermaker" ]; then
    SRC_BIN="$PARENT_DIR/dist/postermaker"
elif [ -f "$PARENT_DIR/postermaker" ]; then
    SRC_BIN="$PARENT_DIR/postermaker"
elif [ -f "$PARENT_DIR/dist/blockposters" ]; then
    SRC_BIN="$PARENT_DIR/dist/blockposters"
fi

# Buscar el icono SVG
SRC_ICON=""
if [ -f "$SCRIPT_DIR/postermaker.svg" ]; then
    SRC_ICON="$SCRIPT_DIR/postermaker.svg"
elif [ -f "$PARENT_DIR/postermaker.svg" ]; then
    SRC_ICON="$PARENT_DIR/postermaker.svg"
elif [ -f "$PARENT_DIR/postermaker/static/favicon.svg" ]; then
    SRC_ICON="$PARENT_DIR/postermaker/static/favicon.svg"
elif [ -f "$PARENT_DIR/blockposters.svg" ]; then
    SRC_ICON="$PARENT_DIR/blockposters.svg"
fi

# Crear directorios de destino
mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICONS_DIR" "$PIXMAPS_DIR"

# 1. Instalar binario o wrapper
DEST_BIN="$BIN_DIR/postermaker"
ALIAS_BIN="$BIN_DIR/blockposters"
if [ -n "$SRC_BIN" ]; then
    rm -f "$DEST_BIN" 2>/dev/null || true
    cp -f "$SRC_BIN" "$DEST_BIN"
    chmod 755 "$DEST_BIN"
    echo "-> Binario instalado en: $DEST_BIN"
else
    # Si no hay binario compilado, usar python del sistema o .venv
    PY_BIN="python3"
    if [ -f "$PARENT_DIR/.venv/bin/python" ]; then
        PY_BIN="$PARENT_DIR/.venv/bin/python"
    fi
    cat <<EOF > "$DEST_BIN"
#!/bin/sh
exec "$PY_BIN" -m postermaker "\$@"
EOF
    chmod 755 "$DEST_BIN"
    echo "-> Lanzador wrapper instalado en: $DEST_BIN"
fi

# Enlace simbólico de compatibilidad para comandos anteriores
ln -sf "postermaker" "$ALIAS_BIN" 2>/dev/null || true

# 2. Instalar icono
if [ -n "$SRC_ICON" ]; then
    cp -f "$SRC_ICON" "$ICONS_DIR/postermaker.svg"
    cp -f "$SRC_ICON" "$PIXMAPS_DIR/postermaker.svg"
    echo "-> Icono instalado en: $ICONS_DIR/postermaker.svg"
fi

# 3. Instalar acceso de escritorio .desktop
DEST_DESKTOP="$APPS_DIR/postermaker.desktop"
cat <<EOF > "$DEST_DESKTOP"
[Desktop Entry]
Version=1.0
Type=Application
Name=PosterMaker
GenericName=Pósteres Imprimibles
Comment=Convierte imágenes en pósteres imprimibles divididos en hojas
Exec="$DEST_BIN" --web --open
Icon=postermaker
Terminal=false
Categories=Graphics;Publishing;
Keywords=poster;print;mural;postermaker;pdf;
StartupNotify=false
EOF
chmod 644 "$DEST_DESKTOP"
echo "-> Acceso directo instalado en: $DEST_DESKTOP"

# Eliminar el antiguo lanzador blockposters.desktop si existiera
rm -f "$APPS_DIR/blockposters.desktop" 2>/dev/null || true

# 4. Actualizar cachés de Linux si las herramientas están instaladas
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    THEME_DIR="$(dirname "$(dirname "$ICONS_DIR")")"
    gtk-update-icon-cache -q -t "$THEME_DIR" 2>/dev/null || true
fi

echo ""
echo "=== ¡Instalación de PosterMaker completada! ==="
echo "Puedes abrir la aplicación desde el menú de tu escritorio (PosterMaker) o ejecutando 'postermaker'."

# Comprobar si BIN_DIR está en PATH
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo ""
        echo "Aviso: '$BIN_DIR' no está en tu variable \$PATH."
        echo "Puedes añadirlo agregando esta línea a tu ~/.bashrc o ~/.zshrc:"
        echo "  export PATH=\"\$PATH:$BIN_DIR\""
        ;;
esac
