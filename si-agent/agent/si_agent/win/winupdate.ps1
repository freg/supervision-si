# si-agent -- Windows Update (livraison #633) : état (mises à jour en attente, historique,
# redémarrage requis, réglage automatique) et installation (toutes ou une liste de KB),
# via l'API COM Microsoft.Update (aucun module à installer, fonctionne sous SYSTEM).
# { pending: [{title, kb, size_mb, severity, downloaded, reboot_required, categories}], history: [...],
#   reboot_required, au_level, checked_at, install?: {count, download_result, result, reboot_required, per_update} }
# Codes de résultat COM : 2 = réussi, 3 = réussi avec erreurs, 4 = échec, 5 = annulé.
param([string]$Action = "status", [string]$Kb = "", [string]$Out = "")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function Emit($obj) {
  $json = $obj | ConvertTo-Json -Depth 6 -Compress
  if ($Out) { [IO.File]::WriteAllText($Out, $json, (New-Object Text.UTF8Encoding $false)) } else { Write-Output $json }
}
try {
  $session = New-Object -ComObject Microsoft.Update.Session
  $searcher = $session.CreateUpdateSearcher()
  $result = $searcher.Search("IsInstalled=0 and IsHidden=0")
  $pending = @()
  foreach ($u in $result.Updates) {
    $pending += @{ title = $u.Title; kb = (@($u.KBArticleIDs | ForEach-Object { "KB$_" }) -join ","); size_mb = [math]::Round($u.MaxDownloadSize / 1MB, 1)
                   severity = [string]$u.MsrcSeverity; downloaded = [bool]$u.IsDownloaded; reboot_required = [bool]$u.RebootRequired
                   categories = (@($u.Categories | ForEach-Object { $_.Name }) -join ", ") }
  }
  $hist = @()
  try {
    $n = [math]::Min(20, $searcher.GetTotalHistoryCount())
    if ($n -gt 0) { $hist = @($searcher.QueryHistory(0, $n) | ForEach-Object { @{ date = $_.Date.ToUniversalTime().ToString("s") + "Z"; title = $_.Title; result = [int]$_.ResultCode; operation = [int]$_.Operation } }) }
  } catch { }
  $reboot = $false
  try { $reboot = [bool](New-Object -ComObject Microsoft.Update.SystemInfo).RebootRequired } catch { }
  $au = $null
  try { $au = [int](New-Object -ComObject Microsoft.Update.AutoUpdate).Settings.NotificationLevel } catch { }
  $out = @{ pending = $pending; history = $hist; reboot_required = $reboot; au_level = $au; checked_at = (Get-Date).ToUniversalTime().ToString("s") + "Z" }
  if ($Action -eq "install") {
    $coll = New-Object -ComObject Microsoft.Update.UpdateColl
    $want = @(); if ($Kb) { $want = $Kb.Split(",") | ForEach-Object { $_.Trim().ToUpper().Replace("KB", "") } | Where-Object { $_ } }
    foreach ($u in $result.Updates) {
      $ids = @($u.KBArticleIDs | ForEach-Object { [string]$_ })
      if ($want.Count -eq 0 -or ($want | Where-Object { $ids -contains $_ })) {
        if (-not $u.EulaAccepted) { $u.AcceptEula() }
        [void]$coll.Add($u)
      }
    }
    if ($coll.Count -eq 0) { $out.install = @{ count = 0; message = "aucune mise à jour correspondante" } }
    else {
      $dl = $session.CreateUpdateDownloader(); $dl.Updates = $coll; $dr = $dl.Download()
      $inst = $session.CreateUpdateInstaller(); $inst.Updates = $coll; $ir = $inst.Install()
      $per = @(); for ($i = 0; $i -lt $coll.Count; $i++) { $per += @{ title = $coll.Item($i).Title; result = [int]$ir.GetUpdateResult($i).ResultCode } }
      $out.install = @{ count = $coll.Count; download_result = [int]$dr.ResultCode; result = [int]$ir.ResultCode; reboot_required = [bool]$ir.RebootRequired; per_update = $per }
    }
  }
  Emit $out
} catch {
  Emit @{ error = [string]$_.Exception.Message; checked_at = (Get-Date).ToUniversalTime().ToString("s") + "Z" }
}
