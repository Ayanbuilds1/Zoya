$ErrorActionPreference = 'Stop'

Write-Host "=== Zoya Tool Execution Layer v1 Apply ===" -ForegroundColor Cyan

$featureDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = $null

$candidates = @(
    (Get-Location).Path,
    (Resolve-Path (Join-Path $featureDir '..\..')).Path
)

foreach ($candidate in $candidates) {
    if ((Test-Path (Join-Path $candidate 'app')) -and (Test-Path (Join-Path $candidate '.venv'))) {
        $projectRoot = (Resolve-Path $candidate).Path
        break
    }
}

if (-not $projectRoot) {
    throw "Could not locate Zoya project root. Run this script from C:\Users\Ayan\Zoya or keep it under features\Zoya Tool Execution Layer."
}

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "Zoya virtualenv Python not found: $python"
}

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupRoot = Join-Path $projectRoot "_tool_execution_backups\$timestamp"
New-Item -ItemType Directory -Force $backupRoot | Out-Null

$targetInit = Join-Path $projectRoot 'app\tools\__init__.py'
$targetExecution = Join-Path $projectRoot 'app\tools\execution.py'
$targetTest = Join-Path $projectRoot 'tests\test_tool_execution_layer.py'

if (-not (Test-Path (Join-Path $projectRoot 'app\tools'))) {
    throw "Existing Zoya Tool System was not found at app\tools. Install Zoya Tool System v1 first."
}

if (Test-Path $targetInit) {
    Copy-Item $targetInit (Join-Path $backupRoot '__init__.py') -Force
}

if (Test-Path $targetExecution) {
    Copy-Item $targetExecution (Join-Path $backupRoot 'execution.py') -Force
}

if (Test-Path $targetTest) {
    Copy-Item $targetTest (Join-Path $backupRoot 'test_tool_execution_layer.py') -Force
}

Copy-Item (Join-Path $featureDir 'app\tools\execution.py') $targetExecution -Force
Copy-Item (Join-Path $featureDir 'app\tools\__init__.py') $targetInit -Force
Copy-Item (Join-Path $featureDir 'tests\test_tool_execution_layer.py') $targetTest -Force

Write-Host "Execution layer files copied." -ForegroundColor Green
Write-Host "Running isolated contract verification..." -ForegroundColor Yellow

Push-Location $projectRoot
try {
    & $python -m unittest tests.test_tool_execution_layer -v
    if ($LASTEXITCODE -ne 0) {
        throw "Tool Execution Layer contract tests failed."
    }
}
finally {
    Pop-Location
}

Write-Host "Zoya Tool Execution Layer v1 installed and verified." -ForegroundColor Green
Write-Host "No Brain, chat, provider, research, memory, scheduler, or frontend files were modified by this installer." -ForegroundColor Green
