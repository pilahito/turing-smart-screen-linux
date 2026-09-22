#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Sistema de diseño 2026 para Centro Turing.

Todo el aspecto visual (superficies redondeadas, gradientes, glass, sombras,
tipografía) se renderiza con Pillow. Así la interfaz que se ve en la app y las
imágenes de previsualización (--mockup) usan exactamente el mismo código.

Sin dependencias nuevas: Pillow ya es requisito del proyecto.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------------------
C = {
    "bg": "#07090f",
    "bg_soft": "#0b0e16",
    "surface": "#12161f",
    "surface_2": "#171c27",
    "surface_3": "#1e2431",
    "border": "#232a38",
    "border_hi": "#303849",
    "text": "#e9eef7",
    "muted": "#9aa6bd",
    "faint": "#6b7688",
    "accent": "#22d3ee",
    "accent_2": "#7c5cff",
    "ok": "#34d399",
    "warn": "#fbbf24",
    "danger": "#fb7185",
    "on_dark": "#04121a",
}

R = {"card": 20, "tile": 18, "button": 14, "input": 14, "chip": 999, "bar": 999}

SP = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

T = {
    "display": 30,
    "h1": 21,
    "h2": 15,
    "body": 13,
    "small": 11,
    "tiny": 10,
}

SIDEBAR_W = 224
HEADER_H = 84
STATUS_H = 34

# --------------------------------------------------------------------------------------
# Tipografía
# --------------------------------------------------------------------------------------
_WINDOWS = os.name == "nt"
_FONT_CACHE: dict[tuple, ImageFont.FreeTypeFont] = {}

_UI_FONTS = {
    "regular": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf",
        ROOT / "res/fonts/roboto/Roboto-Regular.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ],
    "medium": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "seguisb.ttf",
        ROOT / "res/fonts/roboto/Roboto-Medium.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ],
    "bold": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeuib.ttf",
        ROOT / "res/fonts/roboto/Roboto-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ],
    "light": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeuil.ttf",
        ROOT / "res/fonts/roboto/Roboto-Light.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ],
    "mono": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "CascadiaMono.ttf",
        ROOT / "res/fonts/jetbrains-mono/JetBrainsMono-Regular.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ],
    "mono_bold": [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "CascadiaMono.ttf",
        ROOT / "res/fonts/jetbrains-mono/JetBrainsMono-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ],
}


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    """Devuelve la tipografía solicitada, con cadena de respaldo por sistema."""
    key = (size, weight)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    chosen = None
    for candidate in _UI_FONTS.get(weight, _UI_FONTS["regular"]):
        try:
            if Path(candidate).exists():
                chosen = ImageFont.truetype(str(candidate), size)
                break
        except OSError:
            continue
    if chosen is None:
        chosen = ImageFont.load_default()
    _FONT_CACHE[key] = chosen
    return chosen


def text_size(text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = fnt.getbbox(text or " ")
    return box[2] - box[0], box[3] - box[1]


def tk_font(weight: str = "regular") -> tuple[str, str]:
    """Familia y estilo para los textos que dibuja Tk (nítidos, no van en imagen)."""
    family = "Segoe UI" if _WINDOWS else "DejaVu Sans"
    style = "bold" if weight in ("bold", "medium", "mono_bold") else "normal"
    return family, style


# --------------------------------------------------------------------------------------
# Utilidades de color y primitivas
# --------------------------------------------------------------------------------------
def rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = rgb(color)
    return (r, g, b, alpha)


def mix(a: str, b: str, t: float) -> str:
    """Mezcla dos colores hex (t=0 -> a, t=1 -> b)."""
    ra, ga, ba = rgb(a)
    rb, gb, bb = rgb(b)
    return "#%02x%02x%02x" % (
        int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))


def lighten(color: str, amount: float) -> str:
    return mix(color, "#ffffff", amount)


def darken(color: str, amount: float) -> str:
    return mix(color, "#000000", amount)


def gradient_image(size: tuple[int, int], start: str, end: str, diagonal: bool = False) -> Image.Image:
    """Gradiente vertical (o diagonal) entre dos colores."""
    width, height = size
    base = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(base)
    steps = width + height if diagonal else height
    steps = max(steps, 1)
    for index in range(steps):
        ratio = index / steps
        line_color = mix(start, end, ratio if not diagonal else min(1.0, ratio * 1.4))
        if diagonal:
            draw.line([(index, 0), (0, index)], fill=line_color, width=1)
        else:
            draw.line([(0, index), (width, index)], fill=line_color)
    return base


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


def surface(
    size: tuple[int, int],
    radius: int = R["card"],
    fill: str = C["surface"],
    fill_end: str | None = None,
    border: str | None = C["border"],
    border_width: int = 1,
    highlight: bool = True,
    shadow: int = 0,
    padding: int = 0,
) -> Image.Image:
    """Superficie redondeada con gradiente suave, borde, brillo superior y sombra."""
    width, height = size[0] + padding * 2, size[1] + padding * 2
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    if shadow:
        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(shadow_layer).rounded_rectangle(
            [(padding, padding + shadow // 3), (padding + size[0] - 1, padding + size[1] - 1 + shadow // 3)],
            radius=radius, fill=(0, 0, 0, min(200, 40 + shadow * 6)))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow))
        canvas = Image.alpha_composite(canvas, shadow_layer)

    body = Image.new("RGBA", size, (0, 0, 0, 0))
    if fill_end:
        body = gradient_image(size, fill, fill_end).convert("RGBA")
    else:
        body = Image.new("RGBA", size, rgba(fill))
    body.putalpha(rounded_mask(size, radius))

    inner = ImageDraw.Draw(body)
    if highlight:
        inner.line([(radius // 2, 1), (size[0] - radius // 2, 1)], fill=(255, 255, 255, 16), width=1)
    if border and border_width:
        inner.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius,
                                outline=rgba(border), width=border_width)
    canvas.alpha_composite(body, (padding, padding))
    return canvas


def glass(size: tuple[int, int], radius: int = R["card"], alpha: int = 210, shadow: int = 0) -> Image.Image:
    """Superficie tipo cristal: relleno translúcido con borde luminoso."""
    return surface(size, radius=radius, fill=mix(C["surface"], C["bg_soft"], 0.35),
                   fill_end=mix(C["surface_2"], C["bg_soft"], 0.25),
                   border=C["border_hi"], shadow=shadow)


def draw_text(target: Image.Image, xy: tuple[int, int], text: str, *, size: int = T["body"],
              weight: str = "regular", color: str = C["text"], anchor: str = "la",
              alpha: int = 255) -> None:
    ImageDraw.Draw(target).text(xy, text, font=font(size, weight), fill=rgba(color, alpha), anchor=anchor)


def with_text(size: tuple[int, int], text: str, *, size_px: int = T["body"], weight: str = "regular",
              color: str = C["text"], anchor: str = "la", xy: tuple[int, int] | None = None,
              surface_image: Image.Image | None = None) -> Image.Image:
    """Superficie (o imagen base) con texto dibujado encima."""
    base = surface_image if surface_image is not None else Image.new("RGBA", size, (0, 0, 0, 0))
    if xy is None:
        xy = (SP["lg"], size[1] // 2)
        anchor = "lm"
    draw_text(base, xy, text, size=size_px, weight=weight, color=color, anchor=anchor)
    return base


# --------------------------------------------------------------------------------------
# Componentes
# --------------------------------------------------------------------------------------
def _antialias(size: tuple[int, int], draw_fn, scale: int = 4) -> Image.Image:
    """Dibuja a `scale`x y reduce: bordes suaves sin dependencias externas."""
    big = (size[0] * scale, size[1] * scale)
    layer = Image.new("RGBA", big, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), scale, big)
    return layer.resize(size, Image.LANCZOS)


def icon(name: str, *, size: int = 18, color: str = C["muted"], accent: str | None = None  # noqa: C901
         ) -> Image.Image:
    """Iconos vectoriales (no dependen de que la tipografía tenga el glifo)."""
    paint = accent or color
    width = max(1, size // 9)

    def draw_panel(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        gap = 2 * s
        cell = (box[0] - gap * 3) // 2
        for index, (cx, cy) in enumerate([(gap, gap), (gap * 2 + cell, gap),
                                          (gap, gap * 2 + cell), (gap * 2 + cell, gap * 2 + cell)]):
            radius = 3 * s
            color_now = paint if index == 0 else rgba(paint, 150)
            draw.rounded_rectangle([(cx, cy), (cx + cell, cy + cell)], radius=radius, fill=color_now)

    def draw_themes(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        for index in range(3):
            offset = index * 4 * s
            draw.rounded_rectangle([(2 * s + offset // 2, 3 * s + offset),
                                    (box[0] - 2 * s - offset // 2, box[1] - 6 * s + offset // 2)],
                                   radius=3 * s, outline=rgba(paint, 200 - index * 55), width=width)

    def draw_settings(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        for index, ratio in enumerate((0.3, 0.7, 0.45)):
            y = (4 + index * 5) * s
            draw.line([(2 * s, y), (box[0] - 2 * s, y)], fill=rgba(paint, 170), width=width)
            knob_x = int(2 * s + (box[0] - 4 * s) * ratio)
            draw.ellipse([(knob_x - 3 * s, y - 3 * s), (knob_x + 3 * s, y + 3 * s)], fill=paint)

    def draw_log(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.rounded_rectangle([(2 * s, 3 * s), (box[0] - 2 * s, box[1] - 3 * s)], radius=3 * s,
                               outline=rgba(paint, 190), width=width)
        draw.line([(5 * s, 7 * s), (7 * s, 9 * s)], fill=paint, width=width)
        draw.line([(7 * s, 9 * s), (5 * s, 11 * s)], fill=paint, width=width)
        draw.line([(9 * s, 12 * s), (13 * s, 12 * s)], fill=rgba(paint, 200), width=width)

    def draw_system(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.rounded_rectangle([(4 * s, 4 * s), (box[0] - 4 * s, box[1] - 4 * s)], radius=2 * s,
                               outline=rgba(paint, 200), width=width)
        draw.rectangle([(7 * s, 7 * s), (box[0] - 7 * s, box[1] - 7 * s)], fill=rgba(paint, 120))
        for step in range(3):
            y = (6 + step * 3) * s
            draw.line([(2 * s, y), (4 * s, y)], fill=rgba(paint, 160), width=width)
            draw.line([(box[0] - 4 * s, y), (box[0] - 2 * s, y)], fill=rgba(paint, 160), width=width)

    def draw_about(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.ellipse([(2 * s, 2 * s), (box[0] - 2 * s, box[1] - 2 * s)], outline=rgba(paint, 200), width=width)
        draw.ellipse([(box[0] // 2 - s, 5 * s), (box[0] // 2 + s, 7 * s)], fill=paint)
        draw.line([(box[0] // 2, 9 * s), (box[0] // 2, 13 * s)], fill=paint, width=width)

    def draw_chevron(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.line([(5 * s, 8 * s), (box[0] // 2, 12 * s), (box[0] - 5 * s, 8 * s)],
                  fill=rgba(paint, 210), width=width + s, joint="curve")

    def draw_check(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.line([(4 * s, 9 * s), (8 * s, 13 * s), (14 * s, 5 * s)], fill=paint, width=width + s, joint="curve")

    def draw_play(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.polygon([(6 * s, 4 * s), (14 * s, box[1] // 2), (6 * s, box[1] - 4 * s)], fill=paint)

    def draw_stop(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.rounded_rectangle([(5 * s, 5 * s), (box[0] - 5 * s, box[1] - 5 * s)], radius=2 * s, fill=paint)

    def draw_refresh(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.arc([(3 * s, 3 * s), (box[0] - 3 * s, box[1] - 3 * s)], 40, 320, fill=paint, width=width + s)
        draw.polygon([(box[0] - 7 * s, 2 * s), (box[0] - 2 * s, 6 * s), (box[0] - 8 * s, 8 * s)], fill=paint)

    painters = {"panel": draw_panel, "themes": draw_themes, "settings": draw_settings,
                "log": draw_log, "system": draw_system, "about": draw_about,
                "chevron": draw_chevron, "check": draw_check, "play": draw_play,
                "stop": draw_stop, "refresh": draw_refresh}
    return _antialias((size, size), painters.get(name, draw_panel))


def brand_mark(size: int = 34, accent: str = C["accent"], accent_2: str = C["accent_2"]) -> Image.Image:
    """Logotipo: cuadrado redondeado con gradiente y rombo interior."""
    def paint(draw: ImageDraw.ImageDraw, s: int, box: tuple[int, int]) -> None:
        draw.rounded_rectangle([(s, s), (box[0] - s, box[1] - s)], radius=7 * s, fill=rgba(accent))
        draw.polygon([(box[0] // 2, box[1] // 3), (box[0] * 2 // 3, box[1] // 2),
                      (box[0] // 2, box[1] * 2 // 3), (box[0] // 3, box[1] // 2)],
                     fill=rgba(mix(accent, accent_2, 0.55)))
        draw.polygon([(box[0] // 2, box[1] // 3), (box[0] * 2 // 3, box[1] // 2), (box[0] // 2, box[1] // 2)],
                     fill=(255, 255, 255, 70))

    return _antialias((size, size), paint, scale=4)


def button(label: str, *, state: str = "normal", kind: str = "primary", width: int = 150,
           height: int = 42, icon: str = "") -> Image.Image:
    """Boton redondeado. state: normal | hover | press | disabled."""
    pressed = state == "press"
    hover = state in ("hover", "press")
    disabled = state == "disabled"
    size = (width, height)

    if kind == "primary":
        top, bottom = C["accent"], C["accent_2"]
        if hover:
            top, bottom = lighten(top, 0.12), lighten(bottom, 0.12)
        if pressed:
            top, bottom = darken(top, 0.12), darken(bottom, 0.12)
        text_color = C["on_dark"]
        image = surface(size, radius=R["button"], fill=top, fill_end=bottom,
                        border=lighten(top, 0.25), highlight=False,
                        shadow=0 if pressed else 10, padding=6).crop((6, 6, width + 6, height + 6))
        image = image.resize(size) if image.size != size else image
        weight = "bold"
    elif kind == "danger":
        image = surface(size, radius=R["button"], fill=C["danger"] if not hover else lighten(C["danger"], 0.12),
                        border=lighten(C["danger"], 0.2), highlight=False, shadow=0)
        text_color = "#2b0a11"
        weight = "bold"
    elif kind == "ghost":
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        if hover:
            image = surface(size, radius=R["button"], fill=C["surface_3"], border=C["border_hi"], highlight=False)
        text_color = C["muted"] if not hover else C["text"]
        weight = "medium"
    else:  # secondary
        image = surface(size, radius=R["button"],
                        fill=C["surface_3"] if hover else C["surface_2"],
                        fill_end=None, border=C["border_hi"] if hover else C["border"], highlight=True)
        text_color = C["text"]
        weight = "medium"

    if disabled:
        image = image.copy()
        faded = Image.new("RGBA", size, (0, 0, 0, 0))
        faded.alpha_composite(image)
        image = Image.blend(Image.new("RGBA", size, rgba(C["surface_2"])), faded, 0.45)
        text_color = C["faint"]

    content = f"{icon}  {label}".strip() if icon else label
    offset = 1 if pressed else 0
    draw_text(image, (width // 2, height // 2 + offset), content, size=T["body"],
              weight=weight, color=text_color, anchor="mm")
    return image


def icon_button(glyph: str, *, state: str = "normal", size: int = 36, accent: bool = False) -> Image.Image:
    image = surface((size, size), radius=size // 3,
                    fill=C["surface_3"] if state != "normal" else mix(C["surface_2"], C["bg"], 0.3),
                    border=C["border_hi"] if state != "normal" else C["border"], shadow=0)
    draw_text(image, (size // 2, size // 2), glyph, size=T["h2"], weight="medium",
              color=C["accent"] if accent else C["muted"], anchor="mm")
    return image


def toggle(on: bool, *, width: int = 52, height: int = 30, hover: bool = False) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    track = surface((width, height), radius=height // 2,
                    fill=C["accent"] if on else C["surface_3"],
                    fill_end=C["accent_2"] if on else None,
                    border=lighten(C["accent"], 0.3) if on else C["border_hi"],
                    highlight=False,
                    shadow=6 if on else 0, padding=4).crop((4, 4, width + 4, height + 4))
    track = track.resize((width, height)) if track.size != (width, height) else track
    image.alpha_composite(track)
    thumb = height - 8
    x = width - thumb - 4 if on else 4
    draw = ImageDraw.Draw(image)
    draw.ellipse([(x, 4), (x + thumb, 4 + thumb)], fill=rgba("#ffffff" if on else lighten(C["muted"], 0.35)))
    if hover:
        draw.ellipse([(x, 4), (x + thumb, 4 + thumb)], outline=rgba("#ffffff", 90), width=1)
    return image


def chip(text: str, *, kind: str = "neutral", padding: int = 10, height: int = 24) -> Image.Image:
    palette = {
        "neutral": (C["surface_3"], C["muted"]),
        "accent": (mix(C["accent"], C["bg"], 0.78), C["accent"]),
        "ok": (mix(C["ok"], C["bg"], 0.78), C["ok"]),
        "warn": (mix(C["warn"], C["bg"], 0.78), C["warn"]),
        "danger": (mix(C["danger"], C["bg"], 0.78), C["danger"]),
    }
    fill, text_color = palette.get(kind, palette["neutral"])
    width = int(text_size(text, font(T["small"], "medium"))[0]) + padding * 2
    image = surface((width, height), radius=height // 2, fill=fill, border=None, highlight=False)
    draw_text(image, (width // 2, height // 2), text, size=T["small"], weight="medium",
              color=text_color, anchor="mm")
    return image


def segmented(labels: list[str], active: int, *, height: int = 34, item_padding: int = 18) -> Image.Image:
    widths = [int(text_size(label, font(T["small"], "medium"))[0]) + item_padding * 2 for label in labels]
    total = sum(widths) + 8
    image = surface((total, height), radius=height // 2, fill=mix(C["bg"], C["surface"], 0.5),
                    border=C["border"], highlight=False)
    x = 4
    for index, (label, width) in enumerate(zip(labels, widths)):
        if index == active:
            pill = surface((width, height - 8), radius=(height - 8) // 2, fill=C["accent"],
                           fill_end=C["accent_2"], border=None, highlight=False)
            image.alpha_composite(pill, (x, 4))
            draw_text(image, (x + width // 2, height // 2), label, size=T["small"], weight="bold",
                      color=C["on_dark"], anchor="mm")
        else:
            draw_text(image, (x + width // 2, height // 2), label, size=T["small"], weight="medium",
                      color=C["muted"], anchor="mm")
        x += width
    return image


def progress(value: float, *, width: int = 240, height: int = 8, color: str = C["accent"],
             track: str = C["surface_3"]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    image.alpha_composite(surface((width, height), radius=height // 2, fill=track, border=None, highlight=False))
    filled = max(height, int(width * max(0.0, min(1.0, value))))
    if filled > 0:
        bar = surface((filled, height), radius=height // 2, fill=color, fill_end=lighten(color, 0.18),
                      border=None, highlight=False)
        image.alpha_composite(bar, (0, 0))
    return image


def sparkline(values: list[float], *, width: int = 220, height: int = 44, color: str = C["accent"]) -> Image.Image:
    """Mini-grafica de área con degradado (para las tarjetas de estado)."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if len(values) < 2:
        return image
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    points = []
    for index, value in enumerate(values):
        x = index * (width - 1) / (len(values) - 1)
        y = height - 4 - ((value - low) / span) * (height - 10)
        points.append((x, y))

    area = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(area).polygon(points + [(width - 1, height), (0, height)], fill=rgba(color, 70))
    fade = Image.new("L", (width, height), 0)
    fade_draw = ImageDraw.Draw(fade)
    for y in range(height):
        fade_draw.line([(0, y), (width, y)], fill=int(255 * (1 - y / height) ** 1.5))
    area.putalpha(Image.composite(area.getchannel("A"), Image.new("L", (width, height), 0), fade))
    image.alpha_composite(area)
    ImageDraw.Draw(image).line(points, fill=rgba(color), width=2, joint="curve")
    return image


def stat_tile(label: str, value: str, *, sub: str = "", width: int = 250, height: int = 132,
              accent: str = C["accent"], spark: list[float] | None = None, ok: bool = True) -> Image.Image:
    image = glass((width, height), radius=R["tile"], shadow=8)
    dot_color = accent if ok else C["danger"]
    draw = ImageDraw.Draw(image)
    draw.ellipse([(SP["lg"], SP["lg"] + 1), (SP["lg"] + 8, SP["lg"] + 9)], fill=rgba(dot_color))
    draw_text(image, (SP["lg"] + 16, SP["lg"] + 4), label.upper(), size=T["tiny"], weight="medium",
              color=C["muted"])
    draw_text(image, (SP["lg"], SP["lg"] + 26), value, size=25, weight="bold", color=C["text"])
    if spark:
        mini = sparkline(spark, width=width // 2 - SP["lg"], height=38, color=accent)
        image.alpha_composite(mini, (width - mini.width - SP["lg"], height - mini.height - SP["lg"] - 6))
    if sub:
        draw_text(image, (SP["lg"], height - SP["lg"] - 12), sub, size=T["small"], weight="regular",
                  color=C["faint"])
    return image


def slider(value: float, *, width: int = 300, height: int = 26, color: str = C["accent"]) -> Image.Image:
    """Deslizador con pista redondeada, relleno en degradado y tirador."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    track_height = 8
    track_y = (height - track_height) // 2
    image.alpha_composite(surface((width, track_height), radius=track_height // 2, fill=C["surface_3"],
                                  border=None, highlight=False), (0, track_y))
    filled = int(width * max(0.0, min(1.0, value)))
    if filled > 6:
        image.alpha_composite(surface((filled, track_height), radius=track_height // 2, fill=color,
                                      fill_end=C["accent_2"], border=None, highlight=False), (0, track_y))
    knob = height - 4
    knob_x = max(0, min(width - knob, filled - knob // 2))
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([(knob_x, 2), (knob_x + knob, 2 + knob)], fill=(0, 0, 0, 110))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)))
    draw = ImageDraw.Draw(image)
    draw.ellipse([(knob_x, 2), (knob_x + knob, 2 + knob)], fill=rgba("#ffffff"))
    draw.ellipse([(knob_x + 5, 7), (knob_x + knob - 5, 2 + knob - 5)], fill=rgba(color, 90))
    return image


def fit_within(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Escala la imagen completa para que quepa en la caja (contain)."""
    copy = image.copy()
    copy.thumbnail(box, Image.LANCZOS)
    return copy


def cover(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    """Escala y recorta centrado para llenar toda la caja (cover)."""
    target_w, target_h = box
    scale = max(target_w / image.width, target_h / image.height)
    resized = image.resize((max(target_w, round(image.width * scale)),
                            max(target_h, round(image.height * scale))), Image.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def theme_preview(background: Path | None, name: str, detail: str, *, width: int = 560, height: int = 400,
                  badges: list[tuple[str, str]] | None = None) -> Image.Image:
    """Tarjeta de vista previa del tema.

    La foto llena todo el area disponible: detras va la misma imagen ampliada y
    desenfocada (cover) y encima la imagen nitida completa (contain). Asi ninguna
    medida deja huecos: 480x320 horizontal, 320x480 vertical, 5", 8.8"...
    """
    caption_h = 118
    inner_w = max(80, width - SP["lg"] * 2)
    box_h = max(120, height - caption_h - SP["lg"])
    image = glass((width, height), radius=R["card"], shadow=14)
    area = Image.new("RGBA", (inner_w, box_h), rgba(C["bg_soft"]))

    shot = None
    if background and Path(background).exists():
        try:
            with Image.open(background) as source:
                shot = source.convert("RGB")
        except Exception:
            shot = None

    if shot is not None:
        backdrop = cover(shot, (inner_w, box_h)).filter(ImageFilter.GaussianBlur(22))
        backdrop = Image.blend(backdrop, Image.new("RGB", backdrop.size, rgb(C["bg_soft"])), 0.42)
        backdrop = backdrop.convert("RGBA")
        area.alpha_composite(backdrop)
        sharp = fit_within(shot, (inner_w - 10, box_h - 10)).convert("RGBA")
        sharp.putalpha(rounded_mask(sharp.size, 8))
        area.alpha_composite(sharp, ((inner_w - sharp.width) // 2, (box_h - sharp.height) // 2))
    else:
        draw_text(area, (inner_w // 2, box_h // 2), "sin vista previa", size=T["small"],
                  color=C["faint"], anchor="mm")

    area.putalpha(rounded_mask((inner_w, box_h), 14))
    ImageDraw.Draw(area).rounded_rectangle([(0, 0), (inner_w - 1, box_h - 1)], radius=14,
                                           outline=rgba(C["border_hi"]), width=1)
    image.alpha_composite(area, (SP["lg"], SP["lg"]))

    draw_text(image, (SP["lg"], height - 92), name, size=T["h1"], weight="bold", color=C["text"])
    draw_text(image, (SP["lg"] + 1, height - 62), detail, size=T["small"], color=C["muted"])
    x = SP["lg"]
    for text, kind in (badges or []):
        badge = chip(text, kind=kind)
        image.alpha_composite(badge, (x, height - 42))
        x += badge.width + SP["sm"]
    return image


def control_card(*, width: int = 470, height: int = 400, brightness: float = 0.35,
                 theme_name: str = "", running: bool = True) -> Image.Image:
    """Tarjeta de control: tema, brillo y acciones."""
    image = glass((width, height), radius=R["card"], shadow=12)
    draw_text(image, (SP["lg"], SP["lg"]), "Control del monitor", size=T["h2"], weight="bold")
    draw_text(image, (SP["lg"], SP["lg"] + 44), "TEMA ACTIVO", size=T["tiny"], weight="medium", color=C["muted"])
    field = surface((width - SP["lg"] * 2, 42), radius=R["input"], fill=C["surface_2"], border=C["border_hi"])
    draw_text(field, (SP["md"], 21), theme_name or "—", size=T["body"], color=C["text"], anchor="lm")
    field.alpha_composite(icon("chevron", size=16, color=C["muted"]), (field.width - SP["lg"] - 12, 13))
    image.alpha_composite(field, (SP["lg"], SP["lg"] + 66))

    draw_text(image, (SP["lg"], SP["lg"] + 128), "BRILLO", size=T["tiny"], weight="medium", color=C["muted"])
    image.alpha_composite(slider(brightness, width=width - SP["lg"] * 2 - 66), (SP["lg"], SP["lg"] + 148))
    draw_text(image, (width - SP["lg"], SP["lg"] + 152), f"{int(brightness * 100)}%", size=T["body"],
              weight="bold", color=C["accent"], anchor="rm")

    y = height - 96
    image.alpha_composite(button("Encender", kind="primary", width=140, height=44), (SP["lg"], y))
    image.alpha_composite(button("Apagar", kind="danger", width=120, height=44), (SP["lg"] + 152, y))
    image.alpha_composite(button("Reiniciar", kind="secondary", width=140, height=44),
                          (SP["lg"] + 284, y))
    image.alpha_composite(button("Aplicar tema y brillo", kind="secondary",
                                 width=max(120, width - SP["lg"] * 2), height=40),
                          (SP["lg"], height - 152))
    return image


def section_title(title: str, subtitle: str = "", *, width: int = 900, height: int = 62) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_text(image, (0, 8), title, size=T["display"], weight="bold", color=C["text"])
    if subtitle:
        draw_text(image, (2, 44), subtitle, size=T["small"], weight="regular", color=C["muted"])
    return image


def nav_item(label: str, icon_name: str, *, active: bool = False, hover: bool = False,
             width: int = SIDEBAR_W - 24, height: int = 44) -> Image.Image:
    if active:
        image = surface((width, height), radius=R["button"], fill=mix(C["accent"], C["bg"], 0.86),
                        fill_end=mix(C["accent_2"], C["bg"], 0.9), border=mix(C["accent"], C["bg"], 0.6),
                        highlight=False)
    elif hover:
        image = surface((width, height), radius=R["button"], fill=C["surface_2"], border=C["border"],
                        highlight=False)
    else:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if active:
        draw.rounded_rectangle([(0, height // 2 - 10), (3, height // 2 + 10)], radius=2, fill=rgba(C["accent"]))
    image.alpha_composite(icon(icon_name, size=18, color=C["muted"], accent=C["accent"] if active else None),
                          (SP["lg"] - 2, (height - 18) // 2))
    draw_text(image, (SP["lg"] + 32, height // 2), label, size=T["body"],
              weight="medium" if active else "regular",
              color=C["text"] if active else C["muted"], anchor="lm")
    return image


def hero_backdrop(size: tuple[int, int], *, accent: str = C["accent"], accent_2: str = C["accent_2"]) -> Image.Image:
    """Fondo del encabezado: gradiente oscuro con dos resplandores de acento."""
    width, height = size
    image = gradient_image(size, mix(C["bg"], accent, 0.10), mix(C["bg"], accent_2, 0.06)).convert("RGBA")
    for color, center, radius in ((accent, (width * 0.18, -20), max(width, height) * 0.55),
                                  (accent_2, (width * 0.72, height * 0.2), max(width, height) * 0.5)):
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse(
            [(center[0] - radius, center[1] - radius), (center[0] + radius, center[1] + radius)],
            fill=rgba(color, 46))
        glow = glow.filter(ImageFilter.GaussianBlur(radius * 0.45))
        image = Image.alpha_composite(image, glow)
    return image


def app_backdrop(size: tuple[int, int]) -> Image.Image:
    """Fondo de la ventana: degradado muy oscuro con resplandor superior."""
    width, height = size
    image = gradient_image(size, mix(C["bg"], C["accent_2"], 0.06), C["bg"]).convert("RGBA")
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [(-width * 0.2, -height * 0.5), (width * 0.8, height * 0.35)], fill=rgba(C["accent"], 24))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    return Image.alpha_composite(image, glow)


def list_row(name: str, *, detail: str = "", active: bool = False, hover: bool = False,
             width: int = 560, height: int = 46, accent: str = C["accent"]) -> Image.Image:
    if active:
        image = surface((width, height), radius=R["button"], fill=mix(accent, C["bg"], 0.84),
                        border=mix(accent, C["bg"], 0.55), highlight=False)
    elif hover:
        image = surface((width, height), radius=R["button"], fill=C["surface_2"], border=C["border"],
                        highlight=False)
    else:
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_text(image, (SP["lg"], height // 2), name, size=T["body"],
              weight="medium" if active else "regular",
              color=C["text"] if active else C["muted"], anchor="lm")
    if detail:
        draw_text(image, (width - SP["lg"], height // 2), detail, size=T["small"],
                  weight="regular", color=C["accent"] if active else C["faint"], anchor="rm")
    return image


def log_view(lines: list[str], *, width: int = 900, height: int = 460) -> Image.Image:
    """Consola de registro con colores por nivel."""
    image = surface((width, height), radius=R["card"], fill="#0a0d13", fill_end="#070a0f",
                    border=C["border"], shadow=10)
    draw = ImageDraw.Draw(image)
    y = SP["lg"]
    line_height = 17
    for raw in lines[-(height // line_height - 2):]:
        color = C["muted"]
        upper = raw.upper()
        if "[ERROR]" in upper or "ERROR" in upper:
            color = C["danger"]
        elif "[WARNING]" in upper or "WARN" in upper:
            color = C["warn"]
        elif "[INFO]" in upper:
            color = C["ok"]
        draw.text((SP["lg"], y), raw[:150], font=font(T["small"], "mono"), fill=rgba(color))
        y += line_height
    return image


def app_icon(size: int = 256) -> Image.Image:
    """Icono de la aplicacion: marca del proyecto sobre cuadrado redondeado."""
    return brand_mark(size)


def save_app_icon(ico_path: Path, png_path: Path | None = None, size: int = 256) -> list[Path]:
    """Guarda el icono como .ico multiresolucion (y opcionalmente .png)."""
    written: list[Path] = []
    icon = app_icon(size)
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    icon.save(ico_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                             (128, 128), (256, 256)])
    written.append(ico_path)
    if png_path:
        png_path.parent.mkdir(parents=True, exist_ok=True)
        icon.save(png_path, format="PNG")
        written.append(png_path)
    return written


def social_banner(path: Path, *, width: int = 1280, height: int = 640) -> Path:
    """Imagen de presentacion del repositorio (GitHub > Social preview)."""
    image = Image.new("RGBA", (width, height), rgba(C["bg"]))
    image.alpha_composite(gradient_image((width, height), mix(C["bg"], C["accent_2"], 0.16),
                                         mix(C["bg"], C["accent"], 0.06), diagonal=True).convert("RGBA"))
    for color, center, radius in ((C["accent"], (width * 0.22, height * 0.15), width * 0.42),
                                  (C["accent_2"], (width * 0.82, height * 0.85), width * 0.38)):
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([(center[0] - radius, center[1] - radius),
                                      (center[0] + radius, center[1] + radius)], fill=rgba(color, 60))
        image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(radius * 0.5)))

    image.alpha_composite(brand_mark(112), (96, 150))
    draw_text(image, (96, 300), "Centro Turing 3.0", size=64, weight="bold", color=C["text"])
    draw_text(image, (100, 384), "Panel unificado para pantallas Turing / XuanFang",
              size=30, weight="regular", color=C["muted"])
    draw_text(image, (100, 424), "La misma interfaz en Windows y Linux · GPL-3.0 · gratis",
              size=24, weight="regular", color=C["faint"])
    x = 100
    for label, kind in (("Windows", "accent"), ("Linux", "ok"), ("140 temas", "neutral"),
                        ("Sin candados", "warn")):
        badge = chip(label, kind=kind, height=40, padding=20)
        image.alpha_composite(badge, (x, 496))
        x += badge.width + 14
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "PNG")
    return path


# --------------------------------------------------------------------------------------
# Previsualización completa (--mockup)
# --------------------------------------------------------------------------------------
def compose(size: tuple[int, int], layers: list[tuple[Image.Image, tuple[int, int]]]) -> Image.Image:
    canvas = Image.new("RGBA", size, rgba(C["bg"]))
    for image, position in layers:
        canvas.alpha_composite(image, position)
    return canvas


def save_mockups(directory: Path, state: dict) -> list[Path]:  # noqa: C901 - compone 6 paginas
    """Genera una imagen por pagina con el mismo motor que usa la aplicacion."""
    directory.mkdir(parents=True, exist_ok=True)
    width, height = 1440, 900
    written: list[Path] = []

    def shell(title: str, subtitle: str, body: list[tuple[Image.Image, tuple[int, int]]]) -> Image.Image:
        layers: list[tuple[Image.Image, tuple[int, int]]] = [(app_backdrop((width, height)), (0, 0))]
        layers.append((hero_backdrop((width, HEADER_H)), (0, 0)))
        layers.append((brand_mark(36), (SP["xl"], 22)))
        header = Image.new("RGBA", (width - 320, HEADER_H), (0, 0, 0, 0))
        draw_text(header, (0, 20), f"Centro Turing {state.get('version', '3.0')}", size=T["h1"],
                  weight="bold", color=C["text"])
        draw_text(header, (2, 48), "Panel de la mini pantalla USB · Windows y Linux", size=T["small"],
                  color=C["muted"])
        layers.append((header, (SP["xl"] + 48, 0)))
        layers.append((chip(state.get("status_text", "encendida"), kind="ok"), (width - 300, 26)))
        layers.append((chip(state.get("clock", ""), kind="neutral"), (width - 170, 26)))

        sidebar = surface((SIDEBAR_W, height - HEADER_H - STATUS_H), radius=0,
                          fill=mix(C["surface"], C["bg"], 0.45), border=None, highlight=False)
        ImageDraw.Draw(sidebar).line([(SIDEBAR_W - 1, 0), (SIDEBAR_W - 1, sidebar.height)],
                                     fill=rgba(C["border"]))
        layers.append((sidebar, (0, HEADER_H)))
        y = HEADER_H + SP["xl"]
        for index, (label, icon_name) in enumerate(state.get("nav", [])):
            active = index == state.get("nav_active", 0)
            layers.append((nav_item(label, icon_name, active=active), (SP["md"], y)))
            y += 48
        footer = surface((SIDEBAR_W - 24, 62), radius=R["tile"],
                         fill=mix(C["surface_2"], C["bg"], 0.35), border=C["border"], shadow=0)
        draw_text(footer, (SP["lg"], 18), "Gratis y libre", size=T["small"], weight="medium", color=C["muted"])
        draw_text(footer, (SP["lg"], 36), "GPL-3.0 · sin candados", size=T["tiny"], color=C["faint"])
        layers.append((footer, (SP["md"], height - STATUS_H - 78)))
        layers.append((section_title(title, subtitle, width=width - SIDEBAR_W - SP["xxl"] - SP["xl"]),
                       (SIDEBAR_W + SP["xxl"], HEADER_H + SP["lg"])))
        for image, position in body:
            layers.append((image, (SIDEBAR_W + SP["xxl"] + position[0], HEADER_H + SP["lg"] + 70 + position[1])))

        status = surface((width, STATUS_H), radius=0, fill=mix(C["bg"], C["surface"], 0.4), border=None,
                         highlight=False)
        draw_text(status, (SP["xl"], STATUS_H // 2), state.get("status_message", "Listo"), size=T["small"],
                  color=C["muted"], anchor="lm")
        layers.append((status, (0, height - STATUS_H)))
        return compose((width, height), layers)

    tiles = state.get("tiles", [])
    panel_body = []
    for index, tile in enumerate(tiles[:4]):
        panel_body.append((stat_tile(tile["label"], tile["value"], sub=tile.get("sub", ""),
                                     accent=tile.get("accent", C["accent"]), spark=tile.get("spark"),
                                     width=258, height=118), (index * 274, 0)))
    if state.get("preview"):
        preview = state["preview"]
        panel_body.append((preview, (0, 140)))
    if state.get("controls"):
        panel_body.append((state["controls"], (600, 140)))
    written.append(directory / "01-panel.png")
    shell("Panel", "Estado en vivo, vista previa del tema y control rápido.", panel_body).save(written[-1])

    rows = state.get("rows", [])
    themes_body = []
    if state.get("filters"):
        themes_body.append((state["filters"], (0, 0)))
    listing = Image.new("RGBA", (860, 470), (0, 0, 0, 0))
    y = 0
    for index, row in enumerate(rows[:9]):
        listing.alpha_composite(
            list_row(row["name"], detail=row.get("detail", ""),
                     active=index == state.get("row_active", 0),
                     hover=index == (state.get("row_active", 0) + 1),
                     width=860), (0, y))
        y += 50
    themes_body.append((listing, (0, 60)))
    written.append(directory / "02-temas.png")
    shell("Temas", "Catálogo con filtros, búsqueda y vista previa.", themes_body).save(written[-1])

    settings_body = []
    card = glass((620, 300), shadow=10)
    draw_text(card, (SP["lg"], SP["lg"]), "Pantalla y sensores", size=T["h2"], weight="bold")
    rows_y = SP["lg"] + 40
    for label, value in state.get("settings", [])[:5]:
        draw_text(card, (SP["lg"], rows_y), label, size=T["small"], color=C["muted"], anchor="lm")
        field = surface((250, 32), radius=R["input"], fill=C["surface_2"], border=C["border_hi"])
        draw_text(field, (SP["md"], 16), value, size=T["small"], color=C["text"], anchor="lm")
        card.alpha_composite(field, (330, rows_y - 16))
        rows_y += 46
    settings_body.append((card, (0, 0)))
    switches = glass((360, 240), shadow=10)
    draw_text(switches, (SP["lg"], SP["lg"]), "Comportamiento", size=T["h2"], weight="bold")
    for index, (label, on) in enumerate(state.get("switches", [])[:3]):
        y = SP["lg"] + 46 + index * 52
        draw_text(switches, (SP["lg"], y + 15), label, size=T["small"], color=C["muted"], anchor="lm")
        switches.alpha_composite(toggle(on, width=48, height=28), (360 - SP["lg"] - 48, y))
    settings_body.append((switches, (640, 0)))
    written.append(directory / "03-ajustes.png")
    shell("Ajustes", "Edición de config.yaml conservando comentarios y orden.", settings_body).save(written[-1])

    written.append(directory / "04-registro.png")
    shell("Registro", "Seguimiento en vivo del monitor.", [(log_view(state.get("log", []), width=980, height=520),
                                                            (0, 0))]).save(written[-1])

    system_body = []
    info = glass((620, 330), shadow=10)
    draw_text(info, (SP["lg"], SP["lg"]), "Diagnóstico", size=T["h2"], weight="bold")
    for index, (label, value) in enumerate(state.get("diagnostics", [])[:7]):
        y = SP["lg"] + 44 + index * 36
        draw_text(info, (SP["lg"], y), label, size=T["small"], color=C["muted"], anchor="lm")
        draw_text(info, (280, y), str(value), size=T["small"], color=C["text"], anchor="lm")
    system_body.append((info, (0, 0)))
    maintenance = glass((360, 200), shadow=10)
    draw_text(maintenance, (SP["lg"], SP["lg"]), "Mantenimiento", size=T["h2"], weight="bold")
    y = SP["lg"] + 46
    for label in state.get("actions", [])[:3]:
        maintenance.alpha_composite(button(label, kind="secondary", width=300, height=38), (SP["lg"], y))
        y += 46
    system_body.append((maintenance, (640, 0)))
    written.append(directory / "05-sistema.png")
    shell("Sistema", "Arranque automático, dependencias y diagnóstico.", system_body).save(written[-1])

    about = glass((900, 330), shadow=10)
    draw_text(about, (SP["lg"], SP["lg"]), f"Centro Turing {state.get('version', '3.0')}", size=T["h1"],
              weight="bold")
    for index, line in enumerate(state.get("about", [])):
        draw_text(about, (SP["lg"], SP["lg"] + 46 + index * 24), line, size=T["small"], color=C["muted"])
    about.alpha_composite(button("Abrir repositorio", kind="primary", width=200, height=42),
                          (SP["lg"], 240))
    written.append(directory / "06-acerca.png")
    shell("Acerca de", "Software libre y gratuito, sin candados ni compras.", [(about, (0, 0))]).save(written[-1])
    return written


if __name__ == "__main__":  # pragma: no cover - utilidad de linea de comandos
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tmp" / "mockups"
    demo_background = None
    for candidate in ("CircuitoES", "HorizonES", "Cyberdeck", "LandscapeEarth"):
        path = ROOT / "res" / "themes" / candidate / "background.png"
        if path.exists():
            demo_background = path
            break
    demo = {
        "version": "3.0",
        "status_text": "ENCENDIDA",
        "clock": "18:42",
        "nav": [("Panel", "panel"), ("Temas", "themes"), ("Ajustes", "settings"), ("Registro", "log"),
                ("Sistema", "system"), ("Acerca de", "about")],
        "nav_active": 0,
        "status_message": "Listo · 140 temas detectados",
        "tiles": [
            {"label": "Pantalla", "value": "ENCENDIDA", "sub": "PID 29776", "accent": C["ok"],
             "spark": [3, 5, 4, 6, 5, 7, 6, 8, 7, 9, 8, 9]},
            {"label": "Puerto", "value": "COM3", "sub": "3.5\" · revisión A", "accent": C["accent"]},
            {"label": "Brillo", "value": "35%", "sub": "CircuitoES", "accent": C["warn"],
             "spark": [5, 6, 6, 7, 6, 7, 7, 8, 7, 8, 8, 8]},
            {"label": "Sensores", "value": "AUTO", "sub": "LibreHardwareMonitor", "accent": C["accent_2"]},
        ],
        "preview": theme_preview(demo_background, "CircuitoES", "480x320 · horizontal · medida 3.5\"",
                                 badges=[("3.5\"", "accent"), ("horizontal", "ok"), ("140 temas", "neutral")]),
        "controls": control_card(brightness=0.35, theme_name="CircuitoES", running=True),
        "rows": [{"name": name, "detail": detail} for name, detail in [
            ("CircuitoES", "3.5\" · horizontal"), ("HorizonES", "3.5\" · horizontal"),
            ("ConilES", "3.5\" · horizontal"), ("SimpleNeon", "3.5\" · vertical"),
            ("Cyberdeck", "3.5\" · vertical"), ("Terminal", "3.5\" · vertical"),
            ("OnePiece1", "3.5\" · horizontal"), ("LandscapeEarth", "3.5\" · horizontal"),
            ("BigClock", "3.5\" · horizontal")]],
        "row_active": 2,
        "filters": segmented(["Todos", "3.5\" H", "3.5\" V", "5\"", "8.8\""], 1),
        "settings": [("Tema", "CircuitoES"), ("Modo de sensores", "AUTO"), ("Revisión de pantalla", "A"),
                     ("Puerto serie", "COM3"), ("Formato de reloj", "12")],
        "switches": [("Invertir imagen", False), ("Reiniciar al arrancar", True), ("Arranque automático", False)],
        "log": ["22/09 18:19:29 [INFO] Loading theme CircuitoES", "22/09 18:19:30 [DEBUG] Drawing Text: CPU",
                "22/09 18:19:31 [WARNING] Your CPU temperature is not supported yet",
                "22/09 18:19:32 [INFO] Detected Nvidia GPU(s)", "22/09 18:20:04 [INFO] Starting system monitoring",
                "22/09 18:23:44 [ERROR] Cannot open COM port COM3"],
        "diagnostics": [("Sistema", "Windows (win32)"), ("Python", "3.11.9"), ("Entorno virtual", "si"),
                        ("Tkinter", "8.6"), ("Temas instalados", "140"), ("Puertos serie", "COM1, COM3"),
                        ("Registro", "log.log (271 KB)")],
        "actions": ["Aplicar código nuevo (git pull)", "Abrir carpeta del proyecto", "Comprobar actualización"],
        "about": ["Panel de control unificado para pantallas Turing / XuanFang.",
                  "La misma interfaz en Windows y Linux.",
                  "Turing Smart Screen Panel © mathoudebine y colaboradores — GPL-3.0.",
                  "Adaptación en español y edición Linux: pilahito."],
    }
    for path in save_mockups(target, demo):
        print(f"Generado: {path}  ({Image.open(path).size[0]}x{Image.open(path).size[1]})")
