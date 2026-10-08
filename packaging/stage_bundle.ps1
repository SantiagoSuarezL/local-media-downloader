#Requires -Version 5.1
<#
  Stage third-party binaries into the PyInstaller onedir bundle.

  Run AFTER `pnpm build` (web dist) and the PyInstaller build from apps/api:
    uv run --extra build pyinstaller lmd.spec --noconfirm `
      --distpath ../../dist --workpath ../../build/lmd

  Then from the repo root:
    powershell -ExecutionPolicy Bypass -File packaging/stage_bundle.ps1

  Sources (override with environment variables):
    LMD_DENO_EXE      real deno.exe (default: pnpm-managed Deno under node_modules)
    LMD_FFMPEG_EXE    ffmpeg.exe  (default: first `ffmpeg` on PATH)
    LMD_FFPROBE_EXE   ffprobe.exe (default: first `ffprobe` on PATH)
#>
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Bundle = Join-Path $RepoRoot "dist\LocalMediaDownloader"
if (-not (Test-Path -LiteralPath $Bundle)) {
    throw "bundle missing: $Bundle (build it first, see header comment)"
}
$Bin = Join-Path $Bundle "bin"
New-Item -ItemType Directory -Path $Bin -Force | Out-Null

function Find-DefaultDeno {
    $found = Get-ChildItem -Recurse -Filter deno.exe `
        (Join-Path $RepoRoot "node_modules\.pnpm") -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    return $found
}
function Find-OnPath([string]$name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd -or $cmd.Source -like "*.ps1") { return $null }
    $src = $cmd.Source
    # Scoop shims are ~100 KB proxies; stage the real binary instead.
    # (ffprobe ships inside the ffmpeg app, not its own.)
    if ($src -like "*\shims\*") {
        $real = Join-Path $HOME "scoop\apps\$name\current\bin\$name.exe"
        if (Test-Path -LiteralPath $real) { return $real }
        $sibling = Join-Path $HOME "scoop\apps\ffmpeg\current\bin\$name.exe"
        if (Test-Path -LiteralPath $sibling) { return $sibling }
    }
    return $src
}

$DenoExe = $env:LMD_DENO_EXE
if (-not $DenoExe) { $DenoExe = Find-DefaultDeno }
$FfmpegExe = $env:LMD_FFMPEG_EXE
if (-not $FfmpegExe) { $FfmpegExe = Find-OnPath "ffmpeg" }
$FfprobeExe = $env:LMD_FFPROBE_EXE
if (-not $FfprobeExe) { $FfprobeExe = Find-OnPath "ffprobe" }

foreach ($src in @($DenoExe, $FfmpegExe, $FfprobeExe)) {
    if (-not $src -or -not (Test-Path -LiteralPath $src)) {
        throw "binary not found: '$src' (set LMD_DENO_EXE / LMD_FFMPEG_EXE / LMD_FFPROBE_EXE)"
    }
}
Copy-Item -LiteralPath $DenoExe -Destination (Join-Path $Bin "deno.exe") -Force
Copy-Item -LiteralPath $FfmpegExe -Destination (Join-Path $Bin "ffmpeg.exe") -Force
Copy-Item -LiteralPath $FfprobeExe -Destination (Join-Path $Bin "ffprobe.exe") -Force
Copy-Item -LiteralPath (Join-Path $RepoRoot "THIRD_PARTY_NOTICES.md") -Destination $Bundle -Force

Get-ChildItem -LiteralPath $Bin | Format-Table Name, Length
"staged into $Bundle"
