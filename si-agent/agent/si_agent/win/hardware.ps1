# si-agent (#440) -- matériel et logiciels d'un hôte Windows (inventaire) :
# machine, BIOS, carte mère, CPU, mémoire, disques physiques, cartes réseau,
# logiciels installés (registre). UN objet JSON.
$ErrorActionPreference = "SilentlyContinue"
$partial = New-Object System.Collections.ArrayList
function Iso($d) { if ($d) { try { return ([datetime]$d).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") } catch { return $null } } return $null }

$cs = Get-CimInstance Win32_ComputerSystem
$csp = Get-CimInstance Win32_ComputerSystemProduct
$bios = Get-CimInstance Win32_BIOS
$bb = Get-CimInstance Win32_BaseBoard
$cpu = @(Get-CimInstance Win32_Processor)
if (-not $cs) { [void]$partial.Add("computersystem") }
if (-not $bios) { [void]$partial.Add("bios") }

$cpuInfo = $null
if ($cpu.Count -gt 0) {
  $c0 = $cpu[0]
  $cores = ($cpu | Measure-Object -Property NumberOfCores -Sum).Sum
  $logical = ($cpu | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
  $cpuInfo = [ordered]@{
    model = $c0.Name.Trim(); sockets = $cpu.Count; cores = [int]$cores; cpus = [int]$logical
    cores_per_socket = [int]$c0.NumberOfCores
    threads_per_core = $(if ($c0.NumberOfCores -gt 0) { [int]($c0.NumberOfLogicalProcessors / $c0.NumberOfCores) } else { $null })
    mhz_max = [int]$c0.MaxClockSpeed; arch = $env:PROCESSOR_ARCHITECTURE
    hypervisor = $(if ($cs -and $cs.HypervisorPresent) { "present" } else { $null })
  }
} else { [void]$partial.Add("processor") }

$disks = @()
$media = @{}
$pd = Get-PhysicalDisk
if ($pd) { foreach ($d in $pd) { $media[[string]$d.DeviceId] = [ordered]@{ media = [string]$d.MediaType; bus = [string]$d.BusType; health = [string]$d.HealthStatus } } }
$dd = Get-CimInstance Win32_DiskDrive
if ($dd) {
  foreach ($d in $dd) {
    $idx = [string]$d.Index
    $m = $media[$idx]
    $disks += [ordered]@{
      name = $d.DeviceID; model = $d.Model; serial = $(if ($d.SerialNumber) { $d.SerialNumber.Trim() } else { $null })
      size_bytes = $(if ($d.Size) { [int64]$d.Size } else { $null }); interface = $d.InterfaceType
      media = $(if ($m) { $m.media } else { $d.MediaType }); bus = $(if ($m) { $m.bus } else { $null }); health = $(if ($m) { $m.health } else { $null })
    }
  }
} else { [void]$partial.Add("diskdrive") }

$nics = @()
$na = Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter -and $_.MACAddress }
if ($na) {
  foreach ($n in $na) {
    $nics += [ordered]@{ name = $(if ($n.NetConnectionID) { $n.NetConnectionID } else { $n.Name }); description = $n.Name; mac = $n.MACAddress
      state = $(if ($n.NetConnectionStatus -eq 2) { "up" } else { "down" }); speed_mbps = $(if ($n.Speed -and $n.NetConnectionStatus -eq 2) { [int]($n.Speed / 1MB) } else { $null }) }
  }
}

$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
$monitors = @(Get-CimInstance Win32_DesktopMonitor | ForEach-Object { $_.Name })

$software = @()
$keys = @("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*")
foreach ($k in $keys) {
  Get-ItemProperty $k | Where-Object { $_.DisplayName -and -not $_.SystemComponent } | ForEach-Object {
    $software += [ordered]@{ name = $_.DisplayName; version = [string]$_.DisplayVersion; publisher = [string]$_.Publisher; installed = [string]$_.InstallDate }
  }
}
$software = @($software | Sort-Object name -Unique | Select-Object -First 400)

[ordered]@{
  vendor = $(if ($cs) { $cs.Manufacturer } else { $null }); product = $(if ($cs) { $cs.Model } else { $null })
  product_version = $(if ($csp) { $csp.Version } else { $null }); serial = $(if ($bios) { $bios.SerialNumber } else { $null })
  uuid = $(if ($csp) { $csp.UUID } else { $null }); chassis = $(if ($cs) { [string]$cs.PCSystemType } else { $null })
  bios = $(if ($bios) { "$($bios.Manufacturer) $($bios.SMBIOSBIOSVersion) ($(Iso $bios.ReleaseDate))" } else { $null })
  board = $(if ($bb) { "$($bb.Manufacturer) $($bb.Product)" } else { $null })
  cpu = $cpuInfo
  memory_total_bytes = $(if ($cs) { [int64]$cs.TotalPhysicalMemory } else { $null })
  disks = $disks; nics = $nics; gpus = $gpus; monitors = $monitors
  virtualization = $(if ($cs -and $cs.HypervisorPresent) { "hypervisor" } else { "none" })
  software = $software; software_count = $software.Count
  partial = @($partial)
} | ConvertTo-Json -Depth 6 -Compress
