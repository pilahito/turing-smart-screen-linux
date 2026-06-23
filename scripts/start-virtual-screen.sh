#!/usr/bin/env bash
# Pantalla virtual en el PC: modo SIMU + navegador + ventana espejo opcional.
# No sustituye la USB física; sirve para previsualizar temas en el escritorio.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP="$DIR/.config-usb-backup.yaml"
MONITOR="${1:-}"
OPEN_MIRROR="${OPEN_MIRROR:-1}"

cd "$DIR"

if [[ ! -x ".venv/bin/python3" ]]; then
  echo "Falta venv. Ejecuta: ./scripts/install-ubuntu.sh"
  exit 1
fi

# Guardar config USB actual
if [[ ! -f "$BACKUP" ]]; then
  cp "$DIR/config.yaml" "$BACKUP"
  echo "✓ Copia de seguridad → .config-usb-backup.yaml"
fi

# Activar modo simulado
python3 - "$DIR/config.yaml" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(r"^  REVISION:.*$", "  REVISION: SIMU", text, flags=re.M)
path.write_text(text, encoding="utf-8")
PY

systemctl --user stop turing-smart-screen.service 2>/dev/null || true
pkill -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
sleep 1

: >/tmp/turing-screen.log
.venv/bin/python3 main.py >>/tmp/turing-screen.log 2>&1 &
VPID=$!
echo "$VPID" >/tmp/turing-virtual-screen.pid
disown

echo "✓ Pantalla virtual iniciada (PID $VPID, modo SIMU)"
echo "  Navegador: http://localhost:5678"
echo "  Imagen:    $DIR/screencap.png"

sleep 2
xdg-open "http://localhost:5678" 2>/dev/null || true

if [[ "$OPEN_MIRROR" == "1" ]]; then
  MON_ARG=()
  [[ -n "$MONITOR" ]] && MON_ARG=(--monitor "$MONITOR")
  nohup .venv/bin/python3 "$DIR/scripts/preview-window.py" \
    --image "$DIR/screencap.png" \
    --scale 2.5 \
    "${MON_ARG[@]}" >/tmp/turing-mirror.log 2>&1 &
  echo "✓ Ventana espejo flotante abierta"
fi

echo ""
echo "Para volver a la pantalla USB física:"
echo "  ./scripts/restore-usb-screen.sh"