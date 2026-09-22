#!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
# Copyright (C) 2022 Rollbacke
# Copyright (C) 2022 Ebag333
# Copyright (C) 2022 w1ld3r
# Copyright (C) 2022 Charles Ferguson (gerph)
# Copyright (C) 2022 Russ Nelson (RussNelson)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# This file is the system monitor main program to display HW sensors on your screen using themes (see README)

from library.pythoncheck import check_python_version
check_python_version()

# Windows: si el monitor va sin consola (lo lanza el panel en segundo plano), cada
# subproceso de sensores (nvidia-smi via GPUtil, ffmpeg...) provoca que Windows le
# cree una consola nueva: una ventana negra en cada refresco de sensores.
from library.no_console_windows import apply as _no_console_windows
_no_console_windows()

import os
import sys

try:
    import atexit
    import locale
    import platform
    import signal
    import subprocess
    import time
    from pathlib import Path
    from PIL import Image

    if platform.system() == 'Windows':
        import win32api
        import win32con
        import win32gui

    from library.log import logger
    import library.scheduler as scheduler
    from library.display import display

except Exception as e:
    print("""Import error: %s
Please follow start guide to install required packages: https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-how-to-start
Or the troubleshooting page: https://github.com/mathoudebine/turing-smart-screen-python/wiki/Troubleshooting#all-os-tkinter-dependency-not-installed""" % str(
        e))
    try:
        sys.exit(0)
    except:
        os._exit(0)

try:
    import pystray
except:
    # If pystray cannot be loaded do not stop the program, just ignore it. The tray icon will not be displayed.
    pass

MAIN_DIRECTORY = Path(__file__).resolve().parent

if __name__ == "__main__":

    # Apply system locale to this program
    locale.setlocale(locale.LC_ALL, '')

    logger.debug("Using Python %s" % sys.version)


    def wait_for_empty_queue(timeout: int = 5):
        # Waiting for all pending request to be sent to display
        logger.info("Waiting for all pending request to be sent to display (%ds max)..." % timeout)

        wait_time = 0
        while not scheduler.is_queue_empty() and wait_time < timeout:
            time.sleep(0.1)
            wait_time = wait_time + 0.1

        logger.debug("(Waited %.1fs)" % wait_time)

    def clean_stop(tray_icon=None):
        # Turn screen and LEDs off before stopping
        display.turn_off()

        # Do not stop the program now in case data transmission was in progress
        # Instead, ask the scheduler to empty the action queue before stopping
        scheduler.STOPPING = True

        # Waiting for all pending request to be sent to display
        wait_for_empty_queue(5)

        # Remove tray icon just before exit
        if tray_icon:
            tray_icon.visible = False

        # We force the exit to avoid waiting for other scheduled tasks: they may have a long delay!
        try:
            sys.exit(0)
        except:
            os._exit(0)

    def on_signal_caught(signum, frame=None):
        logger.info("Caught signal %d, exiting" % signum)
        clean_stop()

    def _tray_ui_lang():
        """Prefer tools/pantalla-turing-ui.json, else WEATHER_LANGUAGE / es."""
        try:
            import json
            ui = MAIN_DIRECTORY / "tools" / "pantalla-turing-ui.json"
            if ui.is_file():
                data = json.loads(ui.read_text(encoding="utf-8"))
                lang = str(data.get("lang", "es")).lower()
                if lang in ("es", "en"):
                    return lang
        except Exception:
            pass
        try:
            from library.config import CONFIG_DATA
            wl = str(CONFIG_DATA.get("config", {}).get("WEATHER_LANGUAGE", "es")).lower()
            if wl.startswith("en"):
                return "en"
        except Exception:
            pass
        return "es"

    def _tray_labels():
        if _tray_ui_lang() == "en":
            return {
                "title": "Turing Screen",
                "open": "Open",
                "configure": "Configure",
                "exit": "Exit",
            }
        return {
            "title": "Pantalla Turing",
            "open": "Abrir",
            "configure": "Configurar",
            "exit": "Salir",
        }

    def on_open_tray(tray_icon, item):
        """Open PantallaTuring launcher without stopping the monitor."""
        logger.info("Open launcher from tray icon")
        try:
            launcher = MAIN_DIRECTORY / "PantallaTuring.exe"
            if platform.system() == "Windows" and launcher.is_file():
                subprocess.Popen([str(launcher)], cwd=str(MAIN_DIRECTORY))
                return
            # Fallback: classic configure UI without stopping
            configure_file = next(MAIN_DIRECTORY.glob("configure.py"))
            subprocess.Popen([sys.executable, str(configure_file)])
        except Exception as e:
            logger.error("Could not open launcher: %s", e)

    def on_configure_tray(tray_icon, item):
        logger.info("Configure from tray icon")

        try:
            # Classic configure UI (stops monitor so COM port is free)
            configure_file = next(MAIN_DIRECTORY.glob("configure.py"))
            subprocess.Popen([sys.executable, str(configure_file)])
        except:
            configure_file = next(MAIN_DIRECTORY.glob("configure*"))
            if platform.system() == "Windows":
                subprocess.Popen([str(configure_file)], shell=True)
            else:
                subprocess.Popen([str(configure_file)])

        clean_stop(tray_icon)

    def on_exit_tray(tray_icon, item):
        logger.info("Exit from tray icon")
        clean_stop(tray_icon)


    def on_clean_exit(*args):
        logger.info("Program will now exit")
        clean_stop()


    if platform.system() == "Windows":
        def on_win32_ctrl_event(event):
            """Handle Windows console control events (like Ctrl-C)."""
            if event in (win32con.CTRL_C_EVENT, win32con.CTRL_BREAK_EVENT, win32con.CTRL_CLOSE_EVENT):
                logger.debug("Caught Windows control event %s, exiting" % event)
                clean_stop()
            return 0


        def on_win32_wm_event(hWnd, msg, wParam, lParam):
            """Handle Windows window message events (like ENDSESSION, CLOSE, DESTROY)."""
            logger.debug("Caught Windows window message event %s" % msg)
            if msg == win32con.WM_POWERBROADCAST:
                # WM_POWERBROADCAST is used to detect computer going to/resuming from sleep
                if wParam == win32con.PBT_APMSUSPEND:
                    logger.info("Computer is going to sleep, display will turn off")
                    display.turn_off()
                elif wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                    logger.info("Computer is resuming from sleep, display will turn on")
                    display.turn_on()
                    # Some models have troubles displaying back the previous bitmap after being turned off/on
                    display.display_static_images()
                    display.display_static_text()
            else:
                # For any other events, the program will stop
                logger.info("Program will now exit")
                clean_stop()

    # Create a tray icon for the program (ES/EN labels + Abrir)
    try:
        _tl = _tray_labels()
        # Icono de bandeja: el nuevo de Centro Turing; si no estuviera, el antiguo
        icono = MAIN_DIRECTORY / "res/icons/centro-turing/64.png"
        if not icono.exists():
            icono = MAIN_DIRECTORY / "res/icons/monitor-icon-17865/64.png"
        tray_icon = pystray.Icon(
            name='Turing System Monitor',
            title=_tl["title"],
            icon=Image.open(icono),
            menu=pystray.Menu(
                pystray.MenuItem(
                    text=_tl["open"],
                    action=on_open_tray,
                    default=True),
                pystray.MenuItem(
                    text=_tl["configure"],
                    action=on_configure_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    text=_tl["exit"],
                    action=on_exit_tray)
            )
        )

        # For platforms != macOS, display the tray icon now with non-blocking function
        if platform.system() != "Darwin":
            tray_icon.run_detached()
            logger.info("Tray icon has been displayed")
    except:
        tray_icon = None
        logger.warning("Tray icon is not supported on your platform")

    # Set the different stopping event handlers, to send a complete frame to the LCD before exit
    atexit.register(on_clean_exit)
    signal.signal(signal.SIGINT, on_signal_caught)
    signal.signal(signal.SIGTERM, on_signal_caught)
    is_posix = os.name == 'posix'
    if is_posix:
        signal.signal(signal.SIGQUIT, on_signal_caught)
    if platform.system() == "Windows":
        win32api.SetConsoleCtrlHandler(on_win32_ctrl_event, True)

    # Initialize the display
    logger.info("Initialize display")
    display.initialize_display()

    # Start serial queue handler
    scheduler.QueueHandler()

    # Create all static images
    display.display_static_images()

    # Create all static texts
    display.display_static_text()

    # Wait for static images/text to be displayed before starting monitoring (to avoid filling the queue while waiting)
    wait_for_empty_queue(10)

    # Start sensor scheduled reading. Avoid starting them all at the same time to optimize load
    logger.info("Starting system monitoring")
    import library.stats as stats

    scheduler.CPUPercentage(); time.sleep(0.25)
    scheduler.CPUFrequency(); time.sleep(0.25)
    scheduler.CPULoad(); time.sleep(0.25)
    scheduler.CPUTemperature(); time.sleep(0.25)
    scheduler.CPUFanSpeed(); time.sleep(0.25)
    if stats.Gpu.is_available():
        scheduler.GpuStats(); time.sleep(0.25)
    scheduler.MemoryStats(); time.sleep(0.25)
    scheduler.DiskStats(); time.sleep(0.25)
    scheduler.NetStats(); time.sleep(0.25)
    scheduler.DateStats(); time.sleep(0.25)
    scheduler.SystemUptimeStats(); time.sleep(0.25)
    scheduler.CustomStats(); time.sleep(0.25)
    scheduler.WeatherStats(); time.sleep(0.25)
    scheduler.PingStats(); time.sleep(0.25)

    # OS-specific tasks
    if tray_icon and platform.system() == "Darwin":  # macOS-specific
        from AppKit import NSBundle, NSApp, NSApplicationActivationPolicyProhibited

        # Hide Python Launcher icon from macOS dock
        info = NSBundle.mainBundle().infoDictionary()
        info["LSUIElement"] = "1"
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)

        # For macOS: display the tray icon now with blocking function
        tray_icon.run()

    elif platform.system() == "Windows":  # Windows-specific
        # Create a hidden window just to be able to receive window message events (for shutdown/logoff clean stop)
        hinst = win32api.GetModuleHandle(None)
        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = hinst
        wndclass.lpszClassName = "turingEventWndClass"
        messageMap = {win32con.WM_QUERYENDSESSION: on_win32_wm_event,
                      win32con.WM_ENDSESSION: on_win32_wm_event,
                      win32con.WM_QUIT: on_win32_wm_event,
                      win32con.WM_DESTROY: on_win32_wm_event,
                      win32con.WM_CLOSE: on_win32_wm_event,
                      win32con.WM_POWERBROADCAST: on_win32_wm_event}

        wndclass.lpfnWndProc = messageMap

        try:
            myWindowClass = win32gui.RegisterClass(wndclass)
            hwnd = win32gui.CreateWindowEx(win32con.WS_EX_LEFT,
                                           myWindowClass,
                                           "turingEventWnd",
                                           0,
                                           0,
                                           0,
                                           win32con.CW_USEDEFAULT,
                                           win32con.CW_USEDEFAULT,
                                           0,
                                           0,
                                           hinst,
                                           None)
            while True:
                # Receive and dispatch window messages
                win32gui.PumpWaitingMessages()
                time.sleep(0.5)

        except Exception as e:
            logger.error("Exception while creating event window: %s" % str(e))
