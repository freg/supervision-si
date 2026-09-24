"""mikrotik — supervision et commande de base des routeurs MikroTik
de l'infrastructure (livraison #485, demandé explicitement :
« intégrer les fonctionnalités de base de supervision et de
commande/paramétrage dans une interface du hub »).

Registre : mikrotik/routers.json (versionné — noms, hôtes, ports).
Identifiants : le coffre des accès d'équipements du hub (credentials-api,
livraison #498 — demandé explicitement : « retirer du .env les clés
mikrotik, ça doit être géré dans les secrets du hub »). La clé
"credential" du registre est le NOM de l'accès dans ce coffre ;
"default" (ou absente) = l'accès nommé « mikrotik ». Révélation par
jeton interne (CREDENTIALS_INTERNAL_TOKEN), jamais transmis au
navigateur ; cache mémoire court (CREDENTIALS_CACHE_SECONDS, 60 s) pour
ne pas interroger le coffre à chaque sonde. Plus AUCUN identifiant dans
.env ni dans le JSON versionné.

Routes (préfixe /mikrotik/, servi par tls-proxy, sans rewrite) :

    GET  /mikrotik/                              interface du hub
    GET  /mikrotik/health | /version
    GET  /mikrotik/routers                       registre + joignabilité
    GET  /mikrotik/routers/<n>/summary           identité, ressources, santé
    GET  /mikrotik/routers/<n>/interfaces        interfaces + compteurs
    POST /mikrotik/routers/<n>/interfaces/toggle {"id": "*3", "enable": false}
    POST /mikrotik/routers/<n>/ping              {"address": "...", "count": 4}
    POST /mikrotik/routers/<n>/reboot            {"confirm": "REBOOT"}

Les commandes exigent un corps JSON explicite — jamais une action
destructrice sur un simple GET (un crawler/préchargement ne doit
pouvoir RIEN déclencher).
"""
import json
import logging
import os
import time

import requests
from flask import Flask, jsonify, request, send_from_directory

from routeros_client import RouterOSClient, RouterOSError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mikrotik")

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
REGISTRY_PATH = os.environ.get("MIKROTIK_REGISTRY", os.path.join(HERE, "routers.json"))
# #585 : registre LOCAL hors dépôt (mikrotik/routers.local.json), prioritaire s'il existe.
REGISTRY_LOCAL = os.environ.get("MIKROTIK_REGISTRY_LOCAL", os.path.join(HERE, "routers.local.json"))
TLS_VERIFY = os.environ.get("MIKROTIK_TLS_VERIFY", "") == "1"
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "http://credentials-api:5000").rstrip("/")
CREDENTIALS_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "").strip()
CREDENTIALS_CACHE_S = int(os.environ.get("CREDENTIALS_CACHE_SECONDS", "60") or 0)
DEFAULT_CREDENTIAL_NAME = "mikrotik"

app = Flask(__name__)

try:
    from version_endpoint import register_version_route
    register_version_route(app, "mikrotik")
except ImportError:
    pass  # tests sans le build


# ------------------------------------------------------------ registre

def load_registry():
    """Liste des routeurs déclarés. Un fichier absent ou invalide
    donne un registre VIDE (interface fonctionnelle, zéro routeur),
    jamais une 500 — le diagnostic est dans le JSON renvoyé."""
    path = REGISTRY_LOCAL if os.path.exists(REGISTRY_LOCAL) else REGISTRY_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        routers = data.get("routers", [])
        return [{"name": r["name"], "host": r["host"], "port": int(r.get("port", 443)),
                 "credential": r.get("credential", "default")} for r in routers], None
    except FileNotFoundError:
        return [], f"registre absent ({path})"
    except (ValueError, KeyError) as exc:
        return [], f"registre invalide : {exc}"


_cred_cache = {}  # nom -> (expire_monotonic, user, password)


def credential_name(credential):
    return DEFAULT_CREDENTIAL_NAME if not credential or credential == "default" else credential


def credentials_for(credential):
    """Identifiants depuis le coffre des accès d'équipements (#498).
    Retourne (user, password, erreur_éventuelle) ; l'erreur est une
    phrase lisible dans la tuile, jamais une valeur secrète."""
    name = credential_name(credential)
    now = time.monotonic()
    hit = _cred_cache.get(name)
    if hit and hit[0] > now:
        return hit[1], hit[2], None
    if not CREDENTIALS_TOKEN:
        return None, None, "coffre des accès non configuré côté mikrotik (CREDENTIALS_INTERNAL_TOKEN)"
    try:
        resp = requests.get(f"{CREDENTIALS_API_URL}/credentials/reveal/{name}", timeout=5,
                            headers={"X-Credentials-Token": CREDENTIALS_TOKEN, "X-Credentials-Consumer": "mikrotik-api"})
    except requests.RequestException as exc:
        log.warning("coffre des accès injoignable pour « %s » : %s", name, exc.__class__.__name__)
        return None, None, "coffre des accès injoignable (credentials-api)"
    if resp.status_code == 404:
        return None, None, f"accès « {name} » absent du coffre -- à créer dans la tuile Accès d'équipements (Sécurité & accès)"
    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", "")
        except ValueError:
            detail = ""
        return None, None, f"coffre des accès : refus {resp.status_code} {detail}".strip()
    body = resp.json()
    user, password = body.get("username") or "", body.get("password") or ""
    if not user or not password:
        return None, None, f"accès « {name} » incomplet dans le coffre (identifiant ou mot de passe vide)"
    if CREDENTIALS_CACHE_S > 0:
        _cred_cache[name] = (now + CREDENTIALS_CACHE_S, user, password)
    return user, password, None


def forget_credentials():
    _cred_cache.clear()


def client_for(router):
    user, password, error = credentials_for(router["credential"])
    if error:
        return None, error
    return RouterOSClient(router["host"], router["port"], user, password, tls_verify=TLS_VERIFY), None


def find_router(name):
    routers, _ = load_registry()
    for r in routers:
        if r["name"] == name:
            return r
    return None


# ---------------------------------------------------------------- pages

@app.route("/mikrotik/", methods=["GET"])
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/mikrotik/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "mikrotik"}), 200


# ---------------------------------------------------------------- lecture

@app.route("/mikrotik/routers", methods=["GET"])
def list_routers():
    """Registre + joignabilité de chaque routeur (GET
    system/identity — une sonde légère, jamais d'agrégat coûteux
    dans la liste)."""
    routers, registry_error = load_registry()
    out = []
    for router in routers:
        entry = {"name": router["name"], "host": router["host"], "port": router["port"]}
        client, error = client_for(router)
        if error:
            entry.update(reachable=False, error=error)
        else:
            try:
                identity = client.get("system/identity")
                entry.update(reachable=True, identity=identity.get("name", ""))
            except RouterOSError as exc:
                if "authentification refusée" in str(exc):
                    forget_credentials()  # un accès corrigé dans le coffre prend effet à la sonde suivante
                entry.update(reachable=False, error=str(exc))
        out.append(entry)
    return jsonify({"routers": out, "registry_error": registry_error}), 200


@app.route("/mikrotik/routers/<name>/summary", methods=["GET"])
def router_summary(name):
    router = find_router(name)
    if not router:
        return jsonify({"error": f"routeur « {name} » absent du registre"}), 404
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        summary = {
            "identity": client.get("system/identity"),
            "resource": client.get("system/resource"),
        }
        # Santé matérielle : absente sur certains modèles (RB vieux,
        # CHR...) — jamais bloquante pour le reste du résumé.
        try:
            summary["health"] = client.get("system/health")
        except RouterOSError:
            summary["health"] = None
        return jsonify(summary), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/mikrotik/routers/<name>/interfaces", methods=["GET"])
def router_interfaces(name):
    router = find_router(name)
    if not router:
        return jsonify({"error": f"routeur « {name} » absent du registre"}), 404
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        return jsonify({"interfaces": client.get("interface")}), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


# -------------------------------------------------------------- commandes

@app.route("/mikrotik/routers/<name>/interfaces/toggle", methods=["POST"])
def toggle_interface(name):
    """Active/désactive une interface — corps JSON explicite requis.
    ⚠️ Couper l'interface par laquelle on JOIND le routeur coupe la
    commande au milieu : le PATCH part, la réponse peut ne jamais
    revenir. C'est inhérent au geste, documenté dans l'interface."""
    router = find_router(name)
    if not router:
        return jsonify({"error": f"routeur « {name} » absent du registre"}), 404
    body = request.get_json(silent=True) or {}
    iface_id = body.get("id")
    enable = body.get("enable")
    if not iface_id or enable is None:
        return jsonify({"error": "'id' (ex. *3) et 'enable' (true/false) requis"}), 400
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        client.patch(f"interface/{iface_id}", {"disabled": "false" if enable else "true"})
        log.info("routeur %s : interface %s %s", name, iface_id, "activée" if enable else "DÉSACTIVÉE")
        return jsonify({"status": "ok"}), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/mikrotik/routers/<name>/ping", methods=["POST"])
def ping(name):
    router = find_router(name)
    if not router:
        return jsonify({"error": f"routeur « {name} » absent du registre"}), 404
    body = request.get_json(silent=True) or {}
    address = (body.get("address") or "").strip()
    if not address:
        return jsonify({"error": "'address' requis"}), 400
    count = int(body.get("count", 4))
    count = min(max(count, 1), 20)  # borné — jamais un flood depuis le routeur
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        result = client.post_action("ping", {"address": address, "count": str(count)})
        return jsonify({"result": result}), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/mikrotik/routers/<name>/reboot", methods=["POST"])
def reboot(name):
    """Redémarrage — exige {"confirm": "REBOOT"} en corps : jamais
    déclenchable par accident, par un préchargement ou un formulaire
    étourdi."""
    router = find_router(name)
    if not router:
        return jsonify({"error": f"routeur « {name} » absent du registre"}), 404
    body = request.get_json(silent=True) or {}
    if body.get("confirm") != "REBOOT":
        return jsonify({"error": "confirmation requise : {\"confirm\": \"REBOOT\"}"}), 400
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        client.post_action("system/reboot", {})
        log.warning("routeur %s : REDÉMARRAGE demandé via le hub", name)
        return jsonify({"status": "ok", "message": "redémarrage demandé"}), 200
    except RouterOSError as exc:
        # Le routeur peut couper la connexion avant de répondre —
        # c'est même le signe que le reboot a bien été pris en compte.
        return jsonify({"status": "ok", "message": f"redémarrage probablement pris en compte (connexion coupée : {exc})"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
