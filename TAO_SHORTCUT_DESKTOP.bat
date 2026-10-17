@echo off
setlocal
title Tao shortcut HMS QR Desktop

set "SHORTCUT_PATH=%USERPROFILE%\Desktop\HMS QR Desktop.lnk"
set "LAUNCHER_PATH=%~dp0CHAY_DESKTOP.bat"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut($env:SHORTCUT_PATH); $shortcut.TargetPath = $env:LAUNCHER_PATH; $shortcut.WorkingDirectory = Split-Path $env:LAUNCHER_PATH; $shortcut.Description = 'HMS QR Desktop LAN'; $shortcut.IconLocation = $env:SystemRoot + '\System32\shell32.dll,167'; $shortcut.Save()"
if errorlevel 1 (
  echo Khong the tao shortcut. Kiem tra quyen Desktop cua tai khoan Windows.
  pause
  exit /b 1
)

echo Da tao shortcut: %SHORTCUT_PATH%
pause
