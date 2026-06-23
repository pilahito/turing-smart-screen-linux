#!/usr/bin/env bash
# Arranque para systemd: espera USB, una sola instancia, python en primer plano.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="/tmp/turing-screen.log"
LOCK="/tmp/turing-smart-screen.lock"
PIDFILE="/tmp/turing-smart-screen.pid"

cd "$DIR"

if [ ! -x ".venv/bin/python3" ]; then
  echo "Falta .venv en $DIR" >&2
  exit 1
fi

is_running() {
  if [ -f "$PIDFILE" ]; then
    local pid
    pid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  pgrep -f "$DIR/.venv/bin/python3 main.py" >/dev/null 2>&1
}

stop_old() {
  if [ -f "$PIDFILE" ]; then
    local pid
    pid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "$pid" ]; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
  pkill -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
  rm -f "$PIDFILE" "$LOCK"
  sleep 1
}

PORT="$("$DIR/scripts/wait-usb-screen.sh")"
export TURING_COM_PORT="$PORT"

if grep -q '^  COM_PORT:' config.yaml; then
  sed -i "s|^  COM_PORT:.*|  COM_PORT: \"${PORT}\"|" config.yaml
fi

if is_running; then
  stop_old
fi

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "No se pudo obtener lock tras limpiar instancias" >&2
  exit 1
fi

echo "=== $(date -Iseconds) Arranque automático — $PORT ===" >>"$LOG"
echo $$ >"$PIDFILE"
exec .venv/bin/python3 main.py >>"$LOG" 2>&1