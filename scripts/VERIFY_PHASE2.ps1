$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Write-Host "=== Zoya Phase 2 Contract Verification v2 ===" -ForegroundColor Cyan
Write-Host "Project root: $projectRoot"

$required = @(
    "backend/app/core/chat.py",
    "backend/app/memory/manager.py"
)

foreach ($path in $required) {
    if (-not (Test-Path (Join-Path $projectRoot $path))) {
        throw "Missing $path"
    }
}

Push-Location $projectRoot
try {
    python -m pytest "$projectRoot\backend\tests\test_contract_surface.py" -q
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 contract tests failed."
    }

    Write-Host "All Phase 2 contract checks passed." -ForegroundColor Green
}
finally {
    Pop-Location
}


