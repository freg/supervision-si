# -*- coding: utf-8 -*-
"""#761 : assistant de rapatriement / nettoyage d'un nœud Proxmox distant (OVH) -- une CAMPAGNE scénarisée en étapes
(inventaire, préparation, rapatriement, vérification, nettoyage, bilan) que la tuile présente façon assistant
d'installation (Suivant / Précédent) avec un synoptique en bandeau et un pourcentage d'avancement.

Chaque CT / VM à rapatrier est confié à un plan PRA « repatriate » (#750 : export + restauration, vérification,
transition, destruction par tranches dans la plage horaire) : la campagne ne fait qu'orchestrer et MESURER. Ce module
est pur (calculs d'avancement, contrôles de préparation) ; la base et les routes sont dans app.py."""
import json
import time

STEPS = [("inventaire", "Inventaire", 10), ("preparation", "Préparation", 10), ("rapatriement", "Rapatriement", 40),
         ("verification", "Vérification", 15), ("nettoyage", "Nettoyage", 20), ("bilan", "Bilan", 5)]
STEP_IDS = [s[0] for s in STEPS]
DECISIONS = ("rapatrier", "garder", "supprimer", "")
SCHEMA = """CREATE TABLE IF NOT EXISTS repatriation (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, remote TEXT NOT NULL,
    pve_agent_id TEXT NOT NULL, storage TEXT DEFAULT '', step TEXT DEFAULT 'inventaire', settings TEXT DEFAULT '{}', guests TEXT DEFAULT '[]',
    created_at TEXT, updated_at TEXT, by_user TEXT DEFAULT '')"""
DEFAULT_SETTINGS = {"bwlimit_mbps": 400, "window": "20:00-07:00", "mode": "stop", "slice_gb": 10, "newid_base": 9000}

# Phases d'un invité, d'après l'exécution de son plan (cp1, export, vérification, cp2, destruction) : (code, libellé, part)
PHASES = {"todo": ("à lancer", 0.0), "export": ("export et restauration", 0.25), "verify": ("vérification", 0.5), "diff": ("écarts à examiner", 0.5),
          "validate": ("à valider", 0.7), "destroy": ("destruction de l'original (plage horaire)", 0.85), "done": ("terminé", 1.0),
          "failed": ("échec", 0.0), "aborted": ("abandonné", 0.0)}


def public(row):
    d = dict(row)
    d["settings"] = dict(DEFAULT_SETTINGS, **json.loads(d.get("settings") or "{}"))
    d["guests"] = json.loads(d.get("guests") or "[]")
    return d


def guest_phase(run):
    """Exécution d'un plan repatriate (pra_runs public) -> (code de phase, détail)."""
    if not run:
        return "todo", None
    st = run.get("steps") or []
    by = {}
    for s in st:
        a = (s.get("params") or {}).get("action") or ""
        by[a if a in ("export", "verify", "destroy") else ("checkpoint%d" % s.get("index", 0))] = s
    err = next((s.get("result", {}).get("error") for s in st if s.get("status") in ("failed", "timeout", "aborted") and (s.get("result") or {}).get("error")), None)
    if run.get("status") == "failed":
        if (by.get("verify") or {}).get("status") == "failed":
            return "diff", err
        return ("aborted" if any(s.get("status") == "aborted" for s in st) else "failed"), err
    if (by.get("destroy") or {}).get("status") == "done" or (run.get("status") == "done" and by.get("destroy")):
        return "done", None
    if (by.get("destroy") or {}).get("status") == "sent":
        return "destroy", None
    if any(s.get("status") == "waiting" for s in st) and (by.get("verify") or {}).get("status") == "done":
        return "validate", None
    if (by.get("verify") or {}).get("status") in ("sent", "done"):
        return "verify", None
    return "export", None


def progress(campaign, phases):
    """Pourcentage global et par étape. phases : {vmid: code} des invités « rapatrier »."""
    steps = {}
    idx = STEP_IDS.index(campaign.get("step") or "inventaire")
    g = [x for x in campaign.get("guests") or [] if x.get("decision") == "rapatrier"]
    frac = [PHASES.get(phases.get(x["vmid"], "todo"), ("", 0))[1] for x in g]
    decided = any(x.get("decision") for x in campaign.get("guests") or [])

    def avg(f):
        return sum(f) / len(f) if f else (1.0 if idx > 2 else 0.0)
    steps["inventaire"] = 1.0 if decided and idx > 0 else (0.5 if decided else 0.0)
    steps["preparation"] = 1.0 if idx > 1 else 0.0
    steps["rapatriement"] = avg([min(1.0, f / 0.5) for f in frac])
    steps["verification"] = avg([1.0 if f >= 0.7 else (0.5 if f >= 0.5 else 0.0) for f in frac])
    steps["nettoyage"] = avg([1.0 if f >= 1.0 else (0.5 if f >= 0.85 else 0.0) for f in frac])
    steps["bilan"] = 1.0 if idx == len(STEPS) - 1 and steps["nettoyage"] >= 1.0 else 0.0
    total = round(sum(w * steps[s] for s, _l, w in STEPS), 1)
    return {"percent": total, "steps": [{"id": s, "label": l, "weight": w, "done": round(steps[s], 2)} for s, l, w in STEPS]}


def merge_inventory(guests, remote_vms):
    """Invités de la campagne + inventaire distant courant (tuile Infra) : nouveaux ajoutés, décisions gardées."""
    known = {g["vmid"]: g for g in guests or []}
    out = []
    for v in sorted(remote_vms or [], key=lambda v: v.get("vmid") or 0):
        vmid = int(v.get("vmid") or 0)
        if vmid < 100:
            continue
        g = dict(known.pop(vmid, {"vmid": vmid, "decision": ""}))
        g.update(name=v.get("name") or g.get("name") or "", kind="lxc" if v.get("type") == "lxc" else "qemu", status=v.get("status"),
                 size=v.get("maxdisk") or g.get("size"), used=v.get("disk") or g.get("used"), present=True)
        out.append(g)
    for g in known.values():                       # disparu de l'inventaire distant (déjà détruit ?)
        out.append(dict(g, present=False))
    return out


def preparation(campaign, target_node, remote_node, guests):
    """Contrôles avant lancement -> [{label, ok, detail}]. target_node / remote_node : nœuds de /infra/overview."""
    sel = [g for g in guests if g.get("decision") == "rapatrier"]
    need = sum(int(g.get("size") or 0) for g in sel)
    free = None
    if target_node:
        st = next((s for s in target_node.get("storages") or [] if s.get("name") == campaign.get("storage") or s.get("storage") == campaign.get("storage")), None)
        if st:
            free = (st.get("total") or st.get("size") or 0) - (st.get("used") or 0) if st.get("avail") is None else st.get("avail")
    out = [{"label": "au moins un CT / VM à rapatrier", "ok": bool(sel), "detail": "%d sélectionné(s)" % len(sel)},
           {"label": "nœud distant joignable par l'agent du nœud local", "ok": bool(remote_node and remote_node.get("ok", True)),
            "detail": (remote_node or {}).get("error") or ("vu par node-activity" if remote_node else "absent de la tuile Infra : déclarer le nœud dans /etc/si-agent/pve-remote.json et activer node-activity")},
           {"label": "nœud local en ligne", "ok": bool(target_node and target_node.get("ok", True)), "detail": (target_node or {}).get("name") or "inconnu"},
           {"label": "stockage local choisi", "ok": bool(campaign.get("storage")), "detail": campaign.get("storage") or "à choisir"},
           {"label": "place libre sur le stockage local", "ok": free is None or free > need * 1.1,
            "detail": "besoin ~%.0f Go (taille des disques), libre %s" % (need / 1e9, "%.0f Go" % (free / 1e9) if free is not None else "inconnu (vérifier)")}]
    ids = [g.get("newid") for g in sel if g.get("newid")]
    out.append({"label": "nouveaux identifiants distincts", "ok": len(ids) == len(set(ids)), "detail": ", ".join(str(i) for i in ids) or "attribués au lancement"})
    return out


def inventory_state(remote, reports, guests):
    """#764 : d'où vient (ou pourquoi manque) l'inventaire du nœud distant. reports : [(task, agent, at, data)] des sondes
    pve-remote et node-activity -> {reports: [...], hint}."""
    out = []
    for task, agent, at, d in reports:
        for x in (d or {}).get("nodes") or []:
            if x.get("name") == remote:
                out.append({"task": task, "agent": agent, "at": at, "ok": x.get("ok", True) is not False and not x.get("error"), "error": x.get("error"),
                            "guests": len(x.get("guests") or []) if task == "plugin:pve-remote" else None, "source": x.get("source"),
                            "warnings": (x.get("warnings") or [])[:3]})
    pr = [r for r in out if r["task"] == "plugin:pve-remote"]
    if any(g.get("present") for g in guests or []):
        hint = None
    elif not pr:
        hint = ("aucune remontée de la sonde pve-remote pour « %s » : sur l'agent qui joint ce nœud (ex. le PVE local), déclarer "
                "[{\"name\": \"%s\", \"host\": \"…\"}] dans /etc/si-agent/pve-remote.json et activer la sonde pve-remote" % (remote, remote))
    elif not any(r["ok"] for r in pr):
        hint = "la sonde pve-remote ne joint pas « %s » : %s" % (remote, "; ".join("%s : %s" % (r["agent"], r["error"]) for r in pr))
    else:
        hint = ("la sonde pve-remote joint « %s » mais ne voit aucun CT / VM (source %s) : mettre à jour l'agent qui porte la sonde "
                "(≥ 0.5.63, nom de nœud court) ou vérifier « pvesh get /cluster/resources --type vm » sur le nœud" % (remote, ", ".join(sorted({r["source"] or "?" for r in pr}))))
    return {"reports": out, "hint": hint}


# --- #765 : restes du rapatriement sur le nœud local (archives, .part, images en boucle) ---------------------------
LEFTOVER_KIND = {"archive": "archive vzdump", "part": "export interrompu (.part)", "image": "image brute"}


def _pbs_last(pbs_groups, vmid):
    """Dernière sauvegarde PBS complète d'un CT / d'une VM (tous datastores / espaces de noms) -> (epoch, réf) ou (None, None)."""
    best = (None, None)
    for g in pbs_groups or []:
        if str(g.get("id")) == str(vmid) and g.get("last_complete") and g.get("last") and (best[0] is None or g["last"] > best[0]):
            best = (g["last"], "%s%s/%s/%s" % (g.get("store") or "?", ("/" + g["ns"]) if g.get("ns") else "", g.get("type"), g.get("id")))
    return best


def leftover_checks(items, local_vms, pbs_groups, copies, newid_base=9000):
    """items : restes listés par l'agent ; local_vms : {vmid: état} du nœud ; pbs_groups : groupes des sondes PBS ;
    copies : {vmid d'origine: {newid, remote, original}} tirés des campagnes. -> éléments avec checks [{label, ok, required}],
    copy, role, ok (suppression possible sans forcer)."""
    out = []
    for it in items or []:
        x = dict(it)
        v, kind, checks = it.get("vmid"), it.get("kind"), []
        if it.get("in_use"):
            checks.append({"label": "pas en cours d'usage", "ok": False, "required": True, "detail": it["in_use"]})
        cp = (copies or {}).get(v) or {}
        copy = cp.get("newid")
        if v is not None and not copy and v in (local_vms or {}) and kind != "image":
            role, target = "sauvegarde locale de %d" % v, v           # archive d'un CT / VM qui vit ici : sauvegarde ordinaire
        else:
            if v is not None and not copy and (newid_base + v) in (local_vms or {}):
                copy = newid_base + v
            role, target = ("reste du rapatriement de %d -> copie %s" % (v, copy or "?")) if v is not None else "reste sans identifiant reconnu", copy
            checks.append({"label": "copie locale %s présente" % (copy or "?"), "ok": bool(copy and copy in (local_vms or {})), "required": True,
                           "detail": "état %s" % (local_vms or {}).get(copy) if copy in (local_vms or {}) else "introuvable sur ce nœud"})
            checks.append({"label": "copie %s démarrée" % (copy or "?"), "ok": (local_vms or {}).get(copy) == "running", "required": True,
                           "detail": (local_vms or {}).get(copy) or "—"})
        if kind == "part":
            checks.append({"label": "export terminé (fichier .part abandonné)", "ok": not it.get("in_use"), "required": True, "detail": ""})
        last, ref = _pbs_last(pbs_groups, target) if target else (None, None)
        after = it.get("mtime") if kind == "archive" else None
        checks.append({"label": "sauvegarde PBS complète de %s%s" % (target or "?", " postérieure à l'archive" if after else ""),
                       "ok": bool(last and (not after or last >= after)), "required": kind != "part",
                       "detail": ("%s, %s" % (ref, time.strftime("%Y-%m-%d %H:%M", time.localtime(last)))) if last else "aucune sur les PBS supervisés"})
        if cp.get("remote"):
            checks.append({"label": "original sur %s" % cp["remote"], "ok": True, "required": False, "detail": cp.get("original") or "?"})
        x.update(role=role, copy=copy, label=LEFTOVER_KIND.get(kind, kind) + (" montée (%s)" % it["loop"]["dev"] if it.get("loop") else ""),
                 checks=checks, ok=all(c["ok"] for c in checks if c["required"]))
        out.append(x)
    return out
