#!/usr/bin/env bash
# Centro Turing 3.0 — panel grafico para Linux/Ubuntu.
# Sustituye al menu de texto turing-menu.sh (que sigue disponible como respaldo).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

PY="$DIR/.venv/bin/python3"
[[ -x "$PY" ]] || PY="$DIR/venv/bin/python3"
[[ -x "$PY" ]] || PY="$(command -v python3 || true)"

if [[ -z "${PY:-}" ]]; then
  echo "No encuentro Python 3. Instala con: ./scripts/install-ubuntu.sh"
  exit 1
fi

if ! "$PY" -c "import tkinter" 2>/dev/null; then
  echo "Falta Tkinter. En Ubuntu/Debian: sudo apt install python3-tk"
  echo "En Arch: sudo pacman -S tk"
  exit 1
fi

exec "$PY" "$DIR/tools/turing_center.py" "$@"
