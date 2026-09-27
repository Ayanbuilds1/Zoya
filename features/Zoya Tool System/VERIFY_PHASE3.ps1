$ErrorActionPreference = "Stop"

Write-Host "=== Zoya Tool System v1 Verification ===" -ForegroundColor Cyan

$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = $null

$candidates = @(
    (Get-Location).Path,
    (Split-Path -Parent $packageRoot),
    (Split-Path -Parent (Split-Path -Parent $packageRoot))
)

foreach ($candidate in $candidates) {
    if ((Test-Path (Join-Path $candidate "app")) -and (Test-Path (Join-Path $candidate ".venv\Scripts\python.exe"))) {
        $projectRoot = $candidate
        break
    }
}

if (-not $projectRoot) {
    throw "Could not locate the Zoya project root. Run this verifier from Zoya root or keep it under Zoya\features\Zoya Tool System."
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$testFile = Join-Path $projectRoot "tests\test_tool_registry_contract.py"

if (-not (Test-Path $testFile)) {
    throw "Installed Tool System contract test not found: $testFile"
}

Write-Host "Project root: $projectRoot"
Write-Host "Python: $venvPython"

$env:PYTHONPATH = $projectRoot
Push-Location $projectRoot
try {
    & $venvPython -m unittest discover -s (Join-Path $projectRoot "tests") -p "test_tool_registry_contract.py" -v
    if ($LASTEXITCODE -ne 0) {
        throw "Tool System contract verification failed."
    }
} finally {
    Pop-Location
}

Write-Host "All Zoya Tool System v1 contract checks passed." -ForegroundColor Green
