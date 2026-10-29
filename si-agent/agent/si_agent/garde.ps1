<#
si-agent #919 -- garde d'exécution des commandes à distance (analyse technique depuis le hub).

  -Mode lecture       : le script est analysé AVANT exécution (arbre syntaxique PowerShell) et refusé s'il peut
                        modifier le poste : seules passent les cmdlets Get-* et de mise en forme, une liste
                        d'exécutables de diagnostic aux arguments contrôlés (ipconfig /all, chkdsk /scan,
                        sfc /verifyonly, dism /scanhealth, net user <nom>...), sans écriture de fichier
                        (redirection > autre que $null), sans appel dynamique (& $x, Invoke-Expression,
                        [scriptblock]::Create), sans méthode qui agit (.Kill(), .Delete(), .Create()...) ni
                        affectation de propriété d'objet.
  -Mode intervention  : exécuté tel quel (le hub demande confirmation ; tout est journalisé).
  -Verifier           : analyse seulement (« SI-SHELL-OK » ou les motifs de refus), rien n'est exécuté.

Sortie : texte UTF-8, largeur 300 colonnes, flux d'erreur inclus. Code de sortie 3 = refus (lignes « SI-SHELL-REFUS : »).
#>
param(
  [Parameter(Mandatory = $true)][string]$Script,
  [ValidateSet("lecture", "intervention")][string]$Mode = "lecture",
  [switch]$Verifier
)
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$src = [IO.File]::ReadAllText($Script, [Text.Encoding]::UTF8)
$jetons = $null; $erreurs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($src, [ref]$jetons, [ref]$erreurs)
if ($erreurs -and $erreurs.Count -gt 0) {
  foreach ($e in $erreurs) { "SI-SHELL-REFUS : syntaxe, ligne $($e.Extent.StartLineNumber) : $($e.Message)" }
  exit 3
}

# ---------------------------------------------------------------------------------------------------------------
# Règles du mode lecture
# ---------------------------------------------------------------------------------------------------------------
$CmdletsPermises = @(
  'ForEach-Object', 'Where-Object', 'Select-Object', 'Sort-Object', 'Group-Object', 'Measure-Object', 'Compare-Object',
  'Format-Table', 'Format-List', 'Format-Wide', 'Format-Custom', 'Out-String', 'Out-Null',
  'Write-Output', 'Write-Host', 'Write-Verbose', 'Write-Warning', 'Write-Information',
  'Test-Path', 'Test-Connection', 'Test-NetConnection', 'Resolve-DnsName', 'Resolve-Path', 'Join-Path', 'Split-Path',
  'ConvertTo-Json', 'ConvertFrom-Json', 'ConvertTo-Csv', 'ConvertFrom-Csv', 'ConvertTo-Html', 'ConvertTo-Xml',
  'Select-String', 'Select-Xml', 'Start-Sleep', 'New-TimeSpan', 'Measure-Command'
)
$GetRefusees = @('Get-Credential')

# Exécutables de diagnostic : motif de refus (texte) ou $null si les arguments sont acceptés. $a = arguments en minuscules.
function Tous($a, $motif) { foreach ($x in $a) { if ($x -notmatch $motif) { return $false } }; return $true }
$Exe = @{
  'ipconfig'   = { param($a) if (Tous $a '^/(all|displaydns|showclassid6?|allcompartments)$') { $null } else { "ipconfig : seuls /all, /displaydns, /showclassid" } }
  'netstat'    = { param($a) $null }
  'arp'        = { param($a) if (Tous $a '^-(a|g|v|n)$|^[0-9a-f.:]+$') { $null } else { "arp : lecture seulement (-a, -g, -v)" } }
  'route'      = { param($a) if ($a.Count -ge 1 -and $a[0] -eq 'print') { $null } else { "route : seulement « route print »" } }
  'nslookup'   = { param($a) $null }
  'ping'       = { param($a) $null }
  'tracert'    = { param($a) $null }
  'pathping'   = { param($a) $null }
  'systeminfo' = { param($a) $null }
  'whoami'     = { param($a) $null }
  'hostname'   = { param($a) $null }
  'tasklist'   = { param($a) $null }
  'driverquery'= { param($a) $null }
  'getmac'     = { param($a) $null }
  'quser'      = { param($a) $null }
  'query'      = { param($a) if ($a.Count -ge 1 -and $a[0] -in @('user', 'session', 'process', 'termserver')) { $null } else { "query : user, session, process" } }
  'nbtstat'    = { param($a) if (Tous $a '^-(a|c|n|r|s)$|^[0-9a-z.\-]+$' -and -not ($a -ccontains '-R' -or $a -ccontains '-RR')) { $null } else { "nbtstat : pas de -R / -RR" } }
  'gpresult'   = { param($a) if (($a | Where-Object { $_ -match '^/(h|x|f)$' }).Count -eq 0) { $null } else { "gpresult : pas de rapport écrit sur disque (/h, /x)" } }
  'w32tm'      = { param($a) if ($a.Count -ge 1 -and $a[0] -match '^/(query|monitor|tz|stripchart)$') { $null } else { "w32tm : /query, /monitor, /tz, /stripchart" } }
  'powercfg'   = { param($a) if ($a.Count -ge 1 -and $a[0] -match '^[/-](q|query|qh|a|availablesleepstates|l|list|requests|lastwake|devicequery|getactivescheme|waketimers|requestsoverride)$') { $null } else { "powercfg : lecture seulement (/q, /a, /l, /requests, /lastwake, /devicequery, /waketimers)" } }
  'sfc'        = { param($a) if ($a.Count -ge 1 -and (Tous $a '^/(verifyonly|verifyfile=.+|offbootdir=.+|offwindir=.+)$')) { $null } else { "sfc : seulement /verifyonly ou /verifyfile (pas de /scannow)" } }
  'dism'       = { param($a) if ((Tous $a '^/(online|english|cleanup-image|scanhealth|checkhealth|get-[a-z]+|format:(table|list)|featurename:.+|packagename:.+)$') -and -not ($a -contains '/restorehealth')) { $null } else { "dism : seulement /checkhealth, /scanhealth et /get-*" } }
  'chkdsk'     = { param($a) if (($a -contains '/scan') -and (($a | Where-Object { $_ -match '^/(f|r|x|b|spotfix|offlinescanandfix|forceofflinefix|i|c|l.*|markclean|sdcleanup)$' }).Count -eq 0)) { $null } else { "chkdsk : seulement avec /scan, sans /f, /r, /x, /spotfix" } }
  'wevtutil'   = { param($a) if ($a.Count -ge 1 -and $a[0] -in @('qe', 'query-events', 'gl', 'get-log', 'el', 'enum-logs', 'gli', 'get-loginfo', 'ep', 'enum-publishers', 'gp', 'get-publisher')) { $null } else { "wevtutil : qe, gl, el, gli seulement" } }
  'sc'         = { param($a) if ($a.Count -ge 1 -and $a[0] -in @('query', 'queryex', 'qc', 'qdescription', 'qfailure', 'getdisplayname', 'getkeyname', 'enumdepend', 'sdshow', 'qprivs', 'qsidtype', 'qtriggerinfo', 'qpreferrednode')) { $null } else { "sc : interrogation seulement (query, queryex, qc...)" } }
  'schtasks'   = { param($a) if (($a | Where-Object { $_ -match '^/(create|delete|change|run|end|showsid)$' }).Count -eq 0 -and ($a.Count -eq 0 -or $a[0] -eq '/query')) { $null } else { "schtasks : /query seulement" } }
  'net'        = { param($a)
                   $pos = @($a | Where-Object { $_ -notmatch '^/' })
                   if ($a.Count -ge 1 -and $a[0] -in @('share', 'use', 'user', 'users', 'localgroup', 'group', 'session', 'config', 'statistics', 'stats', 'view', 'accounts', 'file') -and $pos.Count -le 2 -and
                       (($a | Where-Object { $_ -match '^/' -and $_ -notmatch '^/domain$' }).Count -eq 0) -and (($a | Where-Object { $_ -match '=' }).Count -eq 0)) { $null }
                   else { "net : consultation seulement (net user <nom>, net use, net share...), sans /add, /delete ni mot de passe" } }
  'reg'        = { param($a) if ($a.Count -ge 1 -and $a[0] -eq 'query') { $null } else { "reg : query seulement" } }
  'manage-bde' = { param($a) if ($a.Count -ge 1 -and $a[0] -match '^-(status|protectors)$' -and -not ($a -match '^-(add|delete|disable|enable)$')) { $null } else { "manage-bde : -status seulement" } }
  'bcdedit'    = { param($a) if (Tous $a '^/(enum|v)$|^(all|active|firmware|bootapp|osloader)$') { $null } else { "bcdedit : /enum seulement" } }
  'vssadmin'   = { param($a) if ($a.Count -ge 1 -and $a[0] -eq 'list') { $null } else { "vssadmin : list seulement" } }
  'pnputil'    = { param($a) if (Tous $a '^/(enum-[a-z]+|connected|problem|class|ids|relations|drivers|deviceids|services|stack|interfaces|properties|files)$|^[^/].*') { $null } else { "pnputil : /enum-* seulement" } }
  'icacls'     = { param($a) if (($a | Where-Object { $_ -match '^/(grant|deny|remove|reset|setowner|save|restore|setintegritylevel|inheritance|substitute)' }).Count -eq 0) { $null } else { "icacls : lecture des droits seulement" } }
  'auditpol'   = { param($a) if ($a.Count -ge 1 -and $a[0] -match '^/(get|list)') { $null } else { "auditpol : /get, /list seulement" } }
  'klist'      = { param($a) if (($a | Where-Object { $_ -match '^(purge|purge_bind|add_bind)$' }).Count -eq 0) { $null } else { "klist : pas de purge" } }
  'findstr'    = { param($a) $null }
  'netsh'      = { param($a) if ($a.Count -ge 2 -and ($a -contains 'show') -and (($a | Where-Object { $_ -match '^(set|add|delete|del|reset|import|export|install|uninstall|connect|disconnect|start|stop|flush|dump|trace|exec)$' }).Count -eq 0)) { $null } else { "netsh : « show » seulement (netsh wlan show interfaces...)" } }
  'fsutil'     = { param($a) if ($a.Count -ge 1 -and ($a[0] -eq 'fsinfo' -or ($a[0] -eq 'dirty' -and $a[1] -eq 'query') -or ($a[0] -eq 'volume' -and $a[1] -eq 'diskfree'))) { $null } else { "fsutil : fsinfo, dirty query, volume diskfree" } }
}
$TypesNew = '^(system\.)?(text\.stringbuilder|collections\..+|datetime|timespan|uri|version|guid|regex|text\.regularexpressions\.regex|management\.automation\.pscustomobject|object)$'
$MembresPermis = '^(To\w*|Get\w*|Read\w*|Split|Replace|Trim\w*|Substring|Contains\w*|StartsWith|EndsWith|IndexOf\w*|LastIndexOf\w*|PadLeft|PadRight|Equals|CompareTo|Where|ForEach|Format|Expand\w*|Round|Floor|Ceiling|Abs|Max|Min|Pow|Sqrt|Truncate|Match|Matches|IsMatch|Escape|Unescape|Normalize|Join|Concat|IsNullOrEmpty|IsNullOrWhiteSpace|Parse|TryParse|Exists|Count|Sum|Average|AddDays|AddHours|AddMinutes|AddSeconds|AddMilliseconds|AddMonths|AddYears|AddTicks|Subtract|Has\w*|Is\w*|Sort|Reverse|Clone|ContainsKey|ContainsValue|FromBase64String|ToBase64String|FromFileTime\w*|FromBinary|Distinct|First|Last)$'
# Volontairement absents : Add / Remove / Clear / Insert (un objet ADSI .Add()/.Remove() modifie un groupe local ou
# l'annuaire) -- en lecture, construire les listes par += et les tables par $t[clé] = valeur.

function Nom-Commande($c) {
  $n = $c.GetCommandName()
  if (-not $n) { return $null }
  $al = Get-Alias -Name ([System.Management.Automation.WildcardPattern]::Escape($n)) -ErrorAction SilentlyContinue  # « ? » / « % » : pas de joker
  if ($al) { $n = $al.ResolvedCommandName; if (-not $n) { $n = $al.Definition } }
  return $n
}

$refus = New-Object System.Collections.Generic.List[string]
if ($Mode -eq "lecture") {
  $fonctions = @($ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) | ForEach-Object { $_.Name })

  foreach ($c in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)) {
    $ligne = $c.Extent.StartLineNumber
    $nom = Nom-Commande $c
    if (-not $nom) {
      if ($c.CommandElements[0] -is [System.Management.Automation.Language.ScriptBlockExpressionAst]) { continue }  # & { ... } : contenu vérifié
      $refus.Add("ligne $ligne : appel dynamique ($($c.CommandElements[0].Extent.Text)) interdit en lecture seule"); continue
    }
    if ($fonctions -contains $nom) { continue }  # fonction définie dans le script : son corps est vérifié
    $feuille = ($nom -split '[\\/]')[-1]
    if ($feuille -ne $nom) {
      $sys32 = if ($env:SystemRoot) { Join-Path $env:SystemRoot 'System32' } else { $null }
      if (-not $sys32 -or -not $nom.StartsWith($sys32, [StringComparison]::OrdinalIgnoreCase)) {
        $refus.Add("ligne $ligne : exécutable hors de System32 ($nom) interdit en lecture seule"); continue
      }
    }
    $base = ($feuille -replace '\.(exe|com)$', '').ToLowerInvariant()
    if ($Exe.ContainsKey($base)) {
      $args2 = @($c.CommandElements | Select-Object -Skip 1 | ForEach-Object { $_.Extent.Text.Trim("'`"").ToLowerInvariant() })
      $motif = & $Exe[$base] $args2
      if ($motif) { $refus.Add("ligne $ligne : $motif") }
      continue
    }
    if ($CmdletsPermises -contains $feuille) { continue }
    if ($feuille -match '^Get-' -and $GetRefusees -notcontains $feuille) { continue }
    $refus.Add("ligne $ligne : « $feuille » peut modifier le poste (ou n'est pas dans la liste de lecture) -- mode intervention requis")
  }

  foreach ($r in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FileRedirectionAst] }, $true)) {
    if ($r.Location.Extent.Text -ne '$null') { $refus.Add("ligne $($r.Extent.StartLineNumber) : écriture dans un fichier ($($r.Extent.Text)) interdite en lecture seule") }
  }

  foreach ($m in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.InvokeMemberExpressionAst] }, $true)) {
    $membre = $m.Member.Extent.Text.Trim("'`"")
    if ($membre -eq 'new') {
      $t = if ($m.Expression -is [System.Management.Automation.Language.TypeExpressionAst]) { $m.Expression.TypeName.FullName.ToLowerInvariant() } else { '?' }
      if ($t -notmatch $TypesNew) { $refus.Add("ligne $($m.Extent.StartLineNumber) : création d'objet [$t]::new() interdite en lecture seule") }
      continue
    }
    if ($membre -notmatch $MembresPermis) { $refus.Add("ligne $($m.Extent.StartLineNumber) : méthode .$membre() interdite en lecture seule (peut agir sur le poste)") }
  }

  foreach ($a in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] }, $true)) {
    $g = $a.Left
    if ($g -is [System.Management.Automation.Language.ConvertExpressionAst]) { $g = $g.Child }
    if ($g -is [System.Management.Automation.Language.MemberExpressionAst]) {
      $refus.Add("ligne $($a.Extent.StartLineNumber) : affectation de propriété ($($g.Extent.Text)) interdite en lecture seule"); continue
    }
    if ($g -is [System.Management.Automation.Language.VariableExpressionAst] -and $g.VariablePath.IsDriveQualified -and $g.VariablePath.DriveName -notin @('env', 'variable', 'global', 'script', 'local', 'private')) {
      $refus.Add("ligne $($a.Extent.StartLineNumber) : écriture par le chemin $($g.Extent.Text) interdite en lecture seule")
    }
  }
}

if ($refus.Count -gt 0) {
  $refus | Select-Object -Unique | ForEach-Object { "SI-SHELL-REFUS : $_" }
  exit 3
}
if ($Verifier) { "SI-SHELL-OK"; exit 0 }

$sb = [scriptblock]::Create($src)
& $sb *>&1 | Out-String -Stream -Width 300
exit 0
