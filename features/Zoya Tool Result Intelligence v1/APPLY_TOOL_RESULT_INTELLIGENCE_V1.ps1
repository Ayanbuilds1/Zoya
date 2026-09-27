$ErrorActionPreference = "Stop"

Write-Host "=== Zoya Tool Result Intelligence v1 Apply ==="

$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$backupRoot = Join-Path $projectRoot "_tool_result_intelligence_backups"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $backupRoot $stamp
New-Item -ItemType Directory -Force $backupDir | Out-Null

$files = @(
    "app\core\chat.py",
    "app\tools\result_presentation.py"
)

foreach ($relative in $files) {
    $source = Join-Path $PSScriptRoot $relative
    $target = Join-Path $projectRoot $relative

    if (-not (Test-Path $source)) { throw "Package file missing: $source" }

    if (Test-Path $target) {
        $backup = Join-Path $backupDir $relative
        $backupParent = Split-Path $backup -Parent
        New-Item -ItemType Directory -Force $backupParent | Out-Null
        Copy-Item $target $backup -Force
    }

    $targetParent = Split-Path $target -Parent
    New-Item -ItemType Directory -Force $targetParent | Out-Null
    Copy-Item $source $target -Force
}

Push-Location $projectRoot
try {
    & $python ".\features\Zoya Tool Result Intelligence v1\tests\test_tool_result_intelligence.py"
    if ($LASTEXITCODE -ne 0) { throw "Tool Result Intelligence verification failed." }
}
finally { Pop-Location }

Write-Host "Zoya Tool Result Intelligence v1 installed and verified."
