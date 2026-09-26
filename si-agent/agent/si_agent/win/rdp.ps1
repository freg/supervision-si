# si-agent -- Bureau à distance Windows (livraison #636) : état, activation, désactivation
# du RDP INTÉGRÉ (service Terminal Server + règle de pare-feu du groupe « Remote Desktop »).
# L'administrateur se connecte ensuite avec SES identifiants ; aucun compte ni mot de passe
# n'est créé ou stocké ici. La NLA (authentification au niveau réseau) reste EXIGÉE par défaut.
# { enabled, nla, firewall_enabled, port, rdp_users, applied, errors }
param([string]$Action = "status", [string]$Nla = "on")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$errors = @(); $applied = @{}
$TS = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
$RDP = "$TS\WinStations\RDP-Tcp"
try {
  if ($Action -eq "enable") {
    Set-ItemProperty -Path $TS -Name fDenyTSConnections -Value 0 -Type DWord
    Set-ItemProperty -Path $RDP -Name UserAuthentication -Value ($(if ($Nla -eq "off") { 0 } else { 1 })) -Type DWord
    try { Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction Stop; $applied.firewall = $true }
    catch { & netsh advfirewall firewall set rule group="remote desktop" new enable=Yes | Out-Null; $applied.firewall = $true }
    $applied.enabled = $true; $applied.nla = ($Nla -ne "off")
  } elseif ($Action -eq "disable") {
    Set-ItemProperty -Path $TS -Name fDenyTSConnections -Value 1 -Type DWord
    try { Disable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction Stop } catch { & netsh advfirewall firewall set rule group="remote desktop" new enable=No | Out-Null }
    $applied.enabled = $false
  }
} catch { $errors += $_.Exception.Message }
$enabled = $false; $nla = $null; $port = 3389; $fw = $false; $users = @()
try { $enabled = ((Get-ItemProperty -Path $TS -Name fDenyTSConnections).fDenyTSConnections -eq 0) } catch { }
try { $nla = ((Get-ItemProperty -Path $RDP -Name UserAuthentication).UserAuthentication -eq 1) } catch { }
try { $port = [int](Get-ItemProperty -Path $RDP -Name PortNumber -ErrorAction Stop).PortNumber } catch { }
try { $fw = [bool](Get-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction Stop | Where-Object { $_.Enabled -eq "True" } | Select-Object -First 1) } catch { }
try { $users = @((Get-LocalGroupMember -Group "Remote Desktop Users" -ErrorAction Stop | ForEach-Object { [string]$_.Name })) } catch { }
@{ enabled = $enabled; nla = $nla; port = $port; firewall_enabled = $fw; rdp_users = $users; applied = $applied; errors = $errors
   checked_at = (Get-Date).ToUniversalTime().ToString("s") + "Z" } | ConvertTo-Json -Depth 4 -Compress
