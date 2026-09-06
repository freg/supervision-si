"""
Client HTTP vers dba-api (livraison #151, backlog BACKLOG.md #5,
correctif #174) -- ce module N'ACCÈDE JAMAIS directement à une base
SGBD : dba-api expose déjà tout ce qu'il faut (GET
/connections/<id>/tables, .../columns, .../rows) -- schema-analyzer
s'appuie dessus plutôt que de dupliquer les connecteurs mysql/
postgres/sqlite de dba/api (décision d'architecture prise avec la
personne avant de coder, voir BACKLOG.md #5). Couplage FAIBLE,
volontaire : un simple client HTTP interne au réseau Docker, jamais
un accès direct au fichier dba.db ni aux connecteurs Python de
dba-api.

**Correctif #174** : un 502 rapporté par la personne
("impossible de lister les tables via dba-api : 502 Server Error:
BAD GATEWAY for url: ...") s'est avéré être le MÊME piège que
mayan_client.py avant #163 -- dba-api renvoie DÉLIBÉRÉMENT un 502
avec le VRAI message d'erreur du connecteur dans le corps JSON
({"error": str(exc)}, voir dba/api/app.py, list_tables et routes
voisines -- 502 choisi là-bas pour signaler "erreur du DRIVER
EXTERNE, pas de ce service"), mais `raise_for_status()` seul ne
donne QUE la ligne de statut générique, jamais ce corps. Corrigé :
`_raise_with_detail` remplace tous les `raise_for_status()` isolés
sur les appels dont l'échec est SURFACÉ à la personne (jamais sur
l'échantillonnage de lignes de fetch_full_schema, volontairement
best-effort silencieux, voir plus bas).
"""
import logging
import time

import requests

# Traces DEBUG (livraison #225, audit rétroactif). dba-api n'exige
# pas d'authentification (appel interne au réseau Docker) -- risque
# de fuite plus faible que les autres clients de cet audit, mais
# `_raise_with_detail` trace le corps d'erreur renvoyé par dba-api,
# qui peut potentiellement inclure un message de driver externe (voir
# docstring du module) -- déjà inclus dans l'exception levée et donc
# déjà surfacé à l'appelant HTTP, tracer cette même valeur n'ajoute
# pas de nouvelle exposition.
_log = logging.getLogger("schema_client")


class DbaApiError(Exception):
    """Levée pour toute erreur de communication avec dba-api --
    jamais une requests.RequestException brute qui remonterait telle
    quelle à l'appelant HTTP de CE module."""


def _raise_with_detail(resp, context):
    """Remplace `resp.raise_for_status()` seul -- capture et inclut
    le CORPS de la réponse dba-api dans le message d'erreur quand
    disponible (dba-api renvoie {"error": "..."} avec le message RÉEL
    du connecteur externe sur ses routes /tables, /columns, /rows --
    voir dba/api/app.py) -- correctif #174, même raisonnement que
    ged/api/mayan_client.py (#163). Ne fait rien si la réponse est OK
    (2xx)."""
    if resp.ok:
        return
    detail = None
    try:
        detail = resp.json()
    except ValueError:
        text = (resp.text or "").strip()
        detail = text[:500] if text else None
    _log.debug("_raise_with_detail : %s -- code HTTP %s -- %s", context, resp.status_code, detail)
    if detail:
        raise DbaApiError(f"{context} (HTTP {resp.status_code}) : {detail}")
    raise DbaApiError(f"{context} (HTTP {resp.status_code}, dba-api n'a renvoyé aucun détail)")


def _safe_json(resp, context):
    """Livraison #287 -- "rendre les erreurs systématiquement plus
    explicites", généralisé depuis #286 (glpi_client.py) : même
    couple que `_raise_with_detail` ci-dessus, mais pour le cas
    complémentaire -- un 2xx avec un corps NON-JSON (dba-api
    injoignable derrière un proxy, panne intermédiaire...) plantait
    encore avec une JSONDecodeError brute à chaque `resp.json()`."""
    try:
        return resp.json()
    except ValueError:
        snippet = (resp.text or "").strip()[:300]
        _log.debug("_safe_json : %s -- réponse 2xx mais pas du JSON valide -- %s", context, snippet)
        raise DbaApiError(f"{context} : réponse HTTP {resp.status_code} inattendue (pas du JSON valide) -- début de la réponse : {snippet!r}")


def fetch_tables_and_columns(dba_api_base, connection_id, database=None, timeout=15):
    """Récupère UNIQUEMENT tables + colonnes (jamais d'échantillonnage
    de lignes) -- utilisé par fetch_full_schema ci-dessous ET par
    l'export du graphe relationnel (livraison #154), qui n'a pas
    besoin des échantillons de list_detector.py -- évite un GET /rows
    par table, superflu pour ce dernier usage.

    Renvoie {nom_table: {"columns": [...]}}. Lève DbaApiError si
    dba-api est injoignable ou renvoie une erreur sur /tables ou
    /columns (le SCHÉMA est indispensable, jamais un best-effort ici,
    contrairement à l'échantillonnage des lignes)."""
    params = {"database": database} if database else {}
    _log.debug("fetch_tables_and_columns : démarré (connection_id=%s, database=%s)", connection_id, database)
    start = time.monotonic()

    try:
        tables_resp = requests.get(
            f"{dba_api_base}/connections/{connection_id}/tables",
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        _log.debug("fetch_tables_and_columns : ÉCHEC réseau sur /tables -- %s", exc)
        raise DbaApiError(f"impossible de joindre dba-api pour lister les tables : {exc}") from exc
    _raise_with_detail(tables_resp, "impossible de lister les tables via dba-api")

    table_names = _safe_json(tables_resp, "impossible de lister les tables via dba-api")
    if not isinstance(table_names, list):
        raise DbaApiError("réponse inattendue de dba-api pour /tables (liste attendue)")
    _log.debug("fetch_tables_and_columns : %d table(s) trouvée(s), récupération des colonnes", len(table_names))

    tables = {}
    for tname in table_names:
        try:
            cols_resp = requests.get(
                f"{dba_api_base}/connections/{connection_id}/tables/{tname}/columns",
                params=params,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            _log.debug("fetch_tables_and_columns : ÉCHEC réseau sur /columns pour '%s' -- %s", tname, exc)
            raise DbaApiError(f"impossible de joindre dba-api pour les colonnes de '{tname}' : {exc}") from exc
        _raise_with_detail(cols_resp, f"impossible de lister les colonnes de '{tname}' via dba-api")
        tables[tname] = {"columns": _safe_json(cols_resp, f"impossible de lister les colonnes de '{tname}' via dba-api")}

    elapsed_ms = int((time.monotonic() - start) * 1000)
    _log.debug("fetch_tables_and_columns : terminé en %d ms (%d table(s))", elapsed_ms, len(tables))
    return tables


def execute_sql(dba_api_base, connection_id, sql, database=None, timeout=30):
    """Exécute du SQL via `POST /connections/<id>/sql` (dba-api) --
    même route que l'onglet SQL du portail DBA, ici réutilisée par
    `relation_validator.py` pour CONFIRMER une relation contre les
    vraies données (livraison #241, backlog #5 -- demandé
    explicitement : "à partir du schéma ET des données, pour
    conforter la relation"). `sql` toujours un SELECT construit par
    CE module -- jamais une entrée libre de la personne à cet
    endroit précis (contrairement à l'onglet SQL du portail DBA)."""
    _log.debug("execute_sql : démarré (connection_id=%s, database=%s)", connection_id, database)
    start = time.monotonic()
    try:
        resp = requests.post(
            f"{dba_api_base}/connections/{connection_id}/sql",
            json={"sql": sql, "database": database},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        _log.debug("execute_sql : ÉCHEC réseau -- %s", exc)
        raise DbaApiError(f"impossible de joindre dba-api pour exécuter du SQL : {exc}") from exc
    _raise_with_detail(resp, "exécution SQL échouée via dba-api")
    elapsed_ms = int((time.monotonic() - start) * 1000)
    body = _safe_json(resp, "exécution SQL échouée via dba-api")
    _log.debug("execute_sql : terminé en %d ms (%d ligne(s))", elapsed_ms, body.get("row_count", 0))
    return body


def fetch_full_schema(dba_api_base, connection_id, database=None, sample_size=20, timeout=15):
    """Récupère le schéma COMPLET (tables + colonnes, via
    fetch_tables_and_columns ci-dessus) PLUS un échantillon de valeurs
    par colonne (pour list_detector.py) -- tout via l'API HTTP de
    dba-api.

    Renvoie {"tables": {nom_table: {"columns": [...]}},
             "samples": {nom_table: {nom_colonne: [valeurs...]}}}.

    L'échantillonnage des LIGNES (/rows) est volontairement
    BEST-EFFORT PAR TABLE : une table dont les lignes ne peuvent pas
    être lues (permissions, vue non standard...) ne fait pas échouer
    tout le diagnostic, seulement priver CETTE table de détection de
    colonnes-listes -- le schéma et les relations par nom restent
    utilisables sans ça. Volontairement PAS de _raise_with_detail ici
    -- l'erreur est de toute façon avalée (samples[tname] = {}),
    jamais surfacée à la personne, inutile d'en extraire le détail."""
    tables = fetch_tables_and_columns(dba_api_base, connection_id, database=database, timeout=timeout)
    params = {"database": database} if database else {}

    samples = {}
    for tname in tables:
        try:
            rows_params = dict(params)
            rows_params.update({"limit": sample_size, "offset": 0})
            rows_resp = requests.get(
                f"{dba_api_base}/connections/{connection_id}/tables/{tname}/rows",
                params=rows_params,
                timeout=timeout,
            )
            rows_resp.raise_for_status()
            rows_data = rows_resp.json()
            col_names = rows_data.get("columns", [])
            rows = rows_data.get("rows", [])
            samples[tname] = {
                cname: [row[i] if i < len(row) else None for row in rows]
                for i, cname in enumerate(col_names)
            }
        except (requests.RequestException, ValueError):
            # ValueError ajouté en #287 -- un corps NON-JSON (2xx)
            # échappait auparavant à ce filet, contredisant
            # l'intention documentée ci-dessus ("l'erreur est de
            # toute façon avalée... inutile d'en extraire le
            # détail") -- un vrai bug, pas une omission volontaire.
            samples[tname] = {}

    return {"tables": tables, "samples": samples}
