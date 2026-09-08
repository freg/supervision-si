@echo off
setlocal
rem si-agent -- lanceur Windows 10/11 (livraison #446).
rem Pourquoi : un double-clic sur install.ps1 l'ouvre dans le Bloc-notes, et la
rem politique d'execution par defaut (Restricted) refuse les scripts. Ce lanceur
rem s'eleve en administrateur (UAC) puis appelle install.ps1 avec Bypass.
rem Usage (cmd ou PowerShell, dossier de l'archive decompressee) :
rem   windows\install.cmd -Agent "ID" -Secret "SECRET" -Central "https://VM:6443/api/si-agent" -Site "siege" -CaFingerprint sha256
rem Sans argument (double-clic) : les valeurs sont demandees.
set "SCRIPT=%~dp0install.ps1"
if not exist "%SCRIPT%" ( echo install.ps1 introuvable a cote de ce lanceur & pause & exit /b 1 )
net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo Elevation en administrateur (UAC)...
  if "%~1"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  ) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
  )
  exit /b
)
if not "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
  goto :fin
)
echo si-agent -- installation Windows (valeurs affichees par le bouton Installation de la tuile Agents hotes)
set /p AGENT=Identifiant de l'agent (-Agent) : 
set /p SECRET=Secret (-Secret) : 
set /p CENTRAL=URL du central (-Central, ex. https://VM:6443/api/si-agent) : 
set /p SITE=Site (-Site, vide = default) : 
set /p FP=Empreinte SHA-256 de la CA (-CaFingerprint ; vide = -Insecure, depannage seulement) : 
if "%SITE%"=="" set "SITE=default"
if "%FP%"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -Agent "%AGENT%" -Secret "%SECRET%" -Central "%CENTRAL%" -Site "%SITE%" -Insecure
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -Agent "%AGENT%" -Secret "%SECRET%" -Central "%CENTRAL%" -Site "%SITE%" -CaFingerprint %FP%
)
:fin
echo.
echo Code de sortie : %errorlevel%
pause
endlocal
