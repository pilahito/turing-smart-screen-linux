# Turing Smart Screen — Linux / Ubuntu

Versión **1.0.1-linux-ubuntu** — monitor de sistema en mini pantalla USB (Turing 3.5", QinHeng `1a86:5722`, etc.).

Basado en [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPL-3.0) con mejoras para **Ubuntu 22.04+ / Debian 12+**:

- Arranque automático al iniciar sesión (systemd user + autostart)
- Compatible con **Cinnamon, GNOME, MATE, XFCE** (autostart vía `.desktop` + systemd user)
- Detección USB `/dev/ttyACM*` (QinHeng `1a86:5722`)
- FPS en Linux (`turing-fps.service` → Hz del monitor o MangoHud)
- Ventiladores CPU en placas Gigabyte (`it87` + `force_id=0x8622`)
- GPU NVIDIA: temperatura y uso vía `nvidia-smi` (ventilador GPU si el driver lo expone)
- Selector de **temas ya incluidos** en `res/themes/`
- [Releases](https://github.com/pilahito/turing-smart-screen-linux/releases) con versiones etiquetadas

## Instalación rápida (Ubuntu)

```bash
git clone https://github.com/pilahito/turing-smart-screen-linux.git
cd turing-smart-screen-linux
./scripts/install-ubuntu.sh
```

## Temas incluidos (3.5")

Usa cualquier carpeta de `res/themes/` sin descargar nada extra:

| Tema | Estilo |
|------|--------|
| **Cyberdeck** | Cyberpunk landscape (por defecto) |
| **LandscapeModernDevice35** | Moderno landscape |
| **SimpleCyberpunkGauge** | Gauges cyberpunk |
| **SimpleNeonGauge** / **SimpleFireGauge** | Gauges color |
| **SimpleBlueGauge** / **SimpleRedGauge** / … | Variantes Simple* |
| **Advanced Radials Test** | Radiales de prueba |
| **Cyberpunk** | Portrait 320×480 |

Listar todos:

```bash
./scripts/list-themes.sh 3.5
```

Cambiar tema y reiniciar:

```bash
./scripts/set-theme.sh LandscapeModernDevice35
```

## Menú en el escritorio

```bash
./scripts/install-desktop-menu.sh
# o doble clic en "Turing Smart Screen" en Escritorio
```

Opciones del menú:
- Elegir tema con filtro **landscape / portrait** (41+ temas 3.5")
- **Galería visual** de temas en el navegador
- **Descargar temas** de la comunidad (RedLineGraphs, CpuGpuStatsMono, …)
- **Pantalla virtual** en el PC (modo SIMU + navegador + ventana espejo en DP-0/HDMI-0)
- Reiniciar monitor, log, autostart, ventiladores

> La mini pantalla USB **no es un monitor extendido** de escritorio (limitación del hardware).  
> Sí puedes verla en vivo en tu PC con la opción *Pantalla virtual* del menú.

## Comandos útiles

```bash
./scripts/turing-menu.sh
systemctl --user status turing-smart-screen turing-fps
./scripts/set-theme.sh Cyberdeck
tail -f /tmp/turing-screen.log
sudo ./scripts/install-fan-modules.sh   # ventiladores Gigabyte (una vez)
```

## Requisitos

- Ubuntu 22.04+ / Debian 12+
- Python 3.10+
- Pantalla USB conectada (`lsusb | grep 1a86:5722`)
- Usuario en grupo `dialout` (el instalador lo configura)

## Licencia

GPL-3.0 — ver LICENSE. No afiliado a Turing/XuanFang.