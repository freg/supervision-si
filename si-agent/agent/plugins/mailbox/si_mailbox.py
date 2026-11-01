# -*- coding: utf-8 -*-
"""Sonde « mailbox » (#840) : résumés publiés par les agents de messagerie si-mailbox des sessions de ce poste, en mode
« relié » seulement (~/.local/share/si-mailbox/publication.json : compteurs, automates, dernières actions, jamais le
contenu des messages). Un agent en mode « discret » ne publie rien et reste invisible. Lecture seule."""
import glob
import json
import os
import time

MOTIFS = ("/home/*/.local/share/si-mailbox/publication.json", "/Users/*/.local/share/si-mailbox/publication.json",
          "/root/.local/share/si-mailbox/publication.json")


def collecter(motifs=MOTIFS, maintenant=None):
    t = maintenant or time.time()
    postes, alerts = [], []
    for m in motifs:
        for f in glob.glob(m):
            try:
                with open(f) as fh:
                    p = json.load(fh)
            except (OSError, ValueError):
                continue
            p = {k: p.get(k) for k in ("version", "ts", "utilisateur", "comptes", "automates", "traites_24h", "erreurs_24h", "derniers")}
            p["session"] = f.split("/")[2] if f.startswith(("/home/", "/Users/")) else "root"
            p["ancien"] = bool(p.get("ts") and t - p["ts"] > 3600)
            postes.append(p)
            if p.get("erreurs_24h"):
                alerts.append({"code": "mailbox-erreurs", "severity": "warning", "message": "si-mailbox (%s) : %d erreur(s) sur 24 h" % (p["session"], p["erreurs_24h"])})
            if p["ancien"]:
                alerts.append({"code": "mailbox-silencieux", "severity": "info", "message": "si-mailbox (%s) : pas de résumé depuis plus d'une heure" % p["session"]})
    return {"postes": postes, "alerts": alerts}


if __name__ == "__main__":
    print(json.dumps(collecter(), ensure_ascii=False))
