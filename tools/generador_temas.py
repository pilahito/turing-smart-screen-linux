#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generador de temas para Centro Turing (pantallas 3.5") + editor avanzado.

Crea temas nuevos y siempre VALIDOS combinando:
  * una PLANTILLA base: cualquier tema 3.5" ya existente (conserva el diseno y
    las posiciones de los sensores, que ya estan probadas), y
  * una PALETA nueva: rotacion de tono + ajuste de saturacion y brillo, aplicada
    de forma coherente al fondo y a los colores del theme.yaml.

Modos:
  aleatorio        plantilla y paleta al azar.
  ia "<texto>"     la descripcion elige la paleta (rojo, azul, matrix, neon...)
                   y la plantilla que mejor encaja.

Ademas:
  listar           lista las plantillas 3.5" disponibles.
  abrir            abre la carpeta de temas en el Explorador.
  editar <tema>    abre el theme.yaml de un tema para editarlo a mano (avanzado).

Uso:
  python tools/generador_temas.py aleatorio
  python tools/generador_temas.py aleatorio --aplicar
  python tools/generador_temas.py ia "cyberpunk azul neon" --aplicar
  python tools/generador_temas.py editar HorizonES
"""
from __future__ import annotations

import argparse
import colorsys
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("Falta Pillow. Ejecuta:  venv\\Scripts\\python.exe -m pip install Pillow")
    raise SystemExit(1)

def _raiz() -> Path:
    """Carpeta del proyecto (tambien dentro del .exe de PyInstaller)."""
    if getattr(sys, "frozen", False):
        try:
            from turing_center import ROOT as raiz

            return Path(raiz)
        except Exception:  # noqa: BLE001
            return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


ROOT = _raiz()
THEMES = ROOT / "res" / "themes"
CONFIG = ROOT / "config.yaml"

# Coincide con colores tipo "255, 176, 48" (nunca con "X: 16" ni con floats)
COLOR_RE = re.compile(r"(\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})")

# Nota: el tono se maneja en escala 0-255 (la de PIL/colorsys), NO en grados.
# Equivalencias: 0=rojo, 21=naranja, 40=amarillo, 85=verde, 124=turquesa,
# 135=cian, 163=azul, 191=violeta, 212=magenta, 234=rosa.
TONOS_BONITOS = [0, 14, 21, 28, 35, 64, 85, 106, 124, 135, 149, 156, 170, 188, 198, 212, 234]

# Palabras -> tono objetivo (escala 0-255)
CLAVES_TONO: tuple[tuple[tuple[str, ...], int], ...] = (
    (("rojo", "fuego", "sangre", "forge", "forja", "roja"), 0),
    (("naranja", "ambar", "ámbar", "atardecer", "sunset", "calido", "cálido"), 21),
    (("amarillo", "dorado", "oro", "miel"), 40),
    (("verde", "matrix", "bosque", "naturaleza", "esmeralda", "menta"), 90),
    (("turquesa", "agua", "oceano", "océano", "marea", "aqua"), 124),
    (("cian", "cián", "cyan", "hielo", "frio", "frío"), 135),
    (("azul", "cielo", "marino", "noche", "cobalto"), 163),
    (("violeta", "morado", "purpura", "púrpura", "lila", "uv"), 191),
    (("rosa", "magenta", "fucsia", "chicle", "sakura"), 223),
)

# Palabras -> fragmento del nombre de la plantilla preferida
CLAVES_PLANTILLA: tuple[tuple[tuple[str, ...], str], ...] = (
    (("cyberpunk", "neon", "neón", "cyber", "synthwave", "futurista"), "Cyber"),
    (("matrix", "terminal", "hacker", "codigo", "código"), "Terminal"),
    (("minimal", "liso", "simple", "limpio", "elegante"), "Minimal"),
    (("hielo", "frio", "frío", "invierno", "nieve"), "Hielo"),
    (("bosque", "naturaleza", "verde", "selva"), "Bosque"),
    (("atardecer", "sunset", "calido", "cálido", "desierto"), "Atardecer"),
    (("oceano", "océano", "mar", "agua", "marea"), "Marea"),
    (("espacio", "galaxia", "cosmos", "estelar"), "Horizon"),
    (("vaporwave", "retro", "80s"), "Vice"),
    (("fuego", "forja", "industrial", "acero"), "Forja"),
)


# --------------------------------------------------------------------------
# Utilidades de color
# --------------------------------------------------------------------------
def _desplazar_color(r: int, g: int, b: int, dh: int, ds: float, dv: int) -> tuple[int, int, int]:
    """Rota el tono y ajusta saturacion/brillo de un color RGB (0-255)."""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h = (h + dh / 256.0) % 1.0
    s = max(0.0, min(1.0, s * ds))
    v = max(0.0, min(1.0, v + dv / 255.0))
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return int(round(r2 * 255)), int(round(g2 * 255)), int(round(b2 * 255))


def _tono_de(r: int, g: int, b: int) -> int:
    h, _, _ = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return int(round(h * 255)) % 256


def _desplazar_yaml(texto: str, dh: int, ds: float, dv: int) -> str:
    """Rota todos los colores 'R, G, B' del theme.yaml (no toca posiciones ni floats)."""
    def repl(m: re.Match) -> str:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if r > 255 or g > 255 or b > 255:
            return m.group(0)
        nr, ng, nb = _desplazar_color(r, g, b, dh, ds, dv)
        return f"{nr}, {ng}, {nb}"

    return COLOR_RE.sub(repl, texto)


def _desplazar_imagen(img: Image.Image, dh: int, ds: float, dv: int) -> Image.Image:
    """Rota el tono del fondo completo con la misma transformacion que el YAML."""
    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    h = h.point(lambda x: (x + dh) % 256)
    s = s.point(lambda x: max(0, min(255, int(x * ds))))
    v = v.point(lambda x: max(0, min(255, x + dv)))
    return Image.merge("HSV", (h, s, v)).convert("RGB")


# --------------------------------------------------------------------------
# Plantillas
# --------------------------------------------------------------------------
def _leer_yaml(carpeta: Path) -> str:
    ruta = carpeta / "theme.yaml"
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def listar_plantillas(orientacion: str = "landscape") -> list[Path]:
    """Temas 3.5" utilizables como plantilla (fondo + theme.yaml validos)."""
    if not THEMES.is_dir():
        return []
    salida: list[Path] = []
    for carpeta in sorted(THEMES.iterdir()):
        if not carpeta.is_dir():
            continue
        texto = _leer_yaml(carpeta)
        if 'DISPLAY_SIZE: 3.5"' not in texto:
            continue
        if orientacion and f"DISPLAY_ORIENTATION: {orientacion}" not in texto:
            continue
        if not (carpeta / "background.png").exists():
            continue
        salida.append(carpeta)
    return salida


def _tono_base_de(carpeta: Path) -> int:
    """Tono dominante (escala 0-255) del tema: el del FONDO, que es lo que se repinta.

    Se calcula sobre los pixeles con color real (saturados), que es lo que el ojo
    identifica como "el color" del tema. Si no hay fondo, se usa el YAML.
    """
    fondo = carpeta / "background.png"
    if fondo.exists():
        try:
            muestra = Image.open(fondo).convert("RGB").resize((160, 110))
            px = muestra.load()
            cubos: dict[int, int] = {}
            for y in range(muestra.height):
                for x in range(muestra.width):
                    r, g, b = px[x, y]
                    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                    if s > 0.35 and v > 0.30:
                        cubo = int(h * 255)
                        cubos[cubo] = cubos.get(cubo, 0) + 1
            if cubos:
                return max(cubos, key=cubos.get)
        except Exception:  # noqa: BLE001
            pass

    # Respaldo: DISPLAY_RGB_LED o el color mas saturado del theme.yaml
    texto = _leer_yaml(carpeta)
    m = re.search(r"(?m)^\s*DISPLAY_RGB_LED:\s*(\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})", texto)
    if m:
        r, g, b = (int(x) for x in m.groups())
        if max(r, g, b) > 40:
            return _tono_de(r, g, b)
    mejor_tono, mejor_s = 26, 0.0
    for mm in COLOR_RE.finditer(texto):
        r, g, b = (int(x) for x in mm.groups())
        if max(r, g, b) > 255:
            continue
        _, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        if v > 0.5 and s > mejor_s:
            mejor_s, mejor_tono = s, _tono_de(r, g, b)
    return mejor_tono


def _buscar_plantilla(fragmento: str, disponibles: list[Path]) -> Path | None:
    frag = fragmento.lower()
    for carpeta in disponibles:
        if frag in carpeta.name.lower():
            return carpeta
    return None


def _nombre_libre(prefijo: str) -> str:
    """Nombre de tema no usado todavia: Gen01, Gen02, ..."""
    usados = {c.name for c in THEMES.iterdir()} if THEMES.is_dir() else set()
    for i in range(1, 999):
        candidato = f"{prefijo}{i:02d}"
        if candidato not in usados:
            return candidato
    return f"{prefijo}{random.randrange(1000, 9999)}"


# --------------------------------------------------------------------------
# Generacion
# --------------------------------------------------------------------------
def generar(nombre: str | None = None, plantilla: Path | None = None, dh: int = 0,
            ds: float = 1.0, dv: int = 0, orientacion: str = "landscape") -> Path:
    """Crea un tema nuevo a partir de una plantilla + transformacion de color."""
    disponibles = listar_plantillas(orientacion) or listar_plantillas("")
    if not disponibles:
        raise SystemExit('No encuentro temas plantilla con DISPLAY_SIZE: 3.5" en res/themes')
    base = Path(plantilla) if plantilla else random.choice(disponibles)
    if not base.is_absolute():
        base = THEMES / base

    nombre = nombre or _nombre_libre("Gen")
    destino = THEMES / nombre
    if destino.exists():
        raise SystemExit(f'El tema "{nombre}" ya existe. Usa otro nombre (--nombre).')

    shutil.copytree(base, destino)

    # 1) repintar las imagenes con la paleta nueva
    for png in ("background.png", "preview.png"):
        ruta = destino / png
        if ruta.exists():
            try:
                _desplazar_imagen(Image.open(ruta).convert("RGB"), dh, ds, dv).save(ruta)
            except Exception as error:  # noqa: BLE001
                print(f"  (aviso) no se pudo repintar {png}: {error}")

    # 2) recolorear el theme.yaml con la misma transformacion
    ruta_yaml = destino / "theme.yaml"
    texto = ruta_yaml.read_text(encoding="utf-8", errors="replace")
    texto = _desplazar_yaml(texto, dh, ds, dv)
    texto = re.sub(r'(?m)^author:.*$', 'author: "Generador Centro Turing"', texto, count=1)
    cabecera = (
        "# ---------------------------------------------------------------------------\n"
        "# Tema GENERADO por Centro Turing (tools/generador_temas.py)\n"
        f"# Plantilla base   : {base.name}\n"
        f"# Rotacion de tono : {dh}/256    saturacion x{ds:.2f}    brillo {dv:+d}\n"
        "# Es YAML normal: puedes editarlo a mano para ajustar posiciones o colores.\n"
        "# ---------------------------------------------------------------------------\n"
    )
    ruta_yaml.write_text(cabecera + texto, encoding="utf-8")

    return destino


def generar_aleatorio(nombre: str | None = None) -> Path:
    """Tema 3.5" con plantilla y paleta al azar."""
    disponibles = listar_plantillas()
    if not disponibles:
        raise SystemExit('No encuentro temas plantilla con DISPLAY_SIZE: 3.5" en res/themes')
    base = random.choice(disponibles)
    tono_obj = random.choice(TONOS_BONITOS)
    dh = (tono_obj - _tono_base_de(base)) % 256
    return generar(nombre=nombre, plantilla=base, dh=dh,
                   ds=random.choice([0.85, 1.0, 1.15, 1.35]),
                   dv=random.choice([0, 0, 0, 10, -10]))


def generar_con_ia(prompt: str, nombre: str | None = None) -> Path:
    """Tema 3.5" a partir de una descripcion en lenguaje natural."""
    texto = (prompt or "").lower()
    disponibles = listar_plantillas()

    # 1) paleta segun el color pedido
    tono_obj = None
    for claves, tono in CLAVES_TONO:
        if any(k in texto for k in claves):
            tono_obj = tono
            break

    # 2) plantilla segun el estilo pedido
    plantilla = None
    for claves, frag in CLAVES_PLANTILLA:
        if any(k in texto for k in claves):
            plantilla = _buscar_plantilla(frag, disponibles)
            if plantilla:
                break
    if plantilla is None:
        plantilla = random.choice(disponibles) if disponibles else None

    # 3) saturacion y brillo segun el estilo
    ds = 1.0
    if any(k in texto for k in ("neon", "neón", "vibrante", "intenso", "cyberpunk", "fuerte")):
        ds = 1.5
    if any(k in texto for k in ("minimal", "liso", "simple", "limpio", "suave", "pastel")):
        ds = 0.5
    dv = 0
    if any(k in texto for k in ("oscuro", "dark", "negro", "sobrio")):
        dv = -14
    if any(k in texto for k in ("brillante", "luminoso", "claro", "vivo")):
        dv = 12

    # 4) rotacion necesaria para que el color dominante de la plantilla llegue al pedido
    tono_base = _tono_base_de(plantilla) if plantilla else 26
    if tono_obj is None:
        tono_obj = random.choice(TONOS_BONITOS)
    dh = (tono_obj - tono_base) % 256

    return generar(nombre=nombre, plantilla=plantilla, dh=dh, ds=ds, dv=dv)


# --------------------------------------------------------------------------
# Aplicar (config.yaml + reiniciar monitor) y utilidades
# --------------------------------------------------------------------------
def aplicar(nombre: str) -> bool:
    """Pone el tema en config.yaml y reinicia el monitor para verlo ya."""
    if not CONFIG.exists():
        print(f"No encuentro {CONFIG}")
        return False
    # Antes se mataba CUALQUIER proceso con "main.py" en la linea de comandos
    # (tambien otros programas Python del equipo). Ahora se usa la plataforma del
    # Centro Turing, que solo detiene el monitor de esta carpeta.
    carpeta = str(ROOT / "tools")
    if carpeta not in sys.path:
        sys.path.insert(0, carpeta)
    try:
        import turing_center as core
    except Exception as error:  # noqa: BLE001
        print(f"No se pudo cargar turing_center: {error}")
        return False
    editor = core.ConfigEditor(CONFIG)
    if not editor.get("THEME"):
        print("config.yaml no tiene la clave THEME; no se aplica")
        return False
    editor.set("THEME", nombre, "config")
    ok, mensaje = core.make_platform().restart()
    print(mensaje)
    return ok


def abrir_carpeta(ruta: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(ruta)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)])


def editar(nombre: str) -> int:
    """Editor avanzado: abre el theme.yaml de un tema con el programa del sistema."""
    ruta = THEMES / nombre / "theme.yaml"
    if not ruta.exists():
        print(f'No existe el tema "{nombre}" ({ruta})')
        return 1
    print(f"Editando a mano: {ruta}")
    if sys.platform == "win32":
        subprocess.Popen(["notepad.exe", str(ruta)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-t", str(ruta)])
    else:
        subprocess.Popen(["xdg-open", str(ruta)])
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generador de temas 3.5\" para Centro Turing")
    sub = parser.add_subparsers(dest="modo")

    for modo in ("aleatorio", "ia"):
        p = sub.add_parser(modo, help="generar un tema")
        if modo == "ia":
            p.add_argument("prompt", help='descripcion, p. ej. "cyberpunk azul neon"')
        p.add_argument("--nombre", help="nombre del tema nuevo (por defecto GenNN)")
        p.add_argument("--aplicar", action="store_true", help="ponerlo en config.yaml y reiniciar")
        p.add_argument("--json", action="store_true", help="salida en una linea (para el panel)")

    sub.add_parser("listar", help="listar plantillas 3.5\"")
    sub.add_parser("abrir", help="abrir la carpeta de temas")
    p_ed = sub.add_parser("editar", help="abrir un theme.yaml para editarlo a mano")
    p_ed.add_argument("tema")

    args = parser.parse_args(argv)

    if args.modo == "listar":
        for carpeta in listar_plantillas():
            print(carpeta.name)
        return 0
    if args.modo == "abrir":
        abrir_carpeta(THEMES)
        return 0
    if args.modo == "editar":
        return editar(args.tema)
    if args.modo in ("aleatorio", "ia"):
        try:
            if args.modo == "aleatorio":
                destino = generar_aleatorio(nombre=args.nombre)
            else:
                destino = generar_con_ia(args.prompt, nombre=args.nombre)
        except SystemExit as error:
            print(f"ERROR: {error}")
            return 1
        if args.json:
            print(str(destino.name))
        else:
            print(f"Tema creado: {destino.name}")
            print(f"  carpeta : {destino}")
            print("  imagenes: background.png, preview.png")
        if args.aplicar:
            aplicar(destino.name)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
