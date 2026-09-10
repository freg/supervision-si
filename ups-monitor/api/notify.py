# -*- coding: utf-8 -*-
"""Notifications des alertes UPS (livraison #433) -- même esprit que
si-agent/api/notify.py : SMS et courriel par `shared/secrets_alert.py`
(variables SECRETS_ALERT_*), webhook `UPS_NOTIFY_WEBHOOK_URL`, seuil
`UPS_NOTIFY_MIN_SEVERITY` (warning ; `none` désactive), anti-tempête
`UPS_NOTIFY_COOLDOWN_SECONDS` (900) par (onduleur, genre), envoi en thread,
échec jamais bloquant, aucune valeur secrète tracée."""
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

try:
    import secrets_alert
except ImportError:  # copie partagée absente (tests hors conteneur)
    secrets_alert = None

_log = logging.getLogger("ups_monitor_notify")
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
_last_sent = {}
_lock = threading.Lock()


def _env(name, default=""):
    return os.environ.get(name, default).strip()


def channels():
    return {
        "sms": bool(_env("SECRETS_ALERT_SMS_URL") and _env("SECRETS_ALERT_SMS_KEY") and _env("SECRETS_ALERT_SMS_NUMBER") and secrets_alert),
        "email": bool(_env("SECRETS_ALERT_SMTP_HOST") and _env("SECRETS_ALERT_EMAIL_TO") and _env("SECRETS_ALERT_SMTP_FROM") and secrets_alert),
        "webhook": bool(_env("UPS_NOTIFY_WEBHOOK_URL")),
    }


def min_severity():
    v = _env("UPS_NOTIFY_MIN_SEVERITY", "warning").lower()
    return v if v in SEVERITY_ORDER or v == "none" else "warning"


def describe():
    try:
        cooldown = int(_env("UPS_NOTIFY_COOLDOWN_SECONDS", "900"))
    except ValueError:
        cooldown = 900
    return {"channels": channels(), "min_severity": min_severity(), "cooldown_seconds": cooldown, "any": any(channels().values()) and min_severity() != "none"}


def should_notify(device, alert, now=None, closing=False):
    if not device.get("notify", True):
        return False, "notifications désactivées pour cet onduleur"
    ms = min_severity()
    if ms == "none":
        return False, "notifications désactivées"
    if SEVERITY_ORDER.get(alert.get("severity"), 2) > SEVERITY_ORDER[ms]:
        return False, "sous le seuil %s" % ms
    if not any(channels().values()):
        return False, "aucun canal configuré"
    key = (device.get("id"), alert.get("kind"), "close" if closing else "open")
    now = now if now is not None else time.time()
    with _lock:
        last = _last_sent.get(key, 0)
        if now - last < describe()["cooldown_seconds"]:
            return False, "déjà notifié il y a %d s" % int(now - last)
        _last_sent[key] = now
    return True, "ok"


def send_all(device, alert, closing=False):
    import alerts  # noqa: PLC0415
    msg = alerts.format_message(device, alert, closing=closing)
    ch = channels()
    out = {}
    if ch["sms"]:
        out["sms"] = bool(secrets_alert.send_sms_alert(msg[:480]))
    if ch["email"]:
        body = "%s\n\nOnduleur : %s (%s)\nHôte : %s\nGenre : %s\nSévérité : %s\n\nDétails :\n%s\n" % (
            alert.get("message"), device.get("name"), device.get("site") or "-", device.get("host"), alert.get("kind"), alert.get("severity"),
            json.dumps(alert.get("details") or {}, indent=2, ensure_ascii=False))
        out["email"] = bool(secrets_alert.send_email_alert("[supervision-si] UPS %s : %s" % (device.get("name"), ("rétabli" if closing else alert.get("message", ""))[:80]), body))
    if ch["webhook"]:
        payload = json.dumps({"text": msg, "alert": alert, "ups": {"id": device.get("id"), "name": device.get("name"), "site": device.get("site"), "host": device.get("host")}, "closing": closing}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(_env("UPS_NOTIFY_WEBHOOK_URL"), data=payload, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                out["webhook"] = 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, ValueError) as exc:
            _log.warning("webhook UPS en échec : %s", exc)
            out["webhook"] = False
    out["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _log.info("notification UPS %s %s : %s", device.get("name"), alert.get("kind"), {k: v for k, v in out.items() if k != "at"})
    return out


def dispatch(db_path, device, alert, closing=False, threaded=True):
    ok, why = should_notify(device, alert, closing=closing)
    if not ok:
        _log.debug("alerte %s non notifiée : %s", alert.get("kind"), why)
        return None

    def _run():
        try:
            result = send_all(device, alert, closing=closing)
            if alert.get("id") is not None and not closing:
                import store  # noqa: PLC0415
                store.mark_alert_notified(db_path, alert["id"], result)
        except Exception as exc:  # noqa: BLE001
            _log.warning("notification UPS impossible : %s", exc)

    if threaded and _env("UPS_NOTIFY_SYNC", "0") != "1":
        threading.Thread(target=_run, daemon=True).start()
        return "queued"
    _run()
    return "sent"
