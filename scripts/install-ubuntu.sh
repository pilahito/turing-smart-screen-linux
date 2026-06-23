#!/usr/bin/env bash
# Instalación completa en Ubuntu/Debian — mini pantalla Turing 3.5" USB.
# Usa los temas ya incluidos en res/themes/ (Cyberdeck, NZXT, Cyberpunk, Simple*, etc.)
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(cat "$DIR/VERSION" 2>/dev/null || echo dev)"

echo "╔══════════════════════════════════════════════════╗"
echo "║  Turing Smart Screen — Linux/Ubuntu $VERSION"
echo "╚══════════════════════════════════════════════════╝"
echo ""

if ! command -v python3 >/dev/null; then
  echo "Instala Python 3: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

# Dependencias del sistema (opcional con sudo)
if command -v apt-get >/dev/null && [[ "$(id -u)" -ne 0 ]]; then
  echo "→ Dependencias recomendadas (puede pedir contraseña)..."
  sudo apt-get update -qq
  sudo apt-get install -y python3-venv python3-pip lm-sensors git \
    libusb-1.0-0 udev 2>/dev/null || true
fi

chmod +x "$DIR"/scripts/*.sh 2>/dev/null || true

# Entorno virtual
if [[ ! -x "$DIR/.venv/bin/python3" ]]; then
  echo "→ Creando entorno virtual..."
  python3 -m venv "$DIR/.venv"
fi
echo "→ Instalando dependencias Python..."
"$DIR/.venv/bin/pip" install -q -U pip
"$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"

# Grupo dialout para puerto USB serial
if groups "$(whoami)" | grep -qv dialout && getent group dialout >/dev/null; then
  echo "→ Añadiendo usuario a dialout (acceso USB)..."
  sudo usermod -aG dialout "$(whoami)" 2>/dev/null || true
  echo "   (cierra sesión y vuelve a entrar si el puerto USB falla)"
fi

# Ventiladores Gigabyte (opcional)
if ! ls /sys/class/hwmon/hwmon*/fan*_input >/dev/null 2>&1; then
  echo ""
  echo "⚠️  Ventiladores CPU no detectados (común en Gigabyte B760)."
  read -r -p "¿Instalar módulo it87 ahora? [s/N] " fan
  if [[ "${fan,,}" == "s" || "${fan,,}" == "y" ]]; then
    sudo "$DIR/scripts/install-fan-modules.sh" || true
  fi
fi

# Elegir tema
echo ""
echo "══ Temas disponibles para pantalla 3.5\" (landscape/portrait) ══"
"$DIR/scripts/list-themes.sh" 3.5 | head -25
echo ""
CURRENT="$(grep '^  THEME:' "$DIR/config.yaml" 2>/dev/null | sed 's/.*: *//' || echo Cyberdeck)"
read -r -p "Tema a usar [$CURRENT]: " PICK
PICK="${PICK:-$CURRENT}"
if [[ -f "$DIR/res/themes/$PICK/theme.yaml" ]]; then
  sed -i "s|^  THEME:.*|  THEME: $PICK|" "$DIR/config.yaml"
  echo "✓ Tema: $PICK"
else
  echo "ℹ️  Tema '$PICK' no encontrado — se mantiene $CURRENT"
fi

# Autostart + FPS
echo ""
echo "→ Instalando arranque automático al iniciar sesión..."
"$DIR/scripts/install-autostart.sh"

echo ""
echo "══════════════════════════════════════════════════"
echo "✓ Instalación completada — $VERSION"
echo ""
echo "  Cambiar tema:  ./scripts/set-theme.sh Cyberdeck"
echo "  Ver temas:     ./scripts/list-themes.sh 3.5"
echo "  Estado:        systemctl --user status turing-smart-screen"
echo "  Log:           tail -f /tmp/turing-screen.log"
echo "══════════════════════════════════════════════════"