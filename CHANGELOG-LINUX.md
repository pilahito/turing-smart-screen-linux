# Changelog — Linux / Ubuntu (pilahito)

## [1.1.0-linux-ubuntu] - 2026-09-30

Centro Turing 3.1.1 (Windows) - temperatura de CPU con administrador y arreglos del panel.

### Nuevo
- **Arranque con administrador sin aviso UAC**: tarea programada "Centro Turing (admin)"
  (al iniciar sesion, `lanzar.py --tarea`) y "Centro Turing (admin) detener".
  LibreHardwareMonitor ya lee la temperatura de la CPU. Se activa con el interruptor
  "Arranque automatico" de Ajustes o con `Arreglar-Temperatura-CPU.ps1`
  (`tools/autoarranque-admin.ps1`). Desactiva el arranque antiguo de la carpeta Inicio.
- El panel arranca, detiene y reinicia el monitor elevado a traves de esas tareas.
- `lanzar.py`: un solo lanzador a la vez (evita dos monitores al iniciar sesion) y
  `--detener`.

### Corregido
- `log.log` y la salida del monitor se escriben en UTF-8 (adios a "Â°C").
- Panel: las tarjetas de estado se quedaban estrechas tras redimensionar.
- Temas: la busqueda quedaba tapada por la vista previa y los botones pisaban la
  ultima fila de la lista; titulos y subtitulos ya no se solapan.
- Simulador: captura guardada de forma atomica.
- Temas incluidos: textos en espanol (Usado/Libre/Disco) y posiciones ajustadas.

## [1.0.9-linux-ubuntu] - 2026-09-30

Centro Turing **3.1.1** (Windows): arranque, apagado y temas horizontales.

### Nuevo
- **4 temas horizontales 480x320** para la 3.5": `AyistaxNeon_H`, `SynthwaveES_H`,
  `MatrixES_H` y `MinimalOscuro_H` (generados con `tools/crear_temas_2026.py`,
  vista previa sin pantalla con `tools/render_sandbox.py`). La página Tema muestra
  una descripción de cada uno.
- **Espera al puerto COM al arrancar** (`lcd_comm.py`): hasta 60 s (`COM_WAIT_SECONDS`)
  y detección automática de la pantalla por VID/PID (1A86:5722) si cambia de número.
- **`tools/lanzar.py`**: lanzador único (`--arranque` para el inicio de Windows) que
  cierra solo el monitor de esta carpeta, espera a "Starting system monitoring" y
  avisa con un mensaje corto si falla.
- **Pantalla apagada al apagar/reiniciar Windows** (`library/apagado_windows.py`):
  ventana oculta que atiende `WM_QUERYENDSESSION`, brillo 0 + `SCREEN_OFF`
  confirmados antes de salir. Script de apagado opcional por directiva de grupo:
  `tools/apagar-pantalla-apagado.cmd` / `tools/apagar_pantalla.py`.

### Corregido
- El generador de temas (aleatorio / IA) y `Arreglar-Temperatura-CPU.ps1` mataban
  **cualquier** proceso Python con `main.py` (también otros programas).
- En el `.exe`, el generador de temas buscaba `res/themes` en la carpeta temporal de
  PyInstaller.
- Una tarea que terminaba con `SystemExit` dejaba el panel en "Hay una tarea en curso".
- Botón "sensores avanzados (UAC)": faltaba cerrar una comilla en el comando.
- `Iniciar-Admin.ps1` buscaba la ruta antigua y dejaba dos monitores peleando por el COM.
- Los scripts ya no reescriben `config.yaml` con BOM.
- `elegir-tema.py` / `Cambiar-Tema.ps1`: temas `_H` y lectura de `THEME` con sangría.
- Envío a la pantalla más rápido (cola drenada sin esperas de 1 ms).

## [1.0.8-linux-ubuntu] - 2026-09-22

Versión **estable**: paquetes instalables, correcciones de librería y la suite de
pruebas del proyecto en verde.

### Paquetes instalables
- **Windows**: `Centro-Turing-3.1.exe` (PyInstaller, un solo fichero, sin consola) con
  el icono del proyecto incrustado. Se acabó el icono de Python: se fija la identidad
  de la aplicación (`SetCurrentProcessExplicitAppUserModelID`) y el ejecutable lleva
  `res/icons/centro-turing.ico`.
- **Ubuntu/Debian**: `centro-turing_1.0.8_all.deb` (57 MB, 75 temas). Instala en
  `/opt/centro-turing`, los comandos `centro-turing` y `turing-menu`, la entrada del
  menú y el icono. Se construye con `tools/build_deb.py` (sin necesitar `dpkg-deb`) y
  el CI lo **instala de prueba** en cada release.
- El `.deb` no incluye `config.yaml` (configuración personal): la aplicación lo crea
  desde `config.example.yaml` la primera vez que se abre.
- `--mockup CARPETA` genera las imágenes de la interfaz sin abrir la ventana.

### Corregido (librería)
- **Rev. C — tamaño del bitmap**: se enviaba `ancho²/64` en vez de `ancho×alto/64`.
  Para una 3.5"/5" (480x800) mandaba 3600 en lugar de 6000 (0x1770), que es el valor
  que llevan las constantes por modelo (`DISPLAY_BITMAP_5INCH`) y los ficheros golden.
- **Rev. C — arranque**: `sub_revision` y `rom_version` solo se creaban en
  `InitializeComm()`, así que cualquier uso previo fallaba con `AttributeError`.
  Ahora tienen valor por defecto en el constructor y existe el comando genérico
  `DISPLAY_BITMAP` para cuando aún no se ha detectado el modelo.
- **Ficheros golden de rev. C** actualizados: estaban grabados de cuando la inversión
  se hacía por hardware (comando `OPTIONS` + `FLIP_180`), rama que está desactivada en
  el propio proyecto porque la inversión se hace rotando la imagen por software.
- **Suite de pruebas: 37 pasan, 0 fallan** (antes 29 pasaban y 8 fallaban).

### Corregido (panel)
- Se comprobaba el PID de `monitor.pid` sin verificar de quién era antes de matarlo
  (Windows recicla PID) y podía cerrar un proceso ajeno.
- Si el monitor corría como administrador, el panel informaba de "detenido" sin serlo.

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