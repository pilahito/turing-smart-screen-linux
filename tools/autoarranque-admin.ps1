# autoarranque-admin.ps1 - Centro Turing
# ------------------------------------------------------------------------------
# Arranque automatico CON administrador y SIN aviso UAC en cada inicio de sesion.
# LibreHardwareMonitor (temperatura de CPU) necesita administrador.
#
# -Activar    crea 2 tareas programadas con "privilegios mas altos":
#               "Centro Turing (admin)"          al iniciar sesion -> lanzar.py --tarea
#               "Centro Turing (admin) detener"  sin disparador    -> lanzar.py --detener
#             y desactiva el arranque antiguo de la carpeta Inicio (evita 2 monitores).
# -Desactivar borra las dos tareas.
# -Iniciar    arranca ya la tarea (monitor elevado).
# Se autoeleva (UAC) una sola vez. El resultado queda en tmp\autoarranque.txt
# ------------------------------------------------------------------------------
param([switch]$Activar, [switch]$Desactivar, [switch]$Iniciar)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$resultado = Join-Path $Root "tmp\autoarranque.txt"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argumentos = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    if ($Activar) { $argumentos += "-Activar" }
    if ($Desactivar) { $argumentos += "-Desactivar" }
    if ($Iniciar) { $argumentos += "-Iniciar" }
    Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList $argumentos
    exit
}

$tarea = "Centro Turing (admin)"
$tareaParar = "Centro Turing (admin) detener"
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "tmp") | Out-Null
    if ($Desactivar) {
        foreach ($t in @($tarea, $tareaParar)) {
            Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue
        }
        [IO.File]::WriteAllText($resultado, "OK desactivado")
        exit 0
    }
    if ($Activar) {
        $pythonw = Join-Path $Root "venv\Scripts\pythonw.exe"
        if (-not (Test-Path $pythonw)) { throw "No encuentro $pythonw" }
        $lanzador = Join-Path $Root "tools\lanzar.py"
        $usuario = "$env:USERDOMAIN\$env:USERNAME"
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
        $quien = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Highest
        $accion = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$lanzador`" --tarea" -WorkingDirectory $Root
        $inicio = New-ScheduledTaskTrigger -AtLogOn -User $usuario
        Register-ScheduledTask -TaskName $tarea -Action $accion -Trigger $inicio -Settings $settings `
            -Principal $quien -Force | Out-Null
        $accionParar = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$lanzador`" --detener" -WorkingDirectory $Root
        Register-ScheduledTask -TaskName $tareaParar -Action $accionParar -Settings $settings `
            -Principal $quien -Force | Out-Null
        # Arranque antiguo (carpeta Inicio, sin admin): se desactiva para no tener DOS monitores
        $startup = [Environment]::GetFolderPath("Startup")
        foreach ($nombre in @("Centro Turing.cmd", "Centro Turing.bat", "Centro Turing.lnk")) {
            $viejo = Join-Path $startup $nombre
            if (Test-Path $viejo) { Move-Item -Force $viejo (Join-Path $Root "tmp\$nombre.desactivado") }
        }
        # HW_SENSORS: AUTO -> con admin se usa LibreHardwareMonitor (temperatura de CPU)
        $cfgPath = Join-Path $Root "config.yaml"
        if (Test-Path $cfgPath) {
            $cfg = [IO.File]::ReadAllText($cfgPath)
            $cfgNew = $cfg -replace '(?m)^(\s*HW_SENSORS:[ \t]*)\S.*$', '${1}AUTO'
            if ($cfgNew -ne $cfg) { [IO.File]::WriteAllText($cfgPath, $cfgNew, (New-Object Text.UTF8Encoding($false))) }
        }
    }
    if ($Iniciar) { Start-ScheduledTask -TaskName $tarea }
    [IO.File]::WriteAllText($resultado, "OK activado")
    exit 0
} catch {
    [IO.File]::WriteAllText($resultado, "ERROR " + $_.Exception.Message)
    exit 1
}
