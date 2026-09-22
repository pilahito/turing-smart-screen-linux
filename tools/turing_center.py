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
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------------------
APP_NAME = "Centro Turing"
VERSION = "3.0.0"
REPO_URL = "https://github.com/pilahito/turing-smart-screen-linux"
UPSTREAM_URL = "https://github.com/mathoudebine/turing-smart-screen-python"


def _resolve_root() -> Path:
    """Carpeta del proyecto, tambien cuando la app va empaquetada (.exe /.deb).

    Empaquetada con PyInstaller, `__file__` apunta a la carpeta temporal de
    extraccion, asi que hay que buscar el proyecto junto al ejecutable.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [
            exe_dir,
            exe_dir.parent,
            Path("/opt/centro-turing"),
            Path("/usr/share/centro-turing"),
            Path("E:/turing-smart-screen-python"),
            Path.home() / "turing-smart-screen-python",
        ]
        for candidate in candidates:
            if (candidate / "main.py").exists():
                return candidate
        return exe_dir
    return Path(__file__).resolve().parents[1]


ROOT = _resolve_root()
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
        self.ensure_exists()

    def ensure_exists(self) -> bool:
        """Crea config.yaml desde config.example.yaml si no existe (paquete nuevo)."""
        if self.path.exists():
            return False
        ejemplo = self.path.with_name("config.example.yaml")
        if not ejemplo.exists():
            ejemplo = self.path.parent / "res" / "config.example.yaml"
        if not ejemplo.exists():
            return False
        try:
            shutil.copy2(ejemplo, self.path)
            log_line(f"config.yaml creado a partir de {ejemplo.name}")
            return True
        except OSError:
            return False

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

    def is_our_monitor(self, pid: int) -> bool:
        """Comprueba que un PID es de verdad nuestro monitor antes de matarlo.

        Windows reutiliza los PID: si el monitor murio y su numero se reasigno a
        otro programa, matarlo por PID cerraria un proceso ajeno. Por eso se mira
        el nombre del ejecutable y la linea de comandos.
        """
        if pid <= 0:
            return False
        try:
            import psutil  # type: ignore

            proc = psutil.Process(pid)
            cmdline = " ".join(proc.cmdline() or []).replace("\\", "/")
            name = (proc.name() or "").lower()
        except Exception:
            return False
        if "python" not in name:
            return False
        if "main.py" not in cmdline:
            return False
        return str(ROOT).replace("\\", "/") in cmdline

    def stop(self) -> tuple[bool, str]:
        messages = []
        blocked = False
        if IS_LINUX and self._systemd_available("turing-smart-screen.service"):
            if self._run_code(["systemctl", "--user", "stop", "turing-smart-screen.service"]) == 0:
                messages.append("systemd detenido")
        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = 0
        if pid > 0:
            if self.is_our_monitor(pid):
                if self._kill(pid):
                    messages.append(f"PID {pid} detenido")
                else:
                    blocked = True
            else:
                messages.append(f"PID {pid} ignorado (ya no es el monitor)")
        for found in filter(None, [self._find_monitor_process()]):
            if self._kill(found):
                messages.append(f"PID {found} detenido")
            else:
                blocked = True
        if blocked:
            return False, ("El monitor se esta ejecutando como administrador y no se puede "
                           "cerrar desde este panel. Cierralo desde el Administrador de tareas "
                           "(o abre el panel como administrador) y vuelve a intentarlo.")
        if IS_WINDOWS:
            self._run(["taskkill", "/IM", "UsbPCMonitor.exe", "/F"])
        try:
            self.pid_file.unlink()
        except OSError:
            pass
        return True, ("Monitor detenido: " + ", ".join(messages)) if messages else "No habia monitor activo"

    def restart(self) -> tuple[bool, str]:
        ok, message = self.stop()
        if not ok:
            return False, message  # no se puede reiniciar lo que no se puede cerrar
        time.sleep(0.6)
        return self.start()

    def _kill(self, pid: int) -> bool:
        """Mata el proceso. Devuelve False si no se pudo (p. ej. corre como admin)."""
        try:
            if IS_WINDOWS:
                self._run(["taskkill", "/PID", str(pid), "/F"])
            else:
                os.kill(pid, 15)
                time.sleep(0.3)
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass
        except Exception:
            return False
        time.sleep(0.4)
        return not self._pid_alive(pid)

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
        # En Linux se prefiere la unidad systemd del proyecto (la que usan los
        # scripts del repo). Escribir ademas un .desktop provocaria un doble
        # arranque del monitor, asi que solo se usa como respaldo.
        if IS_LINUX and self._systemd_available("turing-smart-screen.service"):
            action = "enable" if enabled else "disable"
            code = self._run_code(["systemctl", "--user", action, "turing-smart-screen.service"])
            if code == 0:
                return True, ("Arranque automatico activado (systemd)"
                              if enabled else "Arranque automatico desactivado (systemd)")
            return False, "systemctl no pudo cambiar el arranque automatico"

        path = self.autostart_path
        if not enabled:
            removed = False
            for candidate in (path, Path.home() / ".config/autostart/turing-smart-screen.desktop"):
                if candidate.exists():
                    candidate.unlink()
                    removed = True
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
    # CREATE_NO_WINDOW: el panel va sin consola, asi que sin esta marca cada
    # taskkill/tasklist/git abriria una ventana negra durante un instante.
    _NO_WINDOW = 0x08000000 if IS_WINDOWS else 0

    @classmethod
    def _run(cls, args: list[str], timeout: int = 20) -> str:
        try:
            done = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                  errors="replace", creationflags=cls._NO_WINDOW)
            return (done.stdout or "") + (done.stderr or "")
        except Exception:
            return ""

    @classmethod
    def _run_code(cls, args: list[str], timeout: int = 30) -> int:
        try:
            return subprocess.run(args, capture_output=True, timeout=timeout,
                                  creationflags=cls._NO_WINDOW).returncode
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


def load_ui():
    """Importa la interfaz grafica (turing_ui2026) solo cuando hace falta."""
    try:
        import turing_ui2026
    except ImportError as error:
        print(f"No se pudo cargar la interfaz: {error}")
        print("Instala las dependencias: pip install -r requirements.txt")
        return None
    return turing_ui2026


def render_mockups(directory) -> int:
    """Genera las imagenes de previsualizacion de todas las paginas (sin abrir ventana)."""
    ui = load_ui()
    if ui is None:
        return 4
    ui.render_mockups(Path(directory))
    return 0


def selftest() -> int:
    """Construye la interfaz completa, recorre las paginas y valida el layout."""
    ui = load_ui()
    if ui is None:
        return 4
    return ui.selftest()


def main(argv: list[str] | None = None) -> int:
    try:  # consola de Windows en UTF-8 (evita "Revisi?n" en --status)
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except Exception:
        pass
    parser = argparse.ArgumentParser(description=f"{APP_NAME} {VERSION} — panel multiplataforma")
    parser.add_argument("--status", action="store_true", help="muestra el estado y sale (sin GUI)")
    parser.add_argument("--selftest", action="store_true", help="construye la interfaz y sale (prueba)")
    parser.add_argument("--theme", metavar="NOMBRE", help="aplica un tema y arranca el monitor")
    parser.add_argument("--mockup", metavar="CARPETA", nargs="?", const="tmp/mockups",
                        help="genera imagenes de previsualizacion y sale")
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

    if args.mockup:
        target = Path(args.mockup)
        target = target if target.is_absolute() else ROOT / target
        return render_mockups(target)

    if args.selftest:
        return selftest()

    ui = load_ui()
    if ui is None:
        return 4
    dpi_awareness()
    ui.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
