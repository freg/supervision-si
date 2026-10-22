# -*- coding: utf-8 -*-
"""Sonde « orchestration » (#832) : clusters k3s et Nomad de l'hôte -- nœuds, charges suivies (image, répliques, accès,
expiration). Applique la durée de vie (TTL) : une charge posée avec une expiration dépassée est supprimée et listée
dans « expirees ». Privilégiée (kubeconfig root, API Nomad locale). Code commun : si_agent/orchctl.py."""
import json
import os
import subprocess
import sys

for d in ("/opt/si-agent", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")):
    if os.path.isdir(os.path.join(d, "si_agent")):
        sys.path.insert(0, d)
        break
from si_agent import orchctl  # noqa: E402


def _cmd(argv, timeout=60):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=min(timeout, 40))
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(argv, 124, "", "délai dépassé")


def collecter(cmd=_cmd):
    r = orchctl.run(cmd, {"action": "etat", "moteur": "tous"})
    if not r.get("ok"):
        return {"moteurs": {}, "expirees": [], "alerts": [{"code": "orchestration-etat", "severity": "warning", "message": r.get("error")}]}
    res = r["result"]
    alerts = [{"code": "orchestration-ttl", "severity": "info" if x.get("ok") else "warning",
               "message": "%s %s expirée : %s" % (x["moteur"], x["nom"], "supprimée" if x.get("ok") else "suppression en échec (%s)" % x.get("error"))}
              for x in res.get("expirees") or []]
    for m, e in (res.get("etat") or {}).items():
        for n in e.get("noeuds") or []:
            if not n.get("pret"):
                alerts.append({"code": "orchestration-noeud", "severity": "warning", "message": "%s : nœud %s pas prêt" % (m, n.get("nom"))})
    return {"moteurs": res.get("etat") or {}, "expirees": res.get("expirees") or [], "alerts": alerts}


if __name__ == "__main__":
    print(json.dumps(collecter(), ensure_ascii=False))
