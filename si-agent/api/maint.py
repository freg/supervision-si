# -*- coding: utf-8 -*-
"""#705 : maintenance / réorganisation des Proxmox -- campagnes d'étapes et d'actions, avancement DÉTECTÉ sur les mesures
des agents des hyperviseurs (plugin proxmox), planification, vue des sauvegardes (PBS).

Une campagne = des étapes ; une étape = des actions. Une action est :
- « manual » : à faire à la main (consigne), cochée par l'opérateur ;
- « pra » : une opération PVE (#653 : backup, destroy, migrate, shutdown…) exécutée par l'agent du nœud via un plan PRA
  d'une étape, à la demande ou à l'heure prévue (`at`, `auto`) quand la campagne est active.
Chaque action peut porter un DÉTECTEUR (CT absent, sauvegarde récente, espace libre, stockage PBS déclaré, tâche de
sauvegarde planifiée, état d'un CT, version d'agent) évalué sur la dernière mesure des agents : l'avancement est constaté,
pas seulement coché. Un constat acquis reste acquis quand la donnée disparaît (ex. la sauvegarde d'un CT ensuite supprimé).

Partie pure (snapshot, check, evaluate, templates, due_actions, pbs_overview) testée sans base ; routes `/maint/*`."""
import json
import threading
import time
import uuid

import pra
import store

STALE_S = 3 * 3600          # mesure plus ancienne : constat « inconnu »
GIB = 1024 ** 3
DETECTORS = {
    "guest_absent": {"label": "CT/VM supprimé", "fields": ["vmid", "node?"]},
    "guest_present": {"label": "CT/VM présent sur un nœud", "fields": ["vmid", "node"]},
    "guest_status": {"label": "CT/VM dans un état", "fields": ["vmid", "status", "node?"]},
    "backup_recent": {"label": "Sauvegarde récente", "fields": ["vmid", "max_age_h", "storage?"]},
    "storage_free": {"label": "Espace libre suffisant", "fields": ["node", "storage", "min_free_gb"]},
    "storage_present": {"label": "Stockage déclaré et actif", "fields": ["node", "storage", "type?"]},
    "backup_job": {"label": "Tâche de sauvegarde planifiée", "fields": ["storage", "vmid?"]},
    "agent_version": {"label": "Version de l'agent", "fields": ["agent_id", "min_version"]},
}
STATUSES = ("draft", "active", "done", "archived")


# ------------------------------------------------------------------ pur : instantané des mesures

def snapshot(px, now=None, agents=None):
    """latest_proxmox -> {nodes: {nom: {agent_id, at, stale, storages, vms}}, jobs: [...], agents: {id: version}}."""
    now = now or time.time()
    nodes, jobs, seen = {}, [], set()
    for p in px or []:
        name = (p.get("node") or {}).get("name") or p.get("hostname") or p.get("agent_id")
        at = _epoch(p.get("at"))
        nodes[name] = {"agent_id": p.get("agent_id"), "at": at, "stale": (not p.get("ok", True)) or at is None or now - at > STALE_S,
                       "storages": {s.get("storage"): s for s in p.get("storages") or [] if s.get("storage")},
                       "vms": {int(v["vmid"]): v for v in p.get("vms") or [] if str(v.get("vmid", "")).isdigit()}}
        for j in ((p.get("backups") or {}).get("jobs") or []):
            key = (j.get("id"), j.get("storage"), j.get("schedule"))
            if key not in seen:
                seen.add(key); jobs.append(dict(j, node=name))
    return {"nodes": nodes, "jobs": jobs, "agents": dict(agents or {}), "now": now}


def _epoch(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _ver(v):
    out = []
    for x in str(v or "").split("."):
        out.append(int(x) if x.isdigit() else 0)
    return tuple(out)


def _gb(n):
    return "%.1f Go" % ((n or 0) / GIB)


def _res(state, detail):
    return {"state": state, "detail": detail}


def check(det, snap):
    """Détecteur -> {state: done|pending|unknown, detail}."""
    t = (det or {}).get("type")
    p = (det or {}).get("params") or {}
    nodes = snap["nodes"]
    now = snap.get("now") or time.time()
    try:
        vmid = int(p["vmid"]) if p.get("vmid") not in (None, "") else None
    except (TypeError, ValueError):
        return _res("unknown", "vmid invalide")

    def node_of(name):
        n = nodes.get(name)
        if n is None:
            return None, _res("unknown", "nœud %s : aucune mesure (agent absent ou plugin proxmox inactif)" % name)
        if n["stale"]:
            return None, _res("unknown", "nœud %s : mesure trop ancienne" % name)
        return n, None

    def find(vm_id):
        """-> (liste des (nœud, vm) trouvés sur des mesures fraîches, présence de nœuds périmés)."""
        hits = [(name, n["vms"][vm_id]) for name, n in nodes.items() if not n["stale"] and vm_id in n["vms"]]
        return hits, any(n["stale"] for n in nodes.values())

    if t in ("guest_absent", "guest_present", "guest_status"):
        if vmid is None:
            return _res("unknown", "vmid requis")
        if p.get("node"):
            n, err = node_of(p["node"])
            if err:
                return err
            vm = n["vms"].get(vmid)
            if t == "guest_absent":
                return _res("pending", "%s présent sur %s (%s)" % (vmid, p["node"], vm.get("status"))) if vm else _res("done", "%s absent de %s" % (vmid, p["node"]))
            if not vm:
                return _res("pending", "%s absent de %s" % (vmid, p["node"]))
            if t == "guest_present":
                return _res("done", "%s présent sur %s (%s)" % (vmid, p["node"], vm.get("status")))
            ok = vm.get("status") == p.get("status")
            return _res("done" if ok else "pending", "%s %s sur %s" % (vmid, vm.get("status"), p["node"]))
        hits, stale = find(vmid)
        if t == "guest_absent":
            if hits:
                return _res("pending", "%s présent sur %s" % (vmid, ", ".join(h[0] for h in hits)))
            return _res("unknown", "%s absent des nœuds à jour, mais un nœud n'a pas de mesure récente" % vmid) if stale else _res("done", "%s absent de tous les nœuds" % vmid)
        if not hits:
            return _res("unknown" if stale else "pending", "%s introuvable" % vmid)
        if t == "guest_present":
            return _res("done", "%s présent sur %s" % (vmid, hits[0][0]))
        ok = any(h[1].get("status") == p.get("status") for h in hits)
        return _res("done" if ok else "pending", "%s %s" % (vmid, ", ".join("%s sur %s" % (h[1].get("status"), h[0]) for h in hits)))

    if t == "backup_recent":
        if vmid is None:
            return _res("unknown", "vmid requis")
        hits, stale = find(vmid)
        if not hits:
            return _res("unknown", "%s introuvable sur les nœuds à jour" % vmid)
        max_age = float(p.get("max_age_h") or 24) * 3600
        best = None
        for _name, vm in hits:
            b = vm.get("last_backup") or {}
            if b.get("at") and (not p.get("storage") or str(b.get("volid") or "").startswith(str(p["storage"]) + ":")):
                if best is None or b["at"] > best["at"]:
                    best = b
        if not best:
            return _res("pending", "aucune sauvegarde de %s%s" % (vmid, " sur %s" % p["storage"] if p.get("storage") else ""))
        age = now - float(best["at"])
        txt = "dernière sauvegarde de %s il y a %.0f h (%s)" % (vmid, age / 3600, best.get("volid") or "?")
        return _res("done" if age <= max_age else "pending", txt)

    if t in ("storage_free", "storage_present"):
        n, err = node_of(p.get("node"))
        if err:
            return err
        st = n["storages"].get(p.get("storage"))
        if t == "storage_present":
            if not st:
                return _res("pending", "stockage %s non déclaré ou inactif sur %s" % (p.get("storage"), p.get("node")))
            if p.get("type") and st.get("type") != p["type"]:
                return _res("pending", "stockage %s de type %s (attendu %s)" % (p["storage"], st.get("type"), p["type"]))
            return _res("done", "stockage %s (%s) actif sur %s, %s libres" % (p["storage"], st.get("type"), p["node"], _gb(st.get("avail"))))
        if not st:
            return _res("unknown", "stockage %s absent des mesures de %s" % (p.get("storage"), p.get("node")))
        need = float(p.get("min_free_gb") or 0) * GIB
        avail = st.get("avail") or 0
        return _res("done" if avail >= need else "pending", "%s libres sur %s / %s (objectif %s Go)" % (_gb(avail), p["storage"], _gb(st.get("total")), p.get("min_free_gb")))

    if t == "backup_job":
        fresh = [n for n in nodes.values() if not n["stale"]]
        if not fresh:
            return _res("unknown", "aucun nœud à jour")
        for j in snap["jobs"]:
            if j.get("enabled") and j.get("storage") == p.get("storage") and (vmid is None or j.get("all") or vmid in (j.get("vmids") or [])):
                return _res("done", "tâche %s vers %s (%s)" % (j.get("id"), j.get("storage"), j.get("schedule") or "?"))
        return _res("pending", "aucune tâche active vers %s%s" % (p.get("storage"), " pour %s" % vmid if vmid else ""))

    if t == "agent_version":
        v = snap["agents"].get(p.get("agent_id"))
        if v is None:
            return _res("unknown", "agent %s inconnu" % p.get("agent_id"))
        return _res("done" if _ver(v) >= _ver(p.get("min_version")) else "pending", "agent %s en %s (attendu %s)" % (p.get("agent_id"), v, p.get("min_version")))
    return _res("unknown", "détecteur inconnu : %s" % t)


# ------------------------------------------------------------------ pur : évaluation d'une campagne

def evaluate(camp, snap, runs=None, now=None):
    """Campagne -> (campagne évaluée, changé ?) : état de chaque action / étape, avancement global.
    `runs` : {run_id: statut} des plans PRA lancés par les actions."""
    now = now or time.time()
    runs = runs or {}
    changed = False
    total = done = 0
    prev_done = True
    next_at = None
    for st in camp.get("stages") or []:
        s_total = s_done = 0
        busy = False
        for a in st.get("actions") or []:
            run = a.get("run") or {}
            rstat = runs.get(run.get("run_id")) if run.get("run_id") else None
            if rstat:
                run["status"] = rstat
            det = check(a["detector"], snap) if a.get("detector") else None
            state, detail, how = "todo", "", None
            if det and det["state"] == "done":
                state, detail, how = "done", det["detail"], "detected"
            elif det and det["state"] == "unknown" and a.get("detected_at"):
                state, detail, how = "done", "constaté le %s ; %s" % (time.strftime("%d/%m %H:%M", time.localtime(a["detected_at"])), det["detail"]), "detected"
            elif a.get("manual_done"):
                state, detail, how = "done", (det["detail"] + " -- " if det else "") + "coché par %s" % (a.get("manual_by") or "?"), "manual"
            elif run.get("status") == "running":
                state, detail = "running", "exécution n°%s en cours" % run.get("run_id")
            elif run.get("status") == "failed":
                state, detail = "failed", "exécution n°%s en échec" % run.get("run_id") + (" ; " + det["detail"] if det else "")
            elif not det and run.get("status") == "done":
                state, detail, how = "done", "exécution n°%s réussie" % run.get("run_id"), "run"
            elif det:
                state, detail = ("unknown" if det["state"] == "unknown" else "todo"), det["detail"]
            if how == "detected" and det and det["state"] == "done" and not a.get("detected_at"):
                a["detected_at"] = int(now); changed = True
            a["state"], a["detail"], a["done_how"] = state, detail, how
            s_total += 1
            s_done += state == "done"
            busy = busy or state in ("running", "failed") or (state == "done")
            if state != "done" and a.get("at") and (next_at is None or a["at"] < next_at):
                next_at = a["at"]
        st["progress"] = {"done": s_done, "total": s_total}
        st["state"] = "done" if s_total and s_done == s_total else ("blocked" if st.get("require_previous") and not prev_done else ("doing" if busy else "todo"))
        st["previous_done"] = prev_done
        prev_done = prev_done and st["state"] == "done"
        total += s_total
        done += s_done
    camp["progress"] = {"done": done, "total": total, "pct": round(100.0 * done / total) if total else 0}
    camp["next_at"] = next_at
    return camp, changed


def due_actions(camp, now):
    """Actions « pra » planifiées en automatique, échues, ni faites ni lancées, étape débloquée."""
    if camp.get("status") != "active":
        return []
    out = []
    for st in camp.get("stages") or []:
        if st.get("state") == "blocked":
            continue
        for a in st.get("actions") or []:
            if a.get("kind") == "pra" and a.get("auto") and a.get("at") and a["at"] <= now and not (a.get("run") or {}).get("run_id") and a.get("state") != "done":
                out.append(a)
    return out


LATE_S = 15 * 60          # action datée non faite après ce délai : « en retard »


def transitions(camp, now):
    """Changements à signaler depuis le dernier passage (pur, marque ce qui est signalé) -> [(genre, sévérité, message)].
    À appeler sur une campagne évaluée : échec d'une opération, action en retard, étape terminée, campagne terminée."""
    out = []
    name = camp.get("name")
    for st in camp.get("stages") or []:
        for a in st.get("actions") or []:
            n = a.setdefault("notified", {})
            rid = (a.get("run") or {}).get("run_id")
            if a.get("state") == "failed" and rid and n.get("failed") != rid:
                n["failed"] = rid
                out.append(("maint.echec", "warning", "Maintenance « %s » : échec de « %s » (exécution n°%s)" % (name, a["title"], rid)))
            late = a.get("at") and a.get("state") not in ("done", "running", "failed") and now - a["at"] > LATE_S and camp.get("status") == "active"
            if late and not n.get("late"):
                n["late"] = int(now)
                out.append(("maint.retard", "warning", "Maintenance « %s » : « %s » prévue le %s n'est pas faite" % (
                    name, a["title"], time.strftime("%d/%m %H:%M", time.localtime(a["at"])))))
            elif not late and a.get("state") == "done":
                n.pop("late", None)
        if st.get("state") == "done" and not st.get("notified_done"):
            st["notified_done"] = int(now)
            out.append(("maint.etape", "info", "Maintenance « %s » : étape « %s » terminée" % (name, st["title"])))
        elif st.get("state") != "done" and st.get("notified_done"):
            st.pop("notified_done", None)                  # régression (constat redevenu faux) : resignalée à la prochaine fin
    total = (camp.get("progress") or {}).get("total")
    done_before = any(h.get("event") == "completed" for h in camp.get("history") or [])
    if total and camp["progress"]["done"] == total and not done_before:
        out.append(("maint.campagne", "info", "Maintenance « %s » terminée (%d actions)" % (name, total)))
    return out


# ------------------------------------------------------------------ pur : validation

def validate(body):
    """-> (campagne normalisée, erreur)."""
    name = str(body.get("name") or "").strip()
    if not name:
        return None, "nom de la campagne requis"
    status = body.get("status") or "draft"
    if status not in STATUSES:
        return None, "statut : %s" % ", ".join(STATUSES)
    stages = []
    for i, st in enumerate(body.get("stages") or [], 1):
        title = str(st.get("title") or "").strip()
        if not title:
            return None, "étape %d : titre requis" % i
        acts = []
        for j, a in enumerate(st.get("actions") or [], 1):
            where = "étape %d, action %d" % (i, j)
            kind = a.get("kind") or "manual"
            if kind not in ("manual", "pra"):
                return None, "%s : type manual ou pra" % where
            act = {"id": str(a.get("id") or uuid.uuid4().hex[:10]), "title": str(a.get("title") or "").strip(), "kind": kind,
                   "notes": str(a.get("notes") or ""), "manual_done": bool(a.get("manual_done")), "manual_by": a.get("manual_by"),
                   "manual_at": a.get("manual_at"), "detected_at": a.get("detected_at"), "run": a.get("run") or None,
                   "notified": a.get("notified") or {}}
            if kind == "pra":
                steps, err = pra.validate_steps([a.get("step") or {}])
                if err:
                    return None, "%s : %s" % (where, err)
                act["step"] = steps[0]
            if not act["title"]:
                act["title"] = ("%s %s" % (act["step"]["action"], act["step"].get("vmid") or "")).strip() if kind == "pra" else ""
            if not act["title"]:
                return None, "%s : intitulé requis" % where
            if a.get("detector"):
                d = a["detector"]
                if d.get("type") not in DETECTORS:
                    return None, "%s : détecteur inconnu" % where
                missing = [f for f in DETECTORS[d["type"]]["fields"] if not f.endswith("?") and (d.get("params") or {}).get(f) in (None, "")]
                if missing:
                    return None, "%s : détecteur %s, champ(s) requis : %s" % (where, d["type"], ", ".join(missing))
                act["detector"] = {"type": d["type"], "params": {k: v for k, v in (d.get("params") or {}).items() if v not in (None, "")}}
            if a.get("at") not in (None, ""):
                try:
                    act["at"] = int(float(a["at"]))
                except (TypeError, ValueError):
                    return None, "%s : date planifiée invalide" % where
                act["auto"] = bool(a.get("auto")) and kind == "pra"
            acts.append(act)
        stages.append({"id": str(st.get("id") or uuid.uuid4().hex[:10]), "title": title, "notes": str(st.get("notes") or ""),
                       "require_previous": bool(st.get("require_previous")), "actions": acts, "notified_done": st.get("notified_done")})
    return {"name": name, "notes": str(body.get("notes") or ""), "status": status, "stages": stages}, None


# ------------------------------------------------------------------ pur : modèles

def _kind_of(snap, vmid):
    for n in snap["nodes"].values():
        if vmid in n["vms"]:
            return n["vms"][vmid].get("type") or "lxc"
    return "lxc"


def template(kind, p, snap):
    """Modèles de campagne -> {name, notes, stages} (non enregistré)."""
    vmids = [int(x) for x in p.get("vmids") or [] if str(x).isdigit()]
    if kind == "free_node":
        node, agent, storage = p.get("node"), p.get("agent_id"), p.get("backup_storage")
        if not (node and agent and storage and vmids):
            raise ValueError("nœud, agent, stockage de sauvegarde et au moins un CT/VM requis")
        st1 = [{"title": "Sauvegarder %s" % v, "kind": "pra",
                "step": {"agent_id": agent, "vmid": v, "kind": _kind_of(snap, v), "action": "backup", "params": {"storage": storage, "mode": "stop"}},
                "detector": {"type": "backup_recent", "params": {"vmid": v, "max_age_h": 24 * 7, "storage": storage}}} for v in vmids]
        st3 = [{"title": "Supprimer %s" % v, "kind": "pra",
                "step": {"agent_id": agent, "vmid": v, "kind": _kind_of(snap, v), "action": "destroy", "params": {"confirm": v}},
                "detector": {"type": "guest_absent", "params": {"vmid": v, "node": node}}} for v in vmids]
        stages = [{"title": "Sauvegarder", "actions": st1},
                  {"title": "Contrôler les sauvegardes", "require_previous": True, "actions": [
                      {"title": "Restauration de test d'au moins une sauvegarde (sur un autre nœud ou sous un autre vmid)", "kind": "manual"},
                      {"title": "Copie hors site des sauvegardes (PBS du LAN ou disque)", "kind": "manual"}]},
                  {"title": "Supprimer", "require_previous": True, "actions": st3}]
        if p.get("free_storage"):
            stages.append({"title": "Constater l'espace libéré", "actions": [
                {"title": "%s Go libres sur %s" % (p.get("min_free_gb") or 0, p["free_storage"]), "kind": "manual",
                 "detector": {"type": "storage_free", "params": {"node": node, "storage": p["free_storage"], "min_free_gb": p.get("min_free_gb") or 0}}}]})
        return {"name": "Libérer %s" % node, "notes": "Sauvegarde, contrôle puis suppression de CT/VM arrêtés.", "stages": stages}
    if kind == "pbs_setup":
        storage = p.get("pbs_storage") or "pbs"
        nodes = [n for n in p.get("nodes") or [] if n]
        if not nodes:
            raise ValueError("au moins un nœud")
        stages = [
            {"title": "Réseau", "actions": [
                {"title": "Tunnel WireGuard entre les nœuds et le LAN du PBS opérationnel", "kind": "manual"},
                {"title": "Port 8007 du PBS joignable depuis chaque nœud par le tunnel, et seulement par lui", "kind": "manual"}]},
            {"title": "Serveur de sauvegarde", "actions": [
                {"title": "PBS à jour, datastore créé sur un disque dédié", "kind": "manual"},
                {"title": "Rétention (prune), ramasse-miettes et vérification planifiés sur le datastore", "kind": "manual"},
                {"title": "Utilisateur et jeton API dédiés (droit DatastoreBackup), chiffrement côté client activé, clé sauvegardée hors du PBS", "kind": "manual"}]},
            {"title": "Déclaration sur les nœuds", "actions": [
                {"title": "Stockage %s déclaré sur %s" % (storage, n), "kind": "manual",
                 "detector": {"type": "storage_present", "params": {"node": n, "storage": storage, "type": "pbs"}}} for n in nodes]},
            {"title": "Tâches de sauvegarde", "actions": [
                {"title": "Tâche planifiée vers %s" % storage, "kind": "manual", "detector": {"type": "backup_job", "params": {"storage": storage}}}]},
        ]
        if vmids:
            stages.append({"title": "Premières sauvegardes", "actions": [
                {"title": "Sauvegarde de %s sur %s" % (v, storage), "kind": "manual",
                 "detector": {"type": "backup_recent", "params": {"vmid": v, "max_age_h": 48, "storage": storage}}} for v in vmids]})
        return {"name": "Mise en service du PBS", "notes": "Sauvegardes des Proxmox vers le PBS du LAN.", "stages": stages}
    if kind == "move_guest":
        v = vmids[0] if vmids else None
        src, dst, agent = p.get("source_node"), p.get("target_node"), p.get("source_agent")
        if not (v and src and dst and agent):
            raise ValueError("CT/VM, nœud source (et son agent) et nœud cible requis")
        return {"name": "Déplacer %s de %s vers %s" % (v, src, dst), "notes": "Copie en deux passes (à chaud puis à l'arrêt), bascule, nettoyage.", "stages": [
            {"title": "Préparer", "actions": [
                {"title": "Espace suffisant sur %s" % dst, "kind": "manual"},
                {"title": "Sauvegarde récente de %s" % v, "kind": "manual", "detector": {"type": "backup_recent", "params": {"vmid": v, "max_age_h": 48}}}]},
            {"title": "Passe 1 (à chaud)", "actions": [{"title": "Copie à chaud des données (rsync) vers %s" % dst, "kind": "manual"}]},
            {"title": "Passe 2 (à l'arrêt)", "require_previous": True, "actions": [
                {"title": "Arrêter %s sur %s" % (v, src), "kind": "pra", "step": {"agent_id": agent, "vmid": v, "kind": _kind_of(snap, v), "action": "shutdown"},
                 "detector": {"type": "guest_status", "params": {"vmid": v, "node": src, "status": "stopped"}}},
                {"title": "Copie finale des différences", "kind": "manual"}]},
            {"title": "Bascule", "require_previous": True, "actions": [
                {"title": "%s présent et démarré sur %s" % (v, dst), "kind": "manual", "detector": {"type": "guest_status", "params": {"vmid": v, "node": dst, "status": "running"}}},
                {"title": "Service vérifié (DNS, accès, supervision)", "kind": "manual"}]},
            {"title": "Nettoyage (après observation)", "require_previous": True, "actions": [
                {"title": "Supprimer %s de %s" % (v, src), "kind": "pra", "step": {"agent_id": agent, "vmid": v, "kind": _kind_of(snap, v), "action": "destroy", "params": {"confirm": v}},
                 "detector": {"type": "guest_absent", "params": {"vmid": v, "node": src}}}]},
        ]}
    raise ValueError("modèle inconnu : %s" % kind)


TEMPLATES = {"free_node": "Libérer un nœud (sauvegarder puis supprimer des CT/VM)", "pbs_setup": "Mettre en service un PBS",
             "move_guest": "Déplacer un CT/VM (deux passes)"}


# ------------------------------------------------------------------ pur : vue des sauvegardes

def pbs_overview(snap, old_h=48):
    now = snap.get("now") or time.time()
    stores, guests = [], []
    for name, n in sorted(snap["nodes"].items()):
        for s in n["storages"].values():
            if s.get("type") == "pbs" or "backup" in (s.get("content") or ""):
                stores.append({"node": name, "storage": s.get("storage"), "type": s.get("type"), "used": s.get("used"), "total": s.get("total"), "avail": s.get("avail")})
        for vmid, vm in sorted(n["vms"].items()):
            if vm.get("template"):
                continue
            b = vm.get("last_backup") or {}
            run = vm.get("last_backup_run") or {}
            age = (now - float(b["at"])) / 3600 if b.get("at") else None
            flags = []
            if not vm.get("backup_jobs"):
                flags.append("hors tâche planifiée")
            if age is None:
                flags.append("jamais sauvegardé")
            elif age > old_h:
                flags.append("sauvegarde de plus de %d h" % old_h)
            if run.get("ok") is False:
                flags.append("dernière sauvegarde en échec")
            guests.append({"node": name, "vmid": vmid, "name": vm.get("name"), "type": vm.get("type"), "status": vm.get("status"),
                           "last_backup_at": b.get("at"), "age_h": round(age, 1) if age is not None else None, "volid": b.get("volid"),
                           "storage": str(b.get("volid") or "").split(":")[0] or None, "jobs": vm.get("backup_jobs") or [],
                           "last_run_ok": run.get("ok"), "flags": flags, "stale": n["stale"]})
    pbs = [s for s in stores if s["type"] == "pbs"]
    return {"stores": stores, "jobs": snap["jobs"], "guests": guests, "has_pbs": bool(pbs),
            "summary": {"guests": len(guests), "uncovered": sum(1 for g in guests if "hors tâche planifiée" in g["flags"]),
                        "never": sum(1 for g in guests if "jamais sauvegardé" in g["flags"]),
                        "old": sum(1 for g in guests if any(f.startswith("sauvegarde de plus") for f in g["flags"])),
                        "failed": sum(1 for g in guests if "dernière sauvegarde en échec" in g["flags"]),
                        "on_pbs": sum(1 for g in guests if g["storage"] in {s["storage"] for s in pbs})}}


# ------------------------------------------------------------------ persistance + routes

SCHEMA = """CREATE TABLE IF NOT EXISTS maint_campaigns (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
    notes TEXT DEFAULT '', stages TEXT NOT NULL DEFAULT '[]', history TEXT NOT NULL DEFAULT '[]', created_at TEXT, updated_at TEXT, by_user TEXT DEFAULT '')"""
_lock = threading.Lock()
_db = {"path": None, "latest": None, "emit": None}


def init(db_path, latest_proxmox, emit=None):
    _db["path"], _db["latest"], _db["emit"] = db_path, latest_proxmox, emit
    conn = store._connect(db_path)
    try:
        conn.execute(SCHEMA); conn.commit()
    finally:
        conn.close()


def current_snapshot(now=None):
    conn = store._connect(_db["path"])
    try:
        agents = {r["agent_id"]: r["agent_version"] for r in conn.execute("SELECT agent_id, agent_version FROM agents")}
    finally:
        conn.close()
    return snapshot(_db["latest"](), now, agents)


def _row(conn, cid):
    r = conn.execute("SELECT * FROM maint_campaigns WHERE id = ?", (cid,)).fetchone()
    if not r:
        return None
    d = dict(r); d["stages"] = json.loads(d["stages"] or "[]"); d["history"] = json.loads(d["history"] or "[]")
    return d


def _save(conn, camp, event=None):
    if event:
        camp["history"] = (camp.get("history") or []) + [dict(event, at=int(time.time()))]
        camp["history"] = camp["history"][-200:]
    conn.execute("UPDATE maint_campaigns SET name = ?, status = ?, notes = ?, stages = ?, history = ?, updated_at = ? WHERE id = ?",
                 (camp["name"], camp["status"], camp.get("notes") or "", json.dumps(camp["stages"], ensure_ascii=False),
                  json.dumps(camp.get("history") or [], ensure_ascii=False), store.now_iso(), camp["id"]))


def _runs(conn, camp):
    ids = [a["run"]["run_id"] for st in camp["stages"] for a in st["actions"] if (a.get("run") or {}).get("run_id")]
    if not ids:
        return {}
    q = "SELECT id, status FROM pra_runs WHERE id IN (%s)" % ",".join("?" * len(ids))
    return {r["id"]: r["status"] for r in conn.execute(q, ids)}


def _evaluated(conn, camp, snap):
    camp, changed = evaluate(camp, snap, _runs(conn, camp))
    if changed:
        _save(conn, camp)
        conn.commit()
    return camp


def _find_action(camp, aid):
    for st in camp["stages"]:
        for a in st["actions"]:
            if a["id"] == aid:
                return st, a
    return None, None


def launch(conn, camp, a, mode, actor):
    """Action « pra » -> plan PRA d'une étape (kind maintenance) puis exécution ; renvoie le n° d'exécution."""
    step = dict(a["step"], label=a["title"])
    cur = conn.execute("INSERT INTO pra_plans (name, kind, notes, steps, continue_on_error, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                       ("[maintenance %s] %s" % (camp["id"], a["title"])[:200], "maintenance", "campagne %s" % camp["name"],
                        json.dumps([step], ensure_ascii=False), 0, store.now_iso(), store.now_iso()))
    plan = pra.plan_public(conn.execute("SELECT * FROM pra_plans WHERE id = ?", (cur.lastrowid,)).fetchone())
    conn.commit()
    rid = pra.start_run(_db["path"], plan, mode, actor)
    if mode == "execute":
        a["run"] = {"run_id": rid, "plan_id": plan["id"], "at": int(time.time()), "by": actor, "status": "running"}
    return rid


def tick(now=None, snap=None):
    """Passage du planificateur : constats + lancement des actions automatiques échues. -> n° d'exécutions lancées."""
    now = now or time.time()
    launched = []
    with _lock:
        snap = snap or current_snapshot(now)
        conn = store._connect(_db["path"])
        try:
            for r in conn.execute("SELECT id FROM maint_campaigns WHERE status = 'active'").fetchall():
                camp = _evaluated(conn, _row(conn, r["id"]), snap)
                events = transitions(camp, now)
                if events:
                    for kind, sev, text in events:
                        if _db["emit"]:
                            try:
                                _db["emit"](kind, sev, text, {"campaign_id": camp["id"], "campaign": camp["name"]})
                            except Exception:  # noqa: BLE001 -- un événement manqué ne bloque pas la maintenance
                                pass
                    _save(conn, camp, {"event": "completed"} if any(k == "maint.campagne" for k, _s, _t in events) else None)
                    conn.commit()
                for a in due_actions(camp, now):
                    rid = launch(conn, camp, a, "execute", "planificateur")
                    launched.append(rid)
                    _save(conn, camp, {"event": "auto-run", "action": a["title"], "run_id": rid})
                    conn.commit()
        finally:
            conn.close()
    return launched


def _loop(period=60):
    import fcntl, os, tempfile
    try:
        fh = open(os.path.join(tempfile.gettempdir(), "si-agent-maint.lock"), "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    time.sleep(20)
    while True:
        try:
            tick()
        except Exception:  # noqa: BLE001 -- la boucle ne meurt jamais
            pass
        time.sleep(period)


def register(app, db_path, latest_proxmox, start_loop=True, emit=None):
    """emit(kind, severity, message, details) : journal d'événements du central (+ notification selon le seuil)."""
    from flask import jsonify, request
    init(db_path, latest_proxmox, emit)

    def conn_():
        return store._connect(db_path)

    @app.route("/maint/catalog", methods=["GET"])
    def maint_catalog():
        snap = current_snapshot()
        nodes = [{"node": name, "agent_id": n["agent_id"], "at": n["at"], "stale": n["stale"],
                  "storages": [{"storage": s.get("storage"), "type": s.get("type"), "avail": s.get("avail"), "total": s.get("total")} for s in n["storages"].values()],
                  "vms": [{"vmid": v, "name": vm.get("name"), "type": vm.get("type"), "status": vm.get("status"), "maxdisk": vm.get("maxdisk")} for v, vm in sorted(n["vms"].items())]}
                 for name, n in sorted(snap["nodes"].items())]
        return jsonify({"detectors": DETECTORS, "templates": TEMPLATES, "actions": list(pra.ACTIONS), "required": pra.REQUIRED,
                        "nodes": nodes, "statuses": list(STATUSES)}), 200

    @app.route("/maint/campaigns", methods=["GET"])
    def maint_list():
        snap = current_snapshot()
        c = conn_()
        try:
            out = []
            for r in c.execute("SELECT id FROM maint_campaigns ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'draft' THEN 1 WHEN 'done' THEN 2 ELSE 3 END, updated_at DESC").fetchall():
                camp = _evaluated(c, _row(c, r["id"]), snap)
                planned = [dict(at=a["at"], auto=a.get("auto"), title=a["title"], state=a["state"], stage=st["title"], campaign_id=camp["id"], campaign=camp["name"], action_id=a["id"])
                           for st in camp["stages"] for a in st["actions"] if a.get("at")]
                out.append({"id": camp["id"], "name": camp["name"], "status": camp["status"], "progress": camp["progress"], "next_at": camp["next_at"],
                            "stages": [{"title": s["title"], "state": s["state"], "progress": s["progress"]} for s in camp["stages"]],
                            "planned": planned, "updated_at": camp["updated_at"]})
        finally:
            c.close()
        return jsonify({"campaigns": out}), 200

    @app.route("/maint/campaigns", methods=["POST"])
    def maint_create():
        body = request.get_json(silent=True) or {}
        camp, err = validate(body)
        if err:
            return jsonify({"error": err}), 400
        c = conn_()
        try:
            cur = c.execute("INSERT INTO maint_campaigns (name, status, notes, stages, created_at, updated_at, by_user) VALUES (?,?,?,?,?,?,?)",
                            (camp["name"], camp["status"], camp["notes"], json.dumps(camp["stages"], ensure_ascii=False), store.now_iso(), store.now_iso(), str(body.get("actor") or "")))
            c.commit()
            camp = _row(c, cur.lastrowid)
            _save(c, camp, {"event": "created", "by": body.get("actor")}); c.commit()
            camp = _evaluated(c, _row(c, camp["id"]), current_snapshot())
        finally:
            c.close()
        return jsonify({"campaign": camp}), 201

    @app.route("/maint/campaigns/<int:cid>", methods=["GET"])
    def maint_get(cid):
        c = conn_()
        try:
            camp = _row(c, cid)
            if not camp:
                return jsonify({"error": "campagne inconnue"}), 404
            camp = _evaluated(c, camp, current_snapshot())
        finally:
            c.close()
        return jsonify({"campaign": camp}), 200

    @app.route("/maint/campaigns/<int:cid>", methods=["PUT"])
    def maint_update(cid):
        body = request.get_json(silent=True) or {}
        c = conn_()
        try:
            old = _row(c, cid)
            if not old:
                return jsonify({"error": "campagne inconnue"}), 404
            merged = dict(old, **{k: body[k] for k in ("name", "status", "notes", "stages") if k in body})
            camp, err = validate(merged)
            if err:
                return jsonify({"error": err}), 400
            # l'état acquis (constats, exécutions, coches) suit l'action par son id
            prev = {a["id"]: a for st in old["stages"] for a in st["actions"]}
            for st in camp["stages"]:
                for a in st["actions"]:
                    p = prev.get(a["id"])
                    if p:
                        for k in ("detected_at", "run", "notified"):
                            a[k] = a.get(k) or p.get(k)
            prev_st = {st_["id"]: st_ for st_ in old["stages"]}
            for st_ in camp["stages"]:
                if prev_st.get(st_["id"], {}).get("notified_done"):
                    st_["notified_done"] = prev_st[st_["id"]]["notified_done"]
            camp.update(id=cid, history=old["history"])
            _save(c, camp, {"event": "updated", "by": body.get("actor"), "status": camp["status"] if camp["status"] != old["status"] else None}); c.commit()
            camp = _evaluated(c, _row(c, cid), current_snapshot())
        finally:
            c.close()
        return jsonify({"campaign": camp}), 200

    @app.route("/maint/campaigns/<int:cid>", methods=["DELETE"])
    def maint_delete(cid):
        c = conn_()
        try:
            n = c.execute("DELETE FROM maint_campaigns WHERE id = ?", (cid,)).rowcount; c.commit()
        finally:
            c.close()
        return (jsonify({"ok": True}), 200) if n else (jsonify({"error": "campagne inconnue"}), 404)

    @app.route("/maint/campaigns/<int:cid>/actions/<aid>", methods=["POST"])
    def maint_action(cid, aid):
        """{op: mark|unmark|simulate|execute, actor}."""
        body = request.get_json(silent=True) or {}
        op, actor = body.get("op"), str(body.get("actor") or "")
        with _lock:
            c = conn_()
            try:
                camp = _row(c, cid)
                if not camp:
                    return jsonify({"error": "campagne inconnue"}), 404
                camp = _evaluated(c, camp, current_snapshot())
                st, a = _find_action(camp, aid)
                if not a:
                    return jsonify({"error": "action inconnue"}), 404
                rid = None
                if op in ("mark", "unmark"):
                    a.update(manual_done=op == "mark", manual_by=actor or None, manual_at=int(time.time()) if op == "mark" else None)
                elif op in ("simulate", "execute"):
                    if a.get("kind") != "pra":
                        return jsonify({"error": "action manuelle : rien à exécuter"}), 400
                    if op == "execute" and (a.get("run") or {}).get("status") == "running":
                        return jsonify({"error": "exécution déjà en cours"}), 409
                    if op == "execute" and st.get("state") == "blocked" and not body.get("force"):
                        return jsonify({"error": "étape bloquée : l'étape précédente n'est pas terminée"}), 409
                    rid = launch(c, camp, a, op, actor)
                else:
                    return jsonify({"error": "op : mark, unmark, simulate, execute"}), 400
                _save(c, camp, {"event": op, "action": a["title"], "by": actor, "run_id": rid}); c.commit()
                camp = _evaluated(c, _row(c, cid), current_snapshot())
            finally:
                c.close()
        return jsonify({"campaign": camp, "run_id": rid}), 200

    @app.route("/maint/templates/<kind>", methods=["POST"])
    def maint_template(kind):
        body = request.get_json(silent=True) or {}
        try:
            t = template(kind, body, current_snapshot())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        camp, err = validate(dict(t, status="draft"))
        if err:
            return jsonify({"error": err}), 400
        return jsonify({"campaign": camp}), 200

    @app.route("/maint/backups", methods=["GET"])
    def maint_backups():
        return jsonify(pbs_overview(current_snapshot(), int(request.args.get("old_h") or 48))), 200

    if start_loop:
        threading.Thread(target=_loop, name="maint", daemon=True).start()
