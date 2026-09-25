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
import natmap  # #606 : carte des redirections
import natrules  # #587
try:
    from notify_client import notify as _notify, register_actions as _register_actions  # #590 (shared/, copié par le Dockerfile)
except ImportError:  # tests hors conteneur
    def _notify(*a, **k):
        return None

    def _register_actions(*a, **k):
        return None
from ssh_client import RouterOSSsh, read_only_command  # #587 : transport SSH, transparent pour le routeur
try:
    import registry_edit  # #592 (shared/, copié par le Dockerfile)
except ImportError:  # tests hors conteneur : shared/ du dépôt
    import sys as _sys
    _sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
    import registry_edit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("mikrotik")

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
REGISTRY_PATH = os.environ.get("MIKROTIK_REGISTRY", os.path.join(HERE, "routers.json"))
# #585 : registre LOCAL hors dépôt (mikrotik/routers.local.json), prioritaire s'il existe.
REGISTRY_LOCAL = os.environ.get("MIKROTIK_REGISTRY_LOCAL", os.path.join(HERE, "routers.local.json"))
TLS_VERIFY = os.environ.get("MIKROTIK_TLS_VERIFY", "") == "1"
SSH_TIMEOUT = int(os.environ.get("MIKROTIK_SSH_TIMEOUT", "12"))
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
        out = []
        for r in routers:
            transport = (r.get("transport") or "rest").lower()  # #587 : "ssh" = CLI par SSH (rien à activer sur le routeur)
            if transport not in ("rest", "ssh"):
                transport = "rest"
            out.append({"name": r["name"], "host": r["host"], "port": int(r.get("port") or (22 if transport == "ssh" else 443)),
                        "credential": r.get("credential", "default"), "transport": transport,
                        "site": r.get("site"), "description": r.get("description")})
        return out, None
    except FileNotFoundError:
        return [], f"registre absent ({path})"
    except (ValueError, KeyError) as exc:
        return [], f"registre invalide : {exc}"


_register_actions([
    {"id": "mikrotik.nat.add", "label": "Règle NAT ajoutée", "severity": "warning"},
    {"id": "mikrotik.nat.change", "label": "Règle NAT modifiée", "severity": "warning"},
    {"id": "mikrotik.nat.remove", "label": "Règle NAT supprimée", "severity": "warning"},
    {"id": "mikrotik.interface.toggle", "label": "Interface activée / désactivée", "severity": "warning"},
    {"id": "mikrotik.reboot", "label": "Redémarrage du routeur", "severity": "critical"},
])

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
    if router.get("transport") == "ssh":
        return RouterOSSsh(router["host"], router["port"], user, password, timeout=SSH_TIMEOUT), None
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
        entry = {"name": router["name"], "host": router["host"], "port": router["port"], "transport": router["transport"],
                 "credential": router["credential"], "site": router.get("site"), "description": router.get("description")}
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
        _notify("mikrotik.interface.toggle", "%s : interface %s %s" % (name, iface_id, "activée" if enable else "désactivée"), "Routeur %s (%s)." % (name, router["host"]), {"router": name})
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
        _notify("mikrotik.reboot", "%s : redémarrage demandé" % name, "Routeur %s (%s) redémarré depuis le hub." % (name, router["host"]), {"router": name})
        return jsonify({"status": "ok", "message": "redémarrage demandé"}), 200
    except RouterOSError as exc:
        # Le routeur peut couper la connexion avant de répondre —
        # c'est même le signe que le reboot a bien été pris en compte.
        return jsonify({"status": "ok", "message": f"redémarrage probablement pris en compte (connexion coupée : {exc})"}), 200


# ------------------------------------------------------ règles NAT (#587)
# Périmètre donné : « j'ai le droit de modifier des NAT ip:port/ip:port ».
# Valeurs validées par natrules.py (jamais de chaîne libre vers le routeur),
# chaque geste journalisé avec le routeur et la règle.

def _router_or_404(name):
    router = find_router(name)
    if not router:
        return None, (jsonify({"error": f"routeur « {name} » absent du registre"}), 404)
    return router, None


def _nat_rows(client):
    rows = client.nat_list() if hasattr(client, "nat_list") else client.get("ip/firewall/nat")
    for r in rows:
        r["summary"] = natrules.describe(r)
    return rows


@app.route("/mikrotik/routers/<name>/nat", methods=["GET"])
def nat_list(name):
    router, err = _router_or_404(name)
    if err:
        return err
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        return jsonify({"rules": _nat_rows(client), "transport": router["transport"]}), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/mikrotik/nat-map", methods=["GET"])
def nat_map():
    """#606 : carte des redirections NAT de TOUS les routeurs du registre
    (entrée → routeur → cible), conflits de port, sortants, désactivées.
    Un routeur injoignable apparaît avec son erreur, jamais une 500."""
    routers, registry_error = load_registry()
    site = request.args.get("site")
    per = []
    for router in routers:
        if site and router.get("site") != site:
            continue
        entry = {"name": router["name"], "host": router["host"], "site": router.get("site"), "reachable": True, "rules": []}
        client, error = client_for(router)
        if error:
            entry.update(reachable=False, error=error)
        else:
            try:
                entry["rules"] = _nat_rows(client)
            except RouterOSError as exc:
                entry.update(reachable=False, error=str(exc))
        per.append(entry)
    m = natmap.build(per)
    m["registry_error"] = registry_error
    return jsonify(m), 200


@app.route("/mikrotik/routers/<name>/nat", methods=["POST"])
def nat_add(name):
    router, err = _router_or_404(name)
    if err:
        return err
    fields, errors = natrules.validate(request.get_json(silent=True) or {})
    if errors:
        return jsonify({"error": "règle refusée", "errors": errors}), 400
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        if hasattr(client, "nat_add"):
            res = client.nat_add(fields)
        else:
            res = client._request("PUT", "ip/firewall/nat", json=fields)
        log.warning("routeur %s : règle NAT AJOUTÉE %s (%s)", name, natrules.describe(fields), fields.get("comment") or "")
        _notify("mikrotik.nat.add", "%s : règle NAT ajoutée %s" % (name, natrules.describe(fields)), "Routeur %s (%s)\nRègle : %s\nCommentaire : %s" % (name, router["host"], json.dumps(fields, ensure_ascii=False), fields.get("comment") or "-"), {"router": name, "rule": fields})
        return jsonify({"status": "ok", "rule": fields, "result": res}), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/mikrotik/routers/<name>/nat/<ident>", methods=["PATCH", "DELETE"])
def nat_edit(name, ident):
    router, err = _router_or_404(name)
    if err:
        return err
    if not natrules.re.match(r"^\*[0-9A-Fa-f]{1,8}$", ident):
        return jsonify({"error": "identifiant de règle attendu (ex. *1A)"}), 400
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        if request.method == "DELETE":
            if (request.get_json(silent=True) or {}).get("confirm") != "REMOVE":
                return jsonify({"error": "confirmation requise : {\"confirm\": \"REMOVE\"}"}), 400
            if hasattr(client, "nat_remove"):
                client.nat_remove(ident)
            else:
                client._request("DELETE", f"ip/firewall/nat/{ident}")
            log.warning("routeur %s : règle NAT %s SUPPRIMÉE", name, ident)
            _notify("mikrotik.nat.remove", "%s : règle NAT %s supprimée" % (name, ident), "Routeur %s (%s), règle %s." % (name, router["host"], ident), {"router": name, "id": ident})
            return jsonify({"status": "ok"}), 200
        fields, errors = natrules.validate(request.get_json(silent=True) or {}, partial=True)
        if errors:
            return jsonify({"error": "modification refusée", "errors": errors}), 400
        if not fields:
            return jsonify({"error": "aucun champ à modifier"}), 400
        client.patch(f"ip/firewall/nat/{ident}", fields)
        log.warning("routeur %s : règle NAT %s modifiée : %s", name, ident, fields)
        _notify("mikrotik.nat.change", "%s : règle NAT %s modifiée" % (name, ident), "Routeur %s (%s), règle %s : %s" % (name, router["host"], ident, json.dumps(fields, ensure_ascii=False)), {"router": name, "id": ident, "fields": fields})
        return jsonify({"status": "ok", "fields": fields}), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/mikrotik/routers/<name>/command", methods=["POST"])
def command(name):
    """Commande CLI en LECTURE SEULE (print / export / get / monitor-traffic),
    transport SSH seulement -- pour les relevés que la tuile ne structure pas
    (routes, baux DHCP, filtres, journal...). Tout verbe modifiant est refusé
    avant d'atteindre le routeur."""
    router, err = _router_or_404(name)
    if err:
        return err
    if router["transport"] != "ssh":
        return jsonify({"error": "commandes libres : transport ssh seulement (registre : \"transport\": \"ssh\")"}), 400
    cmd = " ".join(str((request.get_json(silent=True) or {}).get("command") or "").split())
    if not read_only_command(cmd):
        return jsonify({"error": "commande refusée : seuls print / export / get / monitor-traffic sont acceptés ici"}), 400
    client, error = client_for(router)
    if error:
        return jsonify({"error": error}), 500
    try:
        out = client.run(cmd)
        log.info("routeur %s : commande « %s »", name, cmd)
        return jsonify({"command": cmd, "output": out.replace("\r", "").rstrip("\n").split("\n")}), 200
    except RouterOSError as exc:
        return jsonify({"error": str(exc)}), 502


# ------------------------------------------------ registre depuis la tuile (#592)
@app.route("/mikrotik/credentials", methods=["GET"])
def credential_names():
    """Noms des accès du coffre (jamais de secret) pour le formulaire."""
    if not CREDENTIALS_TOKEN:
        return jsonify({"credentials": [], "error": "coffre non configuré"}), 200
    try:
        resp = requests.get(f"{CREDENTIALS_API_URL}/credentials/list", timeout=5)
        items = resp.json().get("credentials", []) if resp.status_code == 200 else []
    except (requests.RequestException, ValueError):
        items = []
    return jsonify({"credentials": [{"name": c.get("name"), "kind": c.get("kind"), "username": c.get("username")} for c in items if c.get("name")]}), 200


@app.route("/mikrotik/routers", methods=["POST"])
def router_save():
    entry, errors = registry_edit.validate_common(request.get_json(silent=True) or {}, ("rest", "ssh"), {"rest": 443, "ssh": 22})
    if errors:
        return jsonify({"error": "entrée refusée", "errors": errors}), 400
    items, _ = registry_edit.read_items(REGISTRY_LOCAL, REGISTRY_PATH, "routers")
    items = [i for i in items if not str(i.get("name", "")).startswith("exemple")]  # les exemples du dépôt ne migrent pas dans le registre réel
    items, what = registry_edit.upsert(items, entry)
    try:
        registry_edit.write_items(REGISTRY_LOCAL, "routers", items)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 500
    log.warning("registre : routeur %s %s (%s, %s)", entry["name"], "modifié" if what == "updated" else "ajouté", entry["host"], entry["transport"])
    return jsonify({"status": "ok", "action": what, "router": entry, "path": REGISTRY_LOCAL}), 200


@app.route("/mikrotik/routers/<name>", methods=["DELETE"])
def router_delete(name):
    items, _ = registry_edit.read_items(REGISTRY_LOCAL, REGISTRY_PATH, "routers")
    items, ok = registry_edit.remove(items, name)
    if not ok:
        return jsonify({"error": "routeur inconnu"}), 404
    try:
        registry_edit.write_items(REGISTRY_LOCAL, "routers", items)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 500
    log.warning("registre : routeur %s retiré", name)
    return jsonify({"status": "ok"}), 200


READ_COMMANDS = [
    ("Adresses IP", "/ip address print"), ("Routes actives", "/ip route print where active"), ("Baux DHCP", "/ip dhcp-server lease print"),
    ("Voisins", "/ip neighbor print"), ("Filtres pare-feu", "/ip firewall filter print"), ("Connexions NAT actives", "/ip firewall connection print where nat"),
    ("Journal (fin)", "/log print"), ("Export de la configuration", "/export"), ("Trafic ether1 (instantané)", "/interface monitor-traffic ether1 once"),
]


@app.route("/mikrotik/commands", methods=["GET"])
def commands_catalog():
    return jsonify({"commands": [{"label": l, "command": c} for l, c in READ_COMMANDS]}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
