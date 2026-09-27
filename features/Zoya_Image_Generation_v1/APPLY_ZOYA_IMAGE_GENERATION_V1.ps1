$ErrorActionPreference = "Stop"

Write-Host "=== Zoya Image Generation Tool v1 Apply ==="

$featureRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$backupRoot = Join-Path $projectRoot "_image_generation_v1_backups"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $backupRoot $timestamp

Write-Host "Project root: $projectRoot"
Write-Host "Python: $pythonExe"

if (-not (Test-Path $pythonExe)) {
    throw "Project venv Python was not found: $pythonExe"
}

$requiredSourceFiles = @(
    (Join-Path $featureRoot "app\tools\imagegen.py"),
    (Join-Path $featureRoot "app\tools\defaults.py"),
    (Join-Path $featureRoot "app\tools\__init__.py"),
    (Join-Path $featureRoot "app\tools\execution.py"),
    (Join-Path $featureRoot "app\core\brain.py")
)

foreach ($path in $requiredSourceFiles) {
    if (-not (Test-Path $path)) {
        throw "Feature source missing: $path"
    }
}

$targetFiles = @(
    "app\tools\imagegen.py",
    "app\tools\defaults.py",
    "app\tools\__init__.py",
    "app\tools\execution.py",
    "app\core\brain.py"
)

$targetGenOffice = Join-Path $projectRoot "app\tools\genoffice.py"
$targetDefaults = Join-Path $projectRoot "app\tools\defaults.py"
$targetBrain = Join-Path $projectRoot "app\core\brain.py"
$targetExecution = Join-Path $projectRoot "app\tools\execution.py"

foreach ($path in @($targetGenOffice, $targetDefaults, $targetBrain, $targetExecution)) {
    if (-not (Test-Path $path)) {
        throw "Required project file missing: $path"
    }
}

$genOfficeText = Get-Content -Raw $targetGenOffice
$defaultsText = Get-Content -Raw $targetDefaults
$brainText = Get-Content -Raw $targetBrain
$executionText = Get-Content -Raw $targetExecution

if ($genOfficeText -notmatch '"sheet_read"' -or $genOfficeText -notmatch '"slides_read"') {
    throw "Current GenOffice adapter is not based on the verified spreadsheet/slides baseline. Aborting."
}
if ($brainText -notmatch '_deterministic_slides_read_tool_decision' -or $brainText -notmatch '_deterministic_spreadsheet_tool_decision') {
    throw "Current Brain is missing the verified spreadsheet/slides routing baseline. Aborting."
}
if ($defaultsText -notmatch 'GenOfficeTool') {
    throw "Current default tool registry is missing GenOfficeTool. Aborting."
}
if ($executionText -notmatch 'class ToolExecutor') {
    throw "Current execution layer is not the expected ToolExecutor baseline. Aborting."
}

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

foreach ($relative in $targetFiles) {
    $target = Join-Path $projectRoot $relative
    if (Test-Path $target) {
        $backup = Join-Path $backupDir $relative
        $backupParent = Split-Path -Parent $backup
        New-Item -ItemType Directory -Force -Path $backupParent | Out-Null
        Copy-Item -Force $target $backup
    }
}

foreach ($relative in $targetFiles) {
    $source = Join-Path $featureRoot $relative
    $target = Join-Path $projectRoot $relative
    $targetParent = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
    Copy-Item -Force $source $target
}

Write-Host "Installed image generation adapter, registry wiring, network allowlist, and Brain routing."
Write-Host "Backup: $backupDir"

Push-Location $projectRoot
try {
    & $pythonExe -m py_compile .\app\tools\imagegen.py .\app\tools\defaults.py .\app\tools\__init__.py .\app\tools\execution.py .\app\core\brain.py
    if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }

    $testFiles = @(
        (Join-Path $featureRoot "tests\test_imagegen_tool_v1.py"),
        (Join-Path $featureRoot "tests\test_image_generation_routing_v1.py"),
        (Join-Path $featureRoot "tests\test_registry_and_defaults_v1.py")
    )

    foreach ($testFile in $testFiles) {
        & $pythonExe -m pytest -q $testFile --disable-warnings --maxfail=1
        if ($LASTEXITCODE -ne 0) { throw "Image generation verification failed: $testFile" }
    }

    $chatPath = Join-Path $projectRoot "app\core\chat.py"
    $chatText = Get-Content -Raw $chatPath
    if ($chatText -notmatch "ToolExecutor" -or $chatText -notmatch "tool_executor") {
        throw "Current chat.py does not expose the expected ToolExecutor integration. Aborting verification."
    }

    Write-Host ""
    Write-Host "Zoya Image Generation Tool v1 installed and verified." -ForegroundColor Green
    Write-Host "Existing GenOffice spreadsheet/slides support is preserved." -ForegroundColor Green
    Write-Host "No frontend, provider, research, memory, scheduler, or database files were modified." -ForegroundColor Green
}
finally {
    Pop-Location
}
