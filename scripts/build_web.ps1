# Build the Vite React SPA in web/ into web/dist.
#   -Clean   remove node_modules first and reinstall from scratch
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts/build_web.ps1 [-Clean]
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Web  = Join-Path $Root "web"

if (-not (Test-Path -LiteralPath (Join-Path $Web "package.json"))) {
    Write-Host "! web/package.json not found - is the SPA checked out?" -ForegroundColor Yellow
    exit 1
}

Push-Location -LiteralPath $Web
try {
    $Modules = Join-Path $Web "node_modules"

    if ($Clean -and (Test-Path -LiteralPath $Modules)) {
        Write-Host "  - removing node_modules (clean build)"
        Remove-Item -LiteralPath $Modules -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $Modules)) {
        Write-Host "  + npm install"
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed (exit $LASTEXITCODE)" }
    } else {
        Write-Host "  = node_modules present - skipping install (use -Clean to force)"
    }

    Write-Host "  + npm run build"
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed (exit $LASTEXITCODE)" }

    $Index = Join-Path $Web "dist\index.html"
    if (Test-Path -LiteralPath $Index) {
        Write-Host "  = built: $Index" -ForegroundColor Green
    } else {
        throw "build finished but web/dist/index.html is missing"
    }
}
finally {
    Pop-Location
}
