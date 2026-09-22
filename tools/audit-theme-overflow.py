# -*- coding: utf-8 -*-
"""Audita si el texto de cada tema se sale de su caja (WIDTH x HEIGHT).

La libreria compone el texto como valor + unidad (p. ej. "46°C", "100%") y lo dibuja
dentro de la caja declarada en el theme.yaml. Aqui se mide el texto real con la
tipografia y el tamano del tema y se compara con esa caja.

Uso:
    python tools/audit-theme-overflow.py [raiz] [--mm-por-px 0.154]
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

RAIZ = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and not sys.argv[1].startswith("-") \
    else Path(__file__).resolve().parents[1]
TEMAS = RAIZ / "res" / "themes"
FUENTES = RAIZ / "res" / "fonts"

# Unidad que anade la libreria segun el tipo de dato, y valores realistas (sin unidad)
UNIDADES = {
    "TEMPERATURE": ("°C", ["25", "46", "100", "-10"]),
    "PERCENTAGE": ("%", ["5", "55", "100"]),
    "USAGE": ("%", ["5", "55", "100"]),
    "FAN_SPEED": (" RPM", ["1200", "3000"]),
    "FREQUENCY": (" GHz", ["3.6", "5.85"]),
    "POWER": (" W", ["65", "250"]),
    "MEMORY": (" M", ["1024", "16384"]),
    "LOAD": ("", ["0.00", "12.34"]),
    "NET": ("", ["1024.5 kB/s"]),
}

# Valores tipicos por tipo de elemento de fecha/reloj (el reloj no muestra segundos
# salvo que el tema los pida, y el dia/mes son cortos)
FECHAS = {
    "HOUR": ["23:59", "11:59"],
    "MINUTE": ["59"],
    "SECOND": ["59"],
    "DAY": ["30", "1"],
    "MONTH": ["ago", "septiembre"],
    "YEAR": ["2026"],
    "UPTIME": ["9 dias", "23:59:59"],
}
FECHAS_GENERICO = ["23:59", "30", "ago", "10 dias"]

# Tamano fisico de una pantalla 3.5" 480x320 (diagonal 3.5" y relacion 3:2)
MM_POR_PX = 73.97 / 480


def unidad_y_muestras(ruta: list[str]) -> tuple[str, list[str]]:
    """Deduce la unidad y los textos de prueba a partir del camino del elemento."""
    texto = " ".join(ruta).upper()
    for nombre, (unidad, muestras) in UNIDADES.items():
        if nombre in texto:
            return unidad, muestras
    for clave, muestras in FECHAS.items():
        if clave in texto:
            return "", muestras
    if any(clave in texto for clave in ("CLOCK", "DATE", "UPTIME")):
        return "", FECHAS_GENERICO
    return "", ["1234", "9999.9"]


def es_caja_de_texto(ruta: list[str]) -> bool:
    """Solo las cajas de texto (STATS/.../TEXT o static_text), no radiales ni barras."""
    return any(parte.upper() in ("TEXT", "STATIC_TEXT") for parte in ruta)


def elementos(datos, ruta: list[str] | None = None):
    """Recorre el YAML y devuelve los diccionarios de texto (con FONT y FONT_SIZE)."""
    ruta = ruta or []
    if isinstance(datos, dict):
        if "FONT" in datos and "FONT_SIZE" in datos:
            yield ruta, datos
        for clave, valor in datos.items():
            yield from elementos(valor, ruta + [str(clave)])
    elif isinstance(datos, list):
        for indice, valor in enumerate(datos):
            yield from elementos(valor, ruta + [str(indice)])


def medir(texto: str, fuente: Path, tamano: int):
    from PIL import ImageFont

    try:
        tipografia = ImageFont.truetype(str(fuente), int(tamano))
    except OSError:
        return None
    caja = tipografia.getbbox(texto)
    return caja[2] - caja[0], caja[3] - caja[1]


def audit(raiz: Path, mm_por_px: float = MM_POR_PX) -> int:
    temas = sorted(raiz.glob("res/themes/*/theme.yaml"))
    problemas = []
    sin_fuente = {}
    for tema_yaml in temas:
        nombre = tema_yaml.parent.name
        try:
            datos = yaml.safe_load(tema_yaml.read_text(encoding="utf-8", errors="replace")) or {}
        except Exception:
            continue
        for ruta, elemento in elementos(datos):
            if not es_caja_de_texto(ruta):
                continue
            fuente_rel = str(elemento.get("FONT", ""))
            fuente = raiz / "res" / "fonts" / fuente_rel
            if not fuente.exists():
                sin_fuente.setdefault(fuente_rel, []).append(nombre)
                continue
            tamano = elemento.get("FONT_SIZE", 10)
            ancho_caja = int(elemento.get("WIDTH", 0) or 0)
            alto_caja = int(elemento.get("HEIGHT", 0) or 0)
            if "STATIC_TEXT" in " ".join(ruta).upper() or elemento.get("TEXT"):
                # Texto fijo escrito por el autor: se mide tal cual
                literal = str(elemento.get("TEXT") or elemento.get("STRING") or "")
                muestras = [literal] if literal else []
                unidad, por_defecto = "", []
            else:
                unidad, muestras = unidad_y_muestras(ruta)
                por_defecto = []
            for muestra in (muestras or por_defecto):
                if unidad and elemento.get("SHOW_UNIT", True):
                    muestra = f"{muestra}{unidad}"
                medida = medir(muestra, fuente, tamano)
                if not medida:
                    continue
                ancho, alto = medida
                anclaje = str(elemento.get("ANCHOR", "lt"))
                alineacion = str(elemento.get("ALIGN", "left"))
                if ancho_caja and ancho > ancho_caja:
                    problemas.append((nombre, "/".join(ruta[-3:]), muestra, ancho, ancho_caja,
                                      ancho - ancho_caja, "ancho", f"{anclaje}/{alineacion}"))
                if alto_caja and alto > alto_caja:
                    problemas.append((nombre, "/".join(ruta[-3:]), muestra, alto, alto_caja,
                                      alto - alto_caja, "alto", f"{anclaje}/{alineacion}"))
    print(f"Temas analizados: {len(temas)}")
    print(f"Cajas de texto cuyo contenido no cabe: {len(problemas)}")
    print()
    print("Nota: 1 px = 0.154 mm en una pantalla 3.5\" (480x320). Con ANCHOR lt/lm el")
    print("texto crece hacia la derecha desde X, asi que puede salirse de la caja sin")
    print("que se note; con ANCHOR mm/center el desbordamiento es simetrico y si se ve.")
    if problemas:
        print()
        print(f"{'tema':<22} {'elemento':<32} {'texto':<12} {'caja':>5} {'real':>5} {'sobra':>6} "
              f"{'mm':>7} {'anclaje':>12}")
        for nombre, elemento, texto, real, caja, sobra, eje, anclaje in problemas:
            mm = sobra * mm_por_px
            print(f"{nombre:<22} {elemento:<32} {texto:<12} {caja:>5} {real:>5} {sobra:>6} "
                  f"{mm:>6.2f}mm {anclaje:>12} ({eje})")
    if sin_fuente:
        print()
        print("Fuentes referenciadas que NO existen:")
        for fuente, temas_afectados in sorted(sin_fuente.items()):
            print(f"  {fuente}: {len(temas_afectados)} tema(s), p. ej. {temas_afectados[0]}")
    return len(problemas)


if __name__ == "__main__":
    mm = MM_POR_PX
    if "--mm-por-px" in sys.argv:
        mm = float(sys.argv[sys.argv.index("--mm-por-px") + 1])
    sys.exit(0 if audit(RAIZ, mm) == 0 else 1)
