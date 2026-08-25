param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendRoot = Join-Path $repoRoot "frontend"
$backendRoot = Join-Path $repoRoot "backend"
$desktopRoot = Join-Path $repoRoot "desktop"
$frontendRuntimeRoot = Join-Path $desktopRoot "frontend-runtime"
$desktopBuild = Join-Path $desktopRoot "build"
$frontendBundle = Join-Path $desktopBuild "frontend"
$backendBundle = Join-Path $desktopBuild "backend"
$pyinstallerWork = Join-Path $desktopBuild "pyinstaller"
$distRoot = Join-Path $repoRoot "dist"
$env:COREPACK_HOME = Join-Path $repoRoot ".corepack"
$env:PNPM_HOME = Join-Path $repoRoot ".pnpm-home"
$env:npm_config_cache = Join-Path $repoRoot ".npm-cache"
$env:CI = "true"
$env:NEXT_TELEMETRY_DISABLED = "1"

function Assert-NativeSuccess([string]$step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$step failed with exit code $LASTEXITCODE"
    }
}

if ($env:MLIB_PYTHON) {
    $python = $env:MLIB_PYTHON
} elseif (Test-Path -LiteralPath (Join-Path $repoRoot ".venv\Scripts\python.exe")) {
    $python = Join-Path $repoRoot ".venv\Scripts\python.exe"
} else {
    $python = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "[1/7] Installing backend dependencies and preparing application icon"
& $python -m pip install -r (Join-Path $backendRoot "requirements-desktop.txt")
Assert-NativeSuccess "Backend dependency installation"
if (-not $SkipTests) {
    & $python -m pip install -r (Join-Path $backendRoot "requirements-dev.txt")
    Assert-NativeSuccess "Backend test dependency installation"
}
& $python (Join-Path $repoRoot "scripts\generate_icon.py")
Assert-NativeSuccess "Icon generation"

Write-Host "[2/7] Installing frontend dependencies"
Push-Location $frontendRoot
try {
    & corepack pnpm install --frozen-lockfile
    Assert-NativeSuccess "Frontend dependency installation"
    if (-not $SkipTests) {
        & corepack pnpm typecheck
        Assert-NativeSuccess "Frontend typecheck"
        & corepack pnpm lint
        Assert-NativeSuccess "Frontend lint"
    }
    $env:BACKEND_INTERNAL_URL = "http://127.0.0.1:9"
    $env:NODE_ENV = "production"
    & corepack pnpm build
    Assert-NativeSuccess "Frontend production build"
} finally {
    Pop-Location
    Remove-Item Env:NODE_ENV -ErrorAction SilentlyContinue
}

Write-Host "[3/7] Preparing Next.js standalone bundle"
if (Test-Path -LiteralPath $frontendBundle) {
    Remove-Item -LiteralPath $frontendBundle -Recurse -Force
}
New-Item -ItemType Directory -Path $frontendBundle -Force | Out-Null
$standaloneRoot = Join-Path $frontendRoot ".next\standalone"
if (-not (Test-Path -LiteralPath (Join-Path $standaloneRoot "server.js"))) {
    throw "Next.js standalone server.js was not generated"
}
Copy-Item -LiteralPath (Join-Path $standaloneRoot "server.js") -Destination (Join-Path $frontendBundle "server.js") -Force
Copy-Item -LiteralPath (Join-Path $standaloneRoot ".next") -Destination (Join-Path $frontendBundle ".next") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $frontendRuntimeRoot "package.json") -Destination (Join-Path $frontendBundle "package.json") -Force
Copy-Item -LiteralPath (Join-Path $frontendRuntimeRoot "pnpm-lock.yaml") -Destination (Join-Path $frontendBundle "pnpm-lock.yaml") -Force
Copy-Item -LiteralPath (Join-Path $frontendRuntimeRoot "pnpm-workspace.yaml") -Destination (Join-Path $frontendBundle "pnpm-workspace.yaml") -Force
$staticBundle = Join-Path $frontendBundle ".next\static"
if (Test-Path -LiteralPath $staticBundle) {
    Remove-Item -LiteralPath $staticBundle -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $frontendRoot ".next\static") -Destination (Join-Path $frontendBundle ".next\static") -Recurse -Force
if (Test-Path -LiteralPath (Join-Path $frontendRoot "public")) {
    Copy-Item -LiteralPath (Join-Path $frontendRoot "public") -Destination (Join-Path $frontendBundle "public") -Recurse -Force
}
Push-Location $frontendBundle
try {
    & corepack pnpm install --prod --frozen-lockfile --config.node-linker=hoisted --offline --ignore-scripts
    Assert-NativeSuccess "Standalone frontend runtime installation"
} finally {
    Pop-Location
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendBundle "node_modules\next\package.json"))) {
    throw "Standalone frontend runtime dependencies were not installed"
}

Write-Host "[4/7] Building hidden FastAPI sidecar"
if (-not $SkipTests) {
    Push-Location $backendRoot
    try {
        & $python -m pytest
        Assert-NativeSuccess "Backend tests"
        & $python -m ruff check app tests desktop_backend.py
        Assert-NativeSuccess "Backend lint"
    } finally {
        Pop-Location
    }
}
if (Test-Path -LiteralPath $backendBundle) {
    Remove-Item -LiteralPath $backendBundle -Recurse -Force
}
if (Test-Path -LiteralPath $pyinstallerWork) {
    Remove-Item -LiteralPath $pyinstallerWork -Recurse -Force
}
& $python -m PyInstaller --noconfirm --clean --distpath $desktopBuild --workpath $pyinstallerWork (Join-Path $backendRoot "mlib_backend.spec")
Assert-NativeSuccess "Backend executable build"
if (-not (Test-Path -LiteralPath (Join-Path $backendBundle "mlib-backend.exe"))) {
    throw "PyInstaller did not create mlib-backend.exe"
}

Write-Host "[5/7] Installing desktop packaging dependencies"
Push-Location $desktopRoot
try {
    if (Test-Path -LiteralPath (Join-Path $desktopRoot "package-lock.json")) {
        & npm ci
        Assert-NativeSuccess "Desktop dependency installation"
    } else {
        & npm install
        Assert-NativeSuccess "Desktop dependency installation"
    }
} finally {
    Pop-Location
}

Write-Host "[6/7] Creating NSIS installer"
if (Test-Path -LiteralPath $distRoot) {
    Remove-Item -LiteralPath $distRoot -Recurse -Force
}
Push-Location $desktopRoot
try {
    & npm run dist
    Assert-NativeSuccess "NSIS installer build"
} finally {
    Pop-Location
}

Write-Host "[7/7] Verifying artifacts"
$installer = Get-ChildItem -LiteralPath $distRoot -Filter "mLib-Setup-*-x64.exe" | Select-Object -First 1
if (-not $installer -or $installer.Length -lt 1MB) {
    throw "Windows installer was not created or is unexpectedly small"
}
$hash = Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256
$checksumPath = "$($installer.FullName).sha256"
[System.IO.File]::WriteAllText($checksumPath, "$($hash.Hash) *$($installer.Name)`n", [System.Text.UTF8Encoding]::new($false))
if ($env:MLIB_GITHUB_REPOSITORY) {
    $updateManifest = Join-Path $distRoot "latest.yml"
    $blockmap = "$($installer.FullName).blockmap"
    if (-not (Test-Path -LiteralPath $updateManifest)) {
        throw "Updater metadata latest.yml was not created"
    }
    if (-not (Test-Path -LiteralPath $blockmap)) {
        throw "Updater blockmap was not created"
    }
}
Write-Host "Created: $($installer.FullName)"
Write-Host "SHA256: $($hash.Hash)"
Write-Host "Checksum: $checksumPath"
