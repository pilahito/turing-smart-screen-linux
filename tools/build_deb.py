#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Construye un paquete .deb de Centro Turing / Turing Smart Screen (Linux).

Funciona en cualquier sistema (no necesita `dpkg-deb`): arma el ar con
`debian-binary`, `control.tar.gz` y `data.tar.gz` como manda la especificación
Debian, y comprueba el resultado (md5sums, rutas y campos del control).

Uso:
    python tools/build_deb.py [--version 1.0.7] [--arch all] [--out dist]
                              [--sin-temas] [--sin-fuentes]

Contenido del paquete:
    /opt/centro-turing/...            aplicacion, biblioteca, scripts, temas y fuentes
    /usr/bin/centro-turing            lanzador del panel grafico
    /usr/bin/turing-menu              menu de texto (respaldo)
    /usr/share/applications/*.desktop entradas de menu
    /usr/share/icons/.../centro-turing.png
    /usr/share/doc/centro-turing/     copyright y changelog
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import re
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_DIR = "opt/centro-turing"
DOC_DIR = "share/doc/centro-turing"

# Carpetas de fuentes que necesitan los temas incluidos (se completan al vuelo)
FUENTES_BASE = ("roboto", "jetbrains-mono")

# Rutas del proyecto que no deben acabar en el paquete
EXCLUIR_DIRS = {
    ".git", "venv", ".venv", "__pycache__", "dist", "build", "tmp", "tests",
    ".github", "external", "res/themes/--Theme examples", "res/fonts/racespace/original",
}
EXCLUIR_SUFIJOS = (".pyc", ".pyo", ".bak", ".bak-centro", ".bak-resolucion", ".xcf", ".gs2",
                   ".svg", ".original", ".md5", ".spec")
EXCLUIR_NOMBRES = {"background_original.gif", "background_original.png", "preview.png"}


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------------------
# Selección de contenido
# --------------------------------------------------------------------------------------
def fuentes_necesarias(project: Path, temas: bool) -> set[str]:
    """Fuentes referenciadas por los temas incluidos (+ las basicas)."""
    necesarias = set(FUENTES_BASE)
    if not temas:
        return necesarias
    patron = re.compile(r"FONT:\s*[\"']?([^\"'\s/]+)/")
    for theme_yaml in (project / "res" / "themes").glob("*/theme.yaml"):
        try:
            texto = theme_yaml.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        necesarias.update(patron.findall(texto))
    disponibles = {p.name for p in (project / "res" / "fonts").iterdir() if p.is_dir()}
    return necesarias & disponibles


def _excluido(relativa: str, nombre: str) -> bool:
    if nombre in EXCLUIR_NOMBRES:
        return True
    if any(relativa == d or relativa.startswith(d + "/") for d in EXCLUIR_DIRS):
        return True
    return nombre.endswith(EXCLUIR_SUFIJOS)


def recolectar(project: Path, con_temas: bool, con_fuentes: bool) -> list[tuple[str, Path]]:
    """Lista (ruta_destino_relativa, fichero_origen) para el paquete."""
    entradas: list[tuple[str, Path]] = []
    fuentes = fuentes_necesarias(project, con_temas) if con_fuentes else set()

    for origen in project.rglob("*"):
        if origen.is_dir() or origen.is_symlink():
            continue
        relativa = origen.relative_to(project).as_posix()
        if _excluido(relativa, origen.name):
            continue
        if relativa.startswith("res/themes/") and not con_temas:
            continue
        if relativa.startswith("res/fonts/"):
            if not con_fuentes:
                continue
            carpeta = relativa.split("/")[2] if len(relativa.split("/")) > 2 else ""
            if carpeta not in fuentes:
                continue
        # Solo el codigo y los recursos de la aplicacion. Nunca config.yaml: es la
        # configuracion personal del usuario (se instala config.example.yaml y la
        # aplicacion crea su config.yaml la primera vez que se abre).
        if relativa == "config.yaml":
            continue
        if not (relativa.startswith(("library/", "tools/", "scripts/", "res/"))
                or relativa in {"main.py", "theme-editor.py", "simple-program.py",
                                "requirements.txt", "config.example.yaml",
                                "VERSION", "LICENSE", "COPYRIGHT", "AUTHORS"}):
            continue
        entradas.append((f"{INSTALL_DIR}/{relativa}", origen))
    return entradas


# --------------------------------------------------------------------------------------
# Ficheros generados
# --------------------------------------------------------------------------------------
def launcher_panel() -> bytes:
    return b"""#!/bin/sh
# Centro Turing 3.0 - panel grafico de la mini pantalla USB
DIR=/opt/centro-turing
PY=python3
if [ -x "$DIR/.venv/bin/python3" ]; then PY="$DIR/.venv/bin/python3"; fi
exec "$PY" "$DIR/tools/turing_center.py" "$@"
"""


def launcher_menu() -> bytes:
    return b"""#!/bin/sh
# Menu de texto (respaldo del panel grafico)
exec /opt/centro-turing/scripts/turing-menu.sh "$@"
"""


def desktop_entry() -> bytes:
    return b"""[Desktop Entry]
Type=Application
Name=Centro Turing
GenericName=Mini pantalla USB
Comment=Panel de la mini pantalla Turing USB: temas, brillo, ajustes y diagnostico
Exec=centro-turing
Icon=centro-turing
Terminal=false
Categories=System;Monitor;Settings;
Keywords=turing;pantalla;monitor;lcd;
StartupNotify=true
"""


def desktop_menu() -> bytes:
    return b"""[Desktop Entry]
Type=Application
Name=Turing Smart Screen (menu)
Comment=Menu de texto: temas, reinicio, registro, ventiladores
Exec=x-terminal-emulator -e turing-menu
Icon=utilities-system-monitor
Terminal=true
Categories=System;Monitor;
"""


def postinst() -> bytes:
    return b"""#!/bin/sh
set -e
# Refrescar caches del escritorio si las herramientas estan disponibles
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
fi
echo "Centro Turing instalado. Abrelo desde el menu (Centro Turing) o con: centro-turing"
echo "Para el puerto USB: sudo usermod -aG dialout \"$USER\"  (y vuelve a iniciar sesion)"
exit 0
"""


def prerm() -> bytes:
    return b"""#!/bin/sh
set -e
pkill -f "/opt/centro-turing/main.py" 2>/dev/null || true
exit 0
"""


def control_file(version: str, arch: str, instalado_kb: int) -> bytes:
    return f"""Package: centro-turing
Version: {version}
Section: utils
Priority: optional
Architecture: {arch}
Maintainer: pilahito <pilahito1chico@gmail.com>
Installed-Size: {instalado_kb}
Depends: python3 (>= 3.10), python3-tk, python3-pil, python3-yaml, python3-serial, python3-psutil
Recommends: lm-sensors, python3-requests
Homepage: https://github.com/pilahito/turing-smart-screen-linux
Description: Panel y monitor para mini pantallas USB Turing / XuanFang
 Centro Turing incluye un panel grafico (interfaz 2026, Tkinter + Pillow) con
 vista previa de temas, brillo, ajustes de config.yaml, registro en vivo y
 diagnostico, ademas del monitor de sistema y un menu de texto de respaldo.
 .
 Funciona con las pantallas Turing 3.5", 5" y 8.8" (y compatibles XuanFang,
 WeAct). Trae temas preparados para 3.5" horizontal y vertical.
""".encode("utf-8")


def copyright_file() -> bytes:
    return b"""Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: turing-smart-screen-python
Source: https://github.com/mathoudebine/turing-smart-screen-python

Files: *
Copyright: mathoudebine and contributors
License: GPL-3.0-or-later
 This program is free software: you can redistribute it and/or modify it under
 the terms of the GNU General Public License as published by the Free Software
 Foundation, either version 3 of the License, or (at your option) any later
 version.
 .
 On Debian systems the full text of the GPL-3 is in
 /usr/share/common-licenses/GPL-3.
"""


# --------------------------------------------------------------------------------------
# Empaquetado
# --------------------------------------------------------------------------------------
def tar_gz(ficheros: list[tuple[str, bytes]], mtime: int,
           ejecutables: set[str] | None = None, con_directorios: bool = True) -> bytes:
    """Crea un .tar.gz con rutas relativas ('./') y permisos correctos.

    `con_directorios` anade las entradas de carpeta: dpkg las necesita para crear
    /opt/centro-turing y el resto del arbol. Sin ellas falla al instalar con
    "unable to create ... No such file or directory".
    """
    ejecutables = ejecutables or set()
    buffer = io.BytesIO()

    def add_dir(tar: tarfile.TarFile, nombre: str) -> None:
        info = tarfile.TarInfo(name=nombre)
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.mtime = mtime
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        tar.addfile(info)

    with tarfile.open(fileobj=buffer, mode="w") as tar:
        add_dir(tar, "./")
        if con_directorios:
            carpetas = set()
            for ruta, _ in ficheros:
                partes = ruta.split("/")[:-1]
                for indice in range(1, len(partes) + 1):
                    carpetas.add("/".join(partes[:indice]))
            for carpeta in sorted(carpetas):  # ordenadas: los padres van antes que los hijos
                add_dir(tar, "./" + carpeta + "/")
        for ruta, datos in ficheros:
            info = tarfile.TarInfo(name="./" + ruta.lstrip("./"))
            info.size = len(datos)
            info.mtime = mtime
            info.mode = 0o755 if ruta in ejecutables else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(datos))
    comprimido = io.BytesIO()
    with gzip.GzipFile(fileobj=comprimido, mode="wb", mtime=mtime) as gz:
        gz.write(buffer.getvalue())
    return comprimido.getvalue()


def ar_archive(miembros: list[tuple[str, bytes]]) -> bytes:
    """Formato ar de Unix (el que usan los .deb)."""
    salida = io.BytesIO()
    salida.write(b"!<arch>\n")
    for nombre, datos in miembros:
        cabecera = (
            f"{nombre + '/':<16}"      # los .deb usan 'nombre/' en el campo de nombre
            f"{int(time.time()):<12}"
            f"{0:<6}{0:<6}"
            f"{0o100644:<8o}"
            f"{len(datos):<10}"
            "`\n"
        ).encode("ascii")
        salida.write(cabecera)
        salida.write(datos)
        if len(datos) % 2:
            salida.write(b"\n")
    return salida.getvalue()


def construir(project: Path, out_dir: Path, version: str, arch: str,
              con_temas: bool, con_fuentes: bool) -> Path:
    mtime = int(time.time())
    entradas = recolectar(project, con_temas, con_fuentes)
    if not entradas:
        raise SystemExit("No se ha seleccionado ningun fichero: revisa las rutas")

    data_files: list[tuple[str, bytes]] = []
    md5_lineas = []
    tamano_total = 0
    for destino, origen in entradas:
        datos = origen.read_bytes()
        tamano_total += len(datos)
        data_files.append((destino, datos))
        md5_lineas.append(f"{hashlib.md5(datos).hexdigest()}  /{destino}")

    # Lanzadores, entradas de menu e iconos
    extras = {
        "usr/bin/centro-turing": launcher_panel(),
        "usr/bin/turing-menu": launcher_menu(),
        "usr/share/applications/centro-turing.desktop": desktop_entry(),
        "usr/share/applications/turing-menu.desktop": desktop_menu(),
        "usr/share/icons/hicolor/256x256/apps/centro-turing.png":
            (project / "res" / "icons" / "centro-turing.png").read_bytes(),
        "usr/share/pixmaps/centro-turing.png":
            (project / "res" / "icons" / "centro-turing.png").read_bytes(),
        f"{DOC_DIR}/copyright": copyright_file(),
        f"{DOC_DIR}/changelog": f"centro-turing ({version}) unstable; urgency=medium\n\n".encode()
                                + b"  * Paquete generado con tools/build_deb.py\n\n"
                                + f" -- pilahito <pilahito1chico@gmail.com>  {time.ctime()}\n".encode(),
    }
    for ruta, datos in extras.items():
        data_files.append((ruta, datos))
        md5_lineas.append(f"{hashlib.md5(datos).hexdigest()}  /{ruta}")
        tamano_total += len(datos)

    data_files.append(("md5sums", "\n".join(md5_lineas).encode() + b"\n"))

    # data.tar.gz con permisos correctos: los lanzadores son ejecutables
    data_tar = tar_gz(data_files, mtime,
                      ejecutables={"usr/bin/centro-turing", "usr/bin/turing-menu"})
    control_files = [
        ("control", control_file(version, arch, max(1, tamano_total // 1024))),
        ("postinst", postinst()),
        ("prerm", prerm()),
    ]
    control_tar = tar_gz(control_files, mtime, ejecutables={"postinst", "prerm"})

    paquete = ar_archive([
        ("debian-binary", b"2.0\n"),
        ("control.tar.gz", control_tar),
        ("data.tar.gz", data_tar),
    ])

    out_dir.mkdir(parents=True, exist_ok=True)
    destino = out_dir / f"centro-turing_{version}_{arch}.deb"
    destino.write_bytes(paquete)
    log(f"Paquete: {destino}  ({destino.stat().st_size / 1024 / 1024:.1f} MB, "
        f"{len(entradas)} ficheros del proyecto + {len(extras)} generados)")
    return destino


def leer_ar(datos: bytes) -> list[tuple[str, bytes]]:
    """Lee un archivo ar (lo usan los .deb) y devuelve sus miembros."""
    if not datos.startswith(b"!<arch>\n"):
        raise ValueError("no es un archivo ar")
    pos = 8
    miembros = []
    while pos + 60 <= len(datos):
        cabecera = datos[pos:pos + 60]
        nombre = cabecera[0:16].decode("ascii").strip()
        tamano = int(cabecera[48:58].decode("ascii").strip())
        pos += 60
        contenido = datos[pos:pos + tamano]
        pos += tamano + (tamano % 2)
        miembros.append((nombre.rstrip("/"), contenido))
    return miembros


def verificar(paquete: Path) -> None:
    log("--- verificacion del paquete ---")
    miembros = leer_ar(paquete.read_bytes())
    nombres = [n for n, _ in miembros]
    assert nombres == ["debian-binary", "control.tar.gz", "data.tar.gz"], f"orden incorrecto: {nombres}"
    assert miembros[0][1] == b"2.0\n", "debian-binary incorrecto"
    log(f"  ar OK: {nombres}")

    control = {n: d for n, d in leer_tar_gz(miembros[1][1])}
    campos = control["control"].decode("utf-8")
    for obligatorio in ("Package: centro-turing", "Version:", "Architecture:", "Depends:",
                        "Description:", "Maintainer:", "Installed-Size:"):
        assert obligatorio in campos, f"falta {obligatorio} en control"
    log("  control OK: " + campos.splitlines()[0] + " | " + campos.splitlines()[1])

    contenido = {n: d for n, d in leer_tar_gz(miembros[2][1])}
    imprescindibles = ["opt/centro-turing/main.py", "opt/centro-turing/tools/turing_center.py",
                       "opt/centro-turing/tools/turing_design.py",
                       "opt/centro-turing/library/config.py",
                       "usr/bin/centro-turing", "usr/share/applications/centro-turing.desktop",
                       "usr/share/icons/hicolor/256x256/apps/centro-turing.png", "md5sums"]
    for ruta in imprescindibles:
        assert ruta in contenido, f"falta {ruta}"
    log(f"  data OK: {len(contenido)} entradas (incluye las {len(imprescindibles)} clave)")

    # dpkg necesita las entradas de carpeta: sin ellas falla al instalar con
    # "unable to create ... No such file or directory"
    directorios = {n for n, es_dir in listar_tar_gz(miembros[2][1]) if es_dir}
    faltan = set()
    for ruta in contenido:
        partes = ruta.split("/")[:-1]
        for indice in range(1, len(partes) + 1):
            carpeta = "/".join(partes[:indice])
            if carpeta not in directorios:
                faltan.add(carpeta)
    assert not faltan, f"faltan entradas de carpeta en data.tar.gz: {sorted(faltan)[:5]}"
    log(f"  carpetas OK: {len(directorios)} entradas de directorio (dpkg puede crear el arbol)")

    fallos = 0
    for linea in contenido["md5sums"].decode().splitlines():
        if not linea.strip():
            continue
        suma, ruta = linea.split("  ", 1)
        clave = ruta.lstrip("/")
        if clave not in contenido:
            fallos += 1
            continue
        if hashlib.md5(contenido[clave]).hexdigest() != suma:
            fallos += 1
    assert fallos == 0, f"md5sums no cuadran en {fallos} ficheros"
    log("  md5sums OK: todas las sumas cuadran")

    temas = [n for n in contenido if n.startswith("opt/centro-turing/res/themes/")
             and n.endswith("theme.yaml")]
    log(f"  temas incluidos: {len(temas)}")
    log("--- paquete valido ---")


def leer_tar_gz(datos: bytes) -> list[tuple[str, bytes]]:
    with tarfile.open(fileobj=io.BytesIO(datos), mode="r:gz") as tar:
        salida = []
        for info in tar.getmembers():
            if info.isfile():
                fh = tar.extractfile(info)
                salida.append((info.name.lstrip("./"), fh.read() if fh else b""))
        return salida


def listar_tar_gz(datos: bytes) -> list[tuple[str, bool]]:
    """Lista (ruta, es_directorio) de un tar.gz: sirve para validar la estructura."""
    with tarfile.open(fileobj=io.BytesIO(datos), mode="r:gz") as tar:
        return [(info.name.lstrip("./").rstrip("/"), info.isdir()) for info in tar.getmembers()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construye el .deb de Centro Turing")
    parser.add_argument("--version", default=None, help="version del paquete (por defecto VERSION)")
    parser.add_argument("--arch", default="all", help="arquitectura (por defecto all)")
    parser.add_argument("--out", default="dist", help="carpeta de salida")
    parser.add_argument("--sin-temas", action="store_true", help="no incluir res/themes")
    parser.add_argument("--sin-fuentes", action="store_true", help="no incluir res/fonts")
    parser.add_argument("--sin-verificar", action="store_true", help="no comprobar el resultado")
    args = parser.parse_args(argv)

    version = args.version
    if not version:
        try:
            version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        except OSError:
            version = "1.0.0"
    # limpieza defensiva: BOM, comillas, espacios y sufijos del proyecto
    version = version.lstrip("\ufeff").strip().strip('"')
    version = version.replace("-linux-ubuntu", "").strip() or "1.0.0"

    destino = construir(ROOT, (ROOT / args.out).resolve(), version, args.arch,
                        not args.sin_temas, not args.sin_fuentes)
    if not args.sin_verificar:
        verificar(destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
