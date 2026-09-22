#!/usr/bin/env bash
# Instala el menú en el escritorio (Escritorio/ o Desktop/).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
DESKTOP=""
for d in "$HOME/Escritorio" "$HOME/Desktop"; do
  if [[ -d "$d" ]]; then DESKTOP="$d"; break; fi
done
if [[ -z "$DESKTOP" ]]; then
  DESKTOP="$HOME/Escritorio"
  mkdir -p "$DESKTOP"
fi

chmod +x "$DIR/scripts/turing-menu.sh"
chmod +x "$DIR/scripts/turing-center.sh" 2>/dev/null || true

cat >"$DESKTOP/turing-menu.sh" <<EOF
#!/usr/bin/env bash
export TURING_SCREEN_DIR="\${TURING_SCREEN_DIR:-$DIR}"
exec "\$TURING_SCREEN_DIR/scripts/turing-menu.sh"
EOF
chmod +x "$DESKTOP/turing-menu.sh"

cat >"$DESKTOP/Turing-Smart-Screen.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Turing Smart Screen
Comment=Menú mini pantalla USB — temas, reinicio, log
Exec=bash -lc '$DESKTOP/turing-menu.sh'
Icon=utilities-system-monitor
Terminal=true
Categories=System;Monitor;
StartupNotify=true
EOF
chmod +x "$DESKTOP/Turing-Smart-Screen.desktop"
gio set "$DESKTOP/Turing-Smart-Screen.desktop" metadata::trusted true 2>/dev/null || true

# Centro Turing 3.0: panel grafico (misma interfaz que en Windows)
cat >"$DESKTOP/Centro-Turing.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Centro Turing
Comment=Panel grafico de la mini pantalla USB — temas, brillo, ajustes y diagnostico
Exec=$(command -v python3 || echo python3) $DIR/tools/turing_center.py
Path=$DIR
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;Settings;
StartupNotify=true
EOF
chmod +x "$DESKTOP/Centro-Turing.desktop"
gio set "$DESKTOP/Centro-Turing.desktop" metadata::trusted true 2>/dev/null || true

# Entrada en el menu de aplicaciones del sistema
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
cp "$DESKTOP/Centro-Turing.desktop" "$APPS/centro-turing.desktop"
update-desktop-database "$APPS" 2>/dev/null || true

echo "✓ Escritorio: $DESKTOP/turing-menu.sh"
echo "✓ Acceso directo: $DESKTOP/Turing-Smart-Screen.desktop"
echo "✓ Centro Turing (GUI): $DESKTOP/Centro-Turing.desktop"
echo "  Doble clic o: $DESKTOP/turing-menu.sh"