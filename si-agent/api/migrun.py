# -*- coding: utf-8 -*-
"""#774 : tuile « Migration 2026-2027 » -- plan d'étapes pré-paramétré (importé en JSON, hors dépôt car il contient les
vrais noms), pilotage (démarrer, pause, reprendre, arrêter, étape suivante, automatique / manuel, relancer, sauter,
« fait » pour une étape manuelle), exécution d'une étape = commande `migstep` à l'agent désigné, état relu de la sonde
« migration » (statut, taille copiée, débit, fin estimée, fin du journal). Toute erreur est classée (cause, détail,
solution) ; une solution sans risque est appliquée par le bouton « Solution » (relance avec reprise), les autres donnent
la commande exacte à lancer. Rien ne s'exécute sans un geste dans le hub, sauf en mode automatique : l'étape suivante
part quand la précédente est réussie. Journal de chaque geste (mig_log). Pur : validate_plan, expand, classify,
next_step, apply_report ; l'état vit en base (plusieurs workers possibles, aucun fil d'exécution)."""
import json
import re
import secrets
import time

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS mig_plan (id INTEGER PRIMARY KEY CHECK (id = 1), data TEXT NOT NULL, vars TEXT NOT NULL DEFAULT '{}', updated_at TEXT, updated_by TEXT)",
    "CREATE TABLE IF NOT EXISTS mig_run (id INTEGER PRIMARY KEY CHECK (id = 1), state TEXT NOT NULL DEFAULT 'arrete', mode TEXT NOT NULL DEFAULT 'manuel', updated_at TEXT, updated_by TEXT)",
    "CREATE TABLE IF NOT EXISTS mig_steps (step_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'a_faire', agent_id TEXT, command_id TEXT, "
    "launched_at REAL, ended_at REAL, attempts INTEGER DEFAULT 0, report TEXT, note TEXT, updated_at TEXT)",
    "CREATE TABLE IF NOT EXISTS mig_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, who TEXT, action TEXT, step_id TEXT, detail TEXT)",
)
KINDS = ("check_ssh", "check_space", "check_file", "zfs_create", "rsync_pull", "rsync_pull_all", "zfs_pull", "zfs_send_file",
         "verify_rsync", "verify_zfs", "manual")
DONE = ("fait", "manuel_fait", "saute")
ACTIVE = ("lance", "en_cours", "en_pause")
STATUS_LABEL = {"a_faire": "à faire", "lance": "envoyé à l'agent", "en_cours": "en cours", "en_pause": "en pause", "fait": "réussie",
                "erreur": "en erreur", "arrete": "arrêtée", "saute": "sautée", "manuel": "à faire à la main", "manuel_fait": "faite à la main"}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]{0,31})\}")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stamp():
    """Horodatage à la microseconde : deux gestes rapprochés (pause puis reprise) partent dans l'ordre."""
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%06dZ" % int((t % 1) * 1e6)


def init(conn):
    for s in SCHEMA:
        conn.execute(s)


# ---------------------------------------------------------------- plan

def validate_plan(plan):
    """Plan importé -> (plan normalisé, erreur). {name, vars: {NOM: valeur}, phases: [{id, title, note?, steps: [{id, title,
    agent, kind, params, why?}]}]} ; identifiants uniques ; types connus ; variables ${NOM} déclarées."""
    if not isinstance(plan, dict) or not isinstance(plan.get("phases"), list) or not plan["phases"]:
        return None, "plan attendu : {name, vars, phases: [{id, title, steps: [...]}]}"
    vars_ = plan.get("vars") or {}
    if not isinstance(vars_, dict) or any(not re.match(r"^[A-Z][A-Z0-9_]{0,31}$", k) for k in vars_):
        return None, "vars : {NOM_EN_MAJUSCULES: valeur}"
    seen, out = set(), {"name": str(plan.get("name") or "Migration")[:120], "vars": {k: str(v)[:200] for k, v in vars_.items()}, "phases": []}
    for ph in plan["phases"]:
        if not isinstance(ph, dict) or not ID_RE.match(str(ph.get("id") or "")) or not isinstance(ph.get("steps"), list):
            return None, "phase invalide (id, title, steps)"
        steps = []
        for st in ph["steps"]:
            if not isinstance(st, dict):
                return None, "étape invalide dans %s" % ph["id"]
            sid, kind = str(st.get("id") or ""), str(st.get("kind") or "")
            if not ID_RE.match(sid) or sid in seen:
                return None, "identifiant d'étape invalide ou en double : %s" % sid
            if kind not in KINDS:
                return None, "étape %s : type inconnu %s" % (sid, kind)
            if kind != "manual" and not str(st.get("agent") or "").strip():
                return None, "étape %s : agent manquant" % sid
            params = st.get("params") or {}
            if not isinstance(params, dict):
                return None, "étape %s : params doit être un objet" % sid
            missing = sorted({v for v in VAR_RE.findall(json.dumps(params)) if v not in vars_})
            if missing:
                return None, "étape %s : variable(s) non déclarée(s) %s" % (sid, ", ".join(missing))
            seen.add(sid)
            steps.append({"id": sid, "title": str(st.get("title") or sid)[:200], "agent": str(st.get("agent") or "")[:64], "kind": kind,
                          "params": params, "why": str(st.get("why") or "")[:600], "check": str(st.get("check") or "")[:600]})
        out["phases"].append({"id": ph["id"], "title": str(ph.get("title") or ph["id"])[:160], "note": str(ph.get("note") or "")[:600], "steps": steps})
    if not seen:
        return None, "plan sans étape"
    return out, None


def all_steps(plan):
    return [s for ph in (plan or {}).get("phases") or [] for s in ph["steps"]]


def expand(params, vars_):
    """Remplace ${NOM} par la valeur de la variable -> (params, variables vides)."""
    empty = set()

    def sub(v):
        if isinstance(v, str):
            def rep(m):
                val = (vars_ or {}).get(m.group(1), "")
                if not str(val).strip():
                    empty.add(m.group(1))
                return str(val)
            return VAR_RE.sub(rep, v)
        if isinstance(v, list):
            return [sub(x) for x in v]
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        return v
    return sub(params), sorted(empty)


def next_step(plan, states):
    """Première étape ni réussie, ni sautée, ni faite à la main (dans l'ordre du plan)."""
    for s in all_steps(plan):
        if (states.get(s["id"]) or {}).get("status", "a_faire") not in DONE:
            return s
    return None


# ---------------------------------------------------------------- erreurs : cause, détail, solution

def _host(step):
    return (step.get("params") or {}).get("host") or "<hôte>"


ERRORS = [   # (code, motif dans le journal, titre, explication, solution(step, agent) -> {label, kind: retry|command|none, command?})
    ("ssh-cle", r"Permission denied \(publickey", "Clé SSH refusée par le nœud distant",
     "L'agent se connecte en root par clé ; la clé publique de cet hôte n'est pas dans /root/.ssh/authorized_keys du nœud distant.",
     lambda s, a: {"label": "Installer la clé (mot de passe root du distant demandé une fois), puis relancer", "kind": "command",
                   "where": a, "command": "[ -f /root/.ssh/id_ed25519 ] || ssh-keygen -q -t ed25519 -N '' -f /root/.ssh/id_ed25519; ssh-copy-id -i /root/.ssh/id_ed25519.pub root@%s" % _host(s)}),
    ("ssh-empreinte", r"Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED", "Empreinte du nœud distant changée",
     "Le nœud distant a été réinstallé ou son adresse a changé : son empreinte ne correspond plus à celle connue de cet hôte.",
     lambda s, a: {"label": "Oublier l'ancienne empreinte puis relancer", "kind": "command", "where": a,
                   "command": "ssh-keygen -R %s && ssh -o StrictHostKeyChecking=accept-new root@%s true" % (_host(s), _host(s))}),
    ("dns", r"Could not resolve hostname|Name or service not known|Temporary failure in name resolution", "Nom du nœud distant introuvable (DNS)",
     "L'hôte ne résout pas le nom : /etc/resolv.conf vide ou nom inconnu.",
     lambda s, a: {"label": "Vérifier la résolution de noms de l'hôte", "kind": "command", "where": a,
                   "command": "cat /etc/resolv.conf; getent hosts %s || echo 'nom inconnu : mettre l adresse IP dans la variable du plan'" % _host(s)}),
    ("reseau", r"Connection (timed out|refused|reset)|Broken pipe|connection unexpectedly closed|kex_exchange_identification|No route to host|Network is unreachable",
     "Liaison coupée ou refusée", "La connexion vers le nœud distant a été interrompue (réseau, redémarrage, pare-feu). Les copies reprennent là où elles s'étaient arrêtées.",
     lambda s, a: {"label": "Relancer (reprise automatique)", "kind": "retry"}),
    ("espace", r"No space left on device|ESPACE INSUFFISANT|out of space|insufficient space", "Place insuffisante sur la destination",
     "Le volume ou le disque de destination est plein (ou n'a pas la place demandée).",
     lambda s, a: {"label": "Voir l'occupation de la destination", "kind": "command", "where": a,
                   "command": "zpool list; zfs list -o name,used,avail -d 2; df -h"}),
    ("deja-en-cours", r"UN AUTRE RSYNC ÉCRIT DÉJÀ|tourne déjà|copie encore en cours", "Une autre copie écrit déjà au même endroit",
     "Une copie lancée à la main (session tmux) ou une étape précédente travaille encore sur cette destination.",
     lambda s, a: {"label": "Voir les copies en cours (arrêter la session tmux si c'est un doublon), puis relancer", "kind": "command", "where": a,
                   "command": "pgrep -af 'rsync|zfs (send|recv)'; tmux ls"}),
    ("zfs-existe", r"destination .* exists|destination has been modified|already exists", "Volume de destination déjà présent et différent",
     "Un volume du même nom existe déjà sans l'instantané attendu (copie précédente non reprenable).",
     lambda s, a: {"label": "Contrôler le volume, puis le renommer avant de relancer (jamais de suppression automatique)", "kind": "command", "where": a,
                   "command": "zfs list -t all -r %s | head -20" % ((s.get("params") or {}).get("dest") or "<volume>")}),
    ("zfs-introuvable", r"AUCUN VOLUME TROUVÉ|dataset does not exist|could not find any snapshots", "Volume ou instantané introuvable sur la source",
     "Les numéros de CT / VM du plan ne correspondent à aucun volume ZFS du nœud distant (ou le pool est différent).",
     lambda s, a: {"label": "Lister les volumes du nœud distant", "kind": "command", "where": a,
                   "command": "ssh root@%s 'pct list; qm list; zfs list -o name,used -r %s'" % (_host(s), (s.get("params") or {}).get("pool") or "rpool")}),
    ("rsync-partiel", r"rsync error: some files/attrs were not transferred|\(code 23\)", "Quelques fichiers non copiés",
     "rsync n'a pas pu lire certains fichiers (droits, fichiers spéciaux ou en cours d'écriture). Une relance recopie seulement la différence.",
     lambda s, a: {"label": "Relancer (seule la différence est recopiée)", "kind": "retry"}),
    ("interrompue", r"ÉTAPE INTERROMPUE", "Étape interrompue en cours de route",
     "Le processus de l'étape a disparu sans code de sortie : l'hôte ou l'agent a redémarré. Les copies reprennent là où elles s'étaient arrêtées.",
     lambda s, a: {"label": "Relancer (reprise automatique)", "kind": "retry"}),
    ("incomplet", r"FICHIER INCOMPLET|TROP DE DIFFÉRENCES|incomplet\(s\)|réception inachevée|fichier absent", "Copie incomplète",
     "La vérification montre une copie inachevée : relancer l'étape de copie correspondante.",
     lambda s, a: {"label": "Relancer la copie concernée", "kind": "retry"}),
    ("agent-ancien", r"commande inconnue : migstep", "Agent trop ancien sur cet hôte",
     "L'agent de cet hôte ne connaît pas encore les étapes de migration (version antérieure à 0.5.71).",
     lambda s, a: {"label": "Mettre l'agent à jour depuis la maison (script agent-ssh.sh), puis relancer", "kind": "command", "where": "maison (Linux)",
                   "command": "cd ~/supervision-si/deploy/migration && ./agent-ssh.sh root@%s" % (a or "<hôte>")}),
    ("agent-bloque", r"agent bloqué", "Agent bloqué depuis le hub",
     "L'agent de cet hôte a été bloqué (Équipements › Agents) : il refuse toute commande.",
     lambda s, a: {"label": "Débloquer l'agent dans le hub, puis relancer", "kind": "none"}),
    ("lancement", r"lancement impossible|systemd-run", "L'étape n'a pas pu démarrer sur l'hôte",
     "systemd-run a refusé de lancer l'étape (unité du même nom encore présente, systemd indisponible).",
     lambda s, a: {"label": "Nettoyer l'unité restée en place, puis relancer", "kind": "command", "where": a,
                   "command": "systemctl reset-failed si-mig-%s 2>/dev/null; systemctl status si-mig-%s --no-pager | head -5" % (s.get("id"), s.get("id"))}),
    ("arret", r"^$", "Étape arrêtée", "L'étape a été arrêtée depuis le hub.", lambda s, a: {"label": "Relancer", "kind": "retry"}),
]


def classify(step, report, agent_name=""):
    """Rapport d'une étape en échec -> {code, title, detail, log, solution}."""
    log = "\n".join((report or {}).get("log_tail") or [])
    rc = (report or {}).get("rc")
    if (report or {}).get("state") == "stopped" or rc == 143:
        code, title, why, sol = ERRORS[-1][0], ERRORS[-1][2], ERRORS[-1][3], ERRORS[-1][4]
    else:
        hit = next((e for e in ERRORS[:-1] if re.search(e[1], log, re.I | re.M)), None)
        if hit:
            code, title, why, sol = hit[0], hit[2], hit[3], hit[4]
        else:
            code, title = "inconnue", "Échec de l'étape (code %s)" % rc
            why = "Cause non reconnue automatiquement : lire la fin du journal ci-dessous."
            sol = lambda s, a: {"label": "Relancer", "kind": "retry"}   # noqa: E731
    return {"code": code, "title": title, "detail": why, "rc": rc, "log": log[-4000:], "solution": sol(step, agent_name)}


# ---------------------------------------------------------------- base

def _log(conn, who, action, step_id=None, detail=""):
    conn.execute("INSERT INTO mig_log (at, who, action, step_id, detail) VALUES (?, ?, ?, ?, ?)", (now_iso(), (who or "?")[:64], action, step_id, str(detail)[:1000]))


def load(conn):
    init(conn)
    r = conn.execute("SELECT data, vars, updated_at, updated_by FROM mig_plan WHERE id = 1").fetchone()
    plan = json.loads(r[0]) if r else None
    vars_ = json.loads(r[1]) if r else {}
    run = conn.execute("SELECT state, mode, updated_at, updated_by FROM mig_run WHERE id = 1").fetchone()
    run = {"state": run[0], "mode": run[1], "updated_at": run[2], "updated_by": run[3]} if run else {"state": "arrete", "mode": "manuel"}
    states = {}
    for x in conn.execute("SELECT step_id, status, agent_id, command_id, launched_at, ended_at, attempts, report, note FROM mig_steps"):
        states[x[0]] = {"status": x[1], "agent_id": x[2], "command_id": x[3], "launched_at": x[4], "ended_at": x[5], "attempts": x[6] or 0,
                        "report": json.loads(x[7]) if x[7] else None, "note": x[8]}
    return plan, vars_, run, states


def _set_step(conn, sid, **kw):
    conn.execute("INSERT OR IGNORE INTO mig_steps (step_id) VALUES (?)", (sid,))
    if "report" in kw and kw["report"] is not None and not isinstance(kw["report"], str):
        kw["report"] = json.dumps(kw["report"], ensure_ascii=False)
    kw["updated_at"] = now_iso()
    conn.execute("UPDATE mig_steps SET %s WHERE step_id = ?" % ", ".join("%s = ?" % k for k in kw), list(kw.values()) + [sid])


def _set_run(conn, by, **kw):
    conn.execute("INSERT OR IGNORE INTO mig_run (id) VALUES (1)")
    kw.update(updated_at=now_iso(), updated_by=(by or "")[:64])
    conn.execute("UPDATE mig_run SET %s WHERE id = 1" % ", ".join("%s = ?" % k for k in kw), list(kw.values()))


def resolve_agent(conn, name):
    r = conn.execute("SELECT agent_id FROM agents WHERE agent_id = ? OR lower(hostname) = lower(?) OR lower(label) = lower(?) "
                     "OR lower(hostname) LIKE lower(?) || '.%' ORDER BY (agent_id = ?) DESC, last_seen_at DESC LIMIT 1",
                     (name, name, name, name, name)).fetchone()
    return r[0] if r else None


def _enqueue(conn, agent_id, params):
    """Commande migstep insérée sur LA connexion courante (appelée aussi pendant la réception d'une mesure)."""
    cid = "c-" + secrets.token_hex(6)
    conn.execute("INSERT INTO commands (id, agent_id, type, params, created_at) VALUES (?, ?, ?, ?, ?)",
                 (cid, agent_id, "migstep", json.dumps(params, ensure_ascii=False), _stamp()))
    return cid


def launch(conn, step, vars_, by):
    """Lance une étape -> (ok, message)."""
    if step["kind"] == "manual":
        _set_step(conn, step["id"], status="manuel", launched_at=time.time(), ended_at=None)
        _log(conn, by, "manuel", step["id"])
        return True, "étape %s : à faire à la main, puis « Fait »" % step["id"]
    params, empty = expand(step["params"], vars_)
    if empty:
        _set_step(conn, step["id"], status="erreur", report={"state": "failed", "rc": None, "log_tail": [], "blocked": "variable(s) à renseigner : %s" % ", ".join(empty)})
        return False, "renseigner d'abord : %s (Paramètres du plan)" % ", ".join(empty)
    aid = resolve_agent(conn, step["agent"])
    if not aid:
        _set_step(conn, step["id"], status="erreur", report={"state": "failed", "rc": None, "log_tail": [], "blocked": "agent %s inconnu du hub" % step["agent"]})
        return False, "agent %s inconnu du hub (installer l'agent sur cet hôte)" % step["agent"]
    cid = _enqueue(conn, aid, {"action": "start", "actor": by, "step": {"id": step["id"], "kind": step["kind"], "title": step["title"], "params": params}})
    prev = conn.execute("SELECT attempts FROM mig_steps WHERE step_id = ?", (step["id"],)).fetchone()
    _set_step(conn, step["id"], status="lance", agent_id=aid, command_id=cid, launched_at=time.time(), ended_at=None,
              attempts=((prev[0] or 0) if prev else 0) + 1, report=None)
    _log(conn, by, "lancer", step["id"], "agent %s, commande %s" % (step["agent"], cid))
    return True, "étape %s envoyée à %s" % (step["id"], step["agent"])


STATE_MAP = {"running": "en_cours", "paused": "en_pause", "done": "fait", "failed": "erreur", "stopped": "arrete"}


def sync_commands(conn, by="agent"):
    """Étapes « envoyées » : refus de l'agent (commande en échec) -> erreur avec le message de l'agent. -> étapes changées."""
    changed = []
    rows = conn.execute("SELECT s.step_id, c.status, c.result FROM mig_steps s JOIN commands c ON c.id = s.command_id "
                        "WHERE s.status = 'lance' AND c.status = 'failed'").fetchall()
    for sid, _st, res in rows:
        try:
            err = str((json.loads(res or "{}") or {}).get("error") or "refus de l'agent")
        except ValueError:
            err = "refus de l'agent"
        _set_step(conn, sid, status="erreur", ended_at=time.time(), report={"state": "failed", "rc": None, "log_tail": [err], "agent_error": err})
        _log(conn, by, "refus", sid, err)
        changed.append(sid)
    return changed


def apply_report(conn, agent_id, data, by="sonde"):
    """Mesure plugin:migration d'un agent -> statuts des étapes ; en mode automatique, l'étape suivante part quand la
    précédente réussit. -> liste des étapes changées."""
    init(conn)
    sync_commands(conn)
    plan, vars_, run, states = load(conn)
    if not plan:
        return []
    known = {s["id"]: s for s in all_steps(plan)}
    changed = []
    for rep in (data or {}).get("steps") or []:
        sid = (rep or {}).get("id")
        cur = states.get(sid)
        if sid not in known or not cur or cur.get("agent_id") != agent_id or cur["status"] in ("a_faire", "saute", "manuel", "manuel_fait"):
            continue
        if (rep.get("started_at") or 0) < (cur.get("launched_at") or 0) - 120:
            continue   # rapport d'une exécution précédente
        new = STATE_MAP.get(rep.get("state"))
        if rep.get("state") == "unknown" and time.time() - (rep.get("started_at") or time.time()) > 90:
            new = "erreur"   # ni en cours, ni code de sortie : processus disparu (hôte ou agent redémarré)
            rep = dict(rep, log_tail=list(rep.get("log_tail") or []) + ["ÉTAPE INTERROMPUE (hôte redémarré ?)"])
        if not new:
            continue
        kw = {"report": rep}
        if new != cur["status"]:
            kw["status"] = new
            if new in ("fait", "erreur", "arrete"):
                kw["ended_at"] = rep.get("ended_at") or time.time()
            changed.append((sid, cur["status"], new))
        _set_step(conn, sid, **kw)
    if any(n == "fait" for _s, _o, n in changed) and run["state"] == "en_cours" and run["mode"] == "auto":
        _p, _v, _r, states = load(conn)
        if not any(st.get("status") in ACTIVE for st in states.values()):
            nxt = next_step(plan, states)
            if nxt:
                launch(conn, nxt, vars_, "automatique")
            else:
                _set_run(conn, "automatique", state="termine")
    if any(n == "erreur" for _s, _o, n in changed) and run["mode"] == "auto":
        _set_run(conn, "automatique", state="en_pause")   # une erreur suspend l'enchaînement automatique
    return changed


def control(conn, action, step_id=None, by=""):
    """Geste depuis le hub -> (ok, message)."""
    init(conn)
    plan, vars_, run, states = load(conn)
    if not plan:
        return False, "aucun plan importé"
    steps = {s["id"]: s for s in all_steps(plan)}
    running = [sid for sid, st in states.items() if st.get("status") in ACTIVE and sid in steps]

    def send(sid, act):
        st = states[sid]
        if st.get("agent_id"):
            _enqueue(conn, st["agent_id"], {"action": act, "id": sid, "actor": by})
    if action in ("auto", "manuel"):
        _set_run(conn, by, mode=action)
        _log(conn, by, "mode", None, action)
        return True, "mode %s" % action
    if action in ("start", "next"):
        if running:
            return False, "une étape tourne déjà (%s) : attendre, mettre en pause ou arrêter" % ", ".join(running)
        nxt = steps.get(step_id) if step_id else next_step(plan, states)
        if not nxt:
            _set_run(conn, by, state="termine")
            return True, "toutes les étapes sont faites"
        _set_run(conn, by, state="en_cours")
        return launch(conn, nxt, vars_, by)
    if action == "pause":
        for sid in running:
            send(sid, "pause")
            _set_step(conn, sid, status="en_pause")
        _set_run(conn, by, state="en_pause")
        _log(conn, by, "pause", None, ",".join(running))
        return True, "pause demandée" + (" (%s)" % ", ".join(running) if running else "")
    if action == "resume":
        paused = [sid for sid, st in states.items() if st.get("status") == "en_pause"]
        for sid in paused:
            send(sid, "resume")
            _set_step(conn, sid, status="en_cours")
        _set_run(conn, by, state="en_cours")
        _log(conn, by, "reprendre", None, ",".join(paused))
        return True, "reprise demandée"
    if action == "stop":
        for sid in running:
            send(sid, "stop")
            _set_step(conn, sid, status="arrete", ended_at=time.time())
        _set_run(conn, by, state="arrete")
        _log(conn, by, "arreter", None, ",".join(running))
        return True, "arrêt demandé"
    if step_id not in steps:
        return False, "étape inconnue"
    st = states.get(step_id) or {"status": "a_faire"}
    if action == "retry":
        if st["status"] in ACTIVE:
            return False, "l'étape tourne déjà"
        _set_run(conn, by, state="en_cours")
        return launch(conn, steps[step_id], vars_, by)
    if action == "skip":
        if st["status"] in ACTIVE:
            return False, "arrêter l'étape avant de la sauter"
        _set_step(conn, step_id, status="saute")
        _log(conn, by, "sauter", step_id)
        return True, "étape %s sautée" % step_id
    if action == "done":
        if st["status"] not in ("manuel", "a_faire", "erreur"):
            return False, "seule une étape manuelle (ou en erreur, réglée à la main) se marque « faite »"
        _set_step(conn, step_id, status="manuel_fait", ended_at=time.time())
        _log(conn, by, "fait", step_id)
        if run["mode"] == "auto" and run["state"] == "en_cours":
            _p, _v, _r, states = load(conn)
            nxt = next_step(plan, states)
            if nxt:
                launch(conn, nxt, vars_, "automatique")
        return True, "étape %s faite" % step_id
    if action == "reset":
        if st["status"] in ACTIVE:
            return False, "arrêter l'étape d'abord"
        _set_step(conn, step_id, status="a_faire", report=None, ended_at=None)
        _log(conn, by, "remettre", step_id)
        return True, "étape %s remise à faire" % step_id
    return False, "geste inconnu"


def set_plan(conn, plan, by):
    p, err = validate_plan(plan)
    if err:
        return None, err
    init(conn)
    old = conn.execute("SELECT vars FROM mig_plan WHERE id = 1").fetchone()
    vars_ = dict(p["vars"])
    if old:   # les valeurs déjà saisies dans le hub sont gardées
        vars_.update({k: v for k, v in json.loads(old[0] or "{}").items() if k in vars_ and str(v).strip()})
    conn.execute("INSERT INTO mig_plan (id, data, vars, updated_at, updated_by) VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                 "data = excluded.data, vars = excluded.vars, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                 (json.dumps(p, ensure_ascii=False), json.dumps(vars_, ensure_ascii=False), now_iso(), by))
    _log(conn, by, "plan", None, "%s : %d étape(s)" % (p["name"], len(all_steps(p))))
    return p, None


def set_vars(conn, vars_, by):
    init(conn)
    r = conn.execute("SELECT vars FROM mig_plan WHERE id = 1").fetchone()
    if not r:
        return None, "aucun plan importé"
    cur = json.loads(r[0] or "{}")
    for k, v in (vars_ or {}).items():
        if k in cur:
            cur[k] = str(v)[:200].strip()
    conn.execute("UPDATE mig_plan SET vars = ? WHERE id = 1", (json.dumps(cur, ensure_ascii=False),))
    _log(conn, by, "parametres", None, ", ".join(sorted(vars_ or {})))
    return cur, None


def view(conn):
    """État complet pour la tuile : plan, paramètres, marche, étapes (statut, mesure, erreur classée), journal récent."""
    init(conn)
    sync_commands(conn)
    plan, vars_, run, states = load(conn)
    if not plan:
        return {"plan": None, "run": run, "vars": {}, "log": []}
    names = {r[0]: r[1] or r[0] for r in conn.execute("SELECT agent_id, hostname FROM agents")}
    out_phases, counts = [], {}
    nxt = next_step(plan, states)
    for ph in plan["phases"]:
        steps = []
        for s in ph["steps"]:
            st = states.get(s["id"]) or {"status": "a_faire", "attempts": 0}
            rep = st.get("report") or {}
            err = classify(s, rep, names.get(st.get("agent_id"), s["agent"])) if st["status"] in ("erreur", "arrete") and not rep.get("blocked") else None
            if rep.get("blocked"):
                err = {"code": "bloque", "title": "Étape bloquée avant lancement", "detail": rep["blocked"], "rc": None, "log": "",
                       "solution": {"label": "Renseigner puis relancer", "kind": "retry"}}
            if st["status"] == "lance" and st.get("launched_at") and time.time() - st["launched_at"] > 300:
                err = {"code": "silence", "title": "L'agent n'a pas encore pris l'étape", "detail": "Envoyée il y a plus de 5 minutes : agent arrêté, "
                       "hôte injoignable, ou sonde « migration » non activée sur cet hôte.", "rc": None, "log": "",
                       "solution": {"label": "Vérifier l'agent sur l'hôte", "kind": "command", "where": names.get(st.get("agent_id"), s["agent"]),
                                    "command": "systemctl status si-agent --no-pager | head -5; grep -c migration /etc/si-agent/agent.json; ls -l /var/lib/si-agent/migration/"}}
            _p, empty = expand(s["params"], vars_)
            counts[st["status"]] = counts.get(st["status"], 0) + 1
            steps.append(dict(s, status=st["status"], status_label=STATUS_LABEL.get(st["status"], st["status"]), attempts=st.get("attempts", 0),
                              launched_at=st.get("launched_at"), ended_at=st.get("ended_at"), report=rep or None, error=err,
                              missing_vars=empty, next=bool(nxt and nxt["id"] == s["id"])))
        out_phases.append(dict(ph, steps=steps))
    log = [{"at": r[0], "who": r[1], "action": r[2], "step": r[3], "detail": r[4]}
           for r in conn.execute("SELECT at, who, action, step_id, detail FROM mig_log ORDER BY id DESC LIMIT 60")]
    total = len(all_steps(plan))
    return {"plan": {"name": plan["name"], "phases": out_phases}, "vars": vars_, "run": run, "counts": counts, "total": total,
            "done": sum(counts.get(k, 0) for k in DONE), "next": nxt["id"] if nxt else None, "log": log}
