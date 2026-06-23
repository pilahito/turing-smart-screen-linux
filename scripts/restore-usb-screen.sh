#!/usr/bin/env bash
# Restaura config USB y reinicia el monitor en la mini pantalla física.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP="$DIR/.config-usb-backup.yaml"

pkill -f "$DIR/scripts/preview-window.py" 2>/dev/null || true
if [[ -f /tmp/turing-virtual-screen.pid ]]; then
  kill "$(cat /tmp/turing-virtual-screen.pid)" 2>/dev/null || true
  rm -f /tmp/turing-virtual-screen.pid
fi
pkill -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
sleep 1

if [[ -f "$BACKUP" ]]; then
  cp "$BACKUP" "$DIR/config.yaml"
  echo "✓ Config USB restaurada"
else
  python3 - "$DIR/config.yaml" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r"^  REVISION:.*$", "  REVISION: A", text, flags=re.M)
path.write_text(text, encoding="utf-8")
PY
  echo "✓ REVISION → A (USB)"
fi

if systemctl --user is-enabled turing-smart-screen.service >/dev/null 2>&1; then
  systemctl --user restart turing-fps.service turing-smart-screen.service
  echo "✓ Monitor USB reiniciado (systemd)"
else
  "$DIR/scripts/start-screen.sh"
fi