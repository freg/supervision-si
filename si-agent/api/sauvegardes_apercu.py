"""#937 : tuile « Sauvegardes » -- aperçu central de toutes les sauvegardes du SI, assemblé à partir des mesures déjà
remontées (aucune commande envoyée, aucun accès aux équipements) :

- postes : dernière sauvegarde de conf (sauvegarde-poste) de chaque agent Windows + dernière poussée PBS (pbs-push du
  pousseur, backup_id = agent) -> état par poste ;
- pbs : sonde `pbs` (datastores, groupes, alertes) ;
- copies host/VM : sonde `pulled-backups` (journal pve-pull-backup / zfs-secours) et inventaire des copies ;
- nas : volumes des NAS (nas-snmp) + snapshots / Time Machine / RAID / partages par SSH (nas-qnap, #939) ;
- backuppc : sonde `backuppc` (#939) sur le serveur BackupPC (hôtes, échecs, pool) ; « non relevé » sans mesure.

Module pur (pas de Flask, pas de SQLite) : `assembler(...)` prend les listes de mesures et renvoie le JSON de la tuile ;
testé par test_z_sauvegardes_apercu.py. Les secrets n'apparaissent jamais ici (les mesures n'en contiennent pas).
"""
from datetime import datetime, timezone

POSTE_FRAIS_J = 7        # sauvegarde de conf « fraîche » si moins de 7 jours
POSTE_VIEUX_J = 30       # au-delà : critique


def _epoch(at):
    """ISO -> secondes epoch (None si illisible). Accepte « Z » et sans fuseau (UTC)."""
    if not at:
        return None
    if isinstance(at, (int, float)):
        return float(at)
    try:
        s = str(at).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except (TypeError, ValueError):
        return None


def _age_j(at, now):
    e = _epoch(at)
    return None if e is None else round(max(0.0, now - e) / 86400.0, 1)


def postes(sauvegardes, pousses, agents, now):
    """sauvegardes : [(agent_id, hostname, at, data)] mesures sauvegarde-poste ; pousses : [data pbs-push] du pousseur ;
    agents : [{agent_id, hostname, os?, active?}] (postes Windows candidats). -> liste triée par état puis nom."""
    par_poste = {a: (h, at, d) for a, h, at, d in sauvegardes}
    pbs_par_poste = {}
    for p in pousses:
        bid = (p or {}).get("backup_id")
        if bid and bid not in pbs_par_poste:       # pousses supposées de la plus récente à la plus ancienne
            pbs_par_poste[bid] = p
    out = []
    for a in agents:
        aid = a.get("agent_id")
        h, at, d = par_poste.get(aid, (a.get("hostname"), None, None))
        d = d or {}
        age = _age_j(at, now)
        dests = [x for x in (d.get("destinations") or []) if isinstance(x, dict)]
        dest_ok = [x.get("type") for x in dests if x.get("ok")]
        dest_ko = [x.get("type") for x in dests if not x.get("ok")]
        arch = d.get("archive") if isinstance(d.get("archive"), dict) else {}
        pb = pbs_par_poste.get(aid) or {}
        if at is None:
            etat, raison = "jamais", "aucune sauvegarde de conf remontée"
        elif d.get("erreurs") and not arch.get("nom"):
            etat, raison = "critique", "dernière sauvegarde en échec"
        elif age is not None and age > POSTE_VIEUX_J:
            etat, raison = "critique", "dernière sauvegarde il y a %d j" % int(age)
        elif dest_ko and not dest_ok:
            etat, raison = "critique", "archive produite mais aucune destination écrite"
        elif age is not None and age > POSTE_FRAIS_J:
            etat, raison = "attention", "dernière sauvegarde il y a %d j" % int(age)
        elif dest_ko:
            etat, raison = "attention", "destination en échec : %s" % ", ".join(str(x) for x in dest_ko)
        else:
            etat, raison = "ok", ""
        out.append({"agent_id": aid, "hostname": h or a.get("hostname") or aid, "at": at, "age_j": age, "etat": etat, "raison": raison,
                    "archive": arch.get("nom"), "octets": arch.get("octets"), "destinations_ok": dest_ok, "destinations_ko": dest_ko,
                    "confs": len(d.get("confs") or []), "montages": len(d.get("montages") or []),
                    "pbs": {"ok": pb.get("ok"), "snapshot": pb.get("snapshot"), "erreur": pb.get("erreur")} if pb else None})
    rang = {"critique": 0, "jamais": 1, "attention": 2, "ok": 3}
    out.sort(key=lambda p: (rang.get(p["etat"], 9), str(p["hostname"]).lower()))
    return out


def pbs(mesures):
    """mesures : [(agent_id, hostname, at, data)] de plugin:pbs -> [{serveur, at, datastores, groupes, alertes, etat}]."""
    out = []
    for aid, h, at, d in mesures:
        d = d or {}
        s = d.get("summary") or {}
        out.append({"agent_id": aid, "serveur": h or aid, "at": at, "erreur": d.get("error"),
                    "datastores": [{"nom": x.get("name"), "pct": x.get("used_percent"), "total": x.get("total"), "libre": x.get("avail")}
                                   for x in (d.get("datastores") or []) if isinstance(x, dict)],
                    "groupes": len(d.get("groups") or []), "en_retard": s.get("late", sum(1 for g in (d.get("groups") or []) if g.get("state") == "en retard")),
                    "inactifs": sum(1 for g in (d.get("groups") or []) if g.get("state") == "inactif"),
                    "alertes": [a.get("message") for a in (d.get("alerts") or []) if isinstance(a, dict)],
                    "etat": "erreur" if d.get("error") else {"critical": "critique", "warning": "attention"}.get(s.get("state"), "ok")})
    return out


def copies(mesures, inventaire_resume=None, now=None):
    """mesures plugin:pulled-backups -> par hôte de secours : dernières copies, échecs, espace libre. `inventaire_resume`
    (copies.assemble(...)['resume']) = verdicts des invités (ok/attention/critique/info)."""
    hotes = []
    for aid, h, at, d in mesures:
        d = d or {}
        bks = [b for b in (d.get("backups") or []) if isinstance(b, dict)]
        hotes.append({"agent_id": aid, "hote": h or aid, "at": at, "erreur": d.get("error"), "libre": d.get("free_bytes"),
                      "copies": len(bks), "echecs": sum(1 for b in bks if not b.get("ok")),
                      "absentes": sum(1 for b in bks if b.get("present") is False),
                      "plus_vieille_h": max([b.get("age_h") for b in bks if isinstance(b.get("age_h"), (int, float))] or [None]),
                      "alertes": [a.get("message") if isinstance(a, dict) else str(a) for a in (d.get("alerts") or [])]})
    res = inventaire_resume or {}
    return {"hotes": hotes, "invites": {"ok": res.get("ok", 0), "attention": res.get("attention", 0), "critique": res.get("critique", 0), "info": res.get("info", 0)}}


def nas(mesures, mesures_ssh=None):
    """plugin:nas-snmp -> [{nom, at, volumes:[{nom, pct, ko}], etat, snapshots, timemachine}] ; #939 : complété par la sonde
    nas-qnap (SSH) -- snapshots par volume, Time Machine, RAID, partages, outils -- rapprochée par nom ou par adresse."""
    ssh = {}
    for aid, h, at, d in mesures_ssh or []:
        for n in ((d or {}).get("nas") or []):
            if isinstance(n, dict):
                n = dict(n, relais_ssh=h or aid, relais_id=aid, at_ssh=at)
                ssh[str(n.get("name") or "").lower()] = n
                if n.get("host"):
                    ssh[str(n["host"]).lower()] = n
    out = []
    vus = set()
    for aid, h, at, d in mesures:
        for n in ((d or {}).get("nas") or []):
            if not isinstance(n, dict):
                continue
            vols = [{"nom": v.get("nom"), "pct": v.get("pct"), "ko": v.get("ko"), "libre_ko": v.get("libre_ko")} for v in (n.get("volumes") or []) if isinstance(v, dict)]
            pires = [v["pct"] for v in vols if isinstance(v.get("pct"), (int, float))]
            e = {"nom": n.get("name"), "hote": n.get("host"), "relais": h or aid, "at": at, "ok": n.get("ok", True), "erreur": n.get("error"),
                 "volumes": vols, "etat": "erreur" if not n.get("ok", True) else "critique" if pires and max(pires) >= 95 else "attention" if pires and max(pires) >= 85 else "ok",
                 "snapshots": None, "timemachine": None, "ssh": None,
                 "snmp": {"disques": n.get("disques") or [], "raid": n.get("raid") or [], "reserves": n.get("reserves") or [], "applications": n.get("applications") or [], "systeme": n.get("systeme") or {}}}   # #944 : pour les conseils
            x = ssh.get(str(n.get("name") or "").lower()) or ssh.get(str(n.get("host") or "").lower())
            if x:
                vus.add(id(x))
                _completer_ssh(e, x)
            out.append(e)
    for x in {id(v): v for v in ssh.values()}.values():          # NAS relevés par SSH seulement
        if id(x) in vus:
            continue
        e = {"nom": x.get("name"), "hote": x.get("host"), "relais": x.get("relais_ssh"), "at": x.get("at_ssh"), "ok": x.get("ok", True), "erreur": x.get("error"),
             "volumes": [{"nom": v.get("nom"), "pct": v.get("pct"), "ko": v.get("ko"), "libre_ko": v.get("libre_ko")} for v in (x.get("volumes") or [])],
             "etat": "erreur" if not x.get("ok", True) else "ok", "snapshots": None, "timemachine": None, "ssh": None}
        _completer_ssh(e, x)
        out.append(e)
    return out


def _completer_ssh(e, x):
    """Fusionne la fiche SSH (nas-qnap) dans l'entrée d'aperçu : snapshots, Time Machine, RAID, partages, outils, alertes."""
    if not x.get("ok", True):
        e["ssh"] = {"ok": False, "erreur": x.get("error"), "relais": x.get("relais_ssh"), "at": x.get("at_ssh")}
        return
    e["snapshots"] = x.get("snapshots") or []
    e["timemachine"] = x.get("timemachine") or []
    e["ssh"] = {"ok": True, "relais": x.get("relais_ssh"), "relais_id": x.get("relais_id"), "at": x.get("at_ssh"), "raid": x.get("raid") or [], "partages": x.get("partages") or [],
                "partages_timemachine": x.get("partages_timemachine") or [], "volumes_sans_snapshot": x.get("volumes_sans_snapshot") or [],
                "outils": x.get("outils") or [], "systeme": x.get("systeme") or {}, "alertes": [a.get("message") for a in (x.get("alertes") or []) if isinstance(a, dict)],
                "connexions": x.get("connexions") or {}, "journaux": x.get("journaux") or {}, "erreurs_acces": x.get("erreurs_acces") or [], "aide": x.get("aide") or {}}   # #940
    sev = [a.get("severity") for a in (x.get("alertes") or []) if isinstance(a, dict)]
    if "critical" in sev and e["etat"] != "erreur":
        e["etat"] = "critique"
    elif "warning" in sev and e["etat"] == "ok":
        e["etat"] = "attention"


def backuppc(mesures):
    """#939 : plugin:backuppc -> {etat, serveurs:[{agent_id, serveur, version, at, hotes, echecs, en_cours, pool_pct, alertes, hotes_detail}]}.
    Sans mesure : « non relevé » (sonde backuppc à activer sur le serveur BackupPC)."""
    serveurs = []
    for aid, h, at, d in mesures or []:
        d = d or {}
        s = d.get("summary") or {}
        pool = d.get("pool") or {}
        serveurs.append({"agent_id": aid, "serveur": h or aid, "at": at, "version": (d.get("serveur") or {}).get("version"),
                         "erreur": (d.get("serveur") or {}).get("erreur"), "hotes": s.get("hotes", len(d.get("hotes") or [])),
                         "echecs": s.get("echecs", len(d.get("echecs") or [])), "en_cours": s.get("en_cours", 0),
                         "pool_pct": pool.get("topdir_pct") if pool.get("topdir_pct") is not None else pool.get("fs_pct"),
                         "pool_octets": pool.get("cpool_octets"), "prochain_reveil": (d.get("serveur") or {}).get("prochain_reveil"),
                         "alertes": [a.get("message") for a in (d.get("alerts") or []) if isinstance(a, dict)],
                         "etat": {"critical": "critique", "warning": "attention"}.get(s.get("state"), "ok"),
                         "hotes_detail": d.get("hotes") or [], "echecs_detail": d.get("echecs") or [], "files": d.get("files") or {}})
    if not serveurs:
        return {"etat": "non relevé", "message": "sonde backuppc à activer sur l'agent du serveur BackupPC (fiche de l'agent › Sondes)", "serveurs": []}
    pire = "critique" if any(x["etat"] == "critique" for x in serveurs) else "attention" if any(x["etat"] == "attention" for x in serveurs) else "ok"
    return {"etat": pire, "message": "%d serveur(s), %d hôte(s), %d échec(s)" % (len(serveurs), sum(x["hotes"] for x in serveurs), sum(x["echecs"] for x in serveurs)), "serveurs": serveurs}


def resume(p, b, c, n, backuppc):
    """Compteurs de la vue d'ensemble + verdict global."""
    crit = sum(1 for x in p if x["etat"] == "critique") + sum(1 for x in b if x["etat"] in ("critique", "erreur")) \
        + c["invites"].get("critique", 0) + sum(1 for x in n if x["etat"] in ("critique", "erreur")) + (1 if backuppc.get("etat") == "critique" else 0)
    att = sum(1 for x in p if x["etat"] in ("attention", "jamais")) + sum(1 for x in b if x["etat"] == "attention") \
        + c["invites"].get("attention", 0) + sum(1 for x in n if x["etat"] == "attention") + sum(h["echecs"] for h in c["hotes"]) \
        + (1 if backuppc.get("etat") == "attention" else 0)
    return {"postes": {"total": len(p), "ok": sum(1 for x in p if x["etat"] == "ok"), "jamais": sum(1 for x in p if x["etat"] == "jamais")},
            "pbs": {"serveurs": len(b), "groupes": sum(x["groupes"] for x in b), "en_retard": sum(x["en_retard"] or 0 for x in b)},
            "copies": {"hotes": len(c["hotes"]), "copies": sum(h["copies"] for h in c["hotes"]), "echecs": sum(h["echecs"] for h in c["hotes"]), "invites": c["invites"]},
            "nas": {"total": len(n)}, "backuppc": backuppc.get("etat"),
            "verdict": "critique" if crit else "attention" if att else "ok", "critiques": crit, "attentions": att}


def assembler(sauvegardes, pousses, agents, mesures_pbs, mesures_copies, inventaire_resume, mesures_nas, mesures_backuppc=None, now=None, mesures_nas_ssh=None):
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    p = postes(sauvegardes, pousses, agents, now)
    b = pbs(mesures_pbs)
    c = copies(mesures_copies, inventaire_resume, now)
    n = nas(mesures_nas, mesures_nas_ssh)
    bpc = backuppc(mesures_backuppc)
    return {"resume": resume(p, b, c, n, bpc), "postes": p, "pbs": b, "copies": c, "nas": n, "backuppc": bpc}
