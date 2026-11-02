# -*- coding: utf-8 -*-
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import audit_securite as A  # noqa: E402

DEV = [{"devId": "sw1", "name": "SW-1", "type": "SW", "model": "GS2220"}, {"devId": "gw1", "name": "FW", "type": "GW", "model": "USG"}, {"devId": "ap1", "name": "AP-1", "type": "AP", "model": "WBE660S"}]
WLANS = [{"name": "Perso", "enabled": True, "vlan": 20, "security": {"authType": "wpa2-psk", "wpaKey": "***"}},
         {"name": "Accueil", "enabled": True, "vlan": 40, "guestNetwork": True, "authType": "open", "clientIsolation": False},
         {"name": "Vieux", "enabled": True, "authType": "wep"},
         {"name": "Pro", "enabled": True, "vlan": 30, "security": {"wpaMode": "wpa3", "auth": "802.1x"}}]
VMAP = {"vlans": [{"vid": 20, "management": ["SW-1"], "clients": 12, "subnet": "10.0.20.0/24"}, {"vid": 30, "management": [], "clients": 5}, {"vid": 40, "management": [], "clients": 0}],
        "links": [{"a": "sw1", "a_port": 50, "b": "gw1", "b_port": 1}], "anomalies": ["VLAN 40 : SSID sans port"]}
PORTS = {"sw1": [{"portNum": 50, "enabled": True, "trunk": True, "allowedVLAN": ["all"]}, {"portNum": 7, "enabled": True, "trunk": True, "allowedVLAN": []},
                 {"portNum": 8, "enabled": True, "trunk": False, "portVid": 20}]}
NAT = [{"enabled": True, "kind": "redirection", "name": "rdp", "public_ip": "1.2.3.4", "private_ip": "10.0.20.5", "ports": [3389], "all_ports": False, "any_remote": True},
       {"enabled": True, "kind": "1:1", "name": "srv", "private_ip": "10.0.100.10", "ports": [], "all_ports": True, "any_remote": True},
       {"enabled": False, "kind": "redirection", "name": "off", "private_ip": "10.0.0.9", "ports": [22], "all_ports": False, "any_remote": True}]
NEB = {"devices": DEV, "wlans": WLANS, "vlan_map": VMAP, "ports_by_sw": PORTS, "nat": NAT, "online": {"sw1": True, "ap1": False},
       "firmware": [{"model": "WBE660S", "versions": {"7.10": ["a"], "7.20": ["b"]}}], "licenses": [{"field": "secureWifiExpiry", "value": "2026-12-01", "days_left": 20}],
       "clients": [{"macAddress": "a"}] * 6 + [{"macAddress": "b", "description": "PC"}]}
HIST = {"clients_vus": [{"mac": "m%d" % i, "manufacturer": "MultiTech Systems" if i < 3 else (None if i < 8 else "Dell"), "vlan": "100", "name": None if i < 8 else "pc", "seen_count": 4} for i in range(12)],
        "anomalies": [{"severity": "haute", "message": "x"}]}
PVE = {"hostname": "pve-x", "pveversion": "pve-manager/7.4-3", "updates_pending": 42, "updates_security": 5, "ssh_permit_root_login": "yes", "ssh_password_auth": "yes",
       "users": [{"user": "root@pam", "enabled": True, "tfa": False, "roles": "Administrator"}, {"user": "bob@pve", "tfa": True, "roles": "Administrator"}],
       "firewall": {"cluster_enabled": False, "host_enabled": False}, "listening": [{"addr": "0.0.0.0", "port": "8006", "proc": "pveproxy"}], "backup_jobs": 0,
       "vms": [{"vmid": "100", "name": "ia-gpu", "status": "running", "bridges": ["vmbr0"], "firewall": False, "gpu": True}], "repos_enterprise": False, "repos_no_subscription": True}
HOTE = {"nom": "lora-gw", "ip": "10.0.100.77", "ports": [{"port": 23, "banner": "MultiTech login:"}, {"port": 22}, {"port": 1700, "service": "udp"}], "sorties_externes": ["52.1.2.3"]}


class TestAnalyse(unittest.TestCase):
    def ids(self, cs):
        return {c["id"] for c in cs}

    def test_securite_ssid(self):
        self.assertEqual([A.securite_ssid(w) for w in WLANS], ["wpa2", "ouvert", "wep", "802.1x"])

    def test_nebula(self):
        cs = A.analyser_nebula(NEB); ids = self.ids(cs)
        for att in ("ssid-psk:Perso", "ssid-ouvert:Accueil", "ssid-invite-isolation:Accueil", "ssid-ouvert:Vieux", "ssid-sans-vlan:Vieux", "ssid-vlan-gestion:Perso",
                    "vlan-gestion-partage:20", "vlan-anomalies", "trunk-libre:sw1", "nat-ouvert:10.0.20.5:3389", "nat-tous-ports:10.0.100.10", "equipements-hors-ligne",
                    "fw-mixte:WBE660S", "licence:secureWifiExpiry", "clients-sans-nom"):
            self.assertIn(att, ids, att)
        self.assertNotIn("nat-ouvert:10.0.0.9:22", ids)                      # règle désactivée ignorée
        self.assertFalse(any(c["id"].startswith("ssid-") and "Pro" in c["id"] for c in cs))   # WPA3/802.1X : rien à redire
        t = next(c for c in cs if c["id"] == "trunk-libre:sw1"); self.assertIn("7", t["preuve"]); self.assertNotIn("50", t["preuve"])
        self.assertEqual(next(c for c in cs if c["id"] == "nat-tous-ports:10.0.100.10")["niveau"], "critique")
        self.assertEqual(next(c for c in cs if c["id"] == "ssid-ouvert:Accueil")["impact"], 2)   # réseau d'accueil : impact réduit

    def test_historiques_proxmox_hotes(self):
        cs = A.analyser_historiques(HIST, {"vlans_serveurs": [100]}); ids = self.ids(cs)
        self.assertIn("iot-vlan:100", ids); self.assertIn("clients-inconnus", ids); self.assertIn("anomalies-hautes", ids)
        self.assertEqual(next(c for c in cs if c["id"] == "iot-vlan:100")["impact"], 4)
        self.assertNotIn("iot-vlan:100", self.ids(A.analyser_historiques(HIST, {"vlans_iot": ["100"]})))
        cs = A.analyser_proxmox(PVE); ids = self.ids(cs)
        for att in ("pve-version", "pve-maj", "pve-ssh-root", "pve-2fa", "pve-firewall", "pve-ecoute", "pve-sauvegarde", "vm-gpu:100"):
            self.assertIn(att, ids, att)
        self.assertEqual(next(c for c in cs if c["id"] == "pve-2fa")["preuve"], "root@pam")
        cs = A.analyser_hotes([HOTE]); ids = self.ids(cs)
        self.assertIn("hote-port:lora-gw:23", ids); self.assertIn("hote-port:lora-gw:1700", ids); self.assertIn("hote-sortie:lora-gw", ids); self.assertNotIn("hote-port:lora-gw:22", ids)

    def test_assemblage_matrice_rapport(self):
        col = {"nebula": NEB, "historiques": HIST, "proxmox": [PVE], "hotes": [HOTE], "manuels": [{"titre": "AnyDesk sans MFA", "domaine": "acces", "probabilite": 3, "impact": 4, "preconisation": "MFA"}]}
        etats = {"pve-ssh-root": {"etat": "traite"}, "nat-tous-ports:10.0.100.10": {"probabilite": 1, "note": "VPN seulement"}}
        cs = A.analyser(col, etats, {"vlans_serveurs": [100]})
        self.assertEqual(cs[0]["score"], max(c["score"] for c in cs))
        n = next(c for c in cs if c["id"] == "nat-tous-ports:10.0.100.10"); self.assertEqual((n["probabilite"], n["score"], n["note"]), (1, 4, "VPN seulement"))
        self.assertEqual(next(c for c in cs if c["id"] == "pve-ssh-root")["etat"], "traite")
        self.assertIn("manuel:anydesk-sans-mfa", self.ids(cs))
        m = A.matrice(cs); self.assertEqual(m["total"], len(cs)); self.assertEqual(sum(len(x) for r in m["cases"].values() for x in r.values()), len(cs))
        pre = A.preconisations(cs); self.assertNotIn("pve-ssh-root", {p["id"] for p in pre}); self.assertEqual(pre[0]["rang"], 1)
        md = A.rapport_markdown("Site", cs, ["API Nebula"], "02/11/2026"); self.assertIn("## Matrice", md); self.assertIn("AnyDesk", md); self.assertIn("(Traité)", md)
        csv = A.constats_csv(cs); self.assertIn("Critique", csv); self.assertEqual(csv.count("\n"), len(cs) + 1)
        self.assertEqual(A.valider_manuel({})[1], "titre requis")


class TestRoutes(unittest.TestCase):
    def test_routes(self):
        try:
            import flask  # noqa: F401
        except ImportError:
            self.skipTest("flask absent")
        import sqlite3
        from flask import Flask
        import audit_routes as AR
        d = tempfile.mkdtemp(); db = os.path.join(d, "n.db")

        def conn():
            c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c

        class Cl:
            def ap_wlan_settings(self, sid): return json.loads(json.dumps(WLANS))
            def get_online_status(self, sid, device_type=None): return [{"devId": "ap1", "currentStatus": "offline"}, {"devId": "sw1", "currentStatus": "online"}]
            def sw_port_settings(self, sid, dev): return PORTS["sw1"]
            def gw_nat_settings(self, sid, dev): return {"virtualServer": [{"description": "rdp", "publicPorts": ["3389"], "privateIPv4": "10.0.20.5", "protocol": "tcp"}]}
            def get_site_clients(self, sid, period="2h", features=None): return NEB["clients"]
        app = Flask(__name__)
        AR.register(app, {"conn": conn, "client": lambda: Cl(), "sites": lambda: [{"siteId": "s1", "name": "Campus"}], "devices": lambda sid: DEV,
                          "vlan_map": lambda sid: VMAP, "anomalies": lambda sid: HIST["anomalies"], "org_of": lambda sid: ("org", {"name": "Org", "licenseExpiry": "2030-01-01"})})
        cl = app.test_client()
        r = cl.post("/sites/s1/audit/collecter").get_json(); self.assertTrue(r["nebula"]["ok"]); self.assertEqual(r["nebula"]["erreurs"], []); self.assertEqual(r["nebula"]["nat"], 1)
        self.assertEqual(cl.post("/sites/s1/audit/importer", json={"source": "proxmox", "donnees": PVE}).status_code, 200)
        self.assertEqual(cl.post("/sites/s1/audit/importer", json={"source": "hote", "donnees": json.dumps(HOTE)}).status_code, 200)
        self.assertEqual(cl.post("/sites/s1/audit/importer", json={"source": "manuel", "donnees": {"titre": "AnyDesk", "impact": 4}}).status_code, 200)
        self.assertEqual(cl.post("/sites/s1/audit/importer", json={"source": "x", "donnees": {}}).status_code, 400)
        a = cl.get("/sites/s1/audit").get_json(); ids = {c["id"] for c in a["constats"]}
        self.assertEqual(a["site"], "Campus"); self.assertIn("pve-2fa", ids); self.assertIn("hote-port:lora-gw:23", ids); self.assertIn("manuel:anydesk", ids); self.assertIn("nat-ouvert:10.0.20.5:3389", ids)
        self.assertEqual(len(a["sources"]), 5)
        neb = next(c for c in cl.get("/sites/s1/audit/collectes").get_json() if c["source"] == "nebula")
        self.assertNotIn("wpaKey", json.dumps(neb)); self.assertNotIn("donnees", neb)
        self.assertEqual(cl.put("/sites/s1/audit/constats/pve-2fa", json={"etat": "traite", "note": "fait"}).status_code, 200)
        a = cl.get("/sites/s1/audit").get_json(); self.assertEqual(next(c for c in a["constats"] if c["id"] == "pve-2fa")["etat"], "traite")
        self.assertNotIn("pve-2fa", {p["id"] for p in a["preconisations"]})
        self.assertEqual(cl.put("/sites/s1/audit/reglages", json={"vlans_serveurs": [100]}).get_json()["vlans_serveurs"], ["100"])
        self.assertIn("Campus", cl.get("/sites/s1/audit.md").get_data(as_text=True)); self.assertIn("pve-2fa", cl.get("/sites/s1/audit.csv").get_data(as_text=True))
        # la clé Wi-Fi ne doit jamais arriver en base
        row = conn().execute("SELECT donnees FROM audit_collectes WHERE source='nebula'").fetchone()[0]; self.assertNotIn("wpaKey\": \"s", row)
        cid = next(c["id"] for c in cl.get("/sites/s1/audit/collectes").get_json() if c["source"] == "manuel")
        self.assertEqual(cl.delete("/sites/s1/audit/collectes/%d" % cid).status_code, 200)
        self.assertNotIn("manuel:anydesk", {c["id"] for c in cl.get("/sites/s1/audit").get_json()["constats"]})


if __name__ == "__main__":
    unittest.main()
