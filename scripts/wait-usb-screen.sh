#!/usr/bin/env bash
# Espera a que la mini pantalla USB aparezca (ttyACM) tras el arranque.
set -euo pipefail

MAX_WAIT="${TURING_USB_WAIT_SEC:-90}"
INTERVAL=2
BY_ID_GLOB="/dev/serial/by-id/usb-*_UsbMonitor_*"
PORT="${TURING_COM_PORT:-/dev/ttyACM0}"

elapsed=0
while [ "$elapsed" -lt "$MAX_WAIT" ]; do
  if ls $BY_ID_GLOB &>/dev/null; then
    port="$(readlink -f "$(ls $BY_ID_GLOB | head -1)")"
    echo "$port"
    exit 0
  fi
  if [ -e "$PORT" ]; then
    echo "$PORT"
    exit 0
  fi
  sleep "$INTERVAL"
  elapsed=$((elapsed + INTERVAL))
done

echo "ERROR: pantalla USB no detectada tras ${MAX_WAIT}s" >&2
exit 1