"""Topologie en arbre (livraison #555)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import topology  # noqa: E402
import vlanmap  # noqa: E402

DEVICES = [
    {"devId": "gw", "name": "USG", "model": "USG FLEX 700H", "type": "GWH", "mac": "AA:BB:CC:00:00:01"},
    {"devId": "core", "name": "XS3800-28", "model": "XS3800-28", "type": "SW", "mac": "AA:BB:CC:00:00:10"},
    {"devId": "edge", "name": "GS2220-1", "model": "GS2220-50HP", "type": "SW", "mac": "AA:BB:CC:00:00:20"},
    {"devId": "ap1", "name": "Borne Hall", "model": "WBE660S", "type": "AP", "mac": "AA:BB:CC:00:00:30"},
    {"devId": "ap2", "name": "Borne Lab", "model": "WBE660S", "type": "AP", "mac": "AA:BB:CC:00:00:40"},
    {"devId": "ap9", "name": "Borne orpheline", "model": "WBE660S", "type": "AP", "mac": "AA:BB:CC:00:00:90"},
]
LLDP = {
    "core": [{"lldpRemLocalPortNum": 1, "lldpRemSysName": "usg", "lldpRemChassisId": "aa:bb:cc:00:00:01", "lldpRemPortId": "ge3"},
             {"lldpRemLocalPortNum": 25, "lldpRemSysName": "GS2220-1", "lldpRemChassisId": "aa:bb:cc:00:00:20", "lldpRemPortId": "49"},
             {"lldpRemLocalPortNum": 3, "lldpRemSysName": "", "lldpRemChassisId": "aa:bb:cc:00:00:33", "lldpRemPortId": "eth0"},  # borne 1 : MAC de base +3
             {"lldpRemLocalPortNum": 4, "lldpRemSysName": "pc-inconnu", "lldpRemChassisId": "11:22:33:44:55:66", "lldpRemPortId": None}],
    "edge": [{"lldpRemLocalPortNum": 49, "lldpRemSysName": "XS3800-28", "lldpRemChassisId": "aa:bb:cc:00:00:10", "lldpRemPortId": "25"},
             {"lldpRemLocalPortNum": 7, "lldpRemSysName": "borne lab", "lldpRemChassisId": "", "lldpRemPortId": "eth0"}],
}
PORTS = {"core": [{"portNum": 25, "enabled": True, "trunk": True, "portVid": 1, "allowedVLAN": ["1", "30"]}, {"portNum": 3, "enabled": True, "trunk": True, "portVid": 1, "allowedVLAN": ["1", "30"]}],
         "edge": [{"portNum": 49, "enabled": True, "trunk": True, "portVid": 1, "allowedVLAN": ["1", "30"]}, {"portNum": 7, "enabled": True, "trunk": True, "portVid": 1, "allowedVLAN": ["30"]}]}
CLIENTS = [
    {"macAddress": "00:11:22:33:44:01", "connectedTo": "ap1", "status": "ONLINE", "vlan": 30, "description": "00:11:22:33:44:01", "osHostname": {"os": "iOS", "hostname": "iphone-x"}, "manufacturer": "Apple"},
    {"macAddress": "00:11:22:33:44:02", "connectedTo": "ap1", "status": "OFFLINE", "vlan": 30, "description": "00:11:22:33:44:02", "osHostname": {"os": None, "hostname": None}, "manufacturer": "MULTITECH"},
    {"macAddress": "00:11:22:33:44:03", "connectedTo": "edge", "status": "ONLINE", "vlan": 20, "description": "Imprimante", "osHostname": {"os": None, "hostname": None}},
    {"macAddress": "00:11:22:33:44:04", "connectedTo": "zzz-inconnu", "status": "ONLINE", "vlan": 20},
    {"macAddress": "00:11:22:33:44:05", "apMac": "AA:BB:CC:00:00:42", "status": "ONLINE"},  # BSSID proche de la borne Lab
]


def _vmap():
    return vlanmap.build_vlan_map(DEVICES, PORTS, LLDP, None, [{"name": "Campus", "vlan": 30}], None, None, None)


class Topo(unittest.TestCase):
    def test_liaisons_vers_bornes_et_passerelle_reconnues(self):
        vm = _vmap()
        dev_links = [l for l in vm["links"] if l.get("device")]
        assert {(l["a"], l["b"]) for l in dev_links} == {("core", "gw"), ("core", "ap1"), ("edge", "ap2")}
        assert all(l["missing_on_a"] == [] and l["missing_on_b"] == [] for l in dev_links)
        ext = [l for l in vm["links"] if l.get("external")]
        assert len(ext) == 1 and ext[0]["sysname"] == "pc-inconnu"
        # aucune fausse anomalie « VLAN manquant » sur une liaison vers une borne
        assert not any("Borne" in a and "manquants" in a for a in vm["anomalies"])
        assert next(l for l in vm["links"] if l["b"] == "ap1")["b_name"] == "Borne Hall"


    def test_arbre_passerelle_en_racine_clients_rattaches(self):
        tree = topology.build_tree(DEVICES, _vmap()["links"], CLIENTS, {"USG": "online", "Borne Hall": "online", "GS2220-1": "offline"})
        by = {n["id"]: n for n in tree["nodes"]}
        assert by["gw"]["parent"] is None and by["gw"]["depth"] == 0
        assert by["core"]["parent"] == "gw" and by["core"]["depth"] == 1 and by["core"]["uplink_port"] == 1 and by["core"]["parent_port"] == 3  # "ge3" -> 3 (_port_num)
        assert by["edge"]["parent"] == "core" and by["edge"]["uplink_port"] == 49 and by["edge"]["parent_port"] == 25
        assert by["ap1"]["parent"] == "core" and by["ap2"]["parent"] == "edge" and by["ap2"]["depth"] == 3
        assert by["ap9"]["parent"] == "gw" and by["ap9"].get("unlinked") is True
        assert by["edge"]["status"] == "offline" and by["ap9"]["status"] == "inconnu"
        # clients : nom lisible, tri en ligne d'abord, filaire selon l'appareil
        assert [c["name"] for c in by["ap1"]["clients"]] == ["iphone-x", "MULTITECH (33:44:02)"]
        assert by["ap1"]["clients"][0]["wired"] is False and by["ap1"]["clients"][0]["os"] == "iOS"
        assert by["edge"]["clients"][0]["name"] == "Imprimante" and by["edge"]["clients"][0]["wired"] is True
        assert by["ap2"]["clients"][0]["mac"] == "00:11:22:33:44:05"  # BSSID proche
        assert [c["mac"] for c in tree["loose_clients"]] == ["00:11:22:33:44:04"]
        assert tree["counts"] == {"devices": 6, "clients": 5, "unlinked": 1}
        assert tree["unmatched"][0]["sysname"] == "pc-inconnu"
        assert [n["id"] for n in tree["nodes"]][:2] == ["gw", "core"]


    def test_sans_passerelle_le_commutateur_le_plus_relie_sert_de_racine(self):
        devs = [d for d in DEVICES if d["devId"] != "gw"]
        lldp = {k: [n for n in v if n["lldpRemSysName"] != "usg"] for k, v in LLDP.items()}
        vm = vlanmap.build_vlan_map(devs, PORTS, lldp, None, None, None, None, None)
        tree = topology.build_tree(devs, vm["links"], [], {})
        by = {n["id"]: n for n in tree["nodes"]}
        assert by["core"]["parent"] is None and by["edge"]["parent"] == "core"


if __name__ == "__main__":
    unittest.main()
