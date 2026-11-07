#!/bin/sh
# Desinstalador de Block Posters para cualquier distribución de Linux.

set -e

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

echo "Desinstalando PosterMaker de $BIN_DIR..."

rm -f "$BIN_DIR/postermaker"
rm -f "$BIN_DIR/blockposters"
rm -f "$APPS_DIR/postermaker.desktop"
rm -f "$APPS_DIR/blockposters.desktop"
rm -f "$ICONS_DIR/postermaker.svg"
rm -f "$ICONS_DIR/blockposters.svg"
rm -f "$PIXMAPS_DIR/postermaker.svg"
rm -f "$PIXMAPS_DIR/blockposters.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "=== Desinstalación completada con éxito ==="
