# -*- coding: utf-8 -*-
"""Tests de notify-api (#590) : producteurs (jeton interne / consommateur
externe), catalogue et groupe par défaut, résolution, regroupement, rafale,
administration, fil d'envoi (SMTP simulé : succès, échecs, backoff,
disjoncteur, abandon)."""
import json
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(ROOT, "si-proxy", "admin"))
os.environ["NOTIFY_DB"] = os.path.join(tempfile.mkdtemp(prefix="notify-"), "n.sqlite")
os.environ["NOTIFY_INTERNAL_TOKEN"] = "interne-test"
os.environ["NOTIFY_WORKER"] = "0"
os.environ["NOTIFY_SMTP_HOST"] = "smtp.exemple.test"
os.environ["NOTIFY_SMTP_FROM"] = "hub@exemple.test"

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from jwt.algorithms import RSAAlgorithm  # noqa: E402

import app as appmod  # noqa: E402
import auth  # noqa: E402

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks():
    j = json.loads(RSAAlgorithm.to_jwk(KEY.public_key()))
    j.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    return {"keys": [j]}


def token(username="francois", groups=("administrateurs",)):
    return jwt.encode({"preferred_username": username, "name": username, "exp": int(time.time()) + 300, "iat": int(time.time()), "typ": "Bearer", "groups": list(groups)}, KEY, algorithm="RS256", headers={"kid": "k1"})


class Base(unittest.TestCase):
    def setUp(self):
        appmod.verifier = auth.KeycloakVerifier("u", [], fetch=lambda _u: jwks(), allowed_groups=["administrateurs"], what="les notifications")
        c = appmod._conn()
        for t in ("actions", "groups", "assignments", "consumers", "blacklist", "queue", "settings", "events"):
            c.execute("DELETE FROM " + t)
        c.commit()
        c.close()
        appmod.SENDER = appmod.Sender()
        self.sent = []
        appmod.SENDER.deliver = lambda rcpt, subj, body: (self.sent.append((rcpt, subj, body)) or (True, ""))
        self.c = appmod.app.test_client()
        self.adm = {"Authorization": "Bearer " + token()}
        self.prod = {"X-Notify-Token": "interne-test", "X-Notify-Consumer": "mikrotik"}

    def notify(self, action, subject="s", **kw):
        return self.c.post("/notify", headers=self.prod, json=dict({"action": action, "subject": subject, "body": "b"}, **kw))


class Producers(Base):
    def test_auth_and_catalog(self):
        self.assertEqual(self.c.post("/notify", json={"action": "a.b"}).status_code, 401)
        self.assertEqual(self.c.get("/actions").status_code, 401)
        self.assertEqual(self.c.get("/actions", headers={"Authorization": "Bearer " + token("bob", [])}).status_code, 403)
        r = self.c.post("/actions/register", headers=self.prod, json={"actions": [{"id": "mikrotik.nat.add", "label": "Ajout de règle NAT", "severity": "warning"}, {"id": "Bad Name"}]})
        self.assertEqual(r.get_json(), {"registered": ["mikrotik.nat.add"], "rejected": ["Bad Name"]})
        acts = self.c.get("/actions", headers=self.adm).get_json()["actions"]
        self.assertEqual((acts[0]["id"], acts[0]["default_group"], acts[0]["groups"]), ("mikrotik.nat.add", "auto:mikrotik", []))
        groups = self.c.get("/groups", headers=self.adm).get_json()["groups"]
        self.assertEqual([g["id"] for g in groups], ["auto:mikrotik"])
        self.assertTrue(groups[0]["auto"])

    def test_no_recipients_then_resolve(self):
        r = self.notify("cisco.restore", "restauration sw1")
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.get_json()["status"], "no-recipients")
        # l'administrateur renseigne le groupe par défaut -> les suivantes partent
        self.assertEqual(self.c.put("/groups/auto:cisco", headers=self.adm, json={"emails": ["Reseau@Exemple.test", "x@exemple.test"]}).status_code, 200)
        self.assertEqual(self.c.put("/groups/auto:cisco", headers=self.adm, json={"emails": ["pas une adresse"]}).status_code, 400)
        r = self.notify("cisco.restore", "restauration sw1 bis").get_json()
        self.assertEqual((r["status"], r["recipients"]), ("queued", 2))
        self.assertEqual(appmod.SENDER.tick(), 1)
        rcpt, subj, body = self.sent[0]
        self.assertEqual(rcpt, ["reseau@exemple.test", "x@exemple.test"])
        self.assertEqual(subj, "[Hub SI] restauration sw1 bis")
        # retry du premier (sans destinataires) maintenant que le groupe est renseigné
        first = self.c.get("/queue?status=no-recipients", headers=self.adm).get_json()["queue"][0]
        self.assertEqual(self.c.post("/queue/%d/retry" % first["id"], headers=self.adm).status_code, 200)
        self.assertEqual(appmod.SENDER.tick(), 1)

    def test_meta_group_assignment_and_blacklist(self):
        self.c.put("/groups/auto:mikrotik", headers=self.adm, json={"emails": ["reseau@exemple.test"]}) if False else None
        self.notify("mikrotik.nat.add")
        self.assertEqual(self.c.post("/groups", headers=self.adm, json={"name": "Astreinte", "emails": ["astreinte@exemple.test"]}).get_json()["id"], "g:astreinte")
        m = self.c.post("/groups", headers=self.adm, json={"name": "Infra", "kind": "meta", "members": ["g:astreinte", "auto:mikrotik"]}).get_json()
        self.assertEqual(m["id"], "m:infra")
        self.assertEqual(self.c.post("/groups", headers=self.adm, json={"name": "Boucle", "kind": "meta", "members": ["m:boucle"]}).status_code, 400)
        self.assertEqual(self.c.put("/actions/mikrotik.*/groups", headers=self.adm, json={"groups": ["m:infra"]}).status_code, 200)
        self.assertEqual(self.c.put("/actions/mikrotik.nat.add/groups", headers=self.adm, json={"groups": ["g:inconnu"]}).status_code, 400)
        r = self.notify("mikrotik.reboot", "reboot").get_json()
        self.assertEqual((r["status"], r["recipients"]), ("queued", 1))
        self.c.post("/blacklist", headers=self.adm, json={"kind": "email", "value": "astreinte@exemple.test", "reason": "en congé"})
        self.assertEqual(self.notify("mikrotik.reboot", "reboot 2").get_json()["status"], "no-recipients")
        self.c.delete("/blacklist/email/astreinte@exemple.test", headers=self.adm)
        self.c.post("/blacklist", headers=self.adm, json={"kind": "action", "value": "mikrotik.*"})
        self.assertEqual(self.notify("mikrotik.reboot", "reboot 3").get_json()["reason"], "action en liste noire")
        self.assertEqual(self.c.delete("/groups/auto:mikrotik", headers=self.adm).status_code, 400)
        self.assertEqual(self.c.delete("/groups/g:astreinte", headers=self.adm).status_code, 200)
        infra = [g for g in self.c.get("/groups", headers=self.adm).get_json()["groups"] if g["id"] == "m:infra"][0]
        self.assertEqual(infra["members"], ["auto:mikrotik"])

    def test_external_consumer(self):
        r = self.c.post("/consumers", headers=self.adm, json={"name": "GED externe"}).get_json()
        tok = r["token"]
        self.assertEqual(r["name"], "ged-externe")
        self.c.put("/groups/auto:ged", headers=self.adm, json={"emails": ["doc@exemple.test"]}) if False else None
        rr = self.c.post("/notify", headers={"X-Notify-Token": tok}, json={"action": "ged.upload", "subject": "nouveau document"})
        self.assertEqual(rr.status_code, 202)
        self.assertEqual(self.c.get("/consumers", headers=self.adm).get_json()["consumers"][0]["name"], "ged-externe")
        self.assertEqual(self.c.post("/notify", headers={"X-Notify-Token": "faux"}, json={"action": "ged.upload"}).status_code, 401)

    def test_coalesce_and_burst(self):
        self.c.put("/groups/auto:tower", headers=self.adm, json={"emails": ["ops@exemple.test"]}) if False else None
        self.notify("tower.heal.restart", "x")  # crée le groupe auto
        self.c.put("/groups/auto:tower", headers=self.adm, json={"emails": ["ops@exemple.test"]})
        self.c.put("/settings", headers=self.adm, json={"burst_threshold": 5, "coalesce_seconds": 60})
        ids = {self.notify("tower.heal.restart", "ged-api relancé").get_json()["status"] for _ in range(3)}
        self.assertEqual(ids, {"queued", "merged"})
        for i in range(10):
            self.notify("tower.heal.restart", "service %d" % i)
        counts = self.c.get("/queue", headers=self.adm).get_json()["counts"]
        self.assertGreaterEqual(counts.get("held", 0), 5)
        self.assertTrue(any(q["subject"].startswith("Rafale") for q in self.c.get("/queue?status=queued", headers=self.adm).get_json()["queue"]))
        n = appmod.SENDER.tick()
        self.assertTrue(any("regroupée" in b for _, _, b in self.sent))
        rel = self.c.post("/queue/release", headers=self.adm).get_json()["released"]
        self.assertGreaterEqual(rel, 5)


class Delivery(Base):
    def test_backoff_breaker_abandon(self):
        self.notify("cisco.write", "w")
        self.c.put("/groups/auto:cisco", headers=self.adm, json={"emails": ["a@exemple.test"]})
        self.c.put("/settings", headers=self.adm, json={"breaker_failures": 2, "breaker_cooldown": 100, "retry_max": 3})
        self.notify("cisco.write", "w2")
        appmod.SENDER.deliver = lambda r, s, b: (False, "connexion refusée")
        t0 = time.time()
        self.assertEqual(appmod.SENDER.tick(t0), 0)
        row = self.c.get("/queue", headers=self.adm).get_json()["queue"][0]
        self.assertEqual((row["attempts"], row["status"]), (1, "queued"))
        self.assertAlmostEqual(row["due_at"], t0 + 60, delta=2)
        self.assertEqual(appmod.SENDER.tick(t0 + 61), 0)  # 2e échec -> disjoncteur ouvert
        self.assertTrue(appmod.SENDER.state()["breaker_open"])
        self.assertEqual(appmod.SENDER.tick(t0 + 150), 0)  # ouvert : rien tenté
        self.assertEqual(self.c.get("/queue", headers=self.adm).get_json()["queue"][0]["attempts"], 2)
        appmod.SENDER.tick(t0 + 400)  # 3e tentative après refroidissement -> abandon
        row = self.c.get("/queue", headers=self.adm).get_json()["queue"][0]
        self.assertEqual(row["status"], "failed")
        appmod.SENDER.deliver = lambda r, s, b: (True, "")
        self.assertEqual(self.c.post("/queue/%d/retry" % row["id"], headers=self.adm).status_code, 200)
        self.assertEqual(appmod.SENDER.tick(t0 + 500), 1)

    def test_disabled_and_rate(self):
        self.notify("cisco.write", "w")
        self.c.put("/groups/auto:cisco", headers=self.adm, json={"emails": ["a@exemple.test"]})
        self.c.put("/settings", headers=self.adm, json={"enabled": False})
        self.assertEqual(self.notify("cisco.write", "w2").get_json()["status"], "held")
        self.c.put("/settings", headers=self.adm, json={"enabled": True, "max_per_minute": 2})
        self.c.post("/queue/release", headers=self.adm)
        for i in range(4):
            self.notify("cisco.write", "w%d" % (10 + i))
        self.assertEqual(appmod.SENDER.tick(), 2)
        self.assertEqual(appmod.SENDER.tick(), 0)  # débit atteint pour la minute
        self.assertEqual(self.c.get("/health").get_json()["queue"].get("queued"), 3)
        self.assertTrue(self.c.get("/events", headers=self.adm).get_json()["events"])


if __name__ == "__main__":
    unittest.main()
