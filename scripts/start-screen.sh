#!/usr/bin/env bash
# Arranca el monitor de la pantalla USB (una sola instancia)
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="/tmp/turing-smart-screen.lock"
LOG="/tmp/turing-screen.log"
PIDFILE="/tmp/turing-smart-screen.pid"

cd "$DIR"

if [ ! -x ".venv/bin/python3" ]; then
  echo "Falta el venv. Ejecuta: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

exec 9>"$LOCK"
if ! flock -n 9; then
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Ya está corriendo (PID $(cat "$PIDFILE")). Log: $LOG"
    exit 0
  fi
  echo "Lock antiguo; reiniciando..."
fi

pkill -9 -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
pkill -9 -f "$DIR.*main.py" 2>/dev/null || true
sleep 2

: >"$LOG"
.venv/bin/python3 main.py >>"$LOG" 2>&1 &
echo $! >"$PIDFILE"
disown
echo "Pantalla iniciada (PID $(cat "$PIDFILE")). Log: $LOG"