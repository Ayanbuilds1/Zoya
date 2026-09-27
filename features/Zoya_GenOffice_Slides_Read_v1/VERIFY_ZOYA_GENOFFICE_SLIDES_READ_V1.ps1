$ErrorActionPreference = "Stop"

$featureRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

Write-Host "=== Zoya GenOffice Slides Read v1 Verify ==="
Write-Host "Project root: $projectRoot"
Write-Host "Python: $pythonExe"

& $pythonExe -m py_compile (Join-Path $projectRoot "app\tools\genoffice.py") (Join-Path $projectRoot "app\core\brain.py")
if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }

& $pythonExe -m pytest -q (Join-Path $featureRoot "tests\test_genoffice_slides_read_v1.py") --disable-warnings --maxfail=1
if ($LASTEXITCODE -ne 0) { throw "GenOffice slides adapter tests failed." }

& $pythonExe -m pytest -q (Join-Path $featureRoot "tests\test_genoffice_slides_routing_v1.py") --disable-warnings --maxfail=1
if ($LASTEXITCODE -ne 0) { throw "Brain slides routing tests failed." }

Write-Host "GenOffice Slides Read v1 verification passed."
