# -*- coding: utf-8 -*-
"""#930 : sauvegarde des configurations logicielles et des montages d'un poste Windows, en vue d'une réinstallation
(système identique ou plus récent). Produit un JEU DE SAUVEGARDE (archive ZIP) contenant :
  - confs/<app>-<n>.reg   : export des clés de registre des applications (reg export) ;
  - appdata/<app>/…       : copie des dossiers de configuration (%APPDATA%, %LOCALAPPDATA%) listés par application ;
  - remonter.cmd          : script de RECONSTRUCTION des montages (lecteurs réseau, partages servis, imprimantes) ;
  - manifeste.json        : ce qui a été capturé, quand, depuis quel poste.
L'archive est ensuite écrite sur une clé USB et/ou un partage réseau (identifiants du coffre, passés par variables
d'environnement -- jamais sur une ligne de commande ni dans une trace). La RESTAURATION (réimport du registre,
recréation des partages) est une opération d'INTERVENTION, livrée séparément.

Ce module est pur/testable : catalogue, fusion des cibles, génération du script de remontage et du script PowerShell
de capture, manifeste. L'exécution réelle (reg.exe, robocopy, Compress-Archive, écriture USB/UNC) est déléguée à un
`runner` injecté.
"""
import json
import time

# La SÉLECTION des applications (catalogue par défaut, déduction des logiciels relevés, liste éditée) est côté hub :
# api/sauvegarde_conf.py. L'agent reçoit la liste FINALE des cibles [{app, cles, dossiers}] et se contente de la
# capturer. Ce module ne garde donc que la génération (remontage, script de capture, manifeste) et l'interprétation.


def _bat(chemin):
    """Chemin pour un fichier .cmd : entre guillemets, sans % (évite l'expansion de variable dans le script généré)."""
    return '"%s"' % str(chemin).replace('"', "").replace("%", "")


def script_remontage(montages):
    """Génère remonter.cmd : reconstruit les montages sur le nouveau système. Lecteurs réseau (net use), partages
    servis (New-SmbShare + droits), imprimantes (best-effort). Pur : testé."""
    m = montages or {}
    out = ["@echo off", "chcp 65001>nul",
           "REM Remontage des lecteurs, partages et imprimantes -- genere par si-agent (sauvegarde).",
           "REM A executer sur le NOUVEAU poste. Les lecteurs reseau : dans la session de l'utilisateur concerne.",
           ""]
    lecteurs = m.get("lecteurs") or []
    out.append("REM --- Lecteurs reseau (%d) ---" % len(lecteurs))
    for d in lecteurs:
        lettre = str(d.get("lettre") or "").rstrip(":")
        chemin = str(d.get("chemin") or "")
        if lettre and chemin:
            u = str(d.get("utilisateur") or "")
            out.append('net use %s: %s /persistent:yes%s' % (lettre, _bat(chemin), ("  REM utilisateur %s" % u) if u else ""))
    out.append("")
    partages = m.get("partages") or []
    out.append("REM --- Partages servis par ce poste (%d) -- PowerShell administrateur ---" % len(partages))
    for s in partages:
        nom = str(s.get("nom") or "")
        chemin = str(s.get("chemin") or "")
        if not nom or not chemin:
            continue
        out.append('powershell -NoProfile -Command "if (-not (Get-SmbShare -Name \'%s\' -EA SilentlyContinue)) '
                   '{ New-SmbShare -Name \'%s\' -Path \'%s\' | Out-Null }"' % (nom.replace("'", "''"), nom.replace("'", "''"), chemin.replace("'", "''")))
        for a in (s.get("acces") or []):
            parts = str(a).split(":")
            if len(parts) >= 3:
                compte, typ, droit = parts[0], parts[1], parts[2]
                if typ.lower().startswith("allow"):
                    acc = {"full": "Full", "change": "Change", "read": "Read"}.get(droit.lower().split()[0] if droit else "read", "Read")
                    out.append('powershell -NoProfile -Command "Grant-SmbShareAccess -Name \'%s\' -AccountName \'%s\' -AccessRight %s -Force | Out-Null"'
                               % (nom.replace("'", "''"), compte.replace("'", "''"), acc))
    out.append("")
    imprimantes = [i for i in (m.get("imprimantes") or []) if i.get("nom")]
    out.append("REM --- Imprimantes (%d) : a reinstaller (pilote + port) ---" % len(imprimantes))
    for i in imprimantes:
        out.append("REM imprimante: %s  port/adresse: %s  pilote: %s" % (i.get("nom"), i.get("adresse") or i.get("port") or "?", i.get("pilote") or "?"))
    out.append("")
    out.append("echo Remontage termine. Verifier les lecteurs et partages ci-dessus.")
    return "\r\n".join(out) + "\r\n"


# ------------------------------------------------------------------------------------------------------------------
def _ps(s):
    """Chaîne littérale PowerShell (guillemets simples, apostrophes doublées)."""
    return "'%s'" % str(s).replace("'", "''")


def slug(app):
    """Nom de dossier sûr pour une application (identique à la capture et à la restauration)."""
    return "".join(ch if ch.isalnum() else "_" for ch in str(app))[:40]


def manifeste(agent_id, cibles, montages, horodatage=None):
    return {"agent": agent_id, "cree": horodatage or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "confs": [{"app": c["app"], "cles": c["cles"], "dossiers": c["dossiers"]} for c in cibles],
            "montages": {"lecteurs": len((montages or {}).get("lecteurs") or []),
                         "partages": len((montages or {}).get("partages") or []),
                         "imprimantes": len((montages or {}).get("imprimantes") or [])}}


# #947 : l'agent tourne en SYSTEM -> %APPDATA% et HKCU désignaient le profil SYSTEM (archives vides). La capture et la
# restauration parcourent les PROFILS UTILISATEURS (HKLM\...\ProfileList : SID + chemin), remplacent %APPDATA% /
# %LOCALAPPDATA% / %USERPROFILE% par le profil, exportent HKCU depuis HKU\<SID> (ruche chargée au besoin depuis
# NTUSER.DAT) et normalisent les .reg en HKEY_CURRENT_USER pour qu'ils se réimportent chez n'importe quel utilisateur.
PS_PROFILS = (
    "$profils=@(); foreach ($p in (Get-ChildItem 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList' -EA SilentlyContinue)) { "
    "$sid=$p.PSChildName; if ($sid -notmatch '^S-1-5-21-') { continue }; $path=[Environment]::ExpandEnvironmentVariables(($p | Get-ItemProperty).ProfileImagePath); "
    "if (-not (Test-Path $path)) { continue }; $nom=Split-Path $path -Leaf; if ($nom -in @('Default','Public','defaultuser0')) { continue }; "
    "$profils+=[pscustomobject]@{sid=$sid; path=$path; nom=$nom; ntuser=(Join-Path $path 'NTUSER.DAT')} }"
)
PS_RUCHE = (
    "function Ruche($p) { if (Test-Path ('Registry::HKEY_USERS\\'+$p.sid)) { return @{cle=('HKU\\'+$p.sid); chargee=$false} }; "
    "$tmp='SIBK_'+($p.sid -replace '[^0-9A-Za-z]','_'); $o=(reg load ('HKU\\'+$tmp) $p.ntuser) 2>&1; if ($LASTEXITCODE -eq 0) { return @{cle=('HKU\\'+$tmp); chargee=$true} }; return $null }"
    "\r\nfunction Decharge($h) { if ($h -and $h.chargee) { [gc]::Collect(); reg unload $h.cle *>$null } }"
    "\r\nfunction CheminProfil($p, $m) { $x=$m -replace '%APPDATA%',($p.path+'\\AppData\\Roaming') -replace '%LOCALAPPDATA%',($p.path+'\\AppData\\Local') -replace '%USERPROFILE%',$p.path; return [Environment]::ExpandEnvironmentVariables($x) }"
)


def construire_script_capture(cibles, dossier_travail, archive, usb=None, unc=None):
    """Script PowerShell de CAPTURE, par profil utilisateur (#947) : reg export des clés (HKCU -> HKU\\<SID>, .reg
    normalisé en HKEY_CURRENT_USER), robocopy des dossiers (%APPDATA%… du profil), inclusion de remonter.cmd et du
    manifeste (déjà écrits par l'agent dans `dossier_travail`), compression en `archive`, puis copie vers la clé USB
    et/ou le partage UNC. Les identifiants UNC viennent des variables d'environnement SI_BK_UNC_USER / SI_BK_UNC_PASS
    (jamais dans le texte du script ni sur une ligne de commande). Émet un JSON SI-BK-DEBUT/FIN. Pur : testé.
    Archive : confs/<utilisateur>/<app>-<n>.reg ; appdata/<utilisateur>/<app>/<j>/…"""
    L = ["$ErrorActionPreference='Continue'", "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
         "$t=%s" % _ps(dossier_travail), "$arch=%s" % _ps(archive),
         "$r=[ordered]@{confs=@(); dossiers=@(); destinations=@(); archive=$null; utilisateurs=@(); erreurs=@()}",
         "New-Item -ItemType Directory -Force -Path (Join-Path $t 'confs') | Out-Null",
         "New-Item -ItemType Directory -Force -Path (Join-Path $t 'appdata') | Out-Null",
         PS_PROFILS, PS_RUCHE,
         "if ($profils.Count -eq 0) { $r.erreurs+=('aucun profil utilisateur trouve (ProfileList)') }",
         "foreach ($p in $profils) {",
         "  $u=$p.nom; $r.utilisateurs+=$u; $h=$null",
         "  New-Item -ItemType Directory -Force -Path (Join-Path $t ('confs\\'+$u)) | Out-Null"]
    n = 0
    for c in cibles:
        app = c["app"]
        sl = slug(app)
        for cle in c.get("cles") or []:
            n += 1
            fichier = "%s-%d.reg" % (sl, n)
            if cle.upper().startswith("HKCU\\") or cle.upper().startswith("HKEY_CURRENT_USER\\"):
                reste = cle.split("\\", 1)[1]
                L.append("  if (-not $h) { $h=Ruche $p }")
                L.append("  if ($h) { $f=Join-Path $t ('confs\\'+$u+'\\'+%s); $o=(reg export ($h.cle+'\\'+%s) $f /y) 2>&1" % (_ps(fichier), _ps(reste)))
                L.append("    if (Test-Path $f) { $c=Get-Content $f -Raw -Encoding Unicode; $c=$c -replace [regex]::Escape('[HKEY_USERS\\'+$h.cle.Substring(4)),'[HKEY_CURRENT_USER'; Set-Content $f $c -Encoding Unicode; "
                         "$r.confs+=[ordered]@{app=%s; cle=%s; utilisateur=$u; fichier=('confs/'+$u+'/'+%s); octets=(Get-Item $f).Length} } "
                         "else { $r.erreurs+=('reg %s ('+$u+') : '+($o-join' ')) } }" % (_ps(app), _ps(cle), _ps(fichier), app.replace("'", "''")))
                L.append("  else { $r.erreurs+=('ruche de '+$u+' inaccessible : '+%s) }" % _ps(cle))
            else:
                # clé machine (HKLM) : une seule fois, rangée sous le premier profil
                L.append("  if ($u -eq $profils[0].nom) { $f=Join-Path $t ('confs\\'+$u+'\\'+%s); $o=(reg export %s $f /y) 2>&1" % (_ps(fichier), _ps(cle)))
                L.append("    if (Test-Path $f) { $r.confs+=[ordered]@{app=%s; cle=%s; utilisateur=$null; fichier=('confs/'+$u+'/'+%s); octets=(Get-Item $f).Length} } else { $r.erreurs+=('reg %s : '+($o-join' ')) } }"
                         % (_ps(app), _ps(cle), _ps(fichier), app.replace("'", "''")))
        for j, dossier in enumerate(c.get("dossiers") or [], 1):
            rel = "appdata\\'+$u+'\\%s\\%d" % (sl, j)
            relj = "appdata/'+$u+'/%s/%d" % (sl.replace("\\", "/"), j)
            L.append("  $src=CheminProfil $p %s" % _ps(dossier))
            L.append("  if (Test-Path $src) { $d=Join-Path $t ('%s'); robocopy $src $d /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD 'cache2' 'Cache' 'Code Cache' 'GPUCache' 'ShaderCache' 'CacheStorage' | Out-Null; "
                     "$sz=(Get-ChildItem $d -Recurse -EA SilentlyContinue | Measure-Object Length -Sum).Sum; "
                     "$r.dossiers+=[ordered]@{app=%s; utilisateur=$u; source=$src; modele=%s; archive=('%s'); octets=[int64]$sz} } "
                     "else { $r.dossiers+=[ordered]@{app=%s; utilisateur=$u; source=$src; modele=%s; archive=('%s'); octets=0; absent=$true} }"
                     % (rel, _ps(app), _ps(dossier), relj, _ps(app), _ps(dossier), relj))
    L += ["  Decharge $h", "}"]
    # compression
    L += ["if (Test-Path $arch) { Remove-Item $arch -Force -EA SilentlyContinue }",
          "Compress-Archive -Path (Join-Path $t '*') -DestinationPath $arch -Force",
          "if (Test-Path $arch) { $r.archive=[ordered]@{nom=(Split-Path $arch -Leaf); octets=(Get-Item $arch).Length; "
          "sha256=(Get-FileHash $arch -Algorithm SHA256).Hash} } else { $r.erreurs+=('archive non creee') }"]
    # destinations
    if usb:
        L += ["$dst=%s" % _ps(usb),
              "try { if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }; "
              "Copy-Item $arch $dst -Force; $r.destinations+=[ordered]@{type='usb'; cible=$dst; ok=$true} } "
              "catch { $r.destinations+=[ordered]@{type='usb'; cible=$dst; ok=$false; erreur=$_.Exception.Message} }"]
    if unc:
        chemin = unc.get("chemin") if isinstance(unc, dict) else str(unc)
        avec_creds = bool(isinstance(unc, dict) and unc.get("avec_identifiants"))
        L.append("$u=%s" % _ps(chemin))
        if avec_creds:
            L += ["$mapok=$false",
                  "try { if ($env:SI_BK_UNC_USER) { $sp=ConvertTo-SecureString $env:SI_BK_UNC_PASS -AsPlainText -Force; "
                  "$cr=New-Object System.Management.Automation.PSCredential($env:SI_BK_UNC_USER,$sp); "
                  "New-SmbMapping -RemotePath $u -UserName $env:SI_BK_UNC_USER -Password $env:SI_BK_UNC_PASS -EA Stop | Out-Null; $mapok=$true } } "
                  "catch { $r.erreurs+=('connexion partage : '+$_.Exception.Message) }"]
        L += ["try { Copy-Item $arch $u -Force; $r.destinations+=[ordered]@{type='unc'; cible=$u; ok=$true} } "
              "catch { $r.destinations+=[ordered]@{type='unc'; cible=$u; ok=$false; erreur=$_.Exception.Message} }"]
        if avec_creds:
            L.append("if ($mapok) { Remove-SmbMapping -RemotePath $u -Force -EA SilentlyContinue }")
    L += ["Remove-Item (Join-Path $t 'appdata') -Recurse -Force -EA SilentlyContinue",
          "Write-Output 'SI-BK-DEBUT'", "Write-Output ($r | ConvertTo-Json -Depth 6 -Compress)", "Write-Output 'SI-BK-FIN'"]
    return "\r\n".join(L) + "\r\n"


def extraire_json(sortie, debut="SI-BK-DEBUT", fin="SI-BK-FIN"):
    """Récupère le JSON entre deux marqueurs dans la sortie d'un script (capture : SI-BK ; restauration : SI-RST)."""
    txt = sortie or ""
    d, f = txt.find(debut), txt.rfind(fin)
    if d < 0 or f < 0 or f <= d:
        return None
    bloc = txt[d + len(debut):f].strip()
    try:
        return json.loads(bloc)
    except ValueError:
        return None


# ------------------------------------------------------------------------------------------------------------------
# #934 : RESTAURATION (opération d'INTERVENTION). Simulation = lecture seule (liste ce qui serait restauré) ;
# application = réimport du registre (avec sauvegarde de repli des clés écrasées), remise des dossiers de config,
# et remontage des lecteurs/partages.
def construire_script_simulation(archive_dir):
    """Script PowerShell LECTURE SEULE : liste le contenu d'une archive de sauvegarde (clés .reg, dossiers de config,
    présence de remonter.cmd, manifeste). N'écrit rien. Émet un JSON SI-RST-DEBUT/FIN. Pur : testé."""
    a = _ps(archive_dir)
    return "\r\n".join([
        "$ErrorActionPreference='Continue'", "[Console]::OutputEncoding=[Text.Encoding]::UTF8", "$a=%s" % a,
        "$r=[ordered]@{simulation=$true; confs=@(); dossiers=@(); remonter=$false; manifeste=$null; erreurs=@()}",
        "if (-not (Test-Path $a)) { $r.erreurs+=('archive introuvable') }",
        "Get-ChildItem (Join-Path $a 'confs') -Filter *.reg -Recurse -EA SilentlyContinue | ForEach-Object { $r.confs+=[ordered]@{fichier=$_.FullName.Substring($a.Length+1); octets=$_.Length} }",   # #947 : confs\<utilisateur>\
        "Get-ChildItem (Join-Path $a 'appdata') -Directory -Recurse -Depth 1 -EA SilentlyContinue | Where-Object { $_.Parent.Name -ne 'appdata' -or (Get-ChildItem $_.FullName -Directory | Where-Object { $_.Name -notmatch '^\\d+$' }).Count -eq 0 } | ForEach-Object { $app=$_.Name; "
        "Get-ChildItem $_.FullName -Directory -EA SilentlyContinue | ForEach-Object { $sz=(Get-ChildItem $_.FullName -Recurse -EA SilentlyContinue | Measure-Object Length -Sum).Sum; "
        "$r.dossiers+=[ordered]@{app=$app; archive=('appdata/'+$app+'/'+$_.Name); octets=[int64]$sz} } }",
        "$r.remonter=(Test-Path (Join-Path $a 'remonter.cmd'))",
        "$mf=Join-Path $a 'manifeste.json'; if (Test-Path $mf) { try { $r.manifeste=(Get-Content $mf -Raw | ConvertFrom-Json) } catch { $r.erreurs+=('manifeste illisible') } }",
        "Write-Output 'SI-RST-DEBUT'", "Write-Output ($r | ConvertTo-Json -Depth 6 -Compress)", "Write-Output 'SI-RST-FIN'", ""])


def construire_script_restauration(cibles, archive_dir, rollback_dir, options=None):
    """Script PowerShell d'APPLICATION (intervention), par profil utilisateur (#947) : les .reg (HKEY_CURRENT_USER) sont
    réimportés dans la ruche HKU\\<SID> de l'utilisateur cible (chargée au besoin), après repli de l'état courant dans
    `rollback_dir` ; les dossiers reviennent dans le profil cible. `options.utilisateur` = nom du profil cible (défaut :
    même nom que dans l'archive, sinon le premier profil). `cibles` = confs du manifeste [{app, cles, dossiers}]. Pur."""
    o = options or {}
    reg_on = o.get("registre", True)
    ad_on = o.get("appdata", True)
    mt_on = o.get("montages", False)
    cible_u = str(o.get("utilisateur") or "").strip()
    L = ["$ErrorActionPreference='Continue'", "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
         "$a=%s" % _ps(archive_dir), "$rb=%s" % _ps(rollback_dir),
         "$r=[ordered]@{simulation=$false; registre=@(); dossiers=@(); montages=$null; rollback=$rb; utilisateurs=@(); erreurs=@()}",
         "New-Item -ItemType Directory -Force -Path $rb | Out-Null",
         PS_PROFILS, PS_RUCHE,
         "$cibleU=%s" % _ps(cible_u),
         "$dossiersArch=@(); if (Test-Path (Join-Path $a 'confs')) { $dossiersArch=@(Get-ChildItem (Join-Path $a 'confs') -Directory | ForEach-Object Name) }",
         "if (Test-Path (Join-Path $a 'appdata')) { $dossiersArch+=@(Get-ChildItem (Join-Path $a 'appdata') -Directory | ForEach-Object Name) }",
         "$dossiersArch=@($dossiersArch | Select-Object -Unique)",
         # archive ancienne (sans sous-dossier utilisateur) : fichiers directement sous confs/ -> traités pour le profil cible
         "$ancien=(Test-Path (Join-Path $a 'confs')) -and ((Get-ChildItem (Join-Path $a 'confs') -File -Filter *.reg -EA SilentlyContinue | Measure-Object).Count -gt 0)",
         "foreach ($p in $profils) {",
         "  $u=$p.nom; $srcU=$u",
         "  if ($cibleU -and $u -ne $cibleU) { continue }",
         "  if (-not $ancien -and ($dossiersArch -notcontains $u)) { if ($cibleU -and $dossiersArch.Count -gt 0) { $srcU=$dossiersArch[0] } else { continue } }",
         "  $r.utilisateurs+=$u; $h=$null"]
    n = 0
    for c in cibles or []:
        app = c.get("app") or ""
        sl = slug(app)
        if reg_on:
            for cle in c.get("cles") or []:
                n += 1
                regf = "%s-%d.reg" % (sl, n)
                perso = cle.upper().startswith("HKCU\\") or cle.upper().startswith("HKEY_CURRENT_USER\\")
                L.append("  $f=Join-Path $a ('confs\\'+$srcU+'\\'+%s); if ($ancien) { $f=Join-Path $a ('confs\\'+%s) }" % (_ps(regf), _ps(regf)))
                if perso:
                    reste = cle.split("\\", 1)[1]
                    L.append("  if (Test-Path $f) { if (-not $h) { $h=Ruche $p }; if ($h) { reg export ($h.cle+'\\'+%s) (Join-Path $rb ($u+'-'+%s)) /y *>$null; "
                             "$c=Get-Content $f -Raw -Encoding Unicode; $c=$c -replace '\\[HKEY_CURRENT_USER',('[HKEY_USERS\\'+$h.cle.Substring(4)); $tmp=Join-Path $env:TEMP ('sibk-'+$u+'-'+%s); Set-Content $tmp $c -Encoding Unicode; "
                             "$o=(reg import $tmp) 2>&1; Remove-Item $tmp -Force -EA SilentlyContinue; "
                             "$r.registre+=[ordered]@{app=%s; cle=%s; utilisateur=$u; ok=($LASTEXITCODE -eq 0); detail=(($o|Out-String).Trim())} } "
                             "else { $r.registre+=[ordered]@{app=%s; cle=%s; utilisateur=$u; ok=$false; detail='ruche inaccessible'} } }"
                             % (_ps(reste), _ps(regf), _ps(regf), _ps(app), _ps(cle), _ps(app), _ps(cle)))
                else:
                    L.append("  if ((Test-Path $f) -and ($u -eq $profils[0].nom)) { reg export %s (Join-Path $rb %s) /y *>$null; $o=(reg import $f) 2>&1; "
                             "$r.registre+=[ordered]@{app=%s; cle=%s; utilisateur=$null; ok=($LASTEXITCODE -eq 0); detail=(($o|Out-String).Trim())} }"
                             % (_ps(cle), _ps(regf), _ps(app), _ps(cle)))
        if ad_on:
            for j, dossier in enumerate(c.get("dossiers") or [], 1):
                L.append("  $src=Join-Path $a ('appdata\\'+$srcU+'\\%s\\%d'); if ($ancien) { $src=Join-Path $a ('appdata\\%s\\%d') }; $dst=CheminProfil $p %s" % (sl, j, sl, j, _ps(dossier)))
                L.append("  if (Test-Path $src) { robocopy $src $dst /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP *>$null; "
                         "$r.dossiers+=[ordered]@{app=%s; utilisateur=$u; cible=$dst; ok=($LASTEXITCODE -lt 8)} }" % _ps(app))
    L += ["  Decharge $h", "}"]
    if mt_on:
        L.append("$rm=Join-Path $a 'remonter.cmd'; if (Test-Path $rm) { $o=(cmd /c $rm) 2>&1; "
                 "$r.montages=[ordered]@{ok=($LASTEXITCODE -eq 0); detail=(($o|Out-String).Trim().Substring(0,[Math]::Min(500,($o|Out-String).Trim().Length)))} } "
                 "else { $r.montages=[ordered]@{ok=$false; detail='remonter.cmd absent'} }")
    L += ["Write-Output 'SI-RST-DEBUT'", "Write-Output ($r | ConvertTo-Json -Depth 6 -Compress)", "Write-Output 'SI-RST-FIN'", ""]
    return "\r\n".join(L)


def constats_restauration(resultat):
    """Alertes à partir du résultat de restauration."""
    out = []
    r = resultat or {}
    ko_reg = [x for x in r.get("registre") or [] if x.get("ok") is False]
    if ko_reg:
        out.append({"code": "restauration-registre", "severity": "critical",
                    "message": "réimport de clés en échec : %s" % ", ".join(sorted({x.get("app") for x in ko_reg}))[:150]})
    ko_ad = [x for x in r.get("dossiers") or [] if x.get("ok") is False]
    if ko_ad:
        out.append({"code": "restauration-dossiers", "severity": "warning",
                    "message": "remise de dossiers en échec : %s" % ", ".join(sorted({x.get("app") for x in ko_ad}))[:150]})
    if r.get("montages") and r["montages"].get("ok") is False:
        out.append({"code": "restauration-montages", "severity": "warning", "message": "remontage en échec : %s" % (r["montages"].get("detail") or "")[:150]})
    for e in r.get("erreurs") or []:
        out.append({"code": "restauration-erreur", "severity": "warning", "message": str(e)[:200]})
    return out


def constats(resultat):
    """Alertes à partir du résultat de capture (jamais de secret)."""
    out = []
    r = resultat or {}
    if not (r.get("archive") or {}).get("nom"):
        out.append({"code": "sauvegarde-echec", "severity": "critical", "message": "archive de sauvegarde non créée"})
    for d in r.get("destinations") or []:
        if not d.get("ok"):
            out.append({"code": "sauvegarde-destination", "severity": "critical",
                        "message": "écriture sur %s en échec : %s" % (d.get("type"), (d.get("erreur") or "")[:150])})
    for e in r.get("erreurs") or []:
        out.append({"code": "sauvegarde-partiel", "severity": "warning", "message": str(e)[:200]})
    manquants = [d.get("app") for d in r.get("dossiers") or [] if d.get("absent")]
    if manquants:
        out.append({"code": "sauvegarde-dossier-absent", "severity": "info",
                    "message": "dossiers absents (rien à sauvegarder) : %s" % ", ".join(sorted(set(manquants)))[:150]})
    return out
