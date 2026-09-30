# -*- coding: utf-8 -*-
"""Centro Turing: apaga la pantalla cuando Windows se apaga, reinicia o cierra sesion.

Crea una ventana oculta propia (en su hilo, con su bucle de mensajes bloqueante) que
recibe WM_QUERYENDSESSION / WM_ENDSESSION. Al recibirlos pone el brillo a 0, envia
SCREEN_OFF y apaga el LED trasero, espera a que la cola serie se vacie y, al
confirmarse el fin de sesion, termina el proceso. Tambien atiende CTRL_LOGOFF /
CTRL_SHUTDOWN cuando main.py corre con consola (python.exe).
"""
import os
import threading
import time

from library.log import logger

WND_CLASS = "CentroTuringApagado"
_hecho = threading.Event()
_lock = threading.Lock()
_hwnd = 0
_display = None
_scheduler = None


def _flush_logs():
    import logging
    for h in list(logger.handlers) + list(logging.getLogger().handlers):
        try:
            h.flush()
            stream = getattr(h, "stream", None)
            if stream is not None and hasattr(stream, "fileno"):
                os.fsync(stream.fileno())  # a disco YA: Windows puede cortar en cualquier momento
        except Exception:
            pass


def _esperar_cola(timeout: float) -> bool:
    """Mete un marcador al final de la cola serie y espera a que el hilo de la cola lo
    ejecute: asi se sabe que TODO lo anterior (brillo 0, SCREEN_OFF) ya se ha escrito."""
    from library import config
    listo = threading.Event()
    try:
        with _display.lcd.update_queue_mutex:
            config.update_queue.put((listo.set, []))
    except Exception:
        return False
    return listo.wait(timeout)


def _block_reason(crear: bool) -> None:
    """Pide a Windows que espere mientras se apaga la pantalla (ShutdownBlockReason)."""
    try:
        import ctypes
        if _hwnd:
            if crear:
                ctypes.windll.user32.ShutdownBlockReasonCreate(_hwnd, "Apagando la pantalla Turing")
            else:
                ctypes.windll.user32.ShutdownBlockReasonDestroy(_hwnd)
    except Exception:
        pass


def apagar_pantalla(motivo: str, timeout: float = 4.0) -> None:
    """Brillo 0 + pantalla apagada + LED apagado. Solo se ejecuta una vez."""
    if _display is None:
        return
    with _lock:
        if _hecho.is_set():
            return
        _hecho.set()
    _block_reason(True)
    logger.info("Windows: %s -> se apaga la pantalla (brillo 0 + SCREEN_OFF)", motivo)
    _flush_logs()
    try:
        lcd = _display.lcd
        lcd.SetBrightness(0)
        lcd.ScreenOff()
        try:
            lcd.SetBackplateLedColor(led_color=(0, 0, 0))
        except Exception:
            pass
        escrito = _esperar_cola(timeout)
        # Ya no hace falta dibujar mas: se paran las tareas periodicas
        _scheduler.STOPPING = True
        if not escrito:
            # El hilo de la cola no responde: se envia directo por el puerto (rev. A)
            try:
                from library.lcd.lcd_comm_rev_a import Command, LcdCommRevA
                if isinstance(lcd, LcdCommRevA):
                    lcd.SendCommand(Command.SET_BRIGHTNESS, 255, 0, 0, 0, bypass_queue=True)
                    lcd.SendCommand(Command.SCREEN_OFF, 0, 0, 0, 0, bypass_queue=True)
                    lcd.lcd_serial.flush()
            except Exception as e:
                logger.error("Apagado directo fallido: %s", e)
        else:
            try:
                _display.lcd.lcd_serial.flush()
            except Exception:
                pass
        logger.info("Pantalla apagada (comandos escritos por la cola: %s)", escrito)
    except Exception as e:
        logger.error("No se pudo apagar la pantalla al cerrar Windows: %s", e)
    _flush_logs()
    _block_reason(False)


def _wndproc(hwnd, msg, wparam, lparam):
    import win32con
    import win32gui
    if msg == win32con.WM_QUERYENDSESSION:
        apagar_pantalla("fin de sesion / apagado (WM_QUERYENDSESSION lParam=0x%X)" % (lparam & 0xFFFFFFFF))
        return True  # no se bloquea el apagado
    if msg == win32con.WM_ENDSESSION:
        if wparam:
            apagar_pantalla("WM_ENDSESSION")
            logger.info("Windows cierra la sesion: el monitor termina")
            _flush_logs()
            os._exit(0)
        else:
            logger.info("Apagado cancelado: se vuelve a encender la pantalla")
            _reencender()
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _reencender():
    try:
        if _hecho.is_set() and _scheduler is not None and _display is not None:
            _hecho.clear()
            from library import config
            _display.lcd.ScreenOn()
            _display.lcd.SetBrightness(int(config.CONFIG_DATA["display"].get("BRIGHTNESS", 25)))
            _display.display_static_images()
            _display.display_static_text()
            logger.warning("Las estadisticas se reanudan al reiniciar el monitor")
    except Exception as e:
        logger.error("No se pudo reencender la pantalla: %s", e)


def _hilo_ventana():
    try:
        import win32api
        import win32gui
        hinst = win32api.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = WND_CLASS
        wc.lpfnWndProc = _wndproc
        atom = win32gui.RegisterClass(wc)
        global _hwnd
        # Ventana de nivel superior oculta (NO message-only: esas no reciben WM_QUERYENDSESSION)
        _hwnd = win32gui.CreateWindowEx(0, atom, "Centro Turing - apagado de pantalla", 0, 0, 0, 0, 0,
                                        0, 0, hinst, None)
        logger.debug("Aviso de apagado de Windows activo (ventana %s)", _hwnd)
        win32gui.PumpMessages()
    except Exception as e:
        logger.error("No se pudo crear la ventana de aviso de apagado: %s", e)


def instalar(display, scheduler) -> None:
    global _display, _scheduler
    if os.name != "nt":
        return
    _display, _scheduler = display, scheduler
    try:
        import ctypes
        # Nivel alto = Windows avisa a este proceso de los primeros al apagar
        ctypes.windll.kernel32.SetProcessShutdownParameters(0x3FF, 0)
    except Exception:
        pass
    threading.Thread(target=_hilo_ventana, name="Apagado_Windows", daemon=True).start()
    try:
        import win32api
        import win32con

        def _ctrl(evento):
            if evento in (win32con.CTRL_LOGOFF_EVENT, win32con.CTRL_SHUTDOWN_EVENT):
                apagar_pantalla("evento de consola %s" % evento)
                return True
            return False
        win32api.SetConsoleCtrlHandler(_ctrl, True)
    except Exception:
        pass
