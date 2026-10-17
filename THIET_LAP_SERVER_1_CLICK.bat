@echo off
setlocal EnableExtensions
net session >nul 2>nul
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
set "ROOT=%~dp0"
pushd "%ROOT%"
set "PYTHON_INSTALLER=%ROOT%installer\python\python-3.14.6-amd64.exe"
set "WHEELS=%ROOT%installer\wheels"

if not exist "%PYTHON_INSTALLER%" (
  echo Missing offline Python installer: %PYTHON_INSTALLER%
  exit /b 1
)
if not exist "%WHEELS%\*.whl" (
  echo Missing offline Python wheels: %WHEELS%
  exit /b 1
)

py -3.14 -c "import sys" >nul 2>nul
if errorlevel 1 (
  "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_launcher=1
  if errorlevel 1 (
    echo Python offline installation failed.
    exit /b 1
  )
)

py -3.14 -m pip install --no-index --find-links "%WHEELS%" -r "%ROOT%requirements.txt" PySide6
if errorlevel 1 (
  echo Offline Python package installation failed.
  exit /b 1
)

py -3.14 -m apps.server.tool
popd
