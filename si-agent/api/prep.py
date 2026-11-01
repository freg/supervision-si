# -*- coding: utf-8 -*-
"""#815 : Migration › « Préparer la réinstallation d'un nœud » -- assemblage PUR des relevés pve-preflight (quorum,
réplications, stockages, sauvegardes, tâches, charge et erreurs de chaque CT / VM), des copies tirées vers le LAN
(pulled-backups) et des fiches des invités (décision garder / migrer / archiver…) :

  1. quorum : état actuel, simulation « sans le nœud à réinstaller », version (un PVE >= 6 réinstallé ne rejoint pas un
     cluster 5.4), HA ; actions dans l'ordre, une commande à la fois, avec la machine où la lancer ;
  2. vérification des invités transférés et de tous ceux du nœud d'accueil : état, charge 24 h (moyenne, pic), erreurs
     du journal 24 h, unités en échec, taux HTTP 5xx -> verdict ;
  3. sauvegardes : dernière sauvegarde locale (et si elle survit à la perte du nœud : stockage partagé ou autre nœud),
     dernière tâche vzdump (réussie / en échec), copie au LAN, archives qui DISPARAÎTRONT avec la réinstallation ;
  4. PRA par CT / VM : scénarios possibles (réplica, sauvegarde hors du nœud, copie au LAN), RPO et RTO estimés,
     étapes ; hypothèses de débit réglables dans la page.
Testé dans test_z_prep.py."""
import datetime as dt
import re
import time

SEUILS = {"err_24h": (50, 500), "http_5xx_pct": (2.0, 10.0), "cpu_max_pct": (90.0, 99.0), "mem_max_pct": (90.0, 98.0),
          "sauvegarde_h": (24 * 8, 24 * 31)}
DEFAUTS = {"debit_restore": 150.0, "debit_lan": 40.0, "ip_min": 15.0, "demarrage_min": 5.0, "quorum_min": 5.0}
NIVEAUX = ("ok", "attention", "bloquant", "inconnu")


def _pire(*n):
    ordre = {"ok": 0, "inconnu": 1, "attention": 2, "bloquant": 3}
    return max([x for x in n if x] or ["ok"], key=lambda x: ordre[x])


def _seuil(v, s):
    if v is None:
        return None
    return "bloquant" if v >= s[1] else "attention" if v >= s[0] else "ok"


def _ts(at):
    """Horodatage d'une sauvegarde : epoch ou « AAAA-MM-JJTHH:MM:SS » (heure du nœud, prise pour UTC : ±2 h)."""
    if isinstance(at, (int, float)):
        return float(at)
    try:
        return dt.datetime.strptime(str(at)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def _sync_ts(s):
    try:
        return dt.datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def noeuds(reports):
    """[(agent, hôte, at, data pve-preflight)] -> {nom du nœud: relevé le plus récent} (un nœud vu par deux agents : le plus frais)."""
    out = {}
    for _aid, _host, at, d in reports or []:
        for n in (d or {}).get("nodes") or []:
            if not n.get("name"):
                continue
            n = dict(n, _at=at)
            if n["name"] not in out or (n.get("ok") and str(at) > str(out[n["name"]].get("_at"))) or not out[n["name"]].get("ok"):
                out[n["name"]] = n
    return out


def copies_lan(reports):
    """pulled-backups -> {vmid: {host, at, age_h, ok, size}} (copie réussie la plus récente)."""
    out = {}
    for _aid, _host, _at, d in reports or []:
        for b in (d or {}).get("backups") or []:
            v = b.get("vmid")
            if not isinstance(v, int) or not b.get("at"):
                continue
            if v not in out or b["at"] > out[v]["at"]:
                out[v] = {"host": b.get("host"), "at": b["at"], "age_h": b.get("age_h"), "ok": b.get("ok"), "size": b.get("size"), "present": b.get("present")}
    return out


def quorum(cible, accueil):
    """Quorum actuel, simulation sans la cible, version, et actions ordonnées (une commande à la fois)."""
    qa, qc = (accueil or {}).get("quorum"), (cible or {}).get("quorum")
    q = qa or qc
    nom_c, nom_a = (cible or {}).get("name"), (accueil or {}).get("name")
    out = {"cluster": q is not None, "actuel": q, "verdict": "inconnu", "detail": "", "actions": [], "versions": {}}
    for n in (cible, accueil):
        if n:
            out["versions"][n["name"]] = n.get("pveversion")
    vieux = [k for k, v in out["versions"].items() if v and re.search(r"pve-manager/[1-5]\.", v)]
    if q is None:
        out.update(verdict="ok" if (cible or accueil) else "inconnu", detail="nœuds hors cluster (ou pvecm illisible) : pas de quorum à préserver")
        return out
    votes_c = sum(m["votes"] for m in q.get("membres") or [] if not m.get("qdevice") and _meme(m["name"], cible)) or 1
    restants = (q.get("total") or 0) - votes_c
    besoin = q.get("quorum") or 0
    out["sans_cible"] = {"votes": restants, "quorum": besoin, "quorate": restants >= besoin}
    if not q.get("quorate"):
        out.update(verdict="bloquant", detail="le cluster n'a PAS le quorum maintenant (%s / %s votes) : /etc/pve est en lecture seule" % (q.get("total"), q.get("expected")))
    elif restants >= besoin:
        out.update(verdict="ok", detail="sans %s : %d vote(s) pour un quorum de %d -- le cluster garde le quorum%s" % (nom_c, restants, besoin, " (QDevice)" if q.get("qdevice") else ""))
    else:
        out.update(verdict="attention", detail="sans %s : %d vote(s) pour un quorum de %d -- %s perdra le quorum (configurations figées, aucun démarrage ni migration) dès l'arrêt de %s"
                   % (nom_c, restants, besoin, nom_a or "le nœud restant", nom_c))
        out["actions"] = [
            {"quand": "après l'arrêt de %s (avant toute manœuvre sur %s)" % (nom_c, nom_a), "ou": nom_a, "cmd": "pvecm expected 1",
             "pourquoi": "rend le quorum au nœud restant (temporaire, jusqu'au redémarrage de corosync)"},
            {"quand": "pendant la réinstallation", "ou": nom_a, "cmd": "pvecm status",
             "pourquoi": "vérifier « Quorate: Yes » avant de démarrer ou déplacer un invité"},
            {"quand": "si %s ne revient PAS dans ce cluster" % nom_c, "ou": nom_a, "cmd": "pvecm delnode %s" % nom_c,
             "pourquoi": "retire définitivement le nœud (il doit être éteint ; ne jamais le rallumer tel quel ensuite)"},
            {"quand": "durable (cluster à deux nœuds)", "ou": nom_a, "cmd": "pvecm qdevice setup <IP d'un hôte corosync-qnetd hors des deux nœuds>",
             "pourquoi": "un troisième vote évite de perdre le quorum à chaque arrêt d'un nœud"},
        ]
    if vieux:
        out["detail"] += (" · %s en PVE %s : un nœud réinstallé en PVE >= 6 (corosync 3) ne pourra PAS rejoindre ce cluster -- prévoir un cluster neuf "
                          "et des transferts par vzdump / zfs send" % (", ".join(vieux), "5.x"))
        out["verdict"] = _pire(out["verdict"], "attention")
    if (accueil or {}).get("ha", {}).get("actif") or (cible or {}).get("ha", {}).get("actif"):
        out["detail"] += " · ressources HA présentes : les retirer ou les déplacer avant d'arrêter le nœud"
        out["verdict"] = _pire(out["verdict"], "attention")
    return out


def _meme(nom_membre, noeud):
    """Un membre de pvecm (souvent une IP) est-il ce nœud ? (local = le nœud qui a fait le relevé)."""
    if not noeud:
        return False
    for m in (noeud.get("quorum") or {}).get("membres") or []:
        if m.get("local") and m["name"] == nom_membre:
            return True
    return nom_membre == noeud.get("name")


def sante(g):
    """Invité -> {verdict, raisons} d'après l'état, la charge et les erreurs relevées."""
    raisons, v = [], "ok"
    if g.get("status") != "running":
        return {"verdict": "inconnu" if g.get("status") == "stopped" else "attention", "raisons": ["arrêté" if g.get("status") == "stopped" else "état %s" % g.get("status")]}
    c, k = g.get("checks"), g.get("charge") or {}
    if c is None or c.get("erreur"):
        v = _pire(v, "inconnu")
        raisons.append("intérieur non lu" + (" (%s)" % c["erreur"] if c and c.get("erreur") else ""))
    else:
        s = _seuil(c.get("err_24h"), SEUILS["err_24h"])
        if s and s != "ok":
            raisons.append("%s erreur(s) au journal en 24 h" % c["err_24h"])
        v = _pire(v, s)
        if c.get("failed_units"):
            v = _pire(v, "attention")
            raisons.append("%s unité(s) systemd en échec" % c["failed_units"])
        if c.get("http_total"):
            pct = round(100.0 * (c.get("http_5xx") or 0) / c["http_total"], 2)
            s = _seuil(pct, SEUILS["http_5xx_pct"])
            v = _pire(v, s)
            if s != "ok":
                raisons.append("%s %% de réponses HTTP 5xx (%s requêtes)" % (pct, c["http_total"]))
    for cle, lib in (("cpu_max_pct", "pic CPU"), ("mem_max_pct", "pic mémoire")):
        s = _seuil(k.get(cle), SEUILS[cle])
        if s and s != "ok":
            v = _pire(v, "attention")
            raisons.append("%s %s %% sur 24 h" % (lib, k[cle]))
    return {"verdict": v, "raisons": raisons}


def sauvegardes(vmid, noeud_invite, tous, lan, maintenant, cible=None):
    """-> {locale (la plus récente), hors_noeud (survit à la perte du nœud ET à la réinstallation de la cible), tache, lan, verdict, raisons}."""
    copies = []
    for n in tous.values():
        stor = n.get("storages") or {}
        for b in n.get("backups") or []:
            if b.get("vmid") != vmid:
                continue
            s = stor.get(b.get("storage")) or {}
            t = _ts(b.get("at"))
            efface = n["name"] == cible and not s.get("shared")
            copies.append(dict(b, noeud=n["name"], partage=bool(s.get("shared")), ts=t, age_h=round((maintenant - t) / 3600, 1) if t else None,
                               efface=efface, hors_noeud=(bool(s.get("shared")) or n["name"] != noeud_invite) and not efface))
    copies.sort(key=lambda b: -(b["ts"] or 0))
    tache = None
    for n in tous.values():
        t = ((n.get("tasks") or {}).get("last_vzdump") or {}).get(str(vmid))
        if t and (tache is None or t["at"] > tache["at"]):
            tache = dict(t, noeud=n["name"], age_h=round((maintenant - t["at"]) / 3600, 1))
    hors = next((b for b in copies if b["hors_noeud"]), None)
    l = lan.get(vmid)
    raisons, v = [], "ok"
    meilleur = min([x for x in [hors and hors["age_h"], l and l.get("age_h")] if x is not None] or [None], key=lambda x: x if x is not None else 1e9)
    if meilleur is None:
        v = "bloquant"
        raisons.append("aucune copie hors du nœud %s%s" % (noeud_invite, " (celles de %s seront effacées)" % cible if any(b["efface"] for b in copies) else ""))
    else:
        s = _seuil(meilleur, SEUILS["sauvegarde_h"])
        v = _pire(v, s)
        if s != "ok":
            raisons.append("copie hors du nœud vieille de %d j" % round(meilleur / 24))
    if tache and not tache["ok"]:
        v = _pire(v, "attention")
        raisons.append("dernière tâche vzdump en échec (%s)" % tache["status"])
    return {"locale": copies[0] if copies else None, "hors_noeud": hors, "tache": tache, "lan": l, "nb": len(copies), "verdict": v, "raisons": raisons}


def pra(g, noeud_invite, tous, sv, params, quorum_perdu, cible=None):
    """Scénarios de reprise si le nœud de l'invité tombe -> {retenu, scenarios, verdict}. Tailles en octets, débits en Mo/s."""
    p = dict(DEFAUTS, **{k: v for k, v in (params or {}).items() if v is not None})
    taille = g.get("disk") or g.get("maxdisk") or 0
    go = taille / 1e9
    fixe = p["demarrage_min"] + (p["ip_min"] if (g.get("conf") or {}).get("vmac") else 0) + (p["quorum_min"] if quorum_perdu else 0)
    sc = []
    for n in tous.values():
        for j in n.get("replication") or []:
            if j.get("vmid") != g["vmid"] or j.get("target") == noeud_invite:
                continue
            t = _sync_ts(j.get("last_sync"))
            efface = j.get("target") == cible
            ok = (j.get("fail_count") or 0) == 0 and t is not None and not efface
            sc.append({"type": "replica", "titre": "réplica ZFS sur %s (job %s)" % (j["target"], j["job"]), "valide": ok,
                       "rpo_h": round((time.time() - t) / 3600, 2) if t else None, "rto_min": round(fixe, 0),
                       "etapes": ["sur %s : vérifier le quorum (pvecm status ; sinon pvecm expected 1)" % j["target"],
                                  "sur %s : mv /etc/pve/nodes/%s/%s/%s.conf /etc/pve/nodes/%s/%s/" % (j["target"], noeud_invite, "lxc" if g["type"] == "lxc" else "qemu-server", g["vmid"], j["target"], "lxc" if g["type"] == "lxc" else "qemu-server"),
                                  "sur %s : %s start %s" % (j["target"], "pct" if g["type"] == "lxc" else "qm", g["vmid"])]
                       + (["manager OVH : déplacer l'IP additionnelle (MAC virtuelle) vers %s" % j["target"]] if (g.get("conf") or {}).get("vmac") else []),
                       "remarque": None if ok else "réplica sur le nœud à réinstaller : il disparaît avec la réinstallation" if efface
                       else "réplication en échec ou jamais synchronisée : %s" % (j.get("state") or "?")})
    h = sv.get("hors_noeud")
    if h:
        sc.append({"type": "sauvegarde", "titre": "sauvegarde %s sur %s (%s)" % (h["storage"], h["noeud"], "partagé" if h["partage"] else "autre nœud"), "valide": True,
                   "rpo_h": h["age_h"], "rto_min": round(go * 1000 / p["debit_restore"] / 60 + fixe, 0),
                   "etapes": ["sur le nœud de reprise : %s %s %s --storage <stockage>" % ("pct restore" if g["type"] == "lxc" else "qmrestore", g["vmid"], h["volid"]),
                              "démarrer, puis déplacer l'IP additionnelle si MAC virtuelle"]})
    l = sv.get("lan")
    if l and l.get("ok") is not False:
        sc.append({"type": "lan", "titre": "copie au LAN (%s)" % (l.get("host") or "?"), "valide": True, "rpo_h": l.get("age_h"),
                   "rto_min": round(go * 1000 / p["debit_lan"] / 60 + go * 1000 / p["debit_restore"] / 60 + fixe, 0),
                   "etapes": ["envoyer l'archive du LAN vers le nœud de reprise (scp / rsync)", "restaurer (pct restore / qmrestore), démarrer, déplacer l'IP"]})
    loc = sv.get("locale")
    if loc and not loc["hors_noeud"]:
        sc.append({"type": "locale", "titre": "sauvegarde %s sur le même nœud" % loc["storage"], "valide": False, "rpo_h": loc["age_h"], "rto_min": None,
                   "etapes": [], "remarque": "ne couvre pas la perte du nœud (seulement une erreur dans l'invité)"})
    valides = [s for s in sc if s["valide"]]
    retenu = min(valides, key=lambda s: (s["rto_min"] if s["rto_min"] is not None else 1e9, s["rpo_h"] if s["rpo_h"] is not None else 1e9)) if valides else None
    if not retenu:
        v = "bloquant"
    else:
        v = _seuil(retenu["rpo_h"], SEUILS["sauvegarde_h"]) or "inconnu"
    return {"retenu": retenu, "scenarios": sc, "verdict": v, "taille_go": round(go, 1)}


def assemble(reports, lan_reports, profils, cible, accueil, params=None, transferes=(), maintenant=None, liens_sonde=(), manuel_sonde=None):
    maintenant = maintenant or time.time()
    tous = noeuds(reports)
    lan = copies_lan(lan_reports)
    nc, na = tous.get(cible), tous.get(accueil)
    q = quorum(nc, na)
    quorum_perdu = q.get("verdict") == "attention" and not (q.get("sans_cible") or {}).get("quorate", True)
    transferes = set(int(x) for x in transferes or [])
    migres = {}
    for n in tous.values():
        for m in (n.get("tasks") or {}).get("migrations") or []:
            migres.setdefault(m["vmid"], m)
    invites = []
    for n in (nc, na):
        if not n:
            continue
        for g in n.get("guests") or []:
            if g.get("template"):
                continue
            prof = (profils or {}).get((n["name"], g["vmid"])) or {}
            sv = sauvegardes(g["vmid"], n["name"], tous, lan, maintenant, cible)
            s = sante(g)
            p = pra(g, n["name"], tous, sv, params, quorum_perdu, cible)
            repl = [dict(j, noeud=x["name"]) for x in tous.values() for j in x.get("replication") or [] if j.get("vmid") == g["vmid"]]
            invites.append({"noeud": n["name"], "vmid": g["vmid"], "type": g["type"], "name": g["name"], "status": g["status"],
                            "transfere": g["vmid"] in transferes or (n["name"] == accueil and g["vmid"] in migres),
                            "migration": migres.get(g["vmid"]), "decision": prof.get("decision"), "conf": g.get("conf"), "charge": g.get("charge"),
                            "checks": g.get("checks"), "disk": g.get("disk"), "maxdisk": g.get("maxdisk"), "uptime_s": g.get("uptime_s"),
                            "sante": s, "sauvegardes": sv, "pra": p, "replication": repl})
    invites.sort(key=lambda i: (i["noeud"] != cible, not i["transfere"], i["vmid"]))
    controles = verifications(nc, na, invites, cible, accueil, q, list(liens_sonde or []), manuel_sonde)
    perdues = [b for b in (nc or {}).get("backups") or [] if not ((nc.get("storages") or {}).get(b.get("storage")) or {}).get("shared")]
    return {"cible": cible, "accueil": accueil, "noeuds": sorted(tous), "releve": {k: {"at": v.get("_at"), "ok": v.get("ok"), "error": v.get("error")} for k, v in tous.items()},
            "quorum": q, "controles": controles, "invites": invites, "params": dict(DEFAUTS, **{k: v for k, v in (params or {}).items() if v is not None}),
            "seuils": SEUILS, "perdues": {"nb": len(perdues), "octets": sum(b.get("size") or 0 for b in perdues), "liste": perdues[:200]},
            "verdict": _pire(*[c["verdict"] for c in controles])}


def verifications(nc, na, invites, cible, accueil, q, liens=(), manuel=None):
    """Liste des contrôles « prêt à réinstaller » (verdict, détail, actions)."""
    out = []
    if not nc or not na:
        out.append({"id": "releves", "titre": "Relevés des deux nœuds", "verdict": "bloquant",
                    "detail": "relevé pve-preflight manquant pour %s : activer la sonde pve-preflight (agent qui joint les Proxmox, pve-remote.json)"
                              % ", ".join(x for x, n in ((cible, nc), (accueil, na)) if not n), "actions": [], "liens": list(liens), "manuel": manuel})
        if not nc and not na:
            return out
    out.append({"id": "quorum", "titre": "1. Quorum", "verdict": q["verdict"], "detail": q["detail"], "actions": q.get("actions") or []})
    sur_c = [i for i in invites if i["noeud"] == cible]
    restants = [i for i in sur_c if i["decision"] not in ("archiver", "arreter")]
    v = "ok" if not sur_c else "bloquant" if any(i["status"] == "running" and i["decision"] not in ("archiver", "arreter") for i in sur_c) else "attention"
    out.append({"id": "vider", "titre": "Invités encore sur %s" % cible, "verdict": v,
                "detail": "aucun" if not sur_c else "%d invité(s), dont %d sans décision « archiver » ou « arrêter » : %s"
                % (len(sur_c), len(restants), ", ".join("%s %s (%s)" % (i["vmid"], i["name"], i["status"]) for i in sur_c)), "actions": []})
    jobs = [j for n in (nc, na) if n for j in n.get("replication") or [] if j.get("target") == cible or (n is nc)]
    jobs = list({j["job"]: j for j in jobs}.values())
    out.append({"id": "replications", "titre": "Réplications liées à %s" % cible, "verdict": "attention" if jobs else "ok",
                "detail": "aucune" if not jobs else "%d job(s) à supprimer avant la réinstallation (et à recréer après) : %s" % (len(jobs), ", ".join("%s → %s" % (j["job"], j["target"]) for j in jobs)),
                "actions": [{"quand": "avant d'arrêter %s" % cible, "ou": accueil, "cmd": "pvesr delete %s" % j["job"], "pourquoi": "réplication vers %s" % j["target"]} for j in jobs]})
    tr = [i for i in invites if i["transfere"]]
    pire = _pire(*[i["sante"]["verdict"] for i in tr]) if tr else "inconnu"
    out.append({"id": "transferes", "titre": "2. Invités transférés sur %s" % accueil, "verdict": pire if tr else "inconnu",
                "detail": "aucun invité marqué « transféré » (cocher dans le tableau, ou migration pct / qm détectée)" if not tr else
                "; ".join("%s %s : %s" % (i["vmid"], i["name"], ", ".join(i["sante"]["raisons"]) or "sain") for i in tr), "actions": []})
    sv = [i for i in invites if i["noeud"] == accueil and i["status"] == "running"]
    pire = _pire(*[i["sauvegardes"]["verdict"] for i in sv]) if sv else "ok"
    out.append({"id": "sauvegardes", "titre": "3. Sauvegardes des invités actifs de %s" % accueil, "verdict": pire,
                "detail": "; ".join("%s %s : %s" % (i["vmid"], i["name"], ", ".join(i["sauvegardes"]["raisons"])) for i in sv if i["sauvegardes"]["raisons"]) or "toutes à jour hors du nœud",
                "actions": []})
    pr = [i for i in invites if i["status"] == "running"]
    sans = [i for i in pr if i["pra"]["verdict"] == "bloquant"]
    out.append({"id": "pra", "titre": "4. PRA des invités actifs", "verdict": "bloquant" if sans else _pire(*[i["pra"]["verdict"] for i in pr]) if pr else "ok",
                "detail": ("sans reprise possible : %s" % ", ".join("%s %s" % (i["vmid"], i["name"]) for i in sans)) if sans else "chaque invité actif a au moins un scénario de reprise",
                "actions": []})
    return out
