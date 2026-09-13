# -*- coding: utf-8 -*-
"""imap-connectors (livraison #489) — gestionnaire de connecteurs IMAP.

Demandé : « un gestionnaire de connecteur imap chacun sur une adresse
de réception pour plusieurs api : demandes SAV/Tickets/ProjeQTor,
alertes supervision Zenoss et autres, SMS entrants sur les passerelles
sms, notifications diverses — le tout avec log et base de données,
statistiques et vue pixelgrid ».

Chaque connecteur = une boîte (hôte, identifiants, dossier) + une
CIBLE (tickets | projeqtor | zenoss | sms | notification). La boucle
de relevé (poller) interroge les boîtes activées à leur rythme,
interprète chaque message non lu (interpreters.py), le route
(router.py) et journalise TOUT (store.py) : messages, livraisons,
erreurs. Un message dont le routage échoue reste NON LU — la boîte
fait office de file d'attente de secours.

UN SEUL worker Gunicorn (CMD du Dockerfile) : le poller est un thread
du processus — deux workers double-sonderaient les boîtes et se
voleraient les marquages « lu ». Les requêtes HTTP restent
concurrentes via les threads Gunicorn."""
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone

from flask import Flask, jsonify, request

import imap_fetch
import interpreters
import router
import store

DB_PATH = os.environ.get("IMAP_CONNECTORS_DB_PATH", "/data/imap-connectors.db")
POLL_TICK_SECONDS = int(os.environ.get("IMAP_CONNECTORS_POLL_TICK", "15"))

app = Flask(__name__)

try:
    from version_endpoint import register_version_route
    register_version_route(app, "imap-connectors")
except ImportError:
    pass  # tests sans le build (version_endpoint copié par le Dockerfile)

LOGS = deque(maxlen=300)
_POLLER_STARTED = False
_POLLER_LOCK = threading.Lock()


def _log(level, message):
    LOGS.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "level": level, "message": message})


# ---------------------------------------------------------------- poller

def poll_connector(connector, fetch=None, deliver_kw=None):
    """Un relevé d'une boîte : récupère les non lus, interprète, route,
    journalise. Retourne (nombre_pris_en_charge, erreur_éventuelle).
    `fetch` injectable (tests sans réseau)."""
    fetch = fetch or imap_fetch.fetch_unseen
    messages, error = fetch(connector)
    if error:
        store.report_poll(DB_PATH, connector["id"], False, error)
        _log("warning", "%s : relevé échoué — %s" % (connector["name"], error))
        return 0, error
    handled = 0
    last_at = None
    seen_nums = []
    for msg in messages:
        parsed = interpreters.parse_message(connector["target"], msg)
        message_id, is_new = store.record_message(DB_PATH, connector["id"], msg, parsed)
        if not is_new:
            continue  # déjà journalisé (relevé précédent, boîte non marquée)
        results = router.deliver(connector, parsed, **(deliver_kw or {}))
        all_ok = True
        for target, ok, detail in results:
            store.record_delivery(DB_PATH, message_id, target, ok, detail)
            all_ok = all_ok and ok
            if not ok:
                _log("warning", "%s : livraison %s échouée pour « %s » — %s"
                     % (connector["name"], target, (msg.get("subject") or "?")[:60], detail))
        handled += 1
        last_at = msg.get("date") or None
        # Marquage « lu » : message interprété ET routé (ou stockage
        # seul pour sms/notification). Un échec laisse le message non
        # lu — la boîte est la file de secours.
        if all_ok and parsed.get("ok") and connector.get("mark_seen", True):
            seen_nums.append(msg.get("_num"))
    if seen_nums:
        err = imap_fetch.mark_seen(connector, seen_nums)
        if err:
            _log("warning", "%s : marquage lu échoué — %s" % (connector["name"], err))
    store.report_poll(DB_PATH, connector["id"], True, None, last_at)
    if handled:
        _log("info", "%s : %d message(s) pris en charge" % (connector["name"], handled))
    return handled, None


def _poller_loop():
    """Boucle de fond : à chaque tick, relève les connecteurs activés
    dont l'intervalle est échu. Un connecteur en échec n'en bloque
    jamais un autre."""
    next_due = {}
    while True:
        try:
            for c in store.list_connectors(DB_PATH):
                if not c["enabled"]:
                    continue
                now = time.time()
                if next_due.get(c["id"], 0) > now:
                    continue
                next_due[c["id"]] = now + max(30, int(c.get("interval_seconds") or 300))
                try:
                    full = store.get_connector(DB_PATH, c["id"], with_secret=True)
                    poll_connector(full)
                except Exception as exc:  # jamais de crash du poller
                    _log("critical", "%s : relevé planté — %s" % (c["name"], exc))
        except Exception as exc:
            _log("critical", "poller : boucle en échec — %s" % exc)
        time.sleep(POLL_TICK_SECONDS)


def _start_poller():
    global _POLLER_STARTED
    with _POLLER_LOCK:
        if _POLLER_STARTED:
            return
        _POLLER_STARTED = True
    threading.Thread(target=_poller_loop, daemon=True).start()


# ---------------------------------------------------------------- API

@app.route("/health", methods=["GET"])
def health():
    connectors = store.list_connectors(DB_PATH)
    return jsonify({"status": "ok", "connectors": len(connectors),
                    "enabled": sum(1 for c in connectors if c["enabled"]),
                    "targets": interpreters.TARGETS}), 200


@app.route("/logs", methods=["GET"])
def logs():
    return jsonify({"logs": list(LOGS)[-100:]}), 200


@app.route("/connectors", methods=["GET"])
def list_route():
    return jsonify({"connectors": store.list_connectors(DB_PATH)}), 200


@app.route("/connectors", methods=["POST"])
def create_route():
    try:
        created = store.upsert_connector(DB_PATH, request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return jsonify({"error": "un connecteur de ce nom existe déjà"}), 409
        raise
    _log("info", "connecteur « %s » créé (cible %s)" % (created["name"], created["target"]))
    return jsonify(created), 201


@app.route("/connectors/<int:connector_id>", methods=["PUT"])
def update_route(connector_id):
    if store.get_connector(DB_PATH, connector_id) is None:
        return jsonify({"error": "connecteur inconnu"}), 404
    try:
        updated = store.upsert_connector(DB_PATH, request.get_json(silent=True) or {}, connector_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _log("info", "connecteur « %s » mis à jour" % updated["name"])
    return jsonify(updated), 200


@app.route("/connectors/<int:connector_id>", methods=["DELETE"])
def delete_route(connector_id):
    if not store.delete_connector(DB_PATH, connector_id):
        return jsonify({"error": "connecteur inconnu"}), 404
    _log("info", "connecteur %d supprimé (journal supprimé avec lui)" % connector_id)
    return jsonify({"status": "ok"}), 200


@app.route("/connectors/<int:connector_id>/test", methods=["POST"])
def test_route(connector_id):
    """Test de connexion réel (login + sélection du dossier), sans
    rien consommer : le diagnostic avant d'activer."""
    c = store.get_connector(DB_PATH, connector_id, with_secret=True)
    if c is None:
        return jsonify({"error": "connecteur inconnu"}), 404
    _, error = imap_fetch.fetch_unseen(c, limit=1)
    if error:
        return jsonify({"ok": False, "error": error}), 200
    return jsonify({"ok": True, "message": "connexion, login et dossier OK"}), 200


@app.route("/connectors/<int:connector_id>/run", methods=["POST"])
def run_route(connector_id):
    """Relevé immédiat (bouton « Relever maintenant » de la vue)."""
    c = store.get_connector(DB_PATH, connector_id, with_secret=True)
    if c is None:
        return jsonify({"error": "connecteur inconnu"}), 404
    handled, error = poll_connector(c)
    return jsonify({"handled": handled, "error": error}), 200


@app.route("/messages", methods=["GET"])
def messages_route():
    return jsonify({"messages": store.list_messages(
        DB_PATH,
        connector_id=request.args.get("connector_id", type=int),
        limit=request.args.get("limit", 100, type=int),
        only_errors=request.args.get("errors") == "1")}), 200


@app.route("/stats", methods=["GET"])
def stats_route():
    return jsonify(store.stats(DB_PATH, days=request.args.get("days", 30, type=int))), 200


store.ensure_schema(DB_PATH)
_start_poller()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
