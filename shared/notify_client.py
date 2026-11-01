# -*- coding: utf-8 -*-
"""Client des notifications du hub (livraison #590) pour les modules
producteurs : `notify(action, subject, body, context)` met en file dans
notify-api et n'attend rien -- jamais une exception, jamais plus de 2 s,
jamais de secret dans le corps. `register_actions([...])` déclare le
catalogue du module au démarrage (groupe par défaut créé côté notify-api).

Variables : NOTIFY_API_URL (http://notify-api:5000), NOTIFY_INTERNAL_TOKEN,
NOTIFY_CONSUMER (nom du module). Sans URL ou jeton : journalisé, ignoré."""
import json
import logging
import os
import threading
import urllib.request

_log = logging.getLogger("notify_client")


def _cfg():
    return os.environ.get("NOTIFY_API_URL", "").rstrip("/"), os.environ.get("NOTIFY_INTERNAL_TOKEN", ""), os.environ.get("NOTIFY_CONSUMER", "hub")


def _post(path, payload, timeout=2.0):
    url, token, consumer = _cfg()
    if not url or not token:
        _log.debug("notifications non configurées (NOTIFY_API_URL / NOTIFY_INTERNAL_TOKEN) : %s ignoré", path)
        return None
    req = urllib.request.Request(url + path, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "X-Notify-Token": token, "X-Notify-Consumer": consumer})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL interne)
            return json.loads(resp.read().decode("utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001
        _log.warning("notification %s non transmise : %s", payload.get("action") or path, exc.__class__.__name__)
        return None


def notify(action, subject, body="", context=None, severity=None, wait=False, to=None, attachments=None):
    """Fire-and-forget (thread) sauf wait=True. #703 : `to` = adresses en plus des
    groupes de l'action ; `attachments` = [(nom, type MIME, octets)] (8 Mo au total)."""
    import base64
    payload = {"action": action, "subject": subject, "body": body, "context": context or {}}
    if severity:
        payload["severity"] = severity
    if to:
        payload["to"] = list(to)
    if attachments:
        payload["attachments"] = [{"filename": n, "content_type": t, "data": base64.b64encode(d).decode("ascii")} for n, t, d in attachments]
    timeout = 20.0 if attachments else 2.0
    if wait:
        return _post("/notify", payload, timeout)
    threading.Thread(target=_post, args=("/notify", payload, timeout), daemon=True).start()
    return None


def register_actions(actions):
    """actions : [{"id": "module.action", "label": "...", "severity": "info|warning|critical"}]."""
    threading.Thread(target=_post, args=("/actions/register", {"actions": actions}, 5.0), daemon=True).start()
