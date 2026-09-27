$ErrorActionPreference = "Stop"

$featureRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backupRoot = Join-Path $projectRoot "_genoffice_slides_read_v1_backups"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $backupRoot $timestamp

Write-Host "=== Zoya GenOffice Slides Read v1 Apply ==="
Write-Host "Project root: $projectRoot"
Write-Host "Python: $pythonExe"

if (-not (Test-Path $pythonExe)) {
    throw "Project venv Python was not found: $pythonExe"
}

$sourceGenOffice = Join-Path $featureRoot "app\tools\genoffice.py"
$sourceBrain = Join-Path $featureRoot "app\core\brain.py"
$targetGenOffice = Join-Path $projectRoot "app\tools\genoffice.py"
$targetBrain = Join-Path $projectRoot "app\core\brain.py"

foreach ($path in @($sourceGenOffice, $sourceBrain, $targetGenOffice, $targetBrain)) {
    if (-not (Test-Path $path)) {
        throw "Required file missing: $path"
    }
}

$sourceGenOfficeText = Get-Content -Raw $sourceGenOffice
$sourceBrainText = Get-Content -Raw $sourceBrain
if ($sourceGenOfficeText -notmatch '"sheet_read"' -or $sourceBrainText -notmatch '_deterministic_spreadsheet_tool_decision') {
    throw "Feature package is not based on the verified GenOffice Spreadsheet Read v2 baseline. Aborting."
}

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$targets = @(
    @{ Source = $sourceGenOffice; Destination = $targetGenOffice },
    @{ Source = $sourceBrain; Destination = $targetBrain }
)

foreach ($item in $targets) {
    $relative = $item.Destination.Substring($projectRoot.Length).TrimStart('\')
    $backupTarget = Join-Path $backupDir $relative
    $backupParent = Split-Path -Parent $backupTarget
    New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
    Copy-Item -Force $item.Destination $backupTarget
}

foreach ($item in $targets) {
    Copy-Item -Force $item.Source $item.Destination
}

Write-Host "Patched GenOffice slides-read routing and adapter."
Write-Host "Spreadsheet Read v2 support is preserved in the source baseline."
Write-Host "Backup: $backupDir"

Push-Location $projectRoot
try {
    & $pythonExe -m py_compile .\app\tools\genoffice.py .\app\core\brain.py
    if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }

    & $pythonExe -m pytest -q (Join-Path $featureRoot "tests\test_genoffice_slides_read_v1.py") --disable-warnings --maxfail=1
    if ($LASTEXITCODE -ne 0) { throw "GenOffice slides adapter tests failed." }

    & $pythonExe -m pytest -q (Join-Path $featureRoot "tests\test_genoffice_slides_routing_v1.py") --disable-warnings --maxfail=1
    if ($LASTEXITCODE -ne 0) { throw "Brain slides routing tests failed." }

    $chatPath = Join-Path $projectRoot "app\core\chat.py"
    $chatText = Get-Content -Raw $chatPath
    if ($chatText -notmatch "ToolExecutor" -or $chatText -notmatch "tool_executor") {
        throw "Current chat.py does not expose the expected ToolExecutor integration. Aborting verification."
    }

    Write-Host ""
    Write-Host "GenOffice Slides Read v1 installed and verified."
    Write-Host "No frontend, provider, research, memory, scheduler, defaults, or execution-layer files were modified."
}
finally {
    Pop-Location
}
