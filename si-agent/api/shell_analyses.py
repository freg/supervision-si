# -*- coding: utf-8 -*-
"""#919 : catalogue des analyses techniques à distance (scripts PowerShell en LECTURE SEULE, passés par l'agent)
et interprétation des résultats côté central.

Chaque analyse : id, titre, description, script, délai (s), format (« json » : un document entre les balises
SI-JSON-DEBUT / SI-JSON-FIN ; « texte » sinon). Les scripts doivent passer la garde du poste en mode lecture
(test : hub/si-agent/agent/tests/test_shell_catalogue.py les vérifie avec PowerShell quand il est présent).

`interpreter(id, sortie)` -> {"axes": {materiel|systeme|viral: {"niveau", "constats"}}, "synthese"} ou None."""
import json
import re

JSON_DEBUT, JSON_FIN = "SI-JSON-DEBUT", "SI-JSON-FIN"

# -------------------------------------------------------------------------------------------------------------------
# Scripts
# -------------------------------------------------------------------------------------------------------------------
_TRIAGE = r'''
$d = (Get-Date).AddDays(-30)
function Chemin-Exe($c) {
  if (-not $c) { return $null }
  $c = [Environment]::ExpandEnvironmentVariables([string]$c)
  if ($c -match '^\s*"([^"]+)"') { return $matches[1] }
  if ($c -match '^\s*(.+?\.(exe|dll|com|bat|cmd|ps1|vbs|js))(\s|,|$)') { return $matches[1] }
  return $null
}
function Signature($p) {
  if (-not $p -or -not (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue)) { return 'introuvable' }
  $s = Get-AuthenticodeSignature -FilePath $p -ErrorAction SilentlyContinue
  if (-not $s) { return 'inconnue' }
  if ("$($s.Status)" -eq 'Valid') { return 'signé : ' + (($s.SignerCertificate.Subject -split ',')[0] -replace '^CN=', '') }
  return "$($s.Status)"
}
function Evt($e) { [pscustomobject]@{ date = $e.TimeCreated.ToString('s'); source = $e.ProviderName; id = $e.Id; message = (($e.Message -split "`r?`n")[0]) } }

$sys = @(Get-WinEvent -FilterHashtable @{LogName = 'System'; StartTime = $d; Level = 1, 2, 3} -ErrorAction SilentlyContinue)
$mat = @($sys | Where-Object { $_.ProviderName -match 'WHEA|^disk$|stor|Ntfs|Kernel-Power|volmgr|SystemErrorReporting|BugCheck|^EventLog$' -and $_.Id -ne 6013 })
$app = @(Get-WinEvent -FilterHashtable @{LogName = 'Application'; StartTime = $d; ProviderName = 'Application Error', 'Application Hang'} -ErrorAction SilentlyContinue)
$scm = @($sys | Where-Object { $_.ProviderName -eq 'Service Control Manager' -and $_.Id -in 7031, 7034 })
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$sysdisk = (Get-Partition -DriveLetter C -ErrorAction SilentlyContinue).DiskNumber

$disques = @(Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object {
  $r = $_ | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue
  [pscustomobject]@{ numero = $_.DeviceId; nom = $_.FriendlyName; type = "$($_.MediaType)"; bus = "$($_.BusType)"; sante = "$($_.HealthStatus)"; etat = "$($_.OperationalStatus)";
    taille_go = [math]::Round($_.Size / 1GB); temperature = $r.Temperature; temperature_max = $r.TemperatureMax; erreurs_lecture_nc = $r.ReadErrorsUncorrected;
    erreurs_ecriture_nc = $r.WriteErrorsUncorrected; usure = $r.Wear; heures = $r.PowerOnHours } })
$volumes = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { [pscustomobject]@{ lecteur = $_.DeviceID; taille_go = [math]::Round($_.Size / 1GB); libre_go = [math]::Round($_.FreeSpace / 1GB, 1) } })
$dumps = @(Get-ChildItem (Join-Path $env:SystemRoot 'Minidump') -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ nom = $_.Name; date = $_.LastWriteTime.ToString('s') } })

$incidents = @($app | Select-Object -First 40 | ForEach-Object { [pscustomobject]@{ date = $_.TimeCreated.ToString('s'); type = $(if ($_.ProviderName -eq 'Application Hang') { 'blocage' } else { 'plantage' });
  appli = "$($_.Properties[0].Value)"; module = $(if ($_.ProviderName -eq 'Application Error') { "$($_.Properties[3].Value)" } else { '' }) } })
$parAppli = @($app | Group-Object { "$($_.Properties[0].Value)".ToLower() } | Sort-Object Count -Descending | Select-Object -First 20 | ForEach-Object { [pscustomobject]@{ appli = $_.Name; n = $_.Count } })
$services = @($scm | Group-Object { "$($_.Properties[0].Value)" } | Sort-Object Count -Descending | Select-Object -First 15 | ForEach-Object { [pscustomobject]@{ service = $_.Name; n = $_.Count } })

$av = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ nom = $_.displayName; etat = $_.productState } })
$detections = @(Get-MpThreatDetection -ErrorAction SilentlyContinue | Select-Object -First 20 | ForEach-Object { [pscustomobject]@{ date = $_.InitialDetectionTime.ToString('s'); processus = $_.ProcessName; ressources = ($_.Resources -join ' ; ') } })
$demarrage = @(Get-CimInstance Win32_StartupCommand -ErrorAction SilentlyContinue | ForEach-Object { $p = Chemin-Exe $_.Command; [pscustomobject]@{ nom = $_.Name; commande = $_.Command; emplacement = $_.Location; chemin = $p; signature = (Signature $p) } })
$svc = @(Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | Where-Object { $_.PathName -and $_.PathName -notmatch '\\Windows\\' } | ForEach-Object { $p = Chemin-Exe $_.PathName; [pscustomobject]@{ nom = $_.Name; etat = $_.State; demarrage = $_.StartMode; chemin = $p; signature = (Signature $p) } })
$taches = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskPath -notlike '\Microsoft\*' } | ForEach-Object { $x = @($_.Actions | ForEach-Object { $_.Execute }) -join ' ; '; $p = Chemin-Exe $x; [pscustomobject]@{ nom = $_.TaskPath + $_.TaskName; etat = "$($_.State)"; execute = $x; chemin = $p; signature = (Signature $p) } })
$conn = @(Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue | Where-Object { $_.RemoteAddress -notmatch '^(127\.|::1|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|fe80|0\.0\.0\.0)' } | ForEach-Object {
  $pp = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).Path; [pscustomobject]@{ distant = "$($_.RemoteAddress):$($_.RemotePort)"; processus = $pp } } | Sort-Object processus, distant -Unique | Select-Object -First 60)
$connSig = @($conn | Select-Object -ExpandProperty processus -Unique | Where-Object { $_ } | ForEach-Object { [pscustomobject]@{ chemin = $_; signature = (Signature $_) } })
$hosts = @(Get-Content (Join-Path $env:SystemRoot 'System32\drivers\etc\hosts') -ErrorAction SilentlyContinue | Where-Object { $_ -match '^\s*[^#\s]' })

$r = [pscustomobject]@{
  poste = [pscustomobject]@{ nom = $env:COMPUTERNAME; modele = "$($cs.Manufacturer) $($cs.Model)"; systeme = $os.Caption; version = $os.Version; demarre = $os.LastBootUpTime.ToString('s');
    memoire_go = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1); memoire_libre_go = [math]::Round($os.FreePhysicalMemory / 1MB, 1); disque_systeme = $sysdisk;
    redemarrage_en_attente = (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') -or (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') }
  materiel = [pscustomobject]@{ evenements = @($mat | Select-Object -First 60 | ForEach-Object { Evt $_ }); disques = $disques; volumes = $volumes; minidumps = $dumps }
  systeme = [pscustomobject]@{ par_appli = $parAppli; incidents = $incidents; services_en_echec = $services; correctifs = @(Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | Select-Object -First 8 | ForEach-Object { [pscustomobject]@{ kb = $_.HotFixID; date = $(if ($_.InstalledOn) { $_.InstalledOn.ToString('s') } else { '' }) } }) }
  viral = [pscustomobject]@{ antivirus = $av; detections = $detections; demarrage = $demarrage; services = $svc; taches = $taches; connexions = $conn; signatures_connexions = $connSig; hosts = $hosts }
}
'SI-JSON-DEBUT'
$r | ConvertTo-Json -Depth 6
'SI-JSON-FIN'
'''

_INTEGRITE = r'''
"### DISM /ScanHealth (magasin de composants)"
dism /Online /Cleanup-Image /ScanHealth /English
"### SFC /verifyonly (fichiers système)"
(sfc /verifyonly | Out-String) -replace "`0", ''
"### CHKDSK C: /scan (système de fichiers, sans réparation)"
chkdsk C: /scan
'''

_PROCESSUS = r'''
"### Agent si-agent et sondes en cours"
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like (Join-Path $env:ProgramFiles 'si-agent\*') -or $_.CommandLine -like '*si-agent\plugins*' -or $_.CommandLine -like '*si_agent*' } | ForEach-Object {
  $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
  [pscustomobject]@{ PID = $_.ProcessId; Parent = $_.ParentProcessId; 'CPU s' = [math]::Round($p.CPU, 1); Mo = [math]::Round($p.WorkingSet64 / 1MB); Commande = $_.CommandLine } } | Format-Table -AutoSize -Wrap
"### Charge instantanée"
Get-CimInstance Win32_Processor | Format-Table Name, NumberOfLogicalProcessors, LoadPercentage -AutoSize
$os = Get-CimInstance Win32_OperatingSystem
"Mémoire libre : {0:N0} Mo sur {1:N0} Mo ; démarré le {2}" -f ($os.FreePhysicalMemory / 1KB), ($os.TotalVisibleMemorySize / 1KB), $os.LastBootUpTime
"### 15 processus les plus gourmands en processeur (temps cumulé)"
Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name, Id, @{n = 'CPU s'; e = { [math]::Round($_.CPU, 1) } }, @{n = 'Mo'; e = { [math]::Round($_.WorkingSet64 / 1MB) } }, Path | Format-Table -AutoSize
"### 15 processus les plus gourmands en mémoire"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 Name, Id, @{n = 'Mo'; e = { [math]::Round($_.WorkingSet64 / 1MB) } }, @{n = 'CPU s'; e = { [math]::Round($_.CPU, 1) } }, Path | Format-Table -AutoSize
'''

_VEILLE = r'''
"### États de veille disponibles"
powercfg /a
"### Ce qui empêche la veille en ce moment"
powercfg /requests
"### Dernier réveil"
powercfg /lastwake
"### Réglages de veille du mode actif (valeurs en secondes, secteur puis batterie)"
powercfg /q SCHEME_CURRENT SUB_SLEEP
"### Veille, réveils, arrêts et redémarrages (7 jours)"
Get-WinEvent -FilterHashtable @{LogName = 'System'; StartTime = (Get-Date).AddDays(-7)} -ErrorAction SilentlyContinue | Where-Object { ($_.ProviderName -match 'Kernel-Power|Power-Troubleshooter|^EventLog$|Kernel-General') -and $_.Id -in 1, 12, 13, 41, 42, 107, 109, 506, 507, 6005, 6006, 6008 } |
  Select-Object -First 50 @{n = 'Date'; e = { $_.TimeCreated.ToString('g') } }, Id, @{n = 'Message'; e = { ($_.Message -split "`r?`n")[0] } } | Format-Table -AutoSize -Wrap
"### Économie d'énergie des cartes réseau"
Get-NetAdapterPowerManagement -ErrorAction SilentlyContinue | Format-Table Name, AllowComputerToTurnOffDevice, WakeOnMagicPacket, DeviceSleepOnDisconnect -AutoSize
'''

_JOURNAL = r'''
"### Journal de l'agent (200 dernières lignes)"
Get-Content (Join-Path $env:ProgramData 'si-agent\agent.log') -Tail 200 -ErrorAction SilentlyContinue
"### Dernier journal de mise à jour"
Get-ChildItem (Join-Path $env:ProgramData 'si-agent') -Filter 'update-*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { "--- $($_.Name)"; Get-Content $_.FullName -Tail 40 }
'''

_RESEAU = r'''
$cfg = Get-Content (Join-Path $env:ProgramData 'si-agent\agent.json') -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
$central = if ($cfg -and $cfg.central_url) { ([uri]$cfg.central_url).Host } else { $null }
"### Cartes réseau"
Get-NetAdapter -ErrorAction SilentlyContinue | Format-Table Name, InterfaceDescription, Status, LinkSpeed, MediaConnectionState -AutoSize
"### Adresses, passerelles, DNS"
Get-NetIPConfiguration -ErrorAction SilentlyContinue | Format-List InterfaceAlias, IPv4Address, IPv4DefaultGateway, DNSServer
"### Wi-Fi"
netsh wlan show interfaces
"### Central de supervision ($central)"
if ($central) { Resolve-DnsName $central -ErrorAction SilentlyContinue | Format-Table Name, Type, IPAddress -AutoSize; Test-NetConnection $central -Port 443 -WarningAction SilentlyContinue | Format-List ComputerName, RemoteAddress, TcpTestSucceeded }
"### Lecteurs réseau des utilisateurs (un serveur injoignable fait geler l'Explorateur et Excel)"
Get-ChildItem 'Registry::HKEY_USERS' -ErrorAction SilentlyContinue | ForEach-Object {
  $sid = $_.PSChildName
  Get-ChildItem "Registry::HKEY_USERS\$sid\Network" -ErrorAction SilentlyContinue | ForEach-Object {
    $rp = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).RemotePath
    $srv = if ($rp -match '^\\\\([^\\]+)') { $matches[1] } else { $null }
    $ok = if ($srv) { (Test-NetConnection $srv -Port 445 -WarningAction SilentlyContinue -InformationLevel Quiet) } else { $null }
    [pscustomobject]@{ Utilisateur = $sid; Lecteur = $_.PSChildName + ':'; Chemin = $rp; 'Joignable (445)' = $ok } } } | Format-Table -AutoSize -Wrap
'''

_OWNCLOUD = r'''
"### Client ownCloud installé"
@((Join-Path $env:ProgramFiles 'ownCloud\owncloud.exe'), (Join-Path ${env:ProgramFiles(x86)} 'ownCloud\owncloud.exe')) | Where-Object { Test-Path $_ } | ForEach-Object { "{0} : version {1}" -f $_, (Get-Item $_).VersionInfo.ProductVersion }
Get-Process owncloud -ErrorAction SilentlyContinue | Format-Table Id, @{n = 'CPU s'; e = { [math]::Round($_.CPU, 1) } }, @{n = 'Mo'; e = { [math]::Round($_.WorkingSet64 / 1MB) } }, StartTime -AutoSize
"### Comptes et dossiers synchronisés, par utilisateur"
Get-ChildItem 'C:\Users' -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $u = $_
  foreach ($cfgPath in @((Join-Path $u.FullName 'AppData\Roaming\ownCloud\owncloud.cfg'), (Join-Path $u.FullName 'AppData\Local\ownCloud\owncloud.cfg'))) {
    if (-not (Test-Path $cfgPath)) { continue }
    "--- $($u.Name) : $cfgPath"
    $lignes = Get-Content $cfgPath -ErrorAction SilentlyContinue
    $lignes | Where-Object { $_ -match '(^|\\)(url|user|dav_user|version|localPath|targetPath|paused|virtualFilesMode)=' }
    $lignes | Where-Object { $_ -match '\\localPath=' } | ForEach-Object {
      $p = ($_ -split '=', 2)[1] -replace '/', '\'
      if (Test-Path $p) {
        $f = @(Get-ChildItem $p -Recurse -File -Force -ErrorAction SilentlyContinue)
        "    dossier $p : {0:N0} fichiers, {1:N1} Go ; conflits : {2} ; chemins de plus de 240 caractères : {3} ; fichiers ouverts par Office (~$) : {4}" -f $f.Count, (($f | Measure-Object Length -Sum).Sum / 1GB), @($f | Where-Object { $_.Name -match 'conflict' }).Count, @($f | Where-Object { $_.FullName.Length -gt 240 }).Count, @($f | Where-Object { $_.Name -like '~$*' }).Count
      } else { "    dossier $p : introuvable" }
    }
  }
  Get-ChildItem (Join-Path $u.FullName 'AppData\Local\ownCloud') -Recurse -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { "--- journal $($_.FullName)"; Get-Content $_.FullName -Tail 40 }
}
"### Office / Excel"
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration' -ErrorAction SilentlyContinue | Format-List VersionToReport, Platform, ProductReleaseIds, UpdateChannel, CDNBaseUrl
"Compléments Excel (machine et utilisateurs ; LoadBehavior 3 = chargé au démarrage)"
@(Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Office\Excel\Addins', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Office\Excel\Addins' -ErrorAction SilentlyContinue) + @(Get-ChildItem 'Registry::HKEY_USERS\*\Software\Microsoft\Office\Excel\Addins' -ErrorAction SilentlyContinue) |
  ForEach-Object { $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue; [pscustomobject]@{ Complement = $_.PSChildName; Nom = $p.FriendlyName; LoadBehavior = $p.LoadBehavior } } | Format-Table -AutoSize
"Plantages et blocages d'Excel et d'ownCloud (30 jours)"
Get-WinEvent -FilterHashtable @{LogName = 'Application'; StartTime = (Get-Date).AddDays(-30); ProviderName = 'Application Error', 'Application Hang'} -ErrorAction SilentlyContinue | Where-Object { "$($_.Properties[0].Value)" -match 'excel|owncloud' } |
  Select-Object -First 30 @{n = 'Date'; e = { $_.TimeCreated.ToString('g') } }, @{n = 'Type'; e = { if ($_.ProviderName -eq 'Application Hang') { 'blocage' } else { 'plantage' } } }, @{n = 'Appli'; e = { $_.Properties[0].Value } }, @{n = 'Module'; e = { $_.Properties[3].Value } } | Format-Table -AutoSize
'''

CATALOGUE = [
    {"id": "triage", "titre": "Triage matériel / système / viral", "delai": 300, "format": "json",
     "description": "Journaux 30 jours (WHEA, disques, arrêts brutaux, écrans bleus), santé des disques et volumes, plantages et "
                    "blocages par application, services en échec, antivirus et détections, démarrage automatique, services, "
                    "tâches planifiées et connexions sortantes avec leur signature. Verdict par axe.",
     "script": _TRIAGE},
    {"id": "integrite", "titre": "Intégrité du système (DISM, SFC, CHKDSK)", "delai": 3600, "format": "texte",
     "description": "Vérifications SANS réparation : magasin de composants (DISM /ScanHealth), fichiers système (SFC /verifyonly), "
                    "système de fichiers C: (CHKDSK /scan). 15 à 40 minutes.",
     "script": _INTEGRITE},
    {"id": "processus", "titre": "Processus : agent, sondes, plus gros consommateurs", "delai": 60, "format": "texte",
     "description": "Ce que font l'agent et ses sondes en ce moment, charge du processeur, mémoire libre, 15 processus les plus "
                    "gourmands en processeur et en mémoire.",
     "script": _PROCESSUS},
    {"id": "veille", "titre": "Veille et alimentation", "delai": 120, "format": "texte",
     "description": "États de veille, ce qui l'empêche, dernier réveil, délais du mode actif, événements de veille / arrêt sur 7 "
                    "jours, économie d'énergie des cartes réseau.",
     "script": _VEILLE},
    {"id": "journal-agent", "titre": "Journal de l'agent", "delai": 60, "format": "texte",
     "description": "Les 200 dernières lignes du journal de si-agent et le dernier journal de mise à jour.",
     "script": _JOURNAL},
    {"id": "reseau", "titre": "Réseau et lecteurs réseau", "delai": 180, "format": "texte",
     "description": "Cartes, adresses, DNS, Wi-Fi, accès au central, lecteurs réseau de chaque utilisateur avec test du serveur "
                    "(un serveur injoignable fait geler l'Explorateur et Excel).",
     "script": _RESEAU},
    {"id": "owncloud-excel", "titre": "ownCloud et Excel", "delai": 900, "format": "texte",
     "description": "Version et comptes du client ownCloud, dossiers synchronisés (volume, conflits, chemins trop longs, fichiers "
                    "Office ouverts), dernier journal du client, version d'Office, compléments Excel, plantages et blocages "
                    "d'Excel et d'ownCloud.",
     "script": _OWNCLOUD},
]
_PAR_ID = {a["id"]: a for a in CATALOGUE}


def analyse(aid):
    return _PAR_ID.get(aid)


def liste():
    """Catalogue publié au hub (le script est montré, pour relecture)."""
    return [dict(a) for a in CATALOGUE]


# -------------------------------------------------------------------------------------------------------------------
# Interprétation
# -------------------------------------------------------------------------------------------------------------------
NIVEAUX = ("rien", "info", "suspect", "probable")


def _pire(a, b):
    return a if NIVEAUX.index(a) >= NIVEAUX.index(b) else b


def _axe():
    return {"niveau": "rien", "constats": []}


def _constat(axe, niveau, texte):
    axe["constats"].append({"niveau": niveau, "texte": texte})
    axe["niveau"] = _pire(axe["niveau"], niveau)


def extraire_json(sortie):
    """Document JSON entre les balises SI-JSON-DEBUT / SI-JSON-FIN (None s'il manque ou est illisible)."""
    m = re.search(re.escape(JSON_DEBUT) + r"\s*(.*?)\s*" + re.escape(JSON_FIN), sortie or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def _liste(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def etat_antivirus(code):
    """productState du Centre de sécurité -> (actif, à jour). Octet du milieu 0x10/0x11 = actif ; dernier 0x00 = à jour."""
    try:
        h = "%06x" % int(code)
    except (TypeError, ValueError):
        return None, None
    return h[2:4] in ("10", "11"), h[4:6] == "00"


_ECRITURE_UTILISATEUR = re.compile(r"\\(appdata|temp|tmp|downloads|t[ée]l[ée]chargements|users\\public|programdata)\\", re.I)
_EVT_DISQUE = {7: "secteur illisible", 11: "erreur du contrôleur", 51: "erreur de pagination", 129: "réinitialisation du contrôleur",
               153: "opération d'E/S répétée", 55: "structure du système de fichiers endommagée", 98: "volume à vérifier",
               157: "disque retiré à chaud", 140: "échec d'écriture différée"}


def _numero_disque(msg):
    m = re.search(r"Harddisk(\d+)", msg or "") or re.search(r"\b(?:disque|disk)\s+(\d+)", msg or "", re.I)
    return int(m.group(1)) if m else None


def interpreter_triage(doc):
    mat, sy, vi = _axe(), _axe(), _axe()
    poste = doc.get("poste") or {}
    m = doc.get("materiel") or {}
    evts = _liste(m.get("evenements"))
    sysdisk = poste.get("disque_systeme")
    disques = {d.get("numero"): d for d in _liste(m.get("disques")) if isinstance(d, dict)}

    whea = [e for e in evts if "WHEA" in str(e.get("source"))]
    if whea:
        _constat(mat, "probable", "%d erreur(s) matérielle(s) signalée(s) par le processeur ou le chipset (WHEA), dernière le %s"
                 % (len(whea), whea[0].get("date", "?")[:16].replace("T", " ")))
    par_disque = {}
    for e in evts:
        src = str(e.get("source") or "").lower()
        if (src == "disk" or src.startswith("stor") or src == "ntfs") and e.get("id") in _EVT_DISQUE:
            par_disque.setdefault(_numero_disque(e.get("message")), []).append(e)
    for num, es in sorted(par_disque.items(), key=lambda x: (x[0] is None, x[0] or 0)):
        types = ", ".join(sorted({_EVT_DISQUE[e["id"]] for e in es}))
        periode = "%s → %s" % (es[-1].get("date", "?")[:16].replace("T", " "), es[0].get("date", "?")[:16].replace("T", " "))
        if num is not None and num == sysdisk:
            _constat(mat, "probable", "disque SYSTÈME (n° %s) : %d erreur(s) (%s), %s" % (num, len(es), types, periode))
        elif num is not None and num not in disques:
            _constat(mat, "suspect", "disque n° %s, absent aujourd'hui (externe, clé USB ou station d'accueil ?) : %d erreur(s) (%s), %s "
                     "-- sans lien avec le poste s'il s'agit d'un support amovible" % (num, len(es), types, periode))
        else:
            _constat(mat, "suspect", "disque n° %s : %d erreur(s) (%s), %s" % (num if num is not None else "?", len(es), types, periode))
    for num, d in disques.items():
        nom = "%s (n° %s%s)" % (d.get("nom") or "disque", num, ", système" if num == sysdisk else "")
        if d.get("sante") and d["sante"] not in ("Healthy", "Sain"):
            _constat(mat, "probable", "%s : santé « %s »" % (nom, d["sante"]))
        if (d.get("erreurs_lecture_nc") or 0) > 0 or (d.get("erreurs_ecriture_nc") or 0) > 0:
            _constat(mat, "probable", "%s : %s erreur(s) de lecture et %s d'écriture non corrigées" % (nom, d.get("erreurs_lecture_nc") or 0, d.get("erreurs_ecriture_nc") or 0))
        if (d.get("temperature") or 0) >= 70:
            _constat(mat, "suspect", "%s : %s °C (chaud)" % (nom, d["temperature"]))
        if (d.get("usure") or 0) >= 80:
            _constat(mat, "suspect", "%s : usure %s %%" % (nom, d["usure"]))
        if d.get("erreurs_lecture_nc") is None and d.get("heures") is None:
            _constat(mat, "info", "%s : le pilote ne publie pas les compteurs SMART détaillés (santé seulement)" % nom)
    kp = [e for e in evts if "Kernel-Power" in str(e.get("source")) and e.get("id") == 41]
    bsod = [e for e in evts if e.get("id") == 1001 and ("BugCheck" in str(e.get("source")) or "SystemErrorReporting" in str(e.get("source")))]
    inattendus = [e for e in evts if e.get("source") == "EventLog" and e.get("id") == 6008]
    dumps = _liste(m.get("minidumps"))
    if kp:
        _constat(mat, "suspect" if len(kp) >= 2 or not bsod else "info",
                 "%d redémarrage(s) brutal(aux) (Kernel-Power 41)%s, le plus récent le %s : gel complet suivi d'un arrêt forcé, ou "
                 "coupure d'alimentation" % (len(kp), " SANS écran bleu" if not bsod and not dumps else "",
                                             kp[0].get("date", "?")[:16].replace("T", " ")))
    elif inattendus:
        _constat(mat, "info", "%d arrêt(s) inattendu(s) (EventLog 6008)" % len(inattendus))
    if bsod or dumps:
        _constat(mat, "suspect", "%d écran(s) bleu(s), %d vidage(s) mémoire : à analyser (pilote ou matériel)" % (len(bsod), len(dumps)))
    mem = poste.get("memoire_go")
    if isinstance(mem, (int, float)) and mem < 8:
        _constat(sy, "suspect", "mémoire installée faible : %s Go" % mem)

    s = doc.get("systeme") or {}
    par_appli = {str(a.get("appli")).lower(): a.get("n") or 0 for a in _liste(s.get("par_appli")) if isinstance(a, dict)}
    incidents = _liste(s.get("incidents"))
    exp = par_appli.get("explorer.exe", 0)
    if exp:
        modules = sorted({i.get("module") for i in incidents if str(i.get("appli")).lower() == "explorer.exe" and i.get("module")})
        _constat(sy, "suspect" if exp >= 3 else "info",
                 "Explorateur : %d plantage(s)/blocage(s) en 30 jours%s -- souvent une extension de l'Explorateur (client de "
                 "synchronisation, compresseur, antivirus) ou un lecteur réseau injoignable" % (exp, (" (modules : %s)" % ", ".join(modules[:6])) if modules else ""))
    for nom, lib in (("excel.exe", "Excel"), ("owncloud.exe", "ownCloud"), ("outlook.exe", "Outlook")):
        n = par_appli.get(nom, 0)
        if n:
            types = sorted({i.get("type") for i in incidents if str(i.get("appli")).lower() == nom})
            _constat(sy, "suspect" if n >= 2 else "info", "%s : %d %s en 30 jours" % (lib, n, " / ".join(types) or "incident(s)"))
    for nom, n in par_appli.items():
        if n >= 5 and nom not in ("explorer.exe", "excel.exe", "owncloud.exe", "outlook.exe", "userinit.exe"):
            _constat(sy, "info", "%s : %d plantage(s)/blocage(s) en 30 jours" % (nom, n))
    if par_appli.get("userinit.exe"):
        _constat(sy, "suspect", "userinit.exe en échec (%d) : ouverture de session perturbée (profil, script ou programme lancé à l'ouverture)" % par_appli["userinit.exe"])
    for v in _liste(m.get("volumes")):
        try:
            if v["taille_go"] and v["libre_go"] / v["taille_go"] < 0.10:
                _constat(sy, "suspect", "volume %s presque plein : %s Go libres sur %s Go" % (v.get("lecteur"), v.get("libre_go"), v.get("taille_go")))
        except (KeyError, TypeError, ZeroDivisionError):
            pass
    svc = [x for x in _liste(s.get("services_en_echec")) if isinstance(x, dict)]
    if svc:
        _constat(sy, "info", "services arrêtés de façon inattendue : " + ", ".join("%s (%s)" % (x.get("service"), x.get("n")) for x in svc[:6]))
    if poste.get("redemarrage_en_attente"):
        _constat(sy, "info", "un redémarrage est en attente (mises à jour)")

    v = doc.get("viral") or {}
    av = [a for a in _liste(v.get("antivirus")) if isinstance(a, dict)]
    actifs = []
    for a in av:
        actif, a_jour = etat_antivirus(a.get("etat"))
        if actif:
            actifs.append(a.get("nom"))
            if a_jour is False:
                _constat(vi, "suspect", "antivirus %s actif mais signatures PAS à jour" % a.get("nom"))
    if av and not actifs:
        _constat(vi, "suspect", "aucun antivirus actif d'après le Centre de sécurité (%s)" % ", ".join(str(a.get("nom")) for a in av))
    elif actifs:
        _constat(vi, "info", "antivirus actif : %s" % ", ".join(str(x) for x in actifs))
    det = _liste(v.get("detections"))
    if det:
        _constat(vi, "probable", "%d détection(s) de Microsoft Defender, dernière le %s" % (len(det), str(det[0].get("date", "?"))[:16].replace("T", " ")))
    for cle, lib in (("demarrage", "démarrage automatique"), ("services", "service"), ("taches", "tâche planifiée")):
        for x in _liste(v.get(cle)):
            if not isinstance(x, dict):
                continue
            sig, chemin = str(x.get("signature") or ""), str(x.get("chemin") or "")
            if sig.startswith("signé") or sig == "introuvable" or not chemin:
                continue
            niveau = "suspect" if _ECRITURE_UTILISATEUR.search(chemin) else "info"
            _constat(vi, niveau, "%s « %s » non signé (%s) : %s" % (lib, x.get("nom"), sig, chemin))
    for x in _liste(v.get("signatures_connexions")):
        if isinstance(x, dict) and not str(x.get("signature") or "").startswith("signé") and _ECRITURE_UTILISATEUR.search(str(x.get("chemin") or "")):
            _constat(vi, "suspect", "programme non signé dans un dossier utilisateur connecté à Internet : %s" % x.get("chemin"))
    hosts = [h for h in _liste(v.get("hosts")) if isinstance(h, str)]
    if hosts:
        _constat(vi, "info", "fichier hosts modifié (%d entrée(s)) : %s" % (len(hosts), " ; ".join(hosts[:4])))

    axes = {"materiel": mat, "systeme": sy, "viral": vi}
    return {"axes": axes, "synthese": synthese(axes), "poste": poste}


def synthese(axes):
    noms = {"materiel": "matériel", "systeme": "système", "viral": "viral"}
    lib = {"rien": "rien de notable", "info": "observations sans gravité", "suspect": "indices", "probable": "cause probable"}
    rangs = sorted(axes, key=lambda k: -NIVEAUX.index(axes[k]["niveau"]))
    tete = axes[rangs[0]]["niveau"]
    phrase = " ; ".join("%s : %s" % (noms[k], lib[axes[k]["niveau"]]) for k in ("materiel", "systeme", "viral"))
    if tete in ("rien", "info"):
        return phrase + ". Aucune piste ne se détache : poursuivre par les tests actifs (charge, mémoire, analyse antivirus complète)."
    poids = lambda k: sum(1 for c in axes[k]["constats"] if c["niveau"] == tete)
    forts = sorted((k for k in axes if axes[k]["niveau"] == tete), key=lambda k: -poids(k))
    if len(forts) == 1:
        return phrase + ". Piste à creuser en premier : %s." % noms[forts[0]]
    return phrase + ". Pistes par nombre d'indices : %s." % ", ".join("%s (%d)" % (noms[k], poids(k)) for k in forts)


_REGLES_INTEGRITE = [
    ("DISM", r"No component store corruption detected", "rien", "magasin de composants sain"),
    ("DISM", r"component store is repairable", "probable", "magasin de composants ENDOMMAGÉ mais réparable (DISM /RestoreHealth, mode intervention)"),
    ("DISM", r"not repairable", "probable", "magasin de composants endommagé et NON réparable en ligne (réparation sur place de Windows)"),
    ("SFC", r"aucune violation|did not find any integrity violations", "rien", "fichiers système intègres"),
    ("SFC", r"trouv.{0,3} des violations|found integrity violations", "probable", "fichiers système endommagés (SFC /scannow après DISM, mode intervention)"),
    ("CHKDSK", r"sans trouver de probl|found no problems", "rien", "système de fichiers sain"),
    ("CHKDSK", r"(trouv|d.tect).{0,6} des probl|found problems|corruption", "probable", "système de fichiers à réparer (CHKDSK /spotfix ou /f au redémarrage, mode intervention)"),
]


def interpreter_integrite(sortie):
    sy = _axe()
    vus = set()
    for outil, motif, niveau, texte in _REGLES_INTEGRITE:
        if outil in vus:
            continue
        if re.search(motif, sortie or "", re.I):
            vus.add(outil)
            _constat(sy, niveau if niveau != "rien" else "info", "%s : %s" % (outil, texte))
    for outil in ("DISM", "SFC", "CHKDSK"):
        if outil not in vus:
            _constat(sy, "info", "%s : résultat non reconnu (lire la sortie)" % outil)
    axes = {"materiel": _axe(), "systeme": sy, "viral": _axe()}
    return {"axes": axes, "synthese": synthese(axes)}


def interpreter(aid, sortie):
    if aid == "triage":
        doc = extraire_json(sortie)
        return interpreter_triage(doc) if isinstance(doc, dict) else None
    if aid == "integrite":
        return interpreter_integrite(sortie)
    return None
