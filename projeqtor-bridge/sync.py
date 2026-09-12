"""Synchronisation ProjeQtOr -> gestion de tickets du hub
(livraison #484, demandé explicitement : « les demandes de ProjeQtOr
se retrouvent dans la gestion de ticket du hub dans la liste des
imports à valider (lien avec les ical) »).

Même esprit que le pipeline ICS de tickets-api (#273) : toute demande
créée dans ProjeQtOr est poussée comme ticket hub avec
`pending_validation=1` — JAMAIS traitée comme pleinement réelle tant
qu'un humain ne l'a pas confirmée dans l'écran de validation.

Mécanisme : boucle bornée (intervalle configurable), requête
/api/Ticket/updated/{depuis}/{maintenant}, puis POST
{tickets-api}/tickets/import-external par ticket nouveau. La
DÉDUPLICATION est côté tickets-api (source_type+source_nom), pas ici :
l'état local (/data/sync_state.json) n'est qu'une optimisation de
trafic, sa perte ne crée jamais de doublon — au pire un tour complet
re-pousse des tickets que tickets-api refusera proprement (déjà connus).
"""
import json
import logging
import os
import threading
import time
from datetime import datetime

import requests

from projeqtor_client import ProjeqtorApiError

log = logging.getLogger("projeqtor-bridge.sync")

STATE_PATH = os.environ.get("BRIDGE_STATE_PATH", "/data/sync_state.json")
INTERVAL = int(os.environ.get("BRIDGE_SYNC_INTERVAL_SECONDS", "120"))
TICKETS_API = os.environ.get("TICKETS_API_INTERNAL_URL", "").rstrip("/")

_status = {"last_run": None, "last_error": None, "pushed_total": 0}


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            state = json.load(fh)
            state.setdefault("pushed_ids", [])
            return state
    except (OSError, ValueError):
        return {"pushed_ids": [], "last_check": None}


def _save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, STATE_PATH)  # écriture atomique, jamais de JSON tronqué
    except OSError as exc:
        log.warning("état de sync non sauvegardé (%s) — la déduplication reste assurée par tickets-api", exc)


def _api_ts(dt):
    return dt.strftime("%Y%m%d%H%M%S")


def push_ticket(ticket):
    """Un ticket ProjeQtOr -> un ticket hub à valider. Retourne
    "created" (201), "known" (409, déjà connu côté hub — JAMAIS un
    doublon) ou "retry" (à réessayer au prochain tour)."""
    ref = f"ProjeQtOr #{ticket.get('id')}"
    description = ticket.get("description") or ""
    try:
        resp = requests.post(
            f"{TICKETS_API}/tickets/import-external",
            json={
                "subject": ticket.get("name") or "(sans sujet)",
                "description": description,
                "source_type": "projeqtor",
                "source_nom": ref,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        log.warning("tickets-api injoignable (%s) — réessaiera au prochain tour", exc)
        return "retry"
    if resp.status_code == 201:
        return "created"
    if resp.status_code == 409:
        return "known"
    log.warning("tickets-api a refusé %s : %s %s", ref, resp.status_code, resp.text[:200])
    return "retry"


def sync_once(client):
    """Un tour de synchronisation. Retourne le résumé (affiché par
    /sync/status et /sync/now)."""
    global _status
    state = _load_state()
    now = datetime.now()
    # Premier tour : fenêtre large (tout l'historique, dédupliqué par
    # tickets-api) — une installation fraîche doit tout rattraper.
    since = state.get("last_check") or "20000101000000"
    until = _api_ts(now)

    pushed = 0
    errors = []
    try:
        tickets = client.get_updated("Ticket", since, until)
        if isinstance(tickets, dict):  # l'API peut renvoyer {"ticket": [...]} ou une liste
            tickets = tickets.get("ticket") or tickets.get("items") or []
    except ProjeqtorApiError as exc:
        _status.update(last_run=now.isoformat(), last_error=str(exc))
        return {"pushed": 0, "errors": [str(exc)]}

    known = set(state["pushed_ids"])
    for ticket in tickets:
        tid = ticket.get("id")
        if tid is None or tid in known:
            continue
        outcome = push_ticket(ticket)
        if outcome in ("created", "known"):
            known.add(tid)
            if outcome == "created":
                pushed += 1
        else:
            errors.append(f"ProjeQtOr #{tid} non poussé")

    state["pushed_ids"] = sorted(known)[-10000:]  # borne mémoire, large devant le réel
    state["last_check"] = until
    _save_state(state)
    _status.update(last_run=now.isoformat(), last_error=(errors[0] if errors else None))
    _status["pushed_total"] += pushed
    return {"pushed": pushed, "errors": errors, "window": [since, until]}


def status():
    return dict(_status, interval_seconds=INTERVAL, tickets_api=bool(TICKETS_API))


def start_background(client):
    """Thread de fond — jamais bloquant pour le service web : la
    disponibilité du formulaire public ne dépend JAMAIS de la sync."""
    if not TICKETS_API:
        log.warning("TICKETS_API_INTERNAL_URL absente — synchronisation DÉSACTIVÉE")
        return None

    def loop():
        while True:
            try:
                summary = sync_once(client)
                if summary["pushed"] or summary["errors"]:
                    log.info("sync : %s", summary)
            except Exception:  # noqa: BLE001 — un tour en échec ne tue jamais la boucle
                log.exception("tour de synchronisation en échec")
            time.sleep(INTERVAL)

    thread = threading.Thread(target=loop, name="projeqtor-sync", daemon=True)
    thread.start()
    return thread
