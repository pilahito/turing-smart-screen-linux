# Arreglar-Temperatura-CPU.ps1  -  Centro Turing
# La temperatura de la CPU solo se lee con administrador (LibreHardwareMonitor).
# Crea la tarea programada "Centro Turing (admin)" (inicio de sesion, privilegios
# mas altos, sin aviso UAC en cada arranque), desactiva el arranque antiguo de la
# carpeta Inicio y arranca ya el monitor elevado. Pide UAC una sola vez.
# Es lo mismo que activar "Arranque automatico" en Ajustes del Centro Turing.
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "tools\autoarranque-admin.ps1") -Activar -Iniciar
$r = Join-Path $Root "tmp\autoarranque.txt"
if (Test-Path $r) { Get-Content $r } else { "Cancelado (no se acepto el aviso de administrador)" }
Write-Host "Comprueba log.log: deberia salir 'Found LibreHardwareMonitorLib' sin aviso de administrador."
