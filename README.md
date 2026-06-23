<div align="center">

# 🐧 Turing Smart Screen — Linux Edition

**Versión mejorada para Linux / Ubuntu** · por [**pilahito**](https://github.com/pilahito)

[![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](README-LINUX-UBUNTU.md)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%2B-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)](README-LINUX-UBUNTU.md)
[![Release](https://img.shields.io/github/v/release/pilahito/turing-smart-screen-linux?label=release&style=for-the-badge)](https://github.com/pilahito/turing-smart-screen-linux/releases)
[![Licence](https://img.shields.io/github/license/pilahito/turing-smart-screen-linux?style=for-the-badge)](LICENSE)

Monitor de sistema en **mini pantalla USB Turing** (3.5", 5", 8.8"…) con instalación en un comando,  
**41+ temas**, menú en el Escritorio, autostart, FPS, ventiladores CPU/GPU y galería visual.

[📖 Guía Linux completa](README-LINUX-UBUNTU.md) · [⬇️ Releases](https://github.com/pilahito/turing-smart-screen-linux/releases) · [🔧 Changelog Linux](CHANGELOG-LINUX.md)

</div>

---

## ¿Por qué esta versión?

Fork mantenido de [mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPL-3.0) con mejoras pensadas para **uso real en Linux**:

| Mejora | Descripción |
|--------|-------------|
| **Instalador Ubuntu** | `./scripts/install-ubuntu.sh` — venv, dialout, tema, autostart |
| **Menú interactivo** | Escritorio + `turing-menu.sh` — temas, galería, reinicio, log |
| **Autostart** | systemd user + `.desktop` — Cinnamon, GNOME, MATE, XFCE |
| **41+ temas 3.5"** | Incluidos + comunidad (RedLineGraphs, CpuGpuStatsMono…) |
| **Tema estable** | **Cyberdeck** por defecto (landscape 3.5" probado) · **Pilahito** = variante cyan |
| **Galería HTML** | Previews en el navegador antes de elegir tema |
| **Pantalla virtual** | Ver la mini pantalla en tu monitor (modo SIMU + espejo) |
| **FPS en Linux** | `turing-fps.service` — Hz del monitor o MangoHud |
| **Ventiladores** | Gigabyte B760 (`it87`) + NVIDIA vía `nvidia-smi` |
| **USB QinHeng** | Detección `/dev/ttyACM*` (`1a86:5722`) |

## Instalación rápida

```bash
git clone https://github.com/pilahito/turing-smart-screen-linux.git
cd turing-smart-screen-linux
./scripts/install-ubuntu.sh
```

Menú en el Escritorio: `./scripts/install-desktop-menu.sh`

## Capturas de temas

<img src="res/themes/Cyberdeck/preview.png" height="140" alt="Cyberdeck" />
<img src="res/themes/LandscapeModernDevice35/preview.png" height="140" alt="LandscapeModernDevice35" />
<img src="res/themes/bash-dark-green-gpu/preview.png" height="140" alt="bash-dark-green-gpu" />
<img src="res/themes/Terminal/preview.png" height="140" alt="Terminal" />

[Ver todos los temas →](res/themes/themes.md)

---

> [!NOTE]
> **Proyecto base:** este repo incluye el código completo de *turing-smart-screen-python* más scripts y documentación Linux.  
> No está afiliado a Turing / XuanFang / Kipye. Ver [avisos legales](#avisos) abajo.

<details>
<summary><strong>📚 Documentación original del proyecto upstream (Windows, macOS, API, wiki…)</strong></summary>

<br/>

# ![Icon](res/icons/monitor-icon-17865/24.png) turing-smart-screen-python (upstream)

> [!WARNING]
> 
> This project is **not affiliated, associated, authorized, endorsed by, or in any way officially connected with Turing / XuanFang / Kipye brands**, or any of theirs subsidiaries, affiliates, manufacturers or sellers of their products. All product and company names are the registered trademarks of their original owners.
> 
> This project is an open-source alternative software, NOT the original software provided for the smart screens. **Please do not open issues for USBMonitor.exe/ExtendScreen.exe or for the smart screens hardware here**.
> * for Turing Smart Screen, use the official forum here: http://discuz.turzx.com/
> * for other smart screens, contact your reseller

![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black) ![Windows](https://img.shields.io/badge/Windows%2010%2F11-0078D6?style=for-the-badge&logoColor=white&logo=data:image/svg%2bxml;base64,PHN2ZyByb2xlPSJpbWciIHZpZXdCb3g9IjAgMCAyNCAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48dGl0bGU+V2luZG93czwvdGl0bGU+PHBhdGggZmlsbCA9ICIjRkZGRkZGIiBkPSJNMCwwSDExLjM3N1YxMS4zNzJIMFpNMTIuNjIzLDBIMjRWMTEuMzcySDEyLjYyM1pNMCwxMi42MjNIMTEuMzc3VjI0SDBabTEyLjYyMywwSDI0VjI0SDEyLjYyMyIvPjwvc3ZnPg==) [![macOS](https://img.shields.io/badge/mac%20os%20(⚠️major%20bug)-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/mathoudebine/turing-smart-screen-python/issues/7) ![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-A22846?style=for-the-badge&logo=Raspberry%20Pi&logoColor=white) ![Python](https://img.shields.io/badge/Python-3.X-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54) [![Licence](https://img.shields.io/github/license/mathoudebine/turing-smart-screen-python?style=for-the-badge)](./LICENSE)
  
A Python system monitor program and an abstraction library for **small IPS USB-C displays.**    

Supported operating systems : macOS, Windows, Linux (incl. Raspberry Pi), basically all OS that support Python 3.9+  

### ✅ Supported smart screens models:

| ✅ Turing Smart Screen / TURZX                                                                                                                                                                                                                                                                                                                                                                  |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <img src="res/docs/turing.webp" width="30%" height="30%"/> <img src="res/docs/turing46inch.png" width="30%" height="30%"/> <img src="res/docs/turing5inch.png" width="30%" height="30%"/> <br/> <img src="res/docs/turing2inch.webp" width="30%" height="30%"/> <img src="res/docs/turing8inch.png" width="30%" height="30%"/> <img src="res/docs/turing8inch.webp" width="30%" height="30%"/> |
| All available sizes and hardware revisions supported: **2.1" / 2.8" / 3.5" / 4.6" / 5" / 5.2" / 8.0" / 8.8" / 9.2" / 12.3"** <br/>UART and USB protocols supported. Note: no video or storage support for now                                                                                                                                                                                  |

| ✅ XuanFang 3.5"                                   | ✅ [UsbPCMonitor 3.5" / 5"](https://aliexpress.com/item/1005003931363455.html)                       | ✅ Kipye Qiye Smart Display 3.5"                                                  |
|---------------------------------------------------|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| <img src="res/docs/xuanfang.webp"/>               | <img src="res/docs/UsbPCMonitor_5inch.webp" width="60%" height="60%"/>                              | <img src="res/docs/kipye-qiye-35.webp" width="60%" height="60%"/>                |
| revision B & flagship (with backplate & RGB LEDs) | Unknown manufacturer, visually similar to Turing 3.5" / 5". Original software is `UsbPCMonitor.exe` | Front panel has an engraved inscription "奇叶智显" Qiye Zhixian (Qiye Smart Display) |

### [> What is my smart screen model?](https://github.com/mathoudebine/turing-smart-screen-python/wiki/Hardware-revisions)  

**Please note all listed smart screens are different products** designed and produced by different companies, despite having a similar appearance. Their communication protocol is also different.  
This project offers an abstraction layer to manage all of these products in a unified way, including some product-specific features like backplate RGB LEDs for available models!

If you haven't received your screen yet but want to start developing your theme now, you can use the [**"simulated LCD" mode!**](https://github.com/mathoudebine/turing-smart-screen-python/wiki/Simulated-display)

## How to start

### [> Follow instructions on the wiki to configure and start this project.](https://github.com/mathoudebine/turing-smart-screen-python/wiki)

There are 2 possible uses of this project Python code:
* **[as a System Monitor](#system-monitor)**, a standalone program working with themes to display your computer HW info and custom data in an elegant way.
[Check if your hardware is supported.](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-hardware-support)
* **[integrated in your project](#control-the-display-from-your-python-projects)**, to fully control the display from your own Python code.

## System monitor

This project is mainly a complete standalone program to use your screen as a system monitor, like the original vendor app.  
Some themes are already included for a quick start!  
### [> Configure and start system monitor](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-how-to-start)
<img src="res/docs/config_wizard.png"/>  

* Fully functional multi-OS code base (operates out of the box, tested on Windows, Linux & MacOS).
* Display configuration using GUI configuration wizard or `config.yaml` file: no Python code to edit.
* Compatible with [multiple smart screen models (Turing, XuanFang...)](https://github.com/mathoudebine/turing-smart-screen-python/wiki/Hardware-revisions). Backplate RGB LEDs are also supported for available models!
* Support [multiple hardware sensors and metrics (CPU/GPU usage, temperatures, memory, disks, etc)](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-themes#stats-entry) with configurable refresh intervals.
* Allow [creation of themes (see `res/themes`) with `theme.yaml` files using theme editor](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-themes) to be [shared with the community!](https://github.com/mathoudebine/turing-smart-screen-python/discussions/categories/themes)
* Easy to expand: [custom Python data sources](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-themes#add-custom-stats-to-a-theme) can be written to pull specific information and display it on themes like any other sensor.
* Auto-detect COM port based on the selected smart screen model.
* Tray icon with Exit option, useful when the program is running in background.

### [> List and preview of included themes](res/themes/themes.md)

### [> Themes creation/edition (using theme editor)](https://github.com/mathoudebine/turing-smart-screen-python/wiki/System-monitor-:-themes)

### [> Control the display from your code](https://github.com/mathoudebine/turing-smart-screen-python/wiki/Control-screen-from-your-own-code)

</details>

## Avisos

Este software es una alternativa open-source basada en [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPL-3.0).  
**No está afiliado** a Turing, XuanFang, Kipye ni a sus fabricantes.  
Para hardware Turing: [foro oficial](http://discuz.turzx.com/).

## Autor Linux Edition

**David / [pilahito](https://github.com/pilahito)** — scripts, menú, autostart, temas y documentación para Ubuntu/Debian.