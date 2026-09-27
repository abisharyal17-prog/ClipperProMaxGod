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
#   -Token <pat>         install from a private repo (or set CLIPPER_GH_TOKEN)
#   -LocalSource <path>  install from a local checkout instead of GitHub (dev/testing)
#   -Extras "ml"         comma-separated uv extras (use "" to skip the ML stack)
#   -NoStart             install but don't launch the engine
#
param(
    [string]$Repo  = $(if ($env:CLIPPER_REPO) { $env:CLIPPER_REPO } else { "abisharyal17-prog/ClipperProMaxGod" }),
    [string]$Branch = "main",
    [string]$Dir   = $(Join-Path $env:LOCALAPPDATA "Clipper"),
    [string]$AppUrl = $env:CLIPPER_APP_URL,
    [string]$Extras = "ml",
    [string]$Token = $env:CLIPPER_GH_TOKEN,
    [string]$LocalSource = $env:CLIPPER_LOCAL_SOURCE,
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
if ($LocalSource) {
    $src = (Resolve-Path -LiteralPath $LocalSource).Path
    Say "+ copying local source: $src"
    New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
    # Exclude heavy / generated dirs (robocopy /XD matches these names anywhere).
    $exclude = @(".git", ".venv", "bin", ".uv-cache", ".pythons", "data",
                 "node_modules", "dist", "__pycache__", ".ruff_cache", ".pytest_cache",
                 ".ultralytics")
    & robocopy $src $AppDir /E /NFL /NDL /NJH /NJS /NP /XD $exclude /XF *.pyc | Out-Null
    if ($LASTEXITCODE -ge 8) { Fail "copying local source failed (robocopy $LASTEXITCODE)" }
    $global:LASTEXITCODE = 0
    Say "= source ready"
} elseif ($haveSource -and -not $Update) {
    Say "= using existing checkout at $AppDir"
} else {
    $zip = Join-Path $env:TEMP "clipper-src.zip"
    $headers = @{ "User-Agent" = "clipper-installer" }
    if ($Token) {
        $headers["Authorization"] = "Bearer $Token"
        $src = "https://api.github.com/repos/$Repo/zipball/$Branch"
        Say "+ downloading $Repo@$Branch (private, token)"
    } else {
        $src = "https://codeload.github.com/$Repo/zip/refs/heads/$Branch"
        Say "+ downloading $Repo@$Branch"
    }
    Remove-Item -Force $zip -ErrorAction SilentlyContinue
    Invoke-WebRequest -Uri $src -OutFile $zip -Headers $headers -UseBasicParsing
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
# Respect a pre-set uv cache / python dir (lets CI and dev reuse a warm cache).
if (-not $env:UV_PYTHON_INSTALL_DIR) { $env:UV_PYTHON_INSTALL_DIR = Join-Path $AppDir ".pythons" }
if (-not $env:UV_CACHE_DIR) { $env:UV_CACHE_DIR = Join-Path $AppDir ".uv-cache" }
$uv = Join-Path $Bin "uv.exe"
# NB: PowerShell variables are case-insensitive - never name this `$extras`, which
# would clobber the `$Extras` parameter.
$extraArgs = @()
foreach ($extra in ($Extras -split ",")) { if ($extra.Trim()) { $extraArgs += @("--extra", $extra.Trim()) } }
Say "+ uv sync $($extraArgs -join ' ')  (first run downloads PyTorch - can take a while)"
& $uv sync --directory $AppDir @extraArgs
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
