@echo off
rem si-agent -- desinstallation Windows (livraison #446) : elevation UAC puis uninstall.ps1 avec Bypass.
set "SCRIPT=%~dp0uninstall.ps1"
net session >nul 2>&1
if not "%errorlevel%"=="0" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
echo.
pause
