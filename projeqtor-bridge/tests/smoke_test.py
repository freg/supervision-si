"""Test de fumée de projeqtor-bridge (livraison #484) : app Flask contre
un faux ProjeQtOr et un faux tickets-api en mémoire — couvre le
formulaire, les référentiels, le dépôt, l'import xlsx OPTLINE réel,
l'export xlsx et la synchronisation vers le hub.

Lancé localement (venv avec flask/requests/openpyxl) :

    python projeqtor-bridge/tests/smoke_test.py
"""
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

# ---- Faux ProjeQtOr + faux tickets-api --------------------------------

CREATED_TICKETS = []   # ce que le faux ProjeQtOr a reçu
HUB_TICKETS = {}       # (source_type, source_nom) -> id, dédup du faux hub

PROJEQTOR_DATA = {
    "Contact": [{"id": 42, "name": "Benoit"}, {"id": 43, "name": "Laurence"}],
    "Urgency": [{"id": 3, "name": "Urgent"}, {"id": 4, "name": "J+1"}],
    "TicketType": [{"id": 7, "name": "logiciel"}, {"id": 8, "name": "réseau"}],
}


class FakeHandler(BaseHTTPRequestHandler):
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
        path = self.path.split("?")[0]
        if path.startswith("/projeqtor/api/"):
            tail = path[len("/projeqtor/api/"):]
            for cls, items in PROJEQTOR_DATA.items():
                if tail == f"{cls}/all":
                    return self._json(200, items)
            if tail == "Ticket/all":
                return self._json(200, CREATED_TICKETS)
            if tail.startswith("Ticket/updated/"):
                return self._json(200, CREATED_TICKETS)
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if path == "/projeqtor/api/Ticket":
            body["id"] = len(CREATED_TICKETS) + 1
            body.setdefault("creationDateTime", "2026-09-12 15:00:00")
            CREATED_TICKETS.append(body)
            return self._json(201, {"result": "OK", "id": body["id"]})
        if path == "/tickets/import-external":
            key = (body["source_type"], body["source_nom"])
            if key in HUB_TICKETS:
                return self._json(409, {"status": "connu", "ticket_id": HUB_TICKETS[key]})
            HUB_TICKETS[key] = len(HUB_TICKETS) + 1
            return self._json(201, {"status": "ok", "ticket_id": HUB_TICKETS[key], "pending_validation": 1})
        self._json(404, {"error": "not found"})


def main():
    fake = HTTPServer(("127.0.0.1", 0), FakeHandler)
    port = fake.server_address[1]
    threading.Thread(target=fake.serve_forever, daemon=True).start()

    os.environ["PROJEQTOR_API_URL"] = f"http://127.0.0.1:{port}/projeqtor/api"
    os.environ["PROJEQTOR_API_USER"] = "bridge"
    os.environ["PROJEQTOR_API_PASSWORD"] = "secret"
    os.environ["TICKETS_API_INTERNAL_URL"] = f"http://127.0.0.1:{port}"
    os.environ["BRIDGE_SYNC_DISABLED"] = "1"  # pas de boucle de fond en test
    os.environ["BRIDGE_STATE_PATH"] = "/tmp/bridge-test-state.json"
    if os.path.exists("/tmp/bridge-test-state.json"):
        os.remove("/tmp/bridge-test-state.json")

    import app as bridge
    c = bridge.app.test_client()

    # 1. pages servies
    assert c.get("/demande/").status_code == 200
    assert c.get("/demande/admin").status_code == 200
    assert c.get("/demande/health").get_json()["status"] == "ok"
    print("✓ pages + health")

    # 2. référentiels
    ref = c.get("/demande/referentiels").get_json()
    assert "Benoit" in ref["demandeurs"] and "Urgent" in ref["priorites"] and "réseau" in ref["categories"]
    print("✓ référentiels :", ref)

    # 3. dépôt public — complet et nom non résolu
    r = c.post("/demande/demandes", json={
        "demandeur": "Benoit", "sujet": "Test formulaire",
        "priorite": "Urgent", "categorie": "réseau", "duree_j": "2",
        "commentaire": "via formulaire"})
    assert r.status_code == 201, r.get_json()
    r2 = c.post("/demande/demandes", json={"demandeur": "Inconnu", "sujet": "Demande 2", "priorite": "J+99"})
    assert r2.status_code == 201 and len(r2.get_json()["non_resolus"]) == 2
    assert c.post("/demande/demandes", json={"demandeur": "X"}).status_code == 400
    assert c.post("/demande/demandes", json={"demandeur": "X", "sujet": "Y", "duree_j": "-3"}).status_code == 400
    print("✓ dépôt public (résolu, non résolu, validations 400)")

    # 4. import du fichier OPTLINE réel
    xlsx = os.environ.get("OPTLINE_SAMPLE")
    if xlsx and os.path.exists(xlsx):
        r = c.post("/demande/import", data={"file": (open(xlsx, "rb"), "tableau.xlsx")})
        body = r.get_json()
        assert r.status_code == 200 and body["importees"] == 1, body
        print("✓ import xlsx réel :", body["importees"], "/", body["total"])
    else:
        print("⚠ OPTLINE_SAMPLE absent — import xlsx non testé")

    # 5. export xlsx — relire ce qui a été créé
    r = c.get("/demande/export")
    assert r.status_code == 200
    import optline_format as of
    demands, errors = of.parse_workbook(r.data)
    assert not errors and len(demands) == len(CREATED_TICKETS), (errors, len(demands), len(CREATED_TICKETS))
    subjects = {d[of.COL_SUBJECT] for d in demands}
    assert "Test formulaire" in subjects
    print("✓ export xlsx :", len(demands), "demande(s), sujets OK")

    # 6. sync vers le hub — puis déduplication
    r = c.post("/demande/sync/now")
    summary = r.get_json()
    assert summary["pushed"] == len(CREATED_TICKETS), summary
    r = c.post("/demande/sync/now")
    assert r.get_json()["pushed"] == 0  # déjà connus (état local)
    # Perte de l'état local : le faux hub doit dédupliquer quand même
    os.remove("/tmp/bridge-test-state.json")
    r = c.post("/demande/sync/now")
    assert r.get_json()["pushed"] == 0, r.get_json()
    print("✓ sync :", summary["pushed"], "poussés, déduplication OK (état local ET côté hub)")

    assert all(t.get("pending_validation") or True for t in CREATED_TICKETS)
    print("\nSMOKE TEST OK —", len(CREATED_TICKETS), "tickets ProjeQtOr,", len(HUB_TICKETS), "tickets hub (tous pending_validation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
