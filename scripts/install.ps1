# Clipper engine installer / launcher (Windows PowerShell 5.1)
#
# One command, run once. It downloads the app, the media toolchain and the Python
# runtime into a per-user folder, installs the dependencies, then starts the local
# engine and opens the Clipper UI (pairing the browser automatically).
#
# Running it again is safe and fast: an existing install is reused and the engine
# simply starts (or the browser re-opens if the engine is already running).
#
#   irm https://raw.githubusercontent.com/abisharyal17-prog/ClipperProMaxGod/main/scripts/install.ps1 | iex
#
# Parameters (optional):
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Repo owner/name -AppUrl https://clipper.vercel.app
#
param(
    [string]$Repo  = $(if ($env:CLIPPER_REPO) { $env:CLIPPER_REPO } else { "abisharyal17-prog/ClipperProMaxGod" }),
    [string]$Branch = "main",
    [string]$Dir   = $(Join-Path $env:LOCALAPPDATA "Clipper"),
    [string]$AppUrl = $env:CLIPPER_APP_URL,
    [string]$Extras = "ml",
    [switch]$Update,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Port    = 8765
$EngineUrl = "http://127.0.0.1:$Port"
$AppDir  = Join-Path $Dir "repo"
$VenvPy  = Join-Path $AppDir ".venv\Scripts\python.exe"
$Bin     = Join-Path $AppDir "bin"

function Say($msg)  { Write-Host "  $msg" }
function Step($msg) { Write-Host ""; Write-Host "== $msg ==" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "  x $msg" -ForegroundColor Red; exit 1 }

function Test-Port([int]$p) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $p); $c.Close(); return $true }
    catch { return $false }
}

function Get-File($url, $out) {
    if (Test-Path -LiteralPath $out) { return }
    $dir = Split-Path -Parent $out
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
}

Write-Host ""
Write-Host "Clipper - local video engine" -ForegroundColor White
Write-Host "install dir: $Dir"

# --- already running? just (re)open the browser ---------------------------
if (Test-Port $Port) {
    Step "Engine already running"
    $token = ""
    if (Test-Path -LiteralPath $VenvPy) {
        try { $token = (& $VenvPy -c "from app import auth; print(auth.ensure_token())" 2>$null).Trim() } catch { $token = "" }
    }
    $target = if ($AppUrl) { $AppUrl } else { $EngineUrl }
    if ($token) { $target = "$target#token=$token" }
    Say "opening $target"
    Start-Process $target | Out-Null
    exit 0
}

# --- 1. fetch the source --------------------------------------------------
Step "Source code"
$haveSource = Test-Path -LiteralPath (Join-Path $AppDir "pyproject.toml")
if ($haveSource -and -not $Update) {
    Say "= using existing checkout at $AppDir"
} else {
    if ($Repo -eq "your-org/clipper") {
        Warn "This script still has a placeholder repo. Re-run with -Repo owner/name"
        Warn "or set `$env:CLIPPER_REPO. Continuing will likely fail to download."
    }
    $zip = Join-Path $env:TEMP "clipper-src.zip"
    $src = "https://codeload.github.com/$Repo/zip/refs/heads/$Branch"
    Say "+ downloading $Repo@$Branch"
    Remove-Item -Force $zip -ErrorAction SilentlyContinue
    Get-File $src $zip
    $tmp = Join-Path $env:TEMP "clipper-src-extract"
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
    Copy-Item -Path (Join-Path $inner.FullName "*") -Destination $AppDir -Recurse -Force
    Remove-Item -Force $zip -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    Say "= source ready"
}

# --- 2. toolchain (uv + ffmpeg + yt-dlp + venv) ---------------------------
if (-not (Test-Path -LiteralPath $VenvPy)) {
    Step "Toolchain"
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $AppDir "scripts\setup.ps1")
    if ($LASTEXITCODE -ne 0) { Fail "toolchain setup failed" }
} else {
    Step "Toolchain"
    Say "= already installed"
}

# --- 3. Python dependencies ----------------------------------------------
Step "Python dependencies"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $AppDir ".pythons"
$env:UV_CACHE_DIR          = Join-Path $AppDir ".uv-cache"
$uv = Join-Path $Bin "uv.exe"
$extras = @()
foreach ($extra in ($Extras -split ",")) { if ($extra.Trim()) { $extras += @("--extra", $extra.Trim()) } }
Say "+ uv sync $($extras -join ' ')  (first run downloads PyTorch - can take a while)"
& $uv sync --directory $AppDir @extras
if ($LASTEXITCODE -ne 0) { Fail "dependency install failed" }

# --- 4. models ------------------------------------------------------------
Step "Models"
$models = Join-Path $AppDir "assets\models"
Get-File "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" (Join-Path $models "face_detection_yunet_2023mar.onnx")
Get-File "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt" (Join-Path $models "yolov8n.pt")
Say "= face + person models ready"

# --- 5. done --------------------------------------------------------------
Step "Ready"
Say "engine: $EngineUrl"
Say "source: $AppDir"
Say "token : (printed below when the engine starts)"

$token = (& $VenvPy -c "from app import auth; print(auth.ensure_token())").Trim()
$target = if ($AppUrl) { $AppUrl } else { $EngineUrl }
if ($token) { $target = "$target#token=$token" }

if ($NoStart) {
    Say ""
    Say "Start later with the same one-line command, or:"
    Say "  `"$VenvPy`" -m app.api.server"
    exit 0
}

Say "opening $target"
Start-Process $target | Out-Null
Say "leave this window open while you use Clipper (Ctrl+C to stop)"
Write-Host ""

Set-Location -LiteralPath $AppDir
& $VenvPy -m app.api.server
