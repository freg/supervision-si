# -*- coding: utf-8 -*-
"""Rapports et alertes des anomalies réseau (livraison #703) -- routes et
boucle de contrôle, branchées sur nebula-api par `register(app, hooks)`.

- GET  /report/settings            réglages + état (prochain récapitulatif, anomalies suivies, journal)
- PUT  /report/settings            {settings, groups, user} (droit `manage`)
- GET  /report/anomalies?format=csv|xlsx|pdf|json&site=<id>|all&hidden=1
- POST /report/send                {kind: daily|test, groups, user} (droit `manage`) : envoi immédiat
- boucle (un seul worker, verrou fichier) : toutes les `check_minutes`, suivi des
  anomalies, alertes d'urgence après le délai, retour à la normale,
  récapitulatif à l'heure et aux jours choisis. Envoi par notify-api
  (destinataires du réglage + groupes de l'action ; pièces jointes)."""
import json
import os
import threading
import time
from datetime import datetime

from flask import Response, jsonify, request

import alerting
import report

try:
    import notify_client
except ImportError:  # pragma: no cover
    notify_client = None

ACTIONS = [{"id": "nebula.anomalie-urgente", "label": "Anomalie réseau persistante (alerte d'urgence)", "severity": "critical"},
           {"id": "nebula.retour-normale", "label": "Anomalie réseau résolue après alerte", "severity": "info"},
           {"id": "nebula.recapitulatif", "label": "Récapitulatif quotidien des anomalies réseau", "severity": "info"}]
MIME = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}

_hooks = {}


def kv_get(key, default=None):
    conn = _hooks["conn"]()
    try:
        r = conn.execute("SELECT value FROM nebula_report_kv WHERE key = ?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default
    finally:
        conn.close()


def kv_set(key, value):
    conn = _hooks["conn"]()
    try:
        conn.execute("INSERT INTO nebula_report_kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def settings():
    return alerting.normalize(kv_get("settings", {}))


def log(event, text):
    entries = kv_get("log", [])
    entries.append({"at": int(time.time()), "event": event, "text": str(text)[:400]})
    kv_set("log", entries[-50:])


def collect(cfg, site=None, refresh=False, include_hidden=False):
    """-> (lignes, erreurs par site) pour tous les sites (ou ceux du réglage, ou `site`)."""
    sites = _hooks["sites"]()
    names = {s.get("siteId"): s.get("name") or s.get("siteId") for s in sites}
    wanted = [site] if site and site != "all" else ([s for s in cfg["sites"] if s in names] or list(names))
    items, errors = {}, {}
    for sid in wanted:
        try:
            items[sid], _e, _m = _hooks["anomalies"](sid, refresh)
        except Exception as exc:  # noqa: BLE001 -- un site en erreur n'empêche pas les autres
            errors[names.get(sid, sid)] = str(exc)[:200]
    state = kv_get("state", {})
    return report.rows_from(items, names, alerting.first_seen_map(state), include_hidden), errors


def _files(rows, formats, title, now):
    stamp = now.strftime("%Y-%m-%d")
    out = []
    for f in formats:
        data = report.to_csv(rows) if f == "csv" else report.to_xlsx(rows, title, now) if f == "xlsx" else report.to_pdf(rows, title, now)
        out.append(("anomalies-reseau-%s.%s" % (stamp, f), MIME[f], data))
    return out


def send_daily(cfg, now=None, test=False):
    now = now or datetime.now()
    rows, errors = collect(cfg, refresh=True)
    rows = [r for r in rows if alerting.severity_ok(r["severity"], cfg["daily"]["min_severity"])]
    if cfg["daily"]["only_if_anomalies"] and not rows and not test:
        log("daily-skip", "récapitulatif non envoyé : aucune anomalie")
        return {"status": "skipped"}
    title = "Récapitulatif réseau du %s" % now.strftime("%d/%m/%Y")
    body = report.text_summary(rows, title)
    resolved = alerting.resolved_since(kv_get("state", {}), time.time() - 86400)
    if resolved:
        body += "\n\nRésolues depuis 24 h :\n" + "\n".join("  ✓ %s — %s" % (e.get("site"), e.get("message")) for e in resolved[:30])
    if errors:
        body += "\n\nSites non relus : " + "; ".join("%s (%s)" % kv for kv in errors.items())
    res = _notify("nebula.recapitulatif", "%s%s : %d anomalie(s)" % ("[TEST] " if test else "", title, len(rows)), body, cfg,
                  attachments=_files(rows, cfg["daily"]["formats"], title, now), severity="info")
    log("daily-test" if test else "daily", "%d anomalie(s), %s" % (len(rows), _res_text(res)))
    return res


def _res_text(res):
    if not res:
        return "notify-api injoignable ou non configuré (NOTIFY_API_URL / NOTIFY_INTERNAL_TOKEN)"
    return "%s, %s destinataire(s)%s" % (res.get("status"), res.get("recipients"), (" : " + res["reason"]) if res.get("reason") else "")


def _notify(action, subject, body, cfg, attachments=None, severity=None):
    if notify_client is None:
        return None
    return notify_client.notify(action, subject, body, context={"module": "nebula"}, severity=severity, wait=True,
                                to=cfg["recipients"], attachments=attachments)


def check_once(now_ts=None, now_dt=None):
    """Un passage : suivi, alertes d'urgence, retour à la normale, récapitulatif si dû."""
    cfg = settings()
    now_ts = now_ts or time.time()
    now_dt = now_dt or datetime.now()
    out = {"urgent": 0, "recovered": 0, "daily": None}
    if cfg["urgent"]["enabled"] or cfg["daily"]["enabled"]:
        rows, errors = collect(cfg, refresh=True)
        state, urgent, recovered = alerting.track(kv_get("state", {}), rows, now_ts, cfg["urgent"])
        kv_set("state", state)
        if urgent:
            sites = sorted({u["site"] for u in urgent})
            body = report.text_summary([dict(u, since=datetime.fromtimestamp(u["first_seen"]).strftime("%d/%m/%Y %H:%M")) for u in urgent],
                                       "Anomalie(s) réseau persistante(s) depuis au moins %d min" % cfg["urgent"]["delay_minutes"])
            res = _notify("nebula.anomalie-urgente", "Anomalie réseau : %d anomalie(s) %s — %s" % (len(urgent), cfg["urgent"]["min_severity"] + " ou plus", ", ".join(sites)),
                          body, cfg, severity="critical")
            log("urgent", "%d anomalie(s) : %s" % (len(urgent), _res_text(res)))
            out["urgent"] = len(urgent)
        if recovered:
            body = "Retour à la normale :\n\n" + "\n".join("  ✓ %s — %s (alerte du %s)" % (e.get("site"), e.get("message"), datetime.fromtimestamp(e["notified_at"]).strftime("%d/%m %H:%M"))
                                                        for e in recovered)
            res = _notify("nebula.retour-normale", "Réseau : %d anomalie(s) résolue(s)" % len(recovered), body, cfg, severity="info")
            log("recovered", "%d anomalie(s) : %s" % (len(recovered), _res_text(res)))
            out["recovered"] = len(recovered)
        if errors:
            log("error", "sites non relus : %s" % "; ".join("%s (%s)" % kv for kv in errors.items()))
    if alerting.daily_due(cfg["daily"], kv_get("daily_last"), now_dt):
        kv_set("daily_last", now_dt.timestamp())          # avant l'envoi : jamais deux récapitulatifs pour un créneau
        out["daily"] = send_daily(cfg, now_dt)
    return out


def _loop(lock_dir):
    import fcntl
    try:
        fh = open(os.path.join(lock_dir, "nebula-report.lock"), "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    time.sleep(30)
    while True:
        try:
            if _hooks["configured"]():
                check_once()
        except Exception as exc:  # noqa: BLE001 -- la boucle ne meurt jamais
            try:
                log("error", "contrôle en échec : %s" % exc)
            except Exception:  # noqa: BLE001
                pass
        try:
            minutes = settings()["check_minutes"]
        except Exception:  # noqa: BLE001
            minutes = 10
        time.sleep(minutes * 60)


def register(app, hooks, start_loop=True):
    """hooks : conn() -> sqlite ; sites() -> inventaire ; anomalies(site, refresh) -> (items, errors, vmap) ;
    manage(body) -> (ok, err) ; configured() -> bool ; lock_dir."""
    _hooks.update(hooks)
    conn = hooks["conn"]()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS nebula_report_kv (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
    finally:
        conn.close()

    @app.route("/report/settings", methods=["GET"])
    def report_settings_get():
        cfg = settings()
        state = kv_get("state", {})
        nd = alerting.next_daily(cfg["daily"], datetime.now())
        tracked = sorted((state.get("open") or {}).values(), key=lambda e: (alerting.SEV_ORDER.get(e.get("severity"), 9), e.get("first_seen", 0)))
        return jsonify({"settings": cfg, "next_daily": nd.isoformat(timespec="minutes") if nd else None, "daily_last": kv_get("daily_last"),
                        "tracked": tracked[:200], "resolved_24h": alerting.resolved_since(state, time.time() - 86400)[-50:], "log": list(reversed(kv_get("log", [])))[:30],
                        "notify_configured": bool(os.environ.get("NOTIFY_API_URL") and os.environ.get("NOTIFY_INTERNAL_TOKEN"))}), 200

    @app.route("/report/settings", methods=["PUT"])
    def report_settings_put():
        body = request.get_json(silent=True) or {}
        ok, err = hooks["manage"](body)
        if not ok:
            return jsonify({"error": err}), 403
        raw = body.get("settings") or {}
        bad = alerting.invalid_recipients(raw.get("recipients"))
        if bad:
            return jsonify({"error": "adresse(s) invalide(s) : %s" % ", ".join(bad[:5])}), 400
        cfg = alerting.normalize(raw)
        kv_set("settings", cfg)
        log("settings", "réglages modifiés par %s" % (body.get("user") or "?"))
        return jsonify({"settings": cfg}), 200

    @app.route("/report/anomalies", methods=["GET"])
    def report_anomalies():
        fmt = request.args.get("format", "json")
        try:
            rows, errors = collect(settings(), site=request.args.get("site"), refresh=request.args.get("refresh") == "1",
                                   include_hidden=request.args.get("hidden") == "1")
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)[:300]}), 502
        now = datetime.now()
        title = "Anomalies réseau — %s" % now.strftime("%d/%m/%Y %H:%M")
        if fmt in MIME:
            name, mime, data = _files(rows, [fmt], title, now)[0]
            return Response(data, mimetype=mime, headers={"Content-Disposition": "attachment; filename=%s" % name})
        return jsonify({"rows": rows, "counts": report.counts(rows), "errors": errors}), 200

    @app.route("/report/send", methods=["POST"])
    def report_send():
        body = request.get_json(silent=True) or {}
        ok, err = hooks["manage"](body)
        if not ok:
            return jsonify({"error": err}), 403
        cfg = settings()
        if not cfg["recipients"]:
            return jsonify({"error": "aucun destinataire dans les réglages"}), 400
        res = send_daily(cfg, test=body.get("kind") != "daily")
        if not res:
            return jsonify({"error": _res_text(res)}), 502
        return jsonify(res), 200

    if notify_client is not None:
        notify_client.register_actions(ACTIONS)
    if start_loop:
        threading.Thread(target=_loop, args=(hooks["lock_dir"],), name="nebula-report", daemon=True).start()
