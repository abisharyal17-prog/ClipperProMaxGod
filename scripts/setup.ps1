# Clipper self-contained toolchain setup (Windows PowerShell 5.1)
# Downloads uv + ffmpeg + yt-dlp into .\bin, then creates a Python 3.12 venv.
# Nothing is installed system-wide.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root = Split-Path -Parent $PSScriptRoot
$Bin  = Join-Path $Root "bin"
New-Item -ItemType Directory -Path $Bin -Force | Out-Null

function Get-File($Url, $Out) {
    if (Test-Path -LiteralPath $Out) { Write-Host "  = exists: $(Split-Path $Out -Leaf)"; return }
    Write-Host "  + downloading $(Split-Path $Out -Leaf)"
    Invoke-WebRequest -Uri $Url -OutFile $Out -UseBasicParsing
}

# --- uv -------------------------------------------------------------------
$uvExe = Join-Path $Bin "uv.exe"
if (-not (Test-Path -LiteralPath $uvExe)) {
    $tmp = Join-Path $env:TEMP "uv.zip"
    Get-File "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" $tmp
    $dst = Join-Path $env:TEMP "uv_extract"
    Remove-Item -Recurse -Force $dst -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $tmp -DestinationPath $dst -Force
    Get-ChildItem -Path $dst -Recurse -Filter "uv*.exe" | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $Bin $_.Name) -Force
    }
    Remove-Item -Force $tmp -ErrorAction SilentlyContinue
} else { Write-Host "  = exists: uv.exe" }

# --- ffmpeg / ffprobe -----------------------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path $Bin "ffmpeg.exe"))) {
    $tmp = Join-Path $env:TEMP "ffmpeg.zip"
    Get-File "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $tmp
    $dst = Join-Path $env:TEMP "ffmpeg_extract"
    Remove-Item -Recurse -Force $dst -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $tmp -DestinationPath $dst -Force
    Get-ChildItem -Path $dst -Recurse -Include "ffmpeg.exe","ffprobe.exe" | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $Bin $_.Name) -Force
    }
    Remove-Item -Force $tmp -ErrorAction SilentlyContinue
} else { Write-Host "  = exists: ffmpeg.exe" }

# --- yt-dlp ---------------------------------------------------------------
Get-File "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" (Join-Path $Bin "yt-dlp.exe")

# --- Python 3.12 venv via uv ---------------------------------------------
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root ".pythons"
$env:UV_CACHE_DIR          = Join-Path $Root ".uv-cache"
Write-Host "  + installing Python 3.12 (uv-managed, project-local)"
& $uvExe python install 3.12
Write-Host "  + creating .venv"
& $uvExe venv --python 3.12 (Join-Path $Root ".venv")

Write-Host ""
Write-Host "Toolchain ready:"
& (Join-Path $Bin "ffmpeg.exe") -version 2>&1 | Select-Object -First 1
& (Join-Path $Bin "yt-dlp.exe") --version
& (Join-Path $Root ".venv\Scripts\python.exe") --version
