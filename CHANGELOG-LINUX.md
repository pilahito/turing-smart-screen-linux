# Changelog — Linux / Ubuntu (pilahito)

## [1.0.6-linux-ubuntu] - 2026-06-23

### Corregido
- **Tema Pilahito** bugueado: fondo custom interfería con los gauges → ahora usa layout Cyberdeck probado + colores cyan/rojo
- Eliminada sección DATE que causaba parpadeos
- **Cyberdeck** restaurado como tema por defecto estable
- `scripts/validate-theme.sh` — valida temas antes de publicar

## [1.0.5-linux-ubuntu] - 2026-06-23

### Añadido
- Tema Pilahito (primera versión — reemplazada en v1.0.6)

## [1.0.4-linux-ubuntu] - 2026-06-23

### Mejorado
- README principal rebranded como **Turing Smart Screen — Linux Edition**
- Perfil GitHub [pilahito](https://github.com/pilahito) con proyecto destacado
- Descripción y topics del repo orientados a “versión mejorada para Linux”

## [1.0.3-linux-ubuntu] - 2026-06-23

### Nuevo
- `scripts/fetch-community-themes.sh` — descarga temas 3.5" de GitHub (RedLineGraphs, CpuGpuStatsMono)
- `scripts/theme-gallery.sh` — galería HTML con previews en el navegador
- `scripts/start-virtual-screen.sh` — pantalla virtual en el PC (modo SIMU)
- `scripts/preview-window.py` — ventana espejo flotante (colocable en DP-0 / HDMI-0)
- `scripts/restore-usb-screen.sh` — vuelve a la pantalla USB física
- Menú ampliado: galería, comunidad, pantalla virtual, espejo, filtros landscape/portrait

## [1.0.2-linux-ubuntu] - 2026-06-23

### Mejorado
- Banner en `README.md` principal → enlace a guía Linux/Ubuntu y releases
- `README-LINUX-UBUNTU.md`: Cinnamon/MATE/XFCE, GPU NVIDIA, enlaces a releases
- Topics de GitHub para mejor descubrimiento del repositorio

## [1.0.1-linux-ubuntu] - 2026-06-23

### Nuevo
- `scripts/turing-menu.sh` — menú interactivo (temas por número, reinicio, log, autostart, fans)
- `scripts/install-desktop-menu.sh` — icono en Escritorio / Desktop
- `Turing-Smart-Screen.desktop` — lanzador con doble clic

## [1.0.0-linux-ubuntu] - 2026-06-23

### Nuevo
- `scripts/install-ubuntu.sh` — instalación completa en Ubuntu/Debian
- `scripts/list-themes.sh` / `scripts/set-theme.sh` — usa los **72 temas** ya en `res/themes/`
- `scripts/install-autostart.sh` — systemd user + autostart al login
- `scripts/poll-fps.sh` + `turing-fps.service` — FPS en Linux (MangoHud o Hz del monitor)
- `scripts/install-fan-modules.sh` — ventiladores Gigabyte B760 (`it87 force_id=0x8622`)
- `scripts/wait-usb-screen.sh` — detecta `/dev/ttyACM*` (QinHeng 1a86:5722)
- Mejoras en `library/stats.py` y `sensors_python.py` (fans, FPS externo)
- Tema **Cyberdeck** ajustado para 3.5" landscape

### Temas recomendados 3.5"
Cyberdeck, LandscapeModernDevice35, SimpleCyberpunkGauge, SimpleNeonGauge, Cyberpunk, Landscape6Grid, NZXT_* (5"), etc. — ver `./scripts/list-themes.sh 3.5`