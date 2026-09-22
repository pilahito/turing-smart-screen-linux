# Instala Centro Turing como programa en Windows (nivel de usuario, sin administrador).
#
#   powershell -ExecutionPolicy Bypass -File Instalar-Como-Programa.ps1
#
# Copia la aplicacion y su entorno a %LOCALAPPDATA%\Programs\CentroTuring, crea los
# accesos directos (menu Inicio y escritorio), registra la entrada en "Aplicaciones
# instaladas" y deja un desinstalador. Se instala en el perfil del usuario a proposito:
# la aplicacion guarda su config.yaml, su registro y sus capturas en su propia carpeta.

[CmdletBinding()]
param(
    [string]$Origen,
    [string]$Destino,
    [switch]$SinEscritorio
)

# Los valores por defecto se calculan aqui: $PSScriptRoot puede no estar disponible
# todavia al evaluar el bloque param.
if (-not $Origen) { $Origen = Split-Path -Parent $PSScriptRoot }
if (-not $Origen) { $Origen = (Get-Location).Path }
if (-not $Destino) { $Destino = Join-Path $env:LOCALAPPDATA 'Programs\CentroTuring' }

$ErrorActionPreference = 'Stop'
$AppNombre = 'Centro Turing'

function Paso($texto) { Write-Host "  $texto" }

# Version de la aplicacion (la del panel), con la del paquete como reserva
$VersionApp = '3.1.0'
$centro = Join-Path $Origen 'tools\turing_center.py'
if (Test-Path $centro) {
    $encontrado = Select-String -Path $centro -Pattern '^VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
    if ($encontrado) { $VersionApp = $encontrado.Matches[0].Groups[1].Value }
}

Write-Host ""
Write-Host "=== Instalando $AppNombre $VersionApp ===" -ForegroundColor Cyan
Paso "origen : $Origen"
Paso "destino: $Destino"
Write-Host ""

if (-not (Test-Path (Join-Path $Origen 'main.py'))) {
    throw "No encuentro main.py en $Origen (usa -Origen para indicar la carpeta del proyecto)"
}

# 1) Cerrar lo que este en marcha (si no, los ficheros estan bloqueados)
Write-Host "1/6 Cerrando lo que esté en marcha"
foreach ($nombre in @('Centro-Turing-3.1', 'CentroTuring', 'Centro-Turing')) {
    Get-Process -Name $nombre -ErrorAction SilentlyContinue | ForEach-Object {
        Paso "cerrando $($_.ProcessName) (PID $($_.Id))"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match 'main\.py' -and $_.CommandLine -match 'turing'
} | ForEach-Object {
    Paso "cerrando monitor (PID $($_.ProcessId))"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

# 2) Copiar la aplicacion (proyecto + entorno virtual, sin basura)
Write-Host "2/6 Copiando la aplicación y su entorno"
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$args = @($Origen, $Destino, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/R:1', '/W:1', '/XD')
foreach ($carpeta in @('dist', 'build', 'tmp', '__pycache__', '.git', 'node_modules',
                       'res\themes\--Theme examples')) {
    $args += (Join-Path $Origen $carpeta)
}
# theme_example.png son capturas de ejemplo del proyecto original (796 MB entre los
# ejemplos y estas): la aplicacion no las usa. background_original.* son copias mias.
$args += @('/XF', 'log.log', '*.pyc', 'theme_example.png', 'background_original.*')
& robocopy @args | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy falló con código $LASTEXITCODE" }

# El ejecutable del panel, con un nombre estable
$panelOrigen = Join-Path $Origen 'dist\Centro-Turing-3.1.exe'
$panelDestino = Join-Path $Destino 'Centro-Turing.exe'
if (Test-Path $panelOrigen) {
    Copy-Item $panelOrigen $panelDestino -Force
    Paso "panel instalado como Centro-Turing.exe"
} else {
    $panelDestino = Join-Path $Destino 'tools\turing_center.py'
    Paso "AVISO: no hay .exe del panel; se usará tools\turing_center.py"
}

# 3) Configuracion y lanzador
Write-Host "3/6 Preparando la configuración"
$cfgOrigen = Join-Path $Origen 'config.yaml'
$cfgDestino = Join-Path $Destino 'config.yaml'
if ((Test-Path $cfgOrigen) -and -not (Test-Path $cfgDestino)) {
    Copy-Item $cfgOrigen $cfgDestino -Force
    Paso "tu config.yaml se ha llevado a la instalación"
}
New-Item -ItemType Directory -Force -Path (Join-Path $Destino 'tmp') | Out-Null
if ($panelDestino -like '*.exe') {
    $lineaLanzador = 'start "" "%~dp0Centro-Turing.exe"'
} else {
    $lineaLanzador = 'start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0tools\turing_center.py"'
}
@"
@echo off
rem Lanzador instalado por $AppNombre $VersionApp
$lineaLanzador
"@ | Set-Content -Path (Join-Path $Destino 'Centro Turing.cmd') -Encoding ASCII

# 4) Desinstalador (se deja dentro de la instalacion)
Write-Host "4/6 Preparando el desinstalador"
$desinstalador = Join-Path $Destino 'Desinstalar Centro Turing.ps1'
@"
# Desinstala $AppNombre $VersionApp
`$ErrorActionPreference = 'SilentlyContinue'
`$AppNombre = '$AppNombre'
`$Destino = '$Destino'
Write-Host "Desinstalando `$AppNombre..."
Get-Process -Name 'Centro-Turing', 'CentroTuring', 'Centro-Turing-3.1' | Stop-Process -Force
Get-CimInstance Win32_Process | Where-Object { `$_.CommandLine -and `$_.CommandLine -match 'main\.py' -and `$_.CommandLine -match 'turing' } | ForEach-Object { Stop-Process -Id `$_.ProcessId -Force }
Start-Sleep -Seconds 2
foreach (`$carpeta in @((Join-Path `$env:APPDATA 'Microsoft\Windows\Start Menu\Programs'), [Environment]::GetFolderPath('Desktop'))) {
    Remove-Item (Join-Path `$carpeta "`$AppNombre.lnk") -Force -ErrorAction SilentlyContinue
}
Remove-Item (Join-Path `$env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\Centro Turing.cmd') -Force -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\CentroTuring' -Recurse -Force -ErrorAction SilentlyContinue
Set-Location `$env:TEMP
Remove-Item `$Destino -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "`$AppNombre desinstalado. (Tu config.yaml se ha borrado con la carpeta)"
"@ | Set-Content -Path $desinstalador -Encoding UTF8

# 5) Accesos directos + registro en "Aplicaciones instaladas"
Write-Host "5/6 Creando accesos directos y registrando en Aplicaciones instaladas"
$shell = New-Object -ComObject WScript.Shell
$carpetas = @((Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))
if (-not $SinEscritorio) { $carpetas += [Environment]::GetFolderPath('Desktop') }
foreach ($carpeta in $carpetas) {
    $ruta = Join-Path $carpeta "$AppNombre.lnk"
    $acceso = $shell.CreateShortcut($ruta)
    $acceso.TargetPath = $panelDestino
    $acceso.WorkingDirectory = $Destino
    if ($panelDestino -like '*.exe') { $acceso.IconLocation = "$panelDestino,0" }
    $acceso.Description = 'Panel de la mini pantalla USB'
    $acceso.Save()
    Paso "acceso directo: $ruta"
}
$clave = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\CentroTuring'
New-Item -Path $clave -Force | Out-Null
$tamanoKB = [int]((Get-ChildItem $Destino -Recurse -File -ErrorAction SilentlyContinue |
                   Measure-Object -Property Length -Sum).Sum / 1KB)
$valores = [ordered]@{
    DisplayName     = $AppNombre
    DisplayVersion  = $VersionApp
    Publisher       = 'pilahito'
    InstallLocation = $Destino
    UninstallString = "powershell.exe -ExecutionPolicy Bypass -File `"$desinstalador`""
    DisplayIcon     = if ($panelDestino -like '*.exe') { $panelDestino } else { Join-Path $Destino 'res\icons\centro-turing.ico' }
    NoModify        = 1
    NoRepair        = 1
}
foreach ($nombre in $valores.Keys) {
    $valor = $valores[$nombre]
    if ($valor -is [int]) {
        New-ItemProperty -Path $clave -Name $nombre -Value $valor -PropertyType DWord -Force | Out-Null
    } else {
        New-ItemProperty -Path $clave -Name $nombre -Value $valor -PropertyType String -Force | Out-Null
    }
}
New-ItemProperty -Path $clave -Name 'EstimatedSize' -Value $tamanoKB -PropertyType DWord -Force | Out-Null
Paso "registrado (tamaño ~$([Math]::Round($tamanoKB / 1024)) MB)"

# 6) Arranque automatico: se reapunta a la copia instalada si ya estaba activo
Write-Host "6/6 Arranque automático"
$autoRuta = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\Centro Turing.cmd'
if (Test-Path $autoRuta) {
    @"
@echo off
rem Arranque automatico creado por Centro Turing
start "" /min "$Destino\venv\Scripts\pythonw.exe" "$Destino\tools\lanzar.py"
"@ | Set-Content -Path $autoRuta -Encoding ASCII
    Paso "arranque automático reapuntado a la instalación"
} else {
    Paso "arranque automático: desactivado (se activa con el interruptor del panel)"
}

Write-Host ""
Write-Host "=== Listo: $AppNombre $VersionApp instalado ===" -ForegroundColor Green
Paso "Ábrelo desde el menú Inicio o el escritorio"
Paso "Desinstalar: $desinstalador"
Write-Host ""
