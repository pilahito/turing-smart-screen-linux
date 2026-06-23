#!/usr/bin/env python3
"""Ventana flotante que muestra la mini pantalla en el PC (espejo en vivo)."""
import argparse
import sys
import time
import tkinter as tk
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    print("Falta Pillow. Ejecuta: .venv/bin/pip install Pillow")
    sys.exit(1)

DEFAULT_IMAGE = Path("screencap.png")
DEFAULT_URL_HINT = "http://localhost:5678"


def monitor_geometry(name: str) -> tuple[int, int, int, int] | None:
    try:
        import subprocess
        out = subprocess.check_output(["xrandr", "--query"], text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        if line.startswith(name):
            parts = line.split()
            for token in parts:
                if "x" in token and "+" in token:
                    wh, xy = token.split("+", 1)
                    w, h = map(int, wh.split("x"))
                    x, y = map(int, xy.split("+"))
                    return x, y, w, h
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Espejo flotante Turing Smart Screen")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--scale", type=float, default=2.5)
    parser.add_argument("--monitor", default="", help="Monitor destino, ej. DP-0 o HDMI-0")
    parser.add_argument("--fps", type=float, default=4.0)
    args = parser.parse_args()

    root = tk.Tk()
    root.title("Turing Smart Screen — espejo")
    root.attributes("-topmost", True)
    root.configure(bg="#111")

    label = tk.Label(root, bg="#111")
    label.pack(padx=4, pady=4)

    hint = tk.Label(
        root,
        text=f"Espejo en vivo · {args.image.name} · Cierra para salir",
        fg="#aaa",
        bg="#111",
        font=("Sans", 9),
    )
    hint.pack(pady=(0, 6))

    photo_ref: dict[str, ImageTk.PhotoImage] = {}
    base_w = base_h = 320

    def refresh() -> None:
        nonlocal base_w, base_h
        path = args.image
        if not path.is_file():
            root.after(int(1000 / args.fps), refresh)
            return
        try:
            img = Image.open(path).convert("RGB")
            base_w, base_h = img.size
            sw, sh = int(base_w * args.scale), int(base_h * args.scale)
            img = img.resize((max(sw, 1), max(sh, 1)), Image.Resampling.NEAREST)
            photo_ref["img"] = ImageTk.PhotoImage(img)
            label.configure(image=photo_ref["img"])
        except OSError:
            pass
        root.after(int(1000 / args.fps), refresh)

    refresh()

    if args.monitor:
        geo = monitor_geometry(args.monitor)
        if geo:
            x, y, mw, mh = geo
            win_w = int(base_w * args.scale) + 8
            win_h = int(base_h * args.scale) + 48
            # Esquina inferior derecha del monitor elegido
            root.geometry(f"{win_w}x{win_h}+{x + mw - win_w - 24}+{y + mh - win_h - 24}")
        else:
            root.geometry(f"{int(base_w * args.scale)}x{int(base_h * args.scale + 40)}+80+80")
    else:
        root.geometry(f"{int(base_w * args.scale)}x{int(base_h * args.scale + 40)}+80+80")

    print(f"Ventana espejo abierta. También: {DEFAULT_URL_HINT}")
    root.mainloop()


if __name__ == "__main__":
    main()