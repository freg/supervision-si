# -*- coding: utf-8 -*-
"""#857 : ÉTAT DES LIEUX des systèmes (nœuds Proxmox et CT / VM) -- version du système et fin de support, date de la
dernière mise à jour, mises à jour en attente (dont sécurité), versions clés obsolètes (PHP, PostgreSQL, Proxmox,
ownCloud / Nextcloud…), services inclus (ports écoutés, services actifs -> rôles en clair), usage (charge, requêtes web,
clients connectés, comptes), exposition sur Internet, INTERACTIONS et DÉPENDANCES (connexions établies entre systèmes).
-> niveau par système (urgent / à planifier / à surveiller / ok / inactif), raisons, action proposée, impact.
Données : relevés pve-preflight (dans chaque invité démarré ; fichiers du disque pour un CT arrêté ; le nœud lui-même).
Pur, testé dans test_z_etat.py. Les dates de fin de support sont des références modifiables (réglage etat_eol)."""
import datetime as dt
import ipaddress
import re
import time

# Fin du support de sécurité (support standard + LTS gratuit), AAAA-MM-JJ. Références modifiables dans le hub.
EOL = {
    "debian": {"6": "2016-02-29", "7": "2018-05-31", "8": "2020-06-30", "9": "2022-06-30", "10": "2024-06-30", "11": "2026-08-31",
               "12": "2028-06-30", "13": "2030-06-30"},
    "ubuntu": {"14.04": "2019-04-30", "16.04": "2021-04-30", "18.04": "2023-05-31", "20.04": "2025-05-31", "22.04": "2027-06-30", "24.04": "2029-05-31"},
    "centos": {"6": "2020-11-30", "7": "2024-06-30", "8": "2021-12-31"},
    "rocky": {"8": "2029-05-31", "9": "2032-05-31"}, "almalinux": {"8": "2029-05-31", "9": "2032-05-31"},
    "alpine": {"3.18": "2025-05-09", "3.19": "2025-11-01", "3.20": "2026-04-01", "3.21": "2026-11-01", "3.22": "2027-05-01"},
    "windows": {"10": "2025-10-14", "11": "2027-10-12"},
    "windows-server": {"2012": "2023-10-10", "2012r2": "2023-10-10", "2016": "2027-01-12", "2019": "2029-01-09", "2022": "2031-10-14", "2025": "2034-10-10"},
    "proxmox-ve": {"4": "2018-06-30", "5": "2020-07-31", "6": "2022-07-31", "7": "2024-07-31", "8": "2026-08-31", "9": "2028-06-30"},
    "proxmox-backup": {"1": "2022-07-31", "2": "2024-06-30", "3": "2026-08-31", "4": "2028-06-30"},
    "php": {"5": "2018-12-31", "7.0": "2019-01-10", "7.1": "2019-12-01", "7.2": "2020-11-30", "7.3": "2021-12-06", "7.4": "2022-11-28",
            "8.0": "2023-11-26", "8.1": "2025-12-31", "8.2": "2026-12-31", "8.3": "2027-12-31", "8.4": "2028-12-31"},
    "postgresql": {"9": "2021-11-11", "10": "2022-11-10", "11": "2023-11-09", "12": "2024-11-21", "13": "2025-11-13", "14": "2026-11-12",
                   "15": "2027-11-11", "16": "2028-11-09", "17": "2029-11-08"},
    "owncloud": {"8": "2016-12-31", "9": "2017-12-31", "10": "2026-12-31"},
    "nextcloud": {"25": "2023-10-31", "26": "2024-03-31", "27": "2024-06-30", "28": "2025-01-31", "29": "2025-04-30", "30": "2025-09-30",
                  "31": "2026-02-28", "32": "2026-08-31"},
}
ROLES_PORT = {22: "administration à distance", 25: "messagerie (envoi)", 465: "messagerie (envoi)", 587: "messagerie (envoi)",
              110: "messagerie (lecture)", 143: "messagerie (lecture)", 993: "messagerie (lecture)", 995: "messagerie (lecture)",
              80: "site ou application web", 443: "site ou application web", 8080: "application web", 8443: "application web",
              3306: "base de données", 5432: "base de données", 6379: "cache", 53: "annuaire de noms (DNS)", 445: "partage de fichiers",
              139: "partage de fichiers", 21: "transfert de fichiers", 8006: "hyperviseur Proxmox", 8007: "sauvegardes Proxmox", 3128: "proxy",
              389: "annuaire", 636: "annuaire", 1194: "accès distant (VPN)", 51820: "accès distant (VPN)", 9090: "supervision", 3000: "application web"}
ROLES_APP = {"owncloud": "partage de fichiers (ownCloud)", "nextcloud": "partage de fichiers (Nextcloud)", "postfix": "messagerie", "dovecot": "messagerie",
             "amavisd-new": "filtrage du courrier", "roundcube-core": "messagerie web", "samba": "partage de fichiers", "squid": "proxy",
             "bind9": "annuaire de noms (DNS)", "pve-manager": "hyperviseur Proxmox", "proxmox-backup-server": "sauvegardes Proxmox"}
NIVEAUX = ("urgent", "à planifier", "à surveiller", "ok", "inactif")


def _date(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def public(ip):
    try:
        a = ipaddress.ip_address(ip)
        return not (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast) and not str(ip).startswith(("100.64.",))
    except ValueError:
        return False


def fin_support(famille, version, eol=None):
    """-> (date de fin AAAA-MM-JJ, clé trouvée) : version exacte, puis majeure (12.5 -> 12, 8.1.2 -> 8.1 puis 8)."""
    t = (eol or EOL).get(famille) or {}
    v = str(version or "")
    for k in (v, ".".join(v.split(".")[:2]), v.split(".")[0]):
        if k and k in t:
            return t[k], k
    return None, None


def statut_fin(date, maintenant):
    t = _date(date)
    if t is None:
        return "inconnu"
    if t < maintenant:
        return "obsolète"
    return "fin proche" if t - maintenant < 180 * 86400 else "supporté"


def os_de(systeme, pveversion=None):
    o = (systeme or {}).get("os") or {}
    fam, ver = (o.get("id") or "").lower() or None, o.get("version")
    if fam in ("rhel", "centos"):
        fam = "centos"
    return fam, ver, o.get("nom") or (("%s %s" % (fam, ver)) if fam else None)


def composants(systeme, os_statut, maintenant, eol=None):
    """Versions clés -> [{nom, version, fin, statut, note}] ; un paquet de la distribution reste maintenu tant que le système l'est."""
    out = []
    pk = (systeme or {}).get("paquets") or {}
    for nom, ver in sorted(pk.items()):
        fam = v = None
        m = re.match(r"^php(\d+\.\d+)-common$", nom)
        if m:
            fam, v = "php", m.group(1)
        elif nom == "php-common":
            continue
        elif re.match(r"^postgresql-\d+", nom):
            fam, v = "postgresql", nom.split("-")[1]
        elif nom == "pve-manager":
            fam, v = "proxmox-ve", ver.split(".")[0]
        elif nom == "proxmox-backup-server":
            fam, v = "proxmox-backup", ver.split(".")[0]
        if not fam:
            continue
        fin, _k = fin_support(fam, v, eol)
        st = statut_fin(fin, maintenant)
        note = None
        if fam in ("php", "postgresql") and st == "obsolète" and os_statut in ("supporté", "fin proche"):
            st, note = "maintenu par la distribution", "fin amont %s" % fin
        out.append({"nom": fam, "version": v, "paquet": ver, "fin": fin, "statut": st, "note": note})
    for a in (systeme or {}).get("apps") or []:
        fin, _k = fin_support(a["nom"], a["version"], eol)
        out.append({"nom": a["nom"], "version": a["version"], "paquet": a["version"], "fin": fin, "statut": statut_fin(fin, maintenant) if fin else "à vérifier", "note": None})
    return out


PROCS_TECHNIQUES = {"spiceproxy", "pvedaemon", "rpcbind", "systemd-resolve", "chronyd", "master"}   # services internes d'un nœud Proxmox
EXIGE_PORT = {"postfix": (25, 465, 587), "dovecot": (110, 143, 993, 995), "samba": (139, 445), "squid": (3128,), "bind9": (53,)}


def roles(systeme):
    """Rôles en clair : ports écoutés hors boucle locale (sauf services internes de Proxmox), puis applications ; un
    paquet de messagerie, de partage ou de proxy ne compte que si son port est réellement ouvert (postfix d'un nœud
    Proxmox = notifications locales, pas un serveur de messagerie)."""
    r = []
    ext = [e for e in (systeme or {}).get("ecoute") or [] if not e["hote"].startswith(("127.", "[::1]", "::1"))]
    ports = {e["port"] for e in ext}
    for e in ext:
        if e.get("proc") in PROCS_TECHNIQUES:
            continue
        x = ROLES_PORT.get(e["port"])
        if x and x not in r:
            r.append(x)
    for n in list(((systeme or {}).get("paquets") or {}).keys()) + [a["nom"] for a in (systeme or {}).get("apps") or []]:
        base = n if n in ROLES_APP else n.split("-")[0]
        x = ROLES_APP.get(base)
        if x and base in EXIGE_PORT and not ports & set(EXIGE_PORT[base]):
            continue
        if x and x not in r:
            r.append(x)
    return r


def usage(status, charge, systeme):
    if status not in ("running", None, "actif"):
        return "nul", {}
    c = charge or {}
    s = systeme or {}
    clients = sum((x.get("clients") or 0) for x in s.get("cnx_in") or [] if x.get("port") != 22)
    req = s.get("requetes") or 0
    cpu = c.get("cpu_avg_pct") or 0
    d = {"clients": clients, "requetes": req, "cpu_moy_pct": c.get("cpu_avg_pct"), "cpu_max_pct": c.get("cpu_max_pct"), "mem_max_pct": c.get("mem_max_pct"),
         "comptes": s.get("comptes")}
    if clients >= 20 or req >= 10000 or cpu >= 30:
        return "fort", d
    if clients >= 3 or req >= 500 or cpu >= 5:
        return "moyen", d
    return "faible", d


def declaration(manuel):
    """Fiche déclarée à la main (système illisible : VM sans agent invité, Windows, appliance, VM arrêtée) ->
    morceau de « systeme » compatible avec le relevé."""
    if not manuel:
        return None
    try:
        maj = int(_date(manuel.get("maj")) or 0) or None
    except (TypeError, ValueError):
        maj = None
    return {"os": {"id": manuel.get("famille"), "version": manuel.get("version"), "nom": manuel.get("nom") or "%s %s" % (manuel.get("famille"), manuel.get("version"))},
            "maj_at": maj, "attente": None, "attente_secu": None, "paquets": {}, "apps": [], "ecoute": [], "cnx_in": [], "cnx_out": [], "services": [],
            "ips": [], "declare": True, "note": manuel.get("note")}


def hors_ligne(reports):
    """#859 : relevés guest-usage [(agent, hôte, at, data)] -> {nœud/vmid: inventaire} (invités démarrés, CT montés, VM
    arrêtées lues hors ligne) ; le plus frais l'emporte."""
    out = {}
    for _a, _h, at, d in sorted(reports or [], key=lambda r: str(r[2])):
        for n in (d or {}).get("nodes") or []:
            for g in n.get("guests") or []:
                if g.get("systeme"):
                    out["%s/%s" % (n.get("name"), g.get("vmid"))] = g["systeme"]
    return out


def assemble(nodes, maintenant=None, eol=None, libelles=None, manuels=None, lus=None):
    """nodes = {nom: relevé pve-preflight d'un nœud} -> {systemes, dependances, resume} ; manuels = fiches déclarées ;
    lus = inventaires de la sonde guest-usage (dont VM arrêtées lues hors ligne), utilisés quand pve-preflight n'a rien."""
    now = maintenant or time.time()
    eol = dict(EOL, **(eol or {}))
    libelles = libelles or {}
    manuels = manuels or {}
    lus = lus or {}
    sys_ = []
    for n, node in sorted((nodes or {}).items()):
        if not node.get("ok", True):
            continue
        sn = node.get("systeme")
        pv = node.get("pveversion") or ""
        sys_.append({"key": "node:%s" % n, "type": "nœud", "node": n, "vmid": None, "name": n, "status": "running", "systeme": sn, "charge": None,
                     "ips": (sn or {}).get("ips") or [], "pveversion": pv})
        for g in node.get("guests") or []:
            if g.get("template"):
                continue
            s = g.get("systeme")
            ips = list(dict.fromkeys(((g.get("conf") or {}).get("ips") or []) + ((s or {}).get("ips") or [])
                                     + ((lus.get("%s/%s" % (n, g["vmid"])) or {}).get("ips") or [])))
            sys_.append({"key": "%s/%s" % (n, g["vmid"]), "type": "CT" if g.get("type") == "lxc" else "VM", "node": n, "vmid": g["vmid"],
                         "name": g.get("name") or "", "status": g.get("status"), "systeme": s, "charge": g.get("charge"), "ips": ips})
    par_ip = {}
    for s in sys_:
        for ip in s["ips"]:
            par_ip.setdefault(ip, s["key"])
    deps = []
    for s in sys_:
        for c in (s["systeme"] or {}).get("cnx_out") or []:
            cible = par_ip.get(c["hote"])
            if cible and cible != s["key"]:
                d = {"de": s["key"], "vers": cible, "port": c["port"], "n": c["n"], "nature": ROLES_PORT.get(c["port"], "port %s" % c["port"])}
                if not any(x["de"] == d["de"] and x["vers"] == d["vers"] and x["port"] == d["port"] for x in deps):
                    deps.append(d)
    lignes = []
    for s in sys_:
        sy = s["systeme"]
        source = "relevé"
        if (not sy or not (sy.get("os") or {}).get("id")) and (lus.get(s["key"]) or {}).get("os"):
            sy, source = lus[s["key"]], ("lu hors ligne" if s["status"] != "running" else "relevé (activité)")
        elif (not sy or not (sy.get("os") or {}).get("id")) and manuels.get(s["key"]):
            sy, source = declaration(manuels[s["key"]]), "déclaré"
        elif not sy or not (sy.get("os") or {}).get("id"):
            source = "aucune"
        fam, ver, nom_os = os_de(sy)
        fin, _k = fin_support(fam, ver, eol) if fam else (None, None)
        st_os = statut_fin(fin, now) if fin else ("inconnu" if sy else "non relevé")
        comp = composants(sy, st_os, now, eol)
        maj = (sy or {}).get("maj_at")
        maj_j = int((now - maj) // 86400) if maj else None
        att, secu = (sy or {}).get("attente"), (sy or {}).get("attente_secu")
        ext = [e for e in (sy or {}).get("ecoute") or [] if not e["hote"].startswith(("127.", "[::1]", "::1"))]
        expose = any(public(ip) for ip in s["ips"]) and bool(ext)
        u, ud = usage(s["status"], s["charge"], sy)
        dependants = sorted({d["de"] for d in deps if d["vers"] == s["key"]})
        utilise = sorted({d["vers"] for d in deps if d["de"] == s["key"]})
        score, raisons, actions = 0, [], []
        if st_os == "obsolète":
            score += 3
            raisons.append("système plus maintenu depuis le %s (%s)" % (fin, nom_os))
            actions.append("mettre à niveau le système (%s → version maintenue)" % nom_os)
        elif st_os == "fin proche":
            score += 1
            raisons.append("fin de support du système le %s" % fin)
            actions.append("planifier la mise à niveau du système avant le %s" % fin)
        elif st_os in ("inconnu", "non relevé"):
            if s["status"] == "running":
                score += 1
            raisons.append("système non identifié (%s)" % ("agent invité QEMU absent ou Windows" if s["type"] == "VM" else "relevé impossible"))
            actions.append("installer l'agent invité QEMU (VM Linux) ou déclarer le système à la main" if s["type"] == "VM" else "déclarer le système à la main")
        if secu:
            score += 2
            raisons.append("%d mise(s) à jour de sécurité en attente" % secu)
            actions.append("appliquer les mises à jour de sécurité")
        elif att and att > 50:
            score += 1
            raisons.append("%d mises à jour en attente" % att)
        if maj_j is not None and maj_j > 365:
            score += 2
            raisons.append("aucune mise à jour depuis %d jours" % maj_j)
            if "appliquer les mises à jour de sécurité" not in actions:
                actions.append("mettre à jour les paquets")
        elif maj_j is not None and maj_j > 90:
            score += 1
            raisons.append("dernière mise à jour il y a %d jours" % maj_j)
        proche = [c for c in comp if c["statut"] == "fin proche"]
        if proche:
            score += 1
            raisons.append("fin de support proche : %s" % ", ".join("%s %s (%s)" % (c["nom"], c["version"], c["fin"]) for c in proche))
            actions.extend("planifier le remplacement de %s %s avant le %s" % (c["nom"], c["version"], c["fin"]) for c in proche)
        obs = [c for c in comp if c["statut"] == "obsolète"]
        if obs:
            score += min(3, 2 * len(obs))
            raisons.append("version(s) obsolète(s) : %s" % ", ".join("%s %s" % (c["nom"], c["version"]) for c in obs))
            actions.extend("remplacer %s %s par une version maintenue" % (c["nom"], c["version"]) for c in obs)
        if expose and (st_os == "obsolète" or obs or secu):
            score += 2
            raisons.append("exposé sur Internet (%s)" % ", ".join(sorted({str(e["port"]) for e in ext})[:8]))
            actions.append("limiter l'accès depuis Internet en attendant la mise à niveau")
        impact = len(dependants) + (2 if u == "fort" else 1 if u == "moyen" else 0)
        if s["status"] != "running":
            niveau = "inactif"
            if st_os == "obsolète":
                actions = ["archiver puis supprimer s'il n'est plus utile"]
        else:
            niveau = "urgent" if score >= 5 else "à planifier" if score >= 3 else "à surveiller" if score >= 1 else "ok"
            if niveau == "à planifier" and impact >= 3:
                niveau = "urgent"
                raisons.append("très utilisé ou dont dépendent d'autres systèmes")
        lignes.append({"key": s["key"], "type": s["type"], "node": s["node"], "vmid": s["vmid"], "name": s["name"], "libelle": libelles.get(s["key"]),
                       "status": s["status"], "os": {"famille": fam, "version": ver, "nom": nom_os, "fin": fin, "statut": st_os},
                       "noyau": (sy or {}).get("noyau"), "maj_at": maj, "maj_jours": maj_j, "attente": att, "attente_secu": secu,
                       "composants": comp, "roles": roles(sy), "services": (sy or {}).get("services") or [],
                       "ecoute": [{"port": e["port"], "proc": e["proc"]} for e in ext], "expose": expose, "ips": s["ips"],
                       "usage": u, "usage_detail": ud, "dependants": dependants, "utilise": utilise, "impact": impact,
                       "score": score, "niveau": niveau, "raisons": raisons, "actions": list(dict.fromkeys(actions)), "releve": bool(sy),
                       "source": source, "note": (sy or {}).get("note")})
    ordre = {n: i for i, n in enumerate(NIVEAUX)}
    lignes.sort(key=lambda l: (ordre[l["niveau"]], -l["score"], -l["impact"], l["node"], l["vmid"] or 0))
    res = {n: sum(1 for l in lignes if l["niveau"] == n) for n in NIVEAUX}
    res["obsoletes"] = sum(1 for l in lignes if l["os"]["statut"] == "obsolète" and l["status"] == "running")
    res["secu"] = sum(1 for l in lignes if (l["attente_secu"] or 0) > 0)
    res["exposes"] = sum(1 for l in lignes if l["expose"])
    res["inconnus"] = sum(1 for l in lignes if l["source"] == "aucune")
    return {"at": now, "systemes": lignes, "dependances": deps, "resume": res, "eol": eol}


def instantane(etat):
    """Ce qu'on garde chaque jour pour le suivi à long terme."""
    return {"resume": etat["resume"], "systemes": {l["key"]: {"niveau": l["niveau"], "os": l["os"]["nom"], "secu": l["attente_secu"], "score": l["score"]}
                                                   for l in etat["systemes"]}}


def tendance(historique):
    """[(jour, instantané)] -> [{jour, urgent, à planifier, …}] dans l'ordre des jours."""
    return [dict({"jour": j}, **{k: (d.get("resume") or {}).get(k, 0) for k in NIVEAUX + ("obsoletes", "secu", "exposes")}) for j, d in sorted(historique or [])]
