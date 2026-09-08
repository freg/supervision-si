<# si-agent -- désinstallation Windows (#440) : tâche planifiée, fichiers du programme ;
   -KeepData conserve C:\ProgramData\si-agent (configuration, file locale, journal). #>
[CmdletBinding()]
param([string]$InstallDir = (Join-Path $env:ProgramFiles "si-agent"), [string]$DataDir = (Join-Path $env:ProgramData "si-agent"), [string]$TaskName = "si-agent", [switch]$KeepData)
$ErrorActionPreference = "SilentlyContinue"
Stop-ScheduledTask -TaskName $TaskName
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Get-Process python* | Where-Object { $_.CommandLine -match "si_agent.agent" } | Stop-Process -Force
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
if (-not $KeepData -and (Test-Path $DataDir)) { Remove-Item $DataDir -Recurse -Force }
Write-Host "si-agent désinstallé ($InstallDir$(if ($KeepData) { '' } else { ", $DataDir" }))"
