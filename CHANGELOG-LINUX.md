# Changelog — Linux / Ubuntu (pilahito)

## [1.0.7-linux-ubuntu] - 2026-09-22

### Nuevo
- **Centro Turing 3.0** (`tools/turing_center.py`): panel gráfico multiplataforma que funciona
  igual en **Windows y Linux**, con Tkinter/ttk (sin dependencias nuevas obligatorias).
  - Panel en vivo: estado del monitor, puerto, brillo y modo de sensores + vista previa del tema
  - Catálogo de temas con filtro por medida/orientación, búsqueda y vista previa del fondo
  - Ajustes de `config.yaml` (tema, sensores, revisión, puerto, brillo, clima) conservando
    comentarios y orden, con copia `.bak-centro`
  - Registro en vivo, diagnóstico del sistema y arranque automático con un interruptor
  - `--status` (estado en texto), `--theme NOMBRE`, `--selftest` (auditoría de layout)
    y `--mockup CARPETA` (genera imágenes de la interfaz sin abrir ventana)
- **Interfaz 2026** (`tools/turing_design.py` + `tools/turing_ui2026.py`): rediseño visual completo.
  - Todo se dibuja con Pillow sobre un lienzo único: superficies redondeadas con degradado,
    borde luminoso y sombra; cabecera con resplandores; tipografía Segoe UI / Roboto
  - Componentes propios: botones con estados, interruptores animados, control segmentado,
    chips, deslizador de brillo arrastrable, tarjetas de estado con mini-gráficas y avisos flotantes
  - Iconos vectoriales dibujados a mano (no dependen de que la tipografía tenga el glifo)
  - Transición deslizante entre páginas, resaltado al pasar el ratón y desplazamiento con rueda
  - El mismo motor genera las previsualizaciones, así que el diseño se puede revisar sin abrir la app
- `scripts/turing-center.sh` — lanzador del panel gráfico para Linux
- `scripts/install-desktop-menu.sh` — crea ahora también el acceso directo **Centro Turing**
  (GUI, sin terminal) y lo registra en el menú de aplicaciones
- `scripts/turing-menu.sh` — nueva opción **g) Panel gráfico (Centro Turing 3.0)**;
  el menú de texto se mantiene como respaldo

### Corregido
- La interfaz anterior (Centro Turing v2) se recortaba y solapaba: usaba `overrideredirect`,
  tamaño fijo 1100x720 y etiquetas flotantes con `place()` encima del contenido. La nueva
  interfaz usa decoración nativa, `grid` con pesos, páginas con scroll y barra de estado.
- Estado de ventana inválido (`1x1`) guardado antes de mapear: la ventana podía arrancar
  invisible. Ahora solo se guarda una geometría válida (>= 920x560).

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