#!/bin/sh
# Desinstalador de Block Posters para cualquier distribución de Linux.

set -e

if [ "$(id -u)" -eq 0 ]; then
    BIN_DIR="/usr/local/bin"
    APPS_DIR="/usr/local/share/applications"
    ICONS_DIR="/usr/local/share/icons/hicolor/scalable/apps"
    PIXMAPS_DIR="/usr/share/pixmaps"
    SYSTEMD_USER_DIR="/etc/systemd/user"
else
    BIN_DIR="$HOME/.local/bin"
    APPS_DIR="$HOME/.local/share/applications"
    ICONS_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
    PIXMAPS_DIR="$HOME/.local/share/pixmaps"
    SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
fi

echo "Desinstalando PosterMaker de $BIN_DIR..."

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop postermaker.service 2>/dev/null || true
    systemctl --user disable postermaker.service 2>/dev/null || true
fi

rm -f "$BIN_DIR/postermaker"
rm -f "$BIN_DIR/blockposters"
rm -f "$APPS_DIR/postermaker.desktop"
rm -f "$APPS_DIR/blockposters.desktop"
rm -f "$ICONS_DIR/postermaker.svg"
rm -f "$ICONS_DIR/blockposters.svg"
rm -f "$PIXMAPS_DIR/postermaker.svg"
rm -f "$PIXMAPS_DIR/blockposters.svg"
rm -f "$SYSTEMD_USER_DIR/postermaker.service"
rm -f "$SYSTEMD_USER_DIR/blockposters.service"

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "=== Desinstalación completada con éxito ==="
