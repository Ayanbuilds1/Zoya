$ErrorActionPreference = 'Stop'

Write-Host "=== Zoya Tool Execution Layer v1 Verify ===" -ForegroundColor Cyan

$projectRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $projectRoot 'app')) -or -not (Test-Path (Join-Path $projectRoot '.venv'))) {
    throw "Run this verifier from the Zoya project root."
}

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "Zoya virtualenv Python not found: $python"
}

Push-Location $projectRoot
try {
    & $python -m unittest tests.test_tool_execution_layer -v
    if ($LASTEXITCODE -ne 0) {
        throw "Verification failed."
    }
}
finally {
    Pop-Location
}

Write-Host "All Tool Execution Layer v1 checks passed." -ForegroundColor Green
