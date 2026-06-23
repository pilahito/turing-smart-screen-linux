#!/usr/bin/env bash
# Mantiene /tmp/turing-fps actualizado para la mini pantalla.
# Prioridad: MangoHud → archivo manual → Hz del monitor principal (escritorio).
set -euo pipefail

TARGET="${TURING_FPS_FILE:-/tmp/turing-fps}"
INTERVAL="${TURING_FPS_INTERVAL:-1}"

mangohud_fps() {
  local f
  for f in \
    /tmp/mangohud.fps \
    "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/mangohud.fps" \
    "${HOME}/.cache/mangohud.fps" \
    "${HOME}/.local/share/mangohud.fps"; do
    if [[ -f "$f" ]]; then
      local raw
      raw="$(tr -d ' \n\r' <"$f" 2>/dev/null || true)"
      if [[ "$raw" =~ ^[0-9]+([.,][0-9]+)?$ ]]; then
        awk -v v="${raw//,/.}" 'BEGIN { printf "%d\n", v+0 }'
        return 0
      fi
    fi
  done
  return 1
}

desktop_refresh_fps() {
  local rate=""
  if command -v xrandr >/dev/null && [[ -n "${DISPLAY:-}" ]]; then
    rate="$(xrandr --query 2>/dev/null | awk '
      / connected primary/ { primary=$1 }
      /\*/ {
        hz=$2
        gsub(/[^0-9.].*/, "", hz)
        split(hz, a, ".")
        print a[1]
        exit
      }
    ')"
  fi
  if [[ -z "$rate" ]] || ! [[ "$rate" =~ ^[0-9]+$ ]] || [[ "$rate" -eq 0 ]]; then
    rate=60
  fi
  printf '%s\n' "$rate"
}

write_fps() {
  local fps="$1"
  local tmp="${TARGET}.tmp"
  printf '%s\n' "$fps" >"$tmp"
  mv -f "$tmp" "$TARGET"
}

while true; do
  if fps="$(mangohud_fps 2>/dev/null)"; then
    write_fps "$fps"
  else
    write_fps "$(desktop_refresh_fps)"
  fi
  sleep "$INTERVAL"
done