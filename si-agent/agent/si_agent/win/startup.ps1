# si-agent -- lanceurs au démarrage (livraison #613) : un objet JSON
# { items: [ {kind, scope, name, command, enabled, location} ], partial: [] }
# kind : run | runonce | folder | task | service ; scope : machine | user.
# Lecture seule. L'état activé/désactivé des clés Run et des dossiers Démarrage
# vient de Explorer\StartupApproved (même source que le Gestionnaire des tâches).
$ErrorActionPreference = "SilentlyContinue"
$items = New-Object System.Collections.ArrayList
$partial = New-Object System.Collections.ArrayList

function Approved($hive, $sub) {
  $m = @{}
  $k = Get-Item -Path "$hive\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\$sub" -ErrorAction SilentlyContinue
  if ($k) {
    foreach ($n in $k.GetValueNames()) {
      $v = $k.GetValue($n)
      if ($v -is [byte[]] -and $v.Length -gt 0) { $m[$n] = (($v[0] -band 1) -eq 0) } else { $m[$n] = $true }
    }
  }
  return $m
}

foreach ($pair in @(@("HKLM:", "machine"), @("HKCU:", "user"))) {
  $hive = $pair[0]; $scope = $pair[1]
  $approvedRun = Approved $hive "Run"
  foreach ($sub in @("Run", "RunOnce")) {
    foreach ($path in @("$hive\Software\Microsoft\Windows\CurrentVersion\$sub", "$hive\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\$sub")) {
      $k = Get-Item -Path $path -ErrorAction SilentlyContinue
      if (-not $k) { continue }
      foreach ($n in $k.GetValueNames()) {
        if ($n -eq "") { continue }
        $enabled = $true
        if ($sub -eq "Run" -and $approvedRun.ContainsKey($n)) { $enabled = $approvedRun[$n] }
        [void]$items.Add(@{ kind = $sub.ToLower(); scope = $scope; name = $n; command = [string]$k.GetValue($n); enabled = $enabled; location = $path })
      }
    }
  }
  $approvedFolder = Approved $hive "StartupFolder"
  $folder = if ($scope -eq "machine") { [Environment]::GetFolderPath("CommonStartup") } else { [Environment]::GetFolderPath("Startup") }
  if ($folder -and (Test-Path $folder)) {
    foreach ($f in Get-ChildItem -Path $folder -File) {
      if ($f.Name -eq "desktop.ini") { continue }
      $enabled = $true
      if ($approvedFolder.ContainsKey($f.Name)) { $enabled = $approvedFolder[$f.Name] }
      $target = $f.FullName
      if ($f.Extension -eq ".lnk") {
        try { $sh = New-Object -ComObject WScript.Shell; $lnk = $sh.CreateShortcut($f.FullName); $target = ($lnk.TargetPath + " " + $lnk.Arguments).Trim() } catch {}
      }
      [void]$items.Add(@{ kind = "folder"; scope = $scope; name = $f.Name; command = $target; enabled = $enabled; location = $folder })
    }
  }
}

# Tâches planifiées déclenchées à l'ouverture de session ou au démarrage (hors \Microsoft\)
try {
  foreach ($t in Get-ScheduledTask | Where-Object { $_.TaskPath -notlike "\Microsoft\*" }) {
    $trig = @($t.Triggers | Where-Object { $_.CimClass.CimClassName -match "Logon|Boot" })
    if ($trig.Count -eq 0) { continue }
    $act = @($t.Actions | ForEach-Object { ($_.Execute + " " + $_.Arguments).Trim() }) -join " ; "
    $when = ($trig | ForEach-Object { if ($_.CimClass.CimClassName -match "Boot") { "démarrage" } else { "ouverture de session" } }) -join ", "
    [void]$items.Add(@{ kind = "task"; scope = "machine"; name = ($t.TaskPath + $t.TaskName); command = $act; enabled = ($t.State -ne "Disabled"); location = $when; user = $t.Principal.UserId })
  }
} catch { [void]$partial.Add("tasks") }

# Services en démarrage automatique, hors éditeur Microsoft
try {
  $svcs = Get-CimInstance Win32_Service | Where-Object { $_.StartMode -like "Auto*" }
  foreach ($s in $svcs) {
    $path = [string]$s.PathName
    if ($path -match "\\Windows\\" -and $path -notmatch "si-agent") { continue }
    [void]$items.Add(@{ kind = "service"; scope = "machine"; name = $s.Name; command = $path; enabled = $true; location = $s.DisplayName; state = $s.State; delayed = ($s.StartMode -eq "Auto (Delayed Start)"); user = $s.StartName })
  }
} catch { [void]$partial.Add("services") }

@{ items = $items.ToArray(); partial = $partial.ToArray(); collected_at = (Get-Date).ToString("o") } | ConvertTo-Json -Depth 4 -Compress
