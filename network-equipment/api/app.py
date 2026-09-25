# -*- coding: utf-8 -*-
"""network-equipment-api (livraison #506) -- facette « équipements
réseau » de l'exploration : QUI sont les routeurs, switchs et autres
équipements de niveau 2/3 du LAN (constructeur, modèle, système,
génération), d'après TOUTES les sources déjà présentes dans le hub, et
QUOI relever dessus (profils de supervision génériques par constructeur).

Demandé : « identifier côté LAN la marque et le modèle d'un routeur
(récents = MikroTik, les autres datent de l'origine de la boucle locale
fibre, ~25 ans) ; à partir de la base Zenoss / SNMP récupérer ces infos
et celles des switchs/équipements niveau 2 ; préparer des interfaces de
supervision génériques Cisco, HP… ».

Sources fusionnées (identify.merge, logique pure testée) :
  - exploration réseau (network-agent) : MAC -> constructeur (OUI),
    dernière IP, nom résolu, rôle observé, services en écoute ;
  - SNMP via snmp-api (une seule implémentation pysnmp dans le projet) :
    sysDescr / sysObjectID / sysName, ENTITY-MIB (modèle, série), voisins
    LLDP et CDP, table des adresses MAC (BRIDGE-MIB) ;
  - Zenoss 2.5 : export zendmd (JSON complet) ou CSV de la liste ;
  - choix manuels de l'utilisateur (dernier mot).

Routes :
  GET  /health, /status
  GET  /equipment[?kind=&vendor=&generation=&q=&site=]   GET/PUT/DELETE /equipment/<id>   POST /equipment
  POST /import/network-agent            tire /devices de network-agent (site optionnel)
  POST /import/zenoss                   fichier (multipart `file`) ou JSON {content|devices, dry_run}
  POST /identify/preview                {sys_descr, sys_object_id, mac, zenoss_class} -> identification, rien n'est stocké
  POST /equipment/<id>/identify         {target_id | credential | community, port?, neighbors?, fdb?}
  POST /identify/batch                  {ids: [...], …} au plus 50, séquentiel
  POST /equipment/<id>/poll             relevé du profil de supervision
  GET  /profiles, /equipment/<id>/profile
  GET  /neighbors[?equipment_id=], /equipment/<id>/fdb, /topology, /where-is?mac=
  POST /oui/import (fichier IEEE)       GET /oui/lookup?mac=

Sécurité : aucune communauté SNMP n'est stockée ici -- `target_id`
(cible enregistrée dans snmp-api), `credential` (nom d'un accès de
genre « snmp » du coffre credentials-api, révélé par jeton interne,
mot de passe = communauté) ou `community` ponctuelle jamais conservée
ni journalisée. Les valeurs relevées ne contiennent jamais de secret.
"""
import json
import logging
import os
import time

import requests
from flask import Flask, jsonify, request

import identify
import oui as oui_mod
import profiles
import snmp_tables
import store
import zenoss_import

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("network-equipment")

DATA_DIR = os.environ.get("NETWORK_EQUIPMENT_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "network-equipment.db")
OUI_PATH = os.path.join(DATA_DIR, "oui.csv")
SNMP_API_URL = os.environ.get("SNMP_API_INTERNAL_URL", "").rstrip("/")
NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/")
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "").rstrip("/")
CREDENTIALS_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "").strip()
if CREDENTIALS_TOKEN == "change-me":
    CREDENTIALS_TOKEN = ""
SNMP_TIMEOUT = int(os.environ.get("NETWORK_EQUIPMENT_SNMP_TIMEOUT", "5"))
MAX_WALK_ROWS = int(os.environ.get("NETWORK_EQUIPMENT_MAX_WALK_ROWS", "4000"))
MAX_UPLOAD = 20 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD
os.makedirs(DATA_DIR, exist_ok=True)
store.ensure_schema(DB_PATH)
OUI = oui_mod.OuiTable(OUI_PATH)

try:
    from version_endpoint import register_version_route
    register_version_route(app, "network-equipment")
except Exception:  # noqa: BLE001 -- shared/ absent en test local
    pass

# A1 (#620) : périmètre de site par groupe Keycloak (SITE_SCOPE_GROUPS) -- sans jeton rien ne change
try:
    import site_scope as _site_scope
    _site_scope.install(app, os.environ.get("SITE_SCOPE_JWKS_URL") or "%s/realms/%s/protocol/openid-connect/certs" % (
        os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth"), os.environ.get("KEYCLOAK_REALM", "supervision-si")),
        resolve_site=None, what="network-equipment")
except ImportError:
    _site_scope = None


# ---------------------------------------------------------------- utilitaires

def _db():
    return store.connect(DB_PATH)


def evidence_of(row):
    """Preuves stockées -> entrée de identify.merge."""
    return {
        "mac": row.get("mac"),
        "oui": {"vendor": row.get("oui_vendor"), "category": row.get("oui_category")} if (row.get("oui_vendor") or row.get("oui_category")) else None,
        "sys_descr": row.get("sys_descr"), "sys_object_id": row.get("sys_object_id"), "sys_name": row.get("sys_name"),
        "entity": row.get("entity") or {},
        "zenoss": row.get("zenoss") or {},
        "role_hint": row.get("role_hint"), "ports": row.get("ports") or [], "hostname": row.get("hostname"),
        "manual": row.get("manual") or {},
    }


def reidentify(conn, equipment_id, source, extra=None):
    row = store.get(conn, equipment_id)
    ident = identify.merge(evidence_of(row))
    prof = profiles.match_profile(ident)
    fields = dict(extra or {})
    fields["profile_id"] = prof["id"]
    store.set_identification(conn, equipment_id, ident, source, fields)
    return ident


def _snmp_post(path, payload, timeout):
    if not SNMP_API_URL:
        raise RuntimeError("snmp-api non configuré (SNMP_API_INTERNAL_URL)")
    try:
        resp = requests.post(SNMP_API_URL + path, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError("snmp-api injoignable (%s)" % exc.__class__.__name__)
    try:
        body = resp.json()
    except ValueError:
        raise RuntimeError("snmp-api : réponse illisible (HTTP %s)" % resp.status_code)
    if resp.status_code != 200:
        raise RuntimeError(body.get("error") or ("snmp-api : HTTP %s" % resp.status_code))
    return body


def community_from_credential(name):
    """Coffre des accès (#498) : accès de genre « snmp », mot de passe =
    communauté. Jamais journalisé, jamais stocké ici."""
    if not CREDENTIALS_API_URL or not CREDENTIALS_TOKEN:
        raise RuntimeError("coffre des accès non configuré côté network-equipment (CREDENTIALS_API_URL / CREDENTIALS_INTERNAL_TOKEN)")
    try:
        resp = requests.get("%s/credentials/reveal/%s" % (CREDENTIALS_API_URL, name), timeout=5,
                            headers={"X-Credentials-Token": CREDENTIALS_TOKEN, "X-Credentials-Consumer": "network-equipment-api"})
    except requests.RequestException as exc:
        raise RuntimeError("coffre des accès injoignable (%s)" % exc.__class__.__name__)
    if resp.status_code == 404:
        raise RuntimeError("accès « %s » absent du coffre -- à créer dans la tuile Accès d'équipements (genre snmp, mot de passe = communauté)" % name)
    if resp.status_code != 200:
        raise RuntimeError("coffre des accès : refus %s" % resp.status_code)
    pwd = (resp.json() or {}).get("password") or ""
    if not pwd:
        raise RuntimeError("accès « %s » sans mot de passe (communauté) dans le coffre" % name)
    return pwd


def snmp_target(row, body):
    """Paramètres de cible pour snmp-api d'après la requête puis la fiche :
    -> (payload de base, description sans secret, persist)."""
    body = body or {}
    host = (body.get("host") or row.get("ip") or "").strip()
    port = int(body.get("port") or row.get("snmp_port") or 161)
    timeout = int(body.get("timeout") or SNMP_TIMEOUT)
    persist = {}
    target_id = body.get("target_id") or row.get("snmp_target_id")
    credential = (body.get("credential") or row.get("snmp_credential") or "").strip()
    community = (body.get("community") or "").strip()
    if body.get("target_id"):
        persist["snmp_target_id"] = int(body["target_id"])
    if body.get("credential"):
        persist["snmp_credential"] = credential
    if body.get("port"):
        persist["snmp_port"] = port
    if community:
        if not host:
            raise RuntimeError("adresse IP inconnue pour cet équipement")
        return {"host": host, "community": community, "port": port, "timeout": timeout}, "communauté ponctuelle", persist
    if credential:
        if not host:
            raise RuntimeError("adresse IP inconnue pour cet équipement")
        return {"host": host, "community": community_from_credential(credential), "port": port, "timeout": timeout}, "coffre « %s »" % credential, persist
    if target_id:
        return {"target_id": int(target_id), "port": port, "timeout": timeout}, "cible snmp-api #%s" % target_id, persist
    raise RuntimeError("aucun accès SNMP : indiquer target_id (cible snmp-api), credential (coffre, genre snmp) ou community (ponctuelle)")


def walk(payload, oid, max_rows=None):
    body = _snmp_post("/walk", dict(payload, oid=oid, max_rows=max_rows or MAX_WALK_ROWS), payload.get("timeout", SNMP_TIMEOUT) * 6 + 5)
    return body.get("rows") or []


def port_names(payload):
    names = {}
    try:
        for idx, v in snmp_tables.column(walk(payload, snmp_tables.IFNAME_PREFIX, 1000), snmp_tables.IFNAME_PREFIX).items():
            names[idx] = v
    except RuntimeError:
        pass
    if not names:
        try:
            for idx, v in snmp_tables.column(walk(payload, snmp_tables.IFDESCR_PREFIX, 1000), snmp_tables.IFDESCR_PREFIX).items():
                names[idx] = v
        except RuntimeError:
            pass
    return names


# ---------------------------------------------------------------- routes de base

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/status", methods=["GET"])
def status_route():
    conn = _db()
    try:
        st = store.status(conn)
    finally:
        conn.close()
    st.update({"snmp_api": bool(SNMP_API_URL), "network_agent": bool(NETWORK_AGENT_API_URL),
               "credentials": bool(CREDENTIALS_API_URL and CREDENTIALS_TOKEN),
               "oui": {"seed": len(oui_mod.SEED), "file": OUI.file_entries, "path": OUI_PATH if OUI.file_entries else None},
               "profiles": [{"id": p["id"], "label": p["label"], "verified": p["verified"]} for p in profiles.PROFILES]})
    return jsonify(st), 200


@app.route("/equipment", methods=["GET"])
def list_route():
    conn = _db()
    try:
        rows = store.list_equipment(conn, kind=request.args.get("kind"), vendor=request.args.get("vendor"),
                                    generation=request.args.get("generation"), q=request.args.get("q"), site=request.args.get("site"))
    finally:
        conn.close()
    return jsonify({"equipment": rows, "total": len(rows)}), 200


@app.route("/equipment", methods=["POST"])
def create_route():
    body = request.get_json(silent=True) or {}
    mac = oui_mod.normalize_mac(body.get("mac"))
    ip = (body.get("ip") or "").strip() or None
    name = (body.get("name") or "").strip() or None
    if not (mac or ip or name):
        return jsonify({"error": "mac, ip ou name requis"}), 400
    conn = _db()
    try:
        fields = {"site": body.get("site"), "manual_json": {k: body[k] for k in ("vendor", "model", "kind", "generation", "notes") if body.get(k)} or None}
        hit = OUI.lookup(mac) if mac else None
        if hit:
            fields["oui_vendor"], fields["oui_category"] = hit.get("vendor"), hit.get("category")
        eq_id, created = store.upsert(conn, fields, mac=mac, ip=ip, name=name)
        ident = reidentify(conn, eq_id, "manuel")
        conn.commit()
        row = store.get(conn, eq_id)
    finally:
        conn.close()
    return jsonify({"equipment": row, "identification": ident, "created": created}), 201 if created else 200


@app.route("/equipment/<int:eq_id>", methods=["GET"])
def get_route(eq_id):
    conn = _db()
    try:
        row = store.get(conn, eq_id)
        if not row:
            return jsonify({"error": "équipement introuvable"}), 404
        row["neighbors"] = store.neighbors_of(conn, eq_id)
        row["fdb_count"] = len(store.fdb_of(conn, eq_id))
        row["profile"] = profiles.profile_summary(profiles.profile_by_id(row.get("profile_id")) or profiles.match_profile(row))
        row["history"] = [dict(r) | {"result": json.loads(r["result_json"] or "{}")} for r in
                          conn.execute("SELECT id, at, source, result_json FROM identifications WHERE equipment_id = ? ORDER BY id DESC LIMIT 10", (eq_id,)).fetchall()]
        for h in row["history"]:
            h.pop("result_json", None)
        if row.get("mac"):
            row["where"] = store.where_is_mac(conn, row["mac"])
    finally:
        conn.close()
    return jsonify(row), 200


@app.route("/equipment/<int:eq_id>", methods=["PUT"])
def update_route(eq_id):
    body = request.get_json(silent=True) or {}
    conn = _db()
    try:
        row = store.get(conn, eq_id)
        if not row:
            return jsonify({"error": "équipement introuvable"}), 404
        manual = dict(row.get("manual") or {})
        for k in ("vendor", "model", "kind", "generation", "notes"):
            if k in body:
                if body[k]:
                    manual[k] = str(body[k]).strip()
                else:
                    manual.pop(k, None)
        if manual.get("kind") and manual["kind"] not in identify.KINDS + ("équipement réseau",):
            return jsonify({"error": "kind invalide (attendu : %s)" % ", ".join(identify.KINDS)}), 400
        fields = {"manual_json": json.dumps(manual, ensure_ascii=False)}
        for k in ("name", "site", "ip", "snmp_credential"):
            if k in body:
                fields[k] = (str(body[k]).strip() or None) if body[k] is not None else None
        if "snmp_target_id" in body:
            fields["snmp_target_id"] = int(body["snmp_target_id"]) if body["snmp_target_id"] else None
        if "snmp_port" in body:
            fields["snmp_port"] = int(body["snmp_port"]) if body["snmp_port"] else None
        if "mac" in body:
            fields["mac"] = oui_mod.normalize_mac(body["mac"])
            hit = OUI.lookup(fields["mac"]) if fields["mac"] else None
            fields["oui_vendor"] = hit.get("vendor") if hit else None
            fields["oui_category"] = hit.get("category") if hit else None
        sets = ", ".join("%s = ?" % k for k in fields)
        conn.execute("UPDATE equipment SET %s, updated_at = ? WHERE id = ?" % sets, list(fields.values()) + [store.now_iso(), eq_id])
        ident = reidentify(conn, eq_id, "manuel")
        conn.commit()
        row = store.get(conn, eq_id)
    finally:
        conn.close()
    return jsonify({"equipment": row, "identification": ident}), 200


@app.route("/equipment/<int:eq_id>", methods=["DELETE"])
def delete_route(eq_id):
    conn = _db()
    try:
        ok = store.delete(conn, eq_id)
        conn.commit()
    finally:
        conn.close()
    return (jsonify({"deleted": eq_id}), 200) if ok else (jsonify({"error": "équipement introuvable"}), 404)


# ---------------------------------------------------------------- imports

@app.route("/import/network-agent", methods=["POST"])
def import_network_agent():
    """Tire les appareils de l'exploration (network-agent /devices) :
    une fiche par MAC, constructeur d'après l'OUI, IP/nom/rôle/services
    conservés comme preuves. `segment_id` optionnel. Rien n'est supprimé."""
    if not NETWORK_AGENT_API_URL:
        return jsonify({"error": "network-agent non configuré (NETWORK_AGENT_API_URL)"}), 400
    body = request.get_json(silent=True) or {}
    params = {}
    if body.get("segment_id"):
        params["segment_id"] = int(body["segment_id"])
    try:
        resp = requests.get(NETWORK_AGENT_API_URL + "/devices", params=params, timeout=30)
        devices = resp.json() if resp.status_code == 200 else None
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"error": "network-agent injoignable (%s)" % exc.__class__.__name__}), 502
    if not isinstance(devices, list):
        return jsonify({"error": "network-agent : réponse inattendue (HTTP %s)" % resp.status_code}), 502
    services = {}
    try:
        sresp = requests.get(NETWORK_AGENT_API_URL + "/devices/services", params=params, timeout=30)
        if sresp.status_code == 200:
            for s in sresp.json() or []:
                if isinstance(s, dict) and s.get("device_id") is not None and s.get("port") is not None:
                    services.setdefault(int(s["device_id"]), set()).add(int(s["port"]))
    except (requests.RequestException, ValueError):
        pass
    counts = {"seen": len(devices), "created": 0, "updated": 0, "skipped": 0, "network_vendors": 0}
    conn = _db()
    try:
        for d in devices:
            mac = oui_mod.normalize_mac(d.get("mac_address"))
            if not mac:
                counts["skipped"] += 1
                continue
            hit = OUI.lookup(mac)
            fields = {"ip": d.get("ip_address") or None, "hostname": d.get("hostname") or None, "role_hint": d.get("role_hint") or None,
                      "network_agent_device_id": d.get("id"), "site": d.get("site") or d.get("site_name") or None,
                      "oui_vendor": hit.get("vendor") if hit else None, "oui_category": hit.get("category") if hit else None}
            ports = sorted(services.get(int(d["id"]), set())) if d.get("id") is not None else []
            if ports:
                fields["ports_json"] = json.dumps(ports)
            eq_id, created = store.upsert(conn, fields, mac=mac, ip=d.get("ip_address") or None, name=d.get("hostname") or None)
            if d.get("ip_address"):
                conn.execute("UPDATE equipment SET ip = ? WHERE id = ?", (d["ip_address"], eq_id))
            reidentify(conn, eq_id, "exploration")
            counts["created" if created else "updated"] += 1
            if hit and hit.get("category") == "reseau":
                counts["network_vendors"] += 1
        store.record_import(conn, "network-agent", None, counts)
        conn.commit()
    finally:
        conn.close()
    return jsonify(counts), 200


@app.route("/import/zenoss", methods=["POST"])
def import_zenoss():
    """Fichier `file` (multipart : JSON du script zendmd ou CSV de la
    liste Zenoss) ou JSON {content: "...", filename?, dry_run?} ou
    {devices: [...]} (déjà parsé). `dry_run` : analyse seulement."""
    dry_run = False
    filename = None
    if request.files.get("file"):
        f = request.files["file"]
        filename = f.filename
        content = f.read()
        dry_run = (request.form.get("dry_run") or "").lower() in ("1", "true", "yes")
        devices, skipped, fmt = zenoss_import.parse(content, filename)
    else:
        body = request.get_json(silent=True) or {}
        dry_run = bool(body.get("dry_run"))
        filename = body.get("filename")
        if isinstance(body.get("devices"), list):
            devices, skipped, fmt = zenoss_import.parse(json.dumps({"devices": body["devices"]}), "inline.json")
        elif body.get("content"):
            devices, skipped, fmt = zenoss_import.parse(body["content"], filename)
        else:
            return jsonify({"error": "fichier `file`, `content` ou `devices` requis"}), 400
    counts = {"format": fmt, "parsed": len(devices), "skipped_rows": skipped, "created": 0, "updated": 0, "with_hardware": 0,
              "by_class": {}, "dry_run": dry_run}
    preview = []
    for d in devices:
        dc = d.get("device_class") or "?"
        counts["by_class"][dc] = counts["by_class"].get(dc, 0) + 1
        if d.get("hw_product") or d.get("sys_descr"):
            counts["with_hardware"] += 1
    if not devices:
        return jsonify(dict(counts, error="aucune fiche reconnue : en-têtes attendus Device/IP/Device Class (CSV) ou {devices:[…]} (JSON zendmd)")), 400
    if dry_run:
        for d in devices[:50]:
            zen = {k: d.get(k) for k in ("device_class", "hw_manufacturer", "hw_product", "os_manufacturer", "os_product", "serial")}
            ident = identify.merge({"sys_descr": d.get("sys_descr"), "sys_object_id": d.get("sys_object_id"), "zenoss": zen,
                                    "oui": OUI.lookup(zenoss_import.primary_mac(d)) if zenoss_import.primary_mac(d) else None})
            preview.append({"name": d.get("name"), "ip": d.get("ip"), "device_class": d.get("device_class"), "mac": zenoss_import.primary_mac(d),
                            "vendor": ident["vendor"], "model": ident["model"], "kind": ident["kind"], "generation": ident["generation"]})
        return jsonify(dict(counts, preview=preview)), 200
    conn = _db()
    try:
        for d in devices:
            mac = oui_mod.normalize_mac(zenoss_import.primary_mac(d))
            zen = {k: d.get(k) for k in ("zenoss_id", "device_class", "production_state", "hw_manufacturer", "hw_product", "os_manufacturer",
                                         "os_product", "serial", "location", "systems", "groups", "comments", "last_change", "snmp_last_collection", "interfaces")}
            fields = {"zenoss_json": json.dumps(zen, ensure_ascii=False), "zenoss_class": d.get("device_class"),
                      "sys_descr": d.get("sys_descr"), "sys_object_id": d.get("sys_object_id"), "sys_name": d.get("sys_name"),
                      "sys_location": d.get("snmp_location"), "sys_contact": d.get("snmp_contact"),
                      "site": d.get("location") or None}
            if mac:
                hit = OUI.lookup(mac)
                fields["oui_vendor"] = hit.get("vendor") if hit else None
                fields["oui_category"] = hit.get("category") if hit else None
            eq_id, created = store.upsert(conn, fields, mac=mac, ip=d.get("ip"), name=d.get("name"))
            reidentify(conn, eq_id, "zenoss")
            counts["created" if created else "updated"] += 1
        store.record_import(conn, "zenoss-" + fmt, filename, {k: v for k, v in counts.items() if k != "by_class"})
        conn.commit()
    finally:
        conn.close()
    return jsonify(counts), 200


# ---------------------------------------------------------------- identification

@app.route("/identify/preview", methods=["POST"])
def identify_preview():
    body = request.get_json(silent=True) or {}
    mac = oui_mod.normalize_mac(body.get("mac"))
    ev = {"mac": mac, "oui": OUI.lookup(mac) if mac else None, "sys_descr": body.get("sys_descr"), "sys_object_id": body.get("sys_object_id"),
          "entity": body.get("entity") or {}, "zenoss": {"device_class": body.get("zenoss_class")} if body.get("zenoss_class") else {},
          "role_hint": body.get("role_hint"), "ports": body.get("ports") or [], "manual": body.get("manual") or {}}
    ident = identify.merge(ev)
    prof = profiles.match_profile(ident)
    return jsonify({"identification": ident, "profile": {"id": prof["id"], "label": prof["label"], "verified": prof["verified"]},
                    "oui": ev["oui"], "sys_descr_parsed": identify.parse_sys_descr(body.get("sys_descr")) if body.get("sys_descr") else {}}), 200


def identify_one(conn, eq_id, body):
    """Relevé SNMP d'identification d'une fiche -> (ident, warnings) ;
    lève RuntimeError avec un message sans secret."""
    row = store.get(conn, eq_id)
    if not row:
        raise RuntimeError("équipement introuvable")
    payload, how, persist = snmp_target(row, body)
    warnings = []
    system = _snmp_post("/query", payload, payload.get("timeout", SNMP_TIMEOUT) + 5).get("system") or {}
    oids = _snmp_post("/get", dict(payload, oids=["1.3.6.1.2.1.1.2.0"]), payload.get("timeout", SNMP_TIMEOUT) + 5).get("values") or {}
    fields = {"sys_descr": system.get("sysDescr"), "sys_name": system.get("sysName"), "sys_location": system.get("sysLocation"),
              "sys_contact": system.get("sysContact"), "sys_object_id": oids.get("1.3.6.1.2.1.1.2.0"),
              "last_identified_at": store.now_iso(), "last_identify_error": None}
    fields.update(persist)
    try:
        ent = snmp_tables.parse_entity(walk(payload, snmp_tables.ENTITY_PREFIX))
        if ent:
            fields["entity_json"] = json.dumps(ent, ensure_ascii=False)
    except RuntimeError as exc:
        warnings.append("ENTITY-MIB : %s" % exc)
    names = {}
    want_neighbors = body.get("neighbors", True)
    want_fdb = body.get("fdb", True)
    if want_neighbors or want_fdb:
        names = port_names(payload)
    if want_neighbors:
        try:
            lldp = snmp_tables.parse_lldp(walk(payload, snmp_tables.LLDP_REM_PREFIX), names)
            store.replace_neighbors(conn, eq_id, "lldp", lldp)
        except RuntimeError as exc:
            warnings.append("LLDP : %s" % exc)
        try:
            cdp = snmp_tables.parse_cdp(walk(payload, snmp_tables.CDP_PREFIX), names)
            if cdp:
                store.replace_neighbors(conn, eq_id, "cdp", cdp)
        except RuntimeError as exc:
            warnings.append("CDP : %s" % exc)
    if want_fdb:
        try:
            base = snmp_tables.column(walk(payload, snmp_tables.BASEPORT_IFINDEX_PREFIX, 2000), snmp_tables.BASEPORT_IFINDEX_PREFIX)
            fdb_rows = walk(payload, snmp_tables.FDB_PREFIX)
            q_rows = []
            try:
                q_rows = walk(payload, snmp_tables.FDB_Q_PREFIX)
            except RuntimeError:
                pass
            entries = snmp_tables.parse_fdb(fdb_rows, base, names, q_rows)
            store.replace_fdb(conn, eq_id, entries)
            fields["_fdb"] = len(entries)
        except RuntimeError as exc:
            warnings.append("table MAC : %s" % exc)
    fdb_n = fields.pop("_fdb", None)
    sets = ", ".join("%s = ?" % k for k in fields)
    conn.execute("UPDATE equipment SET %s WHERE id = ?" % sets, list(fields.values()) + [eq_id])
    ident = reidentify(conn, eq_id, "snmp (%s)" % how)
    return ident, warnings, fdb_n


@app.route("/equipment/<int:eq_id>/identify", methods=["POST"])
def identify_route(eq_id):
    body = request.get_json(silent=True) or {}
    conn = _db()
    try:
        try:
            ident, warnings, fdb_n = identify_one(conn, eq_id, body)
        except RuntimeError as exc:
            conn.execute("UPDATE equipment SET last_identify_error = ?, updated_at = ? WHERE id = ?", (str(exc), store.now_iso(), eq_id))
            conn.commit()
            return jsonify({"error": str(exc)}), 502 if "introuvable" not in str(exc) else 404
        conn.commit()
        row = store.get(conn, eq_id)
        row["neighbors"] = store.neighbors_of(conn, eq_id)
    finally:
        conn.close()
    return jsonify({"equipment": row, "identification": ident, "warnings": warnings, "fdb": fdb_n}), 200


@app.route("/identify/batch", methods=["POST"])
def identify_batch():
    body = request.get_json(silent=True) or {}
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids or len(ids) > 50:
        return jsonify({"error": "ids : liste de 1 à 50 identifiants"}), 400
    results = []
    conn = _db()
    try:
        for eq_id in ids:
            try:
                ident, warnings, _ = identify_one(conn, int(eq_id), body)
                results.append({"id": int(eq_id), "ok": True, "vendor": ident["vendor"], "model": ident["model"], "kind": ident["kind"], "warnings": warnings})
            except (RuntimeError, ValueError) as exc:
                conn.execute("UPDATE equipment SET last_identify_error = ? WHERE id = ?", (str(exc), eq_id))
                results.append({"id": eq_id, "ok": False, "error": str(exc)})
            conn.commit()
    finally:
        conn.close()
    return jsonify({"results": results, "ok": sum(1 for r in results if r["ok"]), "failed": sum(1 for r in results if not r["ok"])}), 200


# ---------------------------------------------------------------- profils / relevé

@app.route("/profiles", methods=["GET"])
def profiles_route():
    return jsonify({"profiles": [profiles.profile_summary(p) for p in profiles.PROFILES]}), 200


@app.route("/equipment/<int:eq_id>/profile", methods=["GET"])
def profile_route(eq_id):
    conn = _db()
    try:
        row = store.get(conn, eq_id)
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "équipement introuvable"}), 404
    p = profiles.profile_by_id(row.get("profile_id")) or profiles.match_profile(row)
    return jsonify({"equipment_id": eq_id, "profile": profiles.profile_summary(p)}), 200


@app.route("/equipment/<int:eq_id>/poll", methods=["POST"])
def poll_route(eq_id):
    """Relevé du profil : GET des scalaires, WALK des colonnes, interfaces
    IF-MIB -> valeurs décodées + synthèse (CPU, mémoire, température,
    alarmes). Un OID absent n'est pas une erreur (équipement sans la MIB)."""
    body = request.get_json(silent=True) or {}
    conn = _db()
    try:
        row = store.get(conn, eq_id)
        if not row:
            return jsonify({"error": "équipement introuvable"}), 404
        p = profiles.profile_by_id(body.get("profile_id") or row.get("profile_id")) or profiles.match_profile(row)
        try:
            payload, how, persist = snmp_target(row, body)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 400
        result = {"profile": p["id"], "verified": p["verified"], "gets": {}, "walks": {}, "interfaces": [], "errors": [], "at": store.now_iso()}
        try:
            if p["gets"]:
                values = _snmp_post("/get", dict(payload, oids=[g["oid"] for g in p["gets"].values()]), payload.get("timeout", SNMP_TIMEOUT) + 5).get("values") or {}
                for key, spec in p["gets"].items():
                    result["gets"][key] = profiles.decode_value(spec, values.get(spec["oid"]))
        except RuntimeError as exc:
            result["errors"].append("GET : %s" % exc)
        for key, spec in p["walks"].items():
            try:
                rows = walk(payload, spec["oid"], 500)
                if spec.get("columns"):
                    cols = snmp_tables.by_column(rows, spec["oid"])
                    table = {}
                    for c, values in cols.items():
                        name = spec["columns"].get(c, c)
                        if name == "address":
                            values = {i: (snmp_tables.hex_to_ipv4(v) or v) for i, v in values.items()}
                        elif name in ("chassis_id", "port_id"):
                            values = {i: (snmp_tables.hex_to_mac(v) or v) for i, v in values.items()}
                        table[name] = values
                    result["walks"][key] = table
                else:
                    result["walks"][key] = snmp_tables.parse_scalar_column(rows, spec["oid"], spec, profiles.decode_value)
            except RuntimeError as exc:
                result["errors"].append("%s : %s" % (key, exc))
        if body.get("interfaces", True):
            try:
                result["interfaces"] = _snmp_post("/walk-interfaces", payload, payload.get("timeout", SNMP_TIMEOUT) * 4 + 5).get("interfaces") or []
            except RuntimeError as exc:
                result["errors"].append("interfaces : %s" % exc)
        result["summary"] = profiles.interpret(p, result["gets"], {k: v for k, v in result["walks"].items() if isinstance(v, list)})
        fatal = result["errors"] and not result["gets"] and not result["walks"] and not result["interfaces"]
        fields = {"last_poll_json": json.dumps(result, ensure_ascii=False), "last_poll_at": result["at"],
                  "last_poll_error": "; ".join(result["errors"]) if fatal else None, "updated_at": store.now_iso()}
        fields.update(persist)
        sets = ", ".join("%s = ?" % k for k in fields)
        conn.execute("UPDATE equipment SET %s WHERE id = ?" % sets, list(fields.values()) + [eq_id])
        conn.commit()
    finally:
        conn.close()
    return jsonify(result), 502 if fatal else 200


# ---------------------------------------------------------------- voisinage / topologie

@app.route("/neighbors", methods=["GET"])
def neighbors_route():
    conn = _db()
    try:
        rows = store.neighbors_of(conn, request.args.get("equipment_id", type=int))
    finally:
        conn.close()
    return jsonify({"neighbors": rows}), 200


@app.route("/equipment/<int:eq_id>/fdb", methods=["GET"])
def fdb_route(eq_id):
    conn = _db()
    try:
        rows = store.fdb_of(conn, eq_id)
        known = {r["mac"]: {"id": r["id"], "name": r["name"], "ip": r["ip"], "vendor": r["vendor"]} for r in
                 conn.execute("SELECT id, mac, name, ip, vendor FROM equipment WHERE mac IN (%s)" % ",".join("?" * len(rows)), [r["mac"] for r in rows]).fetchall()} if rows else {}
        for r in rows:
            r["known"] = known.get(r["mac"])
            hit = OUI.lookup(r["mac"])
            r["oui_vendor"] = hit.get("vendor") if hit else None
    finally:
        conn.close()
    return jsonify({"fdb": rows, "total": len(rows)}), 200


@app.route("/topology", methods=["GET"])
def topology_route():
    conn = _db()
    try:
        links = store.topology(conn)
        nodes = {r["id"]: {"id": r["id"], "name": r["name"] or r["hostname"] or r["ip"] or r["mac"], "kind": r["kind"], "vendor": r["vendor"], "model": r["model"]}
                 for r in conn.execute("SELECT id, name, hostname, ip, mac, kind, vendor, model FROM equipment").fetchall()}
    finally:
        conn.close()
    used = set()
    for l in links:
        used.add(l["from"]); used.add(l["to"])
    return jsonify({"links": links, "nodes": [nodes[i] for i in used if i in nodes]}), 200


@app.route("/where-is", methods=["GET"])
def where_is_route():
    mac = oui_mod.normalize_mac(request.args.get("mac"))
    if not mac:
        return jsonify({"error": "mac requise"}), 400
    conn = _db()
    try:
        rows = store.where_is_mac(conn, mac)
    finally:
        conn.close()
    return jsonify({"mac": mac, "seen_on": rows}), 200


# ---------------------------------------------------------------- OUI

@app.route("/oui/lookup", methods=["GET"])
def oui_lookup():
    mac = request.args.get("mac")
    hit = OUI.lookup(mac)
    return jsonify({"mac": oui_mod.normalize_mac(mac), "result": hit}), 200


@app.route("/oui/import", methods=["POST"])
def oui_import():
    """Fichier IEEE (oui.csv « MA-L » ou oui.txt) -> /data/oui.csv, rechargé."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "fichier `file` requis (oui.csv ou oui.txt de l'IEEE)"}), 400
    content = f.read()
    tmp = OUI_PATH + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(content)
    try:
        table = oui_mod.OuiTable(tmp)
    except Exception as exc:  # noqa: BLE001
        os.remove(tmp)
        return jsonify({"error": "fichier illisible : %s" % exc}), 400
    if table.file_entries < 100:
        os.remove(tmp)
        return jsonify({"error": "fichier reconnu mais %d entrée(s) seulement : pas le registre IEEE" % table.file_entries}), 400
    os.replace(tmp, OUI_PATH)
    global OUI
    OUI = table
    return jsonify({"entries": table.file_entries, "path": OUI_PATH}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
