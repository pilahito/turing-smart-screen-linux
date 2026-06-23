#!/usr/bin/env bash
# Genera y abre una galería HTML con previews de temas 3.5".
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
FILTER="${1:-3.5}"
CACHE="$DIR/.cache"
OUT="$CACHE/turing-theme-gallery.html"
PORT=8765

mkdir -p "$CACHE"

python3 - "$DIR" "$FILTER" "$OUT" <<'PY'
import html
import sys
from pathlib import Path

project = Path(sys.argv[1])
size_filter = sys.argv[2].lower()
out = Path(sys.argv[3])
themes_dir = project / "res/themes"

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
            except ValueError: pass
        elif s.startswith("HEIGHT:") and not h:
            try: h = int(s.split(":", 1)[1].strip())
            except ValueError: pass
    if not size:
        if (w, h) == (480, 320):
            size = '3.5" landscape'
        elif (w, h) == (320, 480):
            size = '3.5" portrait'
        elif w and h:
            size = f"{w}×{h}"
    if size_filter in ("landscape", "l"):
        if orient != "landscape" and (w, h) != (480, 320):
            return None
    elif size_filter in ("portrait", "p"):
        if orient != "portrait" and (w, h) != (320, 480):
            return None
    elif size_filter in ("3.5", '3.5"'):
        if "3.5" not in size and (w, h) not in ((480, 320), (320, 480)):
            if "3.5" not in name.lower():
                return None
    preview = path.parent / "preview.png"
    bg = path.parent / "background.png"
    img = preview if preview.exists() else (bg if bg.exists() else None)
    return {
        "name": name,
        "size": size or "?",
        "orient": orient or "?",
        "img": img,
    }

rows = []
for yaml in sorted(themes_dir.glob("*/theme.yaml")):
    info = parse_theme(yaml)
    if info:
        rows.append(info)

cards = []
for r in rows:
    if r["img"]:
        rel = r["img"].relative_to(project).as_posix()
        img_tag = f'<img src="/{rel}" alt="{html.escape(r["name"])}" loading="lazy">'
    else:
        img_tag = '<div class="noimg">sin preview</div>'
    cards.append(
        f'<article class="card">'
        f'{img_tag}'
        f'<h3>{html.escape(r["name"])}</h3>'
        f'<p>{html.escape(r["size"])} · {html.escape(r["orient"])}</p>'
        f'<code>./scripts/set-theme.sh {html.escape(r["name"])}</code>'
        f'</article>'
    )

page = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Turing — Galería de temas</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f1117; color: #e8eaed; margin: 0; padding: 1.5rem; }}
  h1 {{ margin-top: 0; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }}
  .card {{ background: #1a1d27; border-radius: 12px; padding: 0.75rem; border: 1px solid #2a2f3d; }}
  .card img {{ width: 100%; border-radius: 8px; background: #000; aspect-ratio: 3/2; object-fit: contain; }}
  .noimg {{ height: 120px; display: grid; place-items: center; background: #111; border-radius: 8px; color: #888; }}
  .card h3 {{ margin: 0.6rem 0 0.2rem; font-size: 0.95rem; }}
  .card p {{ margin: 0; color: #9aa0a6; font-size: 0.8rem; }}
  .card code {{ display: block; margin-top: 0.5rem; font-size: 0.72rem; color: #8ab4f8; word-break: break-all; }}
  .hint {{ color: #9aa0a6; margin-bottom: 1rem; }}
</style>
</head>
<body>
<h1>Galería de temas Turing 3.5"</h1>
<p class="hint">Filtro: {html.escape(size_filter)} · {len(rows)} temas</p>
<div class="grid">
{"".join(cards)}
</div>
</body>
</html>"""

out.write_text(page, encoding="utf-8")
print(f"Galería: {out} ({len(rows)} temas)")
PY

if [[ -f /tmp/turing-gallery-server.pid ]]; then
  kill "$(cat /tmp/turing-gallery-server.pid)" 2>/dev/null || true
fi

cd "$DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1 >/tmp/turing-gallery-server.log 2>&1 &
echo $! >/tmp/turing-gallery-server.pid
sleep 0.4

URL="http://127.0.0.1:$PORT/.cache/turing-theme-gallery.html"
xdg-open "$URL" 2>/dev/null \
  || sensible-browser "$URL" 2>/dev/null \
  || echo "Abre: $URL"