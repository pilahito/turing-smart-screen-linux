@echo off
rem Centro Turing: script de APAGADO de Windows (directiva de grupo local, se ejecuta como SYSTEM)
rem Apaga la pantalla Turing (brillo 0 + SCREEN_OFF) antes de que se corte la corriente.
"%~dp0..\venv\Scripts\python.exe" "%~dp0apagar_pantalla.py" --motivo=apagado-windows-gpo
exit /b 0
