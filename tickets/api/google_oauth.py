"""
Connecteur OAuth2 Google Calendar — alternative à l'adresse secrète
iCal, pour un accès plus robuste dans la durée (pas de session à
renouveler manuellement, jeton de rafraîchissement persistant).

⚠️ Ce module n'a PAS pu être testé contre un vrai compte Google —
aucun réseau ni compte disponible dans l'environnement de
développement. Les endpoints Google utilisés (autorisation, échange de
jeton, API Calendar) sont stables et bien documentés, mais un test réel
reste nécessaire avant usage en production.

Prérequis côté utilisateur (rien de tout ça n'est faisable depuis cet
environnement) :
1. Créer un projet dans Google Cloud Console (console.cloud.google.com)
2. Activer l'API "Google Calendar API" pour ce projet
3. Créer des identifiants OAuth 2.0 (type "Application Web")
4. Ajouter l'URI de redirection exacte (voir GOOGLE_OAUTH_REDIRECT_URI)
   dans la configuration de l'identifiant côté Google Cloud Console
5. Renseigner GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET dans
   l'environnement du service tickets-api (voir .env)
"""
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

# Traces DEBUG (livraison #223, audit rétroactif). RÈGLE ABSOLUE : ni
# le code d'autorisation, ni le client_secret, ni les jetons d'accès/
# rafraîchissement n'apparaissent JAMAIS dans une trace.
_log = logging.getLogger("google_oauth")


def _safe_json(response, context):
    """Livraison #287 -- "rendre les erreurs systématiquement plus
    explicites", généralisé depuis #286 (glpi_client.py) : un 2xx de
    Google avec un corps NON-JSON (rare mais possible -- limitation
    de débit renvoyant une page HTML, panne côté Google...) plantait
    encore avec une JSONDecodeError brute. Aucune classe d'erreur
    dédiée dans ce module -- RuntimeError générique, cohérent avec
    l'absence de gestion d'erreur préexistante ici (laissée à
    l'appelant, tickets/api/app.py)."""
    try:
        return response.json()
    except ValueError:
        snippet = (response.text or "").strip()[:300]
        _log.debug("_safe_json : %s -- réponse 2xx mais pas du JSON valide -- %s", context, snippet)
        raise RuntimeError(f"{context} : réponse Google inattendue (pas du JSON valide) -- début de la réponse : {snippet!r}")

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
CALENDAR_EVENTS_ENDPOINT = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:6105/oauth/google/callback")


def is_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


def build_authorization_url(state: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",  # nécessaire pour obtenir un refresh_token
        "prompt": "consent",  # force le renvoi du refresh_token même en re-consentement
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Renvoie {'access_token', 'refresh_token', 'expires_in', ...} ou lève requests.RequestException."""
    _log.debug("exchange_code_for_tokens : démarré (jamais le code, le client_secret ni les jetons ici)")
    start = time.monotonic()
    response = requests.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if not response.ok:
        _log.debug("exchange_code_for_tokens : ÉCHEC HTTP %s après %d ms", response.status_code, elapsed_ms)
    response.raise_for_status()
    _log.debug("exchange_code_for_tokens : succès en %d ms", elapsed_ms)
    return _safe_json(response, "échange du code d'autorisation Google échoué")


def refresh_access_token(refresh_token: str) -> dict:
    """Renvoie {'access_token', 'expires_in', ...} — pas de nouveau refresh_token à chaque fois."""
    _log.debug("refresh_access_token : démarré (jamais le jeton de rafraîchissement ici)")
    start = time.monotonic()
    response = requests.post(
        TOKEN_ENDPOINT,
        data={
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if not response.ok:
        _log.debug("refresh_access_token : ÉCHEC HTTP %s après %d ms", response.status_code, elapsed_ms)
    response.raise_for_status()
    _log.debug("refresh_access_token : succès en %d ms", elapsed_ms)
    return _safe_json(response, "rafraîchissement du jeton Google échoué")


def fetch_calendar_events(access_token: str, max_results: int = 2500) -> list[dict]:
    """
    Appelle l'API Calendar (pas de fichier ICS à parser — JSON natif,
    directement dans notre format interne). Pagine automatiquement si
    plus d'événements que max_results par page (l'API limite à 2500).
    """
    events = []
    page_token = None
    page_num = 0
    _log.debug("fetch_calendar_events : démarré (jamais le jeton d'accès ici)")

    while True:
        page_num += 1
        params = {
            "maxResults": min(max_results, 2500),
            "singleEvents": "true",  # développe les événements récurrents en occurrences individuelles
            "orderBy": "startTime",
            "timeMin": "2000-01-01T00:00:00Z",
        }
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(
            CALENDAR_EVENTS_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30,
        )
        if not response.ok:
            _log.debug("fetch_calendar_events : ÉCHEC HTTP %s au tour %d", response.status_code, page_num)
        response.raise_for_status()
        body = _safe_json(response, "récupération des événements Google Calendar échouée")

        for item in body.get("items", []):
            parsed = _convert_google_event(item)
            if parsed:
                events.append(parsed)

        page_token = body.get("nextPageToken")
        if not page_token:
            break

    _log.debug("fetch_calendar_events : terminé -- %d page(s), %d événement(s) au total", page_num, len(events))
    return events


def _convert_google_event(item: dict) -> "dict | None":
    """Convertit un événement au format JSON natif de l'API Calendar
    vers notre format interne {uid, summary, description, start_ts, end_ts}."""
    uid = item.get("id")
    if not uid:
        return None

    start = item.get("start", {})
    end = item.get("end", {})

    # "dateTime" (horodaté) ou "date" (jour entier, sans heure) selon le type d'événement.
    start_ts = _parse_google_datetime(start.get("dateTime") or start.get("date"))
    end_ts = _parse_google_datetime(end.get("dateTime") or end.get("date"))
    if start_ts is None:
        return None

    return {
        "uid": f"google_api_{uid}",  # préfixe pour ne jamais entrer en collision avec un import ICS du même événement
        "summary": item.get("summary", ""),
        "description": item.get("description", ""),
        "start_ts": start_ts,
        "end_ts": end_ts if end_ts is not None else start_ts,
    }


def _parse_google_datetime(value: "str | None") -> "int | None":
    if not value:
        return None
    try:
        if len(value) == 10:  # "YYYY-MM-DD" (événement jour entier)
            dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:  # "YYYY-MM-DDTHH:MM:SS+ZZ:ZZ" (ISO 8601 avec fuseau)
            dt = datetime.fromisoformat(value)
        return int(dt.timestamp())
    except ValueError:
        return None
