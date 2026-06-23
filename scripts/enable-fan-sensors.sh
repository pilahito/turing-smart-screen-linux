#!/usr/bin/env bash
# Activa sensores de ventiladores en placas Gigabyte (p. ej. B760 GAMING X DDR4)
set -euo pipefail

echo "=== Activando sensores de ventiladores ==="
echo "(B760 GAMING X: suele necesitar nct6683)"

if ! command -v sensors >/dev/null; then
  echo "Instala lm-sensors: sudo apt install lm-sensors"
  exit 1
fi

try_modprobe() {
  local args=("$@")
  echo "-> modprobe ${args[*]}"
  if sudo modprobe "${args[@]}" 2>/dev/null; then
    return 0
  fi
  return 1
}

# Gigabyte recientes (B760/B850): chip NCT6683
try_modprobe nct6683 || true

# Gigabyte clásicas: chip ITE IT86xx/IT87xx
try_modprobe it87 ignore_resource_conflict=1 force_id=0x8622 || true
try_modprobe it87 ignore_resource_conflict=1 || true
try_modprobe it87 ignore_resource_conflict=1 force_id=0x8688 || true

# Alternativa Nuvoton
try_modprobe nct6775 || true

echo
echo "=== Ventiladores detectados ==="
if sensors 2>/dev/null | grep -iE 'fan|pwm'; then
  echo
  echo "OK. Reinicia el monitor:"
  echo "  pkill -f 'turing-smart-screen-python/.venv/bin/python3 main.py'"
  echo "  cd ~/turing-smart-screen-python && source .venv/bin/activate && python3 main.py"
else
  echo
  echo "Aún no hay ventiladores. Prueba:"
  echo "  1) sudo sensors-detect   (di YES a Super I/O)"
  echo "  2) Compilar it87: https://github.com/frankcrawford/it87"
  echo "  3) Carga permanente al arrancar:"
  echo "     sudo cp scripts/load-fan-modules.conf /etc/modules-load.d/turing-fans.conf"
  echo "     sudo cp scripts/modprobe-fans.conf /etc/modprobe.d/turing-fans.conf"
  echo "  4) Reiniciar el PC tras cargar el módulo"
fi