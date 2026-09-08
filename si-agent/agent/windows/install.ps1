<#
si-agent -- installation sous Windows 10 / 11 (livraison #440).
Usage (PowerShell en administrateur, depuis le dossier de l'archive) :
  .\windows\install.ps1 -Agent ID -Secret SECRET -Central https://VM:6443/api/si-agent -Site siege `
      [-CaFingerprint sha256hex | -Ca C:\chemin\ca.crt | -Insecure] [-EnablePlugin id,id] [-LogLevel DEBUG]
Ce que fait le script :
  1. vérifie les droits d'administration et trouve Python 3.8+ (py / python) ; sinon
     télécharge la distribution « embeddable » de python.org (stdlib seule, ~11 Mo,
     aucune installation système) dans <InstallDir>\python (-NoDownload pour refuser) ;
  2. copie si_agent\ et plugins\ dans <InstallDir> (C:\Program Files\si-agent) ;
  3. TLS : -CaFingerprint récupère la CA du central (GET /ca) et la vérifie par
     empreinte SHA-256 (comme install.sh) ; -Ca installe un certificat fourni ;
  4. écrit <DataDir>\agent.json (C:\ProgramData\si-agent, lecture réservée à SYSTEM
     et aux administrateurs) ;
  5. enregistre une tâche planifiée « si-agent » (compte SYSTEM, au démarrage,
     redémarrée en cas d'arrêt, sans limite de durée) et la lance.
Rien d'autre n'est modifié sur le poste. Désinstallation : .\windows\uninstall.ps1
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Agent,
  [Parameter(Mandatory = $true)][string]$Secret,
  [Parameter(Mandatory = $true)][string]$Central,
  [string]$Site = "default",
  [string]$Ca,
  [string]$CaFingerprint,
  [switch]$Insecure,
  [string[]]$EnablePlugin = @(),
  [string]$LogLevel = "INFO",
  [string]$InstallDir = (Join-Path $env:ProgramFiles "si-agent"),
  [string]$DataDir = (Join-Path $env:ProgramData "si-agent"),
  [string]$PythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip",
  [switch]$NoDownload,
  [string]$TaskName = "si-agent"
)
$ErrorActionPreference = "Stop"
$Central = $Central.TrimEnd("/")

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "à lancer dans une console PowerShell « Exécuter en tant qu'administrateur »" }
if (-not $Ca -and -not $CaFingerprint -and -not $Insecure) { throw "préciser -CaFingerprint <sha256> (recommandé), -Ca <ca.crt> ou -Insecure (dépannage seulement)" }
$Src = Split-Path -Parent $PSScriptRoot   # racine de l'archive : si_agent\, plugins\, windows\
if (-not (Test-Path (Join-Path $Src "si_agent\agent.py"))) { throw "si_agent\agent.py introuvable à côté de windows\ : lancer le script depuis l'archive décompressée" }

# --- 1. Python ---------------------------------------------------------------------
function Test-Python($exe, $extra) {
  try {
    $v = & $exe @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -eq 0 -and $v -match '^(\d+)\.(\d+)$' -and ([int]$matches[1] -gt 3 -or ([int]$matches[1] -eq 3 -and [int]$matches[2] -ge 8))) { return $v }
  } catch { }
  return $null
}
$PythonExe = $null; $PythonArgs = @()
$embedded = Join-Path $InstallDir "python\python.exe"
if (Test-Path $embedded) { if (Test-Python $embedded @()) { $PythonExe = $embedded } }
if (-not $PythonExe) {
  foreach ($cand in @(@("py", @("-3")), @("python", @()), @("python3", @()))) {
    $exe = Get-Command $cand[0] -ErrorAction SilentlyContinue
    if ($exe -and $exe.Source -notmatch "WindowsApps") {   # l'alias du Store n'est pas un Python
      $v = Test-Python $exe.Source $cand[1]
      if ($v) { $PythonExe = $exe.Source; $PythonArgs = $cand[1]; Write-Host "Python $v : $PythonExe"; break }
    }
  }
}
if (-not $PythonExe) {
  if ($NoDownload) { throw "aucun Python 3.8+ trouvé (py / python) et -NoDownload demandé : installer Python (python.org) puis relancer" }
  Write-Host "aucun Python 3.8+ trouvé : téléchargement de la distribution embarquée $PythonUrl"
  $pyDir = Join-Path $InstallDir "python"
  New-Item -ItemType Directory -Force -Path $pyDir | Out-Null
  $zip = Join-Path $env:TEMP "si-agent-python.zip"
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $PythonUrl -OutFile $zip -UseBasicParsing
  Expand-Archive -Path $zip -DestinationPath $pyDir -Force
  Remove-Item $zip -Force
  # le fichier python3xx._pth borne sys.path : ajouter le dossier d'installation (paquet si_agent)
  Get-ChildItem $pyDir -Filter "python*._pth" | ForEach-Object { Add-Content -Path $_.FullName -Value ".." -Encoding ASCII }
  $PythonExe = $embedded
  if (-not (Test-Python $PythonExe @())) { throw "la distribution embarquée ne démarre pas ($PythonExe)" }
  Write-Host "Python embarqué installé : $PythonExe"
}

# --- 2. fichiers -----------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $InstallDir, $DataDir, (Join-Path $DataDir "plugins") | Out-Null
foreach ($d in @("si_agent", "plugins")) {
  $dst = Join-Path $InstallDir $d
  if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
  Copy-Item (Join-Path $Src $d) $dst -Recurse -Force
}
Get-ChildItem $InstallDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item $PSScriptRoot\uninstall.ps1 (Join-Path $InstallDir "uninstall.ps1") -Force

# --- 3. CA du central ----------------------------------------------------------------
$caFile = Join-Path $DataDir "central-ca.crt"
if ($CaFingerprint) {
  $expected = $CaFingerprint.ToLower().Replace("sha256:", "").Replace(":", "")
  $bytes = $null
  if ($PSVersionTable.PSVersion.Major -ge 7) {
    $bytes = (Invoke-WebRequest -Uri "$Central/ca" -SkipCertificateCheck -UseBasicParsing).Content
  } else {
    $old = [Net.ServicePointManager]::ServerCertificateValidationCallback
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }   # amorçage : la CA n'est pas encore connue, l'empreinte fait foi
    try { $bytes = (Invoke-WebRequest -Uri "$Central/ca" -UseBasicParsing).Content } finally { [Net.ServicePointManager]::ServerCertificateValidationCallback = $old }
  }
  if ($bytes -is [string]) { $bytes = [Text.Encoding]::ASCII.GetBytes($bytes) }
  $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new([byte[]]$bytes)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $got = ([BitConverter]::ToString($sha.ComputeHash($cert.RawData))).Replace("-", "").ToLower()
  if ($got -ne $expected) { throw "EMPREINTE DE LA CA DIFFÉRENTE : reçue $got, attendue $expected -- installation refusée" }
  [IO.File]::WriteAllBytes($caFile, $bytes)
  Write-Host "CA du central vérifiée ($($got.Substring(0,16))) et installée"
} elseif ($Ca) {
  Copy-Item $Ca $caFile -Force
}

# --- 4. configuration ---------------------------------------------------------------------
$plugins = @{}
foreach ($p in $EnablePlugin) { if ($p) { $plugins[$p] = @{ enabled = $true } } }
$cfg = [ordered]@{
  agent_id = $Agent; secret = $Secret; central_url = $Central; site = $Site
  insecure = [bool]$Insecure; plugins = $plugins; log_level = $LogLevel
  log_file = (Join-Path $DataDir "agent.log")
  queue_path = (Join-Path $DataDir "queue.db"); plugins_dir = (Join-Path $DataDir "plugins")
  state_path = (Join-Path $DataDir "state.json"); block_file = (Join-Path $DataDir "BLOCKED")
}
if (Test-Path $caFile) { $cfg.ca_file = $caFile }
$cfgPath = Join-Path $DataDir "agent.json"
[IO.File]::WriteAllText($cfgPath, ($cfg | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
# lecture réservée à SYSTEM et aux administrateurs (le secret est dedans)
& icacls $DataDir /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null

# --- 5. tâche planifiée (compte SYSTEM, au démarrage, relancée) ---------------------------------
$argLine = (($PythonArgs + @("-m", "si_agent.agent", "--config", "`"$cfgPath`"")) -join " ")
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument $argLine -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "S-1-5-18" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$settings.ExecutionTimeLimit = "PT0S"   # sans limite (la valeur zéro par le paramètre du cmdlet est ignorée sur certaines versions)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "supervision-si : agent hôte si-agent ($Agent)" | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 3
$t = Get-ScheduledTask -TaskName $TaskName
Write-Host "tâche planifiée $TaskName : $($t.State)"
Write-Host "si-agent installé dans $InstallDir ; configuration et journal dans $DataDir"
Write-Host "état : & '$PythonExe' $($PythonArgs -join ' ') -m si_agent.agent --config '$cfgPath' --status   (depuis $InstallDir)"
Write-Host "collecte à blanc : ... --collect ; traces : Get-Content '$DataDir\agent.log' -Wait ; blocage local : New-Item '$DataDir\BLOCKED'"
