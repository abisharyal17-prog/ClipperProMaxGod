# Clipper health check (Windows PowerShell 5.1).
# Every check is isolated: a missing optional dependency degrades to a warning
# and never aborts the script. No dependency is installed by this script.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/doctor.ps1

$ErrorActionPreference = "Continue"

$Root   = Split-Path -Parent $PSScriptRoot
$Bin    = Join-Path $Root "bin"
$VenvPy = Join-Path $Root ".venv\Scripts\python.exe"

function Write-Section([string]$Title) { Write-Host ""; Write-Host "== $Title ==" }
function Write-Ok([string]$Msg)   { Write-Host "  [ ok ] $Msg" }
function Write-Warn([string]$Msg) { Write-Host "  [ -- ] $Msg" -ForegroundColor Yellow }
function Write-Fail([string]$Msg) { Write-Host "  [fail] $Msg" -ForegroundColor Red }

function Test-Tool {
    param([string]$Name, [string]$LocalExe, [string]$VersionArg)
    try {
        $exe = Join-Path $Bin $LocalExe
        if (-not (Test-Path -LiteralPath $exe)) {
            $cmd = Get-Command $Name -ErrorAction Stop
            $exe = $cmd.Source
        }
        if (-not $exe) { throw "not found on PATH" }
        $line = (& $exe $VersionArg 2>&1 | Select-Object -First 1)
        Write-Ok "$Name : $line"
    } catch {
        Write-Warn "$Name : unavailable ($($_.Exception.Message))"
    }
}

function Test-Python {
    param([string]$Label, [string]$Code)
    try {
        $output = @(& $VenvPy -c $Code 2>&1)
        if ($LASTEXITCODE -ne 0) {
            $tail = ($output | Where-Object { $_ -match '\S' } | Select-Object -Last 1)
            Write-Warn "$Label : unavailable ($tail)"
        } else {
            Write-Ok "$Label : $($output -join ' ')"
        }
    } catch {
        Write-Warn "$Label : $($_.Exception.Message)"
    }
}

Write-Host "Clipper doctor"
Write-Host "root: $Root"

Write-Section "Python / venv"
if (Test-Path -LiteralPath $VenvPy) {
    Test-Python "python" "import sys; print(sys.version.split()[0], sys.executable)"
} else {
    Write-Fail "venv python missing at $VenvPy"
    Write-Host "        run scripts/setup.ps1, then: uv sync --extra ml --extra desktop"
}

Write-Section "Media toolchain"
Test-Tool "ffmpeg"  "ffmpeg.exe"  "-version"
Test-Tool "ffprobe" "ffprobe.exe" "-version"
Test-Tool "yt-dlp"  "yt-dlp.exe"  "--version"

Write-Section "ML runtime"
Test-Python "torch" "import torch; print('torch', torch.__version__, '| cuda', torch.cuda.is_available(), '|', torch.version.cuda)"
Test-Python "whisper" "import app; import ctranslate2, faster_whisper; print('faster-whisper', faster_whisper.__version__, '| ctranslate2', ctranslate2.__version__, '| cuda devices', ctranslate2.get_cuda_device_count())"
Test-Python "ultralytics" "import ultralytics; print('ultralytics', ultralytics.__version__)"
Test-Python "pywebview" "import webview; print('pywebview', getattr(webview, '__version__', 'installed'))"

Write-Section "Assets"
foreach ($item in @(
    @{ Label = "fonts (.ttf)"; Path = (Join-Path $Root "assets\fonts"); Filter = "*.ttf" },
    @{ Label = "LUTs (.cube)"; Path = (Join-Path $Root "assets\luts");  Filter = "*.cube" },
    @{ Label = "music";        Path = (Join-Path $Root "assets\music"); Filter = "*.mp3" }
)) {
    try {
        if (Test-Path -LiteralPath $item.Path) {
            $count = @(Get-ChildItem -LiteralPath $item.Path -Filter $item.Filter -File -ErrorAction SilentlyContinue).Count
            Write-Ok "$($item.Label) : $count file(s) in $($item.Path)"
        } else {
            Write-Warn "$($item.Label) : folder missing ($($item.Path))"
        }
    } catch {
        Write-Warn "$($item.Label) : $($_.Exception.Message)"
    }
}

Write-Section "Web UI"
try {
    $index = Join-Path $Root "web\dist\index.html"
    if (Test-Path -LiteralPath $index) {
        Write-Ok "web/dist : built ($index)"
    } else {
        Write-Warn "web/dist : not built - run scripts/build_web.ps1"
    }
} catch {
    Write-Warn "web/dist : $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Done."
