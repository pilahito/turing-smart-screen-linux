# -*- coding: utf-8 -*-
"""Audita la resolucion de los temas frente al fondo real (esquema de este fork).

Campos relevantes del theme.yaml:
    display:
      DISPLAY_SIZE: 3.5"           -> la libreria lo traduce a 320x480 (vertical)
      DISPLAY_ORIENTATION: landscape
    static_images:
      BACKGROUND:
        PATH: background.png
        WIDTH: 480
        HEIGHT: 320

Uso: python tmp/audit-temas.py <raiz-del-proyecto> [--verbose]
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(sys.argv[1]).resolve()
VERBOSE = "--verbose" in sys.argv
THEMES = ROOT / "res" / "themes"


def _png_size(path: Path):
    """Tamano de un PNG leyendo la cabecera (sin dependencias)."""
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    except OSError:
        return None

# Medidas que declara la libreria (en vertical) para cada DISPLAY_SIZE
LIB_SIZES = {
    '0.96"': (80, 160), '2.1"': (480, 480), '2.8"': (480, 480), '3.5"': (320, 480),
    '4.6"': (320, 960), '5"': (480, 800), '5.2"': (720, 1280), '8"': (800, 1280),
    '8.8"': (480, 1920), '9.2"': (480, 1920), '12.3"': (720, 1920),
}
# Medida comercial real segun el fondo (horizontal x vertical)
BY_DIMS = {(480, 320): '3.5"', (320, 480): '3.5"', (480, 480): '2.1"', (800, 480): '5"',
           (480, 800): '5"', (1920, 480): '8.8"', (480, 1920): '8.8"', (1280, 800): '8"',
           (800, 1280): '8"', (720, 1280): '5.2"', (1280, 720): '5.2"', (320, 960): '4.6"',
           (960, 320): '4.6"', (80, 160): '0.96"', (160, 80): '0.96"', (1920, 462): '9.2"',
           (720, 1920): '12.3"', (1920, 720): '12.3"'}


def image_size(path: Path):
    """Tamano real de cualquier imagen soportada (PNG, JPG, GIF...)."""
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        return _png_size(path) if path.suffix.lower() == ".png" else None

rows = []
for theme_yaml in sorted(THEMES.glob("*/theme.yaml")):
    folder = theme_yaml.parent
    try:
        data = yaml.safe_load(theme_yaml.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception as error:
        rows.append((folder.name, "?", "?", (0, 0), f"YAML ilegible: {str(error).splitlines()[0]}"))
        continue
    display = data.get("display") or {}
    background = ((data.get("static_images") or {}).get("BACKGROUND")) or {}
    size_field = str(display.get("DISPLAY_SIZE", "") or "").strip()
    orient_field = str(display.get("DISPLAY_ORIENTATION", "") or "").strip().lower()
    declared_w = background.get("WIDTH")
    declared_h = background.get("HEIGHT")
    path_field = str(background.get("PATH", "") or "").strip().strip('"')
    bg = folder / Path(path_field).name if path_field else folder / "background.png"
    real = image_size(bg) if bg.exists() else None

    issues = []
    if real:
        rw, rh = real
        if declared_w and declared_h:
            try:
                if (int(declared_w), int(declared_h)) != (rw, rh):
                    issues.append(f"WIDTH/HEIGHT {declared_w}x{declared_h} != fondo {rw}x{rh}")
            except (TypeError, ValueError):
                issues.append(f"WIDTH/HEIGHT no numericos: {declared_w}x{declared_h}")
        else:
            issues.append(f"sin WIDTH/HEIGHT (fondo {rw}x{rh})")
        expected_size = BY_DIMS.get((rw, rh))
        if not expected_size:
            issues.append(f"fondo de medida no estandar {rw}x{rh}")
        else:
            if not size_field:
                issues.append(f'sin DISPLAY_SIZE (deberia ser {expected_size})')
            else:
                declared_size = size_field if size_field.endswith('"') else size_field + '"'
                if declared_size != expected_size:
                    issues.append(f'DISPLAY_SIZE {size_field} != {expected_size} (fondo {rw}x{rh})')
                lib_w, lib_h = LIB_SIZES.get(declared_size, (0, 0))
                real_orient = "landscape" if rw >= rh else "portrait"
                if orient_field and orient_field != real_orient and rw != rh:
                    issues.append(f"DISPLAY_ORIENTATION {orient_field} != {real_orient}")
                if not orient_field:
                    issues.append(f"sin DISPLAY_ORIENTATION (deberia ser {real_orient})")
                # El fondo debe caber en la pantalla que la libreria configura
                if (lib_w, lib_h) == (320, 480) and (rw, rh) == (480, 320) and real_orient == "landscape":
                    pass  # correcto: la libreria gira la pantalla
                elif (lib_h, lib_w) != (rw, rh) and (lib_w, lib_h) != (rw, rh):
                    issues.append(f"fondo {rw}x{rh} no encaja en pantalla {lib_w}x{lib_h} de {declared_size}")
    else:
        issues.append(f"fondo no encontrado o no PNG ({bg.name})")

    rows.append((folder.name, size_field or "-", orient_field or "-", real or (0, 0), "; ".join(issues)))

bad = [r for r in rows if r[4]]
print(f"Temas analizados   : {len(rows)}")
print(f"  correctos        : {len(rows) - len(bad)}")
print(f"  con problemas    : {len(bad)}")
print()
if bad:
    print("--- TEMAS 3.5\" (fondo 480x320 / 320x480) CON PROBLEMAS ---")
    for name, size, orient, real, issue in bad:
        if real in ((480, 320), (320, 480)) or size.startswith("3.5"):
            print(f"  {name:38} fondo={real[0]}x{real[1]:<4} size={size:6} orient={orient:9} :: {issue}")
    print()
    print("--- OTROS TAMANOS CON PROBLEMAS ---")
    for name, size, orient, real, issue in bad:
        if not (real in ((480, 320), (320, 480)) or size.startswith("3.5")):
            print(f"  {name:38} fondo={real[0]}x{real[1]:<4} size={size:6} orient={orient:9} :: {issue}")
if VERBOSE:
    print()
    print("--- TODOS LOS TEMAS ---")
    for name, size, orient, real, issue in rows:
        flag = "OK " if not issue else "!! "
        print(f"  {flag}{name:38} fondo={real[0]}x{real[1]:<4} size={size:6} orient={orient}")

# El codigo de salida solo mira los temas de 3.5" (el objetivo del proyecto): los
# ejemplos de otras medidas pueden no declarar WIDTH/HEIGHT y no es un fallo real.
problemas_35 = [r for r in bad if r[3] in ((480, 320), (320, 480)) or r[1].startswith("3.5")]
if problemas_35:
    print()
    print(f"FALLO: {len(problemas_35)} tema(s) de 3.5\" con la resolucion mal declarada")
sys.exit(1 if problemas_35 else 0)
