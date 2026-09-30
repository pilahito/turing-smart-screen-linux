# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# Copyright (C) 2021 Matthieu Houdebine (mathoudebine)
# Copyright (C) 2022 Rollbacke
# Copyright (C) 2022 Ebag333
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

import copy
import os
import queue
import sys
from pathlib import Path
import yaml

from library.log import logger


def load_yaml(configfile):
    with open(configfile, "rt", encoding='utf-8-sig') as stream:
        yamlconfig = yaml.safe_load(stream)
        return yamlconfig


PATH = sys.path[0]
MAIN_DIRECTORY = Path(__file__).parent.parent.resolve()
FONTS_DIR = str(MAIN_DIRECTORY / "res" / "fonts") + "/"
CONFIG_DATA = load_yaml(MAIN_DIRECTORY / "config.yaml")
if not isinstance(CONFIG_DATA, dict):
    # config.yaml vacio o con YAML invalido: mejor decirlo claro que fallar con
    # "TypeError: 'NoneType' object is not subscriptable".
    logger.error("config.yaml no se ha podido leer (esta vacio o el YAML no es valido)")
    CONFIG_DATA = {}
THEME_DEFAULT = load_yaml(MAIN_DIRECTORY / "res/themes/default.yaml")
THEME_DATA = None


def _as_int(value, default: int) -> int:
    """'53', ' 53 ', 53.0 -> 53.  Un valor vacio o invalido usa el default.

    En YAML, "BRIGHTNESS: '53'" (entrecomillado) llega como str y SetBrightness()
    moria con "TypeError: '<=' not supported between instances of 'int' and 'str'",
    un mensaje que no menciona config.yaml por ningun lado.
    """
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _none_paths(node, path: str = "", max_depth: int = 6) -> list:
    """Rutas de claves declaradas pero SIN valor (YAML truncado o clave vacia)."""
    encontradas = []
    if max_depth <= 0 or not isinstance(node, dict):
        return encontradas
    for k, v in node.items():
        ruta = f"{path}.{k}" if path else str(k)
        if v is None:
            encontradas.append(ruta)
        else:
            encontradas += _none_paths(v, ruta, max_depth - 1)
    return encontradas


def copy_default(default, theme):
    """recursively supply default values into a dict of dicts of dicts ....

    Tolera secciones presentes pero VACIAS (None), que es lo que deja un
    theme.yaml cortado a mitad: con "STATS.CPU.PERCENTAGE:" sin contenido, el
    arranque estallaba con "TypeError: argument of type 'NoneType' is not
    iterable" y el monitor se cerraba sin decir que tema fallaba.
    """
    if not isinstance(theme, dict):
        return
    for k, v in default.items():
        if isinstance(v, dict):
            if not isinstance(theme.get(k), dict):
                if theme.get(k) is not None:
                    logger.warning(
                        "El tema define '%s' como %s y deberia ser una seccion: se usa la de por defecto",
                        k, type(theme[k]).__name__)
                theme[k] = copy.deepcopy(v)
            copy_default(v, theme[k])
        elif k not in theme or theme[k] is None:
            theme[k] = copy.deepcopy(v)


def _sanitize_config(data) -> None:
    """Normaliza los tipos de config.yaml (brillo, revision, puerto, tema...).

    display.py y los lcd_comm*.py usan estos valores de forma directa, asi que un
    valor entrecomillado en el YAML no debe llegar nunca hasta ellos.
    """
    if not isinstance(data, dict):
        return
    config = data.get("config")
    if not isinstance(config, dict):
        config = data["config"] = {}
    display = data.get("display")
    if not isinstance(display, dict):
        display = data["display"] = {}

    config["COM_PORT"] = str(config.get("COM_PORT") or "AUTO").strip()
    config["THEME"] = str(config.get("THEME") or "").strip()
    display["REVISION"] = str(display.get("REVISION") or "A").strip().upper()

    brillo = _as_int(display.get("BRIGHTNESS"), 25)
    if not 0 <= brillo <= 100:
        logger.warning("BRIGHTNESS fuera de rango en config.yaml (%r): se ajusta a 0-100", display.get("BRIGHTNESS"))
        brillo = min(100, max(0, brillo))
    if display.get("BRIGHTNESS") != brillo:
        logger.debug("BRIGHTNESS normalizado a %s (en config.yaml: %r)", brillo, display.get("BRIGHTNESS"))
    display["BRIGHTNESS"] = brillo


_sanitize_config(CONFIG_DATA)


def load_theme():
    global THEME_DATA
    theme_name = ""
    try:
        # str(): el nombre del tema puede ser numerico (hay temas llamados 26, 30,
        # 43, 44, 45). Si el config.yaml no lo entrecomilla, YAML lo lee como entero
        # y "res/themes/" + 26 fallaba con TypeError -> "Theme not found or contains
        # errors!" sin decir por que.
        theme_name = str(CONFIG_DATA['config']['THEME'])
        theme_path = Path("res/themes/" + theme_name)
        logger.info("Loading theme %s from %s" % (theme_name, theme_path / "theme.yaml"))
        theme_data = load_yaml(MAIN_DIRECTORY / theme_path / "theme.yaml")
        if not isinstance(theme_data, dict):
            raise ValueError("el theme.yaml esta vacio o no contiene un mapa YAML")
        THEME_DATA = theme_data
        THEME_DATA['PATH'] = str(MAIN_DIRECTORY / theme_path) + "/"

        # Secciones declaradas pero vacias = sintoma de un theme.yaml cortado.
        # Se completan con los valores por defecto y se avisa, en vez de reventar.
        vacias = _none_paths(THEME_DATA)
        copy_default(THEME_DEFAULT, THEME_DATA)
        if vacias:
            logger.warning(
                "El tema '%s' tiene %d seccion(es) sin contenido (%s%s): se completan con los valores por "
                "defecto; el theme.yaml parece incompleto o cortado.",
                theme_name, len(vacias), ", ".join(vacias[:5]), "..." if len(vacias) > 5 else "")
    except Exception as error:
        logger.error(f"Theme not found or contains errors! (tema '{theme_name}': {type(error).__name__}: {error})")
        try:
            sys.exit(0)
        except:
            os._exit(0)


def _norm_size(value) -> str:
    """'3.5', '3.5\"', 3.5 → 3.5  (evita que las skins horizontales fallen por comillas)."""
    s = str(value or "").strip().replace('"', "").replace("'", "").replace(" ", "")
    if s.endswith("inch"):
        s = s[:-4]
    return s


def check_theme_compatible(display_size: str):
    theme_size = _norm_size(THEME_DATA.get("display", {}).get("DISPLAY_SIZE", "3.5\""))
    hw_size = _norm_size(display_size)
    # En 3.5" landscape, permitir temas 3.5 y los que no declaran tamaño (default 3.5).
    if theme_size and hw_size and theme_size != hw_size:
        orient = str(THEME_DATA.get("display", {}).get("DISPLAY_ORIENTATION", "")).lower()
        bg = THEME_DATA.get("static_images", {}).get("BACKGROUND", {})
        w, h = int(bg.get("WIDTH") or 0), int(bg.get("HEIGHT") or 0)
        landscape_35 = orient == "landscape" and hw_size == "3.5" and w == 480 and h == 320
        if landscape_35:
            logger.warning(
                "Tema %s declara DISPLAY_SIZE %s pero el fondo es 480x320: se usa en la 3.5\" horizontal.",
                CONFIG_DATA["config"]["THEME"], theme_size,
            )
            return
        logger.error("The selected theme " + CONFIG_DATA['config'][
            'THEME'] + " is not compatible with your display revision " + CONFIG_DATA["display"]["REVISION"])
        try:
            sys.exit(0)
        except:
            os._exit(0)


# Load theme on import
load_theme()

# Queue containing the serial requests to send to the screen
update_queue = queue.Queue()
