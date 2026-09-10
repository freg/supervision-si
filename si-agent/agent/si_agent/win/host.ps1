# si-agent (#440) -- collecte `host` sous Windows 10/11 : UN objet JSON sur
# la sortie standard, lu par si_agent/winhost.py. Compatible Windows
# PowerShell 5.1 (livré avec Windows) et PowerShell 7. Chaque section est
# protégée : une source absente met son nom dans `partial`, jamais un plantage.
$ErrorActionPreference = "SilentlyContinue"
$partial = New-Object System.Collections.ArrayList
function Iso($d) { if ($d) { try { return ([datetime]$d).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") } catch { return $null } } return $null }

# --- système ---------------------------------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor
$uptime = $null
if ($os -and $os.LastBootUpTime) { $uptime = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalSeconds, 0) }
$rebootKeys = @(
  "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
  "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"
)
$rebootRequired = $false
foreach ($k in $rebootKeys) { if (Test-Path $k) { $rebootRequired = $true } }
$pfro = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name PendingFileRenameOperations
if ($pfro -and $pfro.PendingFileRenameOperations) { $rebootRequired = $true }
$cpuModel = $null; $cpus = $null; $cpuLoad = $null
if ($cpu) {
  $first = @($cpu)[0]
  $cpuModel = $first.Name
  $cpus = (@($cpu) | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
  $loads = @($cpu | Where-Object { $_.LoadPercentage -ne $null } | ForEach-Object { $_.LoadPercentage })
  if ($loads.Count -gt 0) { $cpuLoad = [math]::Round(($loads | Measure-Object -Average).Average, 1) }
}
$system = [ordered]@{
  hostname = $env:COMPUTERNAME
  os = $(if ($os) { $os.Caption } else { $null })
  os_version = $(if ($os) { $os.Version } else { $null })
  build = $(if ($os) { $os.BuildNumber } else { $null })
  display_version = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -Name DisplayVersion).DisplayVersion
  arch = $(if ($os) { $os.OSArchitecture } else { $null })
  install_date = Iso $(if ($os) { $os.InstallDate } else { $null })
  last_boot = Iso $(if ($os) { $os.LastBootUpTime } else { $null })
  uptime_seconds = $uptime
  cpu_model = $cpuModel
  cpus = $cpus
  domain = $(if ($cs) { $cs.Domain } else { $null })
  part_of_domain = $(if ($cs) { [bool]$cs.PartOfDomain } else { $null })
  reboot_required = $rebootRequired
}
if (-not $os) { [void]$partial.Add("os") }

# --- mémoire ---------------------------------------------------------------
$pf = Get-CimInstance Win32_PageFileUsage
$memory = [ordered]@{
  total_bytes = $(if ($os) { [int64]$os.TotalVisibleMemorySize * 1024 } else { $null })
  available_bytes = $(if ($os) { [int64]$os.FreePhysicalMemory * 1024 } else { $null })
  page_total_bytes = $(if ($pf) { [int64]((@($pf) | Measure-Object -Property AllocatedBaseSize -Sum).Sum) * 1MB } else { $null })
  page_used_bytes = $(if ($pf) { [int64]((@($pf) | Measure-Object -Property CurrentUsage -Sum).Sum) * 1MB } else { $null })
}

# --- disques (DriveType 2 amovible, 3 local, 4 réseau) ----------------------
$disks = @()
$ld = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -in 2, 3, 4 }
if ($ld) {
  foreach ($d in $ld) {
    $disks += [ordered]@{
      mountpoint = $d.DeviceID + "\"
      label = $d.VolumeName
      fstype = $d.FileSystem
      drive_type = [int]$d.DriveType
      provider = $d.ProviderName
      total_bytes = $(if ($d.Size) { [int64]$d.Size } else { $null })
      free_bytes = $(if ($d.FreeSpace -ne $null) { [int64]$d.FreeSpace } else { $null })
    }
  }
} else { [void]$partial.Add("disks") }

# --- services automatiques arrêtés ------------------------------------------
$svc = Get-CimInstance Win32_Service
$failed = @(); $runningCount = $null
if ($svc) {
  $failed = @($svc | Where-Object { $_.StartMode -eq "Auto" -and $_.State -ne "Running" -and -not $_.DelayedAutoStart } | ForEach-Object { $_.Name })
  $runningCount = @($svc | Where-Object { $_.State -eq "Running" }).Count
} else { [void]$partial.Add("services") }

# --- ports en écoute ---------------------------------------------------------
$ports = @()
$procNames = @{}
Get-Process | ForEach-Object { $procNames[[int]$_.Id] = $_.ProcessName }
$tcp = Get-NetTCPConnection -State Listen
if ($tcp) {
  foreach ($c in $tcp) { $ports += [ordered]@{ proto = "tcp"; address = $c.LocalAddress; port = [int]$c.LocalPort; pid = [int]$c.OwningProcess; process = $procNames[[int]$c.OwningProcess] } }
} else { [void]$partial.Add("tcp-listen") }
$udp = Get-NetUDPEndpoint
if ($udp) {
  foreach ($c in $udp) { $ports += [ordered]@{ proto = "udp"; address = $c.LocalAddress; port = [int]$c.LocalPort; pid = [int]$c.OwningProcess; process = $procNames[[int]$c.OwningProcess] } }
}

# --- journal des événements : erreurs/critiques des 24 h ----------------------
$logs = @()
$events = Get-WinEvent -FilterHashtable @{ LogName = @("System", "Application"); Level = @(1, 2); StartTime = (Get-Date).AddHours(-24) } -MaxEvents 40
if ($events) {
  foreach ($e in $events) {
    $msg = $e.Message; if ($msg) { $msg = ($msg -replace "\s+", " ").Trim(); if ($msg.Length -gt 240) { $msg = $msg.Substring(0, 240) } }
    $logs += [ordered]@{ time = Iso $e.TimeCreated; log = $e.LogName; source = $e.ProviderName; id = [int]$e.Id; level = [int]$e.Level; message = $msg }
  }
}

# --- comptes : administrateurs locaux, utilisateurs locaux actifs -----------------
$admins = @(); $users = @()
$grp = Get-LocalGroupMember -SID "S-1-5-32-544"
if ($grp) { $admins = @($grp | ForEach-Object { $_.Name }) }
else {
  $nl = & net localgroup Administrators 2>$null
  if ($nl) { $admins = @($nl | Select-Object -Skip 6 | Where-Object { $_ -and $_ -notmatch "^-+$" -and $_ -notmatch "^La commande|^The command" } ) }
}
$lu = Get-LocalUser
if ($lu) { $users = @($lu | Where-Object { $_.Enabled } | ForEach-Object { $_.Name }) }
$accounts = [ordered]@{ admins = $admins; local_users = $users; console_user = $(if ($cs) { $cs.UserName } else { $null }) }

# --- mises à jour, Defender, pare-feu ------------------------------------------
$hf = Get-CimInstance Win32_QuickFixEngineering | Sort-Object InstalledOn -Descending | Select-Object -First 1
$updates = [ordered]@{ pending_reboot = $rebootRequired; last_hotfix = $(if ($hf) { $hf.HotFixID } else { $null }); last_hotfix_date = Iso $(if ($hf) { $hf.InstalledOn } else { $null }) }
$defender = $null
$mp = Get-MpComputerStatus
if ($mp) {
  $defender = [ordered]@{ enabled = [bool]$mp.AntivirusEnabled; realtime = [bool]$mp.RealTimeProtectionEnabled; signatures_age_days = [int]$mp.AntivirusSignatureAge; last_quick_scan = Iso $mp.QuickScanEndTime }
}
$firewall = @()
$fw = Get-NetFirewallProfile
if ($fw) { foreach ($p in $fw) { $firewall += [ordered]@{ profile = $p.Name; enabled = [bool]$p.Enabled } } }
$bl = Get-BitLockerVolume -MountPoint "C:"
$bitlocker = $(if ($bl) { [string]$bl.ProtectionStatus } else { $null })

$out = [ordered]@{
  system = $system; cpu = [ordered]@{ percent = $cpuLoad }; memory = $memory; disks = $disks
  services = [ordered]@{ failed = $failed; running_count = $runningCount }
  ports = $ports; logs = $logs; accounts = $accounts
  windows = [ordered]@{ updates = $updates; defender = $defender; firewall = $firewall; bitlocker_c = $bitlocker }
  partial = @($partial)
}
$out | ConvertTo-Json -Depth 6 -Compress
