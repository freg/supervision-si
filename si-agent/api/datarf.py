# -*- coding: utf-8 -*-
"""#806 : tuile « Data RF » -- sondes radio de tous les sites, assemblées depuis les dernières mesures :
plugin:collecte-sondes (agent du mini-PC d'un site qui porte le collecteur de ses sondes) et, pour une sonde enrôlée
directement au hub, plugin:wifi-monitor / plugin:rf-spectrum / plugin:wifi-probe de son propre agent. Pur (testé dans
test_z_datarf.py)."""

DIRECTES = (("plugin:wifi-monitor", "wifi_monitor"), ("plugin:rf-spectrum", "rf_spectrum"), ("plugin:wifi-probe", "wifi_probe"))


def assembler(collectes, directes):
    """collectes : [(agent_id, hostname, at, data)] de plugin:collecte-sondes ; directes : {tâche: [(agent_id, hostname, at, data)]}.
    -> {sondes: [...], constats: [...]} ; une sonde vue des deux façons garde la mesure la plus récente."""
    sondes, constats = {}, []
    for aid, host, at, d in collectes:
        for s in (d or {}).get("sondes") or []:
            if not isinstance(s, dict) or not s.get("sonde"):
                continue
            cle = str(s["sonde"]).lower()
            sondes[cle] = dict(s, via=host or aid, via_agent=aid, recu=at)
        for c in (d or {}).get("alerts") or []:
            if isinstance(c, dict):
                constats.append(dict(c, via=host or aid))
    for tache, cle in DIRECTES:
        for aid, host, at, d in directes.get(tache) or []:
            nom = str(host or aid)
            if tache == "plugin:wifi-probe" and nom.lower() not in sondes:
                continue   # un poste qui n'a que la sonde client (wifi-probe) n'est pas une sonde radio : section Wi-Fi de sa fiche
            e = sondes.setdefault(nom.lower(), {"sonde": nom, "agent_id": aid, "via": None, "recu": at})
            if (e.get(cle + "_at") or "") <= (at or ""):
                e[cle], e[cle + "_at"] = d, at
            if not e.get("via"):
                for c in (d or {}).get("alerts") or []:
                    if isinstance(c, dict):
                        constats.append(dict(c, message="%s : %s" % (nom, c.get("message", "")), via=None))
    return {"sondes": sorted(sondes.values(), key=lambda s: str(s.get("sonde")).lower()), "constats": constats}
