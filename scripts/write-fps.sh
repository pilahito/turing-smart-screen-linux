#!/usr/bin/env bash
# Escribe FPS en el archivo que lee la mini pantalla.
# Uso manual:  ./scripts/write-fps.sh 144
# Con MangoHud (añade a ~/.config/MangoHud/MangoHud.conf):
#   custom_text_center=echo $(cat /tmp/mangohud.fps) > /tmp/turing-fps
# O más simple, desde un juego con MangoHud:
#   fps_sampling_period=0
#   fps_limit=0
#   exec=echo $FPS > /tmp/turing-fps
set -euo pipefail

TARGET="${TURING_FPS_FILE:-/tmp/turing-fps}"
FPS="${1:-}"

if [[ -z "$FPS" ]]; then
  echo "Uso: $0 <fps>" >&2
  exit 1
fi

if ! [[ "$FPS" =~ ^[0-9]+([.,][0-9]+)?$ ]]; then
  echo "FPS inválido: $FPS" >&2
  exit 1
fi

printf '%s\n' "${FPS//,/.}" | awk '{printf "%d\n", $1}' > "$TARGET"