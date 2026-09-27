$ErrorActionPreference = "Stop"

Write-Host "=== Zoya Tool System v1 Apply ===" -ForegroundColor Cyan

$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Support the user's current layout:
# C:\Users\Ayan\Zoya\features\Zoya Tool System\APPLY_PHASE3.ps1
# Also support placing the package directly under Zoya.
$candidates = @(
    (Split-Path -Parent $packageRoot),
    (Split-Path -Parent (Split-Path -Parent $packageRoot))
)

$projectRoot = $null
foreach ($candidate in $candidates) {
    if ((Test-Path (Join-Path $candidate "app")) -and (Test-Path (Join-Path $candidate ".venv\Scripts\python.exe"))) {
        $projectRoot = $candidate
        break
    }
}

if (-not $projectRoot) {
    throw "Could not locate the Zoya project root. Expected an app folder and .venv under a parent of the Tool System package."
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
Write-Host "Project root: $projectRoot"
Write-Host "Python: $venvPython"

$sourceToolDir = Join-Path $packageRoot "app\tools"
$sourceTestFile = Join-Path $packageRoot "tests\test_tool_registry_contract.py"
$targetToolDir = Join-Path $projectRoot "app\tools"
$targetTestsDir = Join-Path $projectRoot "tests"
$targetTestFile = Join-Path $targetTestsDir "test_tool_registry_contract.py"

foreach ($path in @($sourceToolDir, $sourceTestFile, $targetTestsDir)) {
    if (-not (Test-Path $path)) {
        throw "Required path missing: $path"
    }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $projectRoot "_phase3_backups\$timestamp"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

# Back up an existing app/tools directory before adding/replacing the additive tool layer.
if (Test-Path $targetToolDir) {
    Copy-Item -Recurse -Force $targetToolDir (Join-Path $backupRoot "app-tools")
    Write-Host "Backed up existing app\tools -> $backupRoot\app-tools"
}

# Back up the targeted contract test only if it already exists.
if (Test-Path $targetTestFile) {
    Copy-Item -Force $targetTestFile (Join-Path $backupRoot "test_tool_registry_contract.py")
    Write-Host "Backed up existing contract test -> $backupRoot\test_tool_registry_contract.py"
}

New-Item -ItemType Directory -Force -Path $targetToolDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $sourceToolDir "*") $targetToolDir
Copy-Item -Force $sourceTestFile $targetTestFile

Write-Host "Tool System files copied. Running isolated contract verification..." -ForegroundColor Yellow

$env:PYTHONPATH = $projectRoot
Push-Location $projectRoot
try {
    & $venvPython -m unittest discover -s (Join-Path $projectRoot "tests") -p "test_tool_registry_contract.py" -v
    if ($LASTEXITCODE -ne 0) {
        throw "Tool System contract verification failed. Backup is available at $backupRoot"
    }
} finally {
    Pop-Location
}

Write-Host "Zoya Tool System v1 installed and verified." -ForegroundColor Green
Write-Host "No Brain, chat, provider, research, memory, scheduler, or frontend files were modified by this installer." -ForegroundColor Green
