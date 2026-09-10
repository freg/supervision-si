# si-agent (#440) -- activité de l'hôte Windows : processus (CPU sur 1 s,
# mémoire), sessions ouvertes, dernières ouvertures de session, services en
# cours. UN objet JSON. Windows PowerShell 5.1 / PowerShell 7.
$ErrorActionPreference = "SilentlyContinue"
$partial = New-Object System.Collections.ArrayList
function Iso($d) { if ($d) { try { return ([datetime]$d).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") } catch { return $null } } return $null }

$cpus = [Environment]::ProcessorCount
$p1 = @{}
Get-Process | ForEach-Object { $p1[[int]$_.Id] = $_.CPU }
Start-Sleep -Seconds 1
$now = Get-Date
$procs = Get-Process
$rows = @()
foreach ($p in $procs) {
  $delta = 0.0
  if ($p1.ContainsKey([int]$p.Id) -and $p.CPU -ne $null -and $p1[[int]$p.Id] -ne $null) { $delta = [double]$p.CPU - [double]$p1[[int]$p.Id] }
  $pct = [math]::Round(100.0 * $delta / [math]::Max(1, $cpus), 1)
  $elapsed = $null
  if ($p.StartTime) { $elapsed = [int](($now - $p.StartTime).TotalSeconds) }
  $rows += [pscustomobject]@{ pid = [int]$p.Id; command = $p.ProcessName; cpu_percent = $pct; rss_bytes = [int64]$p.WorkingSet64; elapsed_seconds = $elapsed; user = $null }
}
if (-not $procs) { [void]$partial.Add("processes") }
$topCpu = @($rows | Sort-Object cpu_percent -Descending | Select-Object -First 8)
$topMem = @($rows | Sort-Object rss_bytes -Descending | Select-Object -First 8)

# sessions interactives : `quser` (colonnes à largeur fixe, libellés localisés -> lu tel quel côté Python)
$quser = & quser 2>$null
$sessions_raw = @($quser | ForEach-Object { [string]$_ })
$logon = Get-CimInstance Win32_LogonSession | Where-Object { $_.LogonType -in 2, 10, 11 }
$sessions = @()
if ($logon) {
  foreach ($s in $logon) {
    $u = Get-CimAssociatedInstance -InputObject $s -ResultClassName Win32_UserAccount | Select-Object -First 1
    if ($u) { $sessions += [ordered]@{ user = "$($u.Domain)\$($u.Name)"; type = [int]$s.LogonType; since = Iso $s.StartTime } }
  }
}

# dernières ouvertures de session réussies (journal Sécurité, 4624, interactif/RDP) -- nécessite des droits d'administration
$logins = @()
$ev = Get-WinEvent -FilterHashtable @{ LogName = "Security"; Id = 4624 } -MaxEvents 200
if ($ev) {
  foreach ($e in $ev) {
    $x = [xml]$e.ToXml()
    $data = @{}
    foreach ($d in $x.Event.EventData.Data) { $data[$d.Name] = $d.'#text' }
    if ($data["LogonType"] -in "2", "10", "11") {
      $logins += [ordered]@{ user = "$($data['TargetDomainName'])\$($data['TargetUserName'])"; type = [int]$data["LogonType"]; from = $data["IpAddress"]; at = Iso $e.TimeCreated }
      if ($logins.Count -ge 10) { break }
    }
  }
}

$running = @(Get-Service | Where-Object { $_.Status -eq "Running" } | ForEach-Object { $_.Name })
$pendingUpdates = $null
try {
  $session = New-Object -ComObject Microsoft.Update.Session
  $searcher = $session.CreateUpdateSearcher()
  $result = $searcher.Search("IsInstalled=0 and IsHidden=0")
  if ($result) { $pendingUpdates = [int]$result.Updates.Count }
} catch { }

[ordered]@{
  process_count = $(if ($procs) { @($procs).Count } else { $null })
  top_cpu = $topCpu; top_memory = $topMem
  sessions = $sessions; sessions_raw = $sessions_raw; last_logins = $logins
  running_services = $running; running_services_count = $running.Count
  updates_available = $pendingUpdates
  partial = @($partial)
} | ConvertTo-Json -Depth 6 -Compress
