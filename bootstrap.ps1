<#
.SYNOPSIS
  Prepara a fábrica de mods de SNES nesta máquina (idempotente; não precisa de admin).

.DESCRIPTION
  1. Garante Python 3.12+ (usa o existente; senão instala o Python 3.12 do usuário via winget).
  2. Cria a .venv e instala requirements.txt (versões fixadas com hash).
  3. Memória CoALA: num clone novo, recria a base local a partir do dump versionado (`fab memory restore`).
  4. `fab setup`: baixa o toolchain fixado em tools/manifest.json (Temurin JDK 21, Ghidra 12.1.4 + ghidra-snes,
     MesenCE 2.2.1, Asar 1.91, ffmpeg) para tools/ (fora do git), conferindo o sha256, e monta a ROM de teste.
     O MCP do REA precisa de Node.js >= 22.19 (sem ele o setup avisa e segue; -NoRea pula).
  5. `fab doctor` e, com -SelfTest, `fab selftest` (unitários + ponta a ponta no emulador headless).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -SelfTest
#>
param(
    [switch]$SelfTest,   # rodar `fab selftest` no fim
    [switch]$SkipTools,  # não baixar o toolchain (só Python, .venv e memória)
    [switch]$NoRea       # não instalar o MCP do REA (tools/rea)
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

function Stop-Bootstrap([string]$What, [string]$Fix) {
    Write-Host "Erro: $What — Solução: $Fix" -ForegroundColor Red
    exit 1
}

function Find-Python {
    foreach ($cand in @("py -3.12", "py -3.13", "py -3.14", "python", "python3")) {
        $parts = $cand.Split(" ")
        if (-not (Get-Command $parts[0] -ErrorAction SilentlyContinue)) { continue }
        $probe = @($parts | Select-Object -Skip 1) + @("-c", "import sys; print(sys.version_info >= (3, 12))")
        try { $ok = & $parts[0] @probe 2>$null } catch { $ok = $null }
        if ($ok -eq "True") { return ,$parts }
    }
    return $null
}

function Invoke-Fab {
    & (Join-Path $root "fab.ps1") @args
    if ($LASTEXITCODE -ne 0) { Stop-Bootstrap "fab $($args -join ' ') falhou" "veja a saída acima e rode o bootstrap de novo" }
}

$py = Find-Python
if (-not $py) {
    Write-Host "[bootstrap] Python 3.12+ não encontrado — instalando o Python 3.12 (escopo do usuário) via winget…"
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    $env:PATH = "$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts;$env:PATH"
    $py = Find-Python
    if (-not $py) { Stop-Bootstrap "Python 3.12+ ainda indisponível" "instale-o (python.org ou winget) e rode o bootstrap de novo" }
}
Write-Host "[bootstrap] Python: $($py -join ' ')"

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $venvArgs = @($py | Select-Object -Skip 1) + @("-m", "venv", (Join-Path $root ".venv"))
    & $py[0] @venvArgs
    if ($LASTEXITCODE -ne 0) { Stop-Bootstrap "não consegui criar a .venv" "confira o Python ($($py -join ' ')) e rode de novo" }
}
& $venvPy -m pip install --disable-pip-version-check -q --require-hashes -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Stop-Bootstrap "pip install -r requirements.txt falhou" "veja a saída acima (rede/proxy?) e rode de novo" }

# memória CoALA: a base SQLite é local (fora do git); num clone novo, recria-a a partir do dump versionado
if (-not (Test-Path (Join-Path $root ".agents\snes-mods-coala-agent-skill\memory\coala.sqlite"))) {
    Invoke-Fab memory restore
}

if (-not $SkipTools) {
    $setupArgs = @("setup")
    if ($NoRea) { $setupArgs += "--no-rea" }
    Invoke-Fab @setupArgs
    Invoke-Fab doctor
}
if ($SelfTest) {
    Invoke-Fab selftest
}
Write-Host "[bootstrap] pronto. Abra o agente (Claude Code) nesta pasta e passe a ROM + o pedido; comandos: .\fab.ps1 --help"
