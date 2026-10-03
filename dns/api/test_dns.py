# -*- coding: utf-8 -*-
"""Tests dns-api (test_client) : zones, cache et vue consolidée (divergences), modification appliquée à tous les fournisseurs
avec fallback (Internet en échec -> partiel, intranet servi), rejeu, retour en arrière, validation. Fournisseurs simulés en
mémoire ; providers réels testés sur leurs requêtes (signature OVH, corps Scaleway, scripts nsupdate) avec HTTP/run simulés."""
import os, sys, json, tempfile, unittest, importlib
os.environ["DNS_DATA_DIR"] = tempfile.mkdtemp(); os.environ["CREDENTIALS_INTERNAL_TOKEN"] = "t"
sys.path.insert(0, os.path.dirname(__file__)); import app as appmod; importlib.reload(appmod); import providers

class Fake:
    down = set()
    def __init__(self, label, store): self.label, self.store = label, store
    def list_records(self, zone):
        if self.label in Fake.down: raise providers.ProviderError("%s injoignable" % self.label)
        return [dict(id=None, name=n, type=t, value=v, ttl=300) for (n, t), v in self.store.items()]
    def set_record(self, zone, name, rtype, value, ttl=300):
        if self.label in Fake.down: raise providers.ProviderError("%s injoignable" % self.label)
        self.store[(name, rtype)] = value
    def delete_record(self, zone, name, rtype, value=None):
        if self.label in Fake.down: raise providers.ProviderError("%s injoignable" % self.label)
        self.store.pop((name, rtype), None)
STORES = {}
def factory(spec, creds): return Fake(spec["label"], STORES.setdefault(spec["label"], {}))
appmod.PROVIDER_FACTORY = factory

class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client()
        r = cls.c.post("/zones", json={"name": "Exemple.fr", "providers": [{"kind": "ovh", "credential": "ovh-dns", "label": "ovh"}, {"kind": "scaleway", "credential": "scw-dns", "label": "scw"}, {"kind": "bind", "credential": "tsig", "server": "192.0.2.53", "label": "intranet"}]})
        assert r.status_code == 201, r.json; cls.zone = "exemple.fr"
        STORES["ovh"] = {("www", "A"): "203.0.113.5", ("@", "MX"): "10 mail.exemple.fr."}; STORES["scw"] = {("www", "A"): "203.0.113.5"}; STORES["intranet"] = {("www", "A"): "192.0.2.5"}

    def test_zone_validation(self):
        self.assertEqual(self.c.post("/zones", json={"name": "x", "providers": []}).status_code, 400)
        self.assertIn("server requis", self.c.post("/zones", json={"name": "a.fr", "providers": [{"kind": "bind", "credential": "k"}]}).json["error"])
        self.assertEqual(self.c.post("/zones", json={"name": "exemple.fr", "providers": [{"kind": "ovh", "credential": "x"}]}).status_code, 409)
        z = self.c.get("/zones").json["zones"][0]; self.assertEqual(z["providers"][2]["role"], "intranet"); self.assertEqual(z["providers"][0]["role"], "internet")

    def test_cache_and_changes(self):
        r = self.c.get("/zones/%s/records?refresh=1" % self.zone).json
        self.assertEqual(r["refreshed"], {"ovh": 2, "scw": 1, "intranet": 1})
        www = next(x for x in r["records"] if x["name"] == "www"); self.assertTrue(www["divergent"]); self.assertEqual(www["by_provider"]["intranet"], ["192.0.2.5"])
        self.assertTrue(all(s["status"] == "ok" for s in r["state"]))
        # modification : tous les fournisseurs
        r = self.c.put("/zones/%s/records" % self.zone, json={"name": "api", "type": "A", "value": "203.0.113.9", "ttl": 120, "by_user": "freg"})
        self.assertEqual(r.status_code, 200, r.json); self.assertEqual(STORES["intranet"][("api", "A")], "203.0.113.9"); self.assertEqual(STORES["ovh"][("api", "A")], "203.0.113.9")
        self.assertEqual(self.c.put("/zones/%s/records" % self.zone, json={"name": "bad name", "type": "A", "value": "1.2.3.4"}).status_code, 400)
        self.assertEqual(self.c.put("/zones/%s/records" % self.zone, json={"name": "x", "type": "A", "value": "pas-une-ip"}).json["error"], "A : adresse IPv4 attendue")
        # Internet injoignable -> partiel, l'intranet a la nouvelle valeur (fallback), état dégradé, rejeu quand ça revient
        Fake.down = {"ovh", "scw"}
        r = self.c.put("/zones/%s/records" % self.zone, json={"name": "api", "type": "A", "value": "203.0.113.10", "by_user": "freg"})
        self.assertEqual(r.status_code, 207); self.assertEqual(r.json["status"], "partial"); self.assertEqual(STORES["intranet"][("api", "A")], "203.0.113.10"); self.assertEqual(STORES["ovh"][("api", "A")], "203.0.113.9")
        st = {s["provider"]: s for s in self.c.get("/zones").json["zones"][0]["state"]}; self.assertEqual(st["ovh"]["status"], "degraded"); self.assertEqual(st["intranet"]["status"], "ok")
        self.assertEqual(self.c.post("/zones/%s/replay" % self.zone).json["remaining"], 1)
        Fake.down = set()
        rp = self.c.post("/zones/%s/replay" % self.zone).json; self.assertEqual((rp["replayed"], rp["remaining"]), (1, 0)); self.assertEqual(STORES["ovh"][("api", "A")], "203.0.113.10")
        # retour en arrière de la première modification (avant = aucun enregistrement -> suppression)
        chs = self.c.get("/zones/%s/changes" % self.zone).json["changes"]; first = chs[-1]; self.assertEqual(first["action"], "set"); self.assertEqual(first["before"], [])
        r = self.c.post("/changes/%d/revert" % first["id"], json={"by_user": "freg"}); self.assertEqual(r.status_code, 200); self.assertNotIn(("api", "A"), STORES["ovh"]); self.assertNotIn(("api", "A"), STORES["intranet"])
        self.assertEqual(self.c.get("/zones/%s/changes" % self.zone).json["changes"][-1]["reverted_by"], r.json["change"]["id"])
        # suppression explicite puis zone supprimée
        STORES["ovh"][("old", "TXT")] = "x"; self.c.get("/zones/%s/records?refresh=1" % self.zone)
        self.assertEqual(self.c.delete("/zones/%s/records" % self.zone, json={"name": "old", "type": "TXT"}).status_code, 200); self.assertNotIn(("old", "TXT"), STORES["ovh"])

class Providers(unittest.TestCase):
    def test_ovh_signature_and_flow(self):
        calls = []
        def http(method, url, headers, body):
            calls.append((method, url, body, headers))
            if url.endswith("/record") and method == "GET": return 200, [11]
            if url.endswith("/record/11"): return 200, {"subDomain": "www", "fieldType": "A", "target": "203.0.113.5", "ttl": 300}
            return 200, {}
        p = providers.OvhProvider("AK", "SEC", "CK", http=http)
        self.assertEqual(p.list_records("exemple.fr"), [dict(id="11", name="www", type="A", value="203.0.113.5", ttl=300)])
        self.assertTrue(calls[0][3]["X-Ovh-Signature"].startswith("$1$")); self.assertEqual(calls[0][3]["X-Ovh-Application"], "AK")
        p.set_record("exemple.fr", "www", "A", "203.0.113.9", 120)
        self.assertIn(("PUT", "https://eu.api.ovh.com/1.0/domain/zone/exemple.fr/record/11", {"target": "203.0.113.9", "ttl": 120, "subDomain": "www"}), [(c[0], c[1], c[2]) for c in calls])
        self.assertEqual(calls[-1][1], "https://eu.api.ovh.com/1.0/domain/zone/exemple.fr/refresh")
        p.set_record("exemple.fr", "api", "A", "203.0.113.7"); self.assertEqual([c for c in calls if c[0] == "POST" and c[1].endswith("/record")][0][2]["subDomain"], "api")
        def http_err(m, u, h, b): return 403, {"message": "Invalid signature"}
        with self.assertRaises(providers.ProviderError): providers.OvhProvider("A", "S", "C", http=http_err).list_records("exemple.fr")

    def test_scaleway_and_bind(self):
        calls = []
        def http(method, url, headers, body): calls.append((method, url, body)); return 200, {"records": [{"id": "r1", "name": "www", "type": "A", "data": "203.0.113.5", "ttl": 300}]}
        p = providers.ScalewayProvider("SK", http=http); self.assertEqual(p.list_records("exemple.fr")[0]["value"], "203.0.113.5")
        p.set_record("exemple.fr", "@", "A", "203.0.113.9", 60); self.assertEqual(calls[-1][2]["changes"][0]["set"]["records"][0], {"name": "", "type": "A", "data": "203.0.113.9", "ttl": 60})
        runs = []
        def run(argv, stdin=None): runs.append((argv, stdin)); return (0, "www.int.exemple.fr. 300 IN A 192.0.2.5\nint.exemple.fr. 3600 IN SOA ns1 h 1 2 3 4 5\n", "") if argv[0] == "dig" else (0, "", "")
        b = providers.BindProvider("192.0.2.53", "hubkey", "c2VjcmV0", run=run)
        self.assertEqual(b.list_records("int.exemple.fr"), [dict(id=None, name="www", type="A", value="192.0.2.5", ttl=300)])
        b.set_record("int.exemple.fr", "api", "A", "192.0.2.9", 120)
        self.assertEqual(runs[-1][0], ["nsupdate", "-y", "hmac-sha256:hubkey:c2VjcmV0"]); self.assertIn("update add api.int.exemple.fr. 120 A 192.0.2.9", runs[-1][1]); self.assertIn("zone int.exemple.fr.", runs[-1][1])
        b.set_record("int.exemple.fr", "@", "TXT", "v=spf1 -all"); self.assertIn('update add int.exemple.fr. 300 TXT "v=spf1 -all"', runs[-1][1])
        with self.assertRaises(providers.ProviderError): providers.BindProvider("s", "k", "x", run=lambda a, stdin=None: (2, "", "REFUSED")).set_record("z.fr", "a", "A", "1.2.3.4")
        self.assertEqual(providers.build({"kind": "ovh", "credential": "c"}, lambda n: ("AK/CK", "S")).ck, "CK")
        with self.assertRaises(providers.ProviderError): providers.build({"kind": "ovh", "credential": "c"}, lambda n: ("AK", "S"))

if __name__ == "__main__": unittest.main()
