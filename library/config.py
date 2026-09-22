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
THEME_DEFAULT = load_yaml(MAIN_DIRECTORY / "res/themes/default.yaml")
THEME_DATA = None


def copy_default(default, theme):
    """recursively supply default values into a dict of dicts of dicts ...."""
    for k, v in default.items():
        if k not in theme:
            theme[k] = v
        if type(v) == type({}):
            copy_default(default[k], theme[k])


def load_theme():
    global THEME_DATA
    try:
        # str(): el nombre del tema puede ser numerico (hay temas llamados 26, 30,
        # 43, 44, 45). Si el config.yaml no lo entrecomilla, YAML lo lee como entero
        # y "res/themes/" + 26 fallaba con TypeError -> "Theme not found or contains
        # errors!" sin decir por que.
        theme_name = str(CONFIG_DATA['config']['THEME'])
        theme_path = Path("res/themes/" + theme_name)
        logger.info("Loading theme %s from %s" % (theme_name, theme_path / "theme.yaml"))
        THEME_DATA = load_yaml(MAIN_DIRECTORY / theme_path / "theme.yaml")
        THEME_DATA['PATH'] = str(MAIN_DIRECTORY / theme_path) + "/"
    except Exception as error:
        logger.error(f"Theme not found or contains errors! ({type(error).__name__}: {error})")
        try:
            sys.exit(0)
        except:
            os._exit(0)

    copy_default(THEME_DEFAULT, THEME_DATA)


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
