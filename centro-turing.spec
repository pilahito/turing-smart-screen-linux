# -*- mode: python ; coding: utf-8 -*-
# Centro Turing 3.0 — ejecutable del panel (Windows)
#
# Genera un unico .exe con el icono del proyecto incrustado (para que Windows no
# muestre el icono de Python) y sin consola.
#
#   pyinstaller --noconfirm centro-turing.spec
#
# El .exe es el PANEL: busca el proyecto (main.py) junto a si mismo, en la carpeta
# padre, en /opt/centro-turing o en las rutas habituales, y desde ahi controla el
# monitor y los temas. No incrusta los temas (son cientos de MB): se distribuye
# junto al proyecto o se instala en una carpeta conocida.

import os

root = os.path.abspath(os.getcwd())

block_cipher = None

a = Analysis(
    ['tools/turing_center.py'],
    pathex=[root, os.path.join(root, 'tools')],
    binaries=[],
    datas=[
        ('res/icons', 'res/icons'),
        ('res/fonts/roboto', 'res/fonts/roboto'),
        ('res/fonts/jetbrains-mono/JetBrainsMono-Regular.ttf', 'res/fonts/jetbrains-mono'),
        ('res/fonts/jetbrains-mono/JetBrainsMono-Bold.ttf', 'res/fonts/jetbrains-mono'),
    ],
    hiddenimports=[
        'turing_design',
        'turing_ui2026',
        'PIL._imagingtk',
        'PIL._tkinter_finder',
        'serial.tools.list_ports',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'PyQt5', 'PySide2', 'matplotlib', 'scipy', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Centro-Turing-3.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(root, 'res', 'icons', 'centro-turing.ico'),
)
