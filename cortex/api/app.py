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
import normalize as nz
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
        "classifier": os.environ.get("CLASSIFIER_API_URL", ""), "nebula": os.environ.get("NEBULA_API_URL", ""), "ipam": os.environ.get("IPAM_API_URL", "")}
WINDOW_S = int(os.environ.get("CORTEX_WINDOW_SECONDS", "300"))
INTERVAL_S = int(os.environ.get("CORTEX_INTERVAL_SECONDS", "300"))
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None
collector = collectors.Collector(DB_PATH, URLS, window_s=WINDOW_S, horizon_h=int(os.environ.get("CORTEX_EVENT_HORIZON_HOURS", "24")))
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


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
