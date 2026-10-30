"""#937 : tuile « Sauvegardes » -- aperçu central de toutes les sauvegardes du SI, assemblé à partir des mesures déjà
remontées (aucune commande envoyée, aucun accès aux équipements) :

- postes : dernière sauvegarde de conf (sauvegarde-poste) de chaque agent Windows + dernière poussée PBS (pbs-push du
  pousseur, backup_id = agent) -> état par poste ;
- pbs : sonde `pbs` (datastores, groupes, alertes) ;
- copies host/VM : sonde `pulled-backups` (journal pve-pull-backup / zfs-secours) et inventaire des copies ;
- nas : volumes des NAS (nas-snmp) -- les snapshots / TimeMachine viendront d'un connecteur dédié ;
- backuppc : sonde à venir (#938) -> « non relevé ».

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


def nas(mesures):
    """plugin:nas-snmp -> [{nom, at, volumes:[{nom, pct, ko}], etat}] (les snapshots/TimeMachine viendront du connecteur QNAP)."""
    out = []
    for aid, h, at, d in mesures:
        for n in ((d or {}).get("nas") or []):
            if not isinstance(n, dict):
                continue
            vols = [{"nom": v.get("nom"), "pct": v.get("pct"), "ko": v.get("ko"), "libre_ko": v.get("libre_ko")} for v in (n.get("volumes") or []) if isinstance(v, dict)]
            pires = [v["pct"] for v in vols if isinstance(v.get("pct"), (int, float))]
            out.append({"nom": n.get("name"), "hote": n.get("host"), "relais": h or aid, "at": at, "ok": n.get("ok", True), "erreur": n.get("error"),
                        "volumes": vols, "etat": "erreur" if not n.get("ok", True) else "critique" if pires and max(pires) >= 95 else "attention" if pires and max(pires) >= 85 else "ok",
                        "snapshots": None, "timemachine": None})     # connecteur QNAP à venir
    return out


def resume(p, b, c, n, backuppc):
    """Compteurs de la vue d'ensemble + verdict global."""
    crit = sum(1 for x in p if x["etat"] == "critique") + sum(1 for x in b if x["etat"] in ("critique", "erreur")) \
        + c["invites"].get("critique", 0) + sum(1 for x in n if x["etat"] in ("critique", "erreur"))
    att = sum(1 for x in p if x["etat"] in ("attention", "jamais")) + sum(1 for x in b if x["etat"] == "attention") \
        + c["invites"].get("attention", 0) + sum(1 for x in n if x["etat"] == "attention") + sum(h["echecs"] for h in c["hotes"])
    return {"postes": {"total": len(p), "ok": sum(1 for x in p if x["etat"] == "ok"), "jamais": sum(1 for x in p if x["etat"] == "jamais")},
            "pbs": {"serveurs": len(b), "groupes": sum(x["groupes"] for x in b), "en_retard": sum(x["en_retard"] or 0 for x in b)},
            "copies": {"hotes": len(c["hotes"]), "copies": sum(h["copies"] for h in c["hotes"]), "echecs": sum(h["echecs"] for h in c["hotes"]), "invites": c["invites"]},
            "nas": {"total": len(n)}, "backuppc": backuppc.get("etat"),
            "verdict": "critique" if crit else "attention" if att else "ok", "critiques": crit, "attentions": att}


def assembler(sauvegardes, pousses, agents, mesures_pbs, mesures_copies, inventaire_resume, mesures_nas, backuppc=None, now=None):
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    p = postes(sauvegardes, pousses, agents, now)
    b = pbs(mesures_pbs)
    c = copies(mesures_copies, inventaire_resume, now)
    n = nas(mesures_nas)
    bpc = backuppc or {"etat": "non relevé", "message": "sonde backuppc à activer sur le serveur BackupPC (à venir)"}
    return {"resume": resume(p, b, c, n, bpc), "postes": p, "pbs": b, "copies": c, "nas": n, "backuppc": bpc}
