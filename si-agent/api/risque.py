# -*- coding: utf-8 -*-
"""#856 : Migration › « Risques » -- récapitulatif PERMANENT du risque de chaque CT / VM, sur cinq axes :
  réplication (pvesr : dernière synchro, échecs), sauvegarde (inventaire des copies : distance, volume, survie à la
  perte du nœud), accessibilité des services (acces.py), support (pool du disque : santé, redondance), nœud (quorum,
  nœud à réinstaller). Niveau : critique / élevé / moyen / faible. Pur, testé dans test_z_risque.py."""
import datetime as dt
import time

ORDRE = {"critique": 3, "élevé": 2, "moyen": 1, "faible": 0}
REPLI_RETARD_S = 3600


def _ts(s):
    try:
        return dt.datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def replication(jobs, maintenant):
    if not jobs:
        return {"etat": "aucune", "texte": "pas de réplication"}
    pire, txt = "ok", []
    for j in jobs:
        t = _ts(j.get("last_sync"))
        age = (maintenant - t) if t else None
        if (j.get("fail_count") or 0) > 0:
            e = "critique"
            txt.append("%s vers %s : %s échec(s)" % (j["job"], j["target"], j["fail_count"]))
        elif not j.get("enabled", True):
            e = "attention"
            txt.append("%s vers %s : désactivée" % (j["job"], j["target"]))
        elif age is None or age > REPLI_RETARD_S:
            e = "attention"
            txt.append("%s vers %s : dernière synchro %s" % (j["job"], j["target"], "inconnue" if age is None else "il y a %d min" % (age // 60)))
        else:
            e = "ok"
            txt.append("%s vers %s : il y a %d min" % (j["job"], j["target"], age // 60))
        pire = max(pire, e, key=lambda x: {"ok": 0, "attention": 1, "critique": 2}[x])
    return {"etat": pire, "texte": " ; ".join(txt)}


def sauvegarde(inv):
    if not inv:
        return {"etat": "inconnu", "texte": "absent de l'inventaire des copies"}
    v = inv["verdict"]
    b = inv.get("meilleure")
    t = ("meilleure copie hors du nœud : %s %s (%s)" % (b["type"], b["hote"], b["distance"])) if b else "aucune copie hors du nœud"
    return {"etat": {"info": "ok"}.get(v, v), "texte": t + ("" if not inv["raisons"] else " -- " + " ; ".join(inv["raisons"]))}


def accessibilite(status, res):
    if status != "running":
        return {"etat": "na", "texte": "arrêté"}
    if not res:
        return {"etat": "inconnu", "texte": "aucun service surveillé (pas d'adresse fixe connue : ajouter une cible)"}
    ko = [c for c in res["cibles"] if not c["ok"]]
    e = {"ok": "ok", "partiel": "attention", "panne": "critique"}.get(res["etat"], "inconnu")
    return {"etat": e, "texte": "%d / %d joignable(s)%s" % (len(res["cibles"]) - len(ko), len(res["cibles"]),
                                                              "" if not ko else " ; injoignable : " + ", ".join(c["cible"] for c in ko[:4]))}


def support(pools_noeud, pools_invite):
    f, e = [], "ok"
    for p in pools_invite:
        info = next((x for x in pools_noeud if x.get("name") == p), None)
        if not info:
            continue
        if info.get("health") and info["health"] != "ONLINE":
            e = "critique"
            f.append("pool %s %s" % (p, info["health"]))
        if info.get("redondance") == "non":
            e = "critique" if e == "critique" else "attention"
            f.append("pool %s sans redondance" % p)
    return {"etat": e, "texte": " ; ".join(f) or ("pool %s sain" % ", ".join(pools_invite) if pools_invite else "disques hors ZFS ou inconnus")}


def noeud(node, prep_noeud, cible):
    f, e = [], "ok"
    q = (prep_noeud or {}).get("quorum") or {}
    if q and q.get("quorate") is False:
        e = "critique"
        f.append("cluster sans quorum")
    if cible and node == cible:
        e = "critique" if e == "critique" else "attention"
        f.append("nœud à réinstaller : invité à déplacer ou archiver")
    return {"etat": e, "texte": " ; ".join(f) or "—"}


def niveau(axes):
    etats = [a["etat"] for a in axes.values()]
    if "critique" in etats:
        return "critique"
    n = etats.count("attention")
    if n >= 2:
        return "élevé"
    if n == 1 or (axes["acces"]["etat"] == "inconnu"):
        return "moyen"
    return "faible"


def assemble(inventaire, hotes_copies, prep_noeuds, acces_res, cible=None, maintenant=None):
    now = maintenant or time.time()
    lignes = []
    hc = {h["name"]: h for h in (hotes_copies or {}).values()} if isinstance(hotes_copies, dict) else {h["name"]: h for h in hotes_copies or []}
    for inv in (inventaire or {}).get("invites") or []:
        if inv.get("copie_de"):
            continue                       # un CT restauré (9xxx) n'est pas une source : il apparaît comme copie
        h = hc.get(inv["node"]) or {}
        jobs = [j for j in h.get("replication") or [] if j.get("vmid") == inv["vmid"]]
        pools = sorted({z["name"].split("/")[0] for z in h.get("zfs") or [] if not z.get("snap") and z["name"].split("/")[-1] in inv["disques"]})
        axes = {"replication": replication(jobs, now), "sauvegarde": sauvegarde(inv),
                "acces": accessibilite(inv["status"], (acces_res or {}).get(inv["key"])),
                "support": support(h.get("pools") or [], pools), "noeud": noeud(inv["node"], (prep_noeuds or {}).get(inv["node"]), cible)}
        if axes["replication"]["etat"] == "aucune":
            axes["replication"]["etat"] = "ok" if inv["status"] != "running" else "na"
        lignes.append({"key": inv["key"], "node": inv["node"], "vmid": inv["vmid"], "name": inv["name"], "type": inv["type"], "status": inv["status"],
                       "taille": inv.get("taille"), "axes": axes, "niveau": niveau(axes)})
    lignes.sort(key=lambda l: (-ORDRE[l["niveau"]], l["node"], l["vmid"]))
    res = {k: sum(1 for l in lignes if l["niveau"] == k) for k in ORDRE}
    return {"at": now, "cible": cible, "lignes": lignes, "resume": res,
            "noeuds": [{"name": n, "pools": [{k: p.get(k) for k in ("name", "health", "redondance", "disques_simples", "alloc", "size")} for p in h.get("pools") or []]}
                       for n, h in sorted(hc.items())]}
