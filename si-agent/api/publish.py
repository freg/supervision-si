# -*- coding: utf-8 -*-
"""Publication d'un tableau de santé par un agent hôte (livraison #547) --
logique PURE, testée (api/test_si_agent_api.py).

Demandé : « pour ça l'agent mini-PC (sur le réseau du campus) devrait
porter un service web qui le publie ». Le central prépare le contenu (ici
le tableau de santé Nebula de nebula-api, #546) ; l'agent le relève chaque
minute par son canal signé et le sert sur le LAN du site. La clé Nebula ne
quitte jamais le central."""

# #564 : thématique d'un appareil d'après son modèle (page publiée : historique par thématique)
def device_theme(model, dtype=""):
    m = (model or "").upper(); t = (dtype or "").lower()
    if t in ("gateway", "router", "firewall") or any(k in m for k in ("USG", "ATP", "NSG", "SCR", "VPN")):
        return "passerelle"
    if t in ("ap", "accesspoint", "access_point") or any(k in m for k in ("WAX", "WBE", "NWA", "WAC")):
        return "borne"
    if t == "switch" or any(k in m for k in ("GS", "XS", "XGS", "XMG", "MG")):
        return "commutateur"
    return "autre"


PUBLISH_DEFAULTS = {"enabled": False, "port": 8081, "title": "État du réseau", "site_id": "", "hours": 24, "interval_seconds": 60, "hub_url": ""}


def normalize_publish(raw):
    """Réglage `publish` d'un agent : dict complet et borné, ValueError
    si incohérent. None / {} = publication désactivée."""
    out = dict(PUBLISH_DEFAULTS)
    if not raw:
        return out
    if not isinstance(raw, dict):
        raise ValueError("publish : objet attendu")
    out["enabled"] = bool(raw.get("enabled", False))
    port = raw.get("port", out["port"])
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError("publish.port : entier attendu")
    if not 1024 <= port <= 65535:
        raise ValueError("publish.port : entre 1024 et 65535")
    out["port"] = port
    title = raw.get("title", out["title"])
    if not isinstance(title, str) or not title.strip() or len(title) > 80:
        raise ValueError("publish.title : texte de 1 à 80 caractères")
    out["title"] = title.strip()
    site_id = raw.get("site_id", "") or ""
    if not isinstance(site_id, str) or len(site_id) > 64:
        raise ValueError("publish.site_id : texte attendu")
    out["site_id"] = site_id.strip()
    try:
        hours = int(raw.get("hours", out["hours"]))
        interval = int(raw.get("interval_seconds", out["interval_seconds"]))
    except (TypeError, ValueError):
        raise ValueError("publish.hours / interval_seconds : entiers attendus")
    if not 1 <= hours <= 24 * 31:
        raise ValueError("publish.hours : entre 1 et 744")
    if not 30 <= interval <= 3600:
        raise ValueError("publish.interval_seconds : entre 30 et 3600")
    out["hours"], out["interval_seconds"] = hours, interval
    # #559 : lien « tableau de bord complet » vers le hub (avec connexion),
    # ex. https://hub.exemple/?view=nebula -- facultatif, http(s) seulement.
    hub_url = raw.get("hub_url", "") or ""
    if not isinstance(hub_url, str) or len(hub_url) > 200 or (hub_url and not hub_url.startswith(("http://", "https://"))):
        raise ValueError("publish.hub_url : adresse http(s) de 200 caractères max")
    out["hub_url"] = hub_url.strip()
    return out


def board_payload(board, title, at, hub_url="", transitions=None):
    """Ce que l'agent servira (et rien de plus) : phrases et lignes du
    tableau de santé nebula-api (`/health-board` ou `/sites/<id>/health-board`),
    sans identifiants internes ni adresses."""
    sites = board.get("sites") if isinstance(board, dict) and "sites" in board else [board] if isinstance(board, dict) else []
    out_sites = []
    for s in sites:
        if not isinstance(s, dict):
            continue
        out_sites.append({
            "name": s.get("site_name") or "",
            "resume": s.get("resume") or "",
            "phrases": list(s.get("phrases") or []),
            "availability": s.get("availability"),
            "incidents": s.get("incidents"),
            "online": s.get("online"), "total": s.get("total"), "hours": s.get("hours"),
            "devices": [{"name": d.get("name"), "model": d.get("model"), "status": d.get("status"), "since": d.get("since"),
                         "availability": d.get("availability"), "incidents": d.get("incidents"), "theme": device_theme(d.get("model"), d.get("type"))} for d in s.get("devices") or []],
            # #564 : historique des changements d'état sur la fenêtre, avec la thématique de l'appareil
            "events": [{"at": t.get("at"), "name": t.get("name") or t.get("dev_id"), "from": t.get("from_status") or t.get("from"), "to": t.get("to_status") or t.get("to"),
                        "theme": device_theme(next((d.get("model") for d in s.get("devices") or [] if d.get("dev_id") == t.get("dev_id") or d.get("name") == t.get("name")), ""))}
                       for t in (transitions or {}).get(s.get("site_id"), []) if isinstance(t, dict)],
        })
    out = {"title": title, "at": at, "sites": out_sites}
    if hub_url:
        out["hub_url"] = hub_url
    return out
