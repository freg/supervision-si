# -*- coding: utf-8 -*-
"""#756 : gestes encadrés sur l'hôte, depuis le hub (tuile Parc IA, fiche agent) -- PAS un shell : une liste fermée
d'actions, des paramètres contrôlés, des listes blanches réglées dans agent.json, un motif obligatoire pour tout ce qui
modifie, un journal d'audit sur l'hôte (/var/log/si-agent/hostops-audit.log), une sortie bornée.

  Lecture : service_status, journal, docker_ps, docker_logs, gpu, disk
  Action  : service_restart, docker_restart, compose_update (pull puis up -d)          [motif]

agent.json, clé `hostops` (facultative) :
  {"units": ["ollama", "docker"], "containers": ["*"], "compose_dirs": ["/opt/ia"], "enabled": true}
Unités par défaut : ollama, docker ; conteneurs : tous ; dossiers compose : aucun (compose_update refusé)."""
import fnmatch
import json
import os
import re
import time

AUDIT_LOG = "/var/log/si-agent/hostops-audit.log"
MAX_OUT = 20000
READ = ("service_status", "journal", "docker_ps", "docker_logs", "gpu", "disk")
WRITE = ("service_restart", "docker_restart", "compose_update")
UNIT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9@._-]{0,80}$")
CONTAINER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")
DEFAULTS = {"units": ["ollama", "docker"], "containers": ["*"], "compose_dirs": [], "enabled": True}
LABELS = {"service_status": "état d'un service", "journal": "journal d'un service", "docker_ps": "conteneurs Docker",
          "docker_logs": "journal d'un conteneur", "gpu": "carte graphique", "disk": "espace disque",
          "service_restart": "redémarrer un service", "docker_restart": "redémarrer un conteneur", "compose_update": "mettre à jour une pile compose (pull + up -d)"}


def settings(cfg):
    s = dict(DEFAULTS)
    s.update({k: v for k, v in ((cfg or {}).get("hostops") or {}).items() if k in DEFAULTS})
    return s


def catalogue(cfg):
    """Ce que le hub peut proposer pour cet hôte."""
    s = settings(cfg)
    return {"enabled": bool(s["enabled"]), "read": list(READ), "write": list(WRITE), "labels": LABELS,
            "units": s["units"], "containers": s["containers"], "compose_dirs": s["compose_dirs"]}


def _allowed(value, patterns):
    return any(fnmatch.fnmatchcase(value, p) for p in patterns or [])


def plan(params, cfg, which=None):
    """-> (liste d'argv, erreur). Rien n'est exécuté ici."""
    s = settings(cfg)
    if not s["enabled"]:
        return None, "gestes encadrés désactivés sur cet hôte (agent.json : hostops.enabled)"
    a = str(params.get("action") or "")
    if a not in READ + WRITE:
        return None, "action : %s" % ", ".join(READ + WRITE)
    if a in ("service_status", "journal", "service_restart"):
        unit = str(params.get("unit") or "")
        if not UNIT_RE.match(unit) or not _allowed(unit, s["units"]):
            return None, "service non autorisé (agent.json hostops.units : %s)" % ", ".join(s["units"])
        if a == "service_status":
            return [["systemctl", "status", unit, "--no-pager", "-n", "20"]], None
        if a == "journal":
            n = max(10, min(1000, int(params.get("lines") or 200)))
            argv = ["journalctl", "-u", unit, "-n", str(n), "--no-pager", "-o", "short-iso"]
            if params.get("priority") in ("err", "warning"):
                argv += ["-p", params["priority"]]
            return [argv], None
        return [["systemctl", "restart", unit], ["systemctl", "is-active", unit]], None
    if a == "docker_ps":
        return [["docker", "ps", "-a", "--format", "{{json .}}"]], None
    if a in ("docker_logs", "docker_restart"):
        c = str(params.get("container") or "")
        if not CONTAINER_RE.match(c) or not _allowed(c, s["containers"]):
            return None, "conteneur non autorisé (agent.json hostops.containers)"
        if a == "docker_logs":
            return [["docker", "logs", "--tail", str(max(10, min(1000, int(params.get("lines") or 200)))), "--timestamps", c]], None
        return [["docker", "restart", c]], None
    if a == "compose_update":
        d = str(params.get("dir") or "")
        if not d.startswith("/") or ".." in d or d.rstrip("/") not in [x.rstrip("/") for x in s["compose_dirs"]]:
            return None, "dossier compose non autorisé (agent.json hostops.compose_dirs : %s)" % (", ".join(s["compose_dirs"]) or "aucun")
        return [["docker", "compose", "--project-directory", d, "pull"], ["docker", "compose", "--project-directory", d, "up", "-d"]], None
    if a == "gpu":
        which = which or (lambda x: None)
        if which("nvidia-smi"):
            return [["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,driver_version", "--format=csv"]], None
        if which("xpu-smi"):
            return [["xpu-smi", "discovery"]], None
        return [["sh", "-c", "lspci | grep -Ei 'vga|3d|display'"]], None
    return [["df", "-hT", "-x", "tmpfs", "-x", "devtmpfs", "-x", "overlay"]], None


def audit(entry, path=AUDIT_LOG):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.chmod(path, 0o600)
    except OSError:
        pass


def run(params, cfg, runner, which=None, audit_path=AUDIT_LOG, now=None):
    """runner(argv, timeout) -> (code, stdout, stderr). Écritures : motif ≥ 4 caractères ; tout est journalisé."""
    a = str(params.get("action") or "")
    reason = str(params.get("reason") or "").strip()
    refused = a in WRITE and len(reason) < 4
    argvs, err = (None, "motif obligatoire pour une action qui modifie l'hôte") if refused else plan(params, cfg, which)
    audit({"at": int(now or time.time()), "action": a, "actor": params.get("actor"), "reason": reason or None,
           "params": {k: v for k, v in params.items() if k not in ("reason", "actor")}, "refused": err}, audit_path)
    if err:
        return {"ok": False, "error": err}
    out, code = [], 0
    for argv in argvs:
        code, so, se = runner(argv, 600 if a == "compose_update" else 120)
        out.append("$ %s\n%s%s" % (" ".join(argv), so or "", se or ""))
        if code != 0 and a != "service_status":       # status : code 3 = service arrêté, sortie utile quand même
            break
    text = "\n".join(out)
    res = {"ok": code == 0 or a == "service_status", "action": a, "code": code, "output": text[-MAX_OUT:], "truncated": len(text) > MAX_OUT}
    if a == "docker_ps" and code == 0:
        rows = []
        for line in (out[0].split("\n", 1)[1] if "\n" in out[0] else "").splitlines():
            try:
                c = json.loads(line)
                rows.append({"name": c.get("Names"), "image": c.get("Image"), "state": c.get("State"), "status": c.get("Status"), "ports": c.get("Ports")})
            except ValueError:
                continue
        res["containers"] = rows
    if not res["ok"]:
        res["error"] = "code %d" % code
    return res
