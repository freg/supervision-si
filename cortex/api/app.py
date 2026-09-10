# -*- coding: utf-8 -*-
"""cortex-api (livraison #462) -- « Cortex » : décloisonne, corrèle, relie,
consolide. Première étape du découpage de docs/analyse-supervision-unifiee.md :
modèle commun (entités / relations / événements normalisés), collecte des
sources existantes, incidents par fenêtre glissante + relation partagée
avec cause racine amont, retours humains par principe.

Transparence : chaque hypothèse porte sa confiance, ses preuves et le
PRINCIPE (parti pris) qu'elle applique ; /principles rend l'évaluation
mesurée de chaque principe (base, confirmés, rejetés, appliqués) ; /runs
dit quelle source a répondu, en combien de temps, et ce qui en est sorti.

Routes (préfixe /api/cortex via tls-proxy) :
  GET  /health /status /principles /runs /stats
  POST /collect                       (droit manage)
  GET  /entities?q  /entities/<key>   (rôles pondérés, relations, événements)
  GET  /relations?entity
  GET  /events?state&severity&since&entity
  POST /events/<fp>/ack | /close
  GET  /incidents?state  /incidents/<key>
  POST /incidents/<key>/ack | /close
  POST /incidents/<key>/feedback  {principle, verdict: confirmed|rejected, claim?, by?, note?}
"""
import logging
import os
import threading
import time
from urllib.parse import unquote

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import collectors
import correlate
import learn
import normalize as nz
import notify
import places as pl
import policy
import principles as pr
import store

try:
    from version_endpoint import register_version_route
except ImportError:  # pragma: no cover
    register_version_route = None

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("cortex")

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "cortex-api")

DB_PATH = os.environ.get("CORTEX_DB_PATH", "/data/cortex.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
store.ensure_schema(DB_PATH)
URLS = {"si_agent": os.environ.get("SI_AGENT_API_URL", ""), "vigilance": os.environ.get("VIGILANCE_API_URL", ""), "ups": os.environ.get("UPS_API_URL", ""),
        "orchestrator": os.environ.get("NETMAP_ORCHESTRATOR_API_URL", ""), "netprobe": os.environ.get("NETPROBE_API_URL", ""),
        "network_agent": os.environ.get("NETWORK_AGENT_API_URL", ""), "backup": os.environ.get("BACKUP_RESTORE_API_URL", ""),
        "classifier": os.environ.get("CLASSIFIER_API_URL", ""), "nebula": os.environ.get("NEBULA_API_URL", ""), "ipam": os.environ.get("IPAM_API_URL", ""),
        "pixel_grid": os.environ.get("PIXEL_GRID_API_URL", ""), "geo_catalog": os.environ.get("GEO_CATALOG_API_URL", "")}
WINDOW_S = int(os.environ.get("CORTEX_WINDOW_SECONDS", "300"))
INTERVAL_S = int(os.environ.get("CORTEX_INTERVAL_SECONDS", "300"))
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None
collector = collectors.Collector(DB_PATH, URLS, window_s=WINDOW_S, horizon_h=int(os.environ.get("CORTEX_EVENT_HORIZON_HOURS", "24")))
store.seed_policies(DB_PATH, policy.DEFAULT_POLICIES)
_state = {"last_run": None, "running": False}


def _check_manage_right(body):
    if not RIGHTS_API_URL:
        return True, None
    try:
        resp = requests.post(RIGHTS_API_URL + "/check", json={"groups": body.get("groups") or [], "resource_type": "cortex-api", "resource_id": None, "action": "manage"}, timeout=5)
        if resp.status_code == 200 and resp.json().get("allowed"):
            return True, None
        return False, "droit 'manage' sur cortex-api requis"
    except (requests.RequestException, ValueError):
        return False, "service de droits injoignable -- action refusée par prudence"


def _run_collect():
    if _state["running"]:
        return None
    _state["running"] = True
    try:
        report, counts = collector.run()
        _state["last_run"] = {"at": store.now_iso(), "report": report, "counts": counts}
        return _state["last_run"]
    except Exception as exc:  # noqa: BLE001
        _log.exception("collecte échouée")
        _state["last_run"] = {"at": store.now_iso(), "error": str(exc)}
        return _state["last_run"]
    finally:
        _state["running"] = False


def _loop():
    time.sleep(10)
    while True:
        try:
            _run_collect()
            store.purge(DB_PATH, int(os.environ.get("CORTEX_RETENTION_DAYS", "30")))
        except Exception:  # noqa: BLE001
            _log.exception("boucle de collecte")
        time.sleep(INTERVAL_S)


if os.environ.get("CORTEX_AUTOCOLLECT", "1") == "1" and any(URLS.values()):
    threading.Thread(target=_loop, daemon=True).start()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/status", methods=["GET"])
def status():
    inc = store.list_incidents(DB_PATH, state="open")
    return jsonify({"sources": {k: bool(v) for k, v in URLS.items()}, "window_seconds": WINDOW_S, "interval_seconds": INTERVAL_S,
                    "last_run": _state["last_run"], "running": _state["running"],
                    "incidents_open": len(inc), "incidents_critical": sum(1 for i in inc if i["severity"] == "critical"),
                    "entities": len(store.list_entities(DB_PATH, limit=100000)), "events_open": len(store.list_events(DB_PATH, state="open", limit=100000))}), 200


@app.route("/collect", methods=["POST"])
def collect():
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    r = _run_collect()
    if r is None:
        return jsonify({"error": "collecte déjà en cours"}), 409
    return jsonify(r), 200


@app.route("/principles", methods=["GET"])
def principles():
    fc = store.feedback_counts(DB_PATH)
    return jsonify({"principles": [pr.evaluate(pid, fc) for pid in pr.PRINCIPLES], "feedback": store.list_feedback(DB_PATH, 50)}), 200


@app.route("/runs", methods=["GET"])
def runs():
    return jsonify({"runs": store.list_runs(DB_PATH, request.args.get("limit", 20, type=int))}), 200


@app.route("/stats", methods=["GET"])
def stats():
    days = request.args.get("days", 7, type=int)
    events = store.list_events(DB_PATH, state="all", limit=20000)
    incidents = store.list_incidents(DB_PATH, state="all", limit=5000)
    s = correlate.stats(events, incidents, days=days)
    names = {e["key"]: e.get("name") or e.get("ip") or e["key"] for e in store.list_entities(DB_PATH, limit=100000)}
    for n in s["noisy_entities"]:
        n["name"] = names.get(n["entity"], n["entity"])
    s["principles"] = [{"id": p["id"], "title": p["title"], "effective": p["effective"], "applied": p["applied"], "confirmed": p["confirmed"], "rejected": p["rejected"]}
                       for p in (pr.evaluate(pid, store.feedback_counts(DB_PATH)) for pid in pr.PRINCIPLES)]
    return jsonify(s), 200


@app.route("/entities", methods=["GET"])
def entities():
    fc = store.feedback_counts(DB_PATH)
    out = []
    for e in store.list_entities(DB_PATH, q=request.args.get("q"), limit=request.args.get("limit", 500, type=int)):
        e["roles"] = nz.role_hypotheses(e, fc)
        out.append(e)
    return jsonify({"entities": out}), 200


@app.route("/entities/<path:key>", methods=["GET"])
def entity(key):
    key = unquote(key)
    e = store.get_entity(DB_PATH, key)
    if not e:
        return jsonify({"error": "entité inconnue"}), 404
    e["roles"] = nz.role_hypotheses(e, store.feedback_counts(DB_PATH))
    e["relations"] = store.list_relations(DB_PATH, entity=key)
    e["events"] = store.list_events(DB_PATH, entity=key, state="all", limit=50)
    return jsonify(e), 200


@app.route("/routes", methods=["GET"])
def routes():
    names = store.entity_names(DB_PATH)
    out = store.list_routes(DB_PATH, host=request.args.get("host"))
    for r in out:
        r["host_name"] = names.get(r["host"], r["host"])
    return jsonify({"routes": out}), 200


@app.route("/changes", methods=["GET"])
def changes_route():
    return jsonify({"changes": store.list_changes(DB_PATH, since=request.args.get("since"), limit=request.args.get("limit", 300, type=int))}), 200


@app.route("/graph", methods=["GET"])
def graph():
    """Graphe d'architecture persistant : nœuds (entités avec rôle dominant,
    site, type, constructeur) et arêtes (relations pondérées) -- pour la vue
    Graphe et pour tout autre consommateur (architecture-api, analyse réseau)."""
    fc = store.feedback_counts(DB_PATH)
    nodes = []
    for e in store.list_entities(DB_PATH, limit=5000):
        roles = nz.role_hypotheses(e, fc)
        nodes.append({"key": e["key"], "name": e.get("name") or e.get("ip") or e["key"], "kind": e.get("kind"), "site": e.get("site"), "ip": e.get("ip"),
                      "vendor": e.get("vendor"), "role": roles[0]["role"] if roles else None, "role_confidence": roles[0]["confidence"] if roles else None,
                      "sources": sorted({o.get("source") for o in (e.get("origins") or []) if o.get("source")})})
    edges = [{"a": r["a"], "b": r["b"], "kind": r["kind"], "weight": r.get("weight"), "principle": r.get("principle"), "source": r.get("source")} for r in store.list_relations(DB_PATH)]
    return jsonify({"nodes": nodes, "edges": edges, "generated_at": store.now_iso()}), 200


@app.route("/relations", methods=["GET"])
def relations():
    return jsonify({"relations": store.list_relations(DB_PATH, entity=request.args.get("entity"))}), 200


@app.route("/events", methods=["GET"])
def events():
    return jsonify({"events": store.list_events(DB_PATH, state=request.args.get("state", "open"), severity=request.args.get("severity"),
                                                since=request.args.get("since"), entity=request.args.get("entity"), limit=request.args.get("limit", 300, type=int))}), 200


@app.route("/events/<fp>/<action>", methods=["POST"])
def event_action(fp, action):
    if action not in ("ack", "close"):
        return jsonify({"error": "action : ack | close"}), 400
    body = request.get_json(silent=True) or {}
    ok = store.set_event_state(DB_PATH, fp, "acked" if action == "ack" else "closed", by=body.get("by"))
    collector.recompute()
    return jsonify({"ok": ok}), 200 if ok else 404


@app.route("/incidents", methods=["GET"])
def incidents():
    return jsonify({"incidents": store.list_incidents(DB_PATH, state=request.args.get("state", "open"), limit=request.args.get("limit", 200, type=int))}), 200


@app.route("/incidents/<key>", methods=["GET"])
def incident(key):
    i = store.get_incident(DB_PATH, key)
    if not i:
        return jsonify({"error": "incident inconnu"}), 404
    fps = set(i.get("events") or [])
    i["event_details"] = [e for e in store.list_events(DB_PATH, state="all", limit=5000) if e["fingerprint"] in fps]
    i["entity_details"] = [store.get_entity(DB_PATH, k) for k in i.get("entities") or []]
    ents = set(i.get("entities") or [])
    seen, rels = set(), []
    for k in ents:
        for r in store.list_relations(DB_PATH, entity=k):
            sig = (r["a"], r["b"], r["kind"])
            if sig not in seen and (r["a"] in ents or r["b"] in ents):
                seen.add(sig); rels.append(r)
    i["relations"] = rels[:200]
    # #465 : annonces en attente déclenchées par un événement de cet incident
    i["predictions"] = [p for p in store.list_predictions(DB_PATH, pending_only=True, limit=500) if p.get("trigger") in fps]
    for p in i["predictions"]:
        p.pop("roles", None)
    # #466 : politique appliquée, notifications envoyées, silence en cours, tuiles d'origine
    ents = {e["key"]: e for e in store.list_entities(DB_PATH, limit=100000)}
    roles = collector.roles_map()
    i["policy"] = policy.evaluate_policy(i, ents, roles, store.list_policies(DB_PATH))
    import datetime as _dt
    sil = policy.active_silence(store.list_silences(DB_PATH, active_only=True), i, ents, roles, _dt.datetime.now(_dt.timezone.utc))
    i["silence"] = {"id": sil["id"], "name": sil.get("name"), "ticket": sil.get("ticket"), "end_at": sil.get("end_at")} if sil else None
    i["notifications"] = store.list_notifications(DB_PATH, incident_key=key)
    i["origins"] = policy.origin_views(i, {e["fingerprint"]: e for e in i["event_details"]})
    return jsonify(i), 200


@app.route("/incidents/<key>/<action>", methods=["POST"])
def incident_action(key, action):
    body = request.get_json(silent=True) or {}
    if action in ("ack", "close"):
        ok = store.set_incident_state(DB_PATH, key, "acked" if action == "ack" else "closed", by=body.get("by"))
        return jsonify({"ok": ok}), 200 if ok else 404
    if action == "feedback":
        if body.get("verdict") not in ("confirmed", "rejected") or not body.get("principle"):
            return jsonify({"error": "principle et verdict (confirmed | rejected) requis"}), 400
        if body["principle"] not in pr.PRINCIPLES:
            return jsonify({"error": "principe inconnu"}), 400
        store.add_feedback(DB_PATH, body["principle"], body["verdict"], incident_key=key, claim=body.get("claim"), by=body.get("by"), note=body.get("note"))
        collector.recompute()
        return jsonify({"ok": True, "principle": pr.evaluate(body["principle"], store.feedback_counts(DB_PATH))}), 200
    return jsonify({"error": "action : ack | close | feedback"}), 400


# ---------------------------------------------------------------- lieux / positions / intervention / couches (#464)
TICKETS_URL = os.environ.get("TICKETS_PORTAL_URL", "").rstrip("/") or None
BASTION_ENABLED = os.environ.get("SI_PROXY_ENABLED", "0") in ("1", "true", "yes")


def _bastion_targets(entity):
    """Le bastion (si-proxy) n'a pas de liste de cibles : depuis le Mac de la
    personne autorisée, il ouvre un shell sur le hub et un CONNECT vers le
    LAN du hub. Une IP privée est donc « joignable via le bastion » quand
    le relais est déployé ; None quand il ne l'est pas (fiche : « non
    interrogé »). Cortex ne détient jamais le jeton d'administration."""
    if not BASTION_ENABLED:
        return None
    ip = entity.get("ip") or ""
    try:
        import ipaddress
        return [ip] if ip and ipaddress.ip_address(ip).is_private and not ip.startswith("127.") else []
    except ValueError:
        return []


@app.route("/places", methods=["GET"])
def places_route():
    return jsonify({"places": store.list_places(DB_PATH), "kinds": list(pl.PLACE_KINDS)}), 200


@app.route("/places/<path:key>", methods=["PUT"])
def place_note(key):
    """Contact, accès, notes d'un lieu -- saisie humaine, jamais écrasée par la collecte."""
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    n = store.set_place_note(DB_PATH, key, contact=body.get("contact"), access=body.get("access"), notes=body.get("notes"), by=body.get("by"))
    return jsonify({"ok": True, "note": n}), 200


@app.route("/positions", methods=["GET"])
def positions_route():
    rows = store.list_positions(DB_PATH, provenance=request.args.get("provenance"), entity=request.args.get("entity"))
    return jsonify({"positions": rows, "by_provenance": pl._count(rows, "provenance"), "count": len(rows)}), 200


@app.route("/positions/queue", methods=["GET"])
def positions_queue():
    ents = store.list_entities(DB_PATH, limit=100000)
    pos = store.positions_map(DB_PATH)
    return jsonify({"queue": pl.work_queue(ents, pos), "positioned": len(pos), "entities": len(ents)}), 200


@app.route("/positions/resolve", methods=["POST"])
def positions_resolve():
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    rep = collector.resolve_places()
    store.add_changes(DB_PATH, rep.get("changes") or [])
    rep["changes"] = len(rep.get("changes") or [])
    return jsonify(rep), 200


@app.route("/entities/<path:key>/intervention", methods=["GET"])
def intervention(key):
    e = store.get_entity(DB_PATH, key)
    if not e:
        return jsonify({"error": "entité inconnue"}), 404
    places = {p["key"]: p for p in store.list_places(DB_PATH)}
    alias = getattr(collector, "_alias", {}) or {}
    pos = store.positions_map(DB_PATH)
    ents = {x["key"]: x for x in store.list_entities(DB_PATH, limit=100000)}
    incidents = store.list_incidents(DB_PATH, state="open", limit=500)   # ouverts + acquittés
    events = store.list_events(DB_PATH, state="open", limit=2000) + store.list_events(DB_PATH, state="acked", limit=2000)
    sheet = pl.intervention_sheet(e, pos.get(key), places, alias, store.list_relations(DB_PATH), incidents, events, ents, pos,
                                  notes=store.place_notes(DB_PATH), bastion_targets=_bastion_targets(e), tickets_url=TICKETS_URL)
    sheet["principles"] = [pr.evaluate(pid, store.feedback_counts(DB_PATH)) for pid in sorted({(pos.get(key) or {}).get("principle") or "pos-fallback", "unsupervised"})]
    return jsonify(sheet), 200


@app.route("/layers", methods=["GET"])
def layers_route():
    """Couches carto (GeoJSON) : positions, incidents (halos), density (par
    lieu), unsupervised, dependencies -- ?only=incidents,density pour n'en
    prendre que certaines."""
    ents = store.list_entities(DB_PATH, limit=100000)
    pos = store.positions_map(DB_PATH)
    incidents = store.list_incidents(DB_PATH, state="open", limit=500)   # ouverts + acquittés
    places = {p["key"]: p for p in store.list_places(DB_PATH)}
    out = pl.layers(ents, pos, incidents, store.list_relations(DB_PATH), places)
    only = request.args.get("only")
    if only:
        keep = set(only.split(",")) | {"summary"}
        out = {k: v for k, v in out.items() if k in keep}
    return jsonify(out), 200


# ---------------------------------------------------------------- apprentissage / anticipation / dérives (#465)
@app.route("/rules", methods=["GET"])
def rules_route():
    fb = store.feedback_counts(DB_PATH)
    eff = {pid: pr.evaluate(pid, fb)["effective"] for pid in ("sequence-learned", "sequence-confirmed")}
    names = store.entity_names(DB_PATH)
    out = []
    for r in store.list_rules(DB_PATH, state=request.args.get("state")):
        pid = "sequence-confirmed" if r["state"] == "confirmed" else "sequence-learned"
        r["a_text"], r["b_text"] = learn.describe_signature(r["a"], names), learn.describe_signature(r["b"], names)
        r["effective"] = 0.0 if r["state"] == "rejected" else learn.rule_confidence(r, eff[pid])
        r["principle"] = pid
        out.append(r)
    return jsonify({"rules": out, "counts": {s: sum(1 for r in out if r["state"] == s) for s in ("proposed", "confirmed", "rejected")}}), 200


@app.route("/rules/<path:rid>/<action>", methods=["POST"])
def rule_action(rid, action):
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    state = {"confirm": "confirmed", "reject": "rejected", "reset": "proposed"}.get(action)
    if not state:
        return jsonify({"error": "action : confirm | reject | reset"}), 400
    if not store.set_rule_state(DB_PATH, unquote(rid), state, by=body.get("by"), note=body.get("note")):
        return jsonify({"error": "règle inconnue"}), 404
    # une décision humaine sur une règle est aussi un retour sur le principe qui l'a proposée
    if action in ("confirm", "reject"):
        store.add_feedback(DB_PATH, "sequence-learned", "confirmed" if action == "confirm" else "rejected", claim=unquote(rid), by=body.get("by"), note=body.get("note"))
    return jsonify({"ok": True, "state": state}), 200


@app.route("/predictions", methods=["GET"])
def predictions_route():
    pending = request.args.get("pending") in ("1", "true")
    rows = store.list_predictions(DB_PATH, pending_only=pending, limit=request.args.get("limit", 200, type=int))
    for r in rows:
        r.pop("roles", None)
    return jsonify({"predictions": rows, "pending": sum(1 for r in rows if not r.get("outcome")),
                    "hits": sum(1 for r in rows if r.get("outcome") == "hit"), "misses": sum(1 for r in rows if r.get("outcome") == "miss")}), 200


@app.route("/drifts", methods=["GET"])
def drifts_route():
    """Dérives courantes = événements ouverts de source « cortex » ; plus les
    séries suivies (entité, métrique, nombre de relevés, dernier)."""
    evs = [e for e in store.list_events(DB_PATH, state="open", limit=2000) + store.list_events(DB_PATH, state="acked", limit=2000) if e.get("source") == "cortex"]
    series = store.series(DB_PATH)
    tracked = [{"entity": k[0], "metric": k[1], "label": learn.METRICS.get(k[1], {}).get("label", k[1]), "unit": learn.METRICS.get(k[1], {}).get("unit", ""),
                "points": len(v), "last_at": v[-1][0], "last": v[-1][1], "min": min(x[1] for x in v), "max": max(x[1] for x in v)} for k, v in series.items()]
    tracked.sort(key=lambda t: (t["entity"], t["metric"]))
    return jsonify({"drifts": evs, "tracked": tracked, "metrics": learn.METRICS}), 200


@app.route("/samples", methods=["GET"])
def samples_route():
    entity, metric = request.args.get("entity"), request.args.get("metric")
    series = store.series(DB_PATH, hours=request.args.get("hours", 26, type=int))
    pts = series.get((entity, metric), []) if entity and metric else []
    return jsonify({"entity": entity, "metric": metric, "points": [{"at": a, "value": v} for a, v in pts]}), 200


@app.route("/learn", methods=["POST"])
def learn_route():
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    return jsonify(collector.learn()), 200


# ---------------------------------------------------------------- politiques, silences, notifications, KPI (#466)
@app.route("/policies", methods=["GET"])
def policies_route():
    return jsonify({"policies": store.list_policies(DB_PATH), "channels": notify.describe(), "priorities": list(policy.PRIORITIES), "channel_names": list(policy.CHANNELS)}), 200


@app.route("/policies", methods=["PUT"])
def policy_put():
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    p, err = policy.validate_policy(body.get("policy") or {})
    if err:
        return jsonify({"error": err}), 400
    store.save_policy(DB_PATH, p, by=body.get("by"))
    return jsonify({"ok": True, "policy": p}), 200


@app.route("/policies/<path:pid>", methods=["DELETE"])
def policy_delete(pid):
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    return (jsonify({"ok": True}), 200) if store.delete_policy(DB_PATH, unquote(pid)) else (jsonify({"error": "politique inconnue"}), 404)


@app.route("/policies/preview", methods=["GET"])
def policies_preview():
    """Ce que les politiques décideraient maintenant (sans envoyer)."""
    return jsonify(collector.notify(dry_run=True)), 200


@app.route("/silences", methods=["GET"])
def silences_route():
    return jsonify({"silences": store.list_silences(DB_PATH), "now": store.now_iso()}), 200


@app.route("/silences", methods=["POST"])
def silence_add():
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    if not body.get("start_at") or not body.get("end_at") or body["end_at"] <= body["start_at"]:
        return jsonify({"error": "start_at et end_at (ISO UTC, fin après début) requis"}), 400
    target = {k: [str(x) for x in body.get(k) or []] for k in ("sites", "entities", "roles") if body.get(k)}
    sid = store.add_silence(DB_PATH, body.get("name") or "maintenance", body["start_at"], body["end_at"], target=target, ticket=body.get("ticket"), by=body.get("by"))
    return jsonify({"ok": True, "id": sid}), 201


@app.route("/silences/<int:sid>", methods=["DELETE"])
def silence_delete(sid):
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    return (jsonify({"ok": True}), 200) if store.delete_silence(DB_PATH, sid) else (jsonify({"error": "silence inconnu"}), 404)


@app.route("/notifications", methods=["GET"])
def notifications_route():
    return jsonify({"notifications": store.list_notifications(DB_PATH, limit=request.args.get("limit", 100, type=int)), "channels": notify.describe()}), 200


@app.route("/notify", methods=["POST"])
def notify_now():
    body = request.get_json(silent=True) or {}
    ok, why = _check_manage_right(body)
    if not ok:
        return jsonify({"error": why}), 403
    return jsonify(collector.notify()), 200


@app.route("/kpis", methods=["GET"])
def kpis_route():
    days = request.args.get("days", 30, type=int)
    ents = {e["key"]: e for e in store.list_entities(DB_PATH, limit=100000)}
    k = policy.compute_kpis(store.list_incidents(DB_PATH, state="all", limit=5000), ents, collector.roles_map(), store.positions_map(DB_PATH),
                            store.list_rules(DB_PATH), store.feedback_counts(DB_PATH), days=days)
    k["notifications"] = {"total": len(store.list_notifications(DB_PATH, limit=5000))}
    return jsonify(k), 200


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
