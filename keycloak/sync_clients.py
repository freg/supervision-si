#!/usr/bin/env python3
"""
Pousse dans le realm Keycloak VIVANT les URL de redirection et origines
(redirectUris / webOrigins) des clients OIDC du realm rendu par
keycloak/render.py -- sans purge du volume.

Pourquoi (livraison #611) : `--import-realm` n'importe le realm qu'au
premier démarrage ; après `KEYCLOAK_EXTRA_ORIGINS=https://hub.exemple.fr`
+ `python3 keycloak/render.py`, le fichier rendu est à jour mais Keycloak
répond toujours « paramètre invalide : redirect_uri » depuis le nom
public. La seule voie documentée jusqu'ici était la purge du volume
(`reset-keycloak`) -- qui perd sessions, réglages faits à la main, comptes
locaux (démo, compte de service du realm master). Ce script ne touche que
ces deux listes, client par client, via l'API Admin REST avec le compte
de service (KEYCLOAK_SERVICE_CLIENT_ID / _SECRET, realm master), comme
group_memberships.py.

Usage (sur l'hôte, depuis la racine du projet) :
  python3 keycloak/render.py
  python3 keycloak/sync_clients.py            # applique, affiche ce qui change
  python3 keycloak/sync_clients.py --dry-run  # montre seulement

Variables lues dans .env (l'environnement du process prime) : HOST_IP,
KEYCLOAK_PORT (accès direct http://HOST_IP:KEYCLOAK_PORT/auth, comme
group_memberships.py), KEYCLOAK_SERVICE_CLIENT_ID/_SECRET, KEYCLOAK_IMPORT_DIR.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from render import parse_env, resolve_import_dir  # noqa: E402

URI_KEYS = ("redirectUris", "webOrigins")


def plan_changes(rendered_clients, live_clients):
    """Compare les clients rendus aux clients vivants (liste de dicts
    Keycloak) ; renvoie [(clientId, live_id, {clé: liste fusionnée})] pour
    ceux dont redirectUris/webOrigins n'ont pas toutes les entrées rendues.
    Fusion = entrées vivantes conservées + entrées rendues manquantes
    ajoutées (jamais de retrait : une URL ajoutée à la main reste). Un
    client rendu absent du realm vivant est ignoré (signalé par l'appelant)."""
    live_by_id = {c.get("clientId"): c for c in live_clients if c.get("clientId")}
    plan = []
    for rc in rendered_clients:
        cid = rc.get("clientId")
        lc = live_by_id.get(cid)
        if not cid or lc is None:
            continue
        updates = {}
        for key in URI_KEYS:
            wanted = [u for u in (rc.get(key) or []) if isinstance(u, str)]
            current = [u for u in (lc.get(key) or []) if isinstance(u, str)]
            missing = [u for u in wanted if u not in current]
            if missing:
                updates[key] = current + missing
        if updates:
            plan.append((cid, lc.get("id"), updates))
    return plan


def missing_clients(rendered_clients, live_clients):
    live_ids = {c.get("clientId") for c in live_clients}
    return [c.get("clientId") for c in rendered_clients if c.get("clientId") and c.get("clientId") not in live_ids]


class Admin:
    def __init__(self, base, client_id, secret, timeout=15):
        self.base, self.client_id, self.secret, self.timeout = base.rstrip("/"), client_id, secret, timeout
        self.token = None

    def login(self):
        data = urllib.parse.urlencode({"client_id": self.client_id, "client_secret": self.secret,
                                       "grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(f"{self.base}/realms/master/protocol/openid-connect/token", data=data)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            self.token = json.load(resp)["access_token"]

    def _req(self, method, path, body=None):
        req = urllib.request.Request(f"{self.base}{path}", method=method,
                                     headers={"Authorization": f"Bearer {self.token}"})
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, data=data, timeout=self.timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None

    def clients(self, realm):
        return self._req("GET", f"/admin/realms/{realm}/clients?max=500")

    def update_client(self, realm, live_id, updates):
        # PUT partiel accepté par Keycloak : seuls les champs présents changent
        self._req("PUT", f"/admin/realms/{realm}/clients/{live_id}", {"id": live_id, **updates})


def main(argv):
    dry = "--dry-run" in argv
    env = parse_env(os.path.join(ROOT, ".env"))
    get = lambda k, d="": os.environ.get(k, env.get(k, d)) or d
    path = os.path.join(resolve_import_dir(env), "supervision-si-realm.json")
    if not os.path.exists(path):
        print(f"❌ realm rendu absent : {path} -- lancer d'abord python3 keycloak/render.py", file=sys.stderr)
        return 2
    with open(path, encoding="utf-8") as fh:
        realm = json.load(fh)
    realm_name = realm.get("realm", "supervision-si")
    base = get("KEYCLOAK_ADMIN_URL") or f"http://{get('HOST_IP', 'localhost')}:{get('KEYCLOAK_PORT', '6180')}/auth"
    admin = Admin(base, get("KEYCLOAK_SERVICE_CLIENT_ID", "supervision-si-service"),
                  get("KEYCLOAK_SERVICE_CLIENT_SECRET", "change-me"))
    try:
        admin.login()
        live = admin.clients(realm_name)
    except urllib.error.HTTPError as exc:
        print(f"❌ Keycloak {base} : HTTP {exc.code} ({'compte de service refusé -- ./gateway/scripts/run.sh service-account' if exc.code == 401 else exc.reason})", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"❌ Keycloak injoignable sur {base} : {exc}", file=sys.stderr)
        return 1
    rendered = realm.get("clients", [])
    absent = missing_clients(rendered, live)
    if absent:
        print(f"⚠️  clients rendus absents du realm vivant (ignorés, réimport nécessaire pour eux) : {', '.join(absent)}")
    plan = plan_changes(rendered, live)
    if not plan:
        print(f"✅ realm « {realm_name} » : redirectUris / webOrigins déjà à jour ({len(rendered)} clients).")
        return 0
    for cid, live_id, updates in plan:
        for key, merged in updates.items():
            print(f"{'[à faire] ' if dry else ''}{cid}.{key} -> {len(merged)} entrées : {', '.join(merged)}")
        if not dry:
            admin.update_client(realm_name, live_id, updates)
    print("(simulation, rien d'appliqué -- relancer sans --dry-run)" if dry else f"✅ {len(plan)} client(s) mis à jour dans Keycloak.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
