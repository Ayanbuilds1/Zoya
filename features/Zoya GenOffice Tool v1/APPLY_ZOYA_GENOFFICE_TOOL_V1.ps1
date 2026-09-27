$ErrorActionPreference = "Stop"

Write-Host "=== Zoya GenOffice Tool v1 Apply ==="

$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Write-Host "Project root: $projectRoot"

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}
Write-Host "Python: $python"

$backupRoot = Join-Path $projectRoot "_genoffice_tool_backups"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $backupRoot $stamp
New-Item -ItemType Directory -Force $backupDir | Out-Null

$files = @(
    "app\tools\genoffice.py",
    "app\tools\defaults.py",
    "app\tools\__init__.py"
)

foreach ($relative in $files) {
    $source = Join-Path $PSScriptRoot $relative
    $target = Join-Path $projectRoot $relative

    if (-not (Test-Path $source)) {
        throw "Package file missing: $source"
    }

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

Write-Host "GenOffice adapter and registry wiring copied."
Write-Host "Backup: $backupDir"
Write-Host "Running isolated contract verification..."

Push-Location $projectRoot
try {
    & $python ".\features\Zoya GenOffice Tool v1\tests\test_genoffice_tool.py"
    if ($LASTEXITCODE -ne 0) {
        throw "GenOffice Tool verification failed."
    }
}
finally {
    Pop-Location
}

Write-Host "Zoya GenOffice Tool v1 installed and verified."
Write-Host "This adapter exposes only local info/convert/create/render operations."
Write-Host "Cloud-facing GenOffice search/image/media commands are intentionally not enabled."
