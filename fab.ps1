# fab — fábrica de mods de SNES (PowerShell). Cria a .venv na primeira execução.
$Root = $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[fab] a criar .venv ..."
    & py -3.12 -m venv (Join-Path $Root ".venv")
    if ($LASTEXITCODE -ne 0) { & python -m venv (Join-Path $Root ".venv") }
    & $Py -m pip install --disable-pip-version-check -q -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { exit 3 }
}
$env:PYTHONPATH = "$Root;$env:PYTHONPATH"
$env:PYTHONUTF8 = "1"
& $Py -m snesfab @args
exit $LASTEXITCODE
