# -*- coding: utf-8 -*-
from pathlib import Path
import os, re, sys, time, subprocess

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "venv" / "Scripts" / "python.exe"
CFG = ROOT / "config.yaml"
THEMES = ROOT / "res" / "themes"

def list_themes():
    out = []
    if not THEMES.is_dir():
        return out
    for d in sorted(THEMES.iterdir(), key=lambda p: p.name.lower()):
        y = d / "theme.yaml"
        if not y.is_file():
            continue
        text = y.read_text(encoding="utf-8", errors="replace")
        size = "3.5" in text and ('3.5"' in text or "3.5inch" in text.lower() or "3.5" in text)
        land = "landscape" in text.lower()
        if size and land:
            out.append(d.name)
    return out

def current():
    text = CFG.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(?m)^\s*THEME:\s*(.+)$", text)
    return m.group(1).strip().strip('"') if m else ""

def set_theme(name):
    text = CFG.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"(?m)^\s*THEME:\s*.+$", text):
        raise SystemExit("No hay THEME en config.yaml")
    # conserva la sangria (THEME va dentro de "config:")
    text = re.sub(r"(?m)^(\s*THEME:\s*).+$", lambda m: m.group(1) + name, text, count=1)
    CFG.write_text(text, encoding="utf-8")

def kill_monitor():
    # solo el main.py de ESTE proyecto (lanzador del venv y su proceso hijo)
    venv = str(ROOT / "venv").lower().replace("'", "''")
    ps = (
        "$m = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py*' }; "
        "$raiz = $m | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith('" + venv + "') }; "
        "$ids = @($raiz.ProcessId) + @($m | Where-Object { $raiz.ProcessId -contains $_.ParentProcessId } | ForEach-Object { $_.ProcessId }); "
        "$ids | Where-Object { $_ } | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    time.sleep(1.5)

def start_monitor():
    subprocess.Popen(
        [str(PY), "main.py"],
        cwd=str(ROOT),
        creationflags=0x08000000,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

def apply(name):
    if not (THEMES / name / "theme.yaml").is_file():
        raise SystemExit("No existe el tema: " + name)
    set_theme(name)
    kill_monitor()
    start_monitor()
    print("Tema aplicado: " + name)
    print("La pantalla usa el programa original (main.py), un solo proceso.")

if __name__ == "__main__":
    themes = list_themes()
    if len(sys.argv) > 1:
        apply(sys.argv[1])
        sys.exit(0)
    print("Tema actual:", current() or "(ninguno)")
    print("")
    print("Elige un numero, o crea una carpeta nueva en res\\themes y vuelve a abrir esto.")
    print("")
    for i, name in enumerate(themes, 1):
        mark = "  <-- ahora" if name == current() else ""
        print(f"  {i:3}) {name}{mark}")
    print("")
    raw = input("Numero (enter = salir): ").strip()
    if not raw:
        sys.exit(0)
    if not raw.isdigit() or not (1 <= int(raw) <= len(themes)):
        raise SystemExit("Numero no valido")
    apply(themes[int(raw) - 1])
