$ErrorActionPreference = 'Stop'

$Project = 'C:\Users\Ayan\Zoya'
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupRoot = Join-Path $Project "_baseline_backups\$Stamp"

if (-not (Test-Path $Project)) {
    throw "Zoya project not found at $Project"
}

$Files = @(
    'frontend\src\App.jsx',
    'frontend\src\App.css',
    'frontend\src\index.css',
    'backend\app\core\chat.py',
    'backend\app\memory\manager.py',
    'backend\app\api\routes\chat.py'
)

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

Write-Host "Zoya Clean Baseline v1" -ForegroundColor Cyan
Write-Host "Project: $Project"
Write-Host "Backup:  $BackupRoot"
Write-Host ""

foreach ($Relative in $Files) {
    $Source = Join-Path $PackageRoot $Relative
    $Target = Join-Path $Project $Relative
    $Backup = Join-Path $BackupRoot $Relative

    if (-not (Test-Path $Source)) {
        throw "Package file missing: $Relative"
    }

    if (Test-Path $Target) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Backup) | Out-Null
        Copy-Item $Target $Backup -Force
        Write-Host "BACKUP  $Relative"
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
    Copy-Item $Source $Target -Force
    Write-Host "APPLY   $Relative" -ForegroundColor Green
}

Write-Host ""
Write-Host "Recovery applied. .env and database were not touched." -ForegroundColor Green
Write-Host "Backup saved at: $BackupRoot"
Write-Host ""
Write-Host "Run backend:" -ForegroundColor Cyan
Write-Host "uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload"
Write-Host ""
Write-Host "Run frontend from frontend/: npm run dev" -ForegroundColor Cyan

