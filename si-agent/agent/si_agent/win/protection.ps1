# si-agent -- pare-feu et antivirus Windows (livraison #633) : état, et bascule du pare-feu
# (par profil) et de la protection en temps réel de Microsoft Defender. Un antivirus tiers
# (AVG, ESET…) n'est pas pilotable ici : il est seulement signalé (Security Center).
# { firewall: [{profile, enabled}], defender: {...} | null, third_party: [...], applied: {...}, errors: [...] }
param([string]$Firewall = "", [string]$Profiles = "Domain,Private,Public", [string]$Defender = "")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$errors = @(); $applied = @{}
if ($Firewall) {
  try {
    $profs = $Profiles.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    Set-NetFirewallProfile -Profile $profs -Enabled ($(if ($Firewall -eq "on") { "True" } else { "False" }))
    $applied.firewall = @{ state = $Firewall; profiles = $profs }
  } catch { $errors += "pare-feu : " + $_.Exception.Message }
}
if ($Defender) {
  try {
    Set-MpPreference -DisableRealtimeMonitoring ($Defender -eq "off")
    $applied.defender = $Defender
  } catch { $errors += "Defender : " + $_.Exception.Message + " (protection contre les falsifications active ? à désactiver dans Sécurité Windows)" }
}
$fw = @()
try { $fw = @(Get-NetFirewallProfile | ForEach-Object { @{ profile = $_.Name; enabled = [bool]$_.Enabled } }) } catch { $errors += "état pare-feu : " + $_.Exception.Message }
$def = $null
try {
  $s = Get-MpComputerStatus
  $def = @{ realtime = [bool]$s.RealTimeProtectionEnabled; antivirus = [bool]$s.AntivirusEnabled; service = [bool]$s.AMServiceEnabled
            tamper_protected = [bool]$s.IsTamperProtected; signatures = $(if ($s.AntivirusSignatureLastUpdated) { $s.AntivirusSignatureLastUpdated.ToUniversalTime().ToString("s") + "Z" } else { $null })
            signature_age_days = [int]$s.AntivirusSignatureAge }
} catch { $def = $null }
$third = @()
try { $third = @(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct | ForEach-Object { @{ name = $_.displayName; state = [int]$_.productState } }) } catch { }
@{ firewall = $fw; defender = $def; third_party = $third; applied = $applied; errors = $errors; checked_at = (Get-Date).ToUniversalTime().ToString("s") + "Z" } | ConvertTo-Json -Depth 5 -Compress
