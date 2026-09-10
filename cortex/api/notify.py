# -*- coding: utf-8 -*-
"""Canaux de notification de Cortex (livraison #466) -- UNE notification par
incident et par moment (ouverture, escalade, résolution), décidée par
policy.plan_notifications ; ici seulement l'envoi.

Canaux : SMS et courriel par la COPIE de `shared/secrets_alert.py` (mêmes
variables `SECRETS_ALERT_*` que le PRA, si-agent et UPS -- jamais une
seconde implémentation), webhook HTTP `CORTEX_NOTIFY_WEBHOOK_URL` (POST
JSON {text, incident, kind, priority}). `CORTEX_NOTIFY=0` coupe tout
(les décisions restent journalisées comme « non envoyées »). Aucune
valeur de clé ni de mot de passe dans les traces -- seule leur présence.
"""
import json
import logging
import os
import time
import urllib.error
import urllib.request

try:
    import secrets_alert
except ImportError:  # dépôt de développement
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared"))
    try:
        import secrets_alert
    except ImportError:
        secrets_alert = None

_log = logging.getLogger("cortex.notify")


def _env(name, default=""):
    return os.environ.get(name, default).strip()


def enabled():
    return _env("CORTEX_NOTIFY", "1") not in ("0", "false", "no", "none")


def channels():
    """Canaux configurés (présence des variables, jamais leurs valeurs)."""
    return {
        "sms": bool(_env("SECRETS_ALERT_SMS_URL") and _env("SECRETS_ALERT_SMS_KEY") and _env("SECRETS_ALERT_SMS_NUMBER")),
        "email": bool(_env("SECRETS_ALERT_SMTP_HOST") and _env("SECRETS_ALERT_EMAIL_TO") and _env("SECRETS_ALERT_SMTP_FROM")),
        "webhook": bool(_env("CORTEX_NOTIFY_WEBHOOK_URL")),
    }


def describe():
    ch = channels()
    return {"enabled": enabled(), "channels": ch, "any": enabled() and any(ch.values())}


def send(plan_item, incident):
    """Envoi synchrone sur les canaux du plan ; -> {canal: bool, at}."""
    out = {}
    msg = plan_item["message"]
    if not enabled():
        for c in plan_item["channels"]:
            out[c] = False
        out["disabled"] = True
        out["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return out
    ch = channels()
    for c in plan_item["channels"]:
        if c == "sms" and ch["sms"] and secrets_alert:
            out["sms"] = bool(secrets_alert.send_sms_alert(msg[:480]))
        elif c == "email" and ch["email"] and secrets_alert:
            body = "%s\n\nIncident : %s\nSévérité : %s\nCause proposée : %s\nEntités : %s\nOuvert : %s\nPolitique : %s\n\nHypothèses :\n%s\n" % (
                msg, incident.get("key"), incident.get("severity"), incident.get("root"), ", ".join(incident.get("entities") or []), incident.get("opened_at"),
                plan_item.get("policy"), "\n".join("- %s (%d %%, %s)" % (h.get("claim"), int((h.get("confidence") or 0) * 100), h.get("principle")) for h in incident.get("hypotheses") or []))
            out["email"] = bool(secrets_alert.send_email_alert("[supervision-si] cortex %s : %s" % (plan_item["kind"], (incident.get("title") or "")[:80]), body))
        elif c == "webhook" and ch["webhook"]:
            out["webhook"] = _post_webhook(_env("CORTEX_NOTIFY_WEBHOOK_URL"), plan_item, incident, msg)
        else:
            out[c] = False
    out["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _log.info("notification %s incident %s : %s", plan_item["kind"], incident.get("key"), {k: v for k, v in out.items() if k != "at"})
    return out


def _post_webhook(url, plan_item, incident, text, timeout=10):
    payload = json.dumps({"text": text, "kind": plan_item["kind"], "priority": plan_item.get("priority"), "policy": plan_item.get("policy"),
                          "incident": {k: incident.get(k) for k in ("key", "severity", "state", "title", "root", "entities", "confidence", "opened_at", "hypotheses")}},
                         ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _log.warning("webhook de notification en échec : %s", exc)
        return False
