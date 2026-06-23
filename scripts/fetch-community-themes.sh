#!/usr/bin/env bash
# Descarga temas compatibles 3.5" de repositorios de la comunidad.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# repo:subcarpeta:nombre-local
THEMES=(
  "guisfus/RedLineGraphs:RedLineGraphs:RedLineGraphs"
  "Yevgeniy-Olexandrenko/tssp-themes:CpuGpuStatsMono:CpuGpuStatsMono"
)

echo "══ Temas de la comunidad (3.5\") ══"
echo ""

installed=0
skipped=0

for entry in "${THEMES[@]}"; do
  IFS=: read -r repo subdir name <<<"$entry"
  dest="$DIR/res/themes/$name"

  if [[ -f "$dest/theme.yaml" ]]; then
    echo "⊙ $name — ya instalado"
    ((skipped++)) || true
    continue
  fi

  echo "→ Descargando $name ($repo)..."
  work="$TMP/$name"
  mkdir -p "$work"

  if ! git clone --depth 1 --quiet "https://github.com/$repo.git" "$work/repo" 2>/dev/null; then
    echo "  ✗ No se pudo clonar $repo"
    continue
  fi

  src="$work/repo/$subdir"
  if [[ ! -f "$src/theme.yaml" ]]; then
    echo "  ✗ Sin theme.yaml en $subdir"
    continue
  fi

  if ! python3 - "$src/theme.yaml" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
w = h = 0
size = ""
for line in text.splitlines():
    s = line.strip()
    if s.startswith("DISPLAY_SIZE:"):
        size = s.split(":", 1)[1].strip().strip('"')
    elif s.startswith("WIDTH:") and not w:
        try: w = int(s.split(":", 1)[1].strip())
        except ValueError: pass
    elif s.startswith("HEIGHT:") and not h:
        try: h = int(s.split(":", 1)[1].strip())
        except ValueError: pass

ok = "3.5" in size or (w, h) in ((480, 320), (320, 480))
sys.exit(0 if ok else 1)
PY
  then
    echo "  ✗ $name no es compatible con pantalla 3.5\""
    continue
  fi

  mkdir -p "$dest"
  cp -a "$src/." "$dest/"
  echo "  ✓ Instalado en res/themes/$name"
  ((installed++)) || true
done

echo ""
echo "Instalados: $installed | Ya presentes: $skipped"
echo "Lista: ./scripts/list-themes.sh 3.5"
echo "Aplicar: ./scripts/set-theme.sh <nombre>"