# -*- coding: utf-8 -*-
"""Tests purs de Cortex (#462) : principes, normalisation, fusion,
rôles pondérés, corrélation (fenêtre + relation + amont), statistiques."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import correlate as co  # noqa: E402
import normalize as nz  # noqa: E402
import places as pl  # noqa: E402
import principles as pr  # noqa: E402


class TestPrinciples(unittest.TestCase):
    def test_evaluate(self):
        e = pr.evaluate("upstream-first", {})
        self.assertEqual((e["base"], e["measured"], e["effective"]), (0.75, None, 0.75))
        e = pr.evaluate("upstream-first", {"upstream-first": {"confirmed": 6, "rejected": 0, "applied": 8}})
        self.assertGreater(e["measured"], 0.75)
        e = pr.evaluate("upstream-first", {"upstream-first": {"confirmed": 0, "rejected": 6}})
        self.assertLess(e["measured"], 0.4)
        self.assertEqual(pr.describe("nimp")["title"], "nimp")
        self.assertTrue(all(0 < p["base"] <= 1 for p in pr.PRINCIPLES.values()))


class TestNormalize(unittest.TestCase):
    def test_keys(self):
        self.assertEqual(nz.entity_key(ip="10.0.0.5", mac="AA-BB-CC-DD-EE-FF"), "mac:aa:bb:cc:dd:ee:ff")
        self.assertEqual(nz.entity_key(ip="10.0.0.5"), "ip:10.0.0.5")
        self.assertEqual(nz.entity_key(ip="127.0.0.1", name="Srv-01"), "name:srv-01")
        self.assertIsNone(nz.entity_key(name="localhost"))

    def test_si_agent(self):
        fleet = [{"agent_id": "a1", "hostname": "srv1", "last_ip": "10.0.0.5", "site": "bureau", "online": "offline", "last_seen_at": "2026-09-08T10:00:00Z", "risks": {"state": "warning", "items": [{"kind": "disk-high", "severity": "warning", "message": "disque à 92 %"}]}, "risks_at": "2026-09-08T10:00:00Z"},
                 {"agent_id": "a2", "hostname": "srv2", "last_ip": "10.0.0.6", "site": "bureau", "online": "online", "risks": {"state": "ok"}}]
        netviews = [{"agent_id": "a1", "hostname": "srv1", "last_ip": "10.0.0.5", "site": "bureau", "summary": {"default_gateway": "10.0.0.1", "default_gateway_state": "reachable", "peers": [{"ip": "10.0.0.6", "connections": 4, "ports": ["tcp/5432"]}]}, "neighbors": [{"ip": "10.0.0.9", "mac": "aa:bb:cc:00:00:09"}]}]
        events = [{"id": 3, "agent_id": "a2", "kind": "service-failed", "severity": "critical", "message": "nginx", "at": "2026-09-08T10:01:00Z", "site": "bureau"}, {"id": 4, "agent_id": "a2", "kind": "x", "severity": "info"}]
        ents, rels, evs = nz.from_si_agent(fleet, netviews, events, {"fleet_blocked": True, "fleet_block_reason": "incident"})
        keys = {e["key"] for e in ents}
        self.assertTrue({"ip:10.0.0.5", "ip:10.0.0.6", "ip:10.0.0.1", "mac:aa:bb:cc:00:00:09"} <= keys)
        gw = [r for r in rels if r["kind"] == "gateway_of"][0]
        self.assertEqual((gw["a"], gw["b"], gw["principle"]), ("ip:10.0.0.1", "ip:10.0.0.5", "gateway-of"))
        kinds = sorted(e["kind"] for e in evs)
        self.assertEqual(kinds, ["agent-offline", "fleet-blocked", "risk:disk-high", "service-failed"])
        self.assertTrue(all(len(e["fingerprint"]) == 20 for e in evs))
        # stabilité de l'empreinte
        ents2, rels2, evs2 = nz.from_si_agent(fleet, netviews, events)
        self.assertEqual({e["fingerprint"] for e in evs if e["kind"] != "fleet-blocked"}, {e["fingerprint"] for e in evs2})

    def test_other_sources(self):
        _, _, evs = nz.from_vigilance([{"id": 1, "device_mac": "aa:bb:cc:dd:ee:01", "device_label": "PC-1", "signal_type": "volume_growth", "severity": "warning", "detail": "+300 %", "detected_at": "t"}])
        self.assertEqual((evs[0]["entity"], evs[0]["kind"]), ("mac:aa:bb:cc:dd:ee:01", "signal:volume_growth"))
        ents, rels, evs = nz.from_ups([{"id": 1, "name": "UPS-1", "host": "10.0.0.50", "site": "Bureau", "active_alerts": [{"id": 9, "kind": "on_battery", "severity": "critical", "message": "sur batterie", "opened_at": "t"}], "stale": None}])
        self.assertEqual(rels[0]["kind"], "powers_site"); self.assertEqual(rels[0]["b"], "site:bureau")
        self.assertEqual(evs[0]["kind"], "ups:on_battery")
        _, _, evs = nz.from_orchestrator([{"id": 5, "rule_name": "no_services", "subject_key": "aa:bb:cc:dd:ee:02", "severity": "info", "message": "m", "status": "open"}, {"id": 6, "rule_name": "x", "subject_key": "aa:bb:cc:dd:ee:03", "status": "done"}])
        self.assertEqual(len(evs), 1)
        ents, rels, evs = nz.from_netprobe([{"id": 1, "ip_address": "10.0.0.7", "label": "switch"}], [{"id": 1, "target_id": 1, "success": 0, "error": "timeout", "sampled_at": "t"}], [{"id": 2, "target_id": 1, "analyzer_name": "latency_degradation", "severity": "warning", "message": "x2"}])
        self.assertEqual(sorted(e["kind"] for e in evs), ["analysis:latency_degradation", "probe:unreachable"])
        ents, rels, _ = nz.from_network_agent([{"name": "Siège", "segments": [{"id": 1}]}],
            [{"id": 10, "ip_address": "10.0.0.1", "mac_address": "aa:bb:cc:dd:ee:10", "network_segment_id": 1, "role_hint": "passerelle probable (NAT/routeur)", "external_relay_count": 40, "services": [{"port": 53}]},
             {"id": 11, "ip_address": "10.0.0.5", "mac_address": "aa:bb:cc:dd:ee:11", "network_segment_id": 1}], {1: [{"device_a_id": 10, "device_b_id": 11, "bytes_total": 5e6}]})
        e10 = [e for e in ents if e["key"] == "mac:aa:bb:cc:dd:ee:10"][0]
        self.assertEqual(sorted(h["role"] for h in e10["hints"]), ["dns", "passerelle"])
        self.assertEqual(e10["site"], "Siège")
        self.assertEqual(rels[0]["kind"], "flow")
        self.assertEqual(nz.from_backups({"last": {"rc": 0}}), ([], [], []))
        self.assertEqual(nz.from_backups({"last": {"rc": 1, "kind": "full"}})[2][0]["kind"], "backup:failed")

    def test_alias_consolidation(self):
        ents = [nz._ent("mac:aa:bb:cc:00:00:04", "equipement", None, "192.168.1.35", "aa:bb:cc:00:00:04", None, "vigilance", "x"),
                nz._ent("ip:192.168.1.35", "hote", "PC-COMPTA", "192.168.1.35", None, "siege", "si-agent", "pc"),
                nz._ent("name:pc-compta", "cible", "PC-COMPTA", None, None, None, "netprobe", 1)]
        alias = nz.alias_map(ents)
        self.assertEqual(alias, {"ip:192.168.1.35": "mac:aa:bb:cc:00:00:04", "name:pc-compta": "mac:aa:bb:cc:00:00:04"})
        evs = [{"entity": "name:pc-compta"}]; rels = [{"a": "ip:192.168.1.35", "b": "ip:10.0.0.1"}]
        e2, r2, v2 = nz.apply_aliases(ents, rels, evs, alias)
        m = nz.merge_entities(e2)
        self.assertEqual(len(m), 1); self.assertEqual((m[0]["name"], m[0]["site"], m[0]["kind"]), ("PC-COMPTA", "siege", "hote"))
        self.assertEqual(v2[0]["entity"], "mac:aa:bb:cc:00:00:04"); self.assertEqual(r2[0]["a"], "mac:aa:bb:cc:00:00:04")
        _, _, evs = nz.from_vigilance([{"id": 1, "device_mac": "aa:bb:cc:dd:ee:01", "device_label": "10.0.0.9", "signal_type": "x", "severity": "high"}])
        self.assertEqual(evs[0]["severity"], "critical")

    def test_merge_and_roles(self):
        a = nz._ent("ip:10.0.0.1", "equipement", None, "10.0.0.1", None, None, "network-agent", 1, [{"role": "passerelle", "principle": "relay-gateway", "evidence": "relais"}])
        b = nz._ent("ip:10.0.0.1", "passerelle", "gw", "10.0.0.1", None, "bureau", "si-agent", "g", [{"role": "passerelle", "principle": "gateway-of", "evidence": "route de srv1"}])
        m = nz.merge_entities([a, b])
        self.assertEqual(len(m), 1)
        self.assertEqual((m[0]["kind"], m[0]["name"], m[0]["site"], len(m[0]["origins"]), len(m[0]["hints"])), ("passerelle", "gw", "bureau", 2, 2))
        roles = nz.role_hypotheses(m[0])
        self.assertEqual(roles[0]["role"], "passerelle")
        self.assertGreater(roles[0]["confidence"], 0.85)          # deux indices concordants > chacun seul
        self.assertEqual(sorted(roles[0]["principles"]), ["gateway-of", "relay-gateway"])


class TestCorrelate(unittest.TestCase):
    def setUp(self):
        self.entities = [{"key": "ip:10.0.0.1", "kind": "passerelle", "name": "routeur", "site": "bureau"},
                         {"key": "ip:10.0.0.5", "kind": "hote", "name": "srv1", "site": "bureau"},
                         {"key": "ip:10.0.0.6", "kind": "hote", "name": "srv2", "site": "bureau"},
                         {"key": "ip:10.0.0.50", "kind": "onduleur", "name": "UPS-1", "site": "bureau"},
                         {"key": "ip:10.9.9.9", "kind": "hote", "name": "loin", "site": "agence"}]
        self.relations = [{"a": "ip:10.0.0.1", "b": "ip:10.0.0.5", "kind": "gateway_of", "weight": 1},
                          {"a": "ip:10.0.0.1", "b": "ip:10.0.0.6", "kind": "gateway_of", "weight": 1},
                          {"a": "ip:10.0.0.50", "b": "site:bureau", "kind": "powers_site", "weight": 0.5}]

    def ev(self, fp, entity, sev, at, site=None, kind="x"):
        return {"fingerprint": fp, "entity": entity, "severity": sev, "at": at, "last_at": at, "kind": kind, "site": site, "source": "s", "state": "open"}

    def test_gateway_root_cause(self):
        evs = [self.ev("e1", "ip:10.0.0.5", "warning", "2026-09-08T10:00:10Z", kind="agent-offline"),
               self.ev("e2", "ip:10.0.0.6", "warning", "2026-09-08T10:00:40Z", kind="agent-offline"),
               self.ev("e3", "ip:10.0.0.1", "critical", "2026-09-08T10:00:00Z", kind="probe:unreachable"),
               self.ev("e4", "ip:10.9.9.9", "warning", "2026-09-08T10:00:20Z", kind="agent-offline")]
        inc = co.build_incidents(evs, self.relations, self.entities, window_s=300)
        self.assertEqual(len(inc), 2)
        main = [i for i in inc if len(i["entities"]) == 3][0]
        self.assertEqual((main["root"], main["severity"], main["weak"]), ("ip:10.0.0.1", "critical", False))
        h = main["hypotheses"][0]
        self.assertEqual(h["principle"], "upstream-first")
        self.assertIn("routeur", h["claim"]); self.assertGreater(h["confidence"], 0.6)
        self.assertEqual(sorted(main["events"]), ["e1", "e2", "e3"])
        alone = [i for i in inc if len(i["entities"]) == 1][0]
        self.assertEqual(alone["hypotheses"][0]["principle"], "single-event")

    def test_ups_powers_site(self):
        evs = [self.ev("u", "ip:10.0.0.50", "critical", "2026-09-08T10:00:00Z", kind="ups:on_battery"),
               self.ev("h1", "ip:10.0.0.5", "warning", "2026-09-08T10:02:00Z", kind="agent-offline")]
        inc = co.build_incidents(evs, self.relations, self.entities, window_s=300)
        self.assertEqual(len(inc), 1)
        self.assertEqual(inc[0]["root"], "ip:10.0.0.50")

    def test_window_splits_and_site_cluster(self):
        evs = [self.ev("a", "ip:10.0.0.5", "warning", "2026-09-08T10:00:00Z"), self.ev("b", "ip:10.0.0.6", "warning", "2026-09-08T11:00:00Z")]
        self.assertEqual(len(co.build_incidents(evs, self.relations, self.entities, window_s=300)), 2)
        # sans relation : même site -> regroupement faible
        evs = [self.ev("a", "ip:10.0.0.5", "warning", "2026-09-08T10:00:00Z", site="bureau"), self.ev("b", "ip:10.0.0.6", "warning", "2026-09-08T10:01:00Z", site="bureau")]
        inc = co.build_incidents(evs, [], self.entities, window_s=300)
        self.assertEqual(len(inc), 1); self.assertTrue(inc[0]["weak"])
        self.assertTrue(any(h["principle"] == "site-cluster" for h in inc[0]["hypotheses"]))
        # retour humain négatif sur site-cluster -> confiance baisse
        inc2 = co.build_incidents(evs, [], self.entities, window_s=300, feedback={"site-cluster": {"confirmed": 0, "rejected": 5}})
        self.assertLess(inc2[0]["confidence"], inc[0]["confidence"])

    def test_stats(self):
        evs = [{"fingerprint": "a", "source": "ups", "severity": "critical", "entity": "x", "at": "2026-09-08T10:00:00Z", "count": 3},
               {"fingerprint": "b", "source": "si-agent", "severity": "warning", "entity": "y", "at": "2020-01-01T00:00:00Z"}]
        s = co.stats(evs, [{"state": "open", "weak": True, "severity": "critical"}], days=7, now=co.parse_ts("2026-09-08T12:00:00Z"))
        self.assertEqual(s["events_by_source"], {"ups": 1})
        self.assertEqual(s["noisy_entities"][0], {"entity": "x", "count": 3})
        self.assertEqual((s["incidents_open"], s["incidents_weak"]), (1, 1))


class TestStep2(unittest.TestCase):
    def test_vendor_and_new_sources(self):
        e = nz._ent("mac:b8:27:eb:00:00:01", "equipement", None, "10.0.0.20", "b8:27:eb:00:00:01", None, "network-agent", 1)
        nz.with_vendor_hints([e])
        self.assertEqual(e["vendor"], "Raspberry Pi"); self.assertEqual(e["hints"][0]["role"], "petit-ordinateur")
        e2 = nz._ent("mac:3c:22:fb:00:00:01", "equipement", None, None, "3c:22:fb:00:00:01", None, "x", 1)
        nz.with_vendor_hints([e2]); self.assertEqual((e2.get("vendor"), e2["hints"]), ("Apple", []))
        ents, _, _ = nz.from_classifier([{"id": 1, "input_text": "SRV-DNS-01", "category": "infrastructure", "confirmed": 1}, {"id": 2, "input_text": "x", "category": None}])
        self.assertEqual(len(ents), 1); self.assertEqual(ents[0]["hints"][0]["principle"], "name-class"); self.assertIn("confirmée", ents[0]["hints"][0]["evidence"])
        ents, rels, _ = nz.from_nebula([{"id": 1, "name": "AP-Accueil", "mac_address": "b8:ec:a3:00:00:01", "device_type": "AP", "model": "NWA110AX", "site": "Alpha"}],
                                       [{"id": 5, "name": "tablette", "mac_address": "3c:22:fb:00:00:09", "ipv4_address": "172.16.1.40", "connected_to": "AP-Accueil", "ssid_name": "NUM", "manufacturer": "Apple"}])
        self.assertEqual(ents[0]["hints"][0]["role"], "borne-wifi"); self.assertEqual(ents[0]["site"], "Alpha")
        self.assertEqual((rels[0]["a"], rels[0]["b"], rels[0]["kind"], rels[0]["principle"]), ("mac:b8:ec:a3:00:00:01", "mac:3c:22:fb:00:00:09", "uplink", "attached-to"))
        ents, _, _ = nz.from_ipam([{"id": 3, "ip": "10.0.0.7", "mac": None, "hostname": "sw-core", "description": "cœur de réseau", "subnet": "10.0.0.0/24"}])
        self.assertEqual((ents[0]["key"], ents[0]["description"], ents[0]["subnet"]), ("ip:10.0.0.7", "cœur de réseau", "10.0.0.0/24"))
        h = nz.services_hints([{"id": 10}], {"10": [{"protocol": "udp", "port": 53, "packet_count": 40}, {"protocol": "tcp", "port": 8080}]})
        self.assertEqual([x["role"] for x in h[10]], ["dns"])

    def test_routes_and_changes(self):
        nvs = [{"agent_id": "a1", "hostname": "srv1", "last_ip": "10.0.0.5", "summary": {"default_gateway": "10.0.0.1", "default_gateway_state": "reachable", "attached_subnets": ["10.0.0.0/24"], "reachable_subnets": [{"cidr": "10.1.0.0/16", "via": "10.0.0.254"}]}}]
        routes = nz.routes_from_netviews(nvs)
        self.assertEqual([(r["kind"], r["destination"], r["via"]) for r in routes], [("default", "default", "10.0.0.1"), ("attached", "10.0.0.0/24", None), ("reachable", "10.1.0.0/16", "10.0.0.254")])
        import changes as ch
        roles = lambda e: [{"role": e.get("_role")}] if e.get("_role") else []  # noqa: E731
        before = ch.snapshot([{"key": "a", "kind": "hote", "site": "s1", "_role": "dns", "origins": [{"source": "si-agent"}]}, {"key": "gone", "kind": "hote", "origins": [{"source": "ups"}]}, {"key": "gone2", "kind": "hote", "origins": [{"source": "ups"}]}],
                             [{"a": "g", "b": "a", "kind": "gateway_of"}], [{"host": "a", "kind": "default", "via": "10.0.0.1"}], roles)
        after = ch.snapshot([{"key": "a", "kind": "hote", "site": "s1", "_role": "web", "origins": [{"source": "si-agent"}]}, {"key": "b", "kind": "passerelle", "site": "s1", "origins": []}],
                            [{"a": "b", "b": "a", "kind": "gateway_of"}], [{"host": "a", "kind": "default", "via": "10.0.0.9"}], roles)
        out = ch.compute_changes(before, after, failed_sources={"ups"}, names={"a": "srv1"})
        kinds = sorted(c["kind"] for c in out)
        self.assertEqual(kinds, ["entity-new", "gateway-changed", "relation-gone", "relation-new", "role-changed"])
        self.assertTrue(any("srv1 : rôle dominant dns → web" == c["message"] for c in out))
        # entités « gone » d'une source en échec : pas signalées
        self.assertFalse(any(c["kind"] == "entity-gone" for c in out))
        out2 = ch.compute_changes(before, after, failed_sources=set())
        self.assertEqual(sum(1 for c in out2 if c["kind"] == "entity-gone"), 2)


class TestStep3Places(unittest.TestCase):
    GEOS = [{"localisation": "Bureau", "latitude": 48.85, "longitude": 2.35, "location_type": "site", "parent_localisation": None},
            {"localisation": "Salle serveurs", "latitude": None, "longitude": None, "location_type": "room", "parent_localisation": "Bureau"},
            {"localisation": "Agence Annexe Nord", "latitude": 50.63, "longitude": 3.06, "location_type": None, "parent_localisation": None},
            {"localisation": "__default__", "latitude": 46.6, "longitude": 2.4}]
    SITES = [{"name": "bureau", "latitude": None, "longitude": None, "segments": [{"id": 1}]}]
    DEVICES = [{"id": 10, "ip_address": "192.168.1.20", "mac_address": "aa:bb:cc:00:00:20", "hostname": "sw-acces", "network_segment_id": 1, "building": "B1", "room": "Local technique"},
               {"id": 11, "ip_address": "192.168.1.21", "mac_address": "aa:bb:cc:00:00:21", "hostname": "cam-parking", "network_segment_id": 1, "latitude": 48.851, "longitude": 2.351}]

    def test_places_hierarchy_and_inheritance(self):
        na, by_dev = pl.places_from_network_agent(self.SITES, self.DEVICES)
        places, alias = pl.merge_places(pl.places_from_geolocations(self.GEOS), na)
        by = {p["key"]: p for p in places}
        # « lieu:bureau » (géolocalisation typée site) et « site:bureau » (network-agent) = un seul lieu
        self.assertEqual(alias["lieu:bureau"], alias["site:bureau"])
        self.assertEqual(len([p for p in places if p["name"].lower() == "bureau"]), 1)
        # la salle sans coordonnées hérite du site (place-hierarchy) ; la chaîne est site > bâtiment > salle
        room = by[by_dev[10]]
        self.assertEqual(room["kind"], "salle"); self.assertEqual(room["principle"], "place-hierarchy"); self.assertAlmostEqual(room["lat"], 48.85)
        chain = pl.place_chain(by, by_dev[10], alias)
        self.assertEqual([c["kind"] for c in chain], ["site", "batiment", "salle"])
        self.assertEqual(by["salle:salle serveurs"]["principle"], "place-hierarchy")

    def test_resolution_ladder(self):
        ents, rels, _ = nz.from_network_agent(self.SITES, self.DEVICES, {})
        ents += [nz._ent("ip:192.168.1.30", "hote", "pc-compta", "192.168.1.30", None, "bureau", "si-agent", "a1"),
                 nz._ent("ip:192.168.1.31", "hote", "portable", "192.168.1.31", None, None, "si-agent", "a2"),
                 nz._ent("ip:10.9.9.9", "pair", None, "10.9.9.9", None, None, "network-agent", 99),
                 nz._ent("ip:172.16.0.5", "equipement", "Annexe-Nord-cam", "172.16.0.5", None, None, "network-agent", 98)]
        rels += [{"a": "mac:aa:bb:cc:00:00:20", "b": "ip:192.168.1.31", "kind": "uplink", "weight": 0.8},
                 {"a": "ip:192.168.1.30", "b": "ip:10.9.9.9", "kind": "flow", "weight": 0.3}]
        matches = [{"subject": "name:annexe-nord-cam", "localisation": "Agence Annexe Nord", "latitude": 50.63, "longitude": 3.06, "status": "auto", "method": "similar", "score": 0.8}]
        na, by_dev = pl.places_from_network_agent(self.SITES, self.DEVICES)
        places, alias = pl.merge_places(pl.places_from_geolocations(self.GEOS), na)
        pos = pl.resolve_positions(ents, rels, places, alias, geolocations=self.GEOS, matches=matches, entity_places={e["key"]: e["place"] for e in ents if e.get("place")})
        p = lambda k: pos[k]  # noqa: E731
        self.assertEqual(p("mac:aa:bb:cc:00:00:21")["principle"], "pos-declared")          # coordonnées portées par l'appareil
        self.assertEqual(p("mac:aa:bb:cc:00:00:20")["principle"], "pos-place")             # salle déclarée (héritée du site)
        self.assertEqual(p("ip:192.168.1.30")["principle"], "pos-place")                   # site textuel positionné
        self.assertEqual(p("ip:192.168.1.31")["principle"], "pos-propagated")              # client WiFi -> sa borne
        self.assertEqual(p("ip:192.168.1.31")["chain"][0]["from"], "mac:aa:bb:cc:00:00:20")
        self.assertEqual(p("ip:172.16.0.5")["principle"], "pos-resolved-name")             # correspondance automatique
        self.assertEqual(p("ip:10.9.9.9")["principle"], "pos-neighbor")                    # voisin de flux
        self.assertLess(p("ip:10.9.9.9")["confidence"], p("ip:192.168.1.31")["confidence"])
        # tout barreau est un principe nommé ; l'ordre de l'échelle est décroissant
        for v in pos.values():
            self.assertIn(v["principle"], pr.PRINCIPLES)
        self.assertGreater(p("mac:aa:bb:cc:00:00:21")["confidence"], p("ip:192.168.1.31")["confidence"])
        # file de travail : rien (tout est positionné hors repli) ; sans __default__ le pair isolé y entre
        self.assertEqual(pl.work_queue(ents, pos), [])
        pos2 = pl.resolve_positions(ents, [], places, alias, geolocations=[g for g in self.GEOS if g["localisation"] != "__default__"], matches=matches)
        q = pl.work_queue(ents, pos2)
        queued = {x["key"]: x["status"] for g in q for x in g["entities"]}
        self.assertEqual(queued, {"ip:10.9.9.9": "sans position", "ip:192.168.1.31": "sans position"})   # sans relation, le portable n'a plus de borne

    def test_sheet_and_layers(self):
        ents, rels, _ = nz.from_network_agent(self.SITES, self.DEVICES, {})
        ents += [nz._ent("ip:192.168.1.30", "hote", "pc-compta", "192.168.1.30", None, "bureau", "si-agent", "a1"),
                 nz._ent("ip:192.168.1.250", "onduleur", "UPS-Bureau", "192.168.1.250", None, "bureau", "ups", 1)]
        rels += [{"a": "ip:192.168.1.250", "b": "site:bureau", "kind": "powers_site", "weight": 0.5},
                 {"a": "mac:aa:bb:cc:00:00:20", "b": "ip:192.168.1.30", "kind": "gateway_of", "weight": 1.0, "evidence": "route par défaut"}]
        na, by_dev = pl.places_from_network_agent(self.SITES, self.DEVICES)
        places, alias = pl.merge_places(pl.places_from_geolocations(self.GEOS), na)
        pos = pl.resolve_positions(ents, rels, places, alias, geolocations=self.GEOS, entity_places={e["key"]: e["place"] for e in ents if e.get("place")})
        by = {p["key"]: p for p in places}
        ebk = {e["key"]: e for e in ents}
        incidents = [{"key": "inc1", "title": "onduleur", "severity": "critical", "state": "open", "root": "ip:192.168.1.250", "entities": ["ip:192.168.1.250", "ip:192.168.1.30"]}]
        events = [{"entity": "ip:192.168.1.250", "severity": "critical", "state": "open"}]
        sheet = pl.intervention_sheet(ebk["ip:192.168.1.30"], pos["ip:192.168.1.30"], by, alias, rels, incidents, events, ebk, pos,
                                      notes={alias.get("site:bureau", "site:bureau"): {"contact": "Marie 06…", "access": "badge + clé armoire"}},
                                      bastion_targets=["192.168.1.30"], tickets_url="https://hub/tickets")
        self.assertEqual([w["kind"] for w in sheet["where"]], ["site"])
        self.assertEqual(sheet["contact"], "Marie 06…"); self.assertTrue(sheet["bastion"]["available"]); self.assertIn("pc-compta", sheet["ticket_url"])
        ups = [u for u in sheet["upstream"] if u["kind"] == "powers_site"]
        self.assertEqual(ups[0]["state"], "critical")                       # l'onduleur du site est en défaut
        self.assertEqual([u["kind"] for u in sheet["upstream"] if u["kind"] == "gateway_of"], ["gateway_of"])
        self.assertEqual(sheet["incidents"][0]["key"], "inc1"); self.assertTrue(sheet["supervised"])
        # couches : halo d'incident sur la cause, densité par lieu, non supervisé = vu par la découverte seule
        lay = pl.layers(ents, pos, incidents, rels, by)
        self.assertEqual(lay["summary"]["incidents"], 1)
        self.assertEqual(lay["incidents"]["features"][0]["properties"]["severity"], "critical")
        unsup = {f["properties"]["key"] for f in lay["unsupervised"]["features"]}
        self.assertIn("mac:aa:bb:cc:00:00:21", unsup); self.assertNotIn("ip:192.168.1.30", unsup)
        self.assertGreaterEqual(lay["summary"]["places"], 1)
        self.assertTrue(all(f["geometry"]["type"] == "LineString" for f in lay["dependencies"]["features"]))


if __name__ == "__main__":
    unittest.main()
