# -*- coding: utf-8 -*-
"""Arranque del monitor Turing: Windows, Ubuntu y Arch."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "tmp" / "monitor.pid"
LOG = ROOT / "lanzador.log"
CFG = ROOT / "config.yaml"
WIN = os.name == "nt"


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)
    print(msg)


def popup(msg: str, detalle: str = "") -> None:
    log("ERROR " + msg + (("\n" + detalle) if detalle else ""))
    if WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, " ".join(msg.split())[:200], "Pantalla Turing", 0x10)
            return
        except Exception:
            pass
    print(msg, file=sys.stderr)


def python_exe() -> Path:
    if WIN:
        p = ROOT / "venv" / "Scripts" / "python.exe"
    else:
        p = ROOT / "venv" / "bin" / "python"
        if not p.exists():
            p = ROOT / "venv" / "bin" / "python3"
    if p.exists():
        return p
    # sistema
    import shutil
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return Path(found)
    raise RuntimeError("No hay Python. En Windows: Instalar.ps1  |  En Linux: ./iniciar.sh --install")


def is_our_monitor(pid: int) -> bool:
    """Verifica que el PID sea de verdad nuestro monitor antes de matarlo.

    Windows reutiliza los PID: si el monitor murio y su numero se reasigno a otro
    programa, matarlo por PID cerraria un proceso ajeno (por eso se mira la linea
    de comandos).
    """
    if pid <= 0:
        return False
    try:
        import psutil

        proc = psutil.Process(pid)
        cmdline = " ".join(proc.cmdline() or []).replace("\\", "/")
        if "python" not in (proc.name() or "").lower() or "main.py" not in cmdline:
            return False
        raiz = str(ROOT).replace("\\", "/").lower()
        if raiz in cmdline.lower():
            return True
        # "pythonw.exe main.py" (ruta relativa): se mira el ejecutable y la carpeta de trabajo
        exe = (proc.exe() or "").replace("\\", "/").lower()
        try:
            cwd = (proc.cwd() or "").replace("\\", "/").lower().rstrip("/")
        except Exception:
            cwd = ""
        return exe.startswith(raiz + "/") or cwd == raiz
    except Exception:
        return False


def kill_pid(pid: int) -> None:
    if not is_our_monitor(pid):
        return
    try:
        if WIN:
            # CREATE_NO_WINDOW: sin consola, taskkill abriria una ventana negra
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=8,
                           creationflags=0x08000000)
        else:
            os.kill(pid, 15)
            time.sleep(0.3)
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    except Exception:
        pass


def kill_previous() -> None:
    if WIN:
        subprocess.run(["taskkill", "/IM", "UsbPCMonitor.exe", "/F"], capture_output=True, timeout=8,
                       creationflags=0x08000000)
    if PID_FILE.exists():
        try:
            kill_pid(int(PID_FILE.read_text(encoding="utf-8").strip()))
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except Exception:
            pass
    try:
        import psutil
        me = os.getpid()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            if p.info["pid"] == me:
                continue
            cmd = " ".join(p.info.get("cmdline") or [])
            if "main.py" in cmd:
                kill_pid(int(p.info["pid"]))  # kill_pid solo mata el main.py de ESTA carpeta
    except Exception as e:
        log("psutil: " + str(e))


def set_config(theme: str) -> None:
    text = CFG.read_text(encoding="utf-8")
    if theme:
        if not re.search(r"(?m)^(\s*THEME:\s*).+$", text):
            raise RuntimeError("No hay THEME en config.yaml")
        text = re.sub(r"(?m)^(\s*THEME:\s*).+$", r"\g<1>" + theme, text)
    if WIN:
        text = re.sub(r"(?m)^(\s*HW_SENSORS:\s*).+$", r"\g<1>AUTO", text)
    else:
        text = re.sub(r"(?m)^(\s*HW_SENSORS:\s*).+$", r"\g<1>PYTHON", text)
        # COM3 es Windows; en Linux auto-detecta /dev/ttyACM*
        text = re.sub(r"(?m)^(\s*COM_PORT:\s*).+$", r"\g<1>AUTO", text)
    CFG.write_text(text, encoding="utf-8")


ARRANQUE_PAUSA = 5.0     # s de pausa con --arranque (inicio de Windows)
ESPERA_MONITOR = 90.0    # s maximos esperando a que main.py empiece a dibujar


def log_desde_marca() -> str:
    lf = ROOT / "log.log"
    if not lf.exists():
        return ""
    lines = lf.read_text(encoding="utf-8", errors="replace").splitlines()
    start = 0
    for i, line in enumerate(lines):
        if "--- lanzar start ---" in line:
            start = i
    return "\n".join(lines[start:])


def ensure_tmp() -> None:
    tmp = PID_FILE.parent
    if tmp.exists() and not tmp.is_dir():
        tmp.unlink()
    tmp.mkdir(parents=True, exist_ok=True)


def main() -> int:
    os.chdir(ROOT)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    theme = args[0].strip() if args else ""
    log("lanzar os=%s theme=%r %s" % (sys.platform, theme, " ".join(flags)))
    if "--arranque" in flags:
        # Arranque de Windows: pequena pausa para que se enumeren los USB
        time.sleep(ARRANQUE_PAUSA)
    try:
        kill_previous()
        time.sleep(0.5)
        if theme:
            theme_dir = ROOT / "res" / "themes" / theme
            if not (theme_dir / "theme.yaml").exists():
                popup("No existe el tema:\n" + theme)
                return 2
            set_config(theme)
            log("THEME=" + theme)
        else:
            set_config("")
        py = python_exe()
        ensure_tmp()
        kwargs = {
            "cwd": str(ROOT),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if WIN:
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        # Mark a fresh start in log so popup does not show stale errors
        try:
            with (ROOT / "log.log").open("a", encoding="utf-8") as lf:
                lf.write(time.strftime("%d/%m/%Y %H:%M:%S") + " [INFO] --- lanzar start ---\n")
        except Exception:
            pass
        proc = subprocess.Popen([str(py), "main.py"], **kwargs)
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        # main.py espera por si solo a la pantalla (COM_WAIT_SECONDS, 60 s por defecto):
        # aqui solo se avisa si el monitor muere o si no arranca tras agotar la espera.
        limite = time.time() + ESPERA_MONITOR
        estado = "esperando"
        while time.time() < limite:
            time.sleep(1.0)
            if proc.poll() is not None:
                estado = "muerto"
                break
            if "Starting system monitoring" in log_desde_marca():
                estado = "ok"
                break
        if estado == "muerto":
            texto = log_desde_marca()
            tail = "\n".join(texto.splitlines()[-20:])
            if "no ha aparecido" in texto or "no existe en el sistema" in texto:
                corto = "Windows no detecta la pantalla Turing por USB: desenchufa y vuelve a enchufar su cable (detalles en log.log)."
            else:
                corto = "El monitor de la pantalla Turing no ha podido arrancar (detalles en log.log)."
            popup(corto, tail)
            return 3
        if estado == "esperando":
            log("aviso: el monitor sigue vivo pero aun no dibuja (pid=%s)" % proc.pid)
        log("ok pid=%s python=%s" % (proc.pid, py))
        return 0
    except Exception as e:
        popup(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
