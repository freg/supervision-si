# -*- coding: utf-8 -*-
"""Tests purs de Cortex (#462) : principes, normalisation, fusion,
rôles pondérés, corrélation (fenêtre + relation + amont), statistiques."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import correlate as co  # noqa: E402
import normalize as nz  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
