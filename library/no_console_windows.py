# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Evita las ventanas de consola que abren los subprocesos en Windows.
#
# Cuando el monitor se lanza en segundo plano (pythonw.exe / DETACHED_PROCESS) no
# tiene consola propia. En ese caso, cada subproceso DE CONSOLA que arranca
# (nvidia-smi desde GPUtil, ffmpeg, ...) hace que Windows le cree una consola
# nueva: aparece una ventana negra en cada refresco de sensores.
#
# Este modulo pone CREATE_NO_WINDOW como valor por defecto en subprocess.Popen,
# y SOLO cuando el proceso no tiene consola. Si el monitor se ejecuta desde una
# terminal no cambia nada: los hijos heredan esa consola, como siempre.
#
# Comprobado con tmp/test_padre.py + tmp/test_hijo.py:
#   sin parche -> el hijo de consola recibe ventana nueva
#   con parche -> el hijo no recibe consola

import ctypes
import os
import subprocess

CREATE_NO_WINDOW = 0x08000000


def _has_console() -> bool:
    try:
        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except Exception:
        return True  # ante la duda, no se toca nada


def apply() -> bool:
    """Activa el parche. Devuelve True si se aplico."""
    if os.name != "nt":
        return False
    if _has_console():
        return False
    original = subprocess.Popen.__init__
    if getattr(original, "_no_console_patched", False):
        return True

    def patched(self, *args, **kwargs):
        if not kwargs.get("creationflags") and kwargs.get("startupinfo") is None:
            kwargs["creationflags"] = CREATE_NO_WINDOW
        return original(self, *args, **kwargs)

    patched._no_console_patched = True  # type: ignore[attr-defined]
    subprocess.Popen.__init__ = patched  # type: ignore[method-assign]
    return True
