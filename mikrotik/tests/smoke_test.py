"""Test de fumée du module mikrotik (livraison #485) : app Flask contre
un faux RouterOS REST en mémoire — registre, résumé, interfaces,
toggle, ping, reboot, et les gardes-fous (confirmations, 404, 400).

Lancé localement (venv avec flask/requests) :

    python mikrotik/tests/smoke_test.py
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

IFACES = [
    {".id": "*1", "name": "ether1", "type": "ether", "running": "true", "disabled": "false",
     "rx-byte": "123456789", "tx-byte": "98765432"},
    {".id": "*2", "name": "wlan1", "type": "wlan", "running": "false", "disabled": "true",
     "rx-byte": "0", "tx-byte": "0"},
]
CALLS = []


class FakeRouterOS(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        import base64
        header = self.headers.get("Authorization", "")
        return header == "Basic " + base64.b64encode(b"admin:secret").decode()

    def do_GET(self):
        if not self._auth_ok():
            return self._json(401, {"message": "Unauthorized"})
        path = self.path
        if path == "/rest/system/identity":
            return self._json(200, {"name": "rb-test"})
        if path == "/rest/system/resource":
            return self._json(200, {"version": "7.15.1", "uptime": "1d2h3m", "cpu-load": "12",
                                    "free-memory": "234000000", "free-hdd-space": "89000000",
                                    "architecture-name": "arm"})
        if path == "/rest/system/health":
            return self._json(200, {"temperature": "41", "voltage": "24.1"})
        if path == "/rest/interface":
            return self._json(200, IFACES)
        self._json(404, {"detail": "no such command"})

    def do_PATCH(self):
        if not self._auth_ok():
            return self._json(401, {"message": "Unauthorized"})
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path.startswith("/rest/interface/"):
            CALLS.append(("toggle", self.path, body))
            return self._json(200, {})
        self._json(404, {"detail": "no such command"})

    def do_POST(self):
        if not self._auth_ok():
            return self._json(401, {"message": "Unauthorized"})
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/rest/ping":
            CALLS.append(("ping", body))
            return self._json(200, [{"host": body["address"], "sent": body["count"], "received": body["count"]}])
        if self.path == "/rest/system/reboot":
            CALLS.append(("reboot", body))
            return self._json(200, {})
        self._json(404, {"detail": "no such command"})


REVEALS = []


class FakeCredentials(BaseHTTPRequestHandler):
    """Faux credentials-api : un seul accès « mikrotik » (admin/secret)."""
    def log_message(self, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("X-Credentials-Token") != "jeton-test":
            return self._json(403, {"error": "jeton interne invalide"})
        name = self.path.rsplit("/", 1)[-1]
        REVEALS.append((name, self.headers.get("X-Credentials-Consumer")))
        if name == "mikrotik":
            return self._json(200, {"name": name, "username": "admin", "password": "secret"})
        self._json(404, {"error": f"accès inconnu : {name} -- à créer dans la tuile Accès d'équipements"})


def main():
    fake = HTTPServer(("127.0.0.1", 0), FakeRouterOS)
    port = fake.server_address[1]
    threading.Thread(target=fake.serve_forever, daemon=True).start()

    registry = "/tmp/mikrotik-test-routers.json"
    with open(registry, "w", encoding="utf-8") as fh:
        json.dump({"routers": [
            {"name": "rb-test", "host": f"127.0.0.1", "port": port, "credential": "default"},
            {"name": "sans-creds", "host": "127.0.0.1", "port": port, "credential": "inconnu"},
        ]}, fh)

    # Le client impose https:// — pour le test, on détourne vers http
    # en patchant la construction de l'URL (le comportement testé est
    # l'app, pas TLS).
    # Identifiants : faux coffre des accès (#498) -- plus rien dans l'env.
    os.environ.pop("MIKROTIK_USER", None); os.environ.pop("MIKROTIK_PASSWORD", None)
    cred = HTTPServer(("127.0.0.1", 0), FakeCredentials)
    threading.Thread(target=cred.serve_forever, daemon=True).start()
    os.environ["CREDENTIALS_API_URL"] = f"http://127.0.0.1:{cred.server_address[1]}"
    os.environ["CREDENTIALS_INTERNAL_TOKEN"] = "jeton-test"
    os.environ["CREDENTIALS_CACHE_SECONDS"] = "60"
    os.environ["MIKROTIK_REGISTRY"] = registry

    import routeros_client
    orig_init = routeros_client.RouterOSClient.__init__
    def patched(self, host, port, user, password, tls_verify=False, timeout=10):
        orig_init(self, host, port, user, password, tls_verify, timeout)
        self.base = self.base.replace("https://", "http://")
    routeros_client.RouterOSClient.__init__ = patched

    import app as mk
    c = mk.app.test_client()

    assert c.get("/mikrotik/").status_code == 200
    assert c.get("/mikrotik/health").get_json()["status"] == "ok"
    print("✓ page + health")

    routers = c.get("/mikrotik/routers").get_json()["routers"]
    assert routers[0]["reachable"] and routers[0]["identity"] == "rb-test"
    assert not routers[1]["reachable"] and "absent du coffre" in routers[1]["error"], routers[1]
    assert REVEALS[0] == ("mikrotik", "mikrotik-api") and ("inconnu", "mikrotik-api") in REVEALS
    n = len(REVEALS)
    c.get("/mikrotik/routers")
    assert len([r for r in REVEALS[n:] if r[0] == "mikrotik"]) == 0, "cache : pas de nouvelle révélation dans la minute"
    print("✓ registre : identifiants lus dans le coffre (jamais .env), cache, accès manquant signalé proprement")

    summary = c.get("/mikrotik/routers/rb-test/summary").get_json()
    assert summary["resource"]["version"] == "7.15.1" and summary["health"]["temperature"] == "41"
    assert c.get("/mikrotik/routers/inconnu/summary").status_code == 404
    print("✓ summary (identité + ressources + santé), 404 sur inconnu")

    ifaces = c.get("/mikrotik/routers/rb-test/interfaces").get_json()["interfaces"]
    assert len(ifaces) == 2 and ifaces[0]["name"] == "ether1"
    print("✓ interfaces")

    # gardes-fous des commandes
    assert c.post("/mikrotik/routers/rb-test/interfaces/toggle", json={"enable": False}).status_code == 400
    assert c.post("/mikrotik/routers/rb-test/reboot", json={}).status_code == 400
    r = c.post("/mikrotik/routers/rb-test/interfaces/toggle", json={"id": "*2", "enable": True})
    assert r.status_code == 200
    assert CALLS[-1] == ("toggle", "/rest/interface/*2", {"disabled": "false"})
    r = c.post("/mikrotik/routers/rb-test/ping", json={"address": "192.168.88.1", "count": 99})
    body = r.get_json()
    assert r.status_code == 200 and CALLS[-1][1]["count"] == "20"  # borné
    r = c.post("/mikrotik/routers/rb-test/reboot", json={"confirm": "REBOOT"})
    assert r.status_code == 200 and CALLS[-1][0] == "reboot"
    print("✓ commandes : toggle/ping/reboot + gardes-fous (400 sans corps, ping borné à 20, reboot exige confirm)")

    os.remove(registry)
    print("\nSMOKE TEST MIKROTIK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
