# -*- coding: utf-8 -*-
"""Pilotage du réseau du campus (livraison #855) -- logique PURE, testée (tests/test_pilotage.py).

Tableau de bord à deux faces : les MESURES (charge Nebula par borne / SSID / commutateur, veille, sondes netprobe) et
les OUTILS d'action (réglages Nebula -- puissance, plafond de clients, limite de débit par SSID, limite par application
sur le pare-feu, SNMP, miroir de port --, actions par l'API avec chien de garde, bancs de test, boucles).

- BOUCLES DE RÉTROACTION activables à chaud : une condition sur une mesure (seuil tenu pendant N minutes) déclenche
  des actions (notifier, recommander un outil, lancer un banc de test). Mode « conseil » : notifier et recommander,
  le banc est seulement proposé ; mode « auto » : le banc est lancé. Délai entre deux déclenchements, retour à la normale
  journalisé.
- SCÉNARIOS : boucles et bancs prêts à installer (borne saturée, cast dégradé, latence, signal faible, panne).
- BANCS DE TEST : des étapes, chacune avec un nombre de sondes (= clients simulés) et des tâches injectées dans les
  sondes netprobe (flux UDP type cast, flux TCP parallèles, navigation HTTP, DNS, ping) pendant une durée bornée ; les
  tâches d'origine des sondes sont restaurées à la fin ; synthèse par étape et par sonde, verdict par objectif.

Les réglages radio et de débit ne s'écrivent pas par l'OpenAPI Nebula (lecture seule pour l'essentiel) : les outils
correspondants ouvrent Nebula Control Center avec le chemin exact du menu ; seules les actions sur les ports des
commutateurs passent par l'API (module d'action #852)."""
import copy
import re
import time
from datetime import datetime, timezone

NCC = "https://nebula.zyxel.com/"
HIST_MAX = 240                       # 4 h à un relevé par minute
OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b}
MODES = ("conseil", "auto")
TYPES_ACTION = ("notifier", "recommander", "banc")

METRIQUES = {
    "borne.simultanes": {"libelle": "Clients simultanés par borne (max relevé)", "unite": "clients"},
    "borne.clients": {"libelle": "Clients distincts par borne (2 h)", "unite": "clients"},
    "borne.debit_mbps": {"libelle": "Débit moyen par borne (2 h)", "unite": "Mb/s"},
    "ssid.clients": {"libelle": "Clients par SSID (2 h)", "unite": "clients"},
    "commutateur.debit_mbps": {"libelle": "Débit montant du commutateur (2 h)", "unite": "Mb/s"},
    "site.clients_wifi": {"libelle": "Clients Wi-Fi du site (2 h)", "unite": "clients"},
    "site.debit_wifi_mbps": {"libelle": "Débit Wi-Fi du site (2 h)", "unite": "Mb/s"},
    "veille.niveau": {"libelle": "Veille du campus (0 ok, 1 dégradé, 2 panne)", "unite": ""},
    "veille.anomalies": {"libelle": "Vérifications en échec (veille)", "unite": ""},
    "sonde.rssi_dbm": {"libelle": "Signal reçu par la sonde", "unite": "dBm"},
    "sonde.rtt_ms": {"libelle": "Latence (ping) de la sonde", "unite": "ms"},
    "sonde.perte_pct": {"libelle": "Pertes (ping) de la sonde", "unite": "%"},
    "sonde.gigue_ms": {"libelle": "Gigue d'un flux UDP type cast", "unite": "ms"},
    "sonde.perte_udp_pct": {"libelle": "Pertes d'un flux UDP type cast", "unite": "%"},
    "sonde.debit_mbps": {"libelle": "Débit mesuré par la sonde (iperf3)", "unite": "Mb/s"},
    "sonde.http_ms": {"libelle": "Temps de chargement HTTP", "unite": "ms"},
}
NIVEAU_VEILLE = {"ok": 0, "degrade": 1, "panne": 2}

# -- outils d'action (côté droit du tableau de bord) -------------------------------------------------------------
OUTILS = [
    {"id": "ncc-puissance", "groupe": "Radio", "titre": "Puissance d'émission", "type": "lien", "url": NCC,
     "chemin": "Site-wide › Configure › Access points › Radio settings › Maximum output power (par bande, par borne)",
     "description": "De 1 à 30 dBm par bande (2,4 / 5 / 6 GHz), borne par borne, ou préréglage selon la densité de bornes.",
     "doc": "https://community.zyxel.com/en/discussion/14422/nebula-how-to-optimize-wireless-performance-with-deployment-selection-and-maximum-output-power"},
    {"id": "ncc-equilibrage", "groupe": "Radio", "titre": "Plafond de clients par radio (équilibrage)", "type": "lien", "url": NCC,
     "chemin": "Site-wide › Configure › Access points › AP & port settings › Load balancing",
     "description": "Nombre maximal de clients par bande (jusqu'à 127) ; au-delà, connexions retardées, déconnexion des clients inactifs ou mal captés, orientation vers une borne voisine.",
     "doc": "https://download.zyxel.com/Nebula_CC/user_guide_web/NCC_V20.10/h_Tutorials_Setup_WiFiLoadBalancing.html"},
    {"id": "ncc-limite-ssid", "groupe": "Débit", "titre": "Limite de débit par client d'un SSID", "type": "lien", "url": NCC,
     "chemin": "Site-wide › Configure › Access points › SSID advanced settings › Rate limiting",
     "description": "Plafond montant / descendant par client, réglé par SSID (pas par borne : un SSID distinct par niveau, diffusé par étiquette).",
     "doc": "https://community.zyxel.com/en/discussion/33701/i-want-to-configure-different-rate-limits-for-individual-aps"},
    {"id": "ncc-limite-appli", "groupe": "Débit", "titre": "Limite de débit par application (USG FLEX 700H)", "type": "lien", "url": NCC,
     "chemin": "Site-wide › Configure › Firewall › règles d'application (blocage / limite de débit), globales ou par interface",
     "description": "Disponible sur la série H depuis août 2026 ; c'est une limite, pas une garantie de débit.",
     "doc": "https://community.zyxel.com/en/discussion/33844/h-series-application-bandwidth-limit-feature"},
    {"id": "ncc-snmp", "groupe": "Mesures", "titre": "Activer SNMP v2c sur le site", "type": "lien", "url": NCC,
     "chemin": "Site-wide › Configure › General settings › SNMP (V1/V2c, communauté)",
     "description": "Lecture seule ; bornes : canal et stations ; commutateurs et pare-feu : processeur, mémoire, firmware (compteurs de ports selon firmware).",
     "doc": "https://mysupport.zyxel.com/hc/en-us/articles/28553356666642-Nebula-SNMP-Configuration-Monitor-your-Device-via-SNMP"},
    {"id": "ncc-miroir", "groupe": "Mesures", "titre": "Miroir de port vers le capteur de flux", "type": "lien", "url": NCC,
     "chemin": "Site-wide › Configure › Switches › réglages du XS3800-28 (miroir du port du pare-feu vers la 2e carte du capteur)",
     "description": "Copie passive du trafic vers ntopng / Zeek, hors du chemin : si le capteur tombe, le réseau continue. Disponibilité en mode Nebula à vérifier sur ce modèle."},
    {"id": "api-ports", "groupe": "Actions par l'API", "titre": "Ports des commutateurs (API, chien de garde, retour arrière)", "type": "interne",
     "url": "?view=nebula&tab=vlan", "description": "Seules écritures permises par l'OpenAPI Nebula : impact vérifié avant, contrôle après, retour arrière automatique."},
    {"id": "veille", "groupe": "Suivi", "titre": "Veille du campus", "type": "interne", "url": "?view=nebula&tab=veille",
     "description": "Santé des VLAN, des passerelles, des bornes, des postes attendus ; pauses planifiées."},
    {"id": "charge", "groupe": "Suivi", "titre": "Charge détaillée", "type": "interne", "url": "?view=nebula&tab=charge",
     "description": "Clients et débits par borne, SSID, VLAN, commutateur, sur 2 h à 30 jours."},
]
OUTILS_IDS = {o["id"] for o in OUTILS}

# -- bancs et scénarios prêts à installer ----------------------------------------------------------------------
PLANS_MODELES = [
    {"id": "cast", "nom": "Cast vers les écrans (flux UDP type vidéo)", "arret_si_panne": True,
     "description": "Chaque sonde envoie un flux UDP de 8 Mb/s (comme un cast d'écran) et mesure gigue et pertes, avec un ping de fond.",
     "etapes": [{"nom": "Flux cast", "duree_min": 5, "sondes": "toutes", "taches": [
         {"type": "iperf3", "params": {"host": "{serveur}", "udp": True, "bitrate_mbit": 8, "duration": 10}, "every": 30},
         {"type": "ping", "params": {"host": "{cible}", "count": 5}, "every": 10}]}],
     "objectifs": {"perte_udp_pct": 1, "gigue_ms": 30, "rtt_ms": 50}},
    {"id": "charge-progressive", "nom": "Montée en charge progressive (clients simulés)", "arret_si_panne": True,
     "description": "Une sonde, puis la moitié, puis toutes : flux TCP parallèles (téléchargement) et ping, pour voir à partir de quand la latence et le débit se dégradent.",
     "etapes": [{"nom": "1 client", "duree_min": 3, "sondes": 1, "taches": [
                    {"type": "iperf3", "params": {"host": "{serveur}", "reverse": True, "parallel": 2, "duration": 10}, "every": 20},
                    {"type": "ping", "params": {"host": "{cible}", "count": 5}, "every": 10}]},
                {"nom": "Moitié des sondes", "duree_min": 3, "sondes": "moitie", "taches": [
                    {"type": "iperf3", "params": {"host": "{serveur}", "reverse": True, "parallel": 2, "duration": 10}, "every": 20},
                    {"type": "ping", "params": {"host": "{cible}", "count": 5}, "every": 10}]},
                {"nom": "Toutes les sondes", "duree_min": 3, "sondes": "toutes", "taches": [
                    {"type": "iperf3", "params": {"host": "{serveur}", "reverse": True, "parallel": 2, "duration": 10}, "every": 20},
                    {"type": "ping", "params": {"host": "{cible}", "count": 5}, "every": 10}]}],
     "objectifs": {"rtt_ms": 80, "debit_min_mbps": 5}},
    {"id": "navigation", "nom": "Navigation des usagers (HTTP, DNS)", "arret_si_panne": False,
     "description": "Les sondes chargent les sites du campus et résolvent leurs noms régulièrement, comme des usagers qui naviguent.",
     "etapes": [{"nom": "Navigation", "duree_min": 10, "sondes": "toutes", "taches": [
         {"type": "http", "params": {"url": "{url}"}, "every": 20},
         {"type": "dns", "params": {"name": "{nom}"}, "every": 30},
         {"type": "ping", "params": {"host": "{cible}", "count": 3}, "every": 15}]}],
     "objectifs": {"http_ms": 2000, "rtt_ms": 80}},
    {"id": "pointe-amphi", "nom": "Pointe de l'amphithéâtre (pire cas)", "arret_si_panne": True,
     "description": "Toutes les sondes téléchargent en parallèle et envoient un flux cast en même temps : le pire moment d'un cours.",
     "etapes": [{"nom": "Pointe", "duree_min": 5, "sondes": "toutes", "taches": [
         {"type": "iperf3", "params": {"host": "{serveur}", "reverse": True, "parallel": 4, "duration": 15}, "every": 30},
         {"type": "iperf3", "params": {"host": "{serveur}", "port": 5202, "udp": True, "bitrate_mbit": 8, "duration": 10}, "every": 30},
         {"type": "ping", "params": {"host": "{cible}", "count": 5}, "every": 10}]}],
     "objectifs": {"perte_udp_pct": 2, "gigue_ms": 40, "rtt_ms": 100}},
]

SCENARIOS = [
    {"id": "borne-saturee", "nom": "Borne saturée", "description": "Une borne dépasse 25 clients simultanés pendant 5 min : alerte et recommandation de plafonner les clients par radio.",
     "boucles": [{"nom": "Borne saturée", "condition": {"metrique": "borne.simultanes", "cible": "*", "op": ">", "seuil": 25, "duree_min": 5},
                  "actions": [{"type": "notifier"}, {"type": "recommander", "outil": "ncc-equilibrage"}], "delai_min": 60}], "plans": []},
    {"id": "cast-degrade", "nom": "Cast dégradé", "description": "Une sonde voit plus de 1 % de pertes ou plus de 30 ms de gigue sur le flux cast : alerte, recommandation de limiter le débit du SSID invités, banc « cast » proposé (lancé en mode auto).",
     "boucles": [{"nom": "Cast : pertes", "condition": {"metrique": "sonde.perte_udp_pct", "cible": "*", "op": ">", "seuil": 1, "duree_min": 3},
                  "actions": [{"type": "notifier"}, {"type": "recommander", "outil": "ncc-limite-ssid"}, {"type": "banc", "plan": "cast"}], "delai_min": 120},
                 {"nom": "Cast : gigue", "condition": {"metrique": "sonde.gigue_ms", "cible": "*", "op": ">", "seuil": 30, "duree_min": 3},
                  "actions": [{"type": "recommander", "outil": "ncc-limite-ssid"}], "delai_min": 120}], "plans": ["cast"]},
    {"id": "latence", "nom": "Latence élevée", "description": "La latence vue par une sonde dépasse 80 ms pendant 5 min : recommandation de limiter les applications gourmandes sur le pare-feu, banc de montée en charge proposé.",
     "boucles": [{"nom": "Latence élevée", "condition": {"metrique": "sonde.rtt_ms", "cible": "*", "op": ">", "seuil": 80, "duree_min": 5},
                  "actions": [{"type": "notifier"}, {"type": "recommander", "outil": "ncc-limite-appli"}, {"type": "banc", "plan": "charge-progressive"}], "delai_min": 180}],
     "plans": ["charge-progressive"]},
    {"id": "signal-faible", "nom": "Signal faible", "description": "Une sonde reçoit moins de -72 dBm pendant 10 min : recommandation de revoir la puissance des bornes voisines.",
     "boucles": [{"nom": "Signal faible", "condition": {"metrique": "sonde.rssi_dbm", "cible": "*", "op": "<", "seuil": -72, "duree_min": 10},
                  "actions": [{"type": "recommander", "outil": "ncc-puissance"}], "delai_min": 240}], "plans": []},
    {"id": "panne", "nom": "Panne du réseau", "description": "La veille du campus est en panne depuis 2 min : alerte et accès direct à la veille.",
     "boucles": [{"nom": "Panne (veille)", "condition": {"metrique": "veille.niveau", "cible": "*", "op": ">=", "seuil": 2, "duree_min": 2},
                  "actions": [{"type": "notifier"}, {"type": "recommander", "outil": "veille"}], "delai_min": 30}], "plans": []},
    {"id": "pointe", "nom": "Bancs de pointe et de navigation", "description": "Installe les bancs « pointe de l'amphithéâtre » et « navigation des usagers ».",
     "boucles": [], "plans": ["pointe-amphi", "navigation"]},
]

PLAFONDS = {"duree_totale_min": 60, "duree_etape_min": 30, "every_min_s": 10, "iperf_duree_s": 20, "bitrate_mbit": 50, "parallel": 4, "taches": 6}


# -- mesures ---------------------------------------------------------------------------------------------------------
def _num(v):
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def _iso_ts(s):
    try:
        return datetime.strptime(str(s), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def instantane(charge=None, veille=None, sondes=None, noms_sondes=None, maintenant=None):
    """Relevé courant -> {"at": t, "valeurs": {metrique: {cible: valeur}}}.
    charge : réponse de /sites/<id>/charge ; veille : evaluer() de la veille ; sondes : dernières mesures netprobe
    [{agent_id, task, at, ok, data}] ; noms_sondes : {agent_id: libellé}."""
    t = maintenant or time.time()
    V = {k: {} for k in METRIQUES}
    ch = charge or {}
    for b in ch.get("bornes") or []:
        nom = b.get("nom") or b.get("dev_id")
        for cle, src in (("borne.simultanes", "simultanes_max"), ("borne.clients", "clients"), ("borne.debit_mbps", "debit_mbps")):
            v = _num(b.get(src))
            if v is not None:
                V[cle][nom] = v
    for s in ch.get("ssids") or []:
        if _num(s.get("clients")) is not None:
            V["ssid.clients"][s.get("ssid") or "?"] = _num(s["clients"])
    for c in ch.get("commutateurs") or []:
        if _num(c.get("debit_mbps")) is not None and not c.get("erreur"):
            V["commutateur.debit_mbps"][c.get("nom") or c.get("dev_id")] = _num(c["debit_mbps"])
    tot = ch.get("total") or {}
    if _num(tot.get("clients_wifi")) is not None:
        V["site.clients_wifi"]["site"] = _num(tot["clients_wifi"])
    if _num(tot.get("wifi_debit_mbps")) is not None:
        V["site.debit_wifi_mbps"]["site"] = _num(tot["wifi_debit_mbps"])
    if veille and veille.get("etat") in NIVEAU_VEILLE:
        V["veille.niveau"]["campus"] = NIVEAU_VEILLE[veille["etat"]]
        V["veille.anomalies"]["campus"] = float(sum(1 for v in veille.get("verifs") or [] if v.get("statut") in ("ko", "doute")))
    noms = noms_sondes or {}
    for m in sondes or []:
        at = _iso_ts(m.get("at"))
        if at is None or t - at > 900 or not m.get("ok"):   # mesure de plus de 15 min ou en échec : non comptée
            continue
        nom, d, task = noms.get(m.get("agent_id")) or m.get("agent_id"), m.get("data") or {}, str(m.get("task") or "")
        if task == "wifi_link" and _num(d.get("signal_dbm")) is not None:
            V["sonde.rssi_dbm"][nom] = _num(d["signal_dbm"])
        elif task.startswith("ping:"):
            if _num(d.get("rtt_avg_ms")) is not None:
                V["sonde.rtt_ms"][nom] = _num(d["rtt_avg_ms"])
            if _num(d.get("loss_pct")) is not None:
                V["sonde.perte_pct"][nom] = _num(d["loss_pct"])
        elif task.startswith("iperf3:"):
            if d.get("udp") or _num(d.get("jitter_ms")) is not None:
                if _num(d.get("jitter_ms")) is not None:
                    V["sonde.gigue_ms"][nom] = _num(d["jitter_ms"])
                if _num(d.get("loss_pct")) is not None:
                    V["sonde.perte_udp_pct"][nom] = _num(d["loss_pct"])
            else:
                deb = _num(d.get("received_mbps")) or _num(d.get("sent_mbps"))
                if deb is not None:
                    V["sonde.debit_mbps"][nom] = deb
        elif task.startswith("http:") and _num(d.get("time_ms")) is not None:
            V["sonde.http_ms"][nom] = _num(d["time_ms"])
    return {"at": int(t), "valeurs": {k: v for k, v in V.items() if v}}


def ajouter_historique(hist, inst, maxi=HIST_MAX):
    h = [x for x in (hist or []) if x.get("at") != inst["at"]] + [inst]
    return h[-maxi:]


def serie(hist, metrique, cible):
    return [[x["at"], x["valeurs"][metrique][cible]] for x in hist or [] if cible in (x.get("valeurs") or {}).get(metrique, {})]


# -- boucles ---------------------------------------------------------------------------------------------------------
def valider_condition(c):
    c = c or {}
    if c.get("metrique") not in METRIQUES:
        return None, "métrique inconnue (%s)" % ", ".join(METRIQUES)
    if c.get("op") not in OPS:
        return None, "opérateur : %s" % " ".join(OPS)
    seuil = _num(c.get("seuil"))
    if seuil is None:
        return None, "seuil numérique requis"
    try:
        duree = max(0, min(int(c.get("duree_min") or 0), 240))
    except (TypeError, ValueError):
        return None, "durée en minutes"
    return {"metrique": c["metrique"], "cible": str(c.get("cible") or "*")[:80], "op": c["op"], "seuil": seuil, "duree_min": duree}, None


def valider_boucle(b, plans_ids=()):
    b = b or {}
    nom = str(b.get("nom") or "").strip()[:80]
    if not nom:
        return None, "nom requis"
    cond, err = valider_condition(b.get("condition"))
    if err:
        return None, err
    actions = []
    for a in b.get("actions") or []:
        if not isinstance(a, dict) or a.get("type") not in TYPES_ACTION:
            return None, "action : %s" % ", ".join(TYPES_ACTION)
        if a["type"] == "recommander" and a.get("outil") not in OUTILS_IDS:
            return None, "outil recommandé inconnu"
        if a["type"] == "banc" and a.get("plan") not in plans_ids:
            return None, "banc inconnu : %s" % a.get("plan")
        actions.append({k: a[k] for k in ("type", "outil", "plan") if a.get(k)})
    if not actions:
        return None, "au moins une action"
    mode = b.get("mode") if b.get("mode") in MODES else "conseil"
    try:
        delai = max(5, min(int(b.get("delai_min") or 60), 1440))
    except (TypeError, ValueError):
        return None, "délai en minutes"
    return {"nom": nom, "description": str(b.get("description") or "")[:300], "actif": bool(b.get("actif")), "mode": mode,
            "condition": cond, "actions": actions, "delai_min": delai, "scenario": b.get("scenario")}, None


def violations(cond, hist, maintenant=None):
    """Cibles dont la condition est vraie sur TOUS les relevés de la fenêtre [t - durée, t] (fenêtre couverte) ->
    [{"cible", "valeur"}] (valeur du dernier relevé)."""
    if not hist:
        return []
    t = maintenant or hist[-1]["at"]
    debut = t - cond["duree_min"] * 60
    fen = [x for x in hist if debut - 90 <= x["at"] <= t]
    if not fen or (cond["duree_min"] and fen[0]["at"] > debut + 90):   # fenêtre pas encore couverte
        return []
    if not cond["duree_min"]:
        fen = fen[-1:]
    test = OPS[cond["op"]]
    dernier = (fen[-1]["valeurs"] or {}).get(cond["metrique"], {})
    cibles = list(dernier) if cond["cible"] == "*" else [cond["cible"]] if cond["cible"] in dernier else []
    out = []
    for c in cibles:
        vals = [(x["valeurs"].get(cond["metrique"]) or {}).get(c) for x in fen]
        if all(v is not None and test(v, cond["seuil"]) for v in vals):
            out.append({"cible": c, "valeur": dernier[c]})
    return out


def decider(boucle, viol, etat, maintenant=None):
    """-> (evenement, nouvel_etat) ; evenement : "declenche" | "retour" | None. Délai minimal entre deux
    déclenchements ; le retour à la normale n'est signalé qu'après un déclenchement."""
    t = maintenant or time.time()
    e = dict(etat or {})
    if not boucle.get("actif"):
        return None, {"en_cours": False, "dernier": e.get("dernier")}
    if viol:
        if not e.get("en_cours") and t - (e.get("dernier") or 0) >= boucle["delai_min"] * 60:
            e.update(en_cours=True, dernier=t, cibles=[v["cible"] for v in viol])
            return "declenche", e
        if e.get("en_cours"):
            e["cibles"] = [v["cible"] for v in viol]
        return None, e
    if e.get("en_cours"):
        e.update(en_cours=False, retour=t)
        return "retour", e
    return None, e


def actions_a_faire(boucle, viol, plans_ids=()):
    """Ce qu'un déclenchement produit : [{"type", ...}] ; un banc n'est LANCÉ qu'en mode auto (sinon proposé)."""
    out = []
    det = ", ".join("%s = %s" % (v["cible"], round(v["valeur"], 2)) for v in viol)[:300]
    for a in boucle["actions"]:
        if a["type"] == "banc":
            if a.get("plan") in plans_ids:
                out.append({"type": "banc", "plan": a["plan"], "lancer": boucle["mode"] == "auto", "detail": det})
        else:
            out.append(dict(a, detail=det))
    return out


def installer_scenario(sid, boucles, plans, maintenant=None):
    """Ajoute les boucles (désactivées, mode conseil) et bancs d'un scénario sans doublon -> (boucles, plans, ajouts)."""
    sc = next((s for s in SCENARIOS if s["id"] == sid), None)
    if not sc:
        return boucles, plans, None
    t = int(maintenant or time.time())
    plans = list(plans)
    ids_plans = {p["id"] for p in plans}
    ajouts = {"boucles": [], "plans": []}
    for pid in sc["plans"]:
        if pid not in ids_plans:
            p = copy.deepcopy(next(m for m in PLANS_MODELES if m["id"] == pid))
            plans.append(p)
            ids_plans.add(pid)
            ajouts["plans"].append(p["nom"])
    boucles = list(boucles)
    noms = {b["nom"] for b in boucles}
    ids = {b.get("id") for b in boucles}
    for b in sc["boucles"]:
        if b["nom"] in noms:
            continue
        nb, err = valider_boucle(dict(b, actif=False, mode="conseil", scenario=sid, description=sc["description"]), ids_plans)
        if nb:
            k = 0
            while "b%d-%d" % (t, k) in ids:      # identifiant unique même pour deux scénarios installés dans la même seconde
                k += 1
            nb["id"] = "b%d-%d" % (t, k)
            ids.add(nb["id"])
            boucles.append(nb)
            ajouts["boucles"].append(nb["nom"])
    return boucles, plans, ajouts


# -- bancs de test ---------------------------------------------------------------------------------------------------
def valider_plan(p):
    p = p or {}
    pid = re.sub(r"[^a-z0-9-]", "", str(p.get("id") or "").lower())[:40]
    nom = str(p.get("nom") or "").strip()[:100]
    if not pid or not nom:
        return None, "identifiant et nom requis"
    etapes, total = [], 0
    for e in p.get("etapes") or []:
        try:
            duree = int(e.get("duree_min") or 0)
        except (TypeError, ValueError):
            return None, "durée d'étape en minutes"
        if not 1 <= duree <= PLAFONDS["duree_etape_min"]:
            return None, "durée d'étape de 1 à %d min" % PLAFONDS["duree_etape_min"]
        total += duree
        sondes = e.get("sondes", "toutes")
        if not (sondes in ("toutes", "moitie") or (isinstance(sondes, int) and sondes >= 1) or (isinstance(sondes, list) and sondes)):
            return None, "sondes : toutes, moitie, un nombre ou une liste"
        taches = []
        for tch in e.get("taches") or []:
            if tch.get("type") not in ("iperf3", "ping", "http", "dns", "wifi_link"):
                return None, "tâche : iperf3, ping, http, dns, wifi_link"
            pr = dict(tch.get("params") or {})
            if tch["type"] == "iperf3":
                pr["duration"] = max(1, min(int(pr.get("duration") or 10), PLAFONDS["iperf_duree_s"]))
                pr["parallel"] = max(1, min(int(pr.get("parallel") or 1), PLAFONDS["parallel"]))
                if pr.get("udp"):
                    pr["bitrate_mbit"] = max(0.1, min(float(pr.get("bitrate_mbit") or 8), PLAFONDS["bitrate_mbit"]))
            every = max(PLAFONDS["every_min_s"], int(tch.get("every") or 30))
            taches.append({"type": tch["type"], "params": pr, "every": every})
        if not taches or len(taches) > PLAFONDS["taches"]:
            return None, "de 1 à %d tâches par étape" % PLAFONDS["taches"]
        etapes.append({"nom": str(e.get("nom") or "Étape")[:60], "duree_min": duree, "sondes": sondes, "taches": taches})
    if not etapes:
        return None, "au moins une étape"
    if total > PLAFONDS["duree_totale_min"]:
        return None, "durée totale limitée à %d min" % PLAFONDS["duree_totale_min"]
    obj = {k: _num(v) for k, v in (p.get("objectifs") or {}).items() if k in ("perte_udp_pct", "gigue_ms", "rtt_ms", "http_ms", "debit_min_mbps") and _num(v) is not None}
    return {"id": pid, "nom": nom, "description": str(p.get("description") or "")[:400], "etapes": etapes, "objectifs": obj,
            "arret_si_panne": bool(p.get("arret_si_panne", True))}, None


def sondes_etape(etape, dispo):
    """Sondes engagées pour une étape (clients simulés) parmi celles autorisées pour les bancs."""
    dispo = list(dispo or [])
    s = etape.get("sondes", "toutes")
    if s == "toutes":
        return dispo
    if s == "moitie":
        return dispo[:max(1, (len(dispo) + 1) // 2)]
    if isinstance(s, int):
        return dispo[:s]
    return [a for a in s if a in dispo]


def _remplacer(v, reglages, i):
    if isinstance(v, str):
        urls = reglages.get("urls") or []
        url = urls[i % len(urls)] if urls else ""
        nom = re.sub(r"^https?://([^/:]+).*$", r"\1", url) if url else ""
        return v.replace("{serveur}", reglages.get("serveur_iperf") or "").replace("{cible}", reglages.get("cible_ping") or "") \
                .replace("{url}", url).replace("{nom}", nom)
    return v


def taches_banc(etape, reglages, run_id):
    """Tâches netprobe d'une étape, paramètres remplacés ({serveur}, {cible}, {url}, {nom}), marquées du banc ;
    une tâche dont un paramètre reste vide (réglage manquant) est écartée."""
    out = []
    for i, t in enumerate(etape["taches"]):
        p = {k: _remplacer(v, reglages, i) for k, v in t["params"].items()}
        if any(v == "" for v in p.values()):
            continue
        out.append({"type": t["type"], "params": p, "every": t["every"], "banc": run_id})
    return out


def fusionner(taches, ajout):
    """Tâches d'origine de la sonde (sans celles d'un banc précédent) + tâches du banc."""
    return [t for t in (taches or []) if not t.get("banc")] + list(ajout or [])


def restaurer(taches):
    return [t for t in (taches or []) if not t.get("banc")]


def manquants(plan, reglages):
    """Réglages requis par un banc et absents -> liste de libellés."""
    texte = repr(plan["etapes"])
    req = [("{serveur}", "serveur_iperf", "serveur iperf3"), ("{cible}", "cible_ping", "cible du ping"), ("{url}", "urls", "adresses à charger"),
           ("{nom}", "urls", "adresses à charger")]
    out = [lib for motif, cle, lib in req if motif in texte and not reglages.get(cle)]
    if not reglages.get("sondes"):
        out.append("sondes autorisées pour les bancs")
    return sorted(set(out))


def _moy(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def synthese(run, mesures, objectifs=None):
    """mesures : [{agent_id, task, at, ok, data}] de toutes les sondes du banc -> par étape et par sonde : nombre de
    mesures, échecs, moyennes (RTT, pertes, gigue, pertes UDP, débit, HTTP) ; verdict par objectif sur l'ensemble."""
    obj = objectifs or {}
    etapes = []
    glob = {"rtt_ms": [], "perte_udp_pct": [], "gigue_ms": [], "http_ms": [], "debit_mbps": []}
    for i, e in enumerate(run.get("etapes") or []):
        debut, fin = e.get("debut") or 0, e.get("fin") or time.time()
        par = {}
        for m in mesures:
            at = _iso_ts(m.get("at"))
            if at is None or not debut <= at <= fin or m.get("agent_id") not in (e.get("sondes") or []):
                continue
            s = par.setdefault(m["agent_id"], {"mesures": 0, "echecs": 0, "rtt": [], "perte": [], "gigue": [], "perte_udp": [], "debit": [], "http": []})
            s["mesures"] += 1
            if not m.get("ok"):
                s["echecs"] += 1
                continue
            d, task = m.get("data") or {}, str(m.get("task") or "")
            if task.startswith("ping:"):
                s["rtt"].append(_num(d.get("rtt_avg_ms"))); s["perte"].append(_num(d.get("loss_pct")))
            elif task.startswith("iperf3:"):
                if _num(d.get("jitter_ms")) is not None:
                    s["gigue"].append(_num(d.get("jitter_ms"))); s["perte_udp"].append(_num(d.get("loss_pct")))
                else:
                    s["debit"].append(_num(d.get("received_mbps")) or _num(d.get("sent_mbps")))
            elif task.startswith("http:"):
                s["http"].append(_num(d.get("time_ms")))
        lignes = []
        for agent, s in sorted(par.items()):
            l = {"sonde": agent, "mesures": s["mesures"], "echecs": s["echecs"], "rtt_ms": _moy(s["rtt"]), "perte_pct": _moy(s["perte"]),
                 "gigue_ms": _moy(s["gigue"]), "perte_udp_pct": _moy(s["perte_udp"]), "debit_mbps": _moy(s["debit"]), "http_ms": _moy(s["http"])}
            lignes.append(l)
            for k in glob:
                if l.get(k) is not None:
                    glob[k].append(l[k])
        etapes.append({"nom": e.get("nom"), "debut": debut, "fin": e.get("fin"), "sondes": e.get("sondes"), "lignes": lignes,
                       "nebula_simultanes_max": e.get("nebula_simultanes_max")})
    verdicts = []
    for k, lib, sens in (("perte_udp_pct", "pertes du flux cast", "max"), ("gigue_ms", "gigue du flux cast", "max"), ("rtt_ms", "latence", "max"),
                         ("http_ms", "chargement HTTP", "max"), ("debit_min_mbps", "débit par sonde", "min")):
        if k not in obj:
            continue
        vals = glob["debit_mbps" if k == "debit_min_mbps" else k]
        if not vals:
            verdicts.append({"objectif": lib, "seuil": obj[k], "mesure": None, "ok": None})
            continue
        pire = min(vals) if sens == "min" else max(vals)
        verdicts.append({"objectif": lib, "seuil": obj[k], "mesure": pire, "ok": pire >= obj[k] if sens == "min" else pire <= obj[k]})
    res = [v["ok"] for v in verdicts if v["ok"] is not None]
    return {"etapes": etapes, "verdicts": verdicts, "reussi": (all(res) if res else None)}
