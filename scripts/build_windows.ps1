$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$version = (Get-Content "version.txt" -Raw).Trim()
if (-not $version) {
    throw "version.txt esta vacio."
}

$pyinstallerCmd = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstallerCmd)) {
    throw "No se encontro PyInstaller en .venv. Instala dependencias primero."
}

$chromiumRoots = Get-ChildItem "$env:LOCALAPPDATA\ms-playwright" -Directory -Filter "chromium-*" -ErrorAction SilentlyContinue
if (-not $chromiumRoots) {
    throw "No se encontro Chromium de Playwright en LOCALAPPDATA. Ejecuta '.venv\Scripts\playwright install chromium' antes del build."
}

Write-Host "Limpiando build anterior..."
Remove-Item "build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "dist\MonitorSubastas" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "dist\MonitorSubastas-win64-v$version.zip" -Force -ErrorAction SilentlyContinue

Write-Host "Generando build PyInstaller..."
& $pyinstallerCmd --clean "MonitorSubastas.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller devolvio codigo $LASTEXITCODE."
}

$distDir = Join-Path $projectRoot "dist\MonitorSubastas"
if (-not (Test-Path $distDir)) {
    throw "PyInstaller no genero dist\MonitorSubastas."
}

$readmeOut = Join-Path $distDir "LEEME-PRIMER-USO.txt"
$readmeTxt = @"
Monitor de Subastas - Build Windows v$version

Como usar:
1. Descomprimir toda la carpeta.
2. Ejecutar MonitorSubastas.exe.
3. La base local se guarda en %LOCALAPPDATA%\MonitorSubastas\data\monitor.db

Notas:
- Este build ya incluye runtime de Python y Chromium de Playwright.
- No hace falta instalar Python, Playwright ni Google Chrome.
- Si SmartScreen pregunta, usar 'Mas informacion' -> 'Ejecutar de todas formas' segun politica interna.
"@
Set-Content -Path $readmeOut -Value $readmeTxt -Encoding UTF8

$zipPath = Join-Path $projectRoot "dist\MonitorSubastas-win64-v$version.zip"
Write-Host "Empaquetando ZIP..."
Compress-Archive -Path "$distDir\*" -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Build listo:"
Write-Host "  Carpeta: $distDir"
Write-Host "  ZIP:     $zipPath"
