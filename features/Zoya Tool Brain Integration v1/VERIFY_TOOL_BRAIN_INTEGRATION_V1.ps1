$ErrorActionPreference = "Stop"

Write-Host "=== Zoya Tool Brain Integration v1 Verify ==="

$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Push-Location $projectRoot
try {
    & $python ".\features\Zoya Tool Brain Integration v1\tests\test_tool_brain_integration.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Verification failed."
    }
}
finally {
    Pop-Location
}

Write-Host "All Tool Brain Integration v1 checks passed."
