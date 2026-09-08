# -*- coding: utf-8 -*-
"""Normalisation des sources vers le modèle commun de Cortex (livraison
#462) -- logique PURE : chaque fonction reçoit la charge utile brute d'une
API existante (si-agent, vigilance, UPS, orchestrateur, netprobe,
network-agent, sauvegardes) et rend des entités, relations et événements
au format commun. Aucun appel réseau ici (voir collectors.py).

Formats communs :
  entité   {key, kind, name, ip, mac, site, origins:[{source, id}], hints:[{role, principle, evidence}]}
  relation {a, b, kind, weight, principle, evidence, source}
  événement {fingerprint, at, source, kind, severity, entity, site, message, raw_ref}
La clé d'entité est stable : "mac:<mac>" si connue, sinon "ip:<ip>", sinon
"name:<nom>" (principes identity-*). Les événements portent une empreinte
(source + kind + entité [+ identifiant source]) : un événement qui se
répète est rafraîchi, jamais dupliqué.
"""
import hashlib
import re

SEV = {"critical": 3, "warning": 2, "info": 1}
GENERIC_NAMES = {"localhost", "pc", "serveur", "server", "unknown", "?", ""}
PORT_ROLES = {"53": "dns", "67": "dhcp", "161": "snmp-manageable", "9100": "imprimante", "631": "imprimante",
              "3306": "base-de-donnees", "5432": "base-de-donnees", "443": "serveur-web", "80": "serveur-web",
              "22": "hote-ssh", "3389": "poste-bureau-a-distance", "445": "partage-fichiers", "389": "annuaire", "636": "annuaire"}


def norm_ip(ip):
    ip = (ip or "").strip()
    return None if not ip or ip.startswith("127.") or ip == "::1" else ip


def norm_mac(mac):
    mac = (mac or "").strip().lower().replace("-", ":")
    return mac if re.match(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", mac) else None


def entity_key(ip=None, mac=None, name=None):
    mac, ip = norm_mac(mac), norm_ip(ip)
    if mac:
        return "mac:" + mac
    if ip:
        return "ip:" + ip
    n = (name or "").strip().lower()
    return "name:" + n if n and n not in GENERIC_NAMES else None


def fingerprint(source, kind, entity, extra=""):
    return hashlib.sha1(("%s|%s|%s|%s" % (source, kind, entity or "", extra)).encode("utf-8")).hexdigest()[:20]


def _ent(key, kind, name=None, ip=None, mac=None, site=None, source=None, sid=None, hints=None):
    return {"key": key, "kind": kind, "name": name, "ip": norm_ip(ip), "mac": norm_mac(mac), "site": site or None,
            "origins": [{"source": source, "id": sid}] if source else [], "hints": hints or []}


# ---------------------------------------------------------------- si-agent
def from_si_agent(fleet, netviews, events, status=None, since=None):
    """`since` (ISO) : les événements historiques du central plus anciens sont
    ignorés (ils ne décrivent plus l'état présent) ; l'état courant (agent
    hors ligne, risques, flotte bloquée) vient de /fleet et /status."""
    ents, rels, evs = [], [], []
    by_agent = {}
    for a in fleet or []:
        key = entity_key(ip=a.get("last_ip"), name=a.get("hostname") or a.get("agent_id"))
        if not key:
            continue
        by_agent[a["agent_id"]] = key
        hints = [{"role": "hote-supervise", "principle": "identity-name", "evidence": "agent si-agent %s" % a["agent_id"]}]
        ents.append(_ent(key, "hote", a.get("hostname") or a.get("agent_id"), a.get("last_ip"), None, a.get("site"), "si-agent", a["agent_id"], hints))
        if a.get("online") == "offline":
            evs.append({"fingerprint": fingerprint("si-agent", "agent-offline", key), "at": a.get("last_seen_at"), "source": "si-agent",
                        "kind": "agent-offline", "severity": "warning", "entity": key, "site": a.get("site"),
                        "message": "agent %s hors ligne (dernier contact %s)" % (a.get("hostname") or a["agent_id"], a.get("last_seen_at") or "?"), "raw_ref": "si-agent:%s" % a["agent_id"]})
        rs = (a.get("risks") or {})
        if rs.get("state") in ("warning", "critical"):
            for r in (rs.get("items") or rs.get("findings") or [])[:20]:
                kind = r.get("kind") or r.get("id") or "risk"
                evs.append({"fingerprint": fingerprint("si-agent", "risk:" + kind, key), "at": a.get("risks_at") or a.get("last_seen_at"), "source": "si-agent",
                            "kind": "risk:" + kind, "severity": r.get("severity") or rs["state"], "entity": key, "site": a.get("site"),
                            "message": r.get("message") or kind, "raw_ref": "si-agent:%s" % a["agent_id"]})
    for nv in netviews or []:
        key = by_agent.get(nv.get("agent_id")) or entity_key(ip=nv.get("last_ip"), name=nv.get("hostname") or nv.get("agent_id"))
        if not key:
            continue
        s = nv.get("summary") or {}
        gw = norm_ip(s.get("default_gateway"))
        if gw:
            gk = "ip:" + gw
            ents.append(_ent(gk, "passerelle", None, gw, None, nv.get("site"), "si-agent", "gateway-of:%s" % nv.get("agent_id"),
                             [{"role": "passerelle", "principle": "gateway-of", "evidence": "passerelle par défaut de %s" % (nv.get("hostname") or nv.get("agent_id"))}]))
            rels.append({"a": gk, "b": key, "kind": "gateway_of", "weight": 1.0, "principle": "gateway-of",
                         "evidence": "ip route de %s (%s)" % (nv.get("hostname") or nv.get("agent_id"), s.get("default_gateway_state") or "?"), "source": "si-agent"})
        for n in nv.get("neighbors") or []:
            nk = entity_key(ip=n.get("ip"), mac=n.get("mac"))
            if nk and nk != key:
                ents.append(_ent(nk, "equipement", None, n.get("ip"), n.get("mac"), nv.get("site"), "si-agent", "neighbor"))
                rels.append({"a": key, "b": nk, "kind": "neighbor", "weight": 0.3, "principle": "identity-mac", "evidence": "voisin ARP/NDP", "source": "si-agent"})
        for p in s.get("peers") or []:
            pk = entity_key(ip=p.get("ip"))
            if pk and pk != key and not p.get("local"):
                ents.append(_ent(pk, "pair", None, p.get("ip"), None, None, "si-agent", "peer"))
                rels.append({"a": key, "b": pk, "kind": "talks_to", "weight": min(1.0, (p.get("connections") or 1) / 20.0), "principle": "identity-ip",
                             "evidence": "%s connexion(s) %s" % (p.get("connections"), ", ".join(p.get("ports") or [])[:60]), "source": "si-agent"})
    for e in events or []:
        key = by_agent.get(e.get("agent_id")) or (("name:" + str(e["agent_id"]).lower()) if e.get("agent_id") else "name:si-agent-central")
        if e.get("severity") not in ("warning", "critical"):
            continue
        if since and (e.get("at") or "") < since:
            continue
        if e.get("kind") in ("agent-offline", "agent-online", "fleet-unblocked", "agent-unblocked"):
            continue  # transitions : l'état courant est déjà porté par /fleet et /status
        evs.append({"fingerprint": fingerprint("si-agent", e.get("kind"), key, str(e.get("id"))), "at": e.get("at"), "source": "si-agent",
                    "kind": e.get("kind") or "event", "severity": e.get("severity"), "entity": key, "site": e.get("site"),
                    "message": e.get("message") or "", "raw_ref": "si-agent:event:%s" % e.get("id")})
    if status and status.get("fleet_blocked"):
        evs.append({"fingerprint": fingerprint("si-agent", "fleet-blocked", "central"), "at": status.get("fleet_blocked_at"), "source": "si-agent",
                    "kind": "fleet-blocked", "severity": "warning", "entity": "name:si-agent-central", "site": None,
                    "message": "sondes de la flotte bloquées (%s)" % (status.get("fleet_block_reason") or "coupe-circuit"), "raw_ref": "si-agent:status"})
    return ents, rels, evs


# ---------------------------------------------------------------- vigilance
SEV_ALIAS = {"high": "critical", "critical": "critical", "medium": "warning", "warning": "warning", "low": "info", "info": "info"}


def from_vigilance(signals):
    ents, evs = [], []
    for s in signals or []:
        label = s.get("device_label") or ""
        ip = label if re.match(r"^\d+\.\d+\.\d+\.\d+$", label) else None
        key = entity_key(mac=s.get("device_mac"), ip=ip, name=label)
        if not key:
            continue
        ents.append(_ent(key, "equipement", None if ip else label, ip, s.get("device_mac"), None, "vigilance", s.get("device_mac")))
        evs.append({"fingerprint": fingerprint("vigilance", s.get("signal_type"), key), "at": s.get("detected_at"), "source": "vigilance",
                    "kind": "signal:" + (s.get("signal_type") or "?"), "severity": SEV_ALIAS.get(str(s.get("severity")).lower(), "info"), "entity": key, "site": None,
                    "message": s.get("detail") or s.get("signal_type") or "", "raw_ref": "vigilance:%s" % s.get("id")})
    return ents, [], evs


# ---------------------------------------------------------------- UPS
def from_ups(devices):
    ents, rels, evs = [], [], []
    for d in devices or []:
        key = entity_key(ip=d.get("host"), name=d.get("name"))
        if not key:
            continue
        ents.append(_ent(key, "onduleur", d.get("name"), d.get("host"), None, d.get("site"), "ups", d.get("id"),
                         [{"role": "onduleur", "principle": "identity-ip", "evidence": "déclaré dans la tuile UPS"}]))
        if d.get("site"):
            rels.append({"a": key, "b": "site:" + d["site"].strip().lower(), "kind": "powers_site", "weight": 0.5, "principle": "ups-powers-site",
                         "evidence": "onduleur du site %s" % d["site"], "source": "ups"})
        for a in d.get("active_alerts") or []:
            evs.append({"fingerprint": fingerprint("ups", a.get("kind"), key), "at": a.get("opened_at"), "source": "ups",
                        "kind": "ups:" + (a.get("kind") or "alerte"), "severity": a.get("severity") or "warning", "entity": key, "site": d.get("site"),
                        "message": a.get("message") or a.get("kind") or "", "raw_ref": "ups:alert:%s" % a.get("id")})
        if d.get("stale"):
            evs.append({"fingerprint": fingerprint("ups", "stale", key), "at": d.get("last_polled_at"), "source": "ups", "kind": "ups:stale",
                        "severity": "warning", "entity": key, "site": d.get("site"), "message": d["stale"], "raw_ref": "ups:%s" % d.get("id")})
    return ents, rels, evs


# ---------------------------------------------------------------- orchestrateur
def from_orchestrator(suggestions):
    ents, evs = [], []
    for s in suggestions or []:
        if s.get("status") not in (None, "open"):
            continue
        key = entity_key(mac=s.get("subject_key"), ip=s.get("subject_key"), name=s.get("subject_key"))
        if not key:
            continue
        ents.append(_ent(key, "equipement", None, s.get("subject_key") if norm_ip(s.get("subject_key")) else None, s.get("subject_key"), None, "netmap-orchestrator", s.get("id")))
        evs.append({"fingerprint": fingerprint("netmap-orchestrator", s.get("rule_name"), key), "at": s.get("last_detected_at") or s.get("first_detected_at"),
                    "source": "netmap-orchestrator", "kind": "suggestion:" + (s.get("rule_name") or "?"), "severity": s.get("severity") or "info", "entity": key,
                    "site": None, "message": s.get("message") or "", "raw_ref": "netmap-orchestrator:%s" % s.get("id")})
    return ents, [], evs


# ---------------------------------------------------------------- netprobe
def from_netprobe(targets, latest, results):
    ents, rels, evs = [], [], []
    by_target = {}
    for t in targets or []:
        key = entity_key(ip=t.get("ip_address"), name=t.get("label"))
        if not key:
            continue
        by_target[t.get("id")] = key
        ents.append(_ent(key, "cible", t.get("label"), t.get("ip_address"), None, t.get("site"), "netprobe", t.get("id")))
        rels.append({"a": "name:netprobe", "b": key, "kind": "watches", "weight": 0.2, "principle": "probe-watches", "evidence": "cible %s" % (t.get("label") or t.get("ip_address")), "source": "netprobe"})
    for s in latest or []:
        key = by_target.get(s.get("target_id"))
        if key and s.get("success") in (0, False):
            evs.append({"fingerprint": fingerprint("netprobe", "unreachable", key), "at": s.get("sampled_at"), "source": "netprobe", "kind": "probe:unreachable",
                        "severity": "critical", "entity": key, "site": None, "message": s.get("error") or "cible injoignable", "raw_ref": "netprobe:sample:%s" % s.get("id")})
        elif key and (s.get("packet_loss_percent") or 0) > 0:
            evs.append({"fingerprint": fingerprint("netprobe", "loss", key), "at": s.get("sampled_at"), "source": "netprobe", "kind": "probe:loss",
                        "severity": "warning", "entity": key, "site": None, "message": "perte %s %%" % s.get("packet_loss_percent"), "raw_ref": "netprobe:sample:%s" % s.get("id")})
    for r in results or []:
        key = by_target.get(r.get("target_id"))
        if key and r.get("severity") in ("warning", "critical"):
            evs.append({"fingerprint": fingerprint("netprobe", r.get("analyzer_name") or "analysis", key), "at": r.get("created_at") or r.get("detected_at"), "source": "netprobe",
                        "kind": "analysis:" + (r.get("analyzer_name") or "?"), "severity": r["severity"], "entity": key, "site": None, "message": r.get("message") or "", "raw_ref": "netprobe:result:%s" % r.get("id")})
    return ents, rels, evs


# ---------------------------------------------------------------- network-agent
def from_network_agent(sites, devices, links_by_segment):
    """sites: /sites (sites + segments) ; devices: /devices (liste) ; links_by_segment: {segment_id: [liens]}"""
    ents, rels = [], []
    seg_site = {}
    for s in sites or []:
        for seg in s.get("segments") or []:
            seg_site[seg.get("id")] = s.get("name")
    by_id = {}
    for d in devices or []:
        key = entity_key(ip=d.get("ip_address"), mac=d.get("mac_address"), name=d.get("hostname"))
        if not key:
            continue
        by_id[d.get("id")] = key
        hints = []
        if d.get("role_hint"):
            hints.append({"role": "passerelle", "principle": "relay-gateway", "evidence": "%s (%s relais)" % (d["role_hint"], d.get("external_relay_count") or "?")})
        for svc in d.get("services") or []:
            port = str(svc.get("port") or svc)
            if port in PORT_ROLES:
                hints.append({"role": PORT_ROLES[port], "principle": "serves-port", "evidence": "sert le port %s" % port})
        ents.append(_ent(key, "equipement", d.get("hostname"), d.get("ip_address"), d.get("mac_address"), seg_site.get(d.get("network_segment_id")), "network-agent", d.get("id"), hints))
    for seg_id, links in (links_by_segment or {}).items():
        for l in links or []:
            a, b = by_id.get(l.get("device_a_id")), by_id.get(l.get("device_b_id"))
            if a and b and a != b:
                rels.append({"a": a, "b": b, "kind": "flow", "weight": min(1.0, (l.get("bytes_total") or 0) / 1e7), "principle": "identity-mac",
                             "evidence": "%s octets échangés" % (l.get("bytes_total") or 0), "source": "network-agent"})
    return ents, rels, []


# ---------------------------------------------------------------- sauvegardes
def from_backups(status):
    if not status or not status.get("last") or status["last"].get("rc") == 0:
        return [], [], []
    last = status["last"]
    return [], [], [{"fingerprint": fingerprint("backup", "failed", "name:hub", last.get("started_at") or ""), "at": last.get("ended_at"), "source": "backup-restore",
                     "kind": "backup:failed", "severity": "warning", "entity": "name:hub", "site": None,
                     "message": "sauvegarde %s du hub échouée" % last.get("kind"), "raw_ref": "backup-restore:last"}]


# ---------------------------------------------------------------- fusion
def alias_map(entities):
    """Consolidation inter-clés (principes identity-*) : une entité connue par
    sa MAC absorbe les clés « ip:<même ip> » et « name:<même nom> » ; une
    entité connue par IP absorbe « name:<même nom> ». -> {clé: clé canonique}"""
    by_ip, by_name, keys = {}, {}, {e["key"] for e in entities}
    for e in entities:
        if e["key"].startswith("mac:"):
            if e.get("ip"):
                by_ip.setdefault(e["ip"], e["key"])
            if e.get("name") and e["name"].strip().lower() not in GENERIC_NAMES:
                by_name.setdefault(e["name"].strip().lower(), e["key"])
    for e in entities:
        if e["key"].startswith("ip:") and e.get("name") and e["name"].strip().lower() not in GENERIC_NAMES:
            by_name.setdefault(e["name"].strip().lower(), e["key"])
    alias = {}
    for e in entities:
        k = e["key"]
        if k.startswith("ip:") and by_ip.get(k[3:]) and by_ip[k[3:]] != k:
            alias[k] = by_ip[k[3:]]
        elif k.startswith("name:") and by_name.get(k[5:]) and by_name[k[5:]] != k:
            alias[k] = by_name[k[5:]]
    # fermeture (name -> ip -> mac)
    for k in list(alias):
        while alias[k] in alias and alias[alias[k]] != alias[k]:
            alias[k] = alias[alias[k]]
    return alias


def apply_aliases(entities, relations, events, alias):
    """Réécrit les clés absorbées partout ; les entités absorbées fusionnent."""
    if not alias:
        return entities, relations, events
    for e in entities:
        if e["key"] in alias:
            e["key"] = alias[e["key"]]
    for r in relations:
        r["a"] = alias.get(r["a"], r["a"]); r["b"] = alias.get(r["b"], r["b"])
    for ev in events:
        if ev.get("entity") in alias:
            ev["entity"] = alias[ev["entity"]]
    return entities, relations, events


def merge_entities(entities):
    """Fusionne par clé ; noms, IP, MAC, site pris quand manquants ; origines
    et indices cumulés (sans doublon)."""
    out = {}
    for e in entities:
        cur = out.get(e["key"])
        if not cur:
            out[e["key"]] = {**e, "origins": list(e["origins"]), "hints": list(e["hints"])}
            continue
        for f in ("name", "ip", "mac", "site"):
            if not cur.get(f) and e.get(f):
                cur[f] = e[f]
        if cur["kind"] in ("equipement", "pair") and e["kind"] not in ("equipement", "pair"):
            cur["kind"] = e["kind"]
        for o in e["origins"]:
            if o not in cur["origins"]:
                cur["origins"].append(o)
        for h in e["hints"]:
            if h not in cur["hints"]:
                cur["hints"].append(h)
    return list(out.values())


def role_hypotheses(entity, feedback=None):
    """Rôles pondérés d'une entité : un indice = un principe ; plusieurs
    indices concordants renforcent. -> [{role, confidence, evidence:[...], principles:[...]}]"""
    from principles import evaluate
    by_role = {}
    for h in entity.get("hints") or []:
        r = by_role.setdefault(h["role"], {"role": h["role"], "evidence": [], "principles": [], "conf": 0.0})
        p = evaluate(h["principle"], feedback)["effective"]
        r["evidence"].append(h["evidence"])
        if h["principle"] not in r["principles"]:
            r["principles"].append(h["principle"])
        r["conf"] = 1 - (1 - r["conf"]) * (1 - p)   # indices indépendants
    return sorted(({"role": r["role"], "confidence": round(r["conf"], 2), "evidence": r["evidence"], "principles": r["principles"]} for r in by_role.values()),
                  key=lambda x: -x["confidence"])


# ================================================================ étape 2 (#463)
from oui import vendor_of  # noqa: E402

NEBULA_TYPE_ROLES = {"ap": "borne-wifi", "access point": "borne-wifi", "switch": "switch", "gateway": "routeur", "router": "routeur", "firewall": "pare-feu", "security gateway": "pare-feu"}


def vendor_hint(mac):
    """Indice de rôle depuis l'OUI (principe oui-vendor) ; None si constructeur
    inconnu ou généraliste."""
    vendor, family = vendor_of(mac)
    if not vendor or not family:
        return None, vendor
    return {"role": family, "principle": "oui-vendor", "evidence": "constructeur %s (OUI)" % vendor}, vendor


def with_vendor_hints(entities):
    """Ajoute à chaque entité connue par MAC son constructeur et, s'il est
    parlant, l'indice de rôle correspondant."""
    for e in entities:
        if e.get("mac"):
            hint, vendor = vendor_hint(e["mac"])
            if vendor:
                e["vendor"] = vendor
            if hint and hint not in e["hints"]:
                e["hints"].append(hint)
    return entities


def from_classifier(results):
    """classifier-api /results : {input_text, category, confirmed} -> indices de rôle par nom."""
    ents = []
    for r in results or []:
        key = entity_key(name=r.get("input_text"))
        if not key or not r.get("category"):
            continue
        ents.append(_ent(key, "equipement", r.get("input_text"), None, None, None, "classifier", r.get("id"),
                         [{"role": r["category"], "principle": "name-class", "evidence": "classification %s du nom « %s »" % ("confirmée" if r.get("confirmed") else "automatique", r.get("input_text"))}]))
    return ents, [], []


def from_nebula(devices, clients):
    """Référentiel Nebula importé : appareils (type, modèle, site) et clients (attachés à un appareil)."""
    ents, rels = [], []
    by_name = {}
    for d in devices or []:
        key = entity_key(mac=d.get("mac_address"), name=d.get("name"))
        if not key:
            continue
        typ = (d.get("device_type") or "").strip().lower()
        role = NEBULA_TYPE_ROLES.get(typ) or ("equipement-reseau" if typ else None)
        hints = [{"role": role, "principle": "referential", "evidence": "Nebula : %s %s" % (d.get("device_type") or "appareil", d.get("model") or "")}] if role else []
        e = _ent(key, "equipement-reseau", d.get("name"), None, d.get("mac_address"), d.get("site"), "nebula", d.get("id"), hints)
        e["model"] = d.get("model")
        ents.append(e)
        if d.get("name"):
            by_name[d["name"].strip().lower()] = key
    for c in clients or []:
        key = entity_key(mac=c.get("mac_address"), ip=c.get("ipv4_address"), name=c.get("name"))
        if not key:
            continue
        e = _ent(key, "equipement", c.get("name"), c.get("ipv4_address"), c.get("mac_address"), None, "nebula", c.get("id"))
        if c.get("manufacturer"):
            e["vendor"] = c["manufacturer"]
        if c.get("os"):
            e["os"] = c["os"]
        ents.append(e)
        up = by_name.get((c.get("connected_to") or "").strip().lower())
        if up:
            rels.append({"a": up, "b": key, "kind": "uplink", "weight": 0.8, "principle": "attached-to",
                         "evidence": "client attaché à %s (%s)" % (c.get("connected_to"), c.get("ssid_name") or c.get("band") or "Nebula"), "source": "nebula"})
    return ents, rels, []


def from_ipam(entries):
    """ipam-api /ip_list : nom, description, sous-réseau, état -- déclarations d'administrateur."""
    ents = []
    for r in entries or []:
        key = entity_key(mac=r.get("mac"), ip=r.get("ip"), name=r.get("hostname"))
        if not key:
            continue
        e = _ent(key, "equipement", r.get("hostname"), r.get("ip"), r.get("mac"), None, "ipam", r.get("id"))
        if r.get("description"):
            e["description"] = r["description"]
        if r.get("subnet"):
            e["subnet"] = r["subnet"]
        ents.append(e)
    return ents, [], []


def services_hints(devices, services_by_device):
    """network-agent /devices/services?segment_id : {device_id: [{protocol, port}]} -> indices serves-port."""
    out = {}
    for d in devices or []:
        for svc in (services_by_device or {}).get(str(d.get("id"))) or (services_by_device or {}).get(d.get("id")) or []:
            port = str(svc.get("port"))
            if port in PORT_ROLES:
                out.setdefault(d.get("id"), []).append({"role": PORT_ROLES[port], "principle": "serves-port", "evidence": "sert %s/%s (%s paquets)" % (svc.get("protocol"), port, svc.get("packet_count") or "?")})
    return out


def routes_from_netviews(netviews, by_agent=None):
    """Table de routes (principe route-known) : par hôte, la route par défaut,
    les sous-réseaux attachés et les sous-réseaux joignables via une autre passerelle."""
    out = []
    for nv in netviews or []:
        key = (by_agent or {}).get(nv.get("agent_id")) or entity_key(ip=nv.get("last_ip"), name=nv.get("hostname") or nv.get("agent_id"))
        if not key:
            continue
        s = nv.get("summary") or {}
        if s.get("default_gateway"):
            out.append({"host": key, "destination": "default", "via": s["default_gateway"], "kind": "default", "state": s.get("default_gateway_state"), "source": "si-agent"})
        for cidr in s.get("attached_subnets") or []:
            out.append({"host": key, "destination": cidr, "via": None, "kind": "attached", "state": "direct", "source": "si-agent"})
        for r in s.get("reachable_subnets") or []:
            if isinstance(r, dict):
                out.append({"host": key, "destination": r.get("cidr") or r.get("destination"), "via": r.get("via") or r.get("gateway"), "kind": "reachable", "state": None, "source": "si-agent"})
            elif isinstance(r, str):
                out.append({"host": key, "destination": r, "via": None, "kind": "reachable", "state": None, "source": "si-agent"})
    return out
