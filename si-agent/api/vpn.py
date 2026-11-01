"""#884 : onglet VPN -- état courant des serveurs WireGuard (sonde wireguard) et historique des connexions.

WireGuard ne journalise pas les connexions : on les reconstitue à partir des relevés successifs (toutes les 2 min).
Un pair est « connecté » tant que sa dernière poignée de main a moins de 3 min ; une session va de la première
poignée de main observée à la dernière avant déconnexion. Volumes = écart des compteurs (remis à zéro si l'interface
redémarre). Portée : la rétention des mesures (SI_AGENT_RETENTION_DAYS, 90 j par défaut).
"""
import json
from datetime import datetime, timedelta, timezone

TASK = "plugin:wireguard"


def _dt(s):
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def sessions(releves):
    """releves = [(agent_id, at, data)] triés par date -> [session] (plus récentes d'abord)."""
    ouvertes, closes, dernier = {}, [], {}

    def fermer(cle, s):
        s["duree_s"] = int((_dt(s["fin"]) - _dt(s["debut"])).total_seconds()) if s.get("fin") and s.get("debut") else None
        closes.append(s)
    for agent_id, at, data in releves:
        vus = set()
        for i in (data or {}).get("interfaces") or []:
            for p in i.get("peers") or []:
                cle = (agent_id, i.get("interface"), p.get("public_key"))
                vus.add(cle)
                dernier[cle] = p
                s = ouvertes.get(cle)
                if p.get("connected"):
                    if s is None:
                        hs = _dt(p.get("handshake_at")) or _dt(at)
                        ouvertes[cle] = {"relais": agent_id, "interface": i.get("interface"), "public_key": p.get("public_key"), "nom": p.get("name") or "",
                                         "origine": p.get("endpoint"), "adresses": p.get("allowed_ips") or [], "debut": _iso(hs), "fin": p.get("handshake_at"),
                                         "rx0": p.get("rx") or 0, "tx0": p.get("tx") or 0, "rx": 0, "tx": 0, "en_cours": True}
                        s = ouvertes[cle]
                    s["fin"] = p.get("handshake_at") or s["fin"]
                    s["nom"] = p.get("name") or s["nom"]
                    rx, tx = p.get("rx") or 0, p.get("tx") or 0
                    s["rx"] = rx - s["rx0"] if rx >= s["rx0"] else rx       # compteurs remis à zéro : on repart
                    s["tx"] = tx - s["tx0"] if tx >= s["tx0"] else tx
                    if p.get("endpoint") and p["endpoint"] != s["origine"]:
                        s["origine"] = p["endpoint"]
                elif s is not None:
                    s["en_cours"] = False
                    fermer(cle, ouvertes.pop(cle))
        for cle in [c for c in ouvertes if c[0] == agent_id and c not in vus]:   # pair retiré de la configuration
            s = ouvertes.pop(cle)
            s["en_cours"] = False
            fermer(cle, s)
    for cle, s in ouvertes.items():
        fermer(cle, s)
    for s in closes:
        s.pop("rx0", None)
        s.pop("tx0", None)
    closes.sort(key=lambda s: s.get("debut") or "", reverse=True)
    return closes


def releves(conn, days=30, now=None):
    now = now or datetime.now(timezone.utc)
    depuis = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    out = []
    for r in conn.execute("SELECT agent_id, at, data FROM measurements WHERE task = ? AND at >= ? ORDER BY at", (TASK, depuis)):
        try:
            d = json.loads(r["data"]) if isinstance(r["data"], str) else (r["data"] or {})
        except (TypeError, ValueError):
            continue
        out.append((r["agent_id"], r["at"], d))
    return out


TASK_SE = "plugin:softether"


def softether(courant):
    """Dernière mesure de chaque agent softether -> (serveurs, sessions au format commun de l'onglet VPN).
    Sessions et échecs viennent directement des journaux de SoftEther (heures du serveur, sans fuseau)."""
    serveurs, sessions = [], []
    for agent_id, hote, at, d in courant:
        d = d or {}
        ss = d.get("sessions") or []
        serveurs.append({"type": "softether", "relais": agent_id, "hote": hote, "at": at, "hubs": d.get("hubs") or [],
                         "en_cours": [s for s in ss if s.get("en_cours")], "echecs": (d.get("echecs") or [])[-200:], "alertes": d.get("alerts") or []})
        for s in ss:
            sessions.append({"type": "softether", "relais": agent_id, "interface": s.get("hub"), "nom": s.get("utilisateur") or "",
                             "public_key": s.get("sid"), "origine": s.get("origine"), "nom_origine": s.get("nom_origine") or "",
                             "adresses": [s["adresse_vpn"]] if s.get("adresse_vpn") else [], "protocole": s.get("protocole") or "",
                             "poste": s.get("poste") or "", "debut": s.get("debut"), "fin": s.get("fin"), "duree_s": s.get("duree_s"),
                             "rx": s.get("recu"), "tx": s.get("emis"), "en_cours": bool(s.get("en_cours"))})
    return serveurs, sessions
