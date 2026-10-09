"""Notifications du central si-agent-api (livraison #422/#423) -- un
événement d'une sévérité suffisante part vers les canaux configurés :

  - SMS (passerelle trb140-sms-relay) et courriel (SMTP) : par la COPIE de
    `shared/secrets_alert.py` (canaux déjà éprouvés par le PRA #206), mêmes
    variables `SECRETS_ALERT_*`, jamais une seconde implémentation ;
  - webhook HTTP (`SI_AGENT_NOTIFY_WEBHOOK_URL`, POST JSON) : vers n8n,
    Mattermost, un ticket... ;
  - le journal lui-même (toujours) : la tuile du hub montre qui a été
    notifié de quoi.

Garde-fous : seuil `SI_AGENT_NOTIFY_MIN_SEVERITY` (warning par défaut ;
`none` désactive), anti-tempête `SI_AGENT_NOTIFY_COOLDOWN_SECONDS` (même
genre + même agent pas renotifié avant N s, 900 par défaut), envoi en
thread pour ne jamais ralentir la face agents, échec d'un canal jamais
bloquant (best-effort, tracé). Aucune valeur de clé ou de mot de passe
dans les traces -- seule leur présence.
"""
import json
import logging
import os
import re
import threading
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

try:   # #716 : relais vers notify-api (groupes, affectation par action, file d'envoi)
    import notify_client
except ImportError:
    try:
        import sys as _sys2
        _sys2.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared"))
        import notify_client
    except ImportError:
        notify_client = None

_log = logging.getLogger("si_agent_notify")

# #716 : genres d'événements relayés à notify-api (action « si-agent.<genre> ») -- au-delà, warning et critical.
HUB_ACTIONS = [
    {"id": "si-agent.backup-alert", "label": "Sauvegarde en échec, en retard ou fichier disparu", "severity": "warning"},
    {"id": "si-agent.backup-recovered", "label": "Sauvegarde de nouveau à jour", "severity": "info"},
    {"id": "si-agent.backup-done", "label": "Sauvegarde réussie (tâches marquées notify_ok)", "severity": "info"},
    {"id": "si-agent.probe-alert", "label": "Constat d'une sonde d'agent", "severity": "warning"},
    {"id": "si-agent.agent-offline", "label": "Agent hors ligne", "severity": "warning"},
]
ALWAYS_RELAY = {"backup-alert", "backup-recovered", "backup-done"}


def hub_action(event):
    """Action notify-api d'un événement, ou None s'il n'est pas relayé (pur)."""
    kind = str(event.get("kind") or "")
    if not re.match(r"^[a-z0-9][a-z0-9_-]{0,60}$", kind):
        return None
    if kind in ALWAYS_RELAY or (event.get("severity") or "info") in ("warning", "critical"):
        return "si-agent." + kind
    return None


def relay_to_hub(event, client=None):
    """Envoie l'événement à notify-api (non bloquant, jamais d'exception) ; renvoie l'action ou None."""
    client = client or notify_client
    action = hub_action(event)
    if not action or client is None or not os.environ.get("NOTIFY_API_URL"):
        return None
    body = "%s\n\nAgent : %s\nSite : %s\nSévérité : %s\nQuand : %s\n\nDétails :\n%s\n" % (
        event.get("message"), event.get("agent_id") or "-", event.get("site") or "-", event.get("severity"), event.get("at"),
        json.dumps(event.get("details") or {}, indent=2, ensure_ascii=False))
    try:
        client.notify(action, "[supervision-si] %s" % str(event.get("message") or action)[:150], body,
                      context={"agent_id": event.get("agent_id"), "kind": event.get("kind")}, severity=event.get("severity"))
    except Exception as exc:  # noqa: BLE001
        _log.warning("relais notify-api impossible : %s", exc)
        return None
    return action
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
_last_sent = {}
_lock = threading.Lock()


def _env(name, default=""):
    return os.environ.get(name, default).strip()


def min_severity():
    v = _env("SI_AGENT_NOTIFY_MIN_SEVERITY", "warning").lower()
    return v if v in SEVERITY_ORDER or v == "none" else "warning"


def cooldown_seconds():
    try:
        return int(_env("SI_AGENT_NOTIFY_COOLDOWN_SECONDS", "900"))
    except ValueError:
        return 900


def channels():
    """Canaux configurés (présence des variables, jamais leurs valeurs)."""
    return {
        "sms": bool(_env("SECRETS_ALERT_SMS_URL") and _env("SECRETS_ALERT_SMS_KEY") and _env("SECRETS_ALERT_SMS_NUMBER")),
        "email": bool(_env("SECRETS_ALERT_SMTP_HOST") and _env("SECRETS_ALERT_EMAIL_TO") and _env("SECRETS_ALERT_SMTP_FROM")),
        "webhook": bool(_env("SI_AGENT_NOTIFY_WEBHOOK_URL")),
    }


def describe():
    return {"min_severity": min_severity(), "cooldown_seconds": cooldown_seconds(), "channels": channels(),
            "any": any(channels().values()) and min_severity() != "none"}


def should_notify(event, now=None):
    """(oui, raison) -- seuil de sévérité puis anti-tempête par (genre, agent)."""
    ms = min_severity()
    if ms == "none":
        return False, "notifications désactivées"
    sev = event.get("severity") or "info"
    if SEVERITY_ORDER.get(sev, 2) > SEVERITY_ORDER[ms]:
        return False, "sous le seuil %s" % ms
    if not any(channels().values()):
        return False, "aucun canal configuré"
    key = (event.get("kind"), event.get("agent_id"))
    now = now if now is not None else time.time()
    with _lock:
        last = _last_sent.get(key, 0)
        if now - last < cooldown_seconds():
            return False, "déjà notifié il y a %d s" % int(now - last)
        _last_sent[key] = now
    return True, "ok"


def format_message(event):
    sev = (event.get("severity") or "info").upper()
    who = event.get("agent_id") or "central"
    return "[supervision-si/agents] %s %s : %s (%s)" % (sev, who, event.get("message"), event.get("at"))


def send_all(event, force=False):
    """Envoi synchrone sur tous les canaux configurés ; renvoie {canal: bool}."""
    out = {}
    ch = channels()
    msg = format_message(event)
    if ch["sms"] and secrets_alert:
        out["sms"] = bool(secrets_alert.send_sms_alert(msg[:480]))
    if ch["email"] and secrets_alert:
        body = "%s\n\nAgent : %s\nSite : %s\nGenre : %s\nSévérité : %s\nSource : %s\n\nDétails :\n%s\n" % (
            event.get("message"), event.get("agent_id") or "-", event.get("site") or "-", event.get("kind"), event.get("severity"),
            event.get("source"), json.dumps(event.get("details") or {}, indent=2, ensure_ascii=False))
        out["email"] = bool(secrets_alert.send_email_alert("[supervision-si] agents : %s" % event.get("message", "")[:80], body))
    if ch["webhook"]:
        out["webhook"] = _post_webhook(_env("SI_AGENT_NOTIFY_WEBHOOK_URL"), event, msg)
    out["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _log.info("notification %s (%s) : %s", event.get("kind"), event.get("severity"), {k: v for k, v in out.items() if k != "at"})
    return out


def _post_webhook(url, event, text, timeout=10):
    payload = json.dumps({"text": text, "event": event}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError) as exc:
        _log.warning("webhook de notification en échec : %s", exc)
        return False


def dispatch(db_path, event, threaded=True):
    """Point d'entrée : décide, envoie (en thread), marque l'événement.
    #716 : relais à notify-api d'abord (indépendant des canaux SECRETS_ALERT_* et de leur anti-tempête :
    notify-api a les siens -- regroupement, retenue des rafales)."""
    relay_to_hub(event)
    ok, why = should_notify(event)
    if not ok:
        _log.debug("événement %s non notifié : %s", event.get("kind"), why)
        return None

    def _run():
        try:
            result = send_all(event)
            if event.get("id") is not None and db_path:
                import store  # noqa: PLC0415
                store.mark_notified(db_path, event["id"], result)
        except Exception as exc:  # noqa: BLE001 -- jamais bloquant
            _log.warning("notification impossible : %s", exc)

    if threaded and os.environ.get("SI_AGENT_NOTIFY_SYNC", "0") != "1":
        threading.Thread(target=_run, daemon=True).start()
        return "queued"
    _run()
    return "sent"
