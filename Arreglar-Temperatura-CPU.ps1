# Arreglar-Temperatura-CPU.ps1  —  Centro Turing
# ------------------------------------------------------------------------------
# La temperatura de la CPU solo se puede leer con permisos de administrador
# (LibreHardwareMonitor necesita un driver de kernel). Sin admin, el tema muestra
# la TEMP en blanco.
#
# Este script crea una TAREA PROGRAMADA que arranca el monitor al iniciar sesion
# con privilegios maximos. Asi la temperatura funciona siempre, sin que Windows
# pida UAC cada vez.
#
# USO: clic derecho sobre este archivo -> "Ejecutar con PowerShell".
#      (Se elevara solo pidiendo UAC una unica vez.)
# ------------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- 1) Autoelevacion ---------------------------------------------------------
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Pidiendo permisos de administrador..."
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`""
    )
    exit
}

Write-Host "=== Arreglando la temperatura de CPU (Centro Turing) ===" -ForegroundColor Cyan

# --- 2) Asegurar HW_SENSORS: AUTO en config.yaml -------------------------------
$cfgPath = Join-Path $Root "config.yaml"
if (Test-Path $cfgPath) {
    $cfg = Get-Content $cfgPath -Raw
    $cfgNew = $cfg -replace '(?m)^(\s*HW_SENSORS:\s*).+$', '${1}AUTO'
    if ($cfgNew -ne $cfg) {
        # UTF-8 sin BOM (Set-Content -Encoding UTF8 de PowerShell 5 anade BOM)
        [IO.File]::WriteAllText($cfgPath, $cfgNew, (New-Object Text.UTF8Encoding($false)))
        Write-Host "config.yaml: HW_SENSORS -> AUTO"
    }
}

# --- 3) Desactivar el arranque automatico antiguo (no elevado) ------------------
# Si siguiera activo, arrancarian DOS monitores (uno sin admin) y se pelearian por
# el puerto COM.
$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
foreach ($nombre in @("Centro Turing.cmd", "Centro Turing.bat", "Centro Turing.lnk")) {
    $viejo = Join-Path $startup $nombre
    if (Test-Path $viejo) {
        Rename-Item -Path $viejo -NewName "$nombre.desactivado" -Force
        Write-Host "Arranque antiguo desactivado: $nombre"
    }
}

# --- 4) Crear la tarea programada ----------------------------------------------
$pythonw = Join-Path $Root "venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = Join-Path $Root "venv\Scripts\python.exe" }
if (-not (Test-Path $pythonw)) { throw "No encuentro el Python del proyecto en venv\Scripts" }

$taskName = "Centro Turing (admin)"
$usuario  = "$env:USERDOMAIN\$env:USERNAME"

# Se arranca con el lanzador (espera al puerto COM y avisa si falla), no main.py a pelo
$lanzador  = Join-Path $Root "tools\lanzar.py"
$action    = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$lanzador`" --arranque" -WorkingDirectory $Root
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                                          -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
                                          -MultipleInstances IgnoreNew
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
                       -Settings $settings -Principal $taskPrincipal -Force | Out-Null
Write-Host "Tarea programada creada: '$taskName' (privilegios maximos, al iniciar sesion)."

# --- 5) Reiniciar el monitor ya elevado ----------------------------------------
# (Antes se mataba aqui CUALQUIER main.py del equipo, tambien otros programas.
#  lanzar.py ya cierra solo el monitor anterior de esta carpeta.)

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "LISTO. El monitor esta arrancando con permisos de administrador." -ForegroundColor Green
Write-Host "En unos segundos la TEMP de CPU deberia aparecer en la pantalla."
Write-Host ""
Write-Host "Para comprobarlo, mira el log: $(Join-Path $Root 'log.log')"
Write-Host "Deberia decir 'Found LibreHardwareMonitorLib' SIN el error de administrador."
Write-Host ""
Write-Host "Para deshacerlo: Desinstalar -> schtasks /Delete /TN `"Centro Turing (admin)`" /F"
