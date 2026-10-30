# -*- coding: utf-8 -*-
"""#939 : pilotage de BackupPC depuis l'agent du serveur BackupPC -- argv et interprétation, module pur (testé).
Actions : status (lecture), backup-full / backup-incr (demande une sauvegarde : BackupPC_serverMesg backup <hôte> <hôte>
<utilisateur> <1|0>), stop (BackupPC_serverMesg stop <hôte> <utilisateur> <report_h>). Les actions autres que status sont
des INTERVENTIONS : l'agent exige l'autorisation « intervention » des commandes à distance (comme la restauration #934)."""
import os
import re
import shutil

BIN_CANDIDATS = ("/usr/share/backuppc/bin/BackupPC_serverMesg", "/usr/local/BackupPC/bin/BackupPC_serverMesg",
                 "/usr/local/bin/BackupPC_serverMesg", "/usr/bin/BackupPC_serverMesg")
HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ACTIONS = ("status", "backup-full", "backup-incr", "stop")


def binaire(candidats=BIN_CANDIDATS, existe=os.path.exists):
    return next((b for b in candidats if existe(b)), None)


def argv(action, host=None, user="hub", bin_path=None, backuppc_user="backuppc", backoff_h=0, root=True, which=shutil.which):
    """Ligne de commande (liste) ou lève ValueError. `root` : l'agent tourne en root -> exécution sous `backuppc_user`."""
    if action not in ACTIONS:
        raise ValueError("action inconnue : %s" % action)
    if not bin_path:
        raise ValueError("BackupPC_serverMesg introuvable sur cet hôte (serveur BackupPC ?)")
    if action != "status" and not HOST_RE.match(str(host or "")):
        raise ValueError("nom d'hôte BackupPC invalide")
    user = re.sub(r"[^A-Za-z0-9._@-]", "", str(user or "hub"))[:32] or "hub"
    if action == "status":
        a = [bin_path, "status", "hosts"]
    elif action == "stop":
        a = [bin_path, "stop", host, user, str(int(backoff_h or 0))]
    else:
        a = [bin_path, "backup", host, host, user, "1" if action == "backup-full" else "0"]
    if root and backuppc_user:
        if which("runuser"):
            a = ["runuser", "-u", backuppc_user, "--"] + a
        else:
            a = ["su", "-s", "/bin/sh", backuppc_user, "-c", " ".join(a)]
    return a


def interpreter(action, returncode, stdout, stderr, host=None):
    """Réponse de BackupPC_serverMesg : « ok: ... » = accepté ; sinon le texte d'erreur (hôte inconnu, serveur arrêté...)."""
    out = (stdout or "").strip()
    err = (stderr or "").strip()
    ok = returncode == 0 and not err.lower().startswith("can't") and "unknown host" not in out.lower() and "error" not in out.lower()[:40]
    rep = {"action": action, "host": host, "ok": bool(ok), "reponse": (out or err)[:400]}
    if not ok:
        rep["erreur"] = (err or out or "code %s" % returncode)[:300]
        if "connect" in (err + out).lower():
            rep["erreur"] += " -- le serveur BackupPC tourne-t-il ?"
    return rep


# #948 : mode RELAIS -- le serveur BackupPC (Debian 7) est relevé par SSH depuis un agent du LAN (sonde backuppc v2,
# /etc/si-agent/backuppc.json) : les actions passent par le même chemin, sous l'utilisateur backuppc via sudo.
import json as _json

BIN_DISTANT = ("/usr/share/backuppc/bin/BackupPC_serverMesg", "/usr/local/BackupPC/bin/BackupPC_serverMesg", "/usr/local/bin/BackupPC_serverMesg", "/usr/bin/BackupPC_serverMesg")


def charger_relais(chemin="/etc/si-agent/backuppc.json", lire=None):
    """Première cible du fichier de relais, ou None (pas de relais : BackupPC local)."""
    try:
        txt = lire(chemin) if lire else open(chemin, encoding="utf-8").read()
        l = [c for c in _json.loads(txt) if isinstance(c, dict) and c.get("host")]
        return l[0] if l else None
    except (OSError, ValueError, TypeError):
        return None


def commande_distante(action, host=None, user="hub", backoff_h=0):
    """Commande sh exécutée sur le serveur BackupPC (sous backuppc) : cherche BackupPC_serverMesg puis agit."""
    if action not in ACTIONS:
        raise ValueError("action inconnue : %s" % action)
    if action != "status" and not HOST_RE.match(str(host or "")):
        raise ValueError("nom d'hôte BackupPC invalide")
    user = re.sub(r"[^A-Za-z0-9._@-]", "", str(user or "hub"))[:32] or "hub"
    if action == "status":
        args = "status hosts"
    elif action == "stop":
        args = "stop %s %s %d" % (host, user, int(backoff_h or 0))
    else:
        args = "backup %s %s %s %s" % (host, host, user, "1" if action == "backup-full" else "0")
    cherche = 'B=""; for b in %s; do [ -x "$b" ] && B="$b" && break; done; [ -n "$B" ] || { echo "BackupPC_serverMesg introuvable" >&2; exit 2; }; ' % " ".join(BIN_DISTANT)
    return cherche + '"$B" ' + args


def argv_relais(cible, cmd):
    a = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", "-p", str(int(cible.get("port") or 22))]
    if cible.get("key"):
        a += ["-i", str(cible["key"])]
    a += ["%s@%s" % (cible.get("user") or "si-bk", cible["host"]), "sudo", "-n", "-u", str(cible.get("backuppc_user") or "backuppc"), "sh", "-c", cmd]
    return a
