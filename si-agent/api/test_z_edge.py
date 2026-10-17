# -*- coding: utf-8 -*-
"""#776 : couple de proxys d'entrée -- client DNS (paquets), contrôle DNS (autorité / résolveurs, serveur à modifier),
problèmes des proxys, parcours par les routes (proxys, routes, bascule, application, alertes)."""
import json
import os
import socket
import struct
import sys
import tempfile
import time
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import dnsq  # noqa: E402
import edgepair as ep  # noqa: E402
import store  # noqa: E402


def _enc(name):
    return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"


def packet(qid, answers, aa=True):
    """Réponse DNS fabriquée : en-tête, question, réponses (A, CNAME avec compression vers la question)."""
    q = _enc("www.example.org") + struct.pack(">HH", 1, 1)
    body = b""
    for t, data in answers:
        rd = socket.inet_aton(data) if t == 1 else _enc(data)
        body += b"\xc0\x0c" + struct.pack(">HHIH", t, 1, 300, len(rd)) + rd
    return struct.pack(">HHHHHH", qid, 0x8000 | (0x0400 if aa else 0), 1, len(answers), 0, 0) + q + body


class FakeDNS:
    """Zone example.org : serveurs ns1/ns2 (autorité) ; `auth` = réponse publiée ; `public` = réponse des résolveurs."""
    def __init__(self, auth, public, ns=("ns1.ovh.net", "ns2.ovh.net")):
        self.auth, self.public, self.ns = auth, public, ns
        self.provider_of = dnsq.provider_of

    def query(self, server, name, qtype="A", rd=True):
        if qtype == "NS":
            ans = [{"name": name, "type": "NS", "ttl": 300, "data": n} for n in self.ns] if name == "example.org" else []
            return {"answers": ans, "rcode": 0}
        if name.startswith("ns"):
            return {"answers": [{"name": name, "type": "A", "ttl": 300, "data": "192.0.2.53"}], "rcode": 0}
        src = self.auth if server == "192.0.2.53" else self.public.get(server, self.public.get("*", []))
        return {"answers": [{"name": name, "type": "CNAME" if not x[0].isdigit() else "A", "ttl": 120, "data": x} for x in src], "rcode": 0}

    def authoritative(self, name, resolver, q=None):
        return dnsq.authoritative(name, resolver, q=lambda s, n, t="A", rd=True: self.query(s, n, t, rd))

    def resolve_at(self, server, name, rd=True, q=None, follow=None):
        return dnsq.resolve_at(server, name, rd, q=lambda s, n, t="A", rd_=True: self.query(s, n, t, rd_), follow=follow)


class Pur(unittest.TestCase):
    def test_paquets(self):
        q = dnsq.build_query("www.example.org", "A", rd=False, qid=7)
        self.assertEqual(q[:4], b"\x00\x07\x00\x00")
        r = dnsq.parse_response(packet(7, [(5, "front.example.net"), (1, "198.51.100.10")]))
        self.assertTrue(r["aa"])
        self.assertEqual([(a["type"], a["data"], a["name"]) for a in r["answers"]],
                         [("CNAME", "front.example.net", "www.example.org"), ("A", "198.51.100.10", "www.example.org")])
        with self.assertRaises(ValueError):
            dnsq.parse_response(b"\x00\x01")
        self.assertIn("OVH", dnsq.provider_of(["dns12.ovh.net"])); self.assertIn("autonome", dnsq.provider_of(["ns.example.org"]))

    def test_controle_dns(self):
        rt = {"name": "www.example.org"}
        exp = ["198.51.100.10", "198.51.100.11"]
        ok = ep.dns_check_route(rt, exp, ["1.1.1.1"], FakeDNS(exp, {"*": exp}))
        self.assertEqual((ok["state"], ok["zone"]), ("ok", "example.org"))
        bad = ep.dns_check_route(rt, exp, ["1.1.1.1"], FakeDNS(["front.example.net"], {"*": ["203.0.113.5"]}))
        self.assertEqual(bad["state"], "a_configurer")
        self.assertIn("chez OVH", bad["message"]); self.assertIn("ns1.ovh.net, ns2.ovh.net", bad["message"]); self.assertIn("CNAME vers front.example.net", bad["message"])
        self.assertEqual(bad["records"], ["www.example.org. 300 IN A 198.51.100.10", "www.example.org. 300 IN A 198.51.100.11"])
        prop = ep.dns_check_route(rt, exp, ["1.1.1.1", "8.8.8.8"], FakeDNS(exp, {"1.1.1.1": exp, "8.8.8.8": ["203.0.113.5"]}))
        self.assertEqual(prop["state"], "propagation"); self.assertIn("8.8.8.8", prop["message"])
        self.assertEqual(ep.dns_check_route(rt, exp, ["1.1.1.1"], FakeDNS(exp, {}, ns=()))["state"], "erreur")

    def test_attendu(self):
        px = [{"id": "a", "public_ip": "198.51.100.10", "enabled": True}, {"id": "b", "public_ip": "198.51.100.11", "enabled": True}]
        self.assertEqual(ep.expected_ips({"dns_mode": "both"}, px), ["198.51.100.10", "198.51.100.11"])
        self.assertEqual(ep.expected_ips({"dns_mode": "active", "active_proxy": "b"}, px), ["198.51.100.11"])
        self.assertEqual(ep.expected_ips({"dns_mode": "active", "active_proxy": None}, px), ["198.51.100.10"])

    def test_problemes(self):
        p = {"id": "a", "label": "proxy-a", "agent": "edge-a", "public_ip": "198.51.100.10"}
        st = {"status": {"active": True, "digest": "x", "backends": {"192.0.2.10:443": None, "192.0.2.10:80": 2.0}}}
        codes = [x["code"] for x in ep.proxy_problems(p, st, None, [], "y")]
        self.assertEqual(codes, ["ecart", "interne"])
        self.assertEqual(ep.proxy_problems(p, None, {"error": "commande inconnue : edge"}, [], "y")[0]["code"], "agent-ancien")
        self.assertIn("apt-get install -y haproxy", json.dumps(ep.proxy_problems(p, {"status": {"active": False, "service": "inactive"}}, None, [], None), ensure_ascii=False))


class Parcours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = appmod.app.test_client()
        cls.db = appmod.DB_PATH
        for a in ("edge-a", "edge-b"):
            store.create_agent(cls.db, a, "ovh", label=a)

    def cmds(self, agent):
        conn = store._connect(self.db)
        try:
            return [(r[0], json.loads(r[1])) for r in conn.execute("SELECT id, params FROM commands WHERE agent_id = ? AND type = 'edge' AND status = 'pending' ORDER BY created_at", (agent,))]
        finally:
            conn.close()

    def test_parcours(self):
        for pid, ag, ip, node in (("proxy-a", "edge-a", "198.51.100.10", "pve-a"), ("proxy-b", "edge-b", "198.51.100.11", "pve-b")):
            r = self.c.put("/edge/proxies", json={"proxy": {"id": pid, "agent": ag, "public_ip": ip, "node": node}, "actor": "freg"})
            self.assertEqual(r.status_code, 200, r.get_json()); self.assertIsNone(r.get_json()["proxy"]["warning"])
        self.assertIn("deux proxys", self.c.put("/edge/proxies", json={"proxy": {"id": "proxy-c", "agent": "edge-a", "public_ip": "198.51.100.12"}}).get_json()["error"])
        r = self.c.put("/edge/routes", json={"route": {"id": "www", "mode": "sni", "name": "www.example.org", "backend": "192.0.2.10:443", "candidates": "192.0.2.20:443"}, "actor": "freg"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["route"]["candidates"], ["192.0.2.10:443", "192.0.2.20:443"])
        self.assertEqual(self.c.put("/edge/routes", json={"route": {"id": "x", "mode": "sni", "name": "www.example.org", "backend": "192.0.2.10:443"}}).status_code, 400)
        a, b = self.cmds("edge-a"), self.cmds("edge-b")
        self.assertEqual((len(a), len(b), a[-1][1]["action"]), (1, 1, "apply"))
        self.assertEqual(a[-1][1]["routes"], b[-1][1]["routes"])   # les deux proxys reçoivent la même chose
        # bascule dynamique vers le candidat, refus hors candidats
        self.assertEqual(self.c.post("/edge/switch", json={"route": "www", "backend": "192.0.2.99:443"}).status_code, 400)
        r = self.c.post("/edge/switch", json={"route": "www", "backend": "192.0.2.20:443", "actor": "freg"})
        self.assertEqual(r.status_code, 200, r.get_json())
        last = self.cmds("edge-a")[-1][1]["routes"][0]
        self.assertEqual((last["backend"], last["http_backend"]), ("192.0.2.20:443", "192.0.2.20:80"))
        # acquittement : un proxy à jour, l'autre refuse
        v = self.c.get("/edge").get_json()
        ref = v["ref_digest"]
        for cid, _p in self.cmds("edge-a"):
            store.ack_command(self.db, "edge-a", cid, {"ok": True, "result": {"ok": True, "changed": True, "digest": ref, "status": {"active": True, "digest": ref, "backends": {"192.0.2.20:443": 3.0}}}})
        for cid, _p in self.cmds("edge-b"):
            store.ack_command(self.db, "edge-b", cid, {"ok": False, "error": "configuration refusée par haproxy -c", "result": {"ok": False, "error": "configuration refusée par haproxy -c", "check": "[ALERT] parsing"}})
        v = self.c.get("/edge").get_json()
        pa, pb = v["proxies"]
        self.assertTrue(pa["identical"]); self.assertEqual(pa["problems"], [])
        self.assertEqual(pb["problems"][0]["code"], "apply"); self.assertIn("[ALERT] parsing", pb["problems"][0]["solution"]["command"])
        self.assertEqual(v["routes"][0]["reach"]["proxy-a"], 3.0)
        # contrôle DNS (réseau simulé) -> alerte « DNS à configurer » une seule fois, puis retour à la normale
        events = []
        fake = FakeDNS(["203.0.113.5"], {"*": ["203.0.113.5"]})
        conn = store._connect(self.db)
        try:
            ep.check_dns(conn, time.time(), fake, lambda *a: events.append(a), force=True)
            ep.check_dns(conn, time.time(), fake, lambda *a: events.append(a), force=True)
            self.assertEqual(len(events), 1)
            self.assertEqual((events[0][0], events[0][1]), ("edge-dns", "warning")); self.assertIn("DNS à configurer chez OVH", events[0][2])
            good = FakeDNS(["198.51.100.10", "198.51.100.11"], {"*": ["198.51.100.10", "198.51.100.11"]})
            ep.check_dns(conn, time.time(), good, lambda *a: events.append(a), force=True)
            self.assertEqual((len(events), events[1][1]), (2, "info"))
            # mode « actif » : seul le proxy actif est attendu
            ep.set_settings(conn, {"dns_mode": "active", "active_proxy": "proxy-b"}, "freg")
            ep.check_dns(conn, time.time(), good, lambda *a: events.append(a))
            conn.commit()
        finally:
            conn.close()
        d = self.c.get("/edge").get_json()["routes"][0]["dns"]
        self.assertEqual((d["state"], d["data"]["expected"]), ("a_configurer", ["198.51.100.11"]))
        pv = self.c.get("/edge/preview").get_json()
        self.assertIn("req.ssl_sni -i www.example.org", pv["config"])


if __name__ == "__main__":
    unittest.main()
