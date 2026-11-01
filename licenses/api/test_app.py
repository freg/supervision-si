# -*- coding: utf-8 -*-
"""Tests de licenses-api (#595) : garde Keycloak, catalogue, contrats,
attributions (dépassement notifié), installations et écarts (inventaires
simulés), grille, import xlsx/csv (analyse puis import), comptes vendeurs
(synchronisation Graph simulée), actions installer / désinstaller via le
central des agents (simulé)."""
import csv
import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(ROOT, "si-proxy", "admin"))
os.environ["LICENSES_DB"] = os.path.join(tempfile.mkdtemp(prefix="licenses-"), "l.sqlite")
os.environ["CREDENTIALS_INTERNAL_TOKEN"] = "coffre-test"
os.environ["LICENSES_DIRECTORY_WORKER"] = "0"

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jwt.algorithms import RSAAlgorithm  # noqa: E402

import app as appmod  # noqa: E402
import auth  # noqa: E402

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
INV = [{"agent_id": "a1", "hostname": "PC-01", "site": "site-alpha", "os": "windows", "users": ["alice"], "count": 3, "installed": [
            {"name": "Microsoft 365 Apps for business - fr-fr", "publisher": "Microsoft Corporation", "version": "16"},
            {"name": "DraftSight 2024", "publisher": "Dassault Systèmes"}, {"name": "Zoom", "publisher": "Zoom Video Communications"}]},
       {"agent_id": "a2", "hostname": "PC-02", "site": "site-beta", "os": "linux", "users": ["bob"], "count": 1, "installed": [{"name": "vim", "publisher": "Debian", "source": "dpkg"}]}]


def jwks():
    j = json.loads(RSAAlgorithm.to_jwk(KEY.public_key()))
    j.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    return {"keys": [j]}


def token(username="francois", groups=("administrateurs",)):
    return jwt.encode({"preferred_username": username, "name": username, "exp": int(time.time()) + 300, "iat": int(time.time()), "typ": "Bearer", "groups": list(groups)}, KEY, algorithm="RS256", headers={"kid": "k1"})


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._b = status, body

    def json(self):
        return self._b


class Base(unittest.TestCase):
    def setUp(self):
        appmod.verifier = auth.KeycloakVerifier("u", [], fetch=lambda _u: jwks(), allowed_groups=["administrateurs"], what="les licences")
        c = appmod.sqlite3.connect(appmod.DB_PATH)
        for t in ("software", "contracts", "assignments", "vendor_accounts", "actions", "events", "users", "settings"):
            c.execute("DELETE FROM " + t)
        c.execute("DELETE FROM sqlite_sequence")
        c.commit()
        c.close()
        appmod.app.fetch_inventories = lambda site=None: [i for i in INV if not site or i["site"] == site]
        self.notified = []
        appmod._notify = lambda action, subject, body="", *a, **k: self.notified.append((action, subject))
        self.c = appmod.app.test_client()
        self.adm = {"Authorization": "Bearer " + token()}

    def software(self, name, **kw):
        r = self.c.post("/software", headers=self.adm, json=dict({"name": name}, **kw))
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()["id"]

    def contract(self, sid, **kw):
        r = self.c.post("/contracts", headers=self.adm, json=dict({"software_id": sid, "site": "site-alpha", "label": "L", "kind": "per-user", "quantity": 1}, **kw))
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()["id"]


class Guard(Base):
    def test_reads_free_writes_guarded(self):
        self.assertEqual(self.c.get("/software").status_code, 200)
        self.assertEqual(self.c.get("/health").status_code, 200)
        self.assertEqual(self.c.post("/software", json={"name": "x"}).status_code, 401)
        self.assertEqual(self.c.post("/software", headers={"Authorization": "Bearer " + token("bob", [])}, json={"name": "x"}).status_code, 403)
        self.assertEqual(self.c.post("/software", headers=self.adm, json={"name": "x"}).status_code, 200)


class Catalog(Base):
    def test_software_contracts_assignments(self):
        sid = self.software("Office 365", vendor="Microsoft", patterns=["Microsoft 365 Apps", " "])
        self.assertEqual(self.c.post("/software", headers=self.adm, json={"name": "office 365"}).status_code, 200)  # casse différente = autre nom (UNIQUE strict)
        self.assertEqual(self.c.post("/software", headers=self.adm, json={"name": "Office 365"}).status_code, 409)
        self.assertEqual(self.c.get("/software").get_json()["software"][0]["patterns"], ["Microsoft 365 Apps"])
        self.assertEqual(self.c.post("/contracts", headers=self.adm, json={"software_id": sid, "kind": "bizarre"}).status_code, 400)
        cid = self.contract(sid, quantity=1, end="2099-01-01")
        self.assertEqual(self.c.delete("/software/%d" % sid, headers=self.adm).status_code, 400)  # contrat référent
        r = self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "user", "subject": "alice"})
        self.assertEqual((r.status_code, r.get_json()["over"]), (200, False))
        self.assertEqual(self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "user", "subject": "alice"}).status_code, 409)
        r = self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "host", "subject": "PC-02"})
        self.assertEqual((r.get_json()["count"], r.get_json()["over"]), (2, True))
        self.assertEqual([n[0] for n in self.notified], ["licenses.contract", "licenses.assignment", "licenses.gap"])
        cts = self.c.get("/contracts").get_json()["contracts"]
        self.assertEqual((cts[0]["assigned"], cts[0]["days_left"] > 1000), (2, True))
        self.assertEqual(self.c.get("/contracts?site=site-beta").get_json()["contracts"], [])
        self.assertEqual(self.c.post("/assignments", headers=self.adm, json={"contract_id": 999, "subject": "x"}).status_code, 404)
        self.assertEqual(self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "team", "subject": "x"}).status_code, 400)
        aid = self.c.get("/assignments").get_json()["assignments"][0]["id"]
        self.assertEqual(self.c.delete("/assignments/%d" % aid, headers=self.adm).status_code, 200)
        self.assertEqual(self.c.delete("/contracts/%d" % cid, headers=self.adm).status_code, 200)
        self.assertEqual(self.c.get("/assignments").get_json()["assignments"], [])  # attributions supprimées avec le contrat
        self.assertEqual(self.c.delete("/software/%d" % sid, headers=self.adm).status_code, 200)
        self.assertTrue(any(e["event"] == "assignment" for e in self.c.get("/events").get_json()["events"]))


class Installations(Base):
    def test_installations_gaps_grid_sites(self):
        sid = self.software("Office 365", vendor="Microsoft", patterns=["Microsoft 365 Apps"])
        self.software("DraftSight", vendor="Dassault Systèmes")
        r = self.c.get("/installations").get_json()
        self.assertEqual([h["hostname"] for h in r["hosts"]], ["PC-01", "PC-02"])
        self.assertEqual(sorted(r["found"].keys()), ["1", "2"])
        self.assertEqual([u["name"] for u in r["unknown"]], ["Zoom"])
        self.assertEqual(r["sites"], ["site-alpha", "site-beta"])
        self.assertEqual([h["hostname"] for h in self.c.get("/installations?site=site-beta").get_json()["hosts"]], ["PC-02"])
        d = self.c.get("/installations/a1?q=draft").get_json()
        self.assertEqual([x["name"] for x in d["installed"]], ["DraftSight 2024"])
        self.assertEqual(self.c.get("/installations/nope").status_code, 404)
        g = self.c.get("/gaps").get_json()
        self.assertIn("installed-no-contract", {x["kind"] for x in g["gaps"]})
        self.assertEqual(sum(g["counts"].values()), len(g["gaps"]))
        cid = self.contract(sid, quantity=5, end="2000-01-01")
        self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "host", "subject": "PC-01"})
        kinds = {x["kind"] for x in self.c.get("/gaps").get_json()["gaps"]}
        self.assertIn("expired", kinds)
        grid = self.c.get("/grid").get_json()
        self.assertEqual([c["id"] for c in grid["columns"]], [1])
        row = [r for r in grid["rows"] if r["subject"] == "PC-01"][0]
        self.assertEqual((row["kind"], row["cells"][0]["assigned"], row["cells"][0]["installed"]), ("host", True, True))
        self.assertEqual(self.c.get("/sites").get_json()["sites"], ["site-alpha", "site-beta"])


def _csv_file(rows):
    buf = io.StringIO()
    csv.writer(buf, delimiter=";").writerows(rows)
    return (io.BytesIO(buf.getvalue().encode("utf-8")), "inv.csv")


class Import(Base):
    _csv = staticmethod(_csv_file)

    def test_matrix_dry_run_then_import(self):
        rows = [["Logiciel", "Éditeur", "Licence", "Date Fin", "alice", "bob", "carol"], ["DraftSight", "Dassault", "abonnement", "31/12/2027", "x", "x", ""], ["eDraw", "Wondershare", "perpétuelle", "", "", "", "x"]]
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": "site-alpha", "dry_run": "1"}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_json())
        j = r.get_json()
        self.assertEqual((j["format"], j["dry_run"], [p["software"] for p in j["plan"]]), ("matrix", True, ["DraftSight", "eDraw"]))
        self.assertEqual((j["people"], j["unknown_people"]), (3, ["alice", "bob", "carol"]))
        self.assertEqual(self.c.get("/software").get_json()["software"], [])
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": "site-alpha"}, content_type="multipart/form-data")
        self.assertEqual(r.get_json()["created"], {"software": 2, "contracts": 2, "assignments": 3, "users": 3})
        cts = self.c.get("/contracts").get_json()["contracts"]
        ds = [c for c in cts if c["site"] == "site-alpha" and c["kind"] == "subscription"][0]
        self.assertEqual((ds["quantity"], ds["end"], ds["assigned"]), (2, "2027-12-31", 2))
        # ré-import : rien de nouveau (idempotent)
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": "site-alpha"}, content_type="multipart/form-data")
        self.assertEqual(r.get_json()["created"], {"software": 0, "contracts": 0, "assignments": 0, "users": 0})
        self.assertEqual([(u["login"], u["site"], u["source"]) for u in self.c.get("/users").get_json()["users"]], [("alice", "site-alpha", "import"), ("bob", "site-alpha", "import"), ("carol", "site-alpha", "import")])
        self.assertEqual(self.c.post("/import", headers=self.adm, data={"site": "s"}, content_type="multipart/form-data").status_code, 400)

    def test_contracts_format(self):  # #602
        rows = [["Logiciel", "Éditeur", "Site", "Libellé", "Type", "Quantité", "Début", "Fin", "Coût / an", "Compte vendeur", "SKU", "Référence", "Notes", "Personnes"],
                ["Microsoft 365 Business Standard", "Microsoft", "site-alpha", "annuel 2025-2026", "abonnement", "7", "15/11/2025", "14/11/2026", "982,80", "m365", "O365_BUSINESS_PREMIUM", "G124702568", "carte", ""],
                ["Microsoft 365 Apps for business", "Microsoft", "site-alpha", "mensuel", "abonnement", "14", "09/02/2026", "16/05/2026", "", "", "", "", "résilié", "alice; bob"]]
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": "", "dry_run": "1"}, content_type="multipart/form-data")
        self.assertEqual((r.status_code, r.get_json()["format"]), (200, "contracts"), r.get_json())
        self.assertEqual(r.get_json()["plan"][0]["quantity"], 7)
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": ""}, content_type="multipart/form-data")
        self.assertEqual(r.get_json()["created"], {"software": 2, "contracts": 2, "assignments": 2, "users": 2})
        cts = {c["label"]: c for c in self.c.get("/contracts").get_json()["contracts"]}
        bs = cts["annuel 2025-2026"]
        self.assertEqual((bs["quantity"], bs["start"], bs["end"], bs["cost"], bs["sku"], bs["reference"], bs["site"], bs["kind"]), (7, "2025-11-15", "2026-11-14", 982.8, "O365_BUSINESS_PREMIUM", "G124702568", "site-alpha", "subscription"))
        self.assertEqual(cts["mensuel"]["assigned"], 2)
        # ré-import avec une quantité changée : mise à jour, pas de doublon
        rows[1][5] = "8"
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": ""}, content_type="multipart/form-data")
        self.assertEqual((r.get_json()["created"]["contracts"], r.get_json()["created"]["updated"]), (0, 2))
        self.assertEqual(len(self.c.get("/contracts").get_json()["contracts"]), 2)
        self.assertEqual({c["label"]: c for c in self.c.get("/contracts").get_json()["contracts"]}["annuel 2025-2026"]["quantity"], 8)

    def test_m365_export(self):
        rows = [["Nom complet", "Nom d'utilisateur", "Licences"], ["Alice A", "alice@exemple.test", "Microsoft 365 Business Standard+Exchange Online (Plan 1)"], ["Bob B", "bob@exemple.test", "Microsoft 365 Business Standard"]]
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": "site-alpha"}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_json())
        j = r.get_json()
        self.assertEqual(j["format"], "m365")
        names = {c["software"]: c for c in self.c.get("/contracts").get_json()["contracts"]}
        self.assertEqual(names["Microsoft 365 Business Standard"]["assigned"], 2)
        self.assertEqual(names["Exchange Online (Plan 1)"]["assigned"], 1)


class Users(Base):
    _csv = staticmethod(_csv_file)

    def test_directory_sync_links_imported_people(self):
        # annuaire connu d'abord : l'import rattache « Alice A » au compte LDAP
        appmod.app.fetch_directory = lambda: [{"username": "alice.a", "email": "alice.a@exemple.test", "first_name": "Alice", "last_name": "A", "enabled": True}, {"username": "dan.d", "email": "", "first_name": "Dan", "last_name": "D", "enabled": False}]
        r = self.c.post("/users/sync", headers=self.adm)
        self.assertEqual((r.status_code, r.get_json()["added"]), (200, 2))
        rows = [["Logiciel", "Éditeur", "Licence", "Date Fin", "Alice A", "M. DUPONT"], ["DraftSight", "Dassault", "", "", "x", "x"]]
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": "site-alpha", "dry_run": "1"}, content_type="multipart/form-data")
        self.assertEqual((r.get_json()["people"], r.get_json()["unknown_people"]), (2, ["M. DUPONT"]))
        r = self.c.post("/import", headers=self.adm, data={"file": self._csv(rows), "site": "site-alpha"}, content_type="multipart/form-data")
        self.assertEqual(r.get_json()["created"]["users"], 1)
        users = {u["login"]: u for u in self.c.get("/users").get_json()["users"]}
        self.assertEqual((users["alice.a"]["directory"], users["alice.a"]["site"], users["alice.a"]["assigned"]), (1, "site-alpha", 1))
        self.assertEqual((users["dupont"]["directory"], users["dupont"]["source"], users["dupont"]["name"]), (0, "import", "M. DUPONT"))
        # l'annuaire gagne un compte c.dupont : la ligne « info » est rattachée, l'attribution suit
        appmod.app.fetch_directory = lambda: [{"username": "c.dupont", "email": "", "first_name": "Carol", "last_name": "Dupont", "enabled": True}]
        r = self.c.post("/users/sync", headers=self.adm).get_json()
        self.assertEqual((r["added"], r["linked"]), (1, 1))
        users = {u["login"]: u for u in self.c.get("/users").get_json()["users"]}
        self.assertNotIn("dupont", users)
        self.assertEqual((users["c.dupont"]["site"], users["c.dupont"]["assigned"]), ("site-alpha", 1))
        self.assertEqual([a["subject"] for a in self.c.get("/assignments").get_json()["assignments"]], ["alice.a", "c.dupont"])
        # manuel, filtre par site, suppression protégée, grille = tous les utilisateurs du site
        self.assertEqual(self.c.post("/users", headers=self.adm, json={"login": "Eve.E", "name": "Eve E", "site": "site-beta"}).status_code, 200)
        self.assertEqual([u["login"] for u in self.c.get("/users?site=site-beta").get_json()["users"]], ["dan.d", "eve.e"])
        self.assertEqual(self.c.delete("/users/alice.a", headers=self.adm).status_code, 400)
        self.assertEqual(self.c.delete("/users/eve.e", headers=self.adm).status_code, 200)
        subjects = [(r["kind"], r["subject"]) for r in self.c.get("/grid?site=site-alpha").get_json()["rows"]]
        self.assertIn(("user", "c.dupont"), subjects)
        self.assertNotIn(("user", "dan.d"), subjects)  # sans site -> pas dans la grille d'un site
        appmod.app.fetch_directory = lambda: (_ for _ in ()).throw(RuntimeError("x"))
        self.assertEqual(self.c.post("/users/sync", headers=self.adm).status_code, 502)

    def test_cross_check_former_missing(self):  # #598
        sid = self.software("Office 365")
        cid = self.contract(sid, quantity=5)
        appmod.app.fetch_directory = lambda: [{"username": "alice.a", "first_name": "Alice", "last_name": "A", "enabled": True, "groups": ["administrateurs"]},
                                              {"username": "bob.b", "first_name": "Bob", "last_name": "B", "enabled": True, "groups": ["Anciens"]},
                                              {"username": "carl.c", "enabled": False, "groups": []}, {"username": "dan.d", "enabled": True, "groups": []}]
        self.c.post("/users/sync", headers=self.adm)
        for who in ("alice.a", "bob.b", "carl.c", "dan.d"):
            self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "user", "subject": who})
        self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "user", "subject": "eve"})  # hors annuaire
        # dan disparaît de l'annuaire
        appmod.app.fetch_directory = lambda: [{"username": "alice.a", "enabled": True, "groups": ["administrateurs"]}, {"username": "bob.b", "enabled": True, "groups": ["Anciens"]}, {"username": "carl.c", "enabled": False, "groups": []}]
        r = self.c.post("/users/sync", headers=self.adm).get_json()
        self.assertEqual((r["missing"], r["former"]), (1, 1))
        users = {u["login"]: u for u in self.c.get("/users").get_json()["users"]}
        self.assertEqual((users["bob.b"]["alert"], users["bob.b"]["groups"]), ("former", ["Anciens"]))
        self.assertEqual((users["dan.d"]["alert"], users["carl.c"]["alert"], users["alice.a"]["alert"]), ("missing", "disabled", None))
        gaps = {(x["kind"], x["user"]): x["severity"] for x in self.c.get("/gaps").get_json()["gaps"] if x["kind"].startswith("user-")}
        self.assertEqual(gaps, {("user-former", "bob.b"): "critical", ("user-missing", "dan.d"): "warning", ("user-disabled", "carl.c"): "warning", ("user-unknown", "eve"): "info"})
        # dan revient : plus d'écart
        appmod.app.fetch_directory = lambda: [{"username": "dan.d", "enabled": True, "groups": []}]
        self.c.post("/users/sync", headers=self.adm)
        self.assertIsNone({u["login"]: u for u in self.c.get("/users").get_json()["users"]}["dan.d"]["alert"])
        # portail vendeur sur le compte et sur le contrat lié
        self.c.post("/vendors", headers=self.adm, json={"name": "m365", "kind": "microsoft-graph", "config": {"tenant": "t", "client_id": "c"}, "credential": "x"})
        self.assertEqual(self.c.get("/vendors").get_json()["vendors"][0]["portal"], "https://admin.microsoft.com/#/licenses")
        self.c.put("/contracts/%d" % cid, headers=self.adm, json={"software_id": sid, "site": "site-alpha", "kind": "per-user", "quantity": 5, "vendor_account": "m365"})
        self.assertEqual(self.c.get("/contracts").get_json()["contracts"][0]["portal"], "https://admin.microsoft.com/#/licenses")


class OwnCloud(Base):
    def test_settings_sync_fiche(self):
        import owncloud as oc
        self.assertEqual(self.c.post("/owncloud/sync", headers=self.adm).status_code, 502)  # non configuré
        r = self.c.put("/owncloud", headers=self.adm, json={"url": "https://cloud.exemple", "folder": "Secrets/Fiches", "credential": "exemple-owncloud", "verify": False, "interval": 3600})
        self.assertEqual((r.status_code, r.get_json()["settings"]["former_subfolder"]), (200, "anciens utilisateurs"))
        appmod.app.reveal = lambda name: ("svc", "pw", None)
        fiches = [{"path": "Secrets/Fiches/alice a.txt", "name": "alice a", "former": False, "modified": "m", "size": 10, "fiche": {"name": "alice a", "mails": ["alice.a@exemple.test"], "fields": [], "licenses": [{"product": "office 365", "key_masked": "••••LMNO"}], "software": ["office 365"]}},
                  {"path": "Secrets/Fiches/anciens utilisateurs/bob b.txt", "name": "bob b", "former": True, "modified": "m", "size": 5, "fiche": {"name": "bob b", "mails": [], "fields": [], "licenses": [], "software": []}}]
        with mock.patch.object(oc, "scan", lambda client, folder, sub: fiches), mock.patch.object(oc.OwnCloud, "__init__", lambda self, *a, **k: None):
            appmod.app.fetch_directory = lambda: [{"username": "alice.a", "email": "alice.a@exemple.test", "enabled": True, "groups": []}]
            self.c.post("/users/sync", headers=self.adm)
            r = self.c.post("/owncloud/sync", headers=self.adm)
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual((r.get_json()["fiches"], r.get_json()["former"], r.get_json()["created"], r.get_json()["linked"]), (2, 1, 1, 1))
        users = {u["login"]: u for u in self.c.get("/users").get_json()["users"]}
        self.assertEqual((users["alice.a"]["fiche"]["licenses"][0]["product"], users["alice.a"]["alert"], users["alice.a"]["directory"]), ("office 365", None, 1))
        self.assertEqual((users["bob.b"]["source"], users["bob.b"]["alert"], users["bob.b"]["alert_label"]), ("owncloud", "former", "ancien (fiche ownCloud)"))
        sid = self.software("Office 365")
        cid = self.contract(sid, quantity=5)
        self.c.post("/assignments", headers=self.adm, json={"contract_id": cid, "subject_kind": "user", "subject": "bob.b"})
        kinds = {(x["kind"], x["user"]): x["severity"] for x in self.c.get("/gaps").get_json()["gaps"] if x.get("user")}
        self.assertEqual(kinds[("user-former", "bob.b")], "critical")
        st = self.c.get("/owncloud").get_json()
        self.assertEqual((st["fiches"], st["fiches_former"], st["state"]["fiches"]), (2, 1, 2))
        # lecture à la demande : journalisée, jamais mémorisée
        with mock.patch.object(oc.OwnCloud, "__init__", lambda self, *a, **k: None), mock.patch.object(oc.OwnCloud, "read", lambda self, path: "Licence : ABCDE-12345"):
            r = self.c.post("/users/alice.a/fiche", headers=self.adm)
            self.assertEqual((r.status_code, r.get_json()["text"]), (200, "Licence : ABCDE-12345"))
            self.assertEqual(self.c.post("/users/alice.a/fiche").status_code, 401)
            self.assertEqual(self.c.post("/users/nope/fiche", headers=self.adm).status_code, 404)
        self.assertTrue(any(e["event"] == "fiche-read" for e in self.c.get("/events").get_json()["events"]))
        self.assertNotIn("ABCDE", json.dumps(self.c.get("/users").get_json()))


class Vendors(Base):
    def test_vendor_sync(self):
        self.assertEqual(self.c.post("/vendors", headers=self.adm, json={"name": "m365-alpha", "kind": "inconnu"}).status_code, 400)
        r = self.c.post("/vendors", headers=self.adm, json={"name": "m365-alpha", "kind": "microsoft-graph", "site": "site-alpha", "config": {"tenant": "t", "client_id": "c"}, "credential": "exemple-graph"})
        self.assertEqual(r.status_code, 200, r.get_json())
        v = self.c.get("/vendors").get_json()["vendors"][0]
        self.assertEqual((v["name"], v["credential"], v["config"]["tenant"]), ("m365-alpha", "exemple-graph", "t"))
        # coffre absent -> 502, erreur mémorisée
        appmod.app.reveal = lambda name: (None, None, "accès « %s » : absent du coffre" % name)
        r = self.c.post("/vendors/m365-alpha/sync", headers=self.adm)
        self.assertEqual(r.status_code, 502)
        self.assertIn("absent du coffre", self.c.get("/vendors").get_json()["vendors"][0]["last_error"])
        appmod.app.reveal = lambda name: ("app", "secret", None)
        snap = [{"sku": "SKU1", "label": "Microsoft 365 Business Standard", "quantity": 10, "consumed": 2, "users": ["alice@exemple.test", "bob@exemple.test"]}]
        with mock.patch.object(appmod.vendors, "sync_microsoft_graph", lambda cfg, secret, http=None: snap):
            r = self.c.post("/vendors/m365-alpha/sync", headers=self.adm)
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual((r.get_json()["created_contracts"], r.get_json()["created_software"]), (1, 1))
            snap[0]["quantity"], snap[0]["users"] = 12, ["alice@exemple.test"]
            r = self.c.post("/vendors/m365-alpha/sync", headers=self.adm)
            self.assertEqual((r.get_json()["updated"], r.get_json()["created_contracts"]), (1, 0))
        ct = self.c.get("/contracts").get_json()["contracts"][0]
        self.assertEqual((ct["quantity"], ct["assigned"], ct["sku"], ct["vendor_account"]), (12, 1, "SKU1", "m365-alpha"))
        # #602 : compte administrateur -- connexion par code puis synchronisation avec le jeton mémorisé (jamais renvoyé)
        self.assertEqual(self.c.post("/vendors", headers=self.adm, json={"name": "m365-admin", "kind": "microsoft-account", "site": "site-alpha"}).status_code, 200)
        self.assertEqual(self.c.post("/vendors/m365-alpha/connect", headers=self.adm).status_code, 404)
        self.assertEqual(self.c.post("/vendors/m365-admin/sync", headers=self.adm).status_code, 502)  # non connecté, sans accès
        with mock.patch.object(appmod.vendors, "device_code_start", lambda tenant, **k: {"device_code": "D", "user_code": "ABCD-EFGH", "verification_uri": "https://microsoft.com/devicelogin", "expires_in": 900, "interval": 5}):
            r = self.c.post("/vendors/m365-admin/connect", headers=self.adm)
            self.assertEqual((r.status_code, r.get_json()["user_code"]), (200, "ABCD-EFGH"))
        with mock.patch.object(appmod.vendors, "device_code_poll", lambda tenant, code, **k: ("pending", None)):
            self.assertEqual(self.c.post("/vendors/m365-admin/connect/status", headers=self.adm).get_json()["status"], "pending")
        with mock.patch.object(appmod.vendors, "device_code_poll", lambda tenant, code, **k: ("ok", {"access_token": "A", "refresh_token": "R"})):
            self.assertEqual(self.c.post("/vendors/m365-admin/connect/status", headers=self.adm).get_json()["status"], "ok")
        vs = {v["name"]: v for v in self.c.get("/vendors").get_json()["vendors"]}
        self.assertTrue(vs["m365-admin"]["connected"])
        self.assertNotIn("R", json.dumps(vs))
        with mock.patch.object(appmod.vendors, "refresh_token", lambda tenant, r, **k: {"access_token": "A2", "refresh_token": "R2"}), mock.patch.object(appmod.vendors, "sync_with_token", lambda token, http=None: [{"sku": "SKU9", "label": "Power BI Pro", "quantity": 1, "consumed": 1, "users": ["alice@exemple.test"]}]):
            r = self.c.post("/vendors/m365-admin/sync", headers=self.adm)
            self.assertEqual((r.status_code, r.get_json()["created_contracts"]), (200, 1), r.get_json())
        self.assertEqual(self.c.post("/vendors/m365-admin/disconnect", headers=self.adm).status_code, 200)
        self.assertFalse({v["name"]: v for v in self.c.get("/vendors").get_json()["vendors"]}["m365-admin"]["connected"])
        # e-mail + mot de passe par le coffre (ROPC) : mémorise le jeton de rafraîchissement
        self.c.post("/vendors", headers=self.adm, json={"name": "m365-admin", "kind": "microsoft-account", "site": "site-alpha", "credential": "exemple-admin-m365"})
        appmod.app.reveal = lambda name: ("admin@exemple.test", "pw", None)
        with mock.patch.object(appmod.vendors, "ropc_token", lambda tenant, u, p, **k: {"access_token": "A", "refresh_token": "R"}), mock.patch.object(appmod.vendors, "sync_with_token", lambda token, http=None: []):
            self.assertEqual(self.c.post("/vendors/m365-admin/sync", headers=self.adm).status_code, 200)
        self.assertEqual({v["name"]: v for v in self.c.get("/vendors").get_json()["vendors"]}["m365-admin"]["connected_as"], "admin@exemple.test")
        self.assertEqual(self.c.post("/vendors", headers=self.adm, json={"name": "csv1", "kind": "csv-export", "site": "site-alpha"}).status_code, 200)
        self.assertEqual(self.c.post("/vendors/csv1/sync", headers=self.adm).status_code, 400)
        # #604 : export déposé sur le compte -> contrats rattachés au compte, dernière synchronisation renseignée
        rows = [["Nom complet", "Nom d'utilisateur", "Licences"], ["Zoé Z", "zoe@exemple.test", "Visio Plan 2"]]
        r = self.c.post("/import", headers=self.adm, data={"file": _csv_file(rows), "site": "site-alpha", "vendor_account": "csv1"}, content_type="multipart/form-data")
        self.assertEqual((r.status_code, r.get_json()["created"]["contracts"]), (200, 1), r.get_json())
        v1 = {v["name"]: v for v in self.c.get("/vendors").get_json()["vendors"]}["csv1"]
        self.assertTrue(v1["last_sync"] and v1["snapshot"][0]["label"] == "Visio Plan 2")
        self.assertEqual([c["vendor_account"] for c in self.c.get("/contracts").get_json()["contracts"] if c["software"] == "Visio Plan 2"], ["csv1"])
        self.assertEqual(self.c.delete("/vendors/csv1", headers=self.adm).status_code, 200)
        self.assertEqual(self.c.post("/vendors/nope/sync", headers=self.adm).status_code, 404)


class Actions(Base):
    def test_install_uninstall(self):
        calls = []

        def post(url, json=None, timeout=None):
            calls.append((url, json))
            return FakeResp(201, {"id": "cmd-1", "status": "pending"})

        def get(url, timeout=None, **kw):
            return FakeResp(200, {"id": "cmd-1", "status": "done", "result": {"ok": True, "result": {"output": "installed"}}})

        with mock.patch.object(appmod.requests, "post", post), mock.patch.object(appmod.requests, "get", get):
            self.assertEqual(self.c.post("/actions", headers=self.adm, json={"agent_id": "a1", "action": "purge", "package": "vim"}).status_code, 400)
            self.assertEqual(self.c.post("/actions", headers=self.adm, json={"agent_id": "a1", "action": "install", "package": "vim"}).status_code, 400)  # sans confirmation
            r = self.c.post("/actions", headers=self.adm, json={"agent_id": "a1", "action": "install", "package": "vim", "manager": "apt", "host": "PC-01", "confirm": "a1"})
            self.assertEqual(r.status_code, 200, r.get_json())
            self.assertEqual(calls[0][1], {"type": "software_action", "params": {"action": "install", "package": "vim", "manager": "apt"}})
            self.assertTrue(calls[0][0].endswith("/agents/a1/commands"))
            acts = self.c.get("/actions").get_json()["actions"]
            self.assertEqual((acts[0]["status"], acts[0]["result"], acts[0]["command_id"]), ("done", "installed", "cmd-1"))
        self.assertEqual(self.notified[-1][0], "licenses.action")
        with mock.patch.object(appmod.requests, "post", lambda *a, **k: FakeResp(404, {"error": "agent inconnu"})):
            r = self.c.post("/actions", headers=self.adm, json={"agent_id": "zz", "action": "uninstall", "package": "vim", "confirm": "zz"})
            self.assertEqual((r.status_code, r.get_json()["error"]), (502, "central des agents : agent inconnu"))


if __name__ == "__main__":
    unittest.main()
