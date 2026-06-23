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

echo "✓ Escritorio: $DESKTOP/turing-menu.sh"
echo "✓ Acceso directo: $DESKTOP/Turing-Smart-Screen.desktop"
echo "  Doble clic o: $DESKTOP/turing-menu.sh"