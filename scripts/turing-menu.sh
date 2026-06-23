#!/usr/bin/env bash
# Menú interactivo — Turing Smart Screen Linux/Ubuntu
set -euo pipefail

# Buscar proyecto: variable, mismo directorio, o rutas habituales
if [[ -n "${TURING_SCREEN_DIR:-}" && -f "$TURING_SCREEN_DIR/main.py" ]]; then
  DIR="$TURING_SCREEN_DIR"
elif [[ -f "$(dirname "$0")/../main.py" ]]; then
  DIR="$(cd "$(dirname "$0")/.." && pwd)"
elif [[ -f "$HOME/turing-smart-screen-python/main.py" ]]; then
  DIR="$HOME/turing-smart-screen-python"
elif [[ -f "$HOME/turing-smart-screen-linux/main.py" ]]; then
  DIR="$HOME/turing-smart-screen-linux"
else
  echo "❌ No encuentro turing-smart-screen-python"
  echo "   export TURING_SCREEN_DIR=/ruta/al/proyecto"
  exit 1
fi

VERSION="$(cat "$DIR/VERSION" 2>/dev/null || echo dev)"
LOG="/tmp/turing-screen.log"

current_theme() {
  grep '^  THEME:' "$DIR/config.yaml" 2>/dev/null | sed 's/.*: *//' | tr -d ' "' || echo "?"
}

service_status() {
  local s fps
  s="$(systemctl --user is-active turing-smart-screen.service 2>/dev/null || echo inactive)"
  fps="$(systemctl --user is-active turing-fps.service 2>/dev/null || echo inactive)"
  echo "Monitor: $s | FPS: $fps | Tema: $(current_theme)"
}

list_themes_array() {
  python3 - "$DIR/res/themes" <<'PY'
import sys
from pathlib import Path

themes_dir = Path(sys.argv[1])
rows = []

def parse_theme(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    name = path.parent.name
    size = orient = ""
    w = h = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("DISPLAY_SIZE:"):
            size = s.split(":", 1)[1].strip().strip('"')
        elif s.startswith("DISPLAY_ORIENTATION:"):
            orient = s.split(":", 1)[1].strip()
        elif s.startswith("WIDTH:") and not w:
            try: w = int(s.split(":", 1)[1].strip())
            except: pass
        elif s.startswith("HEIGHT:") and not h:
            try: h = int(s.split(":", 1)[1].strip())
            except: pass
    if not size:
        if (w, h) == (480, 320): size = '3.5" L'
        elif (w, h) == (320, 480): size = '3.5" P'
        elif w and h: size = f"{w}x{h}"
        else: size = "?"
    if "3.5" not in size and "480" not in size and "320" not in size:
        if "3.5" not in name.lower() and "35" not in name:
            return None
    rows.append((name, size, orient or "?"))

for yaml in sorted(themes_dir.glob("*/theme.yaml")):
    r = parse_theme(yaml)
    if r: rows.append(r)

for name, size, orient in rows:
    print(f"{name}\t{size}\t{orient}")
PY
}

pick_theme() {
  mapfile -t LINES < <(list_themes_array)
  if [[ ${#LINES[@]} -eq 0 ]]; then
    echo "No hay temas 3.5\" detectados."
    read -r -p "Enter..."
    return
  fi
  echo ""
  echo "══ Temas para pantalla 3.5\" ══"
  local i=1 cur
  cur="$(current_theme)"
  for line in "${LINES[@]}"; do
    IFS=$'\t' read -r name size orient <<<"$line"
    local mark=""
    [[ "$name" == "$cur" ]] && mark=" ← actual"
    printf "  %2d) %-30s %s %s%s\n" "$i" "$name" "$size" "$orient" "$mark"
    ((i++)) || true
  done
  echo ""
  read -r -p "Número de tema (0=cancelar): " num
  [[ -z "$num" || "$num" == "0" ]] && return
  if ! [[ "$num" =~ ^[0-9]+$ ]] || (( num < 1 || num > ${#LINES[@]} )); then
    echo "Opción inválida."
    read -r -p "Enter..."
    return
  fi
  IFS=$'\t' read -r name _ _ <<<"${LINES[$((num - 1))]}"
  "$DIR/scripts/set-theme.sh" "$name"
  echo ""
  read -r -p "Enter..."
}

pause() { read -r -p "Pulsa Enter..." _; }

while true; do
  clear
  echo "╔══════════════════════════════════════════════════╗"
  echo "║     Turing Smart Screen — Linux/Ubuntu           ║"
  echo "║     v$VERSION"
  echo "╚══════════════════════════════════════════════════╝"
  echo ""
  service_status
  echo "  Proyecto: $DIR"
  echo "  Log:      $LOG"
  echo ""
  echo "  1) Elegir tema (39+ incluidos)"
  echo "  2) Reiniciar monitor"
  echo "  3) Iniciar monitor (manual)"
  echo "  4) Parar monitor"
  echo "  5) Ver últimas líneas del log"
  echo "  6) Estado systemd detallado"
  echo "  7) Instalar/reparar autostart"
  echo "  8) Ventiladores CPU (Gigabyte — sudo)"
  echo "  9) Abrir GitHub del proyecto"
  echo "  0) Salir"
  echo ""
  read -r -p "Opción: " opt

  case "$opt" in
    1) pick_theme ;;
    2)
      systemctl --user restart turing-fps.service turing-smart-screen.service 2>/dev/null \
        || "$DIR/scripts/start-screen.sh"
      echo "✓ Reiniciado"
      pause
      ;;
    3)
      "$DIR/scripts/start-screen.sh"
      pause
      ;;
    4)
      systemctl --user stop turing-smart-screen.service 2>/dev/null || true
      pkill -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
      echo "✓ Detenido"
      pause
      ;;
    5)
      echo ""
      tail -25 "$LOG" 2>/dev/null || echo "(sin log)"
      pause
      ;;
    6)
      systemctl --user status turing-smart-screen.service turing-fps.service --no-pager 2>/dev/null || true
      pause
      ;;
    7)
      "$DIR/scripts/install-autostart.sh"
      pause
      ;;
    8)
      sudo "$DIR/scripts/install-fan-modules.sh" || true
      pause
      ;;
    9)
      xdg-open "https://github.com/pilahito/turing-smart-screen-linux" 2>/dev/null \
        || sensible-browser "https://github.com/pilahito/turing-smart-screen-linux" 2>/dev/null \
        || echo "https://github.com/pilahito/turing-smart-screen-linux"
      pause
      ;;
    0|q|Q) exit 0 ;;
    *) echo "Opción no válida"; sleep 1 ;;
  esac
done