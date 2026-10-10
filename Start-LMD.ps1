# Local Media Downloader - arranque de uso diario (doble clic, sin comandos).
#
# Hace exactamente una cosa: deja el servicio local corriendo en esta ventana
# (el mismo proceso sirve la API y el dashboard ya compilado) y abre el
# navegador cuando esta listo. Se detiene con Ctrl+C.
#
# No cambia tu ExecutionPolicy: Start-LMD.bat lo invoca con
# -ExecutionPolicy Bypass solo para este proceso.
#
# Requisitos (solo la primera vez): uv, Node 22 + pnpm, FFmpeg, y haber
# corrido una vez `uv sync`, `pnpm install` y `pnpm build`
# (ver "First-time setup" en README.md).

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrEmpty($env:LMD_PORT)) {
  $Port = 8765
} else {
  $Port = [int]$env:LMD_PORT
}
$BaseUrl = "http://127.0.0.1:$Port"
$BannerUrl = "$BaseUrl/api/v1"

function Test-ServiceUp {
  try {
    $response = Invoke-RestMethod -Uri $BannerUrl -TimeoutSec 3
    return ($null -ne $response) -and ($response.service -eq 'local-media-downloader')
  } catch {
    return $false
  }
}

Write-Host 'Local Media Downloader - arranque local' -ForegroundColor Cyan

# 1. Si el servicio ya responde, no arrancamos otro: dos procesos en el mismo
#    puerto se pisan entre si y el navegador terminaria leyendo el viejo.
if (Test-ServiceUp) {
  Write-Host "El servicio ya esta corriendo en $BaseUrl. Abriendo el navegador..."
  if (-not $env:LMD_NO_BROWSER) {
    Start-Process "$BaseUrl/"
  }
  exit 0
}

# 2. Herramienta necesaria para correr el backend.
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host ''
  Write-Host "No se encontro 'uv' en el PATH." -ForegroundColor Red
  Write-Host 'Instalalo desde https://docs.astral.sh/uv/ , abre una terminal aqui y corre:'
  Write-Host '  uv sync'
  Write-Host 'Despues vuelve a hacer doble clic en Start-LMD.bat.'
  exit 1
}

# 3. Dashboard compilado: el backend lo sirve el mismo; sin el solo habria API.
$DistIndex = Join-Path $Root 'apps/web/dist/index.html'
if (-not (Test-Path -LiteralPath $DistIndex)) {
  if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    Write-Host ''
    Write-Host "Falta el dashboard compilado y no se encontro 'pnpm' para generarlo." -ForegroundColor Red
    Write-Host 'Instala Node.js 22+ con pnpm, abre una terminal aqui y corre:'
    Write-Host '  pnpm install'
    Write-Host '  pnpm build'
    Write-Host 'Despues vuelve a hacer doble clic en Start-LMD.bat.'
    exit 1
  }
  Write-Host 'Generando el dashboard y la extension por primera vez (pnpm build)...'
  Push-Location $Root
  try {
    & pnpm build
  } finally {
    Pop-Location
  }
  if (-not (Test-Path -LiteralPath $DistIndex)) {
    Write-Host ''
    Write-Host 'pnpm build termino pero el dashboard sigue sin aparecer.' -ForegroundColor Red
    exit 1
  }
}

# 4. El navegador se abre solo cuando el servicio ya responde (el primer
#    arranque en frio tarda unos segundos en escuchar).
$OpenJob = $null
if (-not $env:LMD_NO_BROWSER) {
  $OpenJob = Start-Job -ScriptBlock {
    param($Banner, $Home)
    for ($i = 0; $i -lt 30; $i++) {
      try {
        $r = Invoke-RestMethod -Uri $Banner -TimeoutSec 2
        if ($r.service -eq 'local-media-downloader') {
          Start-Process $Home
          break
        }
      } catch {
        # Servicio todavia arrancando; se reintenta.
      }
      Start-Sleep -Seconds 2
    }
  } -ArgumentList $BannerUrl, "$BaseUrl/"
}

try {
  Write-Host "Iniciando el servicio en $BaseUrl ..."
  Write-Host 'Deja esta ventana abierta mientras lo uses. Para detener: Ctrl+C.'
  Write-Host ''
  Push-Location $Root
  try {
    & uv run --package local-media-downloader-api python -m local_media_downloader
  } finally {
    Pop-Location
  }
} finally {
  if ($OpenJob) {
    Remove-Job -Job $OpenJob -Force -ErrorAction SilentlyContinue
  }
}
