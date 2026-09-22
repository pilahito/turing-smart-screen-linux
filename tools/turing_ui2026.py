#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Interfaz 2026 de Centro Turing.

Toda la ventana es un lienzo sobre el que se dibujan superficies renderizadas con
Pillow (el mismo motor que genera las previsualizaciones de `--mockup`), de modo
que lo que se ve en la app es exactamente el diseño.

Incluye: navegación lateral con iconos vectoriales, cabecera con degradado y
resplandores, tarjetas de estado con mini-gráficas, catálogo de temas con scroll
y hover, deslizadores, interruptores animados, avisos flotantes y transiciones
entre páginas.
"""
from __future__ import annotations

import queue
import sys
import time
from pathlib import Path

import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parent))

import turing_design as D  # noqa: E402
import turing_center as core  # noqa: E402
from turing_center import (  # noqa: E402
    APP_NAME, VERSION, REPO_URL, ConfigEditor, THEMES_DIR, ThemeInfo, make_platform, scan_themes,
)

try:  # Pillow es imprescindible para esta interfaz
    from PIL import Image, ImageTk
except ImportError as error:  # pragma: no cover
    raise SystemExit("Centro Turing necesita Pillow: pip install -r requirements.txt") from error

SP, C, T, R = D.SP, D.C, D.T, D.R
NAV = (("panel", "Panel", "panel"), ("temas", "Temas", "themes"), ("ajustes", "Ajustes", "settings"),
       ("registro", "Registro", "log"), ("sistema", "Sistema", "system"), ("acerca", "Acerca de", "about"))
LIST_ROW_H = 50
SEGMENTS = [("Todos", "all"), ('3.5" H', "35h"), ('3.5" V', "35v"), ('5"', "5"), ('8.8"', "88")]
# Campos editables de la pagina Ajustes: (clave en config.yaml, etiqueta)
AJUSTES: tuple[tuple[str, str], ...] = (
    ("THEME", "Tema"),
    ("HW_SENSORS", "Modo de sensores"),
    ("REVISION", "Revisión de pantalla"),
    ("COM_PORT", "Puerto serie"),
    ("CLOCK_FORMAT", "Formato de reloj"),
    ("WEATHER_LATITUDE", "Latitud"),
    ("WEATHER_LONGITUDE", "Longitud"),
)
# Tk no entiende los anclajes de Pillow: se traducen.
TK_ANCHOR = {"lm": "w", "mm": "center", "rm": "e", "la": "nw", "lt": "nw", "ma": "n",
             "ra": "ne", "center": "center", "nw": "nw", "n": "n", "ne": "ne", "e": "e",
             "se": "se", "s": "s", "sw": "sw", "w": "w"}


class Scene:
    """Lienzo con caché de superficies, zonas interactivas y transiciones."""

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.cache: dict = {}
        self.images: dict[str, ImageTk.PhotoImage] = {}
        self.hotspots: list[tuple[str, int, int, int, int, object]] = []
        self.hover = ""
        self.offset_x = 0
        self.offset_y = 0

    # -- caché --------------------------------------------------------------------
    def cached(self, key, builder):
        if key not in self.cache:
            self.cache[key] = builder()
        return self.cache[key]

    def clear(self, tag: str = "all") -> None:
        self.canvas.delete(tag)
        if tag == "all":
            self.hotspots.clear()
            self.images.clear()
        else:
            self.hotspots = [spot for spot in self.hotspots if spot[0] != tag]

    # -- dibujo -------------------------------------------------------------------
    def image(self, tag: str, key: str, source: Image.Image, x: int, y: int, anchor: str = "nw") -> None:
        photo = ImageTk.PhotoImage(source)
        self.images[f"{tag}:{key}:{x}:{y}"] = photo
        self.canvas.create_image(x + self.offset_x, y + self.offset_y, image=photo, anchor=anchor, tags=tag)

    def text(self, tag: str, x: int, y: int, value: str, *, size: int = T["body"], weight: str = "regular",
             color: str = C["text"], anchor: str = "nw") -> None:
        family, style = D.tk_font(weight)
        self.canvas.create_text(x + self.offset_x, y + self.offset_y, text=value,
                                anchor=TK_ANCHOR.get(anchor, "nw"),
                                fill=color, font=(family, size, style), tags=tag)

    def hotspot(self, tag: str, key: str, x: int, y: int, width: int, height: int, callback) -> None:
        self.hotspots.append((tag, x + self.offset_x, y + self.offset_y, width, height, key, callback))

    def hit(self, x: int, y: int):
        for _tag, hx, hy, width, height, key, callback in reversed(self.hotspots):
            if hx <= x <= hx + width and hy <= y <= hy + height:
                return key, callback
        return "", None


class App(tk.Tk):
    MIN_WIDTH, MIN_HEIGHT = 1120, 700

    def __init__(self):
        super().__init__()
        self.platform = make_platform()
        self.config_editor = ConfigEditor()
        # Catalogo de temas: se lee una vez al abrir (~1,5 s). El estado del monitor,
        # en cambio, se consulta en segundo plano porque se repite en cada repintado.
        self.themes: list[ThemeInfo] = scan_themes()
        self.themes_ready = True
        self.page = "panel"
        self.filter = "all"
        self.search = ""
        self.theme_index = 0
        self.log_offset = 0
        self.list_offset = 0
        self.brightness = self._brightness()
        self.status_message = "Listo"
        self.busy = ""
        self.autostart = self.platform.autostart_enabled()
        self.toast_message = ""
        self.toast_until = 0.0
        self._spark: dict[str, list[float]] = {key: [0.4] * 12 for key in ("cpu", "ram", "gpu", "disk")}
        self._busy = False
        # El estado del monitor se consulta EN SEGUNDO PLANO y aqui solo se lee el
        # valor cacheado: is_running() recorre todos los procesos y la primera vez
        # importa psutil (~2 s), asi que llamarlo desde render() congelaba la ventana.
        self.status: tuple[bool, str] = (False, "comprobando…")
        self.ports: list[str] = []
        self._status_pending = False
        self._resultados: queue.Queue = queue.Queue()
        # Campos editables de la pagina Ajustes (encima de los dibujados en el lienzo)
        self._ajustes_campos: dict[str, tk.Entry] = {}

        self.title(f"{APP_NAME} {VERSION} — panel de la mini pantalla USB")
        self.configure(bg=C["bg"])
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._apply_window_icon()
        self._apply_geometry()
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0, bd=0, cursor="arrow")
        self.canvas.pack(fill="both", expand=True)
        self.scene = Scene(self.canvas)
        self.search_var = tk.StringVar(value="")
        self.search_entry = tk.Entry(self, textvariable=self.search_var, relief="flat", bd=0,
                                     bg=C["surface_2"], fg=C["text"], insertbackground=C["accent"],
                                     highlightthickness=0, font=(self._font_family(), T["body"]))
        self.search_entry.bind("<KeyRelease>", lambda _e: self._on_search())
        self.search_shown = False

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", self._on_wheel)
        self.canvas.bind("<Button-5>", self._on_wheel)
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self.render)
        self.after(100, self._poll_results)
        self.after(150, self._warm_up)
        self.after(400, self.refresh_status)
        self.after(2000, self._tick)

    # -- estado en segundo plano ---------------------------------------------------
    def _warm_up(self) -> None:
        """Prepara psutil fuera del hilo de la interfaz (importarlo tarda ~2 s)."""
        def task():
            try:
                import psutil  # noqa: F401

                for _ in psutil.process_iter(["pid"]):
                    pass
            except Exception:
                pass
            return True

        self.run_quiet(task, lambda _resultado: None)

    def run_quiet(self, task, done) -> None:
        """Tarea en segundo plano sin bloquear ni avisar (consultas de estado)."""
        import threading

        def worker():
            try:
                resultado = task()
            except Exception:
                resultado = None
            self._resultados.put((done, resultado))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_status(self) -> None:
        """Pide el estado del monitor (y los puertos) sin bloquear la ventana."""
        if self._status_pending:
            return
        self._status_pending = True

        def task():
            return self.platform.is_running(), self.platform.serial_ports()

        def done(resultado):
            self._status_pending = False
            if resultado:
                self.status, self.ports = resultado
                if self.page in ("panel", "sistema", "registro"):
                    self.render()

        self.run_quiet(task, done)

    # -- utilidades ---------------------------------------------------------------
    @staticmethod
    def _font_family() -> str:
        return "Segoe UI" if D._WINDOWS else "DejaVu Sans"

    def _apply_window_icon(self) -> None:
        """Icono propio del proyecto en la ventana y en la barra de tareas."""
        icon_png = core.ROOT / "res" / "icons" / "centro-turing.png"
        icon_ico = core.ROOT / "res" / "icons" / "centro-turing.ico"
        try:
            if not icon_png.exists():
                D.save_app_icon(icon_ico, icon_png)
            self._icon_photo = ImageTk.PhotoImage(Image.open(icon_png))
            self.iconphoto(True, self._icon_photo)
            if D._WINDOWS and icon_ico.exists():
                self.iconbitmap(str(icon_ico))
        except Exception:
            pass  # el icono es cosmetico: nunca debe impedir abrir el panel

    def _brightness(self) -> float:
        try:
            return max(0.0, min(1.0, int(self.config_editor.get("BRIGHTNESS") or 35) / 100))
        except ValueError:
            return 0.35

    def _apply_geometry(self) -> None:
        import json
        import re

        state = {}
        try:
            state = json.loads(core.STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        geometry = state.get("geometry") if isinstance(state, dict) else None
        match = re.match(r"^(\d+)x(\d+)", geometry) if isinstance(geometry, str) else None
        if match and int(match.group(1)) >= self.MIN_WIDTH and int(match.group(2)) >= self.MIN_HEIGHT:
            self.geometry(geometry)
            return
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(1460, max(self.MIN_WIDTH, screen_w - 120))
        height = min(940, max(self.MIN_HEIGHT, screen_h - 140))
        self.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}")

    def _save_state(self) -> None:
        import json

        try:
            if self.winfo_width() < self.MIN_WIDTH or self.winfo_height() < self.MIN_HEIGHT:
                return
            core.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            core.STATE_FILE.write_text(json.dumps({"geometry": self.geometry()}, indent=2), encoding="utf-8")
        except Exception:
            pass

    def notify(self, message: str, error: bool = False) -> None:
        self.status_message = message
        self.toast_message = message
        self.toast_until = time.time() + 5
        self.toast_error = error
        self.render()

    def run_bg(self, label: str, task, done=None) -> None:
        import threading

        if self._busy:
            self.notify("Hay una tarea en curso…", error=True)
            return
        self._busy = True
        self.busy = label
        self.render()

        def worker():
            try:
                result = task()
            except Exception as error:  # pragma: no cover - defensivo
                result = (False, f"Error: {error}")
            # La cola la lee el hilo de la interfaz: Tkinter no admite llamarlo desde
            # otro hilo (after() desde el hilo de trabajo puede fallar en silencio).
            self._resultados.put((lambda valor: self._finish(valor, done), result))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_results(self) -> None:
        """Recoge en el hilo principal lo que terminan las tareas de fondo."""
        try:
            while True:
                callback, valor = self._resultados.get_nowait()
                try:
                    callback(valor)
                except Exception:
                    pass
        except queue.Empty:
            pass
        finally:
            self.after(80, self._poll_results)

    def _finish(self, result, done) -> None:
        self._busy = False
        self.busy = ""
        ok, message = result if isinstance(result, tuple) else (True, str(result))
        if done:
            done(ok, message)
        self.notify(message, error=not ok)

    # -- estado -------------------------------------------------------------------
    def _filtered(self) -> list[ThemeInfo]:
        predicate = core.THEME_FILTERS.get(
            {"all": "Todos", "35h": '3.5" horizontal (480x320)', "35v": '3.5" vertical (320x480)',
             "5": '5" horizontal (800x480)', "88": '8.8" (1920x480)'}.get(self.filter, "Todos"),
            core.THEME_FILTERS["Todos"])
        query = self.search.strip().lower()
        return [theme for theme in self.themes
                if (not query or query in theme.name.lower()) and predicate(theme)]

    def _selected_theme(self) -> ThemeInfo | None:
        themes = self._filtered()
        if not themes:
            return None
        return themes[min(self.theme_index, len(themes) - 1)]

    def _tick(self) -> None:
        try:
            for key in self._spark:
                series = self._spark[key]
                series.append(series[-1] + (0.35 - series[-1]) * 0.3)
                del series[:-12]
            if self.toast_message and time.time() > self.toast_until:
                self.toast_message = ""
            self.refresh_status()
            if self.page in ("panel", "sistema", "registro"):
                self.render()
        finally:
            self.after(2500, self._tick)

    # -- eventos ------------------------------------------------------------------
    def _on_resize(self, event) -> None:
        if event.widget is self:
            self.render()

    def _on_motion(self, event) -> None:
        if getattr(self, "_dragging", False):
            self._update_brightness(event.x)
            return
        key, _ = self.scene.hit(event.x, event.y)
        if key != self.scene.hover:
            self.scene.hover = key
            self.canvas.configure(cursor="hand2" if key else "arrow")
            self.render()

    def _on_click(self, event) -> None:
        self._press = self.scene.hit(event.x, event.y)
        if self._press[0] == "slider":
            self._dragging = True
            self._update_brightness(event.x)
            return
        if self._press[1]:
            self.render(pressed=self._press[0])

    def _on_release(self, event) -> None:
        if getattr(self, "_dragging", False):
            self._dragging = False
            value = int(self.brightness * 100)
            self.run_bg("Guardando brillo", lambda: (self.config_editor.set("BRIGHTNESS", value, "display"),
                                                     f"Brillo {value}%"))
            return
        key, callback = self.scene.hit(event.x, event.y)
        pressed = getattr(self, "_press", ("", None))
        self._press = ("", None)
        if callback and key == pressed[0]:
            callback()
        else:
            self.render()

    def _update_brightness(self, mouse_x: int) -> None:
        rect = getattr(self, "_slider_rect", None)
        if not rect:
            return
        x, width = rect
        self.brightness = max(0.0, min(1.0, (mouse_x - x) / max(1, width)))
        self.render(keep_offset=True, dragging=True)

    def _on_wheel(self, event) -> None:
        delta = 0
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        elif getattr(event, "delta", 0):
            delta = -1 if event.delta > 0 else 1
        if self.page == "temas" and self.scene.hit(event.x, event.y)[0].startswith("row"):
            self.list_offset = max(0, self.list_offset + delta)
        elif self.page == "registro":
            self.log_offset = max(0, self.log_offset - delta)
        else:
            return
        self.render()

    def _on_search(self) -> None:
        self.search = self.search_var.get()
        self.theme_index = 0
        self.list_offset = 0
        self.render()

    def _on_close(self) -> None:
        self._save_state()
        self.destroy()

    # -- acciones -----------------------------------------------------------------
    def go(self, page: str) -> None:
        if page == self.page:
            return
        self.page = page
        self.list_offset = 0
        self._animate_entry()

    def _animate_entry(self) -> None:
        """Deslizamiento suave al cambiar de página."""
        self.render()
        for step in range(4):
            self.scene.offset_x = int(26 * (1 - (step + 1) / 4))
            self.render(keep_offset=True)
            self.update_idletasks()
            time.sleep(0.012)
        self.scene.offset_x = 0
        self.render()

    def act_start(self) -> None:
        self.run_bg("Encendiendo", self.platform.start)

    def act_stop(self) -> None:
        self.run_bg("Apagando", self.platform.stop)

    def act_restart(self) -> None:
        self.run_bg("Reiniciando", self.platform.restart)

    def act_apply(self) -> None:
        theme = self._selected_theme()
        if theme is None and not self.themes_ready:
            self.notify("Cargando el catálogo de temas…")
            return
        if not theme:
            self.notify("No hay tema seleccionado", error=True)
            return
        brightness = int(self.brightness * 100)

        def task():
            anterior = {"THEME": self.config_editor.get("THEME"),
                        "BRIGHTNESS": self.config_editor.get("BRIGHTNESS")}
            self.config_editor.set_many({"THEME": (theme.name, "config"),
                                         "BRIGHTNESS": (brightness, "display")})
            ok, message = self.platform.restart()
            if ok:
                return True, f"{theme.name} aplicado y monitor reiniciado{self._aviso_medida(theme)}"
            # Si no arranca, se deja la configuracion como estaba: mejor volver al
            # tema anterior que dejar la pantalla apagada por un tema que falla.
            if anterior["THEME"]:
                self.config_editor.set_many({"THEME": (anterior["THEME"], "config"),
                                             "BRIGHTNESS": (anterior["BRIGHTNESS"] or 35, "display")},
                                            backup=False)
                vuelto, _ = self.platform.restart()
                aviso = (f"Se ha vuelto a {anterior['THEME']}." if vuelto
                         else f"Configuracion restaurada a {anterior['THEME']}.")
                return False, f"No pude aplicar {theme.name}: {message} {aviso}"
            return False, f"No pude aplicar {theme.name}: {message}"

        self.run_bg(f"Aplicando {theme.name}", task)

    def act_save(self, values: dict) -> None:
        def task():
            changed = self.config_editor.set_many({k: (v, None) for k, v in values.items()})
            return True, f"Guardado: {', '.join(changed) if changed else 'sin cambios'}"

        self.run_bg("Guardando ajustes", task)

    def act_toggle(self, key: str, value: bool) -> None:
        if key == "autostart":
            self.autostart = value
            self.run_bg("Arranque automático", lambda: self.platform.set_autostart(value))
            return
        mapping = {"reverse": "DISPLAY_REVERSE", "reset": "RESET_ON_STARTUP"}
        self.run_bg("Guardando", lambda: (self.config_editor.set(mapping[key], value), "Ajuste guardado"))

    def act_autorefresh(self) -> None:
        self.auto_log = not getattr(self, "auto_log", True)
        self.render()

    def act_copy_log(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(core.tail_file(self.platform.log_file, 500))
        self.notify("Registro copiado al portapapeles")

    def act_open(self, target: Path) -> None:
        self.platform.open_path(target)

    def act_git_pull(self) -> None:
        self.run_bg("Actualizando código", lambda: (
            self.platform._run_code(["git", "-C", str(core.ROOT), "pull", "--ff-only"], timeout=180) == 0,
            "Código actualizado"))

    def act_check_update(self) -> None:
        def task():
            self.platform._run(["git", "-C", str(core.ROOT), "fetch", "--quiet"], timeout=120)
            local = self.platform._run(["git", "-C", str(core.ROOT), "rev-parse", "HEAD"]).strip()[:8]
            remote = self.platform._run(["git", "-C", str(core.ROOT), "rev-parse", "@{u}"]).strip()[:8]
            if not remote:
                return False, f"Sin remoto configurado (local {local})"
            return True, "Al día" if local == remote else f"Nuevas confirmaciones: {local} → {remote}"

        self.run_bg("Comprobando", task)

    def act_extra(self, key: str) -> None:
        scripts = {"fans": "install-fan-modules.sh", "fps": "poll-fps.sh", "virtual": "start-virtual-screen.sh"}
        if key == "admin":
            powershell = "powershell"
            command = (f'Start-Process -FilePath "{self.platform.python_exe()}" '
                       f'-ArgumentList \'"{core.ROOT / "tools" / "lanzar.py"}\' -Verb RunAs')
            self.run_bg("Permisos", lambda: (
                self.platform._run_code([powershell, "-NoProfile", "-Command", command], timeout=60) == 0,
                "Ventana de administrador lanzada"))
            return
        if key == "install":
            # EJECUTAR el instalador, no abrirlo en el editor. Va en su propia
            # consola visible para que se vea el progreso de pip.
            self.act_script("Instalando dependencias", core.ROOT / "Instalar.ps1",
                            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
            return
        if key in ("instalar-linux",):
            self.act_script("Instalando dependencias", core.ROOT / "scripts" / "install-ubuntu.sh", ["bash"])
            return
        script = core.ROOT / "scripts" / scripts.get(key, "")
        if script.exists():
            self.run_bg(script.name, lambda: (self.platform._run_code(["bash", str(script)], timeout=300) == 0,
                                              f"{script.name} finalizado"))
        else:
            self.notify("Acción no disponible", error=True)

    def _aviso_medida(self, theme: ThemeInfo) -> str:
        """Avisa si el tema es de otra medida que la pantalla configurada.

        Pasa a menudo: en la lista salen los 140 temas y hay temas de 2.1\" (480x480)
        o de 8.8\" (1920x480). Se aplican igual, pero conviene saberlo.
        """
        revision = (self.config_editor.get("REVISION") or "").strip().upper()
        medida = {"A": "3.5", "B": "3.5", "D": "3.5", "WEACT_A": "3.5",
                  "WEACT_B": "0.96"}.get(revision, "")
        tamano_tema = (theme.size or "").strip().strip('"')
        if medida and tamano_tema and tamano_tema != medida:
            return f" — ojo: es de {tamano_tema}\" y tu pantalla es {medida}\", puede verse mal"
        return ""

    def act_script(self, label: str, script: Path, shell: list[str]) -> None:
        """Ejecuta un script con su intérprete (nunca lo abre con el editor)."""
        if not script.exists():
            self.notify(f"No encuentro {script.name}", error=True)
            return

        def task():
            code = self.platform.run_visible([*shell, str(script)], cwd=core.ROOT)
            if code == 0:
                return True, f"{script.name}: completado"
            return False, f"{script.name}: terminó con errores (mira la ventana)"

        self.run_bg(label, task)

    # -- render -------------------------------------------------------------------
    def render(self, pressed: str = "", keep_offset: bool = False, dragging: bool = False) -> None:
        width, height = max(self.winfo_width(), self.MIN_WIDTH), max(self.winfo_height(), self.MIN_HEIGHT)
        if not keep_offset:
            self.scene.offset_x = 0
        self.scene.clear("all")
        # Los campos de Ajustes solo se ven en su pagina
        if self.page != "ajustes":
            self._ocultar_campos_ajustes()
        self._dragging = dragging or getattr(self, "_dragging", False)
        self.scene.image("shell", "backdrop", self.scene.cached(
            ("backdrop", width, height), lambda: D.app_backdrop((width, height))), 0, 0)
        self._render_header(width)
        self._render_sidebar(height)
        content_x, content_y = D.SIDEBAR_W + SP["xl"], D.HEADER_H + SP["lg"]
        content_w = width - content_x - SP["xl"]
        content_h = height - content_y - D.STATUS_H - SP["lg"]
        builder = {"panel": self._page_panel, "temas": self._page_temas, "ajustes": self._page_ajustes,
                   "registro": self._page_registro, "sistema": self._page_sistema,
                   "acerca": self._page_acerca}[self.page]
        builder(content_x, content_y, content_w, content_h, pressed)
        self._render_status(width, height)
        self._sync_search_entry(content_x, content_y, content_w)

    def _render_header(self, width: int) -> None:
        self.scene.image("shell", "hero", self.scene.cached(
            ("hero", width), lambda: D.hero_backdrop((width, D.HEADER_H))), 0, 0)
        self.scene.image("shell", "mark", self.scene.cached(("mark",), lambda: D.brand_mark(42)), SP["xl"], 24)
        self.scene.text("shell", SP["xl"] + 58, 22, f"{APP_NAME} {VERSION}", size=T["h1"], weight="bold")
        self.scene.text("shell", SP["xl"] + 59, 50, "Panel de la mini pantalla USB · Windows y Linux",
                        size=T["small"], color=C["muted"])
        running, detail = self.status
        status_chip = self.scene.cached(
            ("chip_status", running, detail),
            lambda: D.chip("ENCENDIDA" if running else "APAGADA", kind="ok" if running else "danger"))
        self.scene.image("shell", "chip", status_chip, width - status_chip.width - 190, 30)
        clock = time.strftime("%H:%M")
        clock_chip = self.scene.cached(("chip_clock", clock), lambda: D.chip(clock, kind="neutral"))
        self.scene.image("shell", "clock", clock_chip, width - clock_chip.width - SP["xl"], 30)

    def _render_sidebar(self, height: int) -> None:
        sidebar_h = height - D.HEADER_H - D.STATUS_H
        self.scene.image("shell", "sidebar", self.scene.cached(("sidebar", sidebar_h), lambda: self._sidebar_bg(
            sidebar_h)), 0, D.HEADER_H)
        y = D.HEADER_H + SP["xl"]
        for key, label, icon in NAV:
            active = key == self.page
            hover = self.scene.hover == f"nav:{key}" and not active
            image = self.scene.cached(("nav", key, active, hover),
                                      lambda lbl=label, ico=icon, a=active, h=hover:
                                      D.nav_item(lbl, ico, active=a, hover=h))
            self.scene.image("shell", f"nav:{key}", image, SP["md"], y)
            self.scene.hotspot("shell", f"nav:{key}", SP["md"], y, image.width, image.height,
                               lambda k=key: self.go(k))
            y += 48
        footer = self.scene.cached(("footer",), lambda: self._sidebar_footer())
        self.scene.image("shell", "footer", footer, SP["md"], height - D.STATUS_H - 80)

    @staticmethod
    def _sidebar_bg(height: int):
        image = D.surface((D.SIDEBAR_W, height), radius=0, fill=D.mix(C["surface"], C["bg"], 0.5),
                          border=None, highlight=False)
        from PIL import ImageDraw

        ImageDraw.Draw(image).line([(D.SIDEBAR_W - 1, 0), (D.SIDEBAR_W - 1, height)], fill=D.rgba(C["border"]))
        return image

    @staticmethod
    def _sidebar_footer():
        image = D.surface((D.SIDEBAR_W - 24, 64), radius=R["tile"], fill=D.mix(C["surface_2"], C["bg"], 0.35),
                          border=C["border"])
        D.draw_text(image, (SP["lg"], 18), "Gratis y libre", size=T["small"], weight="medium", color=C["muted"])
        D.draw_text(image, (SP["lg"], 36), "GPL-3.0 · sin candados", size=T["tiny"], color=C["faint"])
        return image

    def _render_status(self, width: int, height: int) -> None:
        bar = D.surface((width, D.STATUS_H), radius=0, fill=D.mix(C["bg"], C["surface"], 0.45), border=None,
                        highlight=False)
        from PIL import ImageDraw

        ImageDraw.Draw(bar).line([(0, 0), (width, 0)], fill=D.rgba(C["border"]))
        D.draw_text(bar, (SP["xl"], D.STATUS_H // 2), self.status_message, size=T["small"], color=C["muted"],
                    anchor="lm")
        if self.busy:
            D.draw_text(bar, (width - SP["xl"], D.STATUS_H // 2), f"{self.busy}…", size=T["small"],
                        color=C["warn"], anchor="rm")
        self.scene.image("shell", "statusbar", bar, 0, height - D.STATUS_H)
        if self.toast_message and time.time() < self.toast_until:
            toast = self.scene.cached(("toast", self.toast_message, getattr(self, "toast_error", False)),
                                      lambda: self._toast_image())
            self.scene.image("shell", "toast", toast, width - toast.width - SP["xl"],
                             height - D.STATUS_H - toast.height - SP["lg"])

    def _toast_image(self):
        error = getattr(self, "toast_error", False)
        text = self.toast_message
        width = int(D.text_size(text, D.font(T["small"], "medium"))[0]) + 58
        image = D.surface((width, 44), radius=R["button"],
                          fill=D.mix(C["danger"] if error else C["ok"], C["bg"], 0.86),
                          border=D.mix(C["danger"] if error else C["ok"], C["bg"], 0.6), shadow=14)
        image.alpha_composite(D.icon("about" if error else "check", size=18,
                                     color=C["danger"] if error else C["ok"]), (SP["lg"], 13))
        D.draw_text(image, (SP["lg"] + 28, 22), text, size=T["small"], weight="medium",
                    color=C["text"], anchor="lm")
        return image

    def _sync_search_entry(self, content_x: int, content_y: int, content_w: int) -> None:
        if self.page == "temas":
            self.search_entry.place(x=content_x + content_w - 260 + SP["md"], y=content_y + 118 + 6,
                                    width=260 - SP["md"] * 2 - 24, height=22)
            self.search_shown = True
        else:
            self.search_entry.place_forget()
            self.search_shown = False

    # -- páginas ------------------------------------------------------------------
    def _title(self, tag: str, x: int, y: int, title: str, subtitle: str) -> None:
        self.scene.text(tag, x, y, title, size=T["display"], weight="bold")
        self.scene.text(tag, x + 2, y + 40, subtitle, size=T["small"], color=C["muted"])

    def _page_panel(self, x: int, y: int, width: int, height: int, pressed: str) -> None:
        tag, top = "current_page", y + 66
        self._title(tag, x, y, "Panel", "Estado en vivo, vista previa del tema y control rápido.")
        running, detail = self.status
        theme_name = self.config_editor.get("THEME") or "—"
        tiles = [
            ("Pantalla", "ENCENDIDA" if running else "APAGADA", detail, C["ok"] if running else C["danger"],
             self._spark["cpu"]),
            ("Puerto", self.config_editor.get("COM_PORT") or "AUTO",
             f"{self.config_editor.get('REVISION') or 'A'} · {self.platform.name}", C["accent"], None),
            ("Brillo", f"{int(self.brightness * 100)}%", theme_name, C["warn"], self._spark["ram"]),
            ("Sensores", self.config_editor.get("HW_SENSORS") or "AUTO", self.platform.admin_hint()[:26],
             C["accent_2"], None),
        ]
        tile_w = (width - SP["md"] * 3) // 4
        for index, (label, value, sub, accent, spark) in enumerate(tiles):
            image = self.scene.cached(("tile", label, value, sub, accent, bool(spark)),
                                      lambda: D.stat_tile(label, value, sub=sub, accent=accent, spark=spark,
                                                          width=tile_w, height=132))
            self.scene.image(tag, f"tile{index}", image, x + index * (tile_w + SP["md"]), top)

        preview_w = int((width - SP["lg"]) * 0.56)
        control_w = width - preview_w - SP["lg"]
        card_h = max(320, min(470, height - 190))
        current = next((t for t in self.themes if t.name == theme_name), None)
        preview = self.scene.cached(
            ("preview", theme_name, preview_w, card_h),
            lambda: D.theme_preview(current.background if current else None, theme_name,
                                    f"{current.resolution if current else '?'} · "
                                    f"{'horizontal' if current and current.is_landscape else 'vertical'} · "
                                    f"medida {current.size if current and current.size else '—'}",
                                    width=preview_w, height=card_h,
                                    badges=[('3.5"' if current and current.size.startswith("3.5") else
                                             (current.size or "medida"), "accent"),
                                            ("horizontal" if current and current.is_landscape else "vertical",
                                             "ok"), (f"{len(self.themes)} temas", "neutral")]))
        self.scene.image(tag, "preview", preview, x, top + 148)
        controls = self.scene.cached(
            ("controls", theme_name, int(self.brightness * 100), running, card_h),
            lambda: D.control_card(width=control_w, height=card_h,
                                   brightness=self.brightness, theme_name=theme_name, running=running))
        control_x = x + preview_w + SP["lg"]
        self.scene.image(tag, "controls", controls, control_x, top + 148)
        self._hotspots_panel(tag, control_x, top + 148, control_w, card_h, pressed)

        tip = self.scene.cached(("tip",), lambda: D.chip(self.platform.admin_hint(), kind="neutral"))
        self.scene.image(tag, "tip", tip, x, top + 148 + card_h + SP["lg"])

    def _hotspots_panel(self, tag: str, cx: int, cy: int, control_w: int, card_h: int,
                        pressed: str) -> None:
        buttons_y = cy + card_h - 96
        self.scene.hotspot(tag, "btn_on", cx + SP["lg"], buttons_y, 140, 44, self.act_start)
        self.scene.hotspot(tag, "btn_off", cx + SP["lg"] + 152, buttons_y, 120, 44, self.act_stop)
        self.scene.hotspot(tag, "btn_restart", cx + SP["lg"] + 284, buttons_y, 140, 44, self.act_restart)
        self.scene.hotspot(tag, "apply", cx + SP["lg"], cy + card_h - 152, control_w - SP["lg"] * 2, 40,
                           self.act_apply)
        slider_x, slider_w = cx + SP["lg"], control_w - SP["lg"] * 2 - 66
        self._slider_rect = (slider_x, slider_w)
        self.scene.hotspot(tag, "slider", slider_x, cy + SP["lg"] + 142, slider_w, 34, lambda: None)

    def _page_temas(self, x: int, y: int, width: int, height: int, pressed: str) -> None:
        tag = "current_page"
        self._title(tag, x, y, "Temas",
                    f"{len(self.themes)} temas instalados · filtro y búsqueda instantáneos.")
        segments = self.scene.cached(("segments", self.filter),
                                     lambda: D.segmented([label for label, _ in SEGMENTS],
                                                         [key for _, key in SEGMENTS].index(self.filter)))
        self.scene.image(tag, "segments", segments, x, y + 66)
        offset = SP["sm"]
        widths = [int(D.text_size(label, D.font(T["small"], "medium"))[0]) + 36 for label, _ in SEGMENTS]
        for (label, key), seg_w in zip(SEGMENTS, widths):
            self.scene.hotspot(tag, f"seg:{key}", x + offset, y + 66, seg_w, 34,
                               lambda k=key: self._set_filter(k))
            offset += seg_w
        self._search_field(tag, x, y, width)

        themes = self._filtered()
        list_x, list_y = x, y + 118
        list_w = int((width - SP["lg"]) * 0.52)
        list_h = height - 200
        rows_visible = max(1, list_h // LIST_ROW_H)
        self.list_offset = max(0, min(self.list_offset, max(0, len(themes) - rows_visible)))
        self.theme_index = max(0, min(self.theme_index, max(0, len(themes) - 1)))
        viewport = Image.new("RGBA", (list_w, list_h), (0, 0, 0, 0))
        for index in range(rows_visible):
            position = self.list_offset + index
            if position >= len(themes):
                break
            theme = themes[position]
            selected = position == self.theme_index
            hover = self.scene.hover == f"row:{position}" and not selected
            row = self.scene.cached(
                ("row", theme.name, selected, hover),
                lambda t=theme, s=selected, h=hover: D.list_row(
                    t.name, detail=f"{t.size or '—'} · {'horizontal' if t.is_landscape else 'vertical'}",
                    active=s, hover=h, width=list_w, height=LIST_ROW_H - 4))
            viewport.alpha_composite(row, (0, index * LIST_ROW_H))
            self.scene.hotspot(tag, f"row:{position}", list_x, list_y + index * LIST_ROW_H,
                               list_w, LIST_ROW_H - 4, lambda p=position: self._select_theme(p))
        self.scene.image(tag, "list", viewport, list_x, list_y)

        theme = self._selected_theme()
        preview_w = width - list_w - SP["lg"]
        preview = self.scene.cached(
            ("theme_preview", theme.name if theme else "", preview_w),
            lambda: D.theme_preview(theme.background if theme else None, theme.name if theme else "—",
                                    f"{theme.resolution if theme else '?'} · "
                                    f"{'horizontal' if theme and theme.is_landscape else 'vertical'}",
                                    width=preview_w, height=min(400, list_h - 90),
                                    badges=[(theme.size or "medida", "accent"),
                                            ("horizontal" if theme and theme.is_landscape else "vertical", "ok")]))
        self.scene.image(tag, "preview", preview, list_x + list_w + SP["lg"], list_y)
        apply_button = self.scene.cached(("apply_btn", pressed == "apply"),
                                         lambda: D.button("Aplicar tema seleccionado", kind="primary",
                                                          width=preview_w, height=44,
                                                          state="press" if pressed == "apply" else
                                                          ("hover" if self.scene.hover == "apply" else "normal")))
        button_y = list_y + preview.height + SP["md"]
        self.scene.image(tag, "apply", apply_button, list_x + list_w + SP["lg"], button_y)
        self.scene.hotspot(tag, "apply", list_x + list_w + SP["lg"], button_y, preview_w, 44, self.act_apply)
        folder = self.scene.cached(("folder_btn",),
                                   lambda: D.button("Abrir carpeta", kind="secondary", width=160, height=34))
        self.scene.image(tag, "folder", folder, x, y + 74 + list_h + SP["sm"])
        self.scene.hotspot(tag, "folder", x, y + 74 + list_h + SP["sm"], 160, 34,
                           lambda: self.act_open(theme.path if theme else THEMES_DIR))

    def _search_field(self, tag: str, x: int, y: int, width: int) -> None:
        field_w, field_h = 260, 34
        field_x, field_y = x + width - field_w, y + 118
        field = self.scene.cached(("search_field", self.scene.hover == "search"),
                                  lambda: D.surface((field_w, field_h), radius=R["input"],
                                                    fill=C["surface_2"], border=C["border_hi"]))
        self.scene.image(tag, "search", field, field_x, field_y)
        self.scene.image(tag, "search_icon", self.scene.cached(("search_icon",),
                                                               lambda: D.icon("log", size=15, color=C["faint"])),
                         field_x + SP["md"], field_y + 9)
        if not self.search:
            self.scene.text(tag, field_x + SP["md"] + 22, field_y + field_h // 2, "Buscar tema…",
                            size=T["small"], color=C["faint"], anchor="lm")
        self.scene.hotspot(tag, "search", field_x, field_y, field_w, field_h,
                           lambda: self.search_entry.focus_set())

    def _set_filter(self, key: str) -> None:
        self.filter = key
        self.theme_index = 0
        self.list_offset = 0
        self.render()

    def _select_theme(self, position: int) -> None:
        self.theme_index = position
        self.render()

    def _page_ajustes(self, x: int, y: int, width: int, height: int, pressed: str) -> None:
        tag = "current_page"
        self._title(tag, x, y, "Ajustes", "Edita aquí y pulsa Guardar ajustes (config.yaml conserva comentarios).")
        left_w = int((width - SP["lg"]) * 0.58)
        right_w = width - left_w - SP["lg"]
        rows = [(etiqueta, self.config_editor.get(clave)) for clave, etiqueta in AJUSTES]
        card_h = 96 + len(rows) * 46
        card = self.scene.cached(("settings_card", tuple(rows)), lambda: self._settings_card(left_w, card_h, rows))
        self.scene.image(tag, "settings", card, x, y + 66)
        self._campos_ajustes(x, y, left_w)

        switches = [("Invertir imagen", self.config_editor.get("DISPLAY_REVERSE").lower() == "true", "reverse"),
                    ("Reiniciar la pantalla al arrancar",
                     self.config_editor.get("RESET_ON_STARTUP").lower() != "false", "reset"),
                    ("Arranque automático", self.autostart, "autostart")]
        switch_h = 96 + len(switches) * 52
        card2 = self.scene.cached(("switch_card", tuple((a, b) for a, b, _ in switches)),
                                  lambda: self._switch_card(right_w, switch_h, switches))
        self.scene.image(tag, "switches", card2, x + left_w + SP["lg"], y + 66)
        for index, (label, value, key) in enumerate(switches):
            self.scene.hotspot(tag, f"toggle:{key}", x + left_w + SP["lg"] + right_w - SP["lg"] - 48,
                               y + 66 + 46 + index * 52, 48, 28,
                               lambda k=key, v=value: self.act_toggle(k, not v))

        buttons_y = y + 66 + card_h + SP["lg"]
        save = self.scene.cached(("save_btn", self.scene.hover == "save"),
                                 lambda: D.button("Guardar ajustes", kind="primary", width=200, height=44,
                                                  state="hover" if self.scene.hover == "save" else "normal"))
        self.scene.image(tag, "save", save, x, buttons_y)
        self.scene.hotspot(tag, "save", x, buttons_y, 200, 44, self._save_settings)
        open_file = self.scene.cached(
            ("open_cfg",), lambda: D.button("Abrir config.yaml", kind="secondary", width=200, height=44))
        self.scene.image(tag, "open_cfg", open_file, x + 216, buttons_y)
        self.scene.hotspot(tag, "open_cfg", x + 216, buttons_y, 200, 44,
                           lambda: self.act_open(core.CONFIG_FILE))
        restore = self.scene.cached(
            ("restore_btn",), lambda: D.button("Restaurar copia", kind="ghost", width=180, height=44))
        self.scene.image(tag, "restore", restore, x + 432, buttons_y)
        self.scene.hotspot(tag, "restore", x + 432, buttons_y, 180, 44, self._restore_backup)

        # Avanzado: editor del YAML del tema actual (lo que tenia la interfaz antigua)
        avanzado = self.scene.cached(
            ("adv_btn", self.scene.hover == "adv"),
            lambda: D.button("Avanzado: editar el YAML del tema", kind="secondary", width=340, height=44,
                             state="hover" if self.scene.hover == "adv" else "normal"))
        self.scene.image(tag, "adv", avanzado, x, buttons_y + 56)
        self.scene.hotspot(tag, "adv", x, buttons_y + 56, 340, 44, self.act_editar_yaml)

    def _campos_ajustes(self, x: int, y: int, ancho_tarjeta: int) -> None:
        """Coloca campos de texto reales encima de los dibujados en el lienzo.

        Antes eran dibujos y "Guardar ajustes" releia el propio fichero: no guardaba
        nada de lo escrito. Ahora cada fila es un Entry de verdad.
        """
        ancho_campo = int(ancho_tarjeta * 0.46)
        base_y = y + 66 + SP["lg"] + 44
        for indice, (clave, _etiqueta) in enumerate(AJUSTES):
            caja = self._ajustes_campos.get(clave)
            if caja is None:
                caja = tk.Entry(self, relief="flat", bd=0, bg=C["surface_2"], fg=C["text"],
                                insertbackground=C["accent"], highlightthickness=0,
                                font=(self._font_family(), T["small"]))
                self._ajustes_campos[clave] = caja
            valor = self.config_editor.get(clave)
            if caja.get() != valor:
                caja.delete(0, "end")
                caja.insert(0, valor)
            caja.place(x=x + ancho_tarjeta - ancho_campo - SP["lg"] + SP["md"],
                       y=base_y + indice * 46 + 5,
                       width=ancho_campo - SP["md"] * 2, height=22)

    def _ocultar_campos_ajustes(self) -> None:
        for caja in self._ajustes_campos.values():
            caja.place_forget()

    def _settings_card(self, width: int, height: int, rows: list[tuple[str, str]]):
        image = D.glass((width, height), radius=R["card"], shadow=12)
        D.draw_text(image, (SP["lg"], SP["lg"]), "Pantalla y sensores", size=T["h2"], weight="bold")
        y = SP["lg"] + 44
        for label, value in rows:
            D.draw_text(image, (SP["lg"], y + 15), label, size=T["small"], color=C["muted"], anchor="lm")
            field = D.surface((int(width * 0.46), 32), radius=R["input"], fill=C["surface_2"],
                              border=C["border_hi"])
            D.draw_text(field, (SP["md"], 16), value or "—", size=T["small"], color=C["text"], anchor="lm")
            image.alpha_composite(field, (width - field.width - SP["lg"], y))
            y += 46
        return image

    def _switch_card(self, width: int, height: int, switches: list[tuple[str, bool, str]]):
        image = D.glass((width, height), radius=R["card"], shadow=12)
        D.draw_text(image, (SP["lg"], SP["lg"]), "Comportamiento", size=T["h2"], weight="bold")
        for index, (label, value, _key) in enumerate(switches):
            y = SP["lg"] + 46 + index * 52
            D.draw_text(image, (SP["lg"], y + 14), label, size=T["small"], color=C["muted"], anchor="lm")
            image.alpha_composite(D.toggle(value, width=48, height=28), (width - SP["lg"] - 48, y))
        return image

    def _save_settings(self) -> None:
        """Guarda lo escrito en los campos y reinicia el monitor para aplicarlo."""
        valores = {}
        for clave, _etiqueta in AJUSTES:
            caja = self._ajustes_campos.get(clave)
            if caja is not None:
                valores[clave] = caja.get().strip()
        valores = {clave: valor for clave, valor in valores.items() if valor != ""}
        # Solo se escribe lo que de verdad cambia (asi no se reformatea el resto)
        valores = {clave: valor for clave, valor in valores.items()
                   if valor != self.config_editor.get(clave)}

        tema = valores.get("THEME", "")
        if tema and not (core.THEMES_DIR / tema / "theme.yaml").exists():
            self.notify(f'El tema "{tema}" no existe (revisa el nombre)', error=True)
            return
        sensores = valores.get("HW_SENSORS", "").upper()
        if sensores and sensores not in core.SENSOR_MODES:
            self.notify(f'Modo de sensores no válido: {sensores}', error=True)
            return
        for clave, etiqueta in (("WEATHER_LATITUDE", "latitud"), ("WEATHER_LONGITUDE", "longitud")):
            try:
                float(valores.get(clave, "0"))
            except ValueError:
                self.notify(f"La {etiqueta} tiene que ser un número", error=True)
                return

        def task():
            cambiados = self.config_editor.set_many({clave: (valor, None) for clave, valor in valores.items()})
            if not cambiados:
                return True, "Sin cambios"
            ok, mensaje = self.platform.restart()
            return ok, (f"Guardado y aplicado: {', '.join(cambiados)}" if ok else mensaje)

        self.run_bg("Guardando ajustes", task)

    def act_editar_yaml(self) -> None:
        """Avanzado: editor del YAML del tema actual (como en la interfaz antigua).

        Valida el YAML antes de escribirlo, guarda copia .bak-centro y reinicia el
        monitor para aplicarlo. No toca el código del programa.
        """
        import shutil

        import yaml

        tema = self.config_editor.get("THEME")
        ruta = core.THEMES_DIR / str(tema) / "theme.yaml"
        if not ruta.exists():
            self.notify(f'No encuentro el theme.yaml del tema "{tema}"', error=True)
            return

        ventana = tk.Toplevel(self)
        ventana.title(f"Avanzado — {tema}/theme.yaml")
        ventana.configure(bg=C["bg"])
        ventana.geometry("880x660")
        try:
            ventana.iconphoto(True, tk.PhotoImage(file=core.ROOT / "res/icons/centro-turing/64.png"))
        except Exception:
            pass
        tk.Label(ventana, text="Avanzado: YAML del tema actual. No toca el código del programa.",
                 bg=C["bg"], fg=C["muted"], font=(self._font_family(), T["small"])).pack(
            anchor="w", padx=14, pady=(12, 6))
        marco = tk.Frame(ventana, bg=C["bg"])
        marco.pack(fill="both", expand=True, padx=14)
        texto = tk.Text(marco, bg=C["surface_2"], fg=C["text"], insertbackground=C["accent"],
                        relief="flat", wrap="none", undo=True, font=("Consolas", 10))
        barra = tk.Scrollbar(marco, command=texto.yview)
        texto.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        texto.pack(fill="both", expand=True)
        texto.insert("1.0", ruta.read_text(encoding="utf-8", errors="replace"))
        estado = tk.Label(ventana, text=str(ruta), bg=C["bg"], fg=C["muted"],
                          font=(self._font_family(), T["small"]))
        estado.pack(anchor="w", padx=14, pady=(6, 0))
        fila = tk.Frame(ventana, bg=C["bg"])
        fila.pack(fill="x", padx=14, pady=12)

        def guardar():
            contenido = texto.get("1.0", "end-1c")
            try:
                datos = yaml.safe_load(contenido)
                if not isinstance(datos, dict) or "display" not in datos:
                    raise ValueError("falta la sección display")
            except Exception as error:  # noqa: BLE001
                estado.config(text=f"YAML no válido: {error}", fg=C["danger"])
                return
            copia = ruta.with_suffix(".yaml.bak-centro")
            try:
                shutil.copy2(ruta, copia)
                ruta.write_text(contenido, encoding="utf-8")
            except OSError as error:
                estado.config(text=f"No se pudo guardar: {error}", fg=C["danger"])
                return
            estado.config(text=f"Guardado (copia: {copia.name}) — aplicando…", fg=C["ok"])
            self.run_bg("Aplicando tema", lambda: (self.platform.restart()[0], f"{tema} aplicado"))

        def recargar():
            texto.delete("1.0", "end")
            texto.insert("1.0", ruta.read_text(encoding="utf-8", errors="replace"))
            estado.config(text=str(ruta), fg=C["muted"])

        for etiqueta, accion, color in (("Guardar y aplicar", guardar, C["accent"]),
                                        ("Recargar del fichero", recargar, C["surface_2"]),
                                        ("Cerrar", ventana.destroy, C["surface_2"])):
            tk.Button(fila, text=etiqueta, command=accion, bg=color,
                      fg=C["bg"] if color == C["accent"] else C["text"], activebackground=color,
                      relief="flat", font=(self._font_family(), T["small"]),
                      padx=14, pady=6).pack(side="left", padx=(0, 8))

    def _restore_backup(self) -> None:
        if self.config_editor.restore_backup():
            self.brightness = self._brightness()
            self.notify("Copia restaurada")
        else:
            self.notify("No hay copia disponible", error=True)

    def _page_registro(self, x: int, y: int, width: int, height: int, pressed: str) -> None:
        tag = "current_page"
        self._title(tag, x, y, "Registro", f"{self.platform.log_file}")
        auto = getattr(self, "auto_log", True)
        toggle = self.scene.cached(("log_toggle", auto), lambda: D.toggle(auto, width=48, height=28))
        self.scene.image(tag, "log_toggle", toggle, x, y + 70)
        self.scene.hotspot(tag, "log_toggle", x, y + 70, 48, 28, self.act_autorefresh)
        self.scene.text(tag, x + 60, y + 84, "Actualizar automáticamente", size=T["small"], color=C["muted"],
                        anchor="lm")

        for index, (label, key, callback) in enumerate([("Refrescar", "refresh", self.render),
                                                        ("Copiar", "copy", self.act_copy_log),
                                                        ("Abrir archivo", "openlog",
                                                         lambda: self.act_open(self.platform.log_file))]):
            button = self.scene.cached(("log_btn", label, self.scene.hover == key),
                                       lambda lbl=label, k=key: D.button(
                                           lbl, kind="secondary", width=150, height=38,
                                           state="hover" if self.scene.hover == k else "normal"))
            bx = x + width - (3 - index) * 162
            self.scene.image(tag, f"log_btn{index}", button, bx, y + 66)
            self.scene.hotspot(tag, key, bx, y + 66, 150, 38, callback)

        lines = core.tail_file(self.platform.log_file, 400).splitlines()
        visible = max(4, (height - 210) // 18)
        self.log_offset = max(0, min(self.log_offset, max(0, len(lines) - visible)))
        window = lines[len(lines) - visible - self.log_offset: len(lines) - self.log_offset or None]
        console = self.scene.cached(("console", tuple(window), width, height - 190),
                                    lambda: D.log_view(window, width=width, height=height - 190))
        self.scene.image(tag, "console", console, x, y + 116)

    def _page_sistema(self, x: int, y: int, width: int, height: int, pressed: str) -> None:
        tag = "current_page"
        self._title(tag, x, y, "Sistema", "Arranque automático, mantenimiento y diagnóstico.")
        left_w = int((width - SP["lg"]) * 0.58)
        right_w = width - left_w - SP["lg"]

        actions = [("Actualizar código (git pull)", "pull", self.act_git_pull),
                   ("Abrir carpeta del proyecto", "folder", lambda: self.act_open(core.ROOT)),
                   ("Comprobar actualización", "check", self.act_check_update)]
        actions += [(label, key, (lambda k=key: self.act_extra(k)))
                    for key, label in self.platform.extra_actions()]
        card_h = 90 + len(actions) * 46
        card = self.scene.cached(("maint_card", tuple(a[0] for a in actions)),
                                 lambda: self._maintenance_card(left_w, card_h, actions))
        self.scene.image(tag, "maint", card, x, y + 66)
        for index, (label, key, callback) in enumerate(actions):
            self.scene.hotspot(tag, f"action:{key}", x + SP["lg"], y + 66 + 44 + index * 46,
                               left_w - SP["lg"] * 2, 38, callback)

        diagnostics = self.platform.diagnostics()
        diag_h = 90 + len(diagnostics) * 34
        diag = self.scene.cached(("diag_card", tuple(diagnostics)),
                                 lambda: self._diagnostics_card(right_w, diag_h, diagnostics))
        self.scene.image(tag, "diag", diag, x + left_w + SP["lg"], y + 66)

    def _maintenance_card(self, width: int, height: int, actions):
        image = D.glass((width, height), radius=R["card"], shadow=12)
        D.draw_text(image, (SP["lg"], SP["lg"]), "Mantenimiento", size=T["h2"], weight="bold")
        for index, (label, key, _callback) in enumerate(actions):
            y = SP["lg"] + 44 + index * 46
            hover = self.scene.hover == f"action:{key}"
            button = D.button(label, kind="secondary", width=width - SP["lg"] * 2, height=38,
                              state="hover" if hover else "normal")
            image.alpha_composite(button, (SP["lg"], y))
        return image

    def _diagnostics_card(self, width: int, height: int, rows):
        image = D.glass((width, height), radius=R["card"], shadow=12)
        D.draw_text(image, (SP["lg"], SP["lg"]), "Diagnóstico", size=T["h2"], weight="bold")
        for index, (label, value) in enumerate(rows):
            y = SP["lg"] + 44 + index * 34
            D.draw_text(image, (SP["lg"], y), label, size=T["small"], color=C["muted"], anchor="lm")
            D.draw_text(image, (int(width * 0.42), y), str(value)[:44], size=T["small"], color=C["text"],
                        anchor="lm")
        return image

    def _page_acerca(self, x: int, y: int, width: int, height: int, pressed: str) -> None:
        tag = "current_page"
        self._title(tag, x, y, "Acerca de", "Software libre y gratuito, sin candados ni compras.")
        card_w = min(860, width)
        lines = [
            f"{APP_NAME} {VERSION} — panel unificado para pantallas Turing / XuanFang.",
            "La misma interfaz en Windows y Linux.",
            "",
            f"Proyecto Linux:  {REPO_URL}",
            f"Proyecto base:   {core.UPSTREAM_URL}",
            "",
            "Turing Smart Screen Panel © mathoudebine y colaboradores — GPL-3.0.",
            "Adaptación al español y edición Linux: pilahito.",
        ]
        card = self.scene.cached(("about_card", card_w, tuple(lines)),
                                 lambda: self._about_card(card_w, lines))
        self.scene.image(tag, "about", card, x, y + 66)
        button = self.scene.cached(("repo_btn", self.scene.hover == "repo"),
                                   lambda: D.button("Abrir repositorio", kind="primary", width=220, height=44,
                                                    state="hover" if self.scene.hover == "repo" else "normal"))
        button_y = y + 66 + card.height + SP["lg"]
        self.scene.image(tag, "repo", button, x, button_y)
        self.scene.hotspot(tag, "repo", x, button_y, 220, 44, self._open_repo)

    def _about_card(self, width: int, lines: list[str]):
        height = 76 + len(lines) * 24
        image = D.glass((width, height), radius=R["card"], shadow=12)
        D.draw_text(image, (SP["lg"], SP["lg"]), f"{APP_NAME} {VERSION}", size=T["h1"], weight="bold")
        for index, line in enumerate(lines):
            D.draw_text(image, (SP["lg"], SP["lg"] + 46 + index * 24), line, size=T["small"], color=C["muted"])
        return image

    def _open_repo(self) -> None:
        import webbrowser

        webbrowser.open(REPO_URL)


def render_mockups(directory: Path) -> list[Path]:
    """Genera las previsualizaciones de las 6 páginas con los datos reales del sistema."""
    platform = make_platform()
    editor = ConfigEditor()
    themes = scan_themes()
    current = next((theme for theme in themes if theme.name == editor.get("THEME")), None)
    running, detail = platform.is_running()
    brightness = max(0.0, min(1.0, int(editor.get("BRIGHTNESS") or 35) / 100))
    rows = [{"name": theme.name,
             "detail": f"{theme.size or '—'} · {'horizontal' if theme.is_landscape else 'vertical'}"}
            for theme in themes[:40]]
    state = {
        "version": VERSION,
        "status_text": "ENCENDIDA" if running else "APAGADA",
        "clock": time.strftime("%H:%M"),
        "nav": [(label, icon) for _key, label, icon in NAV],
        "nav_active": 0,
        "status_message": f"Listo · {len(themes)} temas · {platform.name}",
        "tiles": [
            {"label": "Pantalla", "value": "ENCENDIDA" if running else "APAGADA", "sub": detail,
             "accent": C["ok"] if running else C["danger"], "spark": [4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 9]},
            {"label": "Puerto", "value": editor.get("COM_PORT") or "AUTO",
             "sub": f"{editor.get('REVISION') or 'A'} · {platform.name}", "accent": C["accent"]},
            {"label": "Brillo", "value": f"{int(brightness * 100)}%",
             "sub": editor.get("THEME") or "—", "accent": C["warn"], "spark": [6, 6, 7, 7, 7, 8, 7, 8, 8, 8, 9, 9]},
            {"label": "Sensores", "value": editor.get("HW_SENSORS") or "AUTO",
             "sub": platform.admin_hint()[:30], "accent": C["accent_2"]},
        ],
        "preview": D.theme_preview(current.background if current else None,
                                   editor.get("THEME") or "—",
                                   f"{current.resolution if current else '?'} · "
                                   f"{'horizontal' if current and current.is_landscape else 'vertical'}",
                                   badges=[(current.size if current and current.size else "medida", "accent"),
                                           (f"{len(themes)} temas", "neutral")]),
        "controls": D.control_card(brightness=brightness, theme_name=editor.get("THEME") or "—", running=running),
        "rows": rows,
        "row_active": 0,
        "filters": D.segmented([label for label, _key in SEGMENTS], 1),
        "settings": [("Tema", editor.get("THEME")), ("Modo de sensores", editor.get("HW_SENSORS")),
                     ("Revisión de pantalla", editor.get("REVISION")), ("Puerto serie", editor.get("COM_PORT")),
                     ("Formato de reloj", editor.get("CLOCK_FORMAT"))],
        "switches": [("Invertir imagen", editor.get("DISPLAY_REVERSE").lower() == "true"),
                     ("Reiniciar la pantalla al arrancar",
                      editor.get("RESET_ON_STARTUP").lower() != "false"),
                     ("Arranque automático", platform.autostart_enabled())],
        "log": core.tail_file(platform.log_file, 40).splitlines(),
        "diagnostics": platform.diagnostics(),
        "actions": [label for _key, label in platform.extra_actions()] or ["Abrir carpeta del proyecto"],
        "about": [f"{APP_NAME} {VERSION} — panel unificado para pantallas Turing / XuanFang.",
                  "La misma interfaz en Windows y Linux.",
                  f"Proyecto Linux:  {REPO_URL}",
                  f"Proyecto base:   {core.UPSTREAM_URL}",
                  "Turing Smart Screen Panel © mathoudebine y colaboradores — GPL-3.0."],
    }
    return D.save_mockups(Path(directory), state)


def prepare_windows_app_identity(app_id: str = "pilahito.CentroTuring.3") -> None:
    """Windows: identidad propia para la barra de tareas y el icono.

    Sin esto, Windows agrupa la ventana bajo `pythonw.exe` y muestra el icono de
    Python en lugar del icono del proyecto. Debe llamarse ANTES de crear ventanas.
    """
    if not D._WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def selftest() -> int:
    """Construye la interfaz, recorre las páginas y comprueba el layout."""
    prepare_windows_app_identity()
    app = App()
    app.update_idletasks()
    app.update()
    problems = []
    for key, label, _icon in NAV:
        app.page = key
        app.render()
        app.update_idletasks()
        app.update()
        items = app.canvas.find_all()
        if len(items) < 8:
            problems.append(f"{label}: solo {len(items)} elementos dibujados")
        hotspots = [spot for spot in app.scene.hotspots if spot[0] == "current_page"]
        if not hotspots:
            problems.append(f"{label}: sin zonas interactivas")
    app.page = "panel"
    app.render()
    app.update()
    print(f"Selftest OK: {len(NAV)} páginas, ventana {app.winfo_width()}x{app.winfo_height()}, "
          f"{len(app.themes)} temas, plataforma {app.platform.name}")
    print(f"Layout: {len(problems)} problema(s)")
    for problem in problems:
        print(f"  !! {problem}")
    app.destroy()
    return 0 if not problems else 1


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=f"{APP_NAME} {VERSION} — interfaz 2026")
    parser.add_argument("--selftest", action="store_true", help="construye la interfaz y sale")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    prepare_windows_app_identity()
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
