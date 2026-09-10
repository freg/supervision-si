# si-agent (#440) -- vue réseau passive d'un hôte Windows : interfaces et
# adresses, routes, voisins (ARP/NDP), connexions établies, DNS. UN objet
# JSON, aucun paquet émis.
$ErrorActionPreference = "SilentlyContinue"
$partial = New-Object System.Collections.ArrayList

$adapters = @(Get-NetAdapter | ForEach-Object { [ordered]@{ index = [int]$_.ifIndex; name = $_.Name; description = $_.InterfaceDescription; mac = $_.MacAddress; status = [string]$_.Status; mtu = [int]$_.MtuSize; speed = [string]$_.LinkSpeed; virtual = [bool]$_.Virtual } })
if ($adapters.Count -eq 0) { [void]$partial.Add("adapters") }
$addresses = @(Get-NetIPAddress | ForEach-Object { [ordered]@{ index = [int]$_.InterfaceIndex; alias = $_.InterfaceAlias; ip = $_.IPAddress; prefix = [int]$_.PrefixLength; family = [string]$_.AddressFamily; origin = [string]$_.PrefixOrigin; state = [string]$_.AddressState } })
if ($addresses.Count -eq 0) { [void]$partial.Add("addresses") }
$routes = @(Get-NetRoute | ForEach-Object { [ordered]@{ dst = $_.DestinationPrefix; gateway = $_.NextHop; alias = $_.InterfaceAlias; index = [int]$_.InterfaceIndex; metric = [int]$_.RouteMetric; protocol = [string]$_.Protocol; family = [string]$_.AddressFamily } })
if ($routes.Count -eq 0) { [void]$partial.Add("routes") }
$neighbors = @(Get-NetNeighbor | Where-Object { $_.State -ne "Permanent" -and $_.LinkLayerAddress -and $_.LinkLayerAddress -ne "00-00-00-00-00-00" } | ForEach-Object { [ordered]@{ ip = $_.IPAddress; mac = $_.LinkLayerAddress; alias = $_.InterfaceAlias; state = [string]$_.State; family = [string]$_.AddressFamily } })
$procNames = @{}
Get-Process | ForEach-Object { $procNames[[int]$_.Id] = $_.ProcessName }
$conns = @(Get-NetTCPConnection -State Established | ForEach-Object { [ordered]@{ proto = "tcp"; local_ip = $_.LocalAddress; local_port = [int]$_.LocalPort; remote_ip = $_.RemoteAddress; remote_port = [int]$_.RemotePort; pid = [int]$_.OwningProcess; process = $procNames[[int]$_.OwningProcess] } })
$dnsServers = @()
Get-DnsClientServerAddress | Where-Object { $_.ServerAddresses } | ForEach-Object { foreach ($s in $_.ServerAddresses) { if ($dnsServers -notcontains $s) { $dnsServers += $s } } }
$suffix = @()
$g = Get-DnsClientGlobalSetting
if ($g -and $g.SuffixSearchList) { $suffix = @($g.SuffixSearchList) }
$conn = Get-DnsClient | Where-Object { $_.ConnectionSpecificSuffix } | ForEach-Object { $_.ConnectionSpecificSuffix }
foreach ($s in @($conn)) { if ($s -and $suffix -notcontains $s) { $suffix += $s } }

[ordered]@{
  adapters = $adapters; addresses = $addresses; routes = $routes; neighbors = $neighbors; connections = $conns
  dns = [ordered]@{ servers = $dnsServers; search = $suffix }
  partial = @($partial)
} | ConvertTo-Json -Depth 6 -Compress
