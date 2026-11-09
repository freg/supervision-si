#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde ownCloud (#999). Lecture seule :
  - config/config.php (dbtype, dbname, dbtableprefix, datadirectory, version, conservation corbeille / versions) -- jamais
    les mots de passe ;
  - base MySQL / MariaDB locale par le client `mysql` en root (authentification par socket) : SELECT seulement sur
    <préfixe>accounts, <préfixe>storages, <préfixe>filecache, <préfixe>files_trash, <préfixe>activity ;
  - système : /etc/os-release (fin de support Debian), place sur le disque des données.
Sortie JSON : {"instance": {...}, "comptes": [...], "activite": [...], "totaux": {...}, "alerts": [...]}.
Pur : parse_config, tsv, assembler, fin_support, constats."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

CHEMINS = ("/var/www/owncloud/config/config.php", "/var/www/html/owncloud/config/config.php", "/var/www/html/config/config.php",
           "/srv/owncloud/config/config.php", "/usr/share/owncloud/config/config.php")
# fin du support de sécurité (LTS compris) par version majeure de Debian
FIN_DEBIAN = {"8": "2020-06-30", "9": "2022-06-30", "10": "2024-06-30", "11": "2026-08-31", "12": "2028-06-30", "13": "2030-06-30"}
CHEMINS_ESPACES = ("files", "files_trashbin", "files_versions", "thumbnails", "uploads")
CLES = ("dbtype", "dbname", "dbhost", "dbtableprefix", "datadirectory", "version", "overwrite.cli.url",
        "trashbin_retention_obligation", "versions_retention_obligation")


def parse_config(texte):
    """config.php -> {clé: valeur} pour les clés utiles (chaînes PHP simples), plus trusted_domains."""
    out = {}
    for k in CLES:
        m = re.search(r"'%s'\s*=>\s*'([^']*)'" % re.escape(k), texte or "")
        if m:
            out[k] = m.group(1)
    m = re.search(r"'trusted_domains'\s*=>\s*(?:array\s*\(|\[)(.*?)(?:\)|\])\s*,", texte or "", re.S)
    if m:
        out["trusted_domains"] = re.findall(r"=>\s*'([^']*)'", m.group(1))
    return out


def tsv(texte):
    return [l.split("\t") for l in (texte or "").splitlines() if l.strip()]


def fin_support(os_release, maintenant=None):
    """/etc/os-release -> {nom, version, fin, depasse}."""
    d = dict(re.findall(r'^([A-Z_]+)="?([^"\n]*)"?', os_release or "", re.M))
    nom, ver = d.get("PRETTY_NAME") or d.get("NAME") or "?", (d.get("VERSION_ID") or "").split(".")[0]
    fin = FIN_DEBIAN.get(ver) if d.get("ID") == "debian" else None
    jour = time.strftime("%Y-%m-%d", time.gmtime(maintenant or time.time()))
    return {"nom": nom, "version": ver, "fin": fin, "depasse": bool(fin and fin < jour)}


def _go(o):
    try:
        return round(int(o) / 1024 ** 3, 1)
    except (TypeError, ValueError):
        return 0.0


def assembler(comptes, espaces, corbeilles, activite):
    """Lignes TSV des requêtes -> (comptes, totaux, activite).
    comptes : user_id, display_name, last_login, backend ; espaces : storage_id, path, size ;
    corbeilles : user, min(timestamp), count ; activite : jour, actions, utilisateurs."""
    par = {}
    for r in espaces:
        if len(r) < 3:
            continue
        sid, chemin, taille = r[0], r[1], r[2]
        uid = sid.split("::", 1)[1] if sid.startswith("home::") else None
        if uid is None:
            continue
        par.setdefault(uid, {})[chemin] = _go(taille)
    corb = {r[0]: (int(r[1]) if r[1].isdigit() else None, int(r[2]) if r[2].isdigit() else 0) for r in corbeilles if len(r) >= 3}
    out = []
    for r in comptes:
        if len(r) < 4:
            continue
        uid, nom, dernier, origine = r[0], r[1], r[2], r[3]
        e = par.get(uid, {})
        c = corb.get(uid, (None, 0))
        out.append({"id": uid, "nom": nom if nom and nom != "NULL" else uid,
                    "derniere_connexion": int(dernier) if dernier.isdigit() and int(dernier) > 0 else None,
                    "origine": "ldap" if "LDAP" in origine else "locale" if "Database" in origine else origine,
                    "go_fichiers": e.get("files", 0.0), "go_corbeille": e.get("files_trashbin", 0.0), "go_versions": e.get("files_versions", 0.0),
                    "corbeille_plus_ancien": c[0], "corbeille_elements": c[1]})
    tot = {k: round(sum(e.get(c, 0.0) for e in par.values()), 1) for k, c in
           (("fichiers", "files"), ("corbeilles", "files_trashbin"), ("versions", "files_versions"), ("apercus", "thumbnails"), ("envois", "uploads"))}
    act = [{"jour": r[0], "actions": int(r[1]), "utilisateurs": int(r[2])} for r in activite if len(r) >= 3 and r[1].isdigit() and r[2].isdigit()]
    return sorted(out, key=lambda x: -(x["derniere_connexion"] or 0)), tot, act


def constats(instance, comptes, totaux, maintenant, dormant_jours=365, disque_warn=80, disque_crit=90, corbeille_pct=20):
    alerts = []
    d = instance.get("disque") or {}
    if d.get("pct") is not None and d["pct"] >= disque_warn:
        alerts.append({"code": "owncloud-disque", "severity": "critical" if d["pct"] >= disque_crit else "warning",
                       "message": "ownCloud : disque des données rempli à %s %% (%s Go libres)" % (d["pct"], d.get("libre_go"))})
    s = instance.get("systeme") or {}
    if s.get("depasse"):
        alerts.append({"code": "owncloud-systeme", "severity": "warning",
                       "message": "ownCloud : %s sans mises à jour de sécurité depuis le %s" % (s.get("nom"), s.get("fin"))})
    donnees = (totaux.get("fichiers") or 0) + (totaux.get("corbeilles") or 0) + (totaux.get("versions") or 0)
    if donnees and totaux.get("corbeilles", 0) * 100.0 / donnees >= corbeille_pct:
        alerts.append({"code": "owncloud-corbeilles", "severity": "warning",
                       "message": "ownCloud : corbeilles %s Go (%d %% des données) -- conservation : %s" % (
                           totaux["corbeilles"], round(totaux["corbeilles"] * 100.0 / donnees), instance.get("conservation_corbeille") or "auto (par défaut)")})
    vieux = [c for c in comptes if c["origine"] == "locale" and c["id"] != "admin" and (c["derniere_connexion"] or 0) < maintenant - dormant_jours * 86400]
    if vieux:
        alerts.append({"code": "owncloud-comptes-locaux", "severity": "warning",
                       "message": "ownCloud : %d compte(s) local(aux) hors annuaire inactif(s) depuis plus d'un an : %s" % (len(vieux), ", ".join(c["id"] for c in vieux))})
    return alerts


def _mysql(base, requete, timeout=120):
    r = subprocess.run(["mysql", "--batch", "--raw", "-N", base, "-e", requete], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "mysql en échec").strip()[:300])
    return r.stdout


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="")
    ap.add_argument("--actif-jours", type=int, default=30)
    ap.add_argument("--dormant-jours", type=int, default=365)
    ap.add_argument("--disque-warn", type=float, default=80)
    ap.add_argument("--disque-crit", type=float, default=90)
    ap.add_argument("--corbeille-warn-pct", type=float, default=20)
    a = ap.parse_args(argv)
    chemin = a.config or next((c for c in CHEMINS if os.path.isfile(c)), "")
    if not chemin:
        print(json.dumps({"error": "config.php d'ownCloud introuvable (--config <chemin>)", "alerts": []}, ensure_ascii=False))
        return 0
    with open(chemin, encoding="utf-8", errors="replace") as fh:
        cfg = parse_config(fh.read())
    maintenant = time.time()
    try:
        with open("/etc/os-release", encoding="utf-8") as fh:
            systeme = fin_support(fh.read(), maintenant)
    except OSError:
        systeme = {}
    instance = {"config": chemin, "version": cfg.get("version"), "url": cfg.get("overwrite.cli.url"), "domaines": cfg.get("trusted_domains") or [],
                "base": cfg.get("dbtype"), "donnees": cfg.get("datadirectory"), "systeme": systeme,
                "conservation_corbeille": cfg.get("trashbin_retention_obligation"), "conservation_versions": cfg.get("versions_retention_obligation")}
    try:
        du = shutil.disk_usage(cfg.get("datadirectory") or os.path.dirname(chemin))
        instance["disque"] = {"total_go": _go(du.total), "libre_go": _go(du.free), "pct": round(du.used * 100.0 / du.total) if du.total else None}
    except OSError:
        pass
    if cfg.get("dbtype") not in ("mysql",):
        print(json.dumps({"instance": instance, "error": "base %s non prise en charge (mysql seulement)" % cfg.get("dbtype"), "alerts": []}, ensure_ascii=False))
        return 0
    p, base = cfg.get("dbtableprefix") or "oc_", cfg.get("dbname") or "owncloud"
    if not re.match(r"^[A-Za-z0-9_]{0,20}$", p) or not re.match(r"^[A-Za-z0-9_]{1,64}$", base):
        print(json.dumps({"instance": instance, "error": "nom de base ou préfixe inattendu", "alerts": []}, ensure_ascii=False))
        return 0
    try:
        comptes = tsv(_mysql(base, "SELECT user_id, IFNULL(display_name,''), IFNULL(last_login,0), backend FROM %saccounts" % p))
        espaces = tsv(_mysql(base, "SELECT s.id, f.path, f.size FROM %sfilecache f JOIN %sstorages s ON s.numeric_id=f.storage WHERE f.path IN (%s)"
                                   % (p, p, ",".join("'%s'" % c for c in CHEMINS_ESPACES))))
        try:
            corbeilles = tsv(_mysql(base, "SELECT user, MIN(timestamp), COUNT(*) FROM %sfiles_trash GROUP BY user" % p))
        except RuntimeError:
            corbeilles = []
        try:
            activite = tsv(_mysql(base, "SELECT DATE(FROM_UNIXTIME(timestamp)), COUNT(*), COUNT(DISTINCT user) FROM %sactivity "
                                        "WHERE timestamp > UNIX_TIMESTAMP(NOW() - INTERVAL 90 DAY) GROUP BY 1 ORDER BY 1" % p))
        except RuntimeError:
            activite = []
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        print(json.dumps({"instance": instance, "error": "base illisible : %s" % e, "alerts": []}, ensure_ascii=False))
        return 0
    cs, tot, act = assembler(comptes, espaces, corbeilles, activite)
    actifs = sum(1 for c in cs if (c["derniere_connexion"] or 0) >= maintenant - a.actif_jours * 86400)
    tot.update({"comptes": len(cs), "actifs": actifs, "actif_jours": a.actif_jours, "dormant_jours": a.dormant_jours})
    alerts = constats(instance, cs, tot, maintenant, a.dormant_jours, a.disque_warn, a.disque_crit, a.corbeille_warn_pct)
    print(json.dumps({"instance": instance, "comptes": cs, "activite": act, "totaux": tot, "alerts": alerts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
