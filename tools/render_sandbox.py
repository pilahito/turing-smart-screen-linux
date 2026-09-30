# -*- coding: utf-8 -*-
"""Render de prueba SIN tocar el config.yaml real ni la pantalla fisica.

Crea una copia minima del programa en tmp\\sandbox_render (main.py, library, external,
res\\fonts, res\\themes\\<temas>) con REVISION: SIMU y el tema pedido, arranca main.py
alli ~20 s y guarda screencap.png como tmp\\previews_2026\\<tema>.png
"""
import re, shutil, subprocess, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
SB = ROOT / "tmp" / "sandbox_render"
OUT = ROOT / "tmp" / "previews_2026"
PY = ROOT / "venv" / "Scripts" / "python.exe"
TEMAS = sys.argv[1:]
OUT.mkdir(parents=True, exist_ok=True)

if not (SB / "main.py").exists():
    SB.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "main.py", SB / "main.py")
    for sub in ("library", "external"):
        if (ROOT / sub).exists():
            shutil.copytree(ROOT / sub, SB / sub, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "res" / "fonts", SB / "res" / "fonts")
    for extra in ("res/icons", "res/configs"):
        if (ROOT / extra).exists():
            shutil.copytree(ROOT / extra, SB / extra)
    (SB / "res" / "themes").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "res" / "themes" / "default.yaml", SB / "res" / "themes" / "default.yaml")
    (SB / "tools").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "tools" / "pantalla-turing-ui.json", SB / "tools" / "pantalla-turing-ui.json")

base = (ROOT / "config.yaml").read_text(encoding="utf-8-sig")
base = re.sub(r"(?m)^(\s*REVISION:\s*).*$", r"\g<1>SIMU", base, count=1)
base = re.sub(r"(?m)^(\s*COM_PORT:\s*).*$", r"\g<1>AUTO", base, count=1)

res = []
for tema in TEMAS:
    dst = SB / "res" / "themes" / tema
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ROOT / "res" / "themes" / tema, dst)
    (SB / "config.yaml").write_text(re.sub(r"(?m)^(\s*THEME:\s*).*$", lambda m: m.group(1) + tema, base, count=1),
                                    encoding="utf-8")
    cap = SB / "screencap.png"
    if cap.exists():
        cap.unlink()
    p = subprocess.Popen([str(PY), "main.py"], cwd=str(SB), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    time.sleep(22)
    alive = p.poll() is None
    p.terminate()
    try:
        out = p.communicate(timeout=15)[0] or ""
    except subprocess.TimeoutExpired:
        p.kill(); out = p.communicate()[0] or ""
    (OUT / f"{tema}.log").write_text(out, encoding="utf-8")
    ok = cap.exists()
    if ok:
        shutil.copy2(cap, OUT / f"{tema}.png")
    errs = [l for l in out.splitlines() if ("ERROR" in l or "Traceback" in l or "Error" in l or "WARNING" in l)]
    print(f"=== {tema}: vivo={alive} captura={ok} avisos/errores={len(errs)}")
    for l in errs[:10]:
        print("   !", l.strip()[:220])
print("hecho")
