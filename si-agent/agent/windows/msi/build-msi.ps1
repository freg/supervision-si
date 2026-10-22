<#
si-agent -- construction du MSI (livraison #824, BACKLOG 133). Sur un Windows x64 (poste de build ou VM du pool) :
  1. .NET 8 SDK puis WiX : dotnet tool install --global wix ; wix extension add -g WixToolset.Util.wixext
  2. depuis la racine de l'archive de l'agent (si_agent, plugins, windows côte à côte) ou du dépôt (si-agent\agent) :
       powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\msi\build-msi.ps1
     -> windows\msi\out\si-agent-<version>.msi
Le Python embarqué (python.org, empreinte SHA-256 vérifiée) est inclus : l'installation ne télécharge rien.
Signature (recommandée, déploiement GPO / Intune) : -SignCert <empreinte du certificat de signature de code du magasin>.
#>
[CmdletBinding()]
param(
  [string]$PythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip",
  [string]$PythonSha256 = "",          # vide : l'empreinte est affichée, à reporter ici pour les constructions suivantes
  [string]$SignCert = "",
  [string]$Out = (Join-Path $PSScriptRoot "out")
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)          # ...\agent (si_agent, plugins, windows)
if (-not (Test-Path (Join-Path $root "si_agent\__init__.py"))) { throw "si_agent introuvable sous $root" }
$version = (Select-String -Path (Join-Path $root "si_agent\__init__.py") -Pattern '__version__\s*=\s*"([\d.]+)"').Matches[0].Groups[1].Value
Write-Host "si-agent $version"
$stage = Join-Path $env:TEMP ("si-agent-msi-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$payload = Join-Path $stage "payload"; $python = Join-Path $stage "python"
New-Item -ItemType Directory -Force -Path $payload, $python, $Out | Out-Null
try {
  foreach ($d in @("si_agent", "plugins", "windows")) { Copy-Item -LiteralPath (Join-Path $root $d) (Join-Path $payload $d) -Recurse -Force }
  Remove-Item (Join-Path $payload "windows\msi") -Recurse -Force -ErrorAction SilentlyContinue
  Get-ChildItem $payload -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
  Get-ChildItem $payload -Recurse -File -Filter "test_*.py" | Remove-Item -Force

  $zip = Join-Path $stage "python.zip"
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $PythonUrl -OutFile $zip -UseBasicParsing
  $got = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
  if ($PythonSha256 -and $got -ne $PythonSha256.ToLower()) { throw "empreinte du Python embarqué différente : $got (attendu $PythonSha256)" }
  if (-not $PythonSha256) { Write-Warning "Python embarqué non vérifié : empreinte $got -- la passer en -PythonSha256 désormais" }
  Expand-Archive -Path $zip -DestinationPath $python -Force
  Remove-Item $zip -Force
  # python3xx._pth borne sys.path : le dossier d'installation (paquet si_agent) est le parent de python\
  Get-ChildItem $python -Filter "python*._pth" | ForEach-Object { Add-Content -Path $_.FullName -Value ".." -Encoding ASCII }

  $msi = Join-Path $Out "si-agent-$version.msi"
  & wix build -arch x64 -ext WixToolset.Util.wixext -d "Version=$version" -bindpath "payload=$payload" -bindpath "python=$python" `
      (Join-Path $PSScriptRoot "si-agent.wxs") -o $msi
  if ($LASTEXITCODE -ne 0) { throw "wix build en échec ($LASTEXITCODE)" }
  if ($SignCert) {
    $signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "x64" } | Select-Object -Last 1
    if (-not $signtool) { throw "signtool.exe introuvable (Windows SDK)" }
    & $signtool.FullName sign /sha1 $SignCert /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /d "si-agent" $msi
    if ($LASTEXITCODE -ne 0) { throw "signature en échec" }
  }
  Write-Host "MSI : $msi ($((Get-Item $msi).Length) octets) ; empreinte SHA-256 $((Get-FileHash -Algorithm SHA256 $msi).Hash.ToLower())"
} finally {
  Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}
