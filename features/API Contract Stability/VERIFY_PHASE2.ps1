$ErrorActionPreference = 'Stop'

$phase2Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $phase2Root

Write-Host "=== Zoya Phase 2 Contract Verification v3 ===" -ForegroundColor Cyan
Write-Host "Project root: $projectRoot"

$required = @(
    "app/core/chat.py",
    "app/memory/manager.py",
    "app/api/routes/chat.py"
)

foreach ($relativePath in $required) {
    $fullPath = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Missing required file: $relativePath"
    }
}

# Prefer Zoya's project venv so the verifier never silently switches to a
# global Python installation. Fall back only when the venv does not exist.
$pythonCandidates = @(
    (Join-Path $projectRoot ".venv\Scripts\python.exe"),
    (Join-Path $projectRoot "venv\Scripts\python.exe")
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $pythonExe = $pythonCommand.Source
    }
}

if (-not $pythonExe) {
    throw "No Python interpreter found."
}

Write-Host "Python: $pythonExe"

Push-Location $projectRoot
try {
    # No pytest dependency. This is deliberately standard-library-only.
    & $pythonExe "$phase2Root\tests\contract_check.py" $projectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 contract checks failed."
    }

    Write-Host "All Phase 2 contract checks passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
