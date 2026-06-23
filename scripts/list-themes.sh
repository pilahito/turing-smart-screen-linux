#!/usr/bin/env bash
# Lista temas de res/themes/ compatibles con tu tamaño de pantalla (Linux/Ubuntu).
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
THEMES_DIR="$DIR/res/themes"
FILTER="${1:-}"

python3 - "$THEMES_DIR" "$FILTER" <<'PY'
import sys
from pathlib import Path

themes_dir = Path(sys.argv[1])
size_filter = sys.argv[2].strip() if len(sys.argv) > 2 else ""

def parse_theme(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    name = path.parent.name
    size = ""
    orient = ""
    author = ""
    w = h = 0

    for line in text.splitlines():
        s = line.strip()
        if s.startswith("DISPLAY_SIZE:"):
            size = s.split(":", 1)[1].strip().strip('"')
        elif s.startswith("DISPLAY_ORIENTATION:"):
            orient = s.split(":", 1)[1].strip()
        elif s.startswith("author:"):
            author = s.split(":", 1)[1].strip().strip('"').strip("'")
        elif s.startswith("WIDTH:") and w == 0:
            try:
                w = int(s.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif s.startswith("HEIGHT:") and h == 0:
            try:
                h = int(s.split(":", 1)[1].strip())
            except ValueError:
                pass

    if not size:
        if (w, h) == (480, 320):
            size = '3.5" (480×320 landscape)'
        elif (w, h) == (320, 480):
            size = '3.5" (320×480 portrait)'
        elif w and h:
            size = f"{w}×{h}px"
        else:
            size = "desconocido"

    return {
        "name": name,
        "size": size,
        "orient": orient or "?",
        "author": author,
        "has_preview": (path.parent / "preview.png").exists(),
    }

rows = []
for yaml in sorted(themes_dir.glob("*/theme.yaml")):
    if yaml.parent.name in ("default.yaml",):
        continue
    info = parse_theme(yaml)
    if not info:
        continue
    if size_filter:
        sf = size_filter.lower().replace('"', "")
        if sf not in info["size"].lower() and sf not in info["name"].lower():
            if not (sf in ("3.5", "35") and "3.5" in info["size"]):
                continue
    rows.append(info)

if not rows:
    print("No hay temas para ese filtro.")
    sys.exit(0)

print(f"{'#':<4} {'Tema':<32} {'Pantalla':<28} {'Orientación':<12} Autor")
print("-" * 90)
for i, r in enumerate(rows, 1):
    mark = "★" if r["has_preview"] else " "
    print(f"{i:<4} {r['name']:<32} {r['size']:<28} {r['orient']:<12} {r['author'] or '—'} {mark}")

print()
print(f"Total: {len(rows)} temas. Usa: ./scripts/set-theme.sh <nombre>")
print("Filtro por tamaño: ./scripts/list-themes.sh 3.5   (Turing 3.5\" USB)")
PY