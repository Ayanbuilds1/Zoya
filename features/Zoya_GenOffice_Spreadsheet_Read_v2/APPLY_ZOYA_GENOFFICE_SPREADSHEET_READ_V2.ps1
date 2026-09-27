$ErrorActionPreference = "Stop"

$featureRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backupRoot = Join-Path $projectRoot "_genoffice_spreadsheet_read_v2_backups"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $backupRoot $timestamp

Write-Host "=== Zoya GenOffice Spreadsheet Read v2 Apply ==="
Write-Host "Project root: $projectRoot"
Write-Host "Python: $pythonExe"

if (-not (Test-Path $pythonExe)) {
    throw "Project venv Python was not found: $pythonExe"
}

$targets = @(
    @{ Source = Join-Path $featureRoot "app\tools\genoffice.py"; Destination = Join-Path $projectRoot "app\tools\genoffice.py" },
    @{ Source = Join-Path $featureRoot "app\core\brain.py"; Destination = Join-Path $projectRoot "app\core\brain.py" }
)

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

foreach ($item in $targets) {
    if (-not (Test-Path $item.Source)) {
        throw "Feature source missing: $($item.Source)"
    }
    if (-not (Test-Path $item.Destination)) {
        throw "Project target missing: $($item.Destination)"
    }

    $relative = $item.Destination.Substring($projectRoot.Length).TrimStart('\')
    $backupTarget = Join-Path $backupDir $relative
    $backupParent = Split-Path -Parent $backupTarget
    New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
    Copy-Item -Force $item.Destination $backupTarget
}

foreach ($item in $targets) {
    Copy-Item -Force $item.Source $item.Destination
}

Write-Host "Patched GenOffice spreadsheet-read routing and adapter."
Write-Host "Backup: $backupDir"

Push-Location $projectRoot
try {
    & $pythonExe -m py_compile .\app\tools\genoffice.py .\app\core\brain.py
    if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }

    & $pythonExe -m pytest -q (Join-Path $featureRoot "tests\test_genoffice_spreadsheet_read_v2.py") --disable-warnings --maxfail=1
    if ($LASTEXITCODE -ne 0) { throw "GenOffice spreadsheet adapter tests failed." }

    & $pythonExe -m pytest -q (Join-Path $featureRoot "tests\test_genoffice_spreadsheet_routing_v2.py") --disable-warnings --maxfail=1
    if ($LASTEXITCODE -ne 0) { throw "Brain spreadsheet routing tests failed." }

    $chatPath = Join-Path $projectRoot "app\core\chat.py"
    $chatText = Get-Content -Raw $chatPath
    if ($chatText -notmatch "ToolExecutor" -or $chatText -notmatch "tool_executor") {
        throw "Current chat.py does not expose the expected ToolExecutor integration. Aborting verification."
    }

    Write-Host ""
    Write-Host "GenOffice Spreadsheet Read v2 installed and verified."
    Write-Host "No frontend, provider, research, memory, scheduler, defaults, or execution-layer files were modified."
}
finally {
    Pop-Location
}
