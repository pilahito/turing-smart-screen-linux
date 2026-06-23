#!/usr/bin/env bash
# Escribe FPS en /tmp/turing-fps para que la mini pantalla lo muestre.
# Uso con juego:  fps-bridge.sh 144   (o desde MangoHud con post_cmd)
# Uso en bucle:    watch -n1 'nvidia-smi ...'  (mejor: overlay del juego)
set -euo pipefail
TARGET="${FPS_TARGET:-/tmp/turing-fps}"
if [[ $# -ge 1 ]]; then
  printf '%s\n' "$1" > "$TARGET"
else
  echo "Uso: $0 <fps>" >&2
  exit 1
fi