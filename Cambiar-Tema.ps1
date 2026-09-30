# Cambia el tema landscape 3.5" y reinicia el monitor.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$themes = @(
    @{ Name = "AyistaxNeon_H"; Desc = "ES neon rojo Ayistax - rejilla hexagonal cyberpunk" },
    @{ Name = "SynthwaveES_H"; Desc = "ES synthwave retro - sol y rejilla morado/rosa/cian" },
    @{ Name = "MatrixES_H"; Desc = "ES terminal verde Matrix" },
    @{ Name = "MinimalOscuro_H"; Desc = "ES minimal oscuro - reloj grande blanco/azul" },
    @{ Name = "HorizonES"; Desc = "ES amber/cyan - CPU GPU RAM DISCO RED" },
    @{ Name = "NocheNeon"; Desc = "ES magenta/cyan - ciudad lluvia" },
    @{ Name = "TerminalES"; Desc = "ES terminal verde fosforo" },
    @{ Name = "ConilES"; Desc = "ES playa Conil - arena y mar" },
    @{ Name = "EmberES"; Desc = "ES lava / fuego" },
    @{ Name = "HieloES"; Desc = "ES hielo" },
    @{ Name = "AtardecerES"; Desc = "ES atardecer" },
    @{ Name = "VioletaES"; Desc = "ES violeta neon" },
    @{ Name = "MinimalES"; Desc = "ES minimal oscuro" },
    @{ Name = "CircuitoES"; Desc = "ES circuito / racing" },
    @{ Name = "BosqueES"; Desc = "ES bosque" },
    @{ Name = "AdminES"; Desc = "ES administrador de tareas" },
    @{ Name = "3.5inchTheme2_H"; Desc = "Clasico 3.5 horizontal" },
    @{ Name = "SimpleBlue_H"; Desc = "Azul horizontal" },
    @{ Name = "SimpleOrange_H"; Desc = "Naranja horizontal" },
    @{ Name = "SimpleGreen_H"; Desc = "Verde horizontal" },
    @{ Name = "Cyberpunk_H"; Desc = "Cyberpunk horizontal" },
    @{ Name = "Fallout_H"; Desc = "Fallout horizontal" },
    @{ Name = "Terminal_H"; Desc = "Terminal original horizontal" },
    @{ Name = "Cyberdeck"; Desc = "Relojes radiales" },
    @{ Name = "LandscapeModernDevice35"; Desc = "Graficas servidor" },
    @{ Name = "Landscape6Grid"; Desc = "6 celdas grandes" },
    @{ Name = "LandscapeEarth"; Desc = "Tierra" },
    @{ Name = "LandscapeMagicBlue"; Desc = "Azul magico" },
    @{ Name = "CyberArasaka - Landscape"; Desc = "Cyber Arasaka" },
    @{ Name = "OnePiece1"; Desc = "One Piece" },
    @{ Name = "BigClock"; Desc = "Reloj grande" }
)

Write-Host "Temas horizontales 3.5`""
Write-Host ""
for ($i = 0; $i -lt $themes.Count; $i++) {
    Write-Host ("  {0}) {1}  -  {2}" -f ($i + 1), $themes[$i].Name, $themes[$i].Desc)
}
Write-Host ""
$sel = Read-Host "Elige numero"
$idx = [int]$sel - 1
if ($idx -lt 0 -or $idx -ge $themes.Count) {
    Write-Host "Opcion no valida"
    exit 1
}
$theme = $themes[$idx].Name

$cfg = Get-Content ".\config.yaml" -Raw
if ($cfg -match '(?m)^(\s*THEME:\s*).+$') {
    $cfg = $cfg -replace '(?m)^(\s*THEME:\s*).+$', "`${1}$theme"
} else {
    throw "No se encontro THEME en config.yaml"
}
Set-Content -Path ".\config.yaml" -Value $cfg -Encoding UTF8
Write-Host "Tema activo: $theme"
Write-Host "Reiniciando monitor..."
& ".\Iniciar.ps1"
