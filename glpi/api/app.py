"""
glpi-api -- livraison #192, backlog : "évolution d'intégration GLPI,
une tuile et une api pour utiliser l'api glpi et ses données dans les
autres tuiles du hub" (demande explicite). Ce service est le
DÉBUT de cette intégration -- pour l'instant, seulement ce qu'il
fallait pour le "besoin immédiat" explicite (import de l'inventaire
Excel fourni) : la connexion GLPI elle-même (`glpi_client.py`) et
l'import (`excel_import.py`). PAS ENCORE l'exposition des données
GLPI aux autres tuiles du hub (le "api... dans les autres tuiles" de
la demande) -- volontairement laissé pour une prochaine étape, une
fois ce premier import validé en conditions réelles.

**⚠️ Jamais testé contre un vrai GLPI** -- voir glpi_client.py pour
le détail complet. Toute la logique HTTP est construite à partir de
la documentation officielle de l'API historique GLPI (`apirest.php`),
mais SEULE une vraie tentative contre le GLPI réel de la personne
confirmera que tout s'enchaîne correctement -- commencer PAR le mode
dry-run (voir POST /import/excel, paramètre `dry_run`), jamais
directement en écriture sur un GLPI de production.

UN SEUL compte GLPI configuré (`.env`) -- pas de gestion multi-
instances, jamais demandée explicitement.
"""
import logging
import os
import tempfile

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

import glpi_client as glpi
import excel_import
import nebula_import
import nebula_clients_import
import snmp_import
import network_agent_import

_log = logging.getLogger("glpi_app")

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "glpi-api")

GLPI_BASE_URL = os.environ.get("GLPI_BASE_URL", "").strip().rstrip("/")
GLPI_APP_TOKEN = os.environ.get("GLPI_APP_TOKEN", "").strip() or None
GLPI_USER_TOKEN = os.environ.get("GLPI_USER_TOKEN", "").strip() or None
GLPI_LOGIN = os.environ.get("GLPI_LOGIN", "").strip() or None
GLPI_PASSWORD = os.environ.get("GLPI_PASSWORD", "") or None

# Livraison #294 -- suite du backlog item 38, cinquième service
# branché après ssh-tunnels-api (#289), ldap-admin-api (#290),
# vault-admin-api (#291), dba-api (#292). Aucune décision explicite
# préexistante trouvée dans ce module contraire à ce branchement --
# procédé directement, même motif éprouvé quatre fois déjà. OPT-IN,
# vide/absent = gating désactivé (comportement identique à avant
# #294).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif que les services précédents -- FAIL CLOSED, jamais
    fail-open, y compris pour admin_hub si rights-api est injoignable
    ou répond de façon inattendue."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "glpi-api", "resource_id": None, "action": "manage"},
            timeout=5,
        )
    except requests.RequestException as exc:
        _log.debug("_check_manage_right : rights-api injoignable, refus par prudence -- %s", exc)
        return False, "service de droits injoignable -- action refusée par prudence"
    if resp.status_code != 200:
        _log.debug("_check_manage_right : rights-api a répondu %s", resp.status_code)
        return False, "service de droits indisponible -- action refusée par prudence"
    try:
        allowed = resp.json().get("allowed", False)
    except ValueError:
        return False, "réponse du service de droits illisible -- action refusée par prudence"
    if not allowed:
        _log.debug("_check_manage_right : refusé pour les groupes %s", groups)
    return allowed, None if allowed else "droit 'manage' sur glpi-api requis (groupe admin_hub, ou un octroi explicite)"

# URL interne vers nebula-api (livraison #208, backlog item 16) --
# résolution DNS Docker Compose standard (nom de service = nom
# d'hôte sur le réseau partagé), même motif que MEMCACHED_HOST
# ailleurs dans ce projet -- jamais un chemin public, appel
# CONTENEUR-À-CONTENEUR uniquement.
NEBULA_API_INTERNAL_URL = os.environ.get("NEBULA_API_INTERNAL_URL", "http://nebula-api:5000").rstrip("/")
# URL interne vers snmp-api (livraison #232, backlog "remplir GLPI
# automatiquement... nos futurs outils d'exploration") -- même motif
# que NEBULA_API_INTERNAL_URL ci-dessus.
SNMP_API_INTERNAL_URL = os.environ.get("SNMP_API_INTERNAL_URL", "http://snmp-api:5000").rstrip("/")
# URL interne vers network-agent-api (livraison #264, "je veux
# exporter vers glpi tout ce qu'on va découvrir par l'exploration
# réseau") -- ⚠️ CE service tourne en network_mode: host (#238-239),
# JAMAIS le nom de service Docker habituel -- même piège déjà
# rencontré pour backup-restore-api/#249, architecture-api/#254,
# vigilance-api/#262.
NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/")
# URL interne vers classifier-api (#260) -- OPTIONNELLE, pour le
# filtrage des catégories transitoires (ex. clients DHCP dynamiques)
# à l'export, voir network_agent_import.py.
CLASSIFIER_API_INTERNAL_URL = os.environ.get("CLASSIFIER_API_INTERNAL_URL", "http://classifier-api:5000").rstrip("/")


def _connect():
    """Lève glpi.GlpiError si .env n'est pas encore renseigné --
    jamais une KeyError confuse plus loin, un message actionnable dès
    la première tentative de connexion (même motif que _connect()
    dans imap-client/api/app.py)."""
    if not GLPI_BASE_URL:
        raise glpi.GlpiError("GLPI_BASE_URL non configuré -- voir glpi/README.md pour les variables .env attendues")
    if not GLPI_USER_TOKEN and not (GLPI_LOGIN and GLPI_PASSWORD):
        raise glpi.GlpiError("GLPI_USER_TOKEN, ou GLPI_LOGIN+GLPI_PASSWORD, requis -- voir glpi/README.md")
    client = glpi.GlpiClient(GLPI_BASE_URL, app_token=GLPI_APP_TOKEN)
    client.init_session(GLPI_LOGIN, GLPI_PASSWORD, user_token=GLPI_USER_TOKEN)
    return client


@app.route("/test-connection", methods=["GET"])
def test_connection():
    """Vérifie SEULEMENT que la connexion/authentification GLPI
    fonctionne -- jamais d'écriture, juste initSession puis
    killSession. Premier appel à faire après configuration, avant
    tout import réel."""
    try:
        client = _connect()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502
    client.kill_session()
    return jsonify({"status": "ok", "message": "connexion GLPI réussie"}), 200


# Types d'actifs concernés par la suppression/le listing individuel
# (livraison #269) -- ceux réellement produits par LES IMPORTS de ce
# module (Excel, Nebula, SNMP, network-agent) -- jamais une liste de
# TOUS les itemtypes GLPI possibles, hors de portée de ce qui est
# réellement géré ici.
MANAGED_ITEMTYPES = {"Computer", "NetworkEquipment"}


@app.route("/items/<itemtype>", methods=["GET"])
def list_items_of_type(itemtype):
    """Listing plus complet qu'/inventory-summary (qui plafonne
    volontairement à 20 pour un simple résumé) -- pour parcourir/
    sélectionner des items existants avant une suppression
    individuelle (livraison #269). `range` (query string, défaut
    "0-99") transmis tel quel à GLPI."""
    if itemtype not in MANAGED_ITEMTYPES:
        return jsonify({"error": f"'{itemtype}' non géré par ce module -- voir MANAGED_ITEMTYPES"}), 400
    try:
        client = _connect()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        items = client.get_items(itemtype, range_str=request.args.get("range", "0-99"))
    except glpi.GlpiError as exc:
        client.kill_session()
        return jsonify({"error": str(exc)}), 502
    client.kill_session()
    return jsonify(items), 200


@app.route("/items/<itemtype>/<int:item_id>", methods=["DELETE"])
def delete_item_route(itemtype, item_id):
    """Suppression INDIVIDUELLE (livraison #269, demandé
    explicitement -- "partout dans les imports/exports y a t'il la
    possibilité d'annuler ou de supprimer en sélectionnant
    individuellement ?"). `force_purge` (query string, défaut
    `false`) -- voir `glpi_client.delete_item` pour le raisonnement
    complet (SANS ce paramètre, GLPI déplace l'item dans SA PROPRE
    corbeille -- récupérable, l'équivalent natif d'un "annuler",
    jamais un mécanisme de undo maison nécessaire ici)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    if itemtype not in MANAGED_ITEMTYPES:
        return jsonify({"error": f"'{itemtype}' non géré par ce module -- voir MANAGED_ITEMTYPES"}), 400
    force_purge = request.args.get("force_purge", "false").strip().lower() == "true"
    try:
        client = _connect()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        success = client.delete_item(itemtype, item_id, force_purge=force_purge)
    except glpi.GlpiError as exc:
        client.kill_session()
        return jsonify({"error": str(exc)}), 502
    client.kill_session()
    status_code = 200 if success else 404
    return jsonify({"status": "ok" if success else "not_found", "deleted": success}), status_code


@app.route("/inventory-summary", methods=["GET"])
def inventory_summary():
    """Résumé en LECTURE SEULE de l'inventaire déjà connu de GLPI
    (livraison #231, backlog item 21) -- PAS une configuration de
    tâche de découverte/inventaire (la découverte native GLPI 10+
    remplace l'ancien plugin FusionInventory par un mécanisme dont
    l'itemtype API exact n'a jamais été vérifié dans ce projet --
    voir docs/preparation-glpi-inventory.docx pour ce qui reste à
    cadrer). Montre ce que GLPI sait DÉJÀ, jamais plus -- volontairement
    limité pour ne jamais présenter une action de configuration non
    vérifiée."""
    try:
        client = _connect()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502
    try:
        computers = client.get_items("Computer", range_str="0-999")
        network_equipment = client.get_items("NetworkEquipment", range_str="0-999")
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502
    finally:
        client.kill_session()

    def summarize(items):
        items = items if isinstance(items, list) else []
        return {
            "count": len(items),
            "capped": len(items) >= 999,  # jamais un total exact au-delà -- honnête plutôt qu'approximé
            "sample": [{"id": it.get("id"), "name": it.get("name")} for it in items[:20]],
        }

    return jsonify({
        "computers": summarize(computers),
        "network_equipment": summarize(network_equipment),
    }), 200


@app.route("/import/excel", methods=["POST"])
def import_excel_route():
    """Fichier Excel en `multipart/form-data` (champ `file`) --
    `dry_run` (query string, défaut `true`) : si `true`, AUCUN appel
    d'écriture vers GLPI, juste un aperçu de ce qui serait créé --
    TOUJOURS commencer par ça avant `dry_run=false` (voir docstring
    du module)."""
    # Livraison #294 -- envoi MULTIPART (fichier), jamais de corps
    # JSON -- groups transmis comme champ de formulaire ordinaire
    # (valeurs séparées par des virgules), même motif que
    # dba-api/import_mysql_dump (#292).
    groups_field = request.form.get("groups", "")
    groups = [g.strip() for g in groups_field.split(",") if g.strip()]
    allowed, error = _check_manage_right({"groups": groups})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" not in request.files:
        return jsonify({"error": "fichier requis (champ 'file', multipart/form-data)"}), 400
    dry_run = request.args.get("dry_run", "true").strip().lower() != "false"
    sheet_name = request.args.get("sheet", "Devices")

    uploaded = request.files["file"]
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        uploaded.save(tmp.name)
        tmp_path = tmp.name

    try:
        if dry_run:
            # Client jamais connecté en dry-run -- aucun appel réseau
            # vers GLPI n'est nécessaire pour PRÉVISUALISER (voir
            # excel_import.import_excel, dry_run court-circuite tous
            # les appels d'écriture ET de lecture de dédoublonnage).
            client = glpi.GlpiClient(GLPI_BASE_URL or "https://dry-run.invalid")
        else:
            client = _connect()
        try:
            summary = excel_import.import_excel(client, tmp_path, sheet_name=sheet_name, dry_run=dry_run)
        finally:
            if not dry_run:
                client.kill_session()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:  # noqa: BLE001 -- fichier malformé, feuille absente, etc. -- jamais un 500 nu
        return jsonify({"error": f"import échoué : {exc}"}), 400
    finally:
        os.unlink(tmp_path)

    return jsonify({"dry_run": dry_run, **summary}), 200


@app.route("/import/nebula-devices", methods=["POST"])
def import_nebula_devices_route():
    """Import des appareils Nebula DÉJÀ importés côté nebula-api
    (#200) vers GLPI (livraison #208, backlog item 16). Appel
    CONTENEUR-À-CONTENEUR vers nebula-api (jamais l'API Nebula
    publique directement -- ce service ne connaît que nebula-api, pas
    Zyxel) -- voir nebula_import.py pour le détail du mapping.
    `dry_run` (query string, défaut `true`) -- même garde que
    /import/excel, TOUJOURS commencer par un aperçu. Corps JSON
    optionnel {"only_macs": [...]} (livraison #269, sélection
    multiple demandée explicitement) -- sans corps, tout est importé
    (comportement inchangé)."""
    dry_run = request.args.get("dry_run", "true").strip().lower() != "false"
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    only_macs = set(body["only_macs"]) if isinstance(body.get("only_macs"), list) else None

    try:
        resp = requests.get(f"{NEBULA_API_INTERNAL_URL}/imported/devices", timeout=15)
    except requests.RequestException as exc:
        _log.debug("import_nebula_devices_route : appel à nebula-api échoué -- %s", exc)
        return jsonify({"error": f"appel à nebula-api échoué : {exc}"}), 502
    if resp.status_code != 200:
        _log.debug("import_nebula_devices_route : nebula-api a répondu %s", resp.status_code)
        return jsonify({"error": f"nebula-api a répondu {resp.status_code} : {resp.text[:300]}"}), 502
    try:
        nebula_devices = resp.json()
    except ValueError:
        return jsonify({"error": "réponse de nebula-api illisible (pas du JSON valide)"}), 502
    if not isinstance(nebula_devices, list):
        return jsonify({"error": "réponse de nebula-api inattendue (liste attendue)"}), 502

    try:
        if dry_run:
            client = glpi.GlpiClient(GLPI_BASE_URL or "https://dry-run.invalid")
        else:
            client = _connect()
        try:
            summary = nebula_import.import_devices(client, nebula_devices, dry_run=dry_run, only_macs=only_macs)
        finally:
            if not dry_run:
                client.kill_session()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"dry_run": dry_run, "source_device_count": len(nebula_devices), **summary}), 200


@app.route("/import/nebula-clients", methods=["POST"])
def import_nebula_clients_route():
    """Import des CLIENTS Nebula (livraison #269, demandé
    explicitement : "à partir des logs de nebula je peux exporter
    les clients connectés ou récemment connectés... pourra t'on les
    injecter dans glpi") -- DISTINCT de /import/nebula-devices
    (équipements d'infrastructure). Voir nebula_clients_import.py
    pour le détail complet (type GLPI Computer, pas
    NetworkEquipment). `dry_run` (défaut `true`, même garde que les
    autres imports). Corps JSON optionnel {"only_macs": [...]} --
    sélection multiple, sans corps tout est importé."""
    dry_run = request.args.get("dry_run", "true").strip().lower() != "false"
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    only_macs = set(body["only_macs"]) if isinstance(body.get("only_macs"), list) else None

    try:
        resp = requests.get(f"{NEBULA_API_INTERNAL_URL}/imported/clients", timeout=15)
    except requests.RequestException as exc:
        _log.debug("import_nebula_clients_route : appel à nebula-api échoué -- %s", exc)
        return jsonify({"error": f"appel à nebula-api échoué : {exc}"}), 502
    if resp.status_code != 200:
        _log.debug("import_nebula_clients_route : nebula-api a répondu %s", resp.status_code)
        return jsonify({"error": f"nebula-api a répondu {resp.status_code} : {resp.text[:300]}"}), 502
    try:
        nebula_clients = resp.json()
    except ValueError:
        return jsonify({"error": "réponse de nebula-api illisible (pas du JSON valide)"}), 502
    if not isinstance(nebula_clients, list):
        return jsonify({"error": "réponse de nebula-api inattendue (liste attendue)"}), 502

    try:
        if dry_run:
            client = glpi.GlpiClient(GLPI_BASE_URL or "https://dry-run.invalid")
        else:
            client = _connect()
        try:
            summary = nebula_clients_import.import_clients(client, nebula_clients, dry_run=dry_run, only_macs=only_macs)
        finally:
            if not dry_run:
                client.kill_session()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"dry_run": dry_run, "source_client_count": len(nebula_clients), **summary}), 200


@app.route("/import/network-agent-devices", methods=["POST"])
def import_network_agent_devices_route():
    """Import des appareils découverts par network-agent-api
    (#250-251) vers GLPI (livraison #264, "je veux exporter vers glpi
    tout ce qu'on va découvrir par l'exploration réseau").

    ⚠️ `segment_id` (query string, OPTIONNEL mais fortement
    recommandé) -- demandé explicitement après une première
    confusion : "attention ce que le dns te donne qui match le motif
    dhcp123 ce sont les clients wifi du lan de ma structure pas le
    lan de alpha, tu identifiera alpha avec des adresses 172...".
    Deux réseaux DISTINCTS peuvent être surveillés par network-agent
    (un seul agent, plusieurs segments possibles, voir #233) --
    SANS `segment_id`, TOUS les segments connus sont exportés
    ensemble, mélangeant potentiellement le réseau de la structure de
    la personne ET celui d'un client comme Alpha. Préciser
    `segment_id` cible UN SEUL segment (ex. celui identifié par sa
    plage 172.x.x.x pour Alpha).

    `dry_run` (query string, défaut `true`) -- même garde que les
    autres imports, TOUJOURS commencer par un aperçu.
    `exclude_dynamic` (query string, défaut `false`) -- si `true` ET
    que classifier-api est joignable, exclut les appareils classés
    "client_dhcp_dynamique" -- PAR DÉFAUT, RIEN n'est exclu (la
    demande initiale est "tout ce qu'on va découvrir" ; côté Alpha,
    les clients dynamiques sont justement les 200 clients mobiles que
    Nebula ne voit pas lui-même -- la donnée la plus utile à
    remonter, jamais du bruit à filtrer par défaut)."""
    dry_run = request.args.get("dry_run", "true").strip().lower() != "false"
    exclude_dynamic = request.args.get("exclude_dynamic", "false").strip().lower() == "true"
    segment_id = request.args.get("segment_id", type=int)
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    only_macs = set(body["only_macs"]) if isinstance(body.get("only_macs"), list) else None

    if not NETWORK_AGENT_API_URL:
        return jsonify({"error": "NETWORK_AGENT_API_URL non configurée"}), 502
    params = {"segment_id": segment_id} if segment_id else {}
    try:
        resp = requests.get(f"{NETWORK_AGENT_API_URL}/devices", params=params, timeout=15)
    except requests.RequestException as exc:
        _log.debug("import_network_agent_devices_route : appel à network-agent-api échoué -- %s", exc)
        return jsonify({"error": f"appel à network-agent-api échoué : {exc}"}), 502
    if resp.status_code != 200:
        _log.debug("import_network_agent_devices_route : network-agent-api a répondu %s", resp.status_code)
        return jsonify({"error": f"network-agent-api a répondu {resp.status_code} : {resp.text[:300]}"}), 502
    try:
        network_agent_devices = resp.json()
    except ValueError:
        return jsonify({"error": "réponse de network-agent-api illisible (pas du JSON valide)"}), 502
    if not isinstance(network_agent_devices, list):
        return jsonify({"error": "réponse de network-agent-api inattendue (liste attendue)"}), 502

    classifications = {}
    exclude_categories = set()
    if exclude_dynamic:
        exclude_categories = {"client_dhcp_dynamique"}
        with_hostname = [d for d in network_agent_devices if d.get("hostname")]
        if with_hostname:
            try:
                items = [{"text": d["hostname"], "ip_address": d.get("ip_address")} for d in with_hostname]
                clf_resp = requests.post(f"{CLASSIFIER_API_INTERNAL_URL}/classify/batch", json=items, timeout=15)
                if clf_resp.status_code == 200:
                    results = clf_resp.json()
                    for d in with_hostname:
                        r = results.get(d["hostname"])
                        if r and r.get("category"):
                            classifications[d["mac_address"].lower()] = r["category"]
            except (requests.RequestException, ValueError) as exc:
                # ValueError ajouté en #287 -- un corps NON-JSON (200)
                # échappait auparavant à ce filet, contredisant
                # l'intention déjà documentée ci-dessous.
                # classifier-api best-effort -- son indisponibilité ne
                # doit jamais bloquer l'export lui-même, mais reste
                # tracée en DEBUG (convention "rien ne doit être
                # silencieux", même un échec volontairement ignoré).
                _log.debug("import_network_agent_devices_route : classifier-api injoignable (best-effort) -- %s", exc)

    try:
        if dry_run:
            client = glpi.GlpiClient(GLPI_BASE_URL or "https://dry-run.invalid")
        else:
            client = _connect()
        try:
            summary = network_agent_import.import_devices(
                client, network_agent_devices, dry_run=dry_run,
                exclude_categories=exclude_categories, classifications=classifications, only_macs=only_macs,
            )
        finally:
            if not dry_run:
                client.kill_session()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"dry_run": dry_run, "source_device_count": len(network_agent_devices), **summary}), 200


@app.route("/import/snmp-targets", methods=["POST"])
def import_snmp_targets_route():
    """Import des cibles SNMP DÉJÀ enregistrées côté snmp-api (#213)
    vers GLPI (livraison #232). Appel CONTENEUR-À-CONTENEUR vers
    snmp-api pour la LISTE des cibles ET pour INTERROGER chacune (une
    requête /query par cible -- voir snmp_import.py pour le détail du
    mapping). `dry_run` (défaut `true`) -- même garde que les deux
    autres imports de ce fichier, TOUJOURS commencer par un aperçu."""
    dry_run = request.args.get("dry_run", "true").strip().lower() != "false"
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    only_ids = set(body["only_ids"]) if isinstance(body.get("only_ids"), list) else None

    try:
        resp = requests.get(f"{SNMP_API_INTERNAL_URL}/targets", timeout=15)
    except requests.RequestException as exc:
        _log.debug("import_snmp_targets_route : appel à snmp-api échoué -- %s", exc)
        return jsonify({"error": f"appel à snmp-api échoué : {exc}"}), 502
    if resp.status_code != 200:
        _log.debug("import_snmp_targets_route : snmp-api a répondu %s", resp.status_code)
        return jsonify({"error": f"snmp-api a répondu {resp.status_code} : {resp.text[:300]}"}), 502
    try:
        snmp_targets = resp.json()
    except ValueError:
        return jsonify({"error": "réponse de snmp-api illisible (pas du JSON valide)"}), 502
    if not isinstance(snmp_targets, list):
        return jsonify({"error": "réponse de snmp-api inattendue (liste attendue)"}), 502

    def snmp_query_fn(target_id):
        """Une requête SNMP PEUT échouer indépendamment pour CHAQUE
        cible (injoignable, communauté refusée, délai dépassé) --
        jamais laissé remonter comme une exception, toujours un dict
        avec 'error' que snmp_import.import_targets sait déjà
        interpréter (même contrat que pour un succès)."""
        try:
            q = requests.post(f"{SNMP_API_INTERNAL_URL}/query", json={"target_id": target_id}, timeout=20)
        except requests.RequestException as exc:
            _log.debug("snmp_query_fn : appel à snmp-api échoué pour la cible %s -- %s", target_id, exc)
            return {"error": f"appel à snmp-api échoué : {exc}"}
        try:
            body = q.json()
        except ValueError:
            return {"error": "réponse de snmp-api illisible (pas du JSON valide)"}
        if q.status_code != 200:
            return {"error": body.get("error") or f"snmp-api a répondu {q.status_code}"}
        return body

    try:
        if dry_run:
            client = glpi.GlpiClient(GLPI_BASE_URL or "https://dry-run.invalid")
        else:
            client = _connect()
        try:
            summary = snmp_import.import_targets(client, snmp_query_fn, snmp_targets, dry_run=dry_run, only_ids=only_ids)
        finally:
            if not dry_run:
                client.kill_session()
    except glpi.GlpiError as exc:
        return jsonify({"error": str(exc)}), 502

    return jsonify({"dry_run": dry_run, "source_target_count": len(snmp_targets), **summary}), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

try:
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    _MemcacheClient = None

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


SERVICE_NAME = "glpi-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler and _MemcacheClient:
    import logging as _logging
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    _logging.getLogger().addHandler(_log_handler)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
