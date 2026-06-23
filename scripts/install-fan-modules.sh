#!/usr/bin/env bash
# Carga nct6683/it87 al arrancar (Gigabyte B760 GAMING X DDR4 y similares).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecuta con sudo: sudo $0" >&2
  exit 1
fi

install -m 0644 "$DIR/scripts/load-fan-modules.conf" /etc/modules-load.d/turing-fans.conf
install -m 0644 "$DIR/scripts/modprobe-fans.conf" /etc/modprobe.d/turing-fans.conf

modprobe nct6683 2>/dev/null || true
modprobe it87 ignore_resource_conflict=1 force_id=0x8622 2>/dev/null || \
  modprobe it87 ignore_resource_conflict=1 2>/dev/null || true
modprobe nct6775 2>/dev/null || true

echo "=== Ventiladores tras cargar módulos ==="
if command -v sensors >/dev/null; then
  sensors 2>/dev/null | grep -iE 'fan|pwm' || echo "(ninguno aún — reinicia el PC si sigue vacío)"
else
  echo "Instala lm-sensors: apt install lm-sensors"
fi

echo ""
echo "OK. Reinicia el monitor Turing:"
echo "  systemctl --user restart turing-smart-screen"