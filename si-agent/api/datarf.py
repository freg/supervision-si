# -*- coding: utf-8 -*-
"""#806 : tuile « Data RF » -- sondes radio de tous les sites, assemblées depuis les dernières mesures :
plugin:collecte-sondes (agent du mini-PC d'un site qui porte le collecteur de ses sondes) et, pour une sonde enrôlée
directement au hub, plugin:wifi-monitor / plugin:rf-spectrum / plugin:wifi-probe de son propre agent. Pur (testé dans
test_z_datarf.py)."""

DIRECTES = (("plugin:wifi-monitor", "wifi_monitor"), ("plugin:rf-spectrum", "rf_spectrum"), ("plugin:wifi-probe", "wifi_probe"),
            ("plugin:path-probe", "path_probe"))   # #811 : chemin, pour la colonne LAN


def assembler(collectes, directes, maintenant=None):
    """collectes : [(agent_id, hostname, at, data)] de plugin:collecte-sondes ; directes : {tâche: [(agent_id, hostname, at, data)]}.
    -> {sondes: [...], constats: [...]} ; une sonde vue des deux façons garde la mesure la plus récente.
    maintenant (ISO, optionnel) : borne d'ancienneté -- une mesure directe antérieure est ignorée."""
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
    collecteurs = {str(aid) for aid, _h, _at, _d in collectes}   # #812 : l'hôte d'un collecteur n'est pas une sonde
    for tache, cle in DIRECTES:
        for aid, host, at, d in directes.get(tache) or []:
            nom = str(host or aid)
            if str(aid) in collecteurs or (maintenant and at and at < maintenant):
                continue   # mesure d'un collecteur, ou trop ancienne (sonde désactivée depuis)
            if tache in ("plugin:wifi-probe", "plugin:path-probe") and nom.lower() not in sondes:
                continue   # un poste qui n'a que la sonde client (wifi-probe) n'est pas une sonde radio : section Wi-Fi de sa fiche
            e = sondes.setdefault(nom.lower(), {"sonde": nom, "agent_id": aid, "via": None, "recu": at})
            if (e.get(cle + "_at") or "") <= (at or ""):
                e[cle], e[cle + "_at"] = d, at
            if not e.get("via"):
                for c in (d or {}).get("alerts") or []:
                    if isinstance(c, dict):
                        constats.append(dict(c, message="%s : %s" % (nom, c.get("message", "")), via=None))
    return {"sondes": sorted(sondes.values(), key=lambda s: str(s.get("sonde")).lower()), "constats": constats}


ROLES = ("client", "moniteur", "inactive")


def preparer_config(cfg, reveler):
    """#807 : configuration radio saisie dans la tuile -> (params de wifi_config, réglage à mémoriser sans clé, erreur).
    cfg = {interfaces: {nom: rôle}, ssids: [{ssid, acces?, actif, iface?}]} ; la clé de chaque SSID vient du coffre
    (accès nommé `acces`, son mot de passe) ; un SSID sans accès est un réseau ouvert. reveler(nom) -> {password}."""
    inter = {str(k): v for k, v in ((cfg or {}).get("interfaces") or {}).items() if v in ROLES}
    ssids, memo = [], []
    for s in (cfg or {}).get("ssids") or []:
        if not isinstance(s, dict) or not str(s.get("ssid") or "").strip():
            continue
        ssid, acces = str(s["ssid"]).strip(), str(s.get("acces") or "").strip()
        psk = ""
        if acces and s.get("actif", True):
            try:
                psk = (reveler(acces) or {}).get("password") or ""
            except Exception as e:  # noqa: BLE001 -- le message du coffre suffit
                return None, None, "SSID « %s » : %s" % (ssid, e)
            if not psk:
                return None, None, "SSID « %s » : l'accès « %s » du coffre n'a pas de mot de passe" % (ssid, acces)
        ssids.append({"ssid": ssid, "psk": psk, "actif": bool(s.get("actif", True)), "iface": str(s.get("iface") or "")})
        memo.append({"ssid": ssid, "acces": acces, "actif": bool(s.get("actif", True)), "iface": str(s.get("iface") or "")})
    return {"action": "appliquer", "interfaces": inter, "ssids": ssids}, {"interfaces": inter, "ssids": memo}, None


def commande(sonde, via_agent, agent_id, params):
    """-> (agent qui reçoit la commande, type, params) : par le collecteur du site (via_agent) ou directement."""
    if via_agent:
        return via_agent, "collecteur", {"action": "commande", "sonde": sonde, "type": "wifi_config", "params": params, "attendre_s": 90}
    return agent_id, "wifi_config", params
