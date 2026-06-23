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

current_revision() {
  grep '^  REVISION:' "$DIR/config.yaml" 2>/dev/null | sed 's/.*: *//' | tr -d ' "' || echo "?"
}

theme_count() {
  "$DIR/scripts/list-themes.sh" 3.5 2>/dev/null | awk '/^Total:/ {print $2}'
}

service_status() {
  local s fps rev
  s="$(systemctl --user is-active turing-smart-screen.service 2>/dev/null || echo inactive)"
  fps="$(systemctl --user is-active turing-fps.service 2>/dev/null || echo inactive)"
  rev="$(current_revision)"
  echo "Monitor: $s | FPS: $fps | Modo: $rev | Tema: $(current_theme)"
}

list_themes_array() {
  local filter="${1:-3.5}"
  python3 - "$DIR/res/themes" "$filter" <<'PY'
import sys
from pathlib import Path

themes_dir = Path(sys.argv[1])
size_filter = sys.argv[2].strip().lower() if len(sys.argv) > 2 else ""

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
    if size_filter in ("landscape", "l"):
        if orient != "landscape" and (w, h) != (480, 320):
            return None
    elif size_filter in ("portrait", "p"):
        if orient != "portrait" and (w, h) != (320, 480):
            return None
    elif size_filter in ("3.5", '3.5"'):
        if "3.5" not in size and (w, h) not in ((480, 320), (320, 480)):
            if "3.5" not in name.lower() and "35" not in name:
                return None
    rows.append((name, size, orient or "?"))

rows = []
for yaml in sorted(themes_dir.glob("*/theme.yaml")):
    r = parse_theme(yaml)
    if r: rows.append(r)

for name, size, orient in rows:
    print(f"{name}\t{size}\t{orient}")
PY
}

pick_theme() {
  echo ""
  echo "Filtro: [1] Todos 3.5\"  [2] Landscape  [3] Portrait"
  read -r -p "Elige filtro [1]: " filt
  filt="${filt:-1}"
  local filter="3.5"
  case "$filt" in
    2|l|L) filter="landscape" ;;
    3|p|P) filter="portrait" ;;
  esac

  mapfile -t LINES < <(list_themes_array "$filter")
  if [[ ${#LINES[@]} -eq 0 ]]; then
    echo "No hay temas para ese filtro."
    read -r -p "Enter..."
    return
  fi
  echo ""
  echo "══ Temas (${#LINES[@]}) — filtro: $filter ══"
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

open_mirror_window() {
  local mon=""
  echo ""
  echo "Monitores detectados:"
  xrandr --query 2>/dev/null | awk '/ connected/{print "  - "$1}' || true
  read -r -p "Monitor destino (Enter=actual, ej. DP-0): " mon
  local args=(--image "$DIR/screencap.png" --scale 2.5)
  [[ -n "$mon" ]] && args+=(--monitor "$mon")
  pkill -f "$DIR/scripts/preview-window.py" 2>/dev/null || true
  nohup "$DIR/.venv/bin/python3" "$DIR/scripts/preview-window.py" "${args[@]}" \
    >/tmp/turing-mirror.log 2>&1 &
  echo "✓ Ventana espejo abierta (requiere modo SIMU o pantalla virtual activa)"
}

pause() { read -r -p "Pulsa Enter..." _; }

TCOUNT="$(theme_count 2>/dev/null || echo "?")"

while true; do
  clear
  echo "╔══════════════════════════════════════════════════╗"
  echo "║     Turing Smart Screen — Linux/Ubuntu           ║"
  echo "║     v$VERSION"
  echo "╚══════════════════════════════════════════════════╝"
  echo ""
  service_status
  echo "  Proyecto: $DIR"
  echo "  Temas:    $TCOUNT compatibles 3.5\""
  echo "  Log:      $LOG"
  echo ""
  echo "  ── Temas ──"
  echo "  1) Elegir tema (filtro landscape/portrait)"
  echo "  2) Galería visual de temas (navegador)"
  echo "  3) Descargar temas de la comunidad"
  echo ""
  echo "  ── Monitor ──"
  echo "  4) Reiniciar monitor USB"
  echo "  5) Iniciar / parar monitor"
  echo "  6) Ver log / estado systemd"
  echo ""
  echo "  ── Ver en el PC (como otra pantalla) ──"
  echo "  7) Pantalla virtual en escritorio (SIMU + navegador)"
  echo "  8) Ventana espejo flotante (en DP-0 / HDMI-0)"
  echo "  9) Volver a pantalla USB física"
  echo ""
  echo "  ── Sistema ──"
  echo "  a) Instalar/reparar autostart"
  echo "  b) Ventiladores CPU (Gigabyte — sudo)"
  echo "  c) Abrir GitHub del proyecto"
  echo "  p) 🎁 Pilahito Command Center (Escritorio)"
  echo "  0) Salir"
  echo ""
  read -r -p "Opción: " opt

  case "$opt" in
    1) pick_theme; TCOUNT="$(theme_count 2>/dev/null || echo "?")" ;;
    2)
      echo ""
      echo "Filtro galería: [1] Todos  [2] Landscape  [3] Portrait"
      read -r -p "Elige [1]: " gf
      gf="${gf:-1}"
      gfilter="3.5"
      case "$gf" in 2) gfilter="landscape" ;; 3) gfilter="portrait" ;; esac
      "$DIR/scripts/theme-gallery.sh" "$gfilter"
      pause
      ;;
    3)
      "$DIR/scripts/fetch-community-themes.sh"
      TCOUNT="$(theme_count 2>/dev/null || echo "?")"
      pause
      ;;
    4)
      systemctl --user restart turing-fps.service turing-smart-screen.service 2>/dev/null \
        || "$DIR/scripts/start-screen.sh"
      echo "✓ Reiniciado"
      pause
      ;;
    5)
      echo "  [1] Iniciar  [2] Parar"
      read -r -p "Elige: " sub
      case "$sub" in
        2)
          systemctl --user stop turing-smart-screen.service 2>/dev/null || true
          pkill -f "$DIR/.venv/bin/python3 main.py" 2>/dev/null || true
          echo "✓ Detenido"
          ;;
        *)
          "$DIR/scripts/start-screen.sh"
          ;;
      esac
      pause
      ;;
    6)
      echo ""
      tail -25 "$LOG" 2>/dev/null || echo "(sin log)"
      echo ""
      systemctl --user status turing-smart-screen.service turing-fps.service --no-pager 2>/dev/null || true
      pause
      ;;
    7)
      echo ""
      echo "ℹ️  La mini pantalla USB no puede ser monitor extendido real."
      echo "   Esto abre una copia en vivo en tu PC (modo simulado)."
      read -r -p "Monitor destino para la ventana (Enter=actual, ej. DP-0): " vmon
      if [[ -n "$vmon" ]]; then
        MONITOR="$vmon" "$DIR/scripts/start-virtual-screen.sh"
      else
        "$DIR/scripts/start-virtual-screen.sh"
      fi
      pause
      ;;
    8) open_mirror_window; pause ;;
    9)
      "$DIR/scripts/restore-usb-screen.sh"
      pause
      ;;
    a|A)
      "$DIR/scripts/install-autostart.sh"
      pause
      ;;
    b|B)
      sudo "$DIR/scripts/install-fan-modules.sh" || true
      pause
      ;;
    c|C)
      xdg-open "https://github.com/pilahito/turing-smart-screen-linux" 2>/dev/null \
        || sensible-browser "https://github.com/pilahito/turing-smart-screen-linux" 2>/dev/null \
        || echo "https://github.com/pilahito/turing-smart-screen-linux"
      pause
      ;;
    p|P)
      xdg-open "$HOME/Escritorio/Pilahito-Command-Center.html" 2>/dev/null \
        || xdg-open "$HOME/Desktop/Pilahito-Command-Center.html" 2>/dev/null \
        || echo "Abre: ~/Escritorio/Pilahito-Command-Center.html"
      pause
      ;;
    0|q|Q) exit 0 ;;
    *) echo "Opción no válida"; sleep 1 ;;
  esac
done