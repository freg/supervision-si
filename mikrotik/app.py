"""mikrotik — supervision et commande de base des routeurs MikroTik
de l'infrastructure (livraison #485, demandé explicitement :
« intégrer les fonctionnalités de base de supervision et de
commande/paramétrage dans une interface du hub »).

Registre : mikrotik/routers.json (versionné — noms, hôtes, ports).
Identifiants : .env (SECRET, jamais versionné) — partagés
(MIKROTIK_USER / MIKROTIK_PASSWORD) ou par routeur via la clé
"credential" du registre (MIKROTIK_<NOM>_USER / ..._PASSWORD, nom en
MAJUSCULES, tirets → underscores).

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
import re

from flask import Flask, jsonify, request, send_from_directory

from routeros_client import RouterOSClient, RouterOSError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mikrotik")

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
REGISTRY_PATH = os.environ.get("MIKROTIK_REGISTRY", os.path.join(HERE, "routers.json"))
TLS_VERIFY = os.environ.get("MIKROTIK_TLS_VERIFY", "") == "1"

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
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        routers = data.get("routers", [])
        return [{"name": r["name"], "host": r["host"], "port": int(r.get("port", 443)),
                 "credential": r.get("credential", "default")} for r in routers], None
    except FileNotFoundError:
        return [], f"registre absent ({REGISTRY_PATH})"
    except (ValueError, KeyError) as exc:
        return [], f"registre invalide : {exc}"


def credentials_for(credential):
    """Identifiants d'un routeur depuis .env — jamais dans le JSON
    versionné. Retourne (user, password, erreur_éventuelle)."""
    suffix = "" if credential == "default" else "_" + re.sub(r"[^A-Z0-9]", "_", credential.upper())
    user = os.environ.get(f"MIKROTIK{suffix}_USER", "")
    password = os.environ.get(f"MIKROTIK{suffix}_PASSWORD", "")
    if not user or not password:
        expected = f"MIKROTIK{suffix}_USER / MIKROTIK{suffix}_PASSWORD"
        return None, None, f"identifiants absents du .env ({expected})"
    return user, password, None


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
