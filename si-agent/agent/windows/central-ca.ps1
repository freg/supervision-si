<#
  #682 : faisceau de confiance pour un central au certificat PUBLIC (installation -SystemCa).
  Python (embarqué ou non) ne lit que les magasins ROOT et CA de Windows ; les racines que Windows télécharge à la
  demande (magasin AuthRoot, ex. ISRG Root X2 des certificats Let's Encrypt ECDSA) lui sont invisibles -> CERTIFICATE_
  VERIFY_FAILED alors que le navigateur valide. On fait construire la chaîne du central par Windows (ce qui télécharge la
  racine manquante), puis on écrit un faisceau PEM : chaîne du central + magasins Root, AuthRoot et CA de la machine.
  Usage : central-ca.ps1 -Central https://hub.exemple.fr/api/si-agent -Out C:\ProgramData\si-agent\central-ca.crt
  Appelé par install.ps1 (-SystemCa) et par l'agent lui-même quand la vérification échoue (une fois par heure au plus).
#>
param([Parameter(Mandatory = $true)][string]$Central, [Parameter(Mandatory = $true)][string]$Out)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
if (-not ("SiAgentTrustAll" -as [type])) {
  Add-Type -TypeDefinition @"
using System.Net.Security;
public static class SiAgentTrustAll {
  public static RemoteCertificateValidationCallback Callback() { return delegate { return true; }; }
}
"@
}
$u = [Uri]$Central
$port = if ($u.Port -gt 0) { $u.Port } else { 443 }
$chain = @()
try {
  # lecture seule du certificat présenté (la validation est celle de X509Chain juste après, pas ce rappel)
  $t = New-Object Net.Sockets.TcpClient($u.Host, $port)
  try {
    $s = New-Object Net.Security.SslStream($t.GetStream(), $false, ([SiAgentTrustAll]::Callback()))
    $s.AuthenticateAsClient($u.Host)
    $leaf = New-Object Security.Cryptography.X509Certificates.X509Certificate2($s.RemoteCertificate)
    $x = New-Object Security.Cryptography.X509Certificates.X509Chain
    $ok = $x.Build($leaf)
    if (-not $ok) { Write-Warning ("chaîne du central non validée par Windows : " + (($x.ChainStatus | ForEach-Object { $_.StatusInformation.Trim() }) -join " ; ")) }
    $chain = @($x.ChainElements | Select-Object -Skip 1 | ForEach-Object { $_.Certificate })
  } finally { $t.Close() }
} catch { Write-Warning "chaîne du central non lue ($($_.Exception.Message)) : magasins de la machine seulement" }
$seen = @{}
$sb = New-Object Text.StringBuilder
$stores = @(Get-ChildItem Cert:\LocalMachine\Root, Cert:\LocalMachine\AuthRoot, Cert:\LocalMachine\CA -ErrorAction SilentlyContinue)
foreach ($c in @($chain) + $stores) {
  if (-not $c -or -not $c.RawData -or $seen.ContainsKey($c.Thumbprint)) { continue }
  $seen[$c.Thumbprint] = $true
  [void]$sb.Append("-----BEGIN CERTIFICATE-----`n").Append([Convert]::ToBase64String($c.RawData, 'InsertLineBreaks')).Append("`n-----END CERTIFICATE-----`n")
}
$dir = Split-Path $Out -Parent
if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$tmp = "$Out.tmp"
[IO.File]::WriteAllText($tmp, $sb.ToString(), (New-Object Text.ASCIIEncoding))
Move-Item -Force $tmp $Out
Write-Host "faisceau de confiance écrit : $Out ($($seen.Count) certificats, chaîne du central : $($chain.Count))"
