#Requires -Version 5
# Launch the Bergner Skills installer TUI (Windows / PowerShell).
# Prefers uv (auto-installs Textual via PEP 723 inline deps); falls back to a
# local virtualenv + pip on systems without uv.
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv run installer.py @args
    exit $LASTEXITCODE
}

Write-Host "uv not found - falling back to a local virtualenv (.venv)."
Write-Host "Tip: install uv for a faster, zero-setup launch: https://docs.astral.sh/uv/"

$py = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
      elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' }
      else { $null }
if (-not $py) {
    Write-Error "Need either 'uv' or 'python' on PATH."
    exit 1
}

if (-not (Test-Path .venv)) {
    & $py -m venv .venv
}
$venvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet 'textual>=0.60'
& $venvPy installer.py @args
exit $LASTEXITCODE
