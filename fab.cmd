@echo off
rem fab - SNES mod factory CLI wrapper. Creates .venv on first run.
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [fab] creating .venv ...
  py -3.12 -m venv "%ROOT%.venv" 2>nul || python -m venv "%ROOT%.venv" || exit /b 3
  "%PY%" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt" || exit /b 3
)
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
set "PYTHONUTF8=1"
"%PY%" -m snesfab %*
exit /b %ERRORLEVEL%
