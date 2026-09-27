# Dev convenience: build the SPA if needed, then launch the Clipper desktop app.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/run.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/run.ps1 -Browser   # no native window
#   powershell -ExecutionPolicy Bypass -File scripts/run.ps1 -Clean     # rebuild web from scratch
#   powershell -ExecutionPolicy Bypass -File scripts/run.ps1 -SkipWeb   # assume web/dist is current
param(
    [switch]$Browser,
    [switch]$Clean,
    [switch]$SkipWeb
)

$ErrorActionPreference = "Stop"

$Root    = Split-Path -Parent $PSScriptRoot
$VenvPy  = Join-Path $Root ".venv\Scripts\python.exe"
$WebDist = Join-Path $Root "web\dist\index.html"
$Desktop = Join-Path $Root "app\desktop.py"
$Api     = Join-Path $Root "app\api\server.py"

if (-not (Test-Path -LiteralPath $VenvPy)) {
    Write-Host "! Python venv not found at $VenvPy" -ForegroundColor Yellow
    Write-Host "  Run first: powershell -ExecutionPolicy Bypass -File scripts/setup.ps1"
    Write-Host "             uv sync --extra ml --extra desktop"
    exit 1
}

if (-not $SkipWeb -and -not (Test-Path -LiteralPath $WebDist)) {
    Write-Host "  web/dist missing - building..."
    & (Join-Path $PSScriptRoot "build_web.ps1") -Clean:$Clean
}

if (Test-Path -LiteralPath $Desktop) {
    $moduleArgs = @("-m", "app.desktop")
    if ($Browser) { $moduleArgs += "--browser" }
} elseif (Test-Path -LiteralPath $Api) {
    Write-Host "  app.desktop missing - falling back to app.api.server (no window)"
    $moduleArgs = @("-m", "app.api.server")
} else {
    Write-Host "! Neither app/desktop.py nor app/api/server.py exists." -ForegroundColor Yellow
    exit 1
}

Write-Host "  + $VenvPy $($moduleArgs -join ' ')"
& $VenvPy @moduleArgs
exit $LASTEXITCODE
