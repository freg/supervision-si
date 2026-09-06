"""
Client HTTP vers Mayan EDMS (livraison #158, correctif #163) --
REMPLACE le stockage homemade de #157 (fichiers sur disque +
document_versions SQLite) par de VRAIS appels à l'API REST de Mayan
EDMS, adoptée après recherche ("allons-y pour Mayan EDMS" dit
explicitement par la personne -- voir ged/README.md pour le
raisonnement complet).

La table `document_links` (documents_store.py) reste LOCALE --
Mayan n'a pas d'équivalent direct à "lier un document à N'IMPORTE
QUEL type d'entité externe" (répond à "accès polymorphe" demandé
explicitement en #157) -- ged-api continue de la gérer lui-même, en
référençant les IDs de documents MAYAN (pas des IDs locaux comme dans
la fondation homemade de #157, désormais remplacée pour tout ce qui
touche au STOCKAGE des fichiers/versions).

**Correctif #163** : le premier test réel contre une vraie instance
Mayan (4.11) a produit un 400 sur l'envoi de fichier -- message
totalement muet côté ged-api ("400 Client Error: Bad Request for
url: ..."), `raise_for_status()` seul ne donne QUE la ligne de statut
générique, jamais le corps de la réponse -- alors que Django REST
Framework (le framework utilisé par Mayan) renvoie normalement un
détail PRÉCIS par champ (ex. `{"file_new": ["..."]}`), la seule
information réellement utile pour diagnostiquer CE qui cloche.
Corrigé : `_raise_with_detail` ci-dessous remplace tous les
`raise_for_status()` isolés, capture et inclut le corps de la
réponse dans le message d'erreur -- désormais visible jusque dans
l'interface (voir app.py, TicketDocuments.jsx).

⚠️ CONNAISSANCE PARTIELLE DE L'API RÉELLE -- vue uniquement via des
extraits de documentation glanés en ligne (pas la référence complète).
Le format du PREMIER test réel (`files={'file_new': ...}`) correspond
BIEN à la documentation officielle (vérifié sur deux versions, 4.9 et
4.11) -- le 400 rencontré vient donc probablement d'un détail non
visible dans ces extraits (champ requis en plus, contrainte du
document_type, ou autre) -- le message d'erreur désormais détaillé
(voir ci-dessus) doit permettre de trancher au prochain essai, plutôt
que de deviner à nouveau à l'aveugle.
"""
import logging
import re
import time

import requests

# Traces DEBUG (livraison #223, audit rétroactif). RÈGLE ABSOLUE :
# le mot de passe Mayan n'apparaît JAMAIS dans une trace.
# `_raise_with_detail` est le point de passage UNIQUE de tous les
# chemins d'erreur de ce module -- l'instrumenter couvre
# automatiquement l'issue de TOUTES les fonctions ci-dessous, même
# celles non individuellement tracées à l'entrée/sortie.
_log = logging.getLogger("mayan_client")


class MayanError(Exception):
    """Levée pour toute erreur de communication avec Mayan -- jamais
    une requests.RequestException brute qui remonterait telle quelle
    à l'appelant HTTP de ce module."""


def _auth(username, password):
    return (username, password)


def _raise_with_detail(resp, context):
    """Remplace `resp.raise_for_status()` seul -- capture et inclut
    le CORPS de la réponse Mayan dans le message d'erreur quand
    disponible (Django REST Framework renvoie typiquement un détail
    précis par champ, ex. {"file_new": ["Ce champ est requis."]}) --
    correctif #163, voir docstring du module. Ne fait rien si la
    réponse est OK (2xx)."""
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
        raise MayanError(f"{context} (HTTP {resp.status_code}) : {detail}")
    raise MayanError(f"{context} (HTTP {resp.status_code}, Mayan n'a renvoyé aucun détail)")


def _safe_json(resp, context):
    """Livraison #287 -- "rendre les erreurs systématiquement plus
    explicites", généralisé depuis le correctif réel #286
    (glpi_client.py) : `_raise_with_detail` ne protège QUE contre un
    code HTTP non-2xx -- un 2xx avec un corps NON-JSON (page HTML
    d'erreur d'un proxy, mauvaise URL, Mayan indisponible derrière un
    load-balancer...) plantait encore avec une JSONDecodeError brute
    à chaque `resp.json()` de ce module. Remplace CHAQUE appel
    `resp.json()` par `_safe_json(resp, "...")` -- lève une
    MayanError avec un aperçu du VRAI corps renvoyé (tronqué à 300
    caractères) au lieu d'un traceback Python opaque."""
    try:
        return resp.json()
    except ValueError:
        snippet = (resp.text or "").strip()[:300]
        _log.debug("_safe_json : %s -- réponse 2xx mais pas du JSON valide -- %s", context, snippet)
        raise MayanError(f"{context} : réponse HTTP {resp.status_code} inattendue (pas du JSON valide) -- début de la réponse : {snippet!r}")


def get_default_document_type_id(mayan_base, username, password, type_label="Default", timeout=15):
    """Renvoie l'id du type de document nommé `type_label` (repli
    "Default", créé automatiquement par Mayan à sa première
    initialisation) -- jamais codé en dur (1) : un déploiement
    pourrait avoir un id différent selon son historique. Lève
    MayanError si introuvable, jamais un None silencieux qui ferait
    échouer la création de document plus loin avec un message confus."""
    try:
        resp = requests.get(
            f"{mayan_base}/api/v4/document_types/",
            auth=_auth(username, password),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MayanError(f"impossible de joindre Mayan pour lister les types de documents : {exc}") from exc
    _raise_with_detail(resp, "impossible de lister les types de documents Mayan")
    data = _safe_json(resp, "impossible de lister les types de documents Mayan")
    for result in data.get("results", []):
        if result.get("label") == type_label:
            return result["id"]
    raise MayanError(f"aucun type de document '{type_label}' trouvé sur ce Mayan (déploiement pas encore initialisé ?)")


def create_document(mayan_base, username, password, document_type_id, label, timeout=15):
    """Crée le CONTENEUR document (métadonnées seules, PAS de fichier
    -- voir upload_file ci-dessous, toujours appelée juste après).
    Renvoie l'id Mayan du document créé."""
    _log.debug("create_document : démarré (label=%s, jamais le mot de passe ici)", label)
    start = time.monotonic()
    try:
        resp = requests.post(
            f"{mayan_base}/api/v4/documents/",
            auth=_auth(username, password),
            data={"document_type_id": document_type_id, "label": label},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        _log.debug("create_document : ÉCHEC réseau -- %s", exc)
        raise MayanError(f"impossible de joindre Mayan pour créer le document : {exc}") from exc
    _raise_with_detail(resp, "création du document Mayan échouée")
    elapsed_ms = int((time.monotonic() - start) * 1000)
    data = _safe_json(resp, "création du document Mayan échouée")
    try:
        doc_id = data["id"]
    except (TypeError, KeyError):
        raise MayanError(f"création du document Mayan échouée : réponse JSON sans clé 'id' -- {str(data)[:300]!r}")
    _log.debug("create_document : succès en %d ms (document_id=%s)", elapsed_ms, doc_id)
    return doc_id


def upload_file(mayan_base, username, password, document_id, file_stream, filename, is_new_version=False, timeout=120):
    """Envoie `file_stream` comme nouveau "document file" Mayan --
    PREMIER fichier (`is_new_version=False`) OU nouvelle VERSION
    (`is_new_version=True`). Timeout plus long que le reste de ce
    module (120s, pas 15) -- un envoi de fichier peut prendre du
    temps sur une connexion lente, contrairement aux autres appels
    JSON légers ci-dessus/dessous.

    **Correctif #166** : `action_name` est TOUJOURS envoyé, y
    compris pour le PREMIER fichier -- confirmé par un vrai test
    contre Mayan 4.11 (`{'action_name': ['This field is
    required.']}`), contredisant l'hypothèse initiale de #158 (ce
    champ pensé optionnel hors nouvelle version, d'après une
    documentation glanée qui ne le mentionnait QUE dans le contexte
    "nouvelle version"). `is_new_version` reste un paramètre de CE
    module (clarté d'appel côté app.py), mais n'influence plus la
    valeur envoyée -- aucune AUTRE valeur que "replace" n'est
    documentée nulle part pour ce champ, y compris pour un document
    flambant neuf sans fichier préexistant.

    `202` est la réponse NORMALE (traitement Celery ASYNCHRONE, voir
    docstring du module) -- renvoyé tel quel, aucune attente ici."""
    data = {"action_name": "replace"}
    try:
        resp = requests.post(
            f"{mayan_base}/api/v4/documents/{document_id}/files/",
            auth=_auth(username, password),
            files={"file_new": (filename, file_stream)},
            data=data,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MayanError(f"impossible de joindre Mayan pour envoyer le fichier : {exc}") from exc
    _raise_with_detail(resp, "envoi du fichier vers Mayan échoué")
    return resp.status_code


def get_document(mayan_base, username, password, document_id, timeout=15):
    """Renvoie les métadonnées du document (label, etc.), ou None si
    le document n'existe pas (404 côté Mayan) -- vérification
    EXPLICITE de l'existence, jamais déduite indirectement d'un autre
    endpoint (ex. la liste de ses fichiers, qui pourrait répondre
    différemment sur un document absent -- voir list_document_files
    ci-dessous, comportement non confirmé dans ce cas précis)."""
    try:
        resp = requests.get(
            f"{mayan_base}/api/v4/documents/{document_id}/",
            auth=_auth(username, password),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MayanError(f"impossible de joindre Mayan pour récupérer le document : {exc}") from exc
    if resp.status_code == 404:
        return None
    _raise_with_detail(resp, "récupération du document Mayan échouée")
    return _safe_json(resp, "récupération du document Mayan échouée")


def list_document_files(mayan_base, username, password, document_id, timeout=15):
    """Liste les "document files" Mayan (chaque envoi = une entrée,
    correspond aux VERSIONS successives côté ged-api). Ordre tel que
    renvoyé par Mayan -- jamais retrié ici pour ne pas présumer d'un
    ordre non confirmé par une source directe (voir docstring du
    module, "MOINS CERTAIN")."""
    try:
        resp = requests.get(
            f"{mayan_base}/api/v4/documents/{document_id}/files/",
            auth=_auth(username, password),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MayanError(f"impossible de joindre Mayan pour lister les fichiers : {exc}") from exc
    _raise_with_detail(resp, "liste des fichiers Mayan échouée")
    return _safe_json(resp, "liste des fichiers Mayan échouée").get("results", [])


def download_file(mayan_base, username, password, document_id, file_id, timeout=120):
    """Renvoie (contenu_binaire, content_type, filename_original) du
    fichier Mayan précis.

    **Correctif #168** : l'URL de téléchargement se CONSTRUIT
    directement (`.../files/<file_id>/download/`) -- confirmé par un
    VRAI test contre Mayan 4.11 (`curl -I`, 200 OK, `Content-Disposition`
    avec le nom de fichier déjà présent). L'hypothèse initiale de
    #158 (récupérer d'abord les métadonnées du fichier pour un champ
    `download_url`) était fausse -- ce champ n'existe PAS dans la
    réponse réelle (confirmé par le JSON complet fourni par la
    personne) -- un appel réseau de moins, plus simple ET plus
    robuste."""
    url = f"{mayan_base}/api/v4/documents/{document_id}/files/{file_id}/download/"
    try:
        resp = requests.get(url, auth=_auth(username, password), timeout=timeout)
    except requests.RequestException as exc:
        raise MayanError(f"impossible de joindre Mayan pour télécharger le fichier : {exc}") from exc
    _raise_with_detail(resp, "téléchargement du fichier Mayan échoué")
    filename = _filename_from_content_disposition(resp.headers.get("Content-Disposition", "")) \
        or f"document-{document_id}-fichier-{file_id}"
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream"), filename


def _filename_from_content_disposition(header_value):
    """Extrait le nom de fichier de `Content-Disposition:
    attachment; filename="..."` -- Mayan le fournit déjà tout fait
    (confirmé par un vrai test, #168), jamais besoin de le redemander
    séparément. None si l'en-tête est absent ou mal formé (jamais une
    exception -- l'appelant retombe alors sur un nom générique)."""
    match = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';]+)', header_value)
    if not match:
        return None
    return match.group(1).strip()


def delete_document(mayan_base, username, password, document_id, timeout=15):
    """Best-effort sur les 404 -- un document DÉJÀ absent (ex. nettoyage
    d'un document orphelin déjà supprimé entre-temps) n'est jamais une
    erreur bloquante ici."""
    try:
        resp = requests.delete(
            f"{mayan_base}/api/v4/documents/{document_id}/",
            auth=_auth(username, password),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise MayanError(f"impossible de joindre Mayan pour supprimer le document : {exc}") from exc
    if resp.status_code == 404:
        return
    _raise_with_detail(resp, "suppression du document Mayan échouée")
