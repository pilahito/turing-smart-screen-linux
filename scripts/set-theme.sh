#!/usr/bin/env bash
# Cambia el tema en config.yaml y reinicia el monitor (usa temas de res/themes/).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
THEME="${1:-}"

if [[ -z "$THEME" ]]; then
  echo "Uso: $0 <nombre-tema>"
  echo ""
  "$DIR/scripts/list-themes.sh" 3.5
  exit 1
fi

THEME_DIR="$DIR/res/themes/$THEME"
if [[ ! -f "$THEME_DIR/theme.yaml" ]]; then
  echo "❌ No existe res/themes/$THEME/theme.yaml"
  echo ""
  "$DIR/scripts/list-themes.sh" 3.5
  exit 1
fi

if grep -q '^  THEME:' "$DIR/config.yaml"; then
  sed -i "s|^  THEME:.*|  THEME: $THEME|" "$DIR/config.yaml"
else
  echo "  THEME: $THEME" >>"$DIR/config.yaml"
fi

echo "✓ Tema → $THEME"

if systemctl --user is-active turing-smart-screen.service >/dev/null 2>&1; then
  systemctl --user restart turing-smart-screen.service
  echo "✓ Monitor reiniciado (systemd)"
elif pgrep -f "$DIR/.venv/bin/python3 main.py" >/dev/null; then
  pkill -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
  sleep 2
  "$DIR/scripts/start-screen.sh"
  echo "✓ Monitor reiniciado (manual)"
else
  echo "ℹ️  Monitor no estaba activo. Arranca con: ./scripts/start-screen.sh"
fi