$ErrorActionPreference = "Stop"

Write-Host "=== Zoya Tool Result Intelligence v1 Verify ==="

$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Push-Location $projectRoot
try {
    & $python ".\features\Zoya Tool Result Intelligence v1\tests\test_tool_result_intelligence.py"
    if ($LASTEXITCODE -ne 0) { throw "Verification failed." }
}
finally { Pop-Location }

Write-Host "All Tool Result Intelligence v1 checks passed."
