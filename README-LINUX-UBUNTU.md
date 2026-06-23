# Turing Smart Screen — Linux / Ubuntu

Versión **1.0.0-linux-ubuntu** — monitor de sistema en mini pantalla USB (Turing 3.5", QinHeng `1a86:5722`, etc.).

Basado en [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) (GPL-3.0) con mejoras para **Ubuntu 24.04**:

- Arranque automático al iniciar sesión (systemd user + autostart)
- Detección USB `/dev/ttyACM*`
- FPS en Linux (`turing-fps.service` → Hz del monitor o MangoHud)
- Ventiladores CPU en placas Gigabyte (`it87` + `force_id=0x8622`)
- Selector de **temas ya incluidos** en `res/themes/`

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

## Comandos útiles

```bash
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