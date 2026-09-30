# -*- coding: utf-8 -*-
"""Apaga (o enciende) la pantalla Turing 3.5" directamente por el puerto serie.

Respaldo del apagado de Windows: lo lanza la tarea programada "CentroTuring-ApagarPantalla"
(evento 1074 = se ha pedido apagar/reiniciar). Tambien sirve a mano:

    venv\\Scripts\\python.exe tools\\apagar_pantalla.py              (para el monitor y apaga)
    venv\\Scripts\\python.exe tools\\apagar_pantalla.py --encender   (enciende, brillo de config)

Solo para el main.py de ESTA carpeta (nunca otros main.py, p. ej. Soul-of-Waifu).
"""
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "log.log"

SCREEN_OFF, SCREEN_ON, SET_BRIGHTNESS = 108, 109, 110


def log(msg):
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%d/%m/%Y %H:%M:%S") + " [INFO] apagar_pantalla: " + msg + "\n")
    except Exception:
        pass
    print(msg)


def es_nuestro_monitor(p) -> bool:
    try:
        cmd = " ".join(p.cmdline() or [])
        if "python" not in (p.name() or "").lower() or "main.py" not in cmd:
            return False
        raiz = str(ROOT).lower()
        exe = (p.exe() or "").lower()
        try:
            cwd = (p.cwd() or "").lower()
        except Exception:
            cwd = ""
        return exe.startswith(raiz) or cwd.rstrip("\\/") == raiz or raiz in cmd.lower()
    except Exception:
        return False


def parar_monitor():
    import psutil
    procs = [p for p in psutil.process_iter() if es_nuestro_monitor(p)]
    for p in procs:
        log(f"se para el monitor PID {p.pid}")
        try:
            p.terminate()
        except Exception:
            pass
    psutil.wait_procs(procs, timeout=3)
    for p in procs:
        try:
            if p.is_running():
                p.kill()
        except Exception:
            pass
    if procs:
        time.sleep(0.8)


def leer_config():
    txt = (ROOT / "config.yaml").read_text(encoding="utf-8-sig", errors="replace")
    port = (re.search(r"(?m)^\s*COM_PORT:\s*['\"]?([^'\"\s#]*)", txt) or [None, "AUTO"])[1] or "AUTO"
    m = re.search(r"(?m)^\s*BRIGHTNESS:\s*['\"]?(\d+)", txt)
    return port, int(m.group(1)) if m else 25


def buscar_puerto(port):
    from serial.tools.list_ports import comports
    lista = list(comports())
    if port.upper() != "AUTO" and any(c.device.upper() == port.upper() for c in lista):
        return port
    for c in lista:
        if c.serial_number == "USB35INCHIPSV2" or (c.vid == 0x1A86 and c.pid == 0x5722):
            return c.device
    return None


def comando(cmd, x=0, y=0, ex=0, ey=0):
    b = bytearray(6)
    b[0] = x >> 2
    b[1] = ((x & 3) << 6) + (y >> 4)
    b[2] = ((y & 15) << 4) + (ex >> 6)
    b[3] = ((ex & 63) << 2) + (ey >> 8)
    b[4] = ey & 255
    b[5] = cmd
    return bytes(b)


def main():
    encender = "--encender" in sys.argv
    motivo = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--motivo=")), "manual")
    if "--no-parar" not in sys.argv:
        parar_monitor()
    port_cfg, brillo = leer_config()
    port = buscar_puerto(port_cfg)
    if not port:
        log(f"no se encuentra la pantalla (config {port_cfg}); nada que apagar")
        return 1
    import serial
    for intento in range(5):
        try:
            with serial.Serial(port, 115200, timeout=1, rtscts=True, write_timeout=2) as s:
                if encender:
                    s.write(comando(SCREEN_ON))
                    s.write(comando(SET_BRIGHTNESS, int(255 - brillo / 100 * 255)))
                else:
                    s.write(comando(SET_BRIGHTNESS, 255))  # 255 = lo mas oscuro
                    s.write(comando(SCREEN_OFF))
                s.flush()
                time.sleep(0.2)
            log(("pantalla ENCENDIDA" if encender else "pantalla APAGADA (brillo 0 + SCREEN_OFF)")
                + f" en {port} (motivo: {motivo})")
            return 0
        except Exception as e:
            log(f"intento {intento + 1}: no se puede abrir {port}: {e}")
            time.sleep(1)
    return 2


if __name__ == "__main__":
    sys.exit(main())
