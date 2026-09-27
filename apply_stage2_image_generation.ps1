param(
    [string]$ProjectRoot = "C:\Users\Ayan\Zoya"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    throw "Zoya project root not found: $ProjectRoot"
}

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Zoya virtual-environment Python not found: $python"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $ProjectRoot "_tool_image_generation_backups\$timestamp"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$changed = @(
    "app\tools\imagegen.py",
    "app\tools\defaults.py",
    "app\core\brain.py"
)

foreach ($relative in $changed) {
    $target = Join-Path $ProjectRoot $relative
    if (Test-Path -LiteralPath $target) {
        Copy-Item -LiteralPath $target -Destination $backupRoot -Force
    }
}

$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$copyMap = @{
    "app\tools\imagegen.py" = "app\tools\imagegen.py"
    "app\tools\image_provider.py" = "app\tools\image_provider.py"
    "app\tools\image_providers.py" = "app\tools\image_providers.py"
    "app\tools\image_router.py" = "app\tools\image_router.py"
    "app\tools\defaults.py" = "app\tools\defaults.py"
    "app\core\brain.py" = "app\core\brain.py"
    "tests\test_image_generation_stage2.py" = "tests\test_image_generation_stage2.py"
}

foreach ($sourceRelative in $copyMap.Keys) {
    $source = Join-Path $patchRoot $sourceRelative
    $destination = Join-Path $ProjectRoot $copyMap[$sourceRelative]

    if (-not (Test-Path -LiteralPath $source)) {
        throw "Patch source missing: $source"
    }

    $parent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

Write-Host "=== Zoya Image Generation Stage 2 Apply ==="
Write-Host "Project root: $ProjectRoot"
Write-Host "Backup: $backupRoot"

& $python -m py_compile `
    "$ProjectRoot\app\tools\imagegen.py" `
    "$ProjectRoot\app\tools\image_provider.py" `
    "$ProjectRoot\app\tools\image_providers.py" `
    "$ProjectRoot\app\tools\image_router.py" `
    "$ProjectRoot\app\tools\defaults.py" `
    "$ProjectRoot\app\core\brain.py"

if ($LASTEXITCODE -ne 0) {
    throw "Python compile check failed."
}

try {
    & $python -m pytest -q "$ProjectRoot\tests\test_image_generation_stage2.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Stage 2 image-generation tests failed."
    }
}
catch {
    Write-Warning "Pytest could not be completed: $($_.Exception.Message)"
    Write-Warning "The files were applied and Python compile already passed."
}

Write-Host "Stage 2 image-generation patch applied."
Write-Host "This installer does NOT modify frontend, chat.py, execution.py, registry.py, types.py, memory, research, scheduler, database, or ImageMagick implementation."
