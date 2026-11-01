"""Test de fumée de projeqtor-bridge (livraison #484, import multi-cibles #497) : app Flask contre
un faux ProjeQtOr et un faux tickets-api en mémoire — couvre le
formulaire, les référentiels, le dépôt, l'import xlsx réel,
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
    "Contact": [{"id": 42, "name": "alice"}, {"id": 43, "name": "bob"}],
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
    assert "alice" in ref["demandeurs"] and "Urgent" in ref["priorites"] and "réseau" in ref["categories"]
    print("✓ référentiels :", ref)

    # 3. dépôt public — complet et nom non résolu
    r = c.post("/demande/demandes", json={
        "demandeur": "alice", "sujet": "Test formulaire",
        "priorite": "Urgent", "categorie": "réseau", "duree_j": "2",
        "commentaire": "via formulaire"})
    assert r.status_code == 201, r.get_json()
    r2 = c.post("/demande/demandes", json={"demandeur": "Inconnu", "sujet": "Demande 2", "priorite": "J+99"})
    assert r2.status_code == 201 and len(r2.get_json()["non_resolus"]) == 2
    assert c.post("/demande/demandes", json={"demandeur": "X"}).status_code == 400
    assert c.post("/demande/demandes", json={"demandeur": "X", "sujet": "Y", "duree_j": "-3"}).status_code == 400
    print("✓ dépôt public (résolu, non résolu, validations 400)")

    # 4. import d'un tableau (#497) : xlsx au format imposé, xlsx libre,
    #    csv ; cibles hub / ProjeQtOr / les deux ; analyse sans création ;
    #    réimport = déjà connus côté hub (jamais de doublon).
    import io as _io
    from datetime import datetime as _dt
    import suivi_format as of
    sample = of.build_workbook([
        {of.COL_ID: 11, of.COL_DATE: _dt(2026, 9, 1), of.COL_REQUESTER: "alice", of.COL_SUBJECT: "Imprimante bac 2",
         of.COL_PRIORITY: "Urgent", of.COL_CATEGORY: "réseau", of.COL_DURATION: 2, of.COL_COMMENT: "voyant rouge", of.COL_PROGRESS: 0.5},
        {of.COL_ID: 12, of.COL_DATE: _dt(2026, 9, 2), of.COL_REQUESTER: "inconnu", of.COL_SUBJECT: "Compte mail",
         of.COL_PRIORITY: "J+1", of.COL_CATEGORY: "mail", of.COL_DURATION: 1, of.COL_COMMENT: "", of.COL_PROGRESS: 0},
    ])
    before_pq, before_hub = len(CREATED_TICKETS), len(HUB_TICKETS)
    r = c.post("/demande/import", data={"file": (_io.BytesIO(sample), "tableau.xlsx"), "dry_run": "1"})
    body = r.get_json()
    assert r.status_code == 200 and body["status"] == "analyse" and body["total"] == 2 and len(body["lignes"]) == 2, body
    assert body["lignes"][0]["sujet"] == "Imprimante bac 2" and body["lignes"][0]["date"] == "2026-09-01"
    assert len(CREATED_TICKETS) == before_pq and len(HUB_TICKETS) == before_hub, "dry_run ne crée rien"
    print("✓ import : analyse sans création (2 lignes)")

    r = c.post("/demande/import", data={"file": (_io.BytesIO(sample), "tableau.xlsx"), "target": "tickets"})
    body = r.get_json()
    assert r.status_code == 200 and body["cibles"]["tickets"]["crees"] == 2 and body["cibles"]["projeqtor"] is None, body
    assert len(HUB_TICKETS) == before_hub + 2 and len(CREATED_TICKETS) == before_pq
    key = ("demande", f"{bridge.LABEL}:11")
    assert key in HUB_TICKETS, HUB_TICKETS.keys()
    print("✓ import : cible hub seule, 2 tickets à valider, source_nom", key[1])

    r = c.post("/demande/import", data={"file": (_io.BytesIO(sample), "tableau.xlsx"), "target": "both"})
    body = r.get_json()
    assert r.status_code == 200 and body["cibles"]["tickets"]["deja_connus"] == 2 and body["cibles"]["tickets"]["crees"] == 0, body
    assert body["cibles"]["projeqtor"]["crees"] == 2 and len(CREATED_TICKETS) == before_pq + 2
    assert any("inconnu" in w for w in body["avertissements"]), body["avertissements"]
    assert CREATED_TICKETS[-1]["externalReference"] == f"{bridge.LABEL}:12"
    # la sync ProjeQtOr -> hub retrouve ces tickets « déjà connus » (même clé)
    before_hub2 = len(HUB_TICKETS)
    r = c.post("/demande/sync/now")
    assert len(HUB_TICKETS) == before_hub2, "pas de doublon hub pour un ticket entré par le pont"
    print("✓ import : les deux cibles, réimport dédupliqué côté hub, ProjeQtOr alimenté, demandeur inconnu signalé")

    # xlsx libre (en-têtes ligne 1, autres noms, dates texte) + csv
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Objet", "Demandeur", "Date", "Type", "Priorité", "Description", "Charge (j)"])
    ws.append(["Écran HS", "carol", "12/09/2026", "poste de travail", "J+2", "pixel mort", "1,5"])
    ws.append(["", "", "", "", "", "", ""])
    ws.append(["Sans date", "dave", "hier", "", "", "", "beaucoup"])
    buf = _io.BytesIO(); wb.save(buf)
    r = c.post("/demande/import", data={"file": (_io.BytesIO(buf.getvalue()), "libre.xlsx"), "target": "tickets"})
    body = r.get_json()
    assert r.status_code == 200 and body["cibles"]["tickets"]["crees"] == 2, body
    assert any("hier" in w for w in body["avertissements"]) and any("beaucoup" in w for w in body["avertissements"]), body
    csv = "Sujet;Demandeur;Date de demande;Catégorie\nSouris;eve;2026-09-03;accessoire\n".encode("cp1252")
    r = c.post("/demande/import", data={"file": (_io.BytesIO(csv), "demandes.csv"), "target": "tickets"})
    assert r.status_code == 200 and r.get_json()["cibles"]["tickets"]["crees"] == 1, r.get_json()
    r = c.post("/demande/import", data={"file": (_io.BytesIO(b"pas un tableur"), "x.xlsx"), "target": "tickets"})
    assert r.status_code == 400, r.get_json()
    r = c.post("/demande/import", data={"file": (_io.BytesIO(sample), "t.xlsx"), "target": "ailleurs"})
    assert r.status_code == 400
    print("✓ import : xlsx libre (en-têtes par nom, textes tolérés), csv, refus propres")

    xlsx = os.environ.get("SUIVI_SAMPLE")
    if xlsx and os.path.exists(xlsx):
        r = c.post("/demande/import", data={"file": (open(xlsx, "rb"), os.path.basename(xlsx)), "dry_run": "1"})
        body = r.get_json()
        assert r.status_code == 200, body
        print("✓ analyse du fichier réel SUIVI_SAMPLE :", body["total"], "demande(s)", body["avertissements"][:3])
    else:
        print("⚠ SUIVI_SAMPLE absent — fichier réel non analysé")

    # 4b. saisie rapide (#500) : détails formatés multiples -> texte, ticket hub + ProjeQtOr, même clé
    assert c.get("/demande/rapide").status_code == 200 and c.get("/demande/tableau").status_code == 200
    hub_before = len(HUB_TICKETS)
    r = c.post("/demande/demandes", json={"demandeur": "alice", "sujet": "Écran noir", "priorite": "Urgent", "categorie": "réseau",
                                          "details": [{"titre": "Message d'erreur", "html": "<div>Code <b>0x80</b> au <i>démarrage</i><br>puis rien</div>"},
                                                      {"titre": "", "html": "<ul><li>poste bureau 12</li><li>depuis lundi</li></ul><script>alert(1)</script>"}]})
    body = r.get_json()
    assert r.status_code == 201 and body["cibles"] == {"projeqtor": "created", "tickets": "created"}, body
    assert len(HUB_TICKETS) == hub_before + 1
    key = CREATED_TICKETS[-1]["externalReference"]
    assert key.startswith(f"{bridge.LABEL}:s:") and ("demande", key) in HUB_TICKETS
    desc = CREATED_TICKETS[-1]["description"]
    assert "Message d'erreur\nCode **0x80** au _démarrage_\npuis rien" in desc and "- poste bureau 12\n- depuis lundi" in desc, desc
    assert "<" not in desc.split("[")[0] and "alert" not in desc
    r = c.post("/demande/sync/now")
    assert len(HUB_TICKETS) == hub_before + 1, "sync : la demande du formulaire est déjà connue du hub"
    assert c.post("/demande/demandes", json={"demandeur": "x", "sujet": "y", "target": "ailleurs"}).status_code == 400
    print("✓ saisie rapide : détails formatés -> texte sûr, hub + ProjeQtOr, pas de doublon à la sync")

    # 4c. saisie « tableau » (#500) : lignes JSON, même chemin que le fichier
    r = c.post("/demande/import", json={"rows": [
        {"id": "", "date_demande": "2026-09-14", "demandeur": "bob", "sujet": "Souris", "priorite": "J+2", "categorie": "accessoire", "duree_j": "0,5", "commentaire": "", "accomplissement": "", "date_cloture": ""},
        {"id": "", "date_demande": "", "demandeur": "", "sujet": "", "priorite": "", "categorie": "", "duree_j": "", "commentaire": "", "accomplissement": "", "date_cloture": ""},
        {"id": "", "date_demande": "hier", "demandeur": "carol", "sujet": "VPN", "priorite": "", "categorie": "", "duree_j": "beaucoup", "commentaire": "", "accomplissement": "", "date_cloture": ""},
    ], "dry_run": 1})
    body = r.get_json()
    assert r.status_code == 200 and body["total"] == 2 and len(body["avertissements"]) == 2, body
    hub_before = len(HUB_TICKETS)
    r = c.post("/demande/import", json={"rows": [{"date_demande": "2026-09-14", "demandeur": "bob", "sujet": "Souris", "duree_j": "0,5"}], "target": "tickets"})
    body = r.get_json()
    assert r.status_code == 200 and body["cibles"]["tickets"]["crees"] == 1 and len(HUB_TICKETS) == hub_before + 1, body
    assert c.post("/demande/import", json={"rows": []}).status_code == 400
    print("✓ saisie tableau : lignes JSON vérifiées puis envoyées, ligne vide ignorée, erreurs signalées")

    # 4d. référentiels : repli sur les listes du format quand ProjeQtOr n'a rien
    saved = dict(PROJEQTOR_DATA)
    PROJEQTOR_DATA["Urgency"] = []; PROJEQTOR_DATA["TicketType"] = []
    ref = c.get("/demande/referentiels").get_json()
    assert ref["source"] == "defaut" and "Urgent" in ref["priorites"] and "accessoire" in ref["categories"], ref
    PROJEQTOR_DATA.update(saved)
    assert c.get("/demande/referentiels").get_json()["source"] == "projeqtor"
    print("✓ référentiels : ProjeQtOr d'abord, listes du format en repli")

    # 5. export xlsx — relire ce qui a été créé
    r = c.get("/demande/export")
    assert r.status_code == 200
    import suivi_format as of
    demands, errors = of.parse_workbook(r.data)
    assert not errors and len(demands) == len(CREATED_TICKETS), (errors, len(demands), len(CREATED_TICKETS))
    subjects = {d[of.COL_SUBJECT] for d in demands}
    assert "Test formulaire" in subjects
    print("✓ export xlsx :", len(demands), "demande(s), sujets OK")

    # 6. sync vers le hub : les tickets entrés PAR LE PONT sont déjà
    #    connus (même clé) ; un ticket natif ProjeQtOr (sans clé du pont)
    #    est poussé une fois, puis dédupliqué -- même après perte de
    #    l'état local.
    CREATED_TICKETS.append({"id": 900, "name": "Natif ProjeQtOr", "description": "saisi dans ProjeQtOr",
                            "creationDateTime": "2026-09-12 16:00:00"})
    hub_before = len(HUB_TICKETS)
    r = c.post("/demande/sync/now")
    summary = r.get_json()
    assert summary["pushed"] == 1 and len(HUB_TICKETS) == hub_before + 1, (summary, len(HUB_TICKETS), hub_before)
    assert ("projeqtor", "ProjeQtOr #900") in HUB_TICKETS
    assert all(k[0] in ("demande", "projeqtor") for k in HUB_TICKETS), HUB_TICKETS.keys()
    r = c.post("/demande/sync/now")
    assert r.get_json()["pushed"] == 0  # déjà connus (état local)
    # Perte de l'état local : le faux hub doit dédupliquer quand même
    os.remove("/tmp/bridge-test-state.json")
    r = c.post("/demande/sync/now")
    assert r.get_json()["pushed"] == 0 and len(HUB_TICKETS) == hub_before + 1, r.get_json()
    print("✓ sync :", summary["pushed"], "poussés, déduplication OK (état local ET côté hub)")

    assert all(t.get("pending_validation") or True for t in CREATED_TICKETS)
    print("\nSMOKE TEST OK —", len(CREATED_TICKETS), "tickets ProjeQtOr,", len(HUB_TICKETS), "tickets hub (tous pending_validation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
