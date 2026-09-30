# -*- coding: utf-8 -*-
"""Genera 4 temas nuevos para la Turing Smart Screen 3.5" (Centro Turing).

  AyistaxNeon   - neon rojo sobre negro, rejilla hexagonal (estilo bot Ayistax)
  SynthwaveES   - retro synthwave: sol, rejilla, morado/rosa/cian
  MatrixES      - terminal verde / lluvia Matrix
  MinimalOscuro - minimal oscuro, blanco/azul, reloj grande

Cada tema se crea SOLO en horizontal (480x320, sufijo _H), que es lo que
muestran Elegir-Tema / Centro Turing. (Las versiones verticales se retiraron.)

Uso:  venv\\Scripts\\python.exe tools\\crear_temas_2026.py
No sobrescribe temas que no haya creado este script (marca .generado_crear_temas_2026).
"""
import math
import random
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "res" / "fonts"
THEMES = ROOT / "res" / "themes"
MARK = ".generado_crear_temas_2026"

JBM_XB = "jetbrains-mono/JetBrainsMono-ExtraBold.ttf"
JBM_B = "jetbrains-mono/JetBrainsMono-Bold.ttf"
JBM_M = "jetbrains-mono/JetBrainsMono-Medium.ttf"
JBM_R = "jetbrains-mono/JetBrainsMono-Regular.ttf"
RM_B = "roboto-mono/RobotoMono-Bold.ttf"
GEF_B = "geforce/GeForce-Bold.ttf"
RACE = "racespace/RACESPACEREGULAR-Extended.otf"
ROB_L = "roboto/Roboto-Light.ttf"
ROB_R = "roboto/Roboto-Regular.ttf"
ROB_M = "roboto/Roboto-Medium.ttf"
MISAKI = "misaki/misaki_gothic.ttf"

_font_cache = {}


def F(rel, size):
    key = (rel, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONTS / rel), size)
    return _font_cache[key]


def rgb(c):
    return ", ".join(str(int(v)) for v in c[:3])


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def gradient(w, h, stops):
    """stops: [(pos 0..1, (r,g,b)), ...] vertical."""
    img = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                c = lerp(c0, c1, (t - p0) / max(1e-6, p1 - p0))
                break
        else:
            c = stops[-1][1]
        d.line([(0, y), (w, y)], fill=tuple(c) + (255,))
    return img


def vignette(img, strength=0.55):
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    steps = 40
    for i in range(steps):
        t = i / steps
        a = int(255 * strength * (1 - t) ** 2)
        d.rectangle([int(w * t / 2.6), int(h * t / 2.6), w - int(w * t / 2.6), h - int(h * t / 2.6)], outline=a, width=max(1, int(min(w, h) / 2.6 / steps) + 1))
    mask = mask.filter(ImageFilter.GaussianBlur(18))
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    black.putalpha(mask)
    img.alpha_composite(black)


def scanlines(img, alpha=26, step=2):
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for y in range(0, h, step):
        d.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    img.alpha_composite(layer)


def glow(img, drawfn, radius=3, passes=2):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    drawfn(ImageDraw.Draw(layer))
    if radius:
        g = layer.filter(ImageFilter.GaussianBlur(radius))
        for _ in range(passes):
            img.alpha_composite(g)
    img.alpha_composite(layer)


def overlay(img, drawfn):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    drawfn(ImageDraw.Draw(layer))
    img.alpha_composite(layer)


def spaced(d, xy, text, font, fill, spacing=1.0, anchor="l"):
    """Texto con espaciado entre letras. anchor: l / r / m (horizontal); y = arriba."""
    x, y = xy
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    if anchor == "r":
        x -= total
    elif anchor == "m":
        x -= total / 2
    for ch, cw in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill, anchor="la")
        x += cw + spacing
    return total


def chamfer(box, c):
    x0, y0, x1, y1 = box
    return [(x0 + c, y0), (x1, y0), (x1, y1 - c), (x1 - c, y1), (x0, y1), (x0, y0 + c)]


def arrow_pts(x, y, up, s=4):
    if up:
        return [(x, y + s), (x + s, y - s + 1), (x + 2 * s, y + s)]
    return [(x, y - s + 2), (x + s, y + s + 1), (x + 2 * s, y - s + 2)]


# --------------------------------------------------------------------- widgets
def T(x, y, w, h, font, size, color, align="left", unit=True, **extra):
    anchor = {"left": "lt", "right": "rt", "center": "mt"}[align]
    d = {"SHOW": True, "SHOW_UNIT": unit, "X": int(x), "Y": int(y), "WIDTH": int(w), "HEIGHT": int(h),
         "FONT": font, "FONT_SIZE": int(size), "FONT_COLOR": rgb(color), "BACKGROUND_IMAGE": "background.png",
         "ALIGN": align, "ANCHOR": anchor}
    if align == "left":
        # sin relleno de espacios a la izquierda (la libreria rellena a MIN_SIZE)
        d["MIN_SIZE"] = 0
    d.update(extra)
    return d


def BAR(x, y, w, h, color):
    return {"SHOW": True, "X": int(x), "Y": int(y), "WIDTH": int(w), "HEIGHT": int(h), "MIN_VALUE": 0,
            "MAX_VALUE": 100, "BAR_COLOR": rgb(color), "BAR_OUTLINE": False, "BACKGROUND_IMAGE": "background.png"}


def LG(x, y, w, h, color, autoscale=False, maxv=100, hist=30, lw=2):
    return {"SHOW": True, "X": int(x), "Y": int(y), "WIDTH": int(w), "HEIGHT": int(h), "MIN_VALUE": 0,
            "MAX_VALUE": maxv, "HISTORY_SIZE": hist, "AUTOSCALE": autoscale, "LINE_COLOR": rgb(color),
            "LINE_WIDTH": lw, "AXIS": False, "AXIS_COLOR": rgb(color), "BACKGROUND_IMAGE": "background.png"}


class Theme:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.stats = {}

    def put(self, path, value):
        d = self.stats
        keys = path.split(".")
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value


# ---------------------------------------------------------------------- estilos
class Style:
    name = "Base"
    led = (255, 255, 255)
    vf = JBM_B      # valores grandes
    vf2 = JBM_M     # valores secundarios
    cf = JBM_XB     # reloj
    lf = JBM_B      # etiquetas pequenas
    tf = JBM_XB     # titulos de tarjeta
    tsize = 11
    lsize = 9
    c1 = c2 = c3 = ct = ct2 = cd = cdown = cup = (255, 255, 255)
    ctrack = (40, 40, 40)
    title_color = (255, 255, 255)

    def label_text(self, t):
        return t

    def title_text(self, t):
        return t

    def background(self, w, h):
        raise NotImplementedError

    def card(self, img, box, title=None, right_title=None):
        pass

    def title(self, img, xy, text, right_title=None, x1=None):
        d = ImageDraw.Draw(img)
        spaced(d, xy, self.title_text(text), F(self.tf, self.tsize), self.title_color + (255,), 1.2)
        if right_title and x1:
            spaced(d, (x1, xy[1] + 1), self.label_text(right_title), F(self.lf, self.lsize), self.cd + (255,), 1.0, "r")

    def label(self, img, xy, text, align="left", color=None):
        d = ImageDraw.Draw(img)
        spaced(d, xy, self.label_text(text), F(self.lf, self.lsize), (color or self.cd) + (255,), 1.0,
               {"left": "l", "right": "r", "center": "m"}[align])

    def track(self, img, box):
        overlay(img, lambda d: d.rectangle(box, fill=self.ctrack + (255,)))

    def graph_area(self, img, box):
        x0, y0, x1, y1 = box

        def dr(d):
            for i in range(1, 4):
                yy = y0 + (y1 - y0) * i / 4
                for xx in range(x0, x1, 4):
                    d.point((xx, yy), fill=self.ctrack + (200,))
        overlay(img, dr)

    def divider(self, img, x0, y, x1):
        overlay(img, lambda d: d.line([(x0, y), (x1, y)], fill=self.ctrack + (255,)))

    def arrow(self, img, x, y, up, color):
        overlay(img, lambda d: d.polygon(arrow_pts(x, y, up), fill=color + (255,)))


class Ayistax(Style):
    name = "AyistaxNeon"
    led = (255, 0, 30)
    tf = GEF_B
    tsize = 12
    c1 = (255, 45, 65)
    c2 = (255, 90, 110)
    c3 = (255, 225, 230)
    ct = (255, 240, 242)
    ct2 = (255, 170, 178)
    cd = (190, 70, 82)
    cdown = (255, 60, 80)
    cup = (255, 200, 205)
    ctrack = (60, 6, 14)
    title_color = (255, 50, 70)

    def background(self, w, h):
        rnd = random.Random(7)
        img = Image.new("RGBA", (w, h), (4, 0, 2, 255))
        # halo rojo de fondo
        overlay(img, lambda d: d.ellipse([-w * 0.3, h * 0.25, w * 1.3, h * 1.1], fill=(70, 0, 12, 90)))
        img = img.filter(ImageFilter.GaussianBlur(40))
        r = 13
        dx, dy = math.sqrt(3) * r, 1.5 * r
        hot = [(w * 0.15, h * 0.2), (w * 0.85, h * 0.75), (w * 0.6, h * 0.35)]
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for row in range(-1, int(h / dy) + 2):
            for col in range(-1, int(w / dx) + 2):
                cx = col * dx + (dx / 2 if row % 2 else 0)
                cy = row * dy
                pts = [(cx + (r - 1) * math.cos(math.radians(60 * i - 30)),
                        cy + (r - 1) * math.sin(math.radians(60 * i - 30))) for i in range(6)]
                inten = 0.22
                for hx, hy in hot:
                    dist = math.hypot(cx - hx, cy - hy) / (max(w, h) * 0.45)
                    inten += max(0, 1 - dist) * 0.55
                inten = min(1, inten)
                if rnd.random() < 0.06:
                    d.polygon(pts, fill=(255, 0, 30, int(30 + 60 * inten)))
                d.polygon(pts, outline=(255, 20, 45, int(40 + 130 * inten)))
        g = layer.filter(ImageFilter.GaussianBlur(2.5))
        img.alpha_composite(g)
        img.alpha_composite(layer)
        vignette(img, 0.6)
        scanlines(img, 30)
        return img

    def card(self, img, box, title=None, right_title=None):
        x0, y0, x1, y1 = box
        pts = chamfer(box, 9)
        overlay(img, lambda d: d.polygon(pts, fill=(10, 0, 4, 222)))
        glow(img, lambda d: d.line(pts + [pts[0]], fill=(255, 25, 50, 255), width=1), radius=3, passes=2)

        def accents(d):
            d.line([(x0 + 9, y0), (x0 + 40, y0)], fill=(255, 120, 130, 255), width=2)
            d.line([(x1 - 30, y1), (x1 - 9, y1)], fill=(255, 120, 130, 255), width=2)
            for i in range(3 if title else 0):
                d.rectangle([x1 - 8 - i * 6, y0 + 4, x1 - 5 - i * 6, y0 + 6], fill=(255, 30, 50, 200))
        glow(img, accents, radius=2, passes=1)
        if title:
            glow(img, lambda d: spaced(d, (x0 + 10, y0 + 6), title, F(self.tf, self.tsize), self.title_color + (255,), 1.5),
                 radius=3, passes=1)
            tl = ImageDraw.Draw(img).textlength(title, font=F(self.tf, self.tsize)) + 1.5 * len(title)
            end = x1 - 30 if not right_title else x1 - 14 - ImageDraw.Draw(img).textlength(right_title, font=F(self.lf, self.lsize)) - len(right_title) - 6
            if end > x0 + 18 + tl:
                overlay(img, lambda d: d.line([(x0 + 16 + tl, y0 + 12), (end, y0 + 12)], fill=(120, 10, 25, 255)))
            if right_title:
                self.label(img, (x1 - 12, y0 + 8), right_title, "right")


class Synthwave(Style):
    name = "SynthwaveES"
    led = (255, 40, 200)
    tf = "jetbrains-mono/JetBrainsMono-ExtraBoldItalic.ttf"
    tsize = 12
    vf = JBM_B
    c1 = (255, 90, 205)
    c2 = (90, 235, 255)
    c3 = (255, 214, 110)
    ct = (250, 240, 255)
    ct2 = (220, 190, 255)
    cd = (190, 140, 230)
    cdown = (90, 235, 255)
    cup = (255, 110, 210)
    ctrack = (60, 25, 90)
    title_color = (100, 235, 255)

    def background(self, w, h):
        rnd = random.Random(3)
        hz = int(h * (0.60 if h > w else 0.58))
        img = gradient(w, h, [(0, (8, 2, 26)), (hz / h * 0.55, (40, 8, 80)), (hz / h, (170, 40, 140)),
                              (hz / h + 0.001, (22, 2, 44)), (1, (8, 0, 22))])
        # estrellas
        def stars(d):
            for _ in range(int(w * h / 900)):
                x, y = rnd.randrange(w), rnd.randrange(int(hz * 0.8))
                a = rnd.randint(60, 220)
                d.point((x, y), fill=(255, 230, 255, a))
        overlay(img, stars)
        # sol
        R = int(min(w, h) * (0.34 if h > w else 0.30))
        cx, cy = w // 2, hz - int(R * 0.15)
        halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse([cx - R * 1.35, cy - R * 1.35, cx + R * 1.35, cy + R * 1.35], fill=(255, 60, 160, 110))
        img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(28)))
        sun = gradient(w, h, [(0, (255, 235, 120)), (max(0.01, (cy - R) / h), (255, 225, 110)),
                              (min(0.99, (cy + R * 0.2) / h), (255, 100, 150)), (1, (230, 40, 160))])
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
        md.rectangle([0, hz, w, h], fill=0)
        gap, y = 2, cy
        while y < hz:
            md.rectangle([0, y, w, y + gap], fill=0)
            y += gap + 7
            gap += 1
        img.paste(sun, (0, 0), mask)
        # montanas
        def mountains(d):
            pts = [(0, hz)]
            x = 0
            while x < w:
                x += rnd.randint(18, 40)
                pts.append((x, hz - rnd.randint(6, int(h * 0.07))))
            pts.append((w, hz))
            d.polygon(pts, fill=(30, 6, 56, 255))
            d.line(pts, fill=(255, 80, 200, 200), width=1)
        overlay(img, mountains)
        # rejilla en perspectiva
        def grid(d):
            vx = w / 2
            for k in range(1, 14):
                t = (k / 13) ** 2.1
                yy = hz + (h - hz) * t
                d.line([(0, yy), (w, yy)], fill=(255, 50, 200, int(120 + 120 * t)), width=1)
            for i in range(-12, 13):
                xb = vx + i * (w / 7)
                d.line([(vx + i * 6, hz), (xb, h)], fill=(255, 50, 200, 200), width=1)
        glow(img, grid, radius=2, passes=2)
        vignette(img, 0.35)
        return img

    def card(self, img, box, title=None, right_title=None):
        x0, y0, x1, y1 = box
        overlay(img, lambda d: d.rounded_rectangle(box, 9, fill=(16, 4, 34, 212)))
        glow(img, lambda d: d.rounded_rectangle(box, 9, outline=(255, 70, 200, 255), width=1), radius=3, passes=2)
        overlay(img, lambda d: d.line([(x0 + 12, y1), (x1 - 12, y1)], fill=(120, 230, 255, 180)))
        if title:
            glow(img, lambda d: spaced(d, (x0 + 11, y0 + 7), title, F(self.tf, self.tsize), self.title_color + (255,), 1.5),
                 radius=2, passes=1)
            if right_title:
                self.label(img, (x1 - 11, y0 + 8), right_title, "right")


KATA = [chr(c) for c in range(0x30A2, 0x30F3)] + list("0123456789Z:.=*+<>")


class Matrix(Style):
    name = "MatrixES"
    led = (0, 255, 60)
    tf = JBM_XB
    lf = JBM_M
    tsize = 11
    lsize = 9
    vf = JBM_B
    cf = JBM_XB
    c1 = (40, 255, 110)
    c2 = (120, 255, 160)
    c3 = (200, 255, 210)
    ct = (210, 255, 220)
    ct2 = (120, 220, 140)
    cd = (40, 160, 70)
    cdown = (40, 255, 110)
    cup = (170, 255, 190)
    ctrack = (8, 44, 16)
    title_color = (60, 255, 120)

    def label_text(self, t):
        return "> " + t.lower().replace(" ", "_")

    def title_text(self, t):
        return "[ " + t.lower() + " ]"

    def background(self, w, h):
        rnd = random.Random(11)
        img = Image.new("RGBA", (w, h), (0, 4, 1, 255))
        font = F(MISAKI, 8)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        cw, ch = 10, 10
        for col in range(0, w, cw):
            for _ in range(rnd.randint(1, 2)):
                head = rnd.randint(0, h // ch + 10)
                length = rnd.randint(6, 26)
                for k in range(length):
                    row = head - k
                    if row < 0 or row * ch > h:
                        continue
                    t = 1 - k / length
                    if k == 0:
                        col_c = (190, 255, 200, 230)
                    else:
                        col_c = (0, int(90 + 150 * t), int(30 + 40 * t), int(40 + 150 * t))
                    d.text((col + 1, row * ch), rnd.choice(KATA), font=font, fill=col_c)
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.6)))
        img.alpha_composite(layer)
        scanlines(img, 45)
        vignette(img, 0.5)
        return img

    def card(self, img, box, title=None, right_title=None):
        x0, y0, x1, y1 = box
        overlay(img, lambda d: d.rectangle(box, fill=(0, 10, 3, 228)))
        glow(img, lambda d: d.rectangle(box, outline=(0, 190, 70, 255), width=1), radius=2, passes=1)

        def corners(d):
            L = 7
            c = (120, 255, 150, 255)
            for (x, y, sx, sy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
                d.line([(x, y), (x + sx * L, y)], fill=c, width=2)
                d.line([(x, y), (x, y + sy * L)], fill=c, width=2)
        overlay(img, corners)
        if title:
            t = self.title_text(title)
            fnt = F(self.tf, self.tsize)
            tl = ImageDraw.Draw(img).textlength(t, font=fnt) + 1.2 * len(t)
            overlay(img, lambda d: d.rectangle([x0 + 8, y0 - 1, x0 + 14 + tl, y0 + 1], fill=(0, 10, 3, 255)))
            glow(img, lambda d: spaced(d, (x0 + 11, y0 + 5), t, fnt, self.title_color + (255,), 1.2), radius=2, passes=1)
            if right_title:
                self.label(img, (x1 - 10, y0 + 7), right_title, "right")


class Minimal(Style):
    name = "MinimalOscuro"
    led = (40, 120, 255)
    vf = ROB_M
    vf2 = ROB_R
    cf = ROB_L
    lf = ROB_M
    lsize = 11
    c1 = (236, 240, 246)
    c2 = (236, 240, 246)
    c3 = (72, 160, 255)
    ct = (236, 240, 246)
    ct2 = (140, 150, 166)
    cd = (120, 130, 146)
    cdown = (72, 160, 255)
    cup = (236, 240, 246)
    ctrack = (34, 38, 48)
    accent = (72, 160, 255)

    def background(self, w, h):
        img = gradient(w, h, [(0, (13, 15, 20)), (1, (18, 21, 28))])
        halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if h > w:
            ImageDraw.Draw(halo).ellipse([-40, -60, w + 40, 190], fill=(40, 90, 200, 38))
        else:
            ImageDraw.Draw(halo).ellipse([-60, -20, 280, 240], fill=(40, 90, 200, 38))
        img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(40)))
        return img


# ---------------------------------------------------------------------- layouts
def big_card(s, img, th, box, title, right_title, base, right_label, right_path, color):
    x0, y0, x1, y1 = box
    iw = x1 - x0 - 20
    s.card(img, box, title, right_title)
    th.put(base + ".TEXT", T(x0 + 10, y0 + 22, 120, 40, s.vf, 36, color))
    s.label(img, (x1 - 10, y0 + 26), right_label, "right")
    th.put(right_path, T(x1 - 132, y0 + 39, 122, 22, s.vf, 17, s.c3, "right"))
    s.graph_area(img, (x0 + 10, y0 + 66, x1 - 10, y0 + 86))
    th.put(base + ".LINE_GRAPH", LG(x0 + 10, y0 + 66, iw, 20, color))
    s.track(img, (x0 + 10, y0 + 92, x1 - 10, y0 + 97))
    th.put(base + ".GRAPH", BAR(x0 + 10, y0 + 92, iw, 6, color))


def small_card(s, img, th, box, title, pct, bar, used, used_label, color):
    x0, y0, x1, y1 = box
    s.card(img, box, title)
    th.put(pct, T(x0 + 10, y0 + 24, 80, 30, s.vf, 24, color))
    s.label(img, (x1 - 10, y0 + 24), used_label, "right")
    th.put(used, T(x1 - 70, y0 + 37, 60, 16, s.vf2, 12, s.ct2, "right", unit=False))
    s.track(img, (x0 + 10, y0 + 62, x1 - 10, y0 + 67))
    th.put(bar, BAR(x0 + 10, y0 + 62, x1 - x0 - 20, 6, color))


def common_intervals(th):
    th.put("CPU.PERCENTAGE.INTERVAL", 1)
    th.put("CPU.FREQUENCY.INTERVAL", 2)
    th.put("GPU.INTERVAL", 1)
    th.put("MEMORY.INTERVAL", 3)
    th.put("DISK.INTERVAL", 10)
    th.put("NET.INTERVAL", 1)
    th.put("WEATHER.INTERVAL", 600)
    th.put("DATE.INTERVAL", 1)


def clock(th, x, y, w, h, font, size, color, align="left", fmt12="h:mm a", fmt24="HH:mm"):
    th.put("DATE.HOUR.TEXT", T(x, y, w, h, font, size, color, align, FORMAT=fmt24, FORMAT_12=fmt12, FORMAT_24=fmt24))


def panel_portrait(s, img, th):
    common_intervals(th)
    s.card(img, (8, 8, 312, 80))
    clock(th, 18, 16, 178, 30, s.cf, 25, s.ct)
    th.put("DATE.WEEKDAY.TEXT", T(186, 17, 116, 18, s.vf, 14, s.c1, "right", FORMAT="EEEE"))
    th.put("DATE.DAY.TEXT", T(186, 36, 116, 16, s.vf2, 12, s.ct2, "right", FORMAT="d MMM yyyy"))
    s.divider(img, 18, 55, 302)
    s.label(img, (18, 63), "TIEMPO")
    th.put("WEATHER.TEMPERATURE.TEXT", T(78, 58, 48, 20, s.vf, 16, s.c3, unit=False))
    th.put("WEATHER.WEATHER_DESCRIPTION.TEXT", T(128, 61, 174, 16, s.vf2, 12, s.ct2))
    big_card(s, img, th, (8, 88, 312, 192), "CPU", "PROCESADOR", "CPU.PERCENTAGE", "FRECUENCIA",
             "CPU.FREQUENCY.TEXT", s.c1)
    big_card(s, img, th, (8, 200, 312, 304), "GPU", "NVIDIA", "GPU.PERCENTAGE", "TEMPERATURA",
             "GPU.TEMPERATURE.TEXT", s.c2)
    small_card(s, img, th, (8, 312, 156, 392), "RAM", "MEMORY.VIRTUAL.PERCENT_TEXT", "MEMORY.VIRTUAL.GRAPH",
               "MEMORY.VIRTUAL.USED", "USO MB", s.c1)
    small_card(s, img, th, (164, 312, 312, 392), "DISCO", "DISK.USED.PERCENT_TEXT", "DISK.USED.GRAPH",
               "DISK.USED.TEXT", "USO GB", s.c2)
    s.card(img, (8, 400, 312, 472), "RED", "ETHERNET")
    s.arrow(img, 18, 427, False, s.cdown)
    s.label(img, (30, 423), "BAJADA")
    th.put("NET.ETH.DOWNLOAD.TEXT", T(18, 440, 134, 20, s.vf, 15, s.cdown, "right"))
    s.arrow(img, 168, 427, True, s.cup)
    s.label(img, (180, 423), "SUBIDA")
    th.put("NET.ETH.UPLOAD.TEXT", T(168, 440, 134, 20, s.vf, 15, s.cup, "right"))


def panel_landscape(s, img, th):
    common_intervals(th)
    s.card(img, (8, 6, 472, 54))
    clock(th, 18, 14, 166, 30, s.cf, 24, s.ct)
    overlay(img, lambda d: d.line([(184, 14), (184, 46)], fill=s.ctrack + (255,)))
    th.put("WEATHER.TEMPERATURE.TEXT", T(194, 11, 60, 22, s.vf, 17, s.c3, unit=False))
    th.put("WEATHER.WEATHER_DESCRIPTION.TEXT", T(194, 34, 156, 15, s.vf2, 11, s.ct2))
    th.put("DATE.WEEKDAY.TEXT", T(352, 12, 110, 18, s.vf, 14, s.c1, "right", FORMAT="EEEE"))
    th.put("DATE.DAY.TEXT", T(352, 33, 110, 16, s.vf2, 12, s.ct2, "right", FORMAT="d MMM yyyy"))
    big_card(s, img, th, (8, 62, 236, 166), "CPU", None, "CPU.PERCENTAGE", "FRECUENCIA", "CPU.FREQUENCY.TEXT", s.c1)
    big_card(s, img, th, (244, 62, 472, 166), "GPU", None, "GPU.PERCENTAGE", "TEMPERATURA", "GPU.TEMPERATURE.TEXT", s.c2)
    small_card(s, img, th, (8, 174, 156, 254), "RAM", "MEMORY.VIRTUAL.PERCENT_TEXT", "MEMORY.VIRTUAL.GRAPH",
               "MEMORY.VIRTUAL.USED", "USO MB", s.c1)
    small_card(s, img, th, (164, 174, 312, 254), "DISCO", "DISK.USED.PERCENT_TEXT", "DISK.USED.GRAPH",
               "DISK.USED.TEXT", "USO GB", s.c2)
    # red: tarjeta alta a la derecha
    x0, y0, x1, y1 = 320, 174, 472, 314
    s.card(img, (x0, y0, x1, y1), "RED")
    s.arrow(img, x0 + 10, y0 + 29, False, s.cdown)
    s.label(img, (x0 + 22, y0 + 25), "BAJADA")
    th.put("NET.ETH.DOWNLOAD.TEXT", T(x0 + 10, y0 + 38, 132, 20, s.vf, 15, s.cdown, "right"))
    s.graph_area(img, (x0 + 10, y0 + 60, x1 - 10, y0 + 76))
    th.put("NET.ETH.DOWNLOAD.LINE_GRAPH", LG(x0 + 10, y0 + 60, 132, 16, s.cdown, autoscale=True, maxv=1, hist=30, lw=1))
    s.arrow(img, x0 + 10, y0 + 89, True, s.cup)
    s.label(img, (x0 + 22, y0 + 85), "SUBIDA")
    th.put("NET.ETH.UPLOAD.TEXT", T(x0 + 10, y0 + 98, 132, 20, s.vf, 15, s.cup, "right"))
    s.graph_area(img, (x0 + 10, y0 + 120, x1 - 10, y0 + 132))
    th.put("NET.ETH.UPLOAD.LINE_GRAPH", LG(x0 + 10, y0 + 120, 132, 12, s.cup, autoscale=True, maxv=1, hist=30, lw=1))
    # franja inferior bajo RAM/DISCO: marca
    s.card(img, (8, 262, 312, 314))
    brand = {"AyistaxNeon": "AYISTAX // CENTRO TURING", "SynthwaveES": "OUTRUN // CENTRO TURING",
             "MatrixES": "david@TITAN:~$ monitor --es"}.get(s.name, "CENTRO TURING")
    d = ImageDraw.Draw(img)
    if s.name == "MatrixES":
        spaced(d, (20, 275), brand, F(JBM_B, 12), s.c1 + (255,), 0.5)
        d.rectangle([20 + d.textlength(brand, font=F(JBM_B, 12)) + len(brand) * 0.5 + 3, 276, 20 + d.textlength(brand, font=F(JBM_B, 12)) + len(brand) * 0.5 + 10, 289], fill=s.c1 + (255,))
    else:
        glow(img, lambda dd: spaced(dd, (160, 276), brand, F(s.tf, 12), s.title_color + (255,), 2.0, "m"), radius=3, passes=1)
    s.label(img, (160, 296), "CENTRO TURING 3.1.0" if s.name == "MatrixES" else "PANEL DE SISTEMA", "center")


def minimal_rows(s, img, th, x0, x1, ys, row_h):
    rows = [("CPU  ·  FRECUENCIA", "CPU.PERCENTAGE.TEXT", "CPU.PERCENTAGE.GRAPH", "CPU.FREQUENCY.TEXT", True),
            ("GPU  ·  TEMPERATURA", "GPU.PERCENTAGE.TEXT", "GPU.PERCENTAGE.GRAPH", "GPU.TEMPERATURE.TEXT", True),
            ("RAM  ·  MB EN USO", "MEMORY.VIRTUAL.PERCENT_TEXT", "MEMORY.VIRTUAL.GRAPH", "MEMORY.VIRTUAL.USED", False),
            ("DISCO  ·  GB EN USO", "DISK.USED.PERCENT_TEXT", "DISK.USED.GRAPH", "DISK.USED.TEXT", False)]
    for (lab, pct, bar, sec, unit), y in zip(rows, ys):
        s.label(img, (x0, y + 2), lab)
        th.put(sec, T(x0, y + 19, 110, 18, s.vf2, 14, s.accent, unit=unit))
        th.put(pct, T(x1 - 100, y - 2, 100, 34, s.vf, 28, s.ct, "right"))
        s.track(img, (x0, y + row_h - 16, x1, y + row_h - 14))
        th.put(bar, BAR(x0, y + row_h - 16, x1 - x0, 3, s.accent))


def minimal_portrait(s, img, th):
    common_intervals(th)
    clock(th, 0, 18, 320, 92, s.cf, 90, s.ct, "center", fmt12="h:mm", fmt24="HH:mm")
    th.put("DATE.WEEKDAY.TEXT", T(0, 116, 150, 20, s.vf, 16, s.accent, "right", FORMAT="EEEE"))
    overlay(img, lambda d: d.ellipse([157, 124, 161, 128], fill=s.cd + (255,)))
    th.put("DATE.DAY.TEXT", T(168, 116, 152, 20, s.vf2, 16, s.ct2, FORMAT="d MMM yyyy"))
    th.put("WEATHER.TEMPERATURE.TEXT", T(0, 146, 146, 26, s.vf, 20, s.ct, "right", unit=False))
    th.put("WEATHER.WEATHER_DESCRIPTION.TEXT", T(158, 150, 162, 20, s.vf2, 14, s.ct2))
    s.divider(img, 24, 186, 296)
    minimal_rows(s, img, th, 24, 296, [200, 254, 308, 362], 54)
    s.divider(img, 24, 418, 296)
    s.arrow(img, 24, 434, False, s.accent)
    s.label(img, (38, 430), "BAJADA")
    th.put("NET.ETH.DOWNLOAD.TEXT", T(24, 448, 140, 20, s.vf, 16, s.ct))
    s.arrow(img, 178, 434, True, s.cd)
    s.label(img, (192, 430), "SUBIDA")
    th.put("NET.ETH.UPLOAD.TEXT", T(178, 448, 118, 20, s.vf, 16, s.ct))


def minimal_landscape(s, img, th):
    common_intervals(th)
    clock(th, 0, 22, 236, 80, s.cf, 76, s.ct, "center", fmt12="h:mm", fmt24="HH:mm")
    th.put("DATE.WEEKDAY.TEXT", T(0, 108, 236, 20, s.vf, 16, s.accent, "center", FORMAT="EEEE"))
    th.put("DATE.DAY.TEXT", T(0, 130, 236, 18, s.vf2, 14, s.ct2, "center", FORMAT="d MMM yyyy"))
    s.divider(img, 40, 160, 196)
    th.put("WEATHER.TEMPERATURE.TEXT", T(0, 170, 236, 34, s.cf, 30, s.ct, "center", unit=False))
    th.put("WEATHER.WEATHER_DESCRIPTION.TEXT", T(0, 208, 236, 18, s.vf2, 13, s.ct2, "center"))
    s.divider(img, 24, 244, 212)
    s.arrow(img, 24, 262, False, s.accent)
    s.label(img, (38, 258), "BAJADA")
    th.put("NET.ETH.DOWNLOAD.TEXT", T(24, 276, 94, 18, s.vf, 13, s.ct))
    s.arrow(img, 126, 262, True, s.cd)
    s.label(img, (140, 258), "SUBIDA")
    th.put("NET.ETH.UPLOAD.TEXT", T(126, 276, 94, 18, s.vf, 13, s.ct))
    overlay(img, lambda d: d.line([(248, 24), (248, 296)], fill=s.ctrack + (255,)))
    minimal_rows(s, img, th, 266, 462, [18, 92, 166, 240], 66)


# ----------------------------------------------------------------------- salida
def write_theme(name, s, w, h, layout, orientation):
    folder = THEMES / name
    if folder.exists() and not (folder / MARK).exists():
        print(f"[SALTADO] {name}: ya existe y no lo creo este script (no se sobrescribe)")
        return False
    folder.mkdir(parents=True, exist_ok=True)
    img = s.background(w, h).convert("RGBA")
    th = Theme(w, h)
    layout(s, img, th)
    img.convert("RGB").save(folder / "background.png", optimize=True)
    data = {
        "author": "Ayistax",
        "display": {"DISPLAY_SIZE": '3.5"', "DISPLAY_ORIENTATION": orientation, "DISPLAY_RGB_LED": rgb(s.led)},
        "static_images": {"BACKGROUND": {"PATH": "background.png", "X": 0, "Y": 0, "WIDTH": w, "HEIGHT": h}},
        "STATS": th.stats,
    }
    head = (f"# {name} - tema 3.5\" {orientation} ({w}x{h}) para Centro Turing 3.1.0\n"
            f"# Generado por tools/crear_temas_2026.py (fondo con PIL). Textos en espanol.\n")
    txt = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=200)
    (folder / "theme.yaml").write_text(head + txt, encoding="utf-8")
    (folder / MARK).write_text("generado por tools/crear_temas_2026.py\n", encoding="utf-8")
    print(f"[OK] {name}: {folder}")
    return True


def main():
    solo = set(sys.argv[1:])
    for s in (Ayistax(), Synthwave(), Matrix(), Minimal()):
        is_min = isinstance(s, Minimal)
        # Solo horizontal (480x320): David usa la pantalla en landscape.
        for suffix, w, h, orient, lay in (
                ("_H", 480, 320, "landscape", minimal_landscape if is_min else panel_landscape),):
            name = s.name + suffix
            if solo and name not in solo:
                continue
            write_theme(name, s, w, h, lay, orient)


if __name__ == "__main__":
    main()
