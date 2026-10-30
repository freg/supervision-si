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


def manifeste(agent_id, cibles, montages, horodatage=None):
    return {"agent": agent_id, "cree": horodatage or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "confs": [{"app": c["app"], "cles": c["cles"], "dossiers": c["dossiers"]} for c in cibles],
            "montages": {"lecteurs": len((montages or {}).get("lecteurs") or []),
                         "partages": len((montages or {}).get("partages") or []),
                         "imprimantes": len((montages or {}).get("imprimantes") or [])}}


def construire_script_capture(cibles, dossier_travail, archive, usb=None, unc=None):
    """Script PowerShell de CAPTURE : reg export des clés, robocopy des dossiers, inclusion de remonter.cmd et du
    manifeste (déjà écrits par l'agent dans `dossier_travail`), compression en `archive`, puis copie vers la clé USB
    et/ou le partage UNC. Les identifiants UNC viennent des variables d'environnement SI_BK_UNC_USER / SI_BK_UNC_PASS
    (jamais dans le texte du script ni sur une ligne de commande). Émet un JSON SI-BK-DEBUT/FIN. Pur : testé."""
    L = ["$ErrorActionPreference='Continue'", "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
         "$t=%s" % _ps(dossier_travail), "$arch=%s" % _ps(archive),
         "$r=[ordered]@{confs=@(); dossiers=@(); destinations=@(); archive=$null; erreurs=@()}",
         "New-Item -ItemType Directory -Force -Path (Join-Path $t 'confs') | Out-Null",
         "New-Item -ItemType Directory -Force -Path (Join-Path $t 'appdata') | Out-Null"]
    n = 0
    for c in cibles:
        app = c["app"]
        for cle in c.get("cles") or []:
            n += 1
            fichier = "confs\\%s-%d.reg" % ("".join(ch if ch.isalnum() else "_" for ch in app)[:40], n)
            L.append("$f=Join-Path $t %s" % _ps(fichier))
            L.append("$o=(reg export %s $f /y) 2>&1" % _ps(cle))
            L.append("if (Test-Path $f) { $r.confs+=[ordered]@{app=%s; cle=%s; fichier=%s; octets=(Get-Item $f).Length} } "
                     "else { $r.erreurs+=('reg %s : '+($o-join' ')) }" % (_ps(app), _ps(cle), _ps(fichier), app.replace("'", "''")))
        for dossier in c.get("dossiers") or []:
            dst = "appdata\\%s" % "".join(ch if ch.isalnum() else "_" for ch in app)[:40]
            L.append("$src=[Environment]::ExpandEnvironmentVariables(%s)" % _ps(dossier))
            L.append("if (Test-Path $src) { $d=Join-Path $t %s; robocopy $src $d /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null; "
                     "$sz=(Get-ChildItem $d -Recurse -EA SilentlyContinue | Measure-Object Length -Sum).Sum; "
                     "$r.dossiers+=[ordered]@{app=%s; source=%s; octets=[int64]$sz} } "
                     "else { $r.dossiers+=[ordered]@{app=%s; source=%s; octets=0; absent=$true} }"
                     % (_ps(dst), _ps(app), _ps(dossier), _ps(app), _ps(dossier)))
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


def extraire_json(sortie):
    """Récupère le JSON entre SI-BK-DEBUT et SI-BK-FIN dans la sortie du script de capture."""
    txt = sortie or ""
    d, f = txt.find("SI-BK-DEBUT"), txt.rfind("SI-BK-FIN")
    if d < 0 or f < 0 or f <= d:
        return None
    bloc = txt[d + len("SI-BK-DEBUT"):f].strip()
    try:
        return json.loads(bloc)
    except ValueError:
        return None


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
