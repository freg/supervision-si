# -*- coding: utf-8 -*-
"""#940 : gestion à distance d'un NAS QNAP par SSH depuis l'agent du LAN -- module pur (testé).

Principe (règle de production : rien ne se modifie sans étude ni autorisation) : les commandes exécutées sur le NAS ne
sont PAS inventées par le hub. Elles viennent du fichier de réglages de la sonde (/etc/si-agent/nas-qnap.json), section
"actions" de chaque NAS, écrite par l'administrateur après l'étude (sortie « aide » de la sonde) :

    {"name": "nas-1", "host": "...", "user": "admin", "key": "...",
     "actions": {"snapshot": {"commande": "qcli_snapshot -c -v {volume}", "lecture": false, "description": "prend un snapshot"},
                 "snapshots-liste": {"commande": "qcli_snapshot -l", "lecture": true}}}

- `essai` : exécute une action déclarée `lecture: true` (ou une commande de lecture libre parmi une liste blanche : ls, cat,
  df, getcfg, smbstatus, qcli_* -l) -- autorisation « lecture » suffit ;
- `executer` : exécute une action déclarée (lecture: false) -- INTERVENTION, autorisation « intervention » exigée.
Les arguments ({volume}, {partage}, {nom}) sont substitués après validation stricte (lettres, chiffres, _ - .).
"""
import json
import re

ARG_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
LECTURE_OK = re.compile(r"^(ls|cat|head|tail|df|du|stat|getcfg|smbstatus|mdadm --detail|cat /proc/mdstat|uptime|who|netstat|qcli_\w+ -l|qcli_\w+ --list|snapshot_util -l|find)\b")
INTERDIT = re.compile(r"[;&|`$<>]|\brm\b|\bmv\b|\bdd\b|\bmkfs\b|\breboot\b|\bpoweroff\b|\bsetcfg\b|\bhalt\b")


def charger(chemin="/etc/si-agent/nas-qnap.json", lire=None):
    """Liste des NAS déclarés (fichier de la sonde)."""
    try:
        txt = lire(chemin) if lire else open(chemin, encoding="utf-8").read()
        l = json.loads(txt)
        return [c for c in l if isinstance(c, dict) and c.get("host")]
    except (OSError, ValueError, TypeError):
        return []


def trouver(cibles, nom):
    return next((c for c in cibles if str(c.get("name") or c.get("host")) == str(nom) or str(c.get("host")) == str(nom)), None)


def composer(cible, mode, action=None, commande=None, args=None):
    """-> (commande shell à passer au NAS, lecture: bool) ou lève ValueError. `mode` : essai | executer."""
    args = args if isinstance(args, dict) else {}
    for k, v in args.items():
        if not ARG_RE.match(str(v)):
            raise ValueError("argument %s invalide (lettres, chiffres, . _ - seulement)" % k)
    actions = cible.get("actions") if isinstance(cible.get("actions"), dict) else {}
    if action:
        a = actions.get(action)
        if not isinstance(a, dict) or not a.get("commande"):
            raise ValueError("action « %s » non déclarée dans nas-qnap.json pour ce NAS (section actions)" % action)
        lecture = bool(a.get("lecture"))
        cmd = str(a["commande"])
    elif commande:
        cmd, lecture = str(commande).strip(), True
        if not LECTURE_OK.match(cmd):
            raise ValueError("commande libre refusée : seules des commandes de lecture connues sont admises en essai")
    else:
        raise ValueError("action ou commande requise")
    if INTERDIT.search(cmd) and not (action and not lecture):
        raise ValueError("commande refusée (caractère ou mot interdit en lecture)")
    if mode == "essai" and not lecture:
        raise ValueError("« %s » est une action de modification : passer par executer (intervention)" % action)
    if mode == "executer" and lecture:
        mode = "essai"
    try:
        cmd = cmd.format(**{k: str(v) for k, v in args.items()})
    except (KeyError, IndexError) as e:
        raise ValueError("argument manquant pour la commande : %s" % e)
    if "{" in cmd or "}" in cmd:
        raise ValueError("argument manquant pour la commande")
    return cmd, lecture


def argv_ssh(cible, cmd):
    a = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", "-p", str(int(cible.get("port") or 22))]
    if cible.get("key"):
        a += ["-i", str(cible["key"])]
    a += ["%s@%s" % (cible.get("user") or "admin", cible["host"]), cmd]
    return a


def interpreter(mode, action, cmd, returncode, stdout, stderr):
    out = (stdout or "")[-4000:]
    err = (stderr or "")[-1000:]
    return {"mode": mode, "action": action, "commande": cmd, "ok": returncode == 0, "code": returncode, "sortie": out, "erreur": err if returncode != 0 else ""}
