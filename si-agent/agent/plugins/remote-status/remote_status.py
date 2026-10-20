#!/usr/bin/env python3
"""Sonde remote-status (#792) : veilles distantes lues par ssh, pour les machines sans agent (vieux systèmes).
La machine distante écrit un fichier d'état d'une ligne : « OK|KO AAAA-MM-JJ HH:MM:SS détail » (ex. sms-veille du NMS).
La sonde le lit par ssh avec une clé dédiée ; côté distant, la clé est limitée à cette lecture :
    command="cat /var/www/sms/veille-etat.txt",no-pty,no-port-forwarding,no-X11-forwarding,no-agent-forwarding ssh-rsa AAAA…
Constats (tous critiques : une veille muette ne protège plus rien) :
    remote-status-ko@NOM, remote-status-stale@NOM (plus vieux que --age-max), remote-status-unreachable@NOM, remote-status-format@NOM.
Usage : remote_status.py --cible sms-nms=francois@192.0.2.20:/var/www/sms/veille-etat.txt [--cible …] [--age-max 1500]
                         [--cle /etc/si-agent/remote-status/id_rsa]
Sortie JSON : {at, cibles[], alerts[], error}. Stdlib seulement."""
import datetime
import json
import re
import subprocess
import sys
import time

DOSSIER = "/etc/si-agent/remote-status"
LIGNE = re.compile(r"^\s*(OK|KO)\s+(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\s*(.*)$", re.I)


def args_locaux(argv, chemin):
    """#792 : arguments de l'hôte dans un fichier root (« --option valeur » par ligne, # = commentaire), ajoutés à ceux du
    catalogue -- les cibles réelles (IP, comptes) restent sur la machine, jamais dans le dépôt ni le catalogue central."""
    try:
        for l in open(chemin, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#"):
                o, _, v = l.partition(" ")
                argv = argv + ([o, v.strip()] if v.strip() else [o])
    except OSError:
        pass
    return argv


def parse_cible(v):
    """« nom=compte@hôte:/chemin » -> {nom, compte, hote, chemin} ; None si mal formé."""
    m = re.match(r"^([\w.-]+)=([\w.-]+)@([\w.:-]+?):(/\S+)$", (v or "").strip())
    return {"nom": m.group(1), "compte": m.group(2), "hote": m.group(3), "chemin": m.group(4)} if m else None


def parse_etat(texte, maintenant=None):
    """Première ligne du fichier d'état -> {etat, date, age_s, detail} ; etat None si format inconnu.
    La date est l'heure locale de la machine distante (même fuseau supposé, horloges à l'heure)."""
    ligne = (texte or "").strip().splitlines()[0] if (texte or "").strip() else ""
    m = LIGNE.match(ligne)
    if not m:
        return {"etat": None, "date": None, "age_s": None, "detail": ligne[:200]}
    d = datetime.datetime.strptime(m.group(2).replace("T", " "), "%Y-%m-%d %H:%M:%S")
    age = int((maintenant or time.time()) - time.mktime(d.timetuple()))
    return {"etat": m.group(1).upper(), "date": m.group(2), "age_s": age, "detail": m.group(3).strip()[:300]}


def alerts_for(cibles, age_max):
    out = []
    for c in cibles:
        n = c["nom"]
        if c.get("error"):
            out.append({"code": "remote-status-unreachable@" + n, "severity": "critical",
                        "message": "%s : veille injoignable (%s) -- machine arrêtée, réseau ou clé ssh ?" % (n, c["error"][:150])})
        elif c.get("etat") is None:
            out.append({"code": "remote-status-format@" + n, "severity": "critical",
                        "message": "%s : fichier d'état illisible : %s" % (n, (c.get("detail") or "vide")[:150])})
        elif c["age_s"] is not None and c["age_s"] > age_max:
            out.append({"code": "remote-status-stale@" + n, "severity": "critical",
                        "message": "%s : pas de nouvelles depuis %d min (veille arrêtée ou machine plantée) ; dernier état %s"
                                   % (n, c["age_s"] // 60, c["etat"])})
        elif c["etat"] == "KO":
            out.append({"code": "remote-status-ko@" + n, "severity": "critical",
                        "message": "%s : EN PANNE depuis le dernier test (%s) : %s" % (n, c["date"], c["detail"][:200])})
    return out


def lire(c, cle, run=subprocess.run):
    argv = ["ssh", "-i", cle, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new",
            "-o", "UserKnownHostsFile=%s/known_hosts" % DOSSIER, "-o", "HostKeyAlgorithms=+ssh-rsa",
            "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa", "%s@%s" % (c["compte"], c["hote"]), "cat " + c["chemin"]]
    r = run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(((r.stderr or b"").decode("utf-8", "replace").strip().splitlines() or ["code %d" % r.returncode])[-1])
    return (r.stdout or b"").decode("utf-8", "replace")


def collect(argv, run=subprocess.run, maintenant=None):
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cibles": [], "alerts": [], "error": None}
    cle = argv[argv.index("--cle") + 1] if "--cle" in argv[:-1] else DOSSIER + "/id_rsa"
    age_max = int(argv[argv.index("--age-max") + 1]) if "--age-max" in argv[:-1] else 1500
    brutes = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--cible"]
    if not brutes:
        out["error"] = "aucune --cible (ex. --cible sms-nms=compte@hôte:/var/www/sms/veille-etat.txt)"
    for b in brutes:
        c = parse_cible(b)
        if not c:
            out["alerts"].append({"code": "remote-status-config", "severity": "warning", "message": "cible mal écrite : %s" % b[:100]})
            continue
        try:
            c.update(parse_etat(lire(c, cle, run), maintenant))
        except Exception as exc:  # noqa: BLE001
            c["error"] = str(exc)[:200]
        out["cibles"].append(c)
    out["alerts"] += alerts_for(out["cibles"], age_max)
    return out


if __name__ == "__main__":
    print(json.dumps(collect(args_locaux(sys.argv[1:], DOSSIER + "/args")), ensure_ascii=False))
