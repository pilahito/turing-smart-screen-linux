# -*- coding: utf-8 -*-
"""Busca texto que choque con una linea del fondo (bordes de tarjeta, separadores).

La caja declarada puede estar bien y, aun asi, el texto dibujarse encima de una
linea del fondo: es lo que se ve en el "24°C" de BosqueES, cuya tinta empieza en
y=10 justo donde esta la linea (y=8..12).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

BASE = next((Path(a).resolve() for a in sys.argv[1:] if not a.startswith("-")), Path(__file__).resolve().parents[1])
# --familia ES: solo se tiene en cuenta (para el codigo de salida) esa familia de temas
FAMILIA = sys.argv[sys.argv.index("--familia") + 1] if "--familia" in sys.argv else ""
MM_POR_PX = 73.97 / 480.0

UNIDADES = {
    "TEMPERATURE": ("°C", ["25", "46", "100"]),
    "PERCENTAGE": ("%", ["55", "100"]),
    "USAGE": ("%", ["55", "100"]),
    "FAN_SPEED": (" RPM", ["1200"]),
    "FREQUENCY": (" GHz", ["3.6"]),
    "MEMORY": (" M", ["16384"]),
    "LOAD": ("", ["0.00"]),
}
FECHAS = {"HOUR": ["23:59"], "DAY": ["30"], "MONTH": ["ago"], "UPTIME": ["9 dias"]}


def muestras(ruta: list[str]) -> tuple[str, list[str]]:
    texto = " ".join(ruta).upper()
    for clave, (unidad, valores) in UNIDADES.items():
        if clave in texto:
            return unidad, valores
    for clave, valores in FECHAS.items():
        if clave in texto:
            return "", valores
    return "", ["1234"]


def elementos(datos, ruta: list[str] | None = None):
    ruta = ruta or []
    if isinstance(datos, dict):
        if "FONT" in datos and "FONT_SIZE" in datos:
            yield ruta, datos
        for clave, valor in datos.items():
            yield from elementos(valor, ruta + [str(clave)])
    elif isinstance(datos, list):
        for indice, valor in enumerate(datos):
            yield from elementos(valor, ruta + [str(indice)])


def es_texto(ruta: list[str]) -> bool:
    return any(parte.upper() in ("TEXT", "STATIC_TEXT") for parte in ruta)


def brillo_fila(imagen: Image.Image, fila: int, desde: int, hasta: int) -> float:
    valores = [max(imagen.getpixel((col, fila))[:3]) for col in range(desde, hasta)]
    return sum(valores) / max(1, len(valores))


def es_linea(imagen: Image.Image, fila: int, desde: int, hasta: int) -> bool:
    """Una linea: fila clara con filas mas oscuras justo encima y debajo."""
    if fila < 2 or fila >= imagen.size[1] - 2:
        return False
    aqui = brillo_fila(imagen, fila, desde, hasta)
    if aqui < 45:
        return False
    arriba = min(brillo_fila(imagen, fila - 1, desde, hasta), brillo_fila(imagen, fila - 2, desde, hasta))
    abajo = min(brillo_fila(imagen, fila + 1, desde, hasta), brillo_fila(imagen, fila + 2, desde, hasta))
    return (aqui - arriba) > 12 and (aqui - abajo) > 12


def audit(raiz: Path) -> int:
    temas = sorted(raiz.glob("res/themes/*/theme.yaml"))
    choques = []
    for tema_yaml in temas:
        try:
            datos = yaml.safe_load(tema_yaml.read_text(encoding="utf-8", errors="replace")) or {}
        except Exception:
            continue
        disp = datos.get("display") or {}
        tamano = str(disp.get("DISPLAY_SIZE", "")).replace('"', "").strip()
        for ruta, elemento in elementos(datos):
            if not es_texto(ruta):
                continue
            fuente_path = raiz / "res" / "fonts" / str(elemento.get("FONT", ""))
            fondo_path = tema_yaml.parent / str(elemento.get("BACKGROUND_IMAGE", "background.png"))
            if not fuente_path.exists() or not fondo_path.exists():
                continue
            try:
                imagen = Image.open(fondo_path).convert("RGBA")
                fuente = ImageFont.truetype(str(fuente_path), int(elemento.get("FONT_SIZE", 10)))
            except Exception:
                continue
            ancho, alto = imagen.size
            if tamano and tamano not in ("3.5", "2.1", "2.8", "5", "8.8"):
                continue
            x, y = int(elemento.get("X", 0)), int(elemento.get("Y", 0))
            anclaje = str(elemento.get("ANCHOR", "lt"))
            literal = str(elemento.get("TEXT") or "")
            if literal:
                unidad, valores = "", [literal]
            else:
                unidad, valores = muestras(ruta)
            for valor in valores:
                texto = f"{valor}{unidad}" if unidad and elemento.get("SHOW_UNIT", True) else valor
                lienzo = Image.new("RGBA", imagen.size, (0, 0, 0, 0))
                ImageDraw.Draw(lienzo).text((x, y), texto, font=fuente, fill=(255, 255, 255, 255), anchor=anclaje)
                tinta = lienzo.getbbox()
                if not tinta:
                    continue
                izq, arr, der, aba = tinta
                desde, hasta = max(0, izq), min(ancho, der)
                if hasta - desde < 6:
                    continue
                for fila in range(max(0, arr - 3), min(imagen.size[1], aba + 4)):
                    if es_linea(imagen, fila, desde, hasta) and arr <= fila <= aba:
                        choques.append((tema_yaml.parent.name, "/".join(ruta[-3:]), texto, arr, aba, fila))
    print(f"Temas analizados: {len(temas)}")
    print(f"Textos que cruzan una linea del fondo: {len(choques)}")
    if choques:
        print()
        print(f"{'tema':<22} {'elemento':<30} {'texto':<8} {'tinta y':>10} {'linea y':>8} {'mm':>6}")
        for tema, elemento, texto, arr, aba, fila in choques[:40]:
            mm = min(aba - fila, fila - arr) + 1
            print(f"{tema:<22} {elemento:<30} {texto:<8} {arr:>4}..{aba:<4} {fila:>8} {mm * MM_POR_PX:>5.2f}")
        if len(choques) > 40:
            print(f"... y {len(choques) - 40} mas")
    if FAMILIA:
        propios = [c for c in choques if c[0].endswith(FAMILIA)]
        print(f"de la familia {FAMILIA}: {len(propios)}")
        return len(propios)
    return len(choques)


if __name__ == "__main__":
    sys.exit(0 if audit(BASE) == 0 else 1)
