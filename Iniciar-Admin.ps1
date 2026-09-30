# Arranca con LibreHardwareMonitor (temperaturas CPU reales). Pide administrador.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`""
    )
    exit
}

$cfgPath = Join-Path $Root "config.yaml"
$cfg = Get-Content $cfgPath -Raw
$cfgNew = $cfg -replace '(?m)^(\s*HW_SENSORS:\s*).+$', '${1}AUTO'
if ($cfgNew -ne $cfg) {
    # UTF-8 sin BOM (Set-Content -Encoding UTF8 de PowerShell 5 anade BOM)
    [IO.File]::WriteAllText($cfgPath, $cfgNew, (New-Object Text.UTF8Encoding($false)))
}

# Antes buscaba 'turing-smart-screen-python\main.py' (ruta antigua): no cerraba el
# monitor de esta carpeta y quedaban DOS peleando por el COM. lanzar.py cierra
# solo el monitor de esta carpeta y arranca el nuevo.
$py = Join-Path $Root "venv\Scripts\pythonw.exe"
if (-not (Test-Path $py)) { $py = Join-Path $Root "venv\Scripts\python.exe" }
Start-Process -FilePath $py -ArgumentList "`"$(Join-Path $Root 'tools\lanzar.py')`"" -WorkingDirectory $Root -WindowStyle Hidden
Write-Host "Pantalla Turing en marcha con sensores LHM (admin)."
