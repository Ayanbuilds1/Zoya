$ErrorActionPreference = 'Stop'
$Project = 'C:\Users\Ayan\Zoya'
$Files = @(
    'frontend\src\App.jsx',
    'frontend\src\App.css',
    'frontend\src\index.css',
    'backend\app\core\chat.py',
    'backend\app\memory\manager.py',
    'backend\app\api\routes\chat.py'
)

Write-Host "Checking Zoya baseline files..." -ForegroundColor Cyan
foreach ($Relative in $Files) {
    $Path = Join-Path $Project $Relative
    if (-not (Test-Path $Path)) {
        throw "Missing: $Relative"
    }
    Write-Host "OK $Relative" -ForegroundColor Green
}

$Python = Join-Path $Project '.venv\Scripts\python.exe'
if (Test-Path $Python) {
    & $Python -m py_compile `
        (Join-Path $Project 'backend\app\core\chat.py') `
        (Join-Path $Project 'backend\app\memory\manager.py') `
        (Join-Path $Project 'backend\app\api\routes\chat.py')
    Write-Host 'Python syntax check: OK' -ForegroundColor Green
} else {
    Write-Warning "Could not find .venv\Scripts\python.exe; skipping Python check."
}

Write-Host 'Done.' -ForegroundColor Green

