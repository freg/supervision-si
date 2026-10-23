#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""si-onglets (livraison #848) : rouvre à l'ouverture de la session graphique la fenêtre de terminal et tous ses
onglets (dossier et commande de chacun, ex. « ssh super »), en plein écran. GNOME Terminal, Linux, sans root,
bibliothèque standard seule.

  si-onglets --capturer   relève les onglets ouverts maintenant (shells de gnome-terminal : dossier courant et
                          commande au premier plan) et les enregistre ; à lancer depuis un des onglets ;
  si-onglets --ouvrir     ouvre la fenêtre et ses onglets (lancé par la session, ~/.config/autostart) ;
  si-onglets --liste      affiche les onglets enregistrés.
Configuration : ~/.config/si-onglets/onglets.json (modifiable à la main : titre, dossier, commande ; plein_ecran,
attente_s). Pur et testé : processus_lus, onglets_de, commande_terminal."""
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

VERSION = "1.0.0"
CONF = os.path.expanduser(os.environ.get("SI_ONGLETS_CONF", "~/.config/si-onglets/onglets.json"))
DEFAUT = {"plein_ecran": True, "attente_s": 5, "onglets": []}
NON_RELANCES = ("si-onglets", "si_onglets.py")       # la commande qui capture n'est pas un onglet à rejouer


def processus_lus(proc="/proc"):
    """{pid: {pid, ppid, comm, cmd: [..], cwd}} des processus lisibles (les siens)."""
    out = {}
    for d in os.listdir(proc):
        if not d.isdigit():
            continue
        try:
            stat = open(os.path.join(proc, d, "stat")).read()
            f = stat.rfind(")")
            cmd = [c.decode("utf-8", "replace") for c in open(os.path.join(proc, d, "cmdline"), "rb").read().split(b"\0") if c]
            out[int(d)] = {"pid": int(d), "ppid": int(stat[f + 2:].split()[1]), "comm": stat[stat.find("(") + 1:f], "cmd": cmd,
                           "cwd": os.readlink(os.path.join(proc, d, "cwd"))}
        except (OSError, ValueError, IndexError):
            continue
    return out


def _tilde(chemin, maison):
    return "~" + chemin[len(maison):] if maison and (chemin == maison or chemin.startswith(maison + "/")) else chemin


def onglets_de(procs, maison=None):
    """Shells enfants de gnome-terminal-server (un par onglet, dans l'ordre d'ouverture) -> onglets."""
    maison = maison if maison is not None else os.path.expanduser("~")
    serveurs = {p for p, i in procs.items() if i["comm"].startswith("gnome-terminal")}
    out = []
    for s in sorted((i for i in procs.values() if i["ppid"] in serveurs), key=lambda i: i["pid"]):
        enfants = sorted((i for i in procs.values() if i["ppid"] == s["pid"] and i["cmd"]), key=lambda i: i["pid"])
        enfants = [e for e in enfants if not any(n in " ".join(e["cmd"][:2]) for n in NON_RELANCES)]
        commande, titre = "", os.path.basename(s["cwd"].rstrip("/")) or "~"
        if enfants:
            e = enfants[0]
            commande = " ".join(shlex.quote(c) for c in e["cmd"])
            if os.path.basename(e["cmd"][0]) in ("ssh", "mosh", "telnet"):
                titre = next((c for c in e["cmd"][1:] if not c.startswith("-")), titre)
            else:
                titre = os.path.basename(e["cmd"][0])
        out.append({"titre": titre, "dossier": _tilde(s["cwd"], maison), "commande": commande})
    return out


def commande_terminal(conf, maison=None):
    """Réglages -> argv de gnome-terminal : une fenêtre (plein écran ou agrandie), un onglet par entrée ; la
    commande d'un onglet est suivie d'un shell, pour que l'onglet reste ouvert quand elle se termine."""
    maison = maison if maison is not None else os.path.expanduser("~")
    a = ["gnome-terminal", "--window", "--full-screen" if conf.get("plein_ecran", True) else "--maximize"]
    for i, o in enumerate(conf.get("onglets") or [{"dossier": "~"}]):
        if i:
            a.append("--tab")
        d = o.get("dossier") or "~"
        a += ["--working-directory", maison + d[1:] if d.startswith("~") else d]
        if o.get("commande"):
            a += ["--command", "bash -c %s" % shlex.quote("%s; exec bash" % o["commande"])]
    return a


def lire():
    try:
        c = json.load(open(CONF))
    except (OSError, ValueError):
        c = {}
    return dict(DEFAUT, **c)


def ecrire(c):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    if os.path.exists(CONF):
        shutil.copy2(CONF, CONF + ".avant")
    with open(CONF + ".tmp", "w") as fh:
        json.dump(c, fh, ensure_ascii=False, indent=1)
    os.replace(CONF + ".tmp", CONF)


def main():
    conf = lire()
    if "--capturer" in sys.argv:
        o = onglets_de(processus_lus())
        if not o:
            print("aucun onglet de gnome-terminal trouvé (lancer depuis un onglet de GNOME Terminal)", file=sys.stderr)
            sys.exit(1)
        conf["onglets"] = o
        ecrire(conf)
        print("%d onglet(s) enregistré(s) dans %s (copie précédente : .avant) :" % (len(o), CONF))
    if "--capturer" in sys.argv or "--liste" in sys.argv:
        for i, x in enumerate(conf["onglets"], 1):
            print("%2d. %-16s %-40s %s" % (i, x["titre"], x["dossier"], x["commande"] or "(shell)"))
        return
    if "--ouvrir" in sys.argv or len(sys.argv) == 1:
        if not shutil.which("gnome-terminal"):
            print("gnome-terminal absent", file=sys.stderr)
            sys.exit(1)
        time.sleep(max(0, int(conf.get("attente_s") or 0)) if "--sans-attente" not in sys.argv else 0)
        subprocess.Popen(commande_terminal(conf), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return
    print(__doc__)


if __name__ == "__main__":
    main()
