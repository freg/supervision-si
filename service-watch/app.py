# -*- coding: utf-8 -*-
"""service-watch-api (livraison #531, backlog item 80) -- supervision des
entrées de services vues d'Internet : inventaire (import d'une zone DNS ou
d'une liste de noms, registre versionné), qualification périodique (DNS,
ports, TLS, HTTP, page d'hébergeur), scénarios HTTP avec compte de test du
coffre, empreinte de contenu avec différence, canaris mail (SMTP -> IMAP),
constats -> événements -> notifications (secrets_alert). Page servie sous
/service-watch/. Aucun secret ici : les identifiants sont désignés par leur
nom dans le coffre credentials-api et révélés à l'usage seulement."""
import json
import logging
import os
import re
import sys
import threading
import time

import requests
from flask import Flask, jsonify, request, send_from_directory

import checks
import probe
import store

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
try:
    import secrets_alert
except ImportError:
    secrets_alert = None

log = logging.getLogger("service-watch")
logging.basicConfig(level=os.environ.get("SERVICE_WATCH_LOG_LEVEL", "INFO"))

DATA_DIR = os.environ.get("SERVICE_WATCH_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "service-watch.db")
REGISTRY = os.environ.get("SERVICE_WATCH_REGISTRY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "entries.json"))
INTERVAL_MIN = float(os.environ.get("SERVICE_WATCH_INTERVAL_MINUTES", "10") or 0)
CANARY_INTERVAL_MIN = float(os.environ.get("SERVICE_WATCH_CANARY_INTERVAL_MINUTES", "60") or 0)
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "").rstrip("/")
CREDENTIALS_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "").strip()
if CREDENTIALS_TOKEN == "change-me":
    CREDENTIALS_TOKEN = ""
NOTIFY_MIN = os.environ.get("SERVICE_WATCH_NOTIFY_MIN_SEVERITY", "warning")
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]{0,250}[a-z0-9])?$")
PREFIX = "/service-watch"

app = Flask(__name__, static_folder=None)
os.makedirs(DATA_DIR, exist_ok=True)
try:
    from version_endpoint import register_version_route
    register_version_route(app, "service-watch")
except Exception:  # noqa: BLE001
    pass
_lock = threading.Lock()
_status = {"last_cycle_at": None, "last_canary_at": None, "running": False, "errors": 0}


def _bad(msg, code=400):
    return jsonify({"error": msg}), code


# ---------------------------------------------------------------- coffre
def credentials_for(name):
    if not name:
        return None
    if not CREDENTIALS_API_URL or not CREDENTIALS_TOKEN:
        raise RuntimeError("coffre des accès non configuré (CREDENTIALS_INTERNAL_TOKEN)")
    r = requests.get("%s/credentials/reveal/%s" % (CREDENTIALS_API_URL, name), timeout=5,
                     headers={"X-Credentials-Token": CREDENTIALS_TOKEN, "X-Credentials-Consumer": "service-watch-api"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    b = r.json() or {}
    return (b.get("username") or "", b.get("password") or "")


# ---------------------------------------------------------------- registre
def load_registry(conn):
    """entries.json (versionné, sans secret) -> entrées source `registry`."""
    try:
        with open(REGISTRY, encoding="utf-8") as fh:
            reg = json.load(fh)
    except (OSError, ValueError) as exc:
        log.warning("registre illisible : %s", exc)
        return 0
    n = 0
    for e in reg.get("entries") or []:
        if not e.get("name") or not NAME_RE.match(e["name"].lower()):
            continue
        cfg = {k: v for k, v in e.items() if k != "name"}
        store.upsert_entry(conn, e["name"].lower(), source="registry", hint=e.get("hint"), config=cfg)
        n += 1
    for c in reg.get("canaries") or []:
        if c.get("name"):
            store.upsert_canary(conn, c["name"], {k: v for k, v in c.items() if k != "name"}, c.get("enabled", True))
    return n


# ---------------------------------------------------------------- passages
def notify(conn, subject, kind, severity, message):
    order = {"critical": 0, "warning": 1, "info": 2}
    sent = []
    if secrets_alert and order.get(severity, 2) <= order.get(NOTIFY_MIN, 1):
        try:
            if secrets_alert.send_email_alert("[service-watch] %s : %s" % (severity, subject), message):
                sent.append("email")
            if severity == "critical" and secrets_alert.send_sms_alert("[service-watch] %s" % message[:140]):
                sent.append("sms")
        except Exception as exc:  # noqa: BLE001
            log.warning("notification : %s", exc)
    store.add_event(conn, subject, kind, severity, message, ",".join(sent) or None)


def check_entry(conn, e):
    """Un passage complet sur une entrée : qualification, scénario, contenu, constats, événements."""
    cfg = e.get("config") or {}
    entry = dict(cfg, name=e["name"])
    prev = store.last_run(conn, e["name"])
    res = probe.qualify(entry)
    text = res.pop("_text", "")
    if cfg.get("scenario") and (res.get("http") or {}).get("status"):
        creds = {}
        for st in cfg["scenario"]:
            cname = (st.get("login") or {}).get("credential")
            if cname and cname not in creds:
                try:
                    up = credentials_for(cname)
                    if up:
                        creds[cname] = up
                except Exception as exc:  # noqa: BLE001
                    log.warning("coffre : %s", exc)
        res["scenario"] = probe.run_scenario(entry, cfg["scenario"], creds)
    if text:
        norm = checks.normalize_html(text, cfg.get("masks"))
        fp = checks.fingerprint(norm)
        ref = store.content_ref(conn, e["name"])
        if not ref:
            store.set_content_ref(conn, e["name"], fp, norm, "auto")
            res["content_diff"] = {"change_pct": 0.0, "lines": [], "reference_at": store.now_iso(), "new_reference": True}
        else:
            d = checks.content_diff(ref["text"], norm) if ref["fingerprint"] != fp else {"change_pct": 0.0, "lines": []}
            d["reference_at"] = ref["at"]
            res["content_diff"] = d
        res["content_fingerprint"] = fp
    alerts = checks.evaluate_entry(entry, res, prev=(prev or {}).get("result"))
    state = checks.summarize(alerts)["state"]
    at = store.add_run(conn, e["name"], res, alerts, state)
    new, gone = store.alert_changes((prev or {}).get("alerts"), alerts)
    if new:
        sev = "critical" if any(a["severity"] == "critical" for a in new) else "warning"
        notify(conn, e["name"], "entry-alert", sev, " ; ".join(a["message"] for a in new))
    if gone:
        notify(conn, e["name"], "entry-recovered", "info", "%s : fin de %s" % (e["name"], ", ".join("« %s »" % a["code"] for a in gone)))
    return {"at": at, "state": state, "alerts": alerts, "result": res}


def run_canary(conn, c):
    cfg = c["config"]
    token = probe.new_token()
    result = {"token": token, "sent_at": store.now_iso()}
    try:
        smtp = credentials_for(cfg.get("smtp_credential")) if cfg.get("smtp_credential") else ("", "")
        imap = credentials_for(cfg.get("imap_credential"))
    except Exception as exc:  # noqa: BLE001
        result["send_error"] = "coffre : %s" % exc
        smtp = imap = None
    if smtp is None and cfg.get("smtp_credential"):
        result["send_error"] = "compte SMTP « %s » absent du coffre" % cfg.get("smtp_credential")
    elif imap is None:
        result["send_error"] = "compte IMAP « %s » absent du coffre" % cfg.get("imap_credential")
    if not result.get("send_error"):
        mid, err = probe.canary_send(cfg, smtp[0], smtp[1], token)
        if err:
            result["send_error"] = err
        else:
            result["message_id"] = mid
            result.update(probe.canary_wait(cfg, imap[0], imap[1], token, wait_s=int(cfg.get("wait_s") or 300), poll_s=int(cfg.get("poll_s") or 20), delete=cfg.get("delete", True)))
    alerts = checks.evaluate_canary(dict(cfg, name=c["name"]), result)
    state = checks.summarize(alerts)["state"]
    prev = store.last_canary_run(conn, c["name"])
    at = store.add_canary_run(conn, c["name"], result, alerts, state)
    new, gone = store.alert_changes((prev or {}).get("alerts"), alerts)
    if new:
        notify(conn, c["name"], "canary-alert", "critical" if any(a["severity"] == "critical" for a in new) else "warning", " ; ".join(a["message"] for a in new))
    if gone:
        notify(conn, c["name"], "canary-recovered", "info", "%s : canari revenu à la normale" % c["name"])
    return {"at": at, "state": state, "alerts": alerts, "result": result}


def cycle(what="entries"):
    with _lock:
        _status["running"] = True
        conn = store.connect(DB_PATH)
        try:
            if what in ("entries", "all"):
                for e in store.list_entries(conn, include_gone=False):
                    if e["config"].get("enabled", True):
                        try:
                            check_entry(conn, e)
                        except Exception as exc:  # noqa: BLE001
                            _status["errors"] += 1
                            log.warning("passage %s : %s", e["name"], exc)
                        conn.commit()
                _status["last_cycle_at"] = store.now_iso()
            if what in ("canaries", "all"):
                for c in store.list_canaries(conn):
                    if c["enabled"]:
                        try:
                            run_canary(conn, c)
                        except Exception as exc:  # noqa: BLE001
                            _status["errors"] += 1
                            log.warning("canari %s : %s", c["name"], exc)
                        conn.commit()
                _status["last_canary_at"] = store.now_iso()
        finally:
            conn.close()
            _status["running"] = False


def scheduler():
    time.sleep(15)
    last_e = last_c = 0.0
    while True:
        now = time.monotonic()
        try:
            if INTERVAL_MIN > 0 and now - last_e >= INTERVAL_MIN * 60:
                last_e = now; cycle("entries")
            if CANARY_INTERVAL_MIN > 0 and now - last_c >= CANARY_INTERVAL_MIN * 60:
                last_c = now; cycle("canaries")
        except Exception as exc:  # noqa: BLE001
            log.warning("planificateur : %s", exc)
        time.sleep(30)


if os.environ.get("SERVICE_WATCH_SCHEDULER", "1") == "1":
    with store.connect(DB_PATH) as _c:
        load_registry(_c); _c.commit()
    threading.Thread(target=scheduler, daemon=True).start()


# ---------------------------------------------------------------- routes
@app.route(PREFIX + "/", methods=["GET"])
def index():
    return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"), "index.html")


@app.route(PREFIX + "/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route(PREFIX + "/status", methods=["GET"])
def status():
    conn = store.connect(DB_PATH)
    try:
        entries = store.list_entries(conn)
        canaries = store.list_canaries(conn)
    finally:
        conn.close()
    counts = {"entries": len([e for e in entries if not e.get("gone_at")]), "gone": len([e for e in entries if e.get("gone_at")]),
              "critical": len([e for e in entries if e.get("state") == "critical" and not e.get("gone_at")]),
              "warning": len([e for e in entries if e.get("state") == "warning" and not e.get("gone_at")]),
              "canaries": len(canaries)}
    return jsonify(dict(_status, counts=counts, interval_minutes=INTERVAL_MIN, canary_interval_minutes=CANARY_INTERVAL_MIN,
                        credentials=bool(CREDENTIALS_API_URL and CREDENTIALS_TOKEN), notify=bool(secrets_alert))), 200


@app.route(PREFIX + "/entries", methods=["GET"])
def entries():
    conn = store.connect(DB_PATH)
    try:
        out = []
        for e in store.list_entries(conn):
            lr = store.last_run(conn, e["name"])
            e["last"] = {"at": lr["at"], "state": lr["state"], "alerts": lr["alerts"], "kind": lr["result"].get("kind"),
                         "ips": lr["result"].get("ips"), "open_ports": lr["result"].get("open_ports"),
                         "http": lr["result"].get("http"), "tls": lr["result"].get("tls")} if lr else None
            out.append(e)
    finally:
        conn.close()
    return jsonify({"entries": out}), 200


@app.route(PREFIX + "/entries", methods=["POST"])
def add_entry():
    b = request.get_json(silent=True) or {}
    name = (b.get("name") or "").strip().lower().rstrip(".")
    if not NAME_RE.match(name) or "." not in name:
        return _bad("nom de service invalide")
    cfg = {k: v for k, v in b.items() if k in ("ports", "url", "expected", "scenario", "masks", "max_ms", "diff_threshold_pct", "kind_override", "enabled", "expect_url", "notes")}
    conn = store.connect(DB_PATH)
    try:
        created = store.upsert_entry(conn, name, source="manual", config=cfg)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"name": name, "created": created}), 201 if created else 200


@app.route(PREFIX + "/entries/<name>", methods=["DELETE"])
def del_entry(name):
    conn = store.connect(DB_PATH)
    try:
        store.delete_entry(conn, name.lower()); conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": name}), 200


@app.route(PREFIX + "/entries/<name>/runs", methods=["GET"])
def entry_runs(name):
    conn = store.connect(DB_PATH)
    try:
        runs = store.list_runs(conn, name.lower(), limit=min(int(request.args.get("limit") or 50), 500))
        ref = store.content_ref(conn, name.lower())
    finally:
        conn.close()
    return jsonify({"runs": runs, "reference": {"at": ref["at"], "fingerprint": ref["fingerprint"], "validated_by": ref["validated_by"]} if ref else None}), 200


@app.route(PREFIX + "/entries/<name>/check", methods=["POST"])
def entry_check(name):
    conn = store.connect(DB_PATH)
    try:
        e = store.get_entry(conn, name.lower())
        if not e:
            return _bad("entrée inconnue", 404)
        out = check_entry(conn, e); conn.commit()
    finally:
        conn.close()
    return jsonify(out), 200


@app.route(PREFIX + "/entries/<name>/reference", methods=["POST"])
def entry_reference(name):
    """Valider le contenu courant comme nouvelle référence (déploiement légitime) -- journalisé."""
    conn = store.connect(DB_PATH)
    try:
        lr = store.last_run(conn, name.lower())
        fp = (lr or {}).get("result", {}).get("content_fingerprint")
        if not lr or not fp:
            return _bad("aucun contenu mesuré pour cette entrée", 404)
        e = store.get_entry(conn, name.lower())
        h = probe.http_get((e["config"].get("url") or "https://%s/" % name.lower()))
        norm = checks.normalize_html(h.get("text") or "", e["config"].get("masks"))
        who = (request.headers.get("X-Forwarded-User") or request.remote_addr or "?")[:80]
        store.set_content_ref(conn, name.lower(), checks.fingerprint(norm), norm, who)
        store.add_event(conn, name.lower(), "reference-validated", "info", "%s : nouvelle référence de contenu validée par %s" % (name.lower(), who))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"validated": name.lower()}), 200


@app.route(PREFIX + "/import", methods=["POST"])
def import_zone():
    """Zone BIND ou liste de noms (texte) -> entrées source `dns` ; les noms
    absents d'un import précédent de la même origine sont marqués disparus."""
    b = request.get_json(silent=True) or {}
    text = b.get("text") or ""
    origin = (b.get("origin") or "").strip().lower()
    cands = checks.parse_zone(text, origin)
    conn = store.connect(DB_PATH)
    try:
        created = 0
        for c in cands:
            if store.upsert_entry(conn, c["name"], source="dns", dns_type=c["type"], target=c["target"], hint=c["hint"]):
                created += 1
        gone = store.mark_gone(conn, "dns", {c["name"] for c in cands}) if b.get("replace") else []
        for g in gone:
            store.add_event(conn, g, "entry-gone", "warning", "%s : disparu de la zone DNS importée" % g)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"candidates": len(cands), "created": created, "gone": gone, "names": [c["name"] for c in cands]}), 200


@app.route(PREFIX + "/canaries", methods=["GET"])
def canaries():
    conn = store.connect(DB_PATH)
    try:
        out = store.list_canaries(conn)
    finally:
        conn.close()
    return jsonify({"canaries": out}), 200


@app.route(PREFIX + "/canaries", methods=["POST"])
def add_canary():
    b = request.get_json(silent=True) or {}
    name = (b.get("name") or "").strip()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,63}$", name):
        return _bad("nom de canari invalide")
    cfg = {k: v for k, v in b.items() if k in ("to", "from", "smtp_host", "smtp_port", "smtp_starttls", "smtp_credential", "imap_host", "imap_port", "imap_ssl", "imap_folder", "imap_credential", "wait_s", "poll_s", "max_delay_s", "delete", "notes")}
    if not cfg.get("to") or not cfg.get("smtp_host") or not cfg.get("imap_host") or not cfg.get("imap_credential"):
        return _bad("champs requis : to, smtp_host, imap_host, imap_credential (nom dans le coffre)")
    conn = store.connect(DB_PATH)
    try:
        store.upsert_canary(conn, name, cfg, b.get("enabled", True)); conn.commit()
    finally:
        conn.close()
    return jsonify({"name": name}), 201


@app.route(PREFIX + "/canaries/<name>", methods=["DELETE"])
def del_canary(name):
    conn = store.connect(DB_PATH)
    try:
        store.delete_canary(conn, name); conn.commit()
    finally:
        conn.close()
    return jsonify({"deleted": name}), 200


@app.route(PREFIX + "/canaries/<name>/run", methods=["POST"])
def canary_run_now(name):
    conn = store.connect(DB_PATH)
    try:
        c = next((x for x in store.list_canaries(conn) if x["name"] == name), None)
        if not c:
            return _bad("canari inconnu", 404)
        out = run_canary(conn, c); conn.commit()
    finally:
        conn.close()
    return jsonify(out), 200


@app.route(PREFIX + "/canaries/<name>/runs", methods=["GET"])
def canary_runs(name):
    conn = store.connect(DB_PATH)
    try:
        runs = store.list_canary_runs(conn, name, limit=min(int(request.args.get("limit") or 50), 300))
    finally:
        conn.close()
    return jsonify({"runs": runs}), 200


@app.route(PREFIX + "/events", methods=["GET"])
def events():
    conn = store.connect(DB_PATH)
    try:
        out = store.list_events(conn, limit=min(int(request.args.get("limit") or 200), 2000))
    finally:
        conn.close()
    return jsonify({"events": out}), 200


@app.route(PREFIX + "/cycle", methods=["POST"])
def cycle_now():
    what = (request.get_json(silent=True) or {}).get("what") or "entries"
    if _status["running"]:
        return _bad("un passage est déjà en cours", 409)
    threading.Thread(target=cycle, args=(what,), daemon=True).start()
    return jsonify({"started": what}), 202


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
