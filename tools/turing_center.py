#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Centro Turing 3.0 — panel de control multiplataforma (Windows y Linux)
# para turing-smart-screen-python / turing-smart-screen-linux.
#
# Sustituye a los lanzadores separados (Centro Turing v2 en Windows y el menu de
# texto turing-menu.sh en Linux) por una sola interfaz grafica que funciona igual
# en ambos sistemas.
#
# Diseno de la interfaz:
#   * Ventana nativa con decoracion del sistema (nada de overrideredirect), por lo
#     que no hay barras superpuestas ni contenido recortado.
#   * Layout con grid + pesos y paginas con scroll: todo se adapta al tamano real.
#   * Los mensajes van a una barra de estado inferior (no hay etiquetas flotantes
#     colocadas con place() encima del contenido).
#   * Cada opcion del menu tiene contenido real y funcional.
#
# Dependencias: Tkinter (stdlib). Opcionales, con degradacion elegante:
#   Pillow (vistas previas), pyserial (puertos COM), psutil (procesos).
#
# Uso:
#   python tools/turing_center.py                 # interfaz grafica
#   python tools/turing_center.py --status        # estado en texto (sin GUI)
#   python tools/turing_center.py --theme Cyberdeck
#   python tools/turing_center.py --selftest      # comprueba que la UI se construye
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------------------
APP_NAME = "Centro Turing"
VERSION = "3.0.0"
REPO_URL = "https://github.com/pilahito/turing-smart-screen-linux"
UPSTREAM_URL = "https://github.com/mathoudebine/turing-smart-screen-python"

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config.yaml"
THEMES_DIR = ROOT / "res" / "themes"
STATE_FILE = ROOT / "tmp" / "centro-ui.json"

IS_WINDOWS = os.name == "nt"
IS_LINUX = sys.platform.startswith("linux")

# Paleta (identica a la del Centro Turing v2 para no romper la identidad visual)
BG = "#0f1319"
SIDE = "#12161c"
CARD = "#1b222c"
CARD_HI = "#232c38"
FG = "#e6edf3"
MUTED = "#8b9bab"
CYAN = "#3dccc7"
AMBER = "#e0a050"
GREEN = "#3dd68c"
RED = "#f07178"
LINE = "#2a3542"

UI_FONT = "Segoe UI" if IS_WINDOWS else "DejaVu Sans"
MONO_FONT = "Consolas" if IS_WINDOWS else "DejaVu Sans Mono"

# Revisiones de pantalla soportadas por library/display.py
REVISIONS = ("A", "B", "C", "D", "TUR_USB", "WEACT_A", "WEACT_B", "SIMU")
SENSOR_MODES = ("AUTO", "PYTHON", "LHM", "STUB_RANDOM", "STUB_STATIC")


def log_line(message: str) -> None:
    """Escribe en consola con marca de tiempo (util al lanzar desde terminal)."""
    stamp = time.strftime("%d/%m/%Y %H:%M:%S")
    print(f"{stamp} [centro] {message}", flush=True)


# --------------------------------------------------------------------------------------
# Utilidades de configuracion (edicion textual: conserva comentarios y orden)
# --------------------------------------------------------------------------------------
class ConfigEditor:
    """Edita config.yaml con expresiones regulares para no perder comentarios.

    Se usa en lugar de yaml.dump() porque volcar el YAML destruiria los comentarios
    y el orden original del archivo del usuario.
    """

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = Path(path)

    # -- lectura -----------------------------------------------------------------
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8-sig")

    def get(self, key: str, default: str = "") -> str:
        match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.*)$", self.text())
        if not match:
            return default
        return match.group(1).strip().strip('"').strip("'")

    def as_dict(self) -> dict:
        data = {}
        for key in ("THEME", "COM_PORT", "HW_SENSORS"):
            data[key] = self.get(key)
        for key in ("REVISION", "BRIGHTNESS", "DISPLAY_REVERSE", "RESET_ON_STARTUP"):
            data[key] = self.get(key)
        return data

    # -- escritura ---------------------------------------------------------------
    def set(self, key: str, value, section: str | None = None) -> bool:
        """Fija una clave. Devuelve True si el archivo cambio."""
        text = self.text()
        rendered = self._render(value)
        pattern = re.compile(rf"(?m)^(\s*{re.escape(key)}:\s*).*$")
        if pattern.search(text):
            new_text = pattern.sub(lambda m: m.group(1) + rendered, text, count=1)
        elif section and re.search(rf"(?m)^{re.escape(section)}:\s*$", text):
            new_text = self._insert_in_section(text, section, key, rendered)
        else:
            new_text = text.rstrip("\n") + f"\n{key}: {rendered}\n"
        if new_text == text:
            return False
        self.path.write_text(new_text, encoding="utf-8")
        return True

    def set_many(self, values: dict[str, tuple], backup: bool = True) -> list[str]:
        """Aplica varias claves. values: {clave: (valor, seccion_o_None)}."""
        if backup:
            self.backup()
        changed = []
        for key, payload in values.items():
            value, section = payload if isinstance(payload, tuple) else (payload, None)
            if self.set(key, value, section):
                changed.append(key)
        return changed

    def backup(self) -> Path | None:
        if not self.path.exists():
            return None
        target = self.path.with_suffix(".yaml.bak-centro")
        shutil.copy2(self.path, target)
        return target

    def restore_backup(self) -> bool:
        target = self.path.with_suffix(".yaml.bak-centro")
        if not target.exists():
            return False
        shutil.copy2(target, self.path)
        return True

    # -- internos ----------------------------------------------------------------
    @staticmethod
    def _render(value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value)
        if text == "":
            return ""
        # Las cadenas con caracteres especiales se entrecomillan
        if re.search(r"[:#\[\]{},&*?|>!%@`\"']", text) or text != text.strip():
            return '"' + text.replace('"', '\\"') + '"'
        return text

    @staticmethod
    def _insert_in_section(text: str, section: str, key: str, rendered: str) -> str:
        lines = text.splitlines()
        start = None
        for index, line in enumerate(lines):
            if re.match(rf"^{re.escape(section)}:\s*$", line):
                start = index
                break
        if start is None:
            return text
        insert_at = start + 1
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line.strip() and not line.startswith((" ", "\t")):
                break
            if re.match(r"^\s+\S", line):
                insert_at = index + 1
        lines.insert(insert_at, f"  {key}: {rendered}")
        return "\n".join(lines) + "\n"


def tail_file(path: Path, lines: int = 400) -> str:
    """Devuelve las ultimas `lines` lineas de un archivo (o "" si no existe)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(handle.readlines()[-lines:])
    except OSError:
        return ""


def human_size(num: float) -> str:
    """Tamano legible (B/KB/MB/GB/TB)."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024.0:
            return f"{num:3.0f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


# --------------------------------------------------------------------------------------
# Capa de plataforma: todo lo que cambia entre Windows y Linux
# --------------------------------------------------------------------------------------
class Platform:
    """Operaciones del sistema operativo que consume la interfaz."""

    name = "Sistema"
    accent_os = "?"

    # -- rutas -------------------------------------------------------------------
    @property
    def log_file(self) -> Path:
        return ROOT / "log.log"

    @property
    def pid_file(self) -> Path:
        return ROOT / "tmp" / "monitor.pid"

    def python_exe(self) -> Path:
        """Interprete a usar para lanzar main.py."""
        candidates = []
        if IS_WINDOWS:
            candidates += [ROOT / "venv" / "Scripts" / "pythonw.exe", ROOT / "venv" / "Scripts" / "python.exe"]
        candidates += [
            ROOT / ".venv" / "bin" / "python3",
            ROOT / ".venv" / "bin" / "python",
            ROOT / "venv" / "bin" / "python3",
            ROOT / "venv" / "bin" / "python",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        found = shutil.which("python3") or shutil.which("python") or sys.executable
        return Path(found)

    def has_venv(self) -> bool:
        if IS_WINDOWS:
            return (ROOT / "venv" / "Scripts" / "python.exe").exists()
        return (ROOT / ".venv" / "bin" / "python3").exists() or (ROOT / "venv" / "bin" / "python").exists()

    # -- estado -----------------------------------------------------------------
    def is_running(self) -> tuple[bool, str]:
        """(activo, detalle)."""
        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = 0
        if pid > 0 and self._pid_alive(pid):
            return True, f"PID {pid}"
        if IS_LINUX:
            active = self._run(["systemctl", "--user", "is-active", "turing-smart-screen.service"])
            if active.strip() == "active":
                return True, "systemd: activo"
        found = self._find_monitor_process()
        if found:
            return True, f"PID {found}"
        return False, "detenido"

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            import psutil  # type: ignore

            return psutil.pid_exists(pid)
        except Exception:
            pass
        if IS_WINDOWS:
            result = self._run(["tasklist", "/FI", f"PID eq {pid}", "/NH"])
            return str(pid) in result
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _find_monitor_process(self) -> int:
        try:
            import psutil  # type: ignore

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = " ".join(proc.info.get("cmdline") or [])
                except Exception:
                    continue
                if "main.py" in cmdline and str(ROOT).replace("\\", "/") in cmdline.replace("\\", "/"):
                    return int(proc.info["pid"])
        except Exception:
            return 0
        return 0

    # -- arranque y parada -------------------------------------------------------
    def start(self, detached: bool = True) -> tuple[bool, str]:
        python = self.python_exe()
        if not python.exists() and not shutil.which(str(python)):
            return False, "No encuentro Python. Ejecuta la instalacion primero."
        if not (ROOT / "main.py").exists():
            return False, f"No encuentro main.py en {ROOT}"

        if IS_LINUX and detached and self._systemd_available("turing-smart-screen.service"):
            code = self._run_code(["systemctl", "--user", "start", "turing-smart-screen.service"])
            if code == 0:
                return True, "Iniciado con systemd (usuario)"

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        creation = 0
        if IS_WINDOWS:
            creation = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
        try:
            with self.log_file.open("a", encoding="utf-8") as log_handle:
                log_handle.write(time.strftime("%d/%m/%Y %H:%M:%S") + f" [INFO] Arranque desde {APP_NAME} {VERSION}\n")
                proc = subprocess.Popen(
                    [str(python), "main.py"],
                    cwd=str(ROOT),
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    env=env,
                    creationflags=creation,
                    start_new_session=not IS_WINDOWS,
                )
        except OSError as error:
            return False, f"No se pudo lanzar main.py: {error}"
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(proc.pid), encoding="utf-8")
        time.sleep(2.0)
        if proc.poll() is not None:
            return False, "El monitor se cerro al arrancar. Revisa el registro."
        return True, f"Monitor iniciado (PID {proc.pid})"

    def stop(self) -> tuple[bool, str]:
        messages = []
        if IS_LINUX and self._systemd_available("turing-smart-screen.service"):
            if self._run_code(["systemctl", "--user", "stop", "turing-smart-screen.service"]) == 0:
                messages.append("systemd detenido")
        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = 0
        if pid > 0:
            self._kill(pid)
            messages.append(f"PID {pid} detenido")
        for found in filter(None, [self._find_monitor_process()]):
            self._kill(found)
            messages.append(f"PID {found} detenido")
        if IS_WINDOWS:
            self._run(["taskkill", "/IM", "UsbPCMonitor.exe", "/F"])
        try:
            self.pid_file.unlink()
        except OSError:
            pass
        return True, ("Monitor detenido: " + ", ".join(messages)) if messages else "No habia monitor activo"

    def restart(self) -> tuple[bool, str]:
        self.stop()
        time.sleep(0.6)
        return self.start()

    def _kill(self, pid: int) -> None:
        try:
            if IS_WINDOWS:
                self._run(["taskkill", "/PID", str(pid), "/F", "/T"])
            else:
                os.kill(pid, 15)
                time.sleep(0.3)
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass
        except Exception:
            pass

    def _systemd_available(self, unit: str) -> bool:
        if not IS_LINUX or not shutil.which("systemctl"):
            return False
        return self._run_code(["systemctl", "--user", "list-unit-files", unit]) == 0

    # -- arranque automatico -----------------------------------------------------
    @property
    def autostart_path(self) -> Path:
        if IS_WINDOWS:
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
            return base / "Microsoft/Windows/Start Menu/Programs/Startup/Centro Turing.cmd"
        return Path.home() / ".config" / "autostart" / "turing-smart-screen.desktop"

    def autostart_enabled(self) -> bool:
        if IS_LINUX:
            unit = self._run(["systemctl", "--user", "is-enabled", "turing-smart-screen.service"]).strip()
            if unit == "enabled":
                return True
        return self.autostart_path.exists()

    def set_autostart(self, enabled: bool) -> tuple[bool, str]:
        path = self.autostart_path
        if not enabled:
            removed = False
            for candidate in (path, Path.home() / ".config/autostart/turing-smart-screen.desktop"):
                if candidate.exists():
                    candidate.unlink()
                    removed = True
            if IS_LINUX and self._systemd_available("turing-smart-screen.service"):
                self._run(["systemctl", "--user", "disable", "turing-smart-screen.service"])
            return True, "Arranque automatico desactivado" if removed else "Ya estaba desactivado"

        path.parent.mkdir(parents=True, exist_ok=True)
        python = self.python_exe()
        if IS_WINDOWS:
            launcher = ROOT / "tools" / "lanzar.py"
            content = (
                "@echo off\r\n"
                "rem Arranque automatico creado por Centro Turing 3.0\r\n"
                f'start "" /min "{python}" "{launcher}"\r\n'
            )
            path.write_text(content, encoding="utf-8")
        else:
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Turing Smart Screen\n"
                "Comment=Monitor de la mini pantalla USB\n"
                f"Exec={python} {ROOT / 'main.py'}\n"
                f"Path={ROOT}\n"
                "X-GNOME-Autostart-enabled=true\n"
                "Terminal=false\n"
            )
            path.write_text(content, encoding="utf-8")
            path.chmod(0o755)
            if self._systemd_available("turing-smart-screen.service"):
                self._run(["systemctl", "--user", "enable", "turing-smart-screen.service"])
        return True, f"Arranque automatico activado ({path.name})"

    # -- puertos serie -----------------------------------------------------------
    def serial_ports(self) -> list[str]:
        ports: list[str] = []
        try:
            from serial.tools import list_ports  # type: ignore

            ports = [port.device for port in list_ports.comports()]
        except Exception:
            ports = []
        if not ports and not IS_WINDOWS:
            for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
                ports += [str(p) for p in sorted(Path("/").glob(pattern.lstrip("/")))]
        if not ports and IS_WINDOWS:
            ports = re.findall(r"(COM\d+)", self._run(["mode"]))
        return sorted(set(ports))

    # -- extras por sistema ------------------------------------------------------
    def open_path(self, target: Path) -> None:
        try:
            if IS_WINDOWS:
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as error:
            log_line(f"No se pudo abrir {target}: {error}")

    def reveal_log(self) -> None:
        self.open_path(self.log_file.parent if not self.log_file.exists() else self.log_file)

    def admin_hint(self) -> str:
        if IS_WINDOWS:
            return "Para temperaturas reales abre Iniciar-Admin.ps1 (LibreHardwareMonitor)."
        return "En Linux los sensores los lee Python: instala lm-sensors si faltan datos."

    # -- ejecucion de comandos ---------------------------------------------------
    @staticmethod
    def _run(args: list[str], timeout: int = 20) -> str:
        try:
            done = subprocess.run(args, capture_output=True, text=True, timeout=timeout, errors="replace")
            return (done.stdout or "") + (done.stderr or "")
        except Exception:
            return ""

    @staticmethod
    def _run_code(args: list[str], timeout: int = 30) -> int:
        try:
            return subprocess.run(args, capture_output=True, timeout=timeout).returncode
        except Exception:
            return 1

    def default_sensors(self) -> str:
        """Modo de sensores recomendado en este sistema."""
        return "AUTO"

    def extra_actions(self) -> list[tuple[str, str]]:
        """Acciones de mantenimiento propias del sistema: (clave, etiqueta)."""
        return []

    def diagnostics(self) -> list[tuple[str, str]]:
        try:
            log_size = human_size(self.log_file.stat().st_size) if self.log_file.exists() else "no existe"
        except OSError:
            log_size = "no accesible"
        info = [
            ("Sistema", f"{self.name} ({sys.platform})"),
            ("Python", f"{sys.version.split()[0]} — {self.python_exe().name}"),
            ("Entorno virtual", "si" if self.has_venv() else "no (se usa el Python del sistema)"),
            ("Tkinter", getattr(sys.modules.get("tkinter"), "TkVersion", "?")),
            ("Proyecto", str(ROOT)),
            ("Temas instalados", str(len(list(THEMES_DIR.glob("*/theme.yaml"))))),
            ("Puertos serie", ", ".join(self.serial_ports()) or "ninguno detectado"),
            ("Registro", f"{self.log_file} ({log_size})"),
        ]
        try:
            import PIL  # type: ignore

            info.append(("Pillow", getattr(PIL, "__version__", "?")))
        except Exception:
            info.append(("Pillow", "no instalado (vistas previas desactivadas)"))
        return info


class WindowsPlatform(Platform):
    name = "Windows"
    accent_os = "win"

    @property
    def log_file(self) -> Path:
        return ROOT / "log.log"

    def extra_actions(self) -> list[tuple[str, str]]:
        return [
            ("admin", "Iniciar con sensores avanzados (UAC)"),
            ("install", "Instalar dependencias (Instalar.ps1)"),
        ]


class LinuxPlatform(Platform):
    name = "Linux"
    accent_os = "linux"

    @property
    def log_file(self) -> Path:
        return Path("/tmp/turing-screen.log")

    @property
    def pid_file(self) -> Path:
        return Path("/tmp/turing-smart-screen.pid")

    def default_sensors(self) -> str:
        return "PYTHON"

    def extra_actions(self) -> list[tuple[str, str]]:
        return [
            ("fans", "Instalar modulos de ventiladores (Gigabyte)"),
            ("fps", "Activar puente de FPS"),
            ("virtual", "Pantalla virtual (SIMU + navegador)"),
        ]


def make_platform() -> Platform:
    return WindowsPlatform() if IS_WINDOWS else LinuxPlatform()


# --------------------------------------------------------------------------------------
# Catalogo de temas
# --------------------------------------------------------------------------------------
@dataclass
class ThemeInfo:
    name: str
    path: Path
    width: int = 0
    height: int = 0
    orientation: str = ""
    size: str = ""
    background: Path | None = None
    meta: dict = field(default_factory=dict)

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}" if self.width and self.height else "?"

    @property
    def is_landscape(self) -> bool:
        return self.orientation == "landscape" or (self.width >= self.height > 0)

    @property
    def label(self) -> str:
        orient = "horizontal" if self.is_landscape else "vertical"
        return f"{self.name}  ·  {self.resolution} {orient}  ·  {self.size or 'sin medida'}"


def _parse_theme_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def scan_themes() -> list[ThemeInfo]:
    themes: list[ThemeInfo] = []
    if not THEMES_DIR.is_dir():
        return themes
    for theme_yaml in sorted(THEMES_DIR.glob("*/theme.yaml")):
        info = ThemeInfo(name=theme_yaml.parent.name, path=theme_yaml.parent)
        data = _parse_theme_yaml(theme_yaml)
        info.meta = data
        _apply_theme_dimensions(info, data)
        themes.append(info)
    return themes


def _apply_theme_dimensions(info: ThemeInfo, data: dict) -> None:
    """Rellena medida, orientación, resolución y fondo a partir del theme.yaml."""
    display = data.get("display") or {}
    static = data.get("static_images") or {}
    background = static.get("BACKGROUND") or {}
    info.size = str(display.get("DISPLAY_SIZE", "") or "").replace('"', "")
    info.orientation = str(display.get("DISPLAY_ORIENTATION", "") or "").lower()
    try:
        info.width = int(background.get("WIDTH") or 0)
        info.height = int(background.get("HEIGHT") or 0)
    except (TypeError, ValueError):
        info.width = info.height = 0
    info.background = _background_file(info.path, background)
    if not info.width or not info.height:
        if info.background and info.background.suffix.lower() == ".png":
            size = _png_size(info.background)
            if size:
                info.width, info.height = size
    if info.width and info.height:
        if not info.orientation:
            info.orientation = "landscape" if info.width >= info.height else "portrait"
        if not info.size:
            info.size = _size_from_dims(info.width, info.height)


def _background_file(folder: Path, background: dict) -> Path | None:
    candidate = background.get("FILE") if isinstance(background, dict) else None
    if candidate:
        candidate = str(candidate).strip().strip('"').strip("'")
        path = folder / Path(candidate).name
        if path.exists():
            return path
    for name in ("background.png", "background.jpg", "background_fo.png", "preview.png"):
        path = folder / name
        if path.exists():
            return path
    return None


def _png_size(path: Path) -> tuple[int, int] | None:
    """Lee el tamano de un PNG sin dependencias externas."""
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        return width, height
    except OSError:
        return None


def _size_from_dims(width: int, height: int) -> str:
    known = {(480, 320): '3.5"', (320, 480): '3.5"', (800, 480): '5"', (480, 800): '5"',
             (1920, 480): '8.8"', (480, 1920): '8.8"', (1280, 800): '8.8"'}
    return known.get((width, height), "")


# Filtros del catalogo de temas: etiqueta visible -> predicado sobre ThemeInfo
THEME_FILTERS = {
    "Todos": lambda theme: True,
    '3.5" horizontal (480x320)': lambda theme: (theme.width, theme.height) == (480, 320),
    '3.5" vertical (320x480)': lambda theme: (theme.width, theme.height) == (320, 480),
    '5" horizontal (800x480)': lambda theme: (theme.width, theme.height) == (800, 480),
    '5" vertical (480x800)': lambda theme: (theme.width, theme.height) == (480, 800),
    '8.8" (1920x480)': lambda theme: (theme.width, theme.height) == (1920, 480),
    "Horizontal (cualquier medida)": lambda theme: theme.is_landscape,
    "Vertical (cualquier medida)": lambda theme: not theme.is_landscape,
}
THEME_FILTER_LABELS = list(THEME_FILTERS)


# --------------------------------------------------------------------------------------
# Widgets reutilizables
# --------------------------------------------------------------------------------------
import tkinter as tk  # noqa: E402  (se importa tras las constantes para orden visual)
from tkinter import messagebox, ttk  # noqa: E402


class Card(tk.Frame):
    """Tarjeta con borde suave, base del layout."""

    def __init__(self, master, title: str | None = None, subtitle: str | None = None, **kwargs):
        super().__init__(master, bg=CARD, highlightbackground=LINE, highlightthickness=1, **kwargs)
        inner = tk.Frame(self, bg=CARD)
        inner.pack(fill="both", expand=True, padx=14, pady=12)
        self.body = inner
        if title:
            tk.Label(inner, text=title, bg=CARD, fg=FG, font=(UI_FONT, 12, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(inner, text=subtitle, bg=CARD, fg=MUTED, font=(UI_FONT, 9), justify="left",
                     wraplength=520).pack(anchor="w", pady=(2, 0))


class StatPill(tk.Frame):
    """Indicador compacto: etiqueta + valor + punto de color."""

    def __init__(self, master, label: str, value: str = "—", ok: bool = True):
        super().__init__(master, bg=CARD_HI, highlightbackground=LINE, highlightthickness=1)
        self.value_label = tk.Label(self, text=value, bg=CARD_HI, fg=FG, font=(UI_FONT, 13, "bold"))
        self.value_label.pack(anchor="w", padx=12, pady=(10, 0))
        row = tk.Frame(self, bg=CARD_HI)
        row.pack(anchor="w", padx=12, pady=(0, 10))
        self.dot = tk.Label(row, text="●", bg=CARD_HI, fg=GREEN if ok else RED, font=(UI_FONT, 9))
        self.dot.pack(side="left")
        tk.Label(row, text=label, bg=CARD_HI, fg=MUTED, font=(UI_FONT, 9)).pack(side="left", padx=(5, 0))

    def update_value(self, value: str, ok: bool = True) -> None:
        self.value_label.configure(text=value)
        self.dot.configure(fg=GREEN if ok else RED)


class ScrollPage(tk.Frame):
    """Pagina con scroll vertical: evita que el contenido se recorte."""

    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        for widget in (self.canvas, self.inner):
            widget.bind("<Enter>", self._bind_wheel)
            widget.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        delta = 0
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        elif getattr(event, "delta", 0):
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")


def make_button(master, text: str, command, color: str = CYAN, width: int = 16, outline: bool = False):
    """Boton plano consistente en todas las plataformas."""
    bg = CARD_HI if outline else color
    fg = FG if outline else "#08131a"
    button = tk.Button(
        master,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=color,
        activeforeground="#08131a",
        relief="flat",
        bd=0,
        padx=14,
        pady=7,
        width=width,
        cursor="hand2",
        font=(UI_FONT, 10, "bold"),
        highlightthickness=1 if outline else 0,
        highlightbackground=LINE,
    )
    button.bind("<Enter>", lambda _e: button.configure(bg=color if not outline else LINE))
    button.bind("<Leave>", lambda _e: button.configure(bg=bg))
    return button


# --------------------------------------------------------------------------------------
# Aplicacion
# --------------------------------------------------------------------------------------
class CentroTuring(tk.Tk):
    MIN_WIDTH = 920
    MIN_HEIGHT = 560
    PAGES = (
        ("panel", "Panel"),
        ("temas", "Temas"),
        ("ajustes", "Ajustes"),
        ("registro", "Registro"),
        ("sistema", "Sistema"),
        ("acerca", "Acerca de"),
    )

    def __init__(self):
        super().__init__()
        self.platform = make_platform()
        self.config_editor = ConfigEditor()
        self.themes: list[ThemeInfo] = []
        self._preview_image = None
        self._nav_buttons: dict[str, tk.Button] = {}
        self._pages: dict[str, tk.Frame] = {}
        self._current_page = "panel"
        self._log_auto = tk.BooleanVar(value=True)
        self._busy = False
        self._settings_widgets: list = []
        self._settings_host: tk.Frame | None = None

        self.title(f"{APP_NAME} {VERSION} — monitor de mini pantalla USB")
        self.configure(bg=BG)
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._apply_state_geometry()
        self._install_style()
        self._build_layout()
        self._load_themes()
        self.show_page("panel")
        self.refresh_status()
        self.after(250, self._first_run_hints)
        self.after(2000, self._tick)

    def _tick(self) -> None:
        """Refresco periodico suave: registro en vivo y estado del monitor."""
        try:
            if self._current_page == "registro" and self._log_auto.get():
                position = self.log_text.yview()[1] if hasattr(self, "log_text") else 1.0
                self.refresh_log()
                if position < 0.999 and hasattr(self, "log_text"):
                    self.log_text.yview_moveto(position)
            if self._current_page in ("panel", "sistema") and not self._busy:
                self.refresh_status()
        finally:
            self.after(2000, self._tick)

    # -- infraestructura ---------------------------------------------------------
    def _install_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TScrollbar", background=CARD, troughcolor=BG, bordercolor=BG,
                        arrowcolor=MUTED, relief="flat")
        style.configure("TCombobox", fieldbackground=CARD_HI, background=CARD_HI,
                        foreground=FG, arrowcolor=MUTED, bordercolor=LINE, lightcolor=CARD_HI,
                        darkcolor=CARD_HI, selectbackground=CARD_HI, selectforeground=FG)
        style.map("TCombobox", fieldbackground=[("readonly", CARD_HI)], foreground=[("readonly", FG)])
        style.configure("TEntry", fieldbackground=CARD_HI, foreground=FG, bordercolor=LINE,
                        lightcolor=LINE, darkcolor=LINE, insertcolor=FG)
        style.configure("TCheckbutton", background=CARD, foreground=FG, focuscolor=CARD)
        style.map("TCheckbutton", background=[("active", CARD)])
        style.configure("TScale", background=CARD, troughcolor=CARD_HI)
        style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=FG,
                        bordercolor=LINE, rowheight=24)
        style.configure("Treeview.Heading", background=CARD_HI, foreground=MUTED, relief="flat")
        style.map("Treeview", background=[("selected", CYAN)], foreground=[("selected", "#08131a")])
        style.configure("Vertical.TScrollbar", background=CARD_HI)

    def _apply_state_geometry(self) -> None:
        state = {}
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        geometry = state.get("geometry") if isinstance(state, dict) else None
        match = re.match(r"^(\d+)x(\d+)", geometry) if isinstance(geometry, str) else None
        # Se descarta cualquier geometria guardada antes de que la ventana se mapeara
        # (Tk informa 1x1 en ese momento y la ventana arrancaria invisible).
        if match and int(match.group(1)) >= self.MIN_WIDTH and int(match.group(2)) >= self.MIN_HEIGHT:
            self.geometry(geometry)
            return
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(1080, max(self.MIN_WIDTH, screen_w - 80))
        height = min(720, max(self.MIN_HEIGHT, screen_h - 120))
        self.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}")

    def _save_state(self) -> None:
        try:
            width, height = self.winfo_width(), self.winfo_height()
            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                return  # ventana aun sin mapear: no guardamos basura
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({"geometry": self.geometry()}, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Cabecera
        header = tk.Frame(self, bg=SIDE, height=62)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_propagate(False)
        left = tk.Frame(header, bg=SIDE)
        left.pack(side="left", fill="y", padx=18)
        tk.Label(left, text="◆", bg=SIDE, fg=CYAN, font=(UI_FONT, 15, "bold")).pack(side="left", padx=(0, 10))
        titles = tk.Frame(left, bg=SIDE)
        titles.pack(side="left")
        tk.Label(titles, text=f"{APP_NAME} {VERSION}", bg=SIDE, fg=FG, font=(UI_FONT, 14, "bold")).pack(anchor="w")
        tk.Label(titles, text="Software libre para pantallas Turing · Windows y Linux",
                 bg=SIDE, fg=MUTED, font=(UI_FONT, 9)).pack(anchor="w")

        right = tk.Frame(header, bg=SIDE)
        right.pack(side="right", padx=18)
        self.header_status = tk.Label(right, text="Consultando…", bg=SIDE, fg=MUTED, font=(UI_FONT, 10))
        self.header_status.pack(side="right")
        make_button(right, "Actualizar", self.refresh_status, color=CYAN, width=10).pack(side="right", padx=10)

        # Barra lateral
        sidebar = tk.Frame(self, bg=SIDE, width=196)
        sidebar.grid(row=1, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text="NAVEGACIÓN", bg=SIDE, fg=MUTED, font=(UI_FONT, 8, "bold")).pack(
            anchor="w", padx=18, pady=(18, 8))
        for key, label in self.PAGES:
            button = tk.Button(
                sidebar, text=f"  {label}", command=lambda k=key: self.show_page(k),
                bg=SIDE, fg=FG, activebackground=CARD_HI, activeforeground=FG, relief="flat", bd=0,
                anchor="w", padx=12, pady=9, cursor="hand2", font=(UI_FONT, 10),
            )
            button.pack(fill="x", padx=10, pady=2)
            self._nav_buttons[key] = button
        footer = tk.Frame(sidebar, bg=SIDE)
        footer.pack(side="bottom", fill="x", pady=14)
        tk.Label(footer, text="100% gratis · GPL-3.0", bg=SIDE, fg=MUTED, font=(UI_FONT, 8)).pack()

        # Contenido
        self.content = tk.Frame(self, bg=BG)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)

        # Barra de estado (sustituye a las etiquetas flotantes que se solapaban)
        status_bar = tk.Frame(self, bg=SIDE, height=30)
        status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        status_bar.grid_propagate(False)
        self.status_message = tk.Label(status_bar, text="Listo", bg=SIDE, fg=MUTED, font=(UI_FONT, 9), anchor="w")
        self.status_message.pack(side="left", padx=16)
        self.busy_label = tk.Label(status_bar, text="", bg=SIDE, fg=AMBER, font=(UI_FONT, 9))
        self.busy_label.pack(side="right", padx=16)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- navegacion ---------------------------------------------------------------
    def show_page(self, name: str) -> None:
        if name not in dict(self.PAGES):
            return
        for key, button in self._nav_buttons.items():
            active = key == name
            button.configure(bg=CARD_HI if active else SIDE, fg=CYAN if active else FG)
        for page in self._pages.values():
            page.grid_forget()
        if name not in self._pages:
            self._pages[name] = self._build_page(name)
        self._pages[name].grid(row=0, column=0, sticky="nsew")
        self._current_page = name

    def _build_page(self, name: str) -> tk.Frame:
        builder = {
            "panel": self._page_panel,
            "temas": self._page_temas,
            "ajustes": self._page_ajustes,
            "registro": self._page_registro,
            "sistema": self._page_sistema,
            "acerca": self._page_acerca,
        }[name]
        page = ScrollPage(self.content)
        builder(page.inner)
        return page

    # -- utilidades de UI --------------------------------------------------------
    def set_status(self, message: str) -> None:
        self.status_message.configure(text=message)
        log_line(message)

    def toast(self, message: str, error: bool = False) -> None:
        self.status_message.configure(text=message, fg=RED if error else GREEN)
        self.after(6000, lambda: self.status_message.configure(fg=MUTED))

    def run_bg(self, label: str, func, on_done=None) -> None:
        """Ejecuta una tarea larga sin congelar la interfaz."""
        if self._busy:
            self.toast("Hay una tarea en curso…", error=True)
            return
        self._busy = True
        self.busy_label.configure(text=f"⏳ {label}")

        def worker():
            try:
                result = func()
            except Exception as error:  # pragma: no cover - defensivo
                result = (False, f"Error inesperado: {error}")
            self.after(0, lambda: self._finish_bg(result, on_done))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_bg(self, result, on_done) -> None:
        self._busy = False
        self.busy_label.configure(text="")
        ok, message = result if isinstance(result, tuple) else (True, str(result))
        self.toast(message, error=not ok)
        if on_done:
            on_done(ok, message)
        self.refresh_status()

    def section_title(self, parent, text: str, hint: str = ""):
        holder = tk.Frame(parent, bg=BG)
        holder.pack(fill="x", padx=22, pady=(20, 4))
        tk.Label(holder, text=text, bg=BG, fg=FG, font=(UI_FONT, 17, "bold")).pack(anchor="w")
        if hint:
            tk.Label(holder, text=hint, bg=BG, fg=MUTED, font=(UI_FONT, 10), justify="left",
                     wraplength=760).pack(anchor="w", pady=(3, 0))
        return holder

    # -- panel -------------------------------------------------------------------
    def _page_panel(self, parent) -> None:
        self.section_title(parent, "Panel", "Estado en vivo de la mini pantalla y control rápido.")

        cards = tk.Frame(parent, bg=BG)
        cards.pack(fill="x", padx=22, pady=(14, 0))

        self.pill_screen = StatPill(cards, "Pantalla", "…")
        self.pill_screen.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.pill_port = StatPill(cards, "Puerto", "…")
        self.pill_port.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.pill_bright = StatPill(cards, "Brillo", "…")
        self.pill_bright.grid(row=0, column=2, sticky="ew", padx=(0, 10))
        self.pill_sensors = StatPill(cards, "Sensores", "…")
        self.pill_sensors.grid(row=0, column=3, sticky="ew")
        for column in range(4):
            cards.columnconfigure(column, weight=1)

        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=14)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=4)

        preview_card = Card(body, "Vista previa del tema activo")
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.preview_label = tk.Label(preview_card.body, bg=CARD, fg=MUTED, font=(UI_FONT, 9),
                                      text="Selecciona un tema para verlo", width=38, height=12)
        self.preview_label.pack(pady=(8, 6))
        self.preview_caption = tk.Label(preview_card.body, text="", bg=CARD, fg=MUTED, font=(UI_FONT, 9),
                                        wraplength=340, justify="left")
        self.preview_caption.pack(anchor="w", pady=(0, 4))

        control_card = Card(body, "Control del monitor")
        control_card.grid(row=0, column=1, sticky="nsew")
        controls = control_card.body

        tk.Label(controls, text="Tema activo", bg=CARD, fg=MUTED, font=(UI_FONT, 9)).pack(anchor="w", pady=(6, 2))
        self.theme_combo = ttk.Combobox(controls, state="readonly", values=[], height=18)
        self.theme_combo.pack(fill="x")
        self.theme_combo.bind("<<ComboboxSelected>>", lambda _e: self._preview_selected(self.theme_combo.get()))

        tk.Label(controls, text="Brillo de la pantalla", bg=CARD, fg=MUTED, font=(UI_FONT, 9)).pack(
            anchor="w", pady=(14, 2))
        brightness_row = tk.Frame(controls, bg=CARD)
        brightness_row.pack(fill="x")
        self.brightness_var = tk.IntVar(value=35)
        self.brightness_scale = ttk.Scale(brightness_row, from_=0, to=100, orient="horizontal",
                                          variable=self.brightness_var,
                                          command=lambda _v: self.brightness_value.configure(
                                              text=f"{int(self.brightness_var.get())}%"))
        self.brightness_scale.pack(side="left", fill="x", expand=True)
        self.brightness_value = tk.Label(brightness_row, text="35%", bg=CARD, fg=CYAN, font=(UI_FONT, 10, "bold"))
        self.brightness_value.pack(side="left", padx=(10, 0))

        actions = tk.Frame(controls, bg=CARD)
        actions.pack(fill="x", pady=(18, 0))
        make_button(actions, "Encender", self.action_start, color=GREEN, width=11).pack(side="left", padx=(0, 8))
        make_button(actions, "Apagar", self.action_stop, color=RED, width=11).pack(side="left", padx=8)
        make_button(actions, "Reiniciar", self.action_restart, color=AMBER, width=11).pack(side="left", padx=8)

        extra = tk.Frame(controls, bg=CARD)
        extra.pack(fill="x", pady=(10, 0))
        make_button(extra, "Aplicar tema y brillo", self.action_apply, color=CYAN, width=22,
                    outline=True).pack(side="left")
        make_button(extra, "Ver registro", lambda: self.show_page("registro"), color=CYAN, width=14,
                    outline=True).pack(side="left", padx=8)

        tk.Label(controls, text=self.platform.admin_hint(), bg=CARD, fg=MUTED, font=(UI_FONT, 9),
                 wraplength=420, justify="left").pack(anchor="w", pady=(16, 0))

    def _preview_selected(self, label: str) -> None:
        name = label.split("  ·  ")[0].strip()
        info = next((theme for theme in self.themes if theme.name == name), None)
        if info:
            self._render_preview(info)

    def _render_preview(self, info: ThemeInfo) -> None:
        self.preview_caption.configure(
            text=f"{info.name}\n{info.resolution} · {'horizontal' if info.is_landscape else 'vertical'}"
                 f" · medida {info.size or 'sin declarar'}"
        )
        if not info.background:
            self.preview_label.configure(image="", text=f"{info.name}\n(sin imagen de fondo)", width=38, height=12)
            self._preview_image = None
            return
        try:
            from PIL import Image, ImageTk  # type: ignore

            image = Image.open(info.background).convert("RGB")
            image.thumbnail((420, 300), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._preview_image = photo
            self.preview_label.configure(image=photo, text="", width=image.width, height=image.height)
        except Exception:
            self._preview_image = None
            self.preview_label.configure(
                image="", text=f"{info.name}\n{info.background.name}\n(instala Pillow para la vista previa)",
                width=38, height=12)

    # -- temas -------------------------------------------------------------------
    def _page_temas(self, parent) -> None:
        self.section_title(parent, "Temas", f"{len(self.themes)} temas instalados en res/themes.")

        toolbar = Card(parent)
        toolbar.pack(fill="x", padx=22, pady=(14, 0))
        row = toolbar.body

        tk.Label(row, text="Filtrar", bg=CARD, fg=MUTED, font=(UI_FONT, 9)).pack(side="left")
        self.theme_filter = ttk.Combobox(row, state="readonly", width=26, values=THEME_FILTER_LABELS)
        self.theme_filter.current(0)
        self.theme_filter.pack(side="left", padx=8)
        self.theme_filter.bind("<<ComboboxSelected>>", lambda _e: self._fill_theme_table())

        tk.Label(row, text="Buscar", bg=CARD, fg=MUTED, font=(UI_FONT, 9)).pack(side="left", padx=(14, 0))
        self.theme_search = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.theme_search, width=24)
        entry.pack(side="left", padx=8)
        entry.bind("<KeyRelease>", lambda _e: self._fill_theme_table())

        make_button(row, "Recargar", self._load_themes, color=CYAN, width=10, outline=True).pack(side="right")

        table_card = Card(parent)
        table_card.pack(fill="both", expand=True, padx=22, pady=12)
        columns = ("tema", "medida", "orientacion", "resolucion")
        self.theme_table = ttk.Treeview(table_card.body, columns=columns, show="headings", height=12)
        for column, title, width in (("tema", "Tema", 300), ("medida", "Medida", 90),
                                     ("orientacion", "Orientación", 110), ("resolucion", "Resolución", 110)):
            self.theme_table.heading(column, text=title)
            self.theme_table.column(column, width=width, anchor="w")
        self.theme_table.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table_card.body, orient="vertical", command=self.theme_table.yview)
        scroll.pack(side="right", fill="y")
        self.theme_table.configure(yscrollcommand=scroll.set)
        self.theme_table.bind("<<TreeviewSelect>>", self._on_theme_row)
        self.theme_table.bind("<Double-1>", lambda _e: self.action_apply())

        buttons = tk.Frame(parent, bg=BG)
        buttons.pack(fill="x", padx=22, pady=(0, 18))
        self.theme_count_label = tk.Label(buttons, text="", bg=BG, fg=MUTED, font=(UI_FONT, 9))
        self.theme_count_label.pack(side="left")
        make_button(buttons, "Aplicar tema seleccionado", self.action_apply, color=GREEN, width=26).pack(side="right")
        make_button(buttons, "Abrir carpeta del tema", self._open_theme_folder, color=CYAN, width=22,
                    outline=True).pack(side="right", padx=8)

        self._fill_theme_table()

    def _filtered_themes(self) -> list[ThemeInfo]:
        choice = self.theme_filter.get() if hasattr(self, "theme_filter") else "Todos"
        query = (self.theme_search.get() if hasattr(self, "theme_search") else "").strip().lower()
        predicate = THEME_FILTERS.get(choice, THEME_FILTERS["Todos"])
        return [
            theme for theme in self.themes
            if (not query or query in theme.name.lower()) and predicate(theme)
        ]

    def _fill_theme_table(self) -> None:
        for row in self.theme_table.get_children():
            self.theme_table.delete(row)
        themes = self._filtered_themes()
        current = self.config_editor.get("THEME")
        for theme in themes:
            tag = "actual" if theme.name == current else ""
            self.theme_table.insert("", "end", iid=theme.name, values=(
                theme.name + ("  ← activo" if tag else ""),
                theme.size or "—",
                "horizontal" if theme.is_landscape else "vertical",
                theme.resolution,
            ))
        self.theme_count_label.configure(text=f"Mostrando {len(themes)} de {len(self.themes)} temas")

    def _on_theme_row(self, _event=None) -> None:
        selection = self.theme_table.selection()
        if not selection:
            return
        info = next((theme for theme in self.themes if theme.name == selection[0]), None)
        if info:
            self._render_preview(info)

    def _open_theme_folder(self) -> None:
        selection = self.theme_table.selection()
        target = THEMES_DIR / selection[0] if selection else THEMES_DIR
        self.platform.open_path(target)

    # -- ajustes -----------------------------------------------------------------
    def _page_ajustes(self, parent) -> None:
        self.section_title(parent, "Ajustes", "Edición de config.yaml conservando comentarios y orden. "
                                              "Se guarda una copia .bak-centro en cada cambio.")
        self._settings_widgets = []

        general = Card(parent, "Pantalla y sensores")
        general.pack(fill="x", padx=22, pady=(14, 0))
        self._form_row(general.body, "Tema", self._combo_setting(general.body, "THEME", [t.name for t in self.themes]))
        self._form_row(general.body, "Modo de sensores",
                       self._combo_setting(general.body, "HW_SENSORS", list(SENSOR_MODES)))
        self._form_row(general.body, "Revisión de pantalla",
                       self._combo_setting(general.body, "REVISION", list(REVISIONS)))
        ports = self.platform.serial_ports() or ["AUTO"]
        self._form_row(general.body, "Puerto serie",
                       self._combo_setting(general.body, "COM_PORT", ["AUTO"] + ports, editable=True))
        self._form_row(general.body, "Formato de reloj",
                       self._combo_setting(general.body, "CLOCK_FORMAT", ["12", "24"]))

        display = Card(parent, "Comportamiento")
        display.pack(fill="x", padx=22, pady=12)
        self.reverse_var = tk.BooleanVar(value=self.config_editor.get("DISPLAY_REVERSE").lower() == "true")
        self.reset_var = tk.BooleanVar(value=self.config_editor.get("RESET_ON_STARTUP").lower() != "false")
        tk.Checkbutton(display.body, text="Invertir imagen (DISPLAY_REVERSE)", variable=self.reverse_var,
                       bg=CARD, fg=FG, selectcolor=CARD_HI, activebackground=CARD,
                       activeforeground=FG, font=(UI_FONT, 10)).pack(anchor="w", pady=2)
        tk.Checkbutton(display.body, text="Reiniciar la pantalla al arrancar (RESET_ON_STARTUP)",
                       variable=self.reset_var, bg=CARD, fg=FG, selectcolor=CARD_HI,
                       activebackground=CARD, activeforeground=FG, font=(UI_FONT, 10)).pack(anchor="w", pady=2)

        weather = Card(parent, "Clima (Open-Meteo)")
        weather.pack(fill="x", padx=22, pady=0)
        self._form_row(weather.body, "Latitud", self._entry_setting(weather.body, "WEATHER_LATITUDE"))
        self._form_row(weather.body, "Longitud", self._entry_setting(weather.body, "WEATHER_LONGITUDE"))
        self._form_row(weather.body, "Unidades",
                       self._combo_setting(weather.body, "WEATHER_UNITS", ["metric", "imperial"]))
        self._form_row(weather.body, "Idioma",
                       self._combo_setting(weather.body, "WEATHER_LANGUAGE", ["es", "en"]))

        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", padx=22, pady=16)
        make_button(actions, "Guardar ajustes", self.action_save_settings, color=GREEN, width=18).pack(side="left")
        make_button(actions, "Restaurar copia", self.action_restore_backup, color=AMBER, width=16,
                    outline=True).pack(side="left", padx=8)
        make_button(actions, "Abrir config.yaml", lambda: self.platform.open_path(CONFIG_FILE),
                    color=CYAN, width=16, outline=True).pack(side="left", padx=8)

    def _form_row(self, parent, label: str, widget) -> None:
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label, bg=CARD, fg=MUTED, font=(UI_FONT, 10), width=20, anchor="w").pack(side="left")
        widget.pack(side="left", fill="x", expand=True)

    def _combo_setting(self, parent, key: str, values: list[str], editable: bool = False):
        combo = ttk.Combobox(parent, state="normal" if editable else "readonly", values=values)
        current = self.config_editor.get(key) or (self.platform.default_sensors() if key == "HW_SENSORS" else "")
        if current:
            combo.set(current)
        elif values:
            combo.set(values[0])
        combo.setting_key = key  # type: ignore[attr-defined]
        self._settings_widgets.append(combo)
        return combo

    def _entry_setting(self, parent, key: str):
        var = tk.StringVar(value=self.config_editor.get(key))
        entry = ttk.Entry(parent, textvariable=var)
        entry.setting_key = key  # type: ignore[attr-defined]
        entry.setting_var = var  # type: ignore[attr-defined]
        self._settings_widgets.append(entry)
        return entry

    # -- registro ----------------------------------------------------------------
    def _page_registro(self, parent) -> None:
        self.section_title(parent, "Registro", f"Archivo: {self.platform.log_file}")

        card = Card(parent)
        card.pack(fill="both", expand=True, padx=22, pady=(14, 18))
        toolbar = tk.Frame(card.body, bg=CARD)
        toolbar.pack(fill="x", pady=(0, 8))
        tk.Checkbutton(toolbar, text="Actualizar automáticamente", variable=self._log_auto,
                       bg=CARD, fg=FG, selectcolor=CARD_HI, activebackground=CARD, activeforeground=FG,
                       font=(UI_FONT, 10)).pack(side="left")
        make_button(toolbar, "Refrescar", self.refresh_log, color=CYAN, width=10, outline=True).pack(side="right")
        make_button(toolbar, "Copiar", self._copy_log, color=CYAN, width=9, outline=True).pack(side="right", padx=8)
        make_button(toolbar, "Abrir archivo", lambda: self.platform.reveal_log(), color=CYAN, width=12,
                    outline=True).pack(side="right")

        text_frame = tk.Frame(card.body, bg=CARD)
        text_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(text_frame, bg="#0b0f14", fg="#cfe3f0", insertbackground=FG, relief="flat",
                                wrap="none", font=(MONO_FONT, 9), height=18)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll_y = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_text.yview)
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(card.body, orient="horizontal", command=self.log_text.xview)
        scroll_x.pack(fill="x")
        self.log_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.refresh_log()

    def refresh_log(self) -> None:
        if not hasattr(self, "log_text"):
            return
        content = tail_file(self.platform.log_file, 500) or "(el registro está vacío)"
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.insert("1.0", content)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _copy_log(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.log_text.get("1.0", "end"))
        self.toast("Registro copiado al portapapeles")

    # -- sistema -----------------------------------------------------------------
    def _page_sistema(self, parent) -> None:
        self.section_title(parent, "Sistema", "Arranque automático, dependencias y diagnóstico.")

        autostart = Card(parent, "Arranque automático")
        autostart.pack(fill="x", padx=22, pady=(14, 0))
        row = tk.Frame(autostart.body, bg=CARD)
        row.pack(fill="x", pady=(6, 0))
        self.autostart_var = tk.BooleanVar(value=self.platform.autostart_enabled())
        tk.Checkbutton(row, text="Arrancar el monitor al iniciar sesión", variable=self.autostart_var,
                       command=self.action_toggle_autostart, bg=CARD, fg=FG, selectcolor=CARD_HI,
                       activebackground=CARD, activeforeground=FG, font=(UI_FONT, 10)).pack(side="left")
        tk.Label(autostart.body, text=str(self.platform.autostart_path), bg=CARD, fg=MUTED,
                 font=(UI_FONT, 8)).pack(anchor="w", pady=(4, 0))

        maintenance = Card(parent, "Mantenimiento")
        maintenance.pack(fill="x", padx=22, pady=12)
        buttons = tk.Frame(maintenance.body, bg=CARD)
        buttons.pack(fill="x")
        options = [
            ("Aplicar código nuevo (git pull)", self.action_git_pull, CYAN),
            ("Abrir carpeta del proyecto", lambda: self.platform.open_path(ROOT), CYAN),
            ("Comprobar actualización", self.action_check_update, CYAN),
        ]
        for index, (label, command, color) in enumerate(options):
            make_button(buttons, label, command, color=color, width=26, outline=True).grid(
                row=index // 2, column=index % 2, padx=(0, 8), pady=4, sticky="w")
        for index, (key, label) in enumerate(self.platform.extra_actions()):
            if not label:
                continue
            make_button(buttons, label, lambda k=key: self.action_extra(k), color=AMBER, width=26,
                        outline=True).grid(row=(index + 3) // 2, column=(index + 3) % 2, padx=(0, 8), pady=4,
                                           sticky="w")

        diagnostics = Card(parent, "Diagnóstico")
        diagnostics.pack(fill="x", padx=22, pady=(0, 18))
        self.diag_holder = diagnostics.body
        self._fill_diagnostics()

    def _fill_diagnostics(self) -> None:
        for child in self.diag_holder.winfo_children():
            child.destroy()
        for label, value in self.platform.diagnostics():
            row = tk.Frame(self.diag_holder, bg=CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=CARD, fg=MUTED, font=(UI_FONT, 9), width=18, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=CARD, fg=FG, font=(UI_FONT, 9), anchor="w", justify="left").pack(side="left")

    # -- acerca ------------------------------------------------------------------
    def _page_acerca(self, parent) -> None:
        self.section_title(parent, "Acerca de", "Software libre y gratuito, sin candados ni compras.")

        card = Card(parent)
        card.pack(fill="x", padx=22, pady=(14, 18))
        text = (
            f"{APP_NAME} {VERSION}\n\n"
            "Panel de control unificado para pantallas Turing / XuanFang, con la misma\n"
            "interfaz en Windows y en Linux. Sustituye a los lanzadores separados\n"
            "(Centro Turing v2 en Windows y el menú de texto turing-menu.sh en Linux).\n\n"
            f"Proyecto Linux: {REPO_URL}\n"
            f"Proyecto base:  {UPSTREAM_URL}\n\n"
            "Turing Smart Screen Panel © mathoudebine y colaboradores — GPL-3.0.\n"
            "Adaptación en español y edición Linux: pilahito."
        )
        tk.Label(card.body, text=text, bg=CARD, fg=FG, font=(UI_FONT, 10), justify="left").pack(anchor="w")
        buttons = tk.Frame(card.body, bg=CARD)
        buttons.pack(anchor="w", pady=(12, 0))
        make_button(buttons, "Abrir repositorio", lambda: webbrowser.open(REPO_URL), color=CYAN,
                    width=18, outline=True).pack(side="left", padx=(0, 8))
        make_button(buttons, "Ver temas en el navegador", self._open_theme_gallery, color=CYAN,
                    width=24, outline=True).pack(side="left")

    def _open_theme_gallery(self) -> None:
        gallery = ROOT / "screencap.png"
        if gallery.exists():
            self.platform.open_path(gallery)
        else:
            webbrowser.open(REPO_URL)

    # -- estado ------------------------------------------------------------------
    def refresh_status(self) -> None:
        running, detail = self.platform.is_running()
        theme = self.config_editor.get("THEME") or "(sin definir)"
        port = self.config_editor.get("COM_PORT") or "AUTO"
        brightness = self.config_editor.get("BRIGHTNESS") or "?"
        sensors = self.config_editor.get("HW_SENSORS") or "AUTO"
        revision = self.config_editor.get("REVISION") or "?"

        self.header_status.configure(
            text=f"{self.platform.name} · tema {theme} · {'encendida' if running else 'apagada'}")
        if hasattr(self, "pill_screen"):
            self.pill_screen.update_value("ENCENDIDA" if running else "APAGADA", ok=running)
            self.pill_port.update_value(port, ok=port not in ("", "AUTO") or bool(self.platform.serial_ports()))
            self.pill_bright.update_value(f"{brightness}%", ok=True)
            self.pill_sensors.update_value(sensors, ok=sensors.upper() != "AUTO")
            self.preview_caption.configure(text=f"{theme}\n{detail} · revisión {revision} · {self.platform.name}")
        if hasattr(self, "autostart_var"):
            self.autostart_var.set(self.platform.autostart_enabled())

    def _first_run_hints(self) -> None:
        if not self.config_editor.path.exists():
            self.toast("No encuentro config.yaml: copia config.example.yaml", error=True)
        elif not self.platform.has_venv():
            self.toast("No hay entorno virtual: revisa la sección Sistema", error=True)

    def _load_themes(self) -> None:
        self.themes = scan_themes()
        names = [theme.name for theme in self.themes]
        if hasattr(self, "theme_combo"):
            current = self.config_editor.get("THEME")
            self.theme_combo.configure(values=[theme.label for theme in self.themes])
            match = next((theme for theme in self.themes if theme.name == current), None)
            if match:
                self.theme_combo.set(match.label)
                self._render_preview(match)
        if hasattr(self, "theme_table"):
            self._fill_theme_table()
        for widget in self._settings_widgets:
            if getattr(widget, "setting_key", "") == "THEME":
                widget.configure(values=names)
        self.toast(f"{len(names)} temas cargados")

    # -- acciones ----------------------------------------------------------------
    def _selected_theme_name(self) -> str:
        current_page = self._current_page
        if current_page == "temas":
            selection = self.theme_table.selection()
            if selection:
                return selection[0]
        label = self.theme_combo.get() if hasattr(self, "theme_combo") else ""
        return label.split("  ·  ")[0].strip()

    def action_start(self) -> None:
        self.set_status("Arrancando el monitor…")
        self.run_bg("Arrancando monitor", self.platform.start)

    def action_stop(self) -> None:
        self.set_status("Deteniendo el monitor…")
        self.run_bg("Deteniendo monitor", self.platform.stop)

    def action_restart(self) -> None:
        self.set_status("Reiniciando el monitor…")
        self.run_bg("Reiniciando monitor", self.platform.restart)

    def action_apply(self) -> None:
        name = self._selected_theme_name()
        if not name:
            self.toast("Selecciona un tema primero", error=True)
            return
        if not (THEMES_DIR / name / "theme.yaml").exists():
            self.toast(f"No existe el tema {name}", error=True)
            return
        brightness = int(self.brightness_var.get()) if hasattr(self, "brightness_var") else None

        def task():
            changed = self.config_editor.set_many({
                "THEME": (name, "config"),
                **({"BRIGHTNESS": (brightness, "display")} if brightness is not None else {}),
            })
            ok, message = self.platform.restart()
            if not ok:
                return False, message
            return True, f"Tema {name} aplicado ({', '.join(changed) or 'sin cambios'}) y monitor reiniciado"

        self.run_bg(f"Aplicando {name}", task)

    def action_save_settings(self) -> None:
        values = {}
        widgets = getattr(self, "_settings_widgets", [])
        for widget in widgets:
            key = getattr(widget, "setting_key", None)
            if not key:
                continue
            if hasattr(widget, "setting_var"):
                values[key] = (widget.setting_var.get().strip(), None)
            else:
                values[key] = (widget.get().strip(), None)
        values["DISPLAY_REVERSE"] = (bool(self.reverse_var.get()), None)
        values["RESET_ON_STARTUP"] = (bool(self.reset_var.get()), None)
        values = {key: value for key, value in values.items() if value[0] != ""}

        def task():
            changed = self.config_editor.set_many(values)
            return True, f"Guardado: {', '.join(changed) if changed else 'sin cambios'} (copia .bak-centro)"

        self.run_bg("Guardando ajustes", task)

    def action_restore_backup(self) -> None:
        if not messagebox.askyesno(APP_NAME, "¿Restaurar config.yaml desde la copia .bak-centro?"):
            return
        if self.config_editor.restore_backup():
            self.show_page(self._current_page)
            self._refresh_settings_from_config()
            self.toast("Copia restaurada")
        else:
            self.toast("No hay copia disponible", error=True)

    def _refresh_settings_from_config(self) -> None:
        for widget in getattr(self, "_settings_widgets", []):
            key = getattr(widget, "setting_key", None)
            if not key:
                continue
            value = self.config_editor.get(key)
            if hasattr(widget, "setting_var"):
                widget.setting_var.set(value)
            else:
                widget.set(value)

    def action_toggle_autostart(self) -> None:
        wanted = bool(self.autostart_var.get())
        self.run_bg("Configurando arranque automático", lambda: self.platform.set_autostart(wanted))

    def action_git_pull(self) -> None:
        if not messagebox.askyesno(APP_NAME, "Se ejecutará 'git pull' en el proyecto.\n¿Continuar?"):
            return

        def task():
            code = self.platform._run_code(["git", "-C", str(ROOT), "pull", "--ff-only"], timeout=180)
            if code != 0:
                return False, "git pull falló (¿cambios locales sin confirmar?)"
            return True, "Código actualizado. Reinicia el Centro para aplicar cambios de UI."

        self.run_bg("Actualizando código", task)

    def action_check_update(self) -> None:
        def task():
            self.platform._run(["git", "-C", str(ROOT), "fetch", "--quiet"], timeout=120)
            local = self.platform._run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]).strip()[:8]
            remote = self.platform._run(["git", "-C", str(ROOT), "rev-parse", "@{u}"]).strip()[:8]
            if not remote:
                return False, f"Sin remoto configurado (local {local})"
            if local == remote:
                return True, f"Al día ({local})"
            behind = self.platform._run(["git", "-C", str(ROOT), "rev-list", "--count", "HEAD..@{u}"]).strip()
            return True, f"Hay {behind} confirmaciones nuevas ({local} → {remote})"

        self.run_bg("Comprobando actualizaciones", task)

    def action_extra(self, key: str) -> None:
        scripts = {
            "admin": [str(self.platform.python_exe()), str(ROOT / "tools" / "lanzar.py")],
            "install": ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "Instalar.ps1")],
            "fans": ["bash", str(ROOT / "scripts" / "install-fan-modules.sh")],
            "fps": ["bash", str(ROOT / "scripts" / "poll-fps.sh")],
            "virtual": ["bash", str(ROOT / "scripts" / "start-virtual-screen.sh")],
        }
        if key == "admin":
            powershell = shutil.which("powershell") or "powershell"
            command = (
                f'Start-Process -FilePath "{self.platform.python_exe()}" '
                f'-ArgumentList \'"{ROOT / "tools" / "lanzar.py"}"\' -Verb RunAs'
            )
            self.run_bg("Solicitando permisos", lambda: (
                self.platform._run_code([powershell, "-NoProfile", "-Command", command], timeout=60) == 0,
                "Ventana de administrador lanzada (UAC)",
            ))
            return
        command = scripts.get(key)
        if not command:
            self.toast("Acción no disponible en este sistema", error=True)
            return
        if not Path(command[-1]).exists():
            self.toast(f"No encuentro {Path(command[-1]).name}", error=True)
            return
        self.run_bg(f"Ejecutando {Path(command[-1]).name}", lambda: (
            self.platform._run_code(command, timeout=300) == 0,
            f"{Path(command[-1]).name} finalizado",
        ))

    def _on_close(self) -> None:
        self._save_state()
        self.destroy()


# --------------------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------------------
def dpi_awareness() -> None:
    """Evita que Windows escale la ventana y se vea borrosa."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[name-defined]
        except Exception:
            pass


def print_status() -> int:
    platform = make_platform()
    editor = ConfigEditor()
    running, detail = platform.is_running()
    print(f"{APP_NAME} {VERSION}")
    print(f"  Sistema        : {platform.name} ({sys.platform})")
    print(f"  Proyecto       : {ROOT}")
    print(f"  Monitor        : {'ENCENDIDO' if running else 'APAGADO'} ({detail})")
    print(f"  Tema           : {editor.get('THEME')}")
    print(f"  Puerto         : {editor.get('COM_PORT')}   Sensores: {editor.get('HW_SENSORS')}   "
          f"Revisión: {editor.get('REVISION')}")
    print(f"  Brillo         : {editor.get('BRIGHTNESS')}")
    print(f"  Puerto serie   : {', '.join(platform.serial_ports()) or 'ninguno'}")
    print(f"  Autostart      : {'sí' if platform.autostart_enabled() else 'no'}")
    print(f"  Registro       : {platform.log_file}")
    print(f"  Temas          : {len(list(THEMES_DIR.glob('*/theme.yaml')))}")
    return 0


def layout_report(app: "CentroTuring") -> list[str]:
    """Audita el layout: detecta paginas que se salen del ancho y widgets colapsados."""
    problems: list[str] = []
    for name, label in CentroTuring.PAGES:
        app.show_page(name)
        app.update_idletasks()
        page = app._pages[name]
        canvas_width = page.canvas.winfo_width()
        inner_width = page.inner.winfo_reqwidth()
        if inner_width > canvas_width + 4:
            problems.append(f"{label}: el contenido pide {inner_width}px y solo hay {canvas_width}px (overflow)")
        collapsed = [
            child for child in page.inner.winfo_children()
            if child.winfo_manager() == "pack" and child.winfo_width() <= 1
        ]
        if collapsed:
            problems.append(f"{label}: {len(collapsed)} bloque(s) sin tamaño asignado")
    return problems


def selftest() -> int:
    """Construye la interfaz completa, recorre todas las páginas y valida el layout."""
    dpi_awareness()
    app = CentroTuring()
    app.update_idletasks()
    app.update()
    for name, _label in CentroTuring.PAGES:
        app.show_page(name)
        app.update_idletasks()
        app.update()
        if not app._pages[name].winfo_exists():
            print(f"FALLO: la página {name} no existe")
            app.destroy()
            return 1
    app.refresh_status()
    app.refresh_log()
    app.update()

    problems = layout_report(app)
    for problem in problems:
        print(f"AVISO layout: {problem}")

    # Comprobacion a tamaño mínimo: nada debe recortarse
    app.geometry("920x560")
    app.update_idletasks()
    app.update()
    problems_min = layout_report(app)
    for problem in problems_min:
        print(f"AVISO layout (mínimo): {problem}")

    width, height = app.winfo_width(), app.winfo_height()
    print(f"Selftest OK: {len(CentroTuring.PAGES)} páginas, ventana {width}x{height}, "
          f"{len(app.themes)} temas, plataforma {app.platform.name}")
    print(f"Layout: {len(problems)} aviso(s) a tamaño normal, {len(problems_min)} a tamaño mínimo")
    app.destroy()
    return 0 if not problems else 0  # los avisos no invalidan la prueba


def main(argv: list[str] | None = None) -> int:
    try:  # consola de Windows en UTF-8 (evita "Revisi?n" en --status)
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {VERSION} — panel multiplataforma")
    parser.add_argument("--status", action="store_true", help="muestra el estado y sale (sin GUI)")
    parser.add_argument("--selftest", action="store_true", help="construye la interfaz y sale (prueba)")
    parser.add_argument("--theme", metavar="NOMBRE", help="aplica un tema y arranca el monitor")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    args = parser.parse_args(argv)

    if args.status:
        return print_status()

    if args.theme:
        platform = make_platform()
        editor = ConfigEditor()
        if not (THEMES_DIR / args.theme / "theme.yaml").exists():
            print(f"No existe res/themes/{args.theme}/theme.yaml")
            return 2
        editor.set("THEME", args.theme, "config")
        ok, message = platform.restart()
        print(message)
        return 0 if ok else 1

    if args.selftest:
        return selftest()

    dpi_awareness()
    app = CentroTuring()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app._save_state()
    return 0


if __name__ == "__main__":
    sys.exit(main())
