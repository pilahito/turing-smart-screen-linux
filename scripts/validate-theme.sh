#!/usr/bin/env bash
# Valida un tema 3.5" landscape antes de publicarlo (evita pantallas bugueadas).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
THEME="${1:-}"

if [[ -z "$THEME" ]]; then
  echo "Uso: $0 <nombre-tema>"
  exit 1
fi

YAML="$DIR/res/themes/$THEME/theme.yaml"
BG="$DIR/res/themes/$THEME/background.png"

err=0
[[ -f "$YAML" ]] || { echo "❌ Falta theme.yaml"; exit 1; }
[[ -f "$BG" ]] || { echo "❌ Falta background.png"; err=1; }

python3 - "$YAML" "$BG" <<'PY'
import sys
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    print("⚠️  Instala Pillow para validar tamaño de imagen")
    sys.exit(0)

yaml = Path(sys.argv[1])
bg = Path(sys.argv[2])
text = yaml.read_text(encoding="utf-8", errors="ignore")

if 'DISPLAY_ORIENTATION: landscape' not in text and 'WIDTH: 480' not in text:
    print("⚠️  No parece landscape 480×320")

img = Image.open(bg)
if img.size != (480, 320):
    print(f"❌ background.png debe ser 480×320, es {img.size}")
    sys.exit(1)

# DATE y fondos con texto grande suelen causar ghosting
if 'STATS:' in text and '  DATE:' in text:
    print("⚠️  Sección DATE puede causar parpadeos — mejor evitarla")

if 'static_text:' not in text:
    print("ℹ️  Sin static_text (opcional)")

print(f"✓ Tema {yaml.parent.name} — background {img.size[0]}×{img.size[1]} OK")
PY

exit $err