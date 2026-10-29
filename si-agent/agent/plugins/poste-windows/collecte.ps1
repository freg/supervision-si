# si-agent #896 -- poste Windows : configuration à réinstaller et diagnostic. LECTURE SEULE, UN objet JSON.
# Lancé par poste_windows.py (compte SYSTEM). Aucun mot de passe ni clé complète n'est lu : clé de produit partielle seulement.
param([int]$Jours = 30)
$ErrorActionPreference = "SilentlyContinue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$partiel = New-Object System.Collections.ArrayList
function Iso($d) { if ($d) { try { return ([datetime]$d).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") } catch { return $null } } return $null }
function Coupe($s, $n) { if ($s) { $t = [string]$s; if ($t.Length -gt $n) { return $t.Substring(0, $n) } return $t } return $null }
$depuis = (Get-Date).AddDays(-$Jours)

# --- comptes utilisateurs (profils) et ruches chargées
$profils = @()
foreach ($p in (Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special -and $_.LocalPath -like "C:\Users\*" })) {
  $profils += [ordered]@{ sid = $p.SID; chemin = $p.LocalPath; utilisateur = Split-Path $p.LocalPath -Leaf; charge = [bool]$p.Loaded; derniere_utilisation = Iso $p.LastUseTime }
}
New-PSDrive -Name HKU -PSProvider Registry -Root HKEY_USERS | Out-Null

# --- partages servis par le poste (hors partages administratifs)
$partages = @()
foreach ($s in (Get-SmbShare | Where-Object { -not $_.Special -and $_.Name -notlike "*$" })) {
  $acces = @(Get-SmbShareAccess -Name $s.Name | ForEach-Object { "{0}:{1}:{2}" -f $_.AccountName, $_.AccessControlType, $_.AccessRight })
  $partages += [ordered]@{ nom = $s.Name; chemin = $s.Path; description = $s.Description; acces = $acces }
}

# --- lecteurs réseau, raccourcis réseau, profils Outlook et identités Office par utilisateur (ruches chargées)
$lecteurs = @(); $raccourcis = @(); $outlook = @(); $identites = @()
foreach ($p in $profils) {
  $racine = "HKU:\" + $p.sid
  if (Test-Path $racine) {
    foreach ($k in (Get-ChildItem "$racine\Network")) {
      $v = Get-ItemProperty $k.PSPath
      $lecteurs += [ordered]@{ utilisateur = $p.utilisateur; lettre = $k.PSChildName + ":"; chemin = $v.RemotePath; compte = $v.UserName }
    }
    foreach ($k in (Get-ChildItem "$racine\Software\Microsoft\Office\16.0\Outlook\Profiles")) { $outlook += [ordered]@{ utilisateur = $p.utilisateur; profil = $k.PSChildName } }
    foreach ($k in (Get-ChildItem "$racine\Software\Microsoft\Office\16.0\Common\Identity\Identities")) {
      $v = Get-ItemProperty $k.PSPath
      if ($v.EmailAddress) { $identites += [ordered]@{ utilisateur = $p.utilisateur; courriel = $v.EmailAddress; fournisseur = $v.ProviderId } }
    }
  }
  foreach ($f in (Get-ChildItem (Join-Path $p.chemin "AppData\Roaming\Microsoft\Windows\Network Shortcuts"))) { $raccourcis += [ordered]@{ utilisateur = $p.utilisateur; nom = $f.Name } }
}

# --- fichiers de données Outlook (taille : à sauvegarder avant réinstallation)
$pst = @()
foreach ($p in $profils) {
  foreach ($d in @("AppData\Local\Microsoft\Outlook", "Documents\Outlook Files", "Documents\Fichiers Outlook")) {
    foreach ($f in (Get-ChildItem (Join-Path $p.chemin $d) -Include *.pst, *.ost -Recurse)) { $pst += [ordered]@{ utilisateur = $p.utilisateur; fichier = $f.FullName; octets = [int64]$f.Length; modifie = Iso $f.LastWriteTime } }
  }
}

# --- Thunderbird : lignes de préférences utiles (comptes, identités, serveurs d'envoi, agendas) ; aucun mot de passe n'y figure
$thunderbird = @()
foreach ($p in $profils) {
  $ini = Join-Path $p.chemin "AppData\Roaming\Thunderbird\profiles.ini"
  if (Test-Path $ini) {
    $base = Split-Path $ini
    foreach ($l in (Get-Content $ini | Where-Object { $_ -like "Path=*" })) {
      $chemin = $l.Substring(5).Replace("/", "\"); if (-not [System.IO.Path]::IsPathRooted($chemin)) { $chemin = Join-Path $base $chemin }
      $prefs = Join-Path $chemin "prefs.js"
      $lignes = @(); if (Test-Path $prefs) { $lignes = @(Get-Content $prefs -Encoding UTF8 | Where-Object { $_ -match '^user_pref\("(mail\.server\.|mail\.identity\.|mail\.smtpserver\.|mail\.account\.|calendar\.registry\.)' } | Select-Object -First 800 | ForEach-Object { [string]$_ }) }  # #923 : texte brut -- sinon PowerShell 5.1 sérialise chaque ligne en objet {value, PSPath, ReadCount...}
      $thunderbird += [ordered]@{ utilisateur = $p.utilisateur; profil = $chemin; prefs = $lignes }
    }
  }
}

# --- imprimantes
$imprimantes = @(); $ports = @{}
foreach ($pp in (Get-PrinterPort)) { $ports[$pp.Name] = $pp.PrinterHostAddress }
foreach ($i in (Get-Printer)) { $imprimantes += [ordered]@{ nom = $i.Name; pilote = $i.DriverName; port = $i.PortName; adresse = $ports[$i.PortName]; partagee = [bool]$i.Shared; type = [string]$i.Type } }

# --- abonnements et licences : Office Click-to-Run, licences Windows / Office (clé partielle), antivirus
$c2r = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration"
$office = $null
if ($c2r) { $office = [ordered]@{ produits = $c2r.ProductReleaseIds; version = $c2r.VersionToReport; plateforme = $c2r.Platform; canal = $(if ($c2r.UpdateChannel) { $c2r.UpdateChannel } else { $c2r.CDNBaseUrl }); langues = $c2r.ClientCulture } }
$licences = @()
foreach ($l in (Get-CimInstance SoftwareLicensingProduct -Filter "PartialProductKey IS NOT NULL")) {
  $licences += [ordered]@{ nom = $l.Name; description = $l.Description; etat = [int]$l.LicenseStatus; cle_partielle = $l.PartialProductKey; expiration_min = [int]$l.GracePeriodRemaining }
}
$antivirus = @()
foreach ($a in (Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct)) { $antivirus += [ordered]@{ nom = $a.displayName; etat = [int]$a.productState; exe = $a.pathToSignedProductExe; maj = $a.timestamp } }

# --- logiciels : machine (64 et 32 bits) et par utilisateur
$logiciels = @()
$cles = @("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*")
foreach ($p in $profils) { if (Test-Path ("HKU:\" + $p.sid)) { $cles += ("HKU:\" + $p.sid + "\Software\Microsoft\Windows\CurrentVersion\Uninstall\*") } }
foreach ($c in $cles) {
  $portee = $(if ($c -like "HKU:*") { ($profils | Where-Object { $c -like ("HKU:\" + $_.sid + "*") } | Select-Object -First 1).utilisateur } elseif ($c -like "*WOW6432Node*") { "machine-32" } else { "machine" })
  foreach ($v in (Get-ItemProperty $c | Where-Object { $_.DisplayName -and -not $_.SystemComponent -and -not $_.ParentKeyName })) {
    $logiciels += [ordered]@{ nom = $v.DisplayName; version = $v.DisplayVersion; editeur = $v.Publisher; installe = $v.InstallDate; emplacement = Coupe $v.InstallLocation 200; portee = $portee }
  }
}

# --- diagnostic : journaux Système et Application (erreurs et avertissements), regroupés
function Regroupe($log, $niveaux, $max) {
  $ev = @(Get-WinEvent -FilterHashtable @{ LogName = $log; Level = $niveaux; StartTime = $depuis } -MaxEvents $max)
  $g = @{}
  foreach ($e in $ev) {
    $k = $e.ProviderName + "|" + $e.Id
    if (-not $g.ContainsKey($k)) { $g[$k] = [ordered]@{ journal = $log; source = $e.ProviderName; id = $e.Id; niveau = [int]$e.Level; nombre = 0; premier = $null; dernier = Iso $e.TimeCreated; exemple = Coupe $e.Message 400 } }
    $g[$k].nombre += 1; $g[$k].premier = Iso $e.TimeCreated
  }
  return @($g.Values)
}
$groupes = @(Regroupe "System" @(1, 2, 3) 6000) + @(Regroupe "Application" @(1, 2) 4000)

# chronologie des évènements critiques (arrêts brutaux, écrans bleus, erreurs matérielles, disque, diagnostic mémoire)
$cles_crit = @{ "Microsoft-Windows-Kernel-Power" = @(41); "EventLog" = @(6008); "Microsoft-Windows-WER-SystemErrorReporting" = @(1001); "BugCheck" = @(1001)
  "Microsoft-Windows-WHEA-Logger" = @(); "disk" = @(7, 11, 51, 153); "Ntfs" = @(55, 98, 140); "volmgr" = @(161, 162); "storahci" = @(129); "stornvme" = @(11, 129)
  "Display" = @(4101); "Microsoft-Windows-Resource-Exhaustion-Detector" = @(2004); "Microsoft-Windows-MemoryDiagnostics-Results" = @(1101, 1201, 1102, 1202) }
$critiques = @()
# (un fournisseur absent du poste ferait échouer tout le filtre : on filtre par numéros, puis par source ici)
$ids_crit = @(41, 6008, 1001, 7, 11, 51, 153, 55, 98, 140, 161, 162, 129, 4101, 2004, 1101, 1201, 1102, 1202)
$evc = @(Get-WinEvent -FilterHashtable @{ LogName = "System"; StartTime = $depuis; Id = $ids_crit } -MaxEvents 3000)
$evc += @(Get-WinEvent -FilterHashtable @{ LogName = "System"; StartTime = $depuis; ProviderName = "Microsoft-Windows-WHEA-Logger" } -MaxEvents 500)
foreach ($e in $evc) {
  $ids = $cles_crit[$e.ProviderName]
  if ($null -eq $ids) { continue }
  if ($ids.Count -gt 0 -and -not ($ids -contains $e.Id)) { continue }
  $critiques += [ordered]@{ t = Iso $e.TimeCreated; source = $e.ProviderName; id = $e.Id; niveau = [int]$e.Level; message = Coupe $e.Message 300 }
}
# plantages et blocages d'applications : nom de l'application (propriété 0, indépendante de la langue)
$plantages = @()
foreach ($e in (Get-WinEvent -FilterHashtable @{ LogName = "Application"; StartTime = $depuis; Id = @(1000, 1002) } -MaxEvents 2000)) {
  if ($e.ProviderName -in @("Application Error", "Application Hang")) { $plantages += [ordered]@{ t = Iso $e.TimeCreated; type = $(if ($e.Id -eq 1000) { "plantage" } else { "blocage" }); application = [string]$e.Properties[0].Value; module = $(if ($e.Id -eq 1000) { [string]$e.Properties[3].Value } else { $null }) } }
}

# vidages mémoire, disques (fiabilité), volumes, indice de stabilité, températures, démarrage
$vidages = @(); foreach ($f in (Get-ChildItem "C:\Windows\Minidump\*.dmp")) { $vidages += [ordered]@{ fichier = $f.Name; t = Iso $f.LastWriteTime; octets = [int64]$f.Length } }
$memdmp = Get-Item "C:\Windows\MEMORY.DMP"
$disques = @()
foreach ($d in (Get-PhysicalDisk)) {
  $r = $d | Get-StorageReliabilityCounter
  $disques += [ordered]@{ modele = $d.FriendlyName; media = [string]$d.MediaType; bus = [string]$d.BusType; sante = [string]$d.HealthStatus; etat = [string]$d.OperationalStatus
    temperature = $r.Temperature; temperature_max = $r.TemperatureMax; usure = $r.Wear; erreurs_lecture = $r.ReadErrorsTotal; erreurs_ecriture = $r.WriteErrorsTotal
    erreurs_lecture_non_corrigees = $r.ReadErrorsUncorrected; heures = $r.PowerOnHours; demarrages = $r.StartStopCycleCount }
}
$volumes = @(); foreach ($v in (Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq "Fixed" })) { $volumes += [ordered]@{ lettre = [string]$v.DriveLetter + ":"; systeme_fichiers = $v.FileSystem; octets = [int64]$v.Size; libre = [int64]$v.SizeRemaining; sante = [string]$v.HealthStatus } }
$stabilite = @(); foreach ($s in (Get-CimInstance Win32_ReliabilityStabilityMetrics | Sort-Object TimeGenerated -Descending | Select-Object -First 30)) { $stabilite += [ordered]@{ t = Iso $s.TimeGenerated; indice = [double]$s.SystemStabilityIndex } }
$temperatures = @(); foreach ($z in (Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature)) { $temperatures += [ordered]@{ zone = $z.InstanceName; celsius = [math]::Round($z.CurrentTemperature / 10 - 273.15, 1) } }
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem

[ordered]@{
  jours = $Jours; nom = $env:COMPUTERNAME; systeme = $os.Caption; version = $os.Version; demarrage = Iso $os.LastBootUpTime
  fabricant = $cs.Manufacturer; modele = $cs.Model; memoire_octets = [int64]$cs.TotalPhysicalMemory; domaine = $cs.Domain
  profils = $profils; partages = $partages; lecteurs = $lecteurs; raccourcis_reseau = $raccourcis; imprimantes = $imprimantes
  office = $office; identites_office = $identites; outlook = $outlook; fichiers_outlook = $pst; thunderbird = $thunderbird
  licences = $licences; antivirus = $antivirus; logiciels = $logiciels
  evenements = $groupes; critiques = $critiques; plantages = $plantages; vidages = $vidages; memory_dmp = $(if ($memdmp) { Iso $memdmp.LastWriteTime } else { $null })
  disques = $disques; volumes = $volumes; stabilite = $stabilite; temperatures = $temperatures; partiel = $partiel
} | ConvertTo-Json -Depth 6 -Compress
