"""
Récupération des entités depuis les services existants -- jamais un
accès direct à leur base de données, toujours leur API HTTP déjà
publique (même principe d'autonomie entre modules déjà établi
partout ailleurs dans ce projet). Chaque fonction `fetch_*` renvoie
une liste de dicts `{"id": str, "label": str}` -- volontairement
minimal pour cette première passe (seul le "marqueur" texte sert au
calcul de relation directe ; le reste des champs de chaque entité
reste dans son propre module, jamais dupliqué ici).
"""
import requests

KNOWN_ENTITY_TYPES = {"ticket", "calendar_event", "document", "task"}

REQUEST_TIMEOUT_SECONDS = 10


class FetchError(Exception):
    """Un service source était injoignable ou a répondu de façon
    inattendue -- toujours renvoyée telle quelle jusqu'à l'appelant
    HTTP (502), jamais masquée par un résultat partiel silencieux
    qui laisserait croire à un calcul de relations complet alors
    qu'il ne l'est pas."""


def _get_json(url, service_label):
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise FetchError(f"{service_label} injoignable : {exc}") from exc
    if resp.status_code != 200:
        raise FetchError(f"{service_label} a répondu {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise FetchError(f"{service_label} : réponse illisible (pas du JSON)") from exc


def fetch_tickets(tickets_api_url):
    """Tickets OUVERTS uniquement (voir /queue) -- périmètre
    volontairement restreint pour cette première passe (les tickets
    les plus pertinents pour une mise en relation active), jamais
    l'historique complet. `t.*` de la requête SQL de /queue inclut
    déjà `description` -- combinée au sujet dans `text` pour la
    détection d'IP (livraison #336), jamais pour la correspondance
    de nom qui reste sur le sujet SEUL (`label`). `site_label` (déjà
    joint côté /queue) capturé séparément pour la proximité
    géographique (#338) -- seule source de site parmi les quatre
    types d'entités, les autres (événement/document/tâche) n'ont
    aucune notion de lieu dans ce projet."""
    data = _get_json(f"{tickets_api_url}/queue", "tickets-api (/queue)")
    tickets = data.get("tickets") if isinstance(data, dict) else data
    return [
        {
            "id": str(t["id"]),
            "label": t.get("subject") or "",
            "text": f"{t.get('subject') or ''} {t.get('description') or ''}",
            "site": t.get("site_label"),
        }
        for t in (tickets or [])
        if t.get("subject")
    ]


def fetch_calendar_events(tickets_api_url):
    data = _get_json(f"{tickets_api_url}/calendar/events", "tickets-api (/calendar/events)")
    events = data.get("events") if isinstance(data, dict) else data
    return [
        {
            "id": str(e["id"]),
            "label": e.get("summary") or "",
            "text": f"{e.get('summary') or ''} {e.get('description') or ''}",
            "site": None,
        }
        for e in (events or [])
        if e.get("summary")
    ]


def fetch_documents(ged_api_url):
    docs = _get_json(f"{ged_api_url}/documents", "ged-api (/documents)")
    return [
        {"id": str(d["id"]), "label": d.get("name") or "", "text": d.get("name") or "", "site": None}
        for d in (docs or [])
        if d.get("name")
    ]


def fetch_tasks(tasks_api_url):
    tasks = _get_json(f"{tasks_api_url}/tasks", "tasks-api (/tasks)")
    return [
        {
            "id": str(t["id"]),
            "label": t.get("title") or "",
            "text": f"{t.get('title') or ''} {t.get('description') or ''}",
            "site": None,
        }
        for t in (tasks or [])
        if t.get("title")
    ]


def fetch_geolocations(pixel_grid_api_url):
    """{localisation_normalisée: (latitude, longitude)} -- UNIQUEMENT
    les localisations `mapped` (coordonnées connues, jamais None) ;
    normalisée avec relation_engine.normalize_label pour matcher un
    `site_label` de ticket même en cas de différence mineure de
    casse/espaces. Import tardif (évite un import circulaire, ce
    module est importé PAR relation_engine pour ses tests en
    isolation, jamais l'inverse en usage normal)."""
    from relation_engine import normalize_label

    data = _get_json(f"{pixel_grid_api_url}/geolocations", "pixel-grid-api (/geolocations)")
    entries = data.get("geolocations") if isinstance(data, dict) else data
    result = {}
    for g in (entries or []):
        if g.get("latitude") is None or g.get("longitude") is None:
            continue
        result[normalize_label(g.get("localisation"))] = (g["latitude"], g["longitude"])
    return result


def fetch_all_entities(tickets_api_url, ged_api_url, tasks_api_url):
    """Renvoie un dict {(type, id): {"label": str, "text": str,
    "site": str|None}} -- `label` sert à la correspondance de NOM
    (#335), `text` à la détection d'IP (#336) et de proximité
    sémantique (#337), `site` à la proximité géographique (#338, via
    fetch_geolocations, résolu séparément par l'appelant -- ce module
    ne fait ici que RÉCUPÉRER le nom de site brut, jamais la
    résolution en coordonnées elle-même)."""
    entities = {}
    for entity_type, items in (
        ("ticket", fetch_tickets(tickets_api_url)),
        ("calendar_event", fetch_calendar_events(tickets_api_url)),
        ("document", fetch_documents(ged_api_url)),
        ("task", fetch_tasks(tasks_api_url)),
    ):
        for item in items:
            entities[(entity_type, item["id"])] = {"label": item["label"], "text": item["text"], "site": item.get("site")}
    return entities
