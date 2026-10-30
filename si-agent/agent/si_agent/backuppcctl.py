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
