$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

Write-Host "=== Zoya GenOffice Spreadsheet Read v2 Verify ==="

if (-not (Test-Path $pythonExe)) {
    throw "Project venv Python was not found: $pythonExe"
}

Push-Location $projectRoot
try {
    & $pythonExe -m py_compile .\app\tools\genoffice.py .\app\core\brain.py
    if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }

    if ((Get-Content -Raw .\app\tools\genoffice.py) -notmatch "sheet_read") {
        throw "GenOffice adapter does not contain sheet_read."
    }
    if ((Get-Content -Raw .\app\core\brain.py) -notmatch "_deterministic_spreadsheet_tool_decision") {
        throw "Brain does not contain deterministic spreadsheet routing."
    }
    if ((Get-Content -Raw .\app\core\chat.py) -notmatch "ToolExecutor") {
        throw "ToolExecutor integration is missing from chat.py."
    }

    Write-Host "Static integration checks passed."

    $genoffice = Get-Command genoffice -ErrorAction SilentlyContinue
    if ($genoffice) {
        genoffice --version
    }

    if (Test-Path .\tool_test\test-sheet.xlsx) {
        Write-Host ""
        Write-Host "Runtime spreadsheet smoke test:"
        genoffice sheet read ".\tool_test\test-sheet.xlsx" --json
    }

    Write-Host ""
    Write-Host "Verification complete."
}
finally {
    Pop-Location
}
