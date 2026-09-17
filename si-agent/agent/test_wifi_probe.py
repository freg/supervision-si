# -*- coding: utf-8 -*-
"""Tests de la sonde wifi-probe (#525) : analyseurs iw/ping/iperf3 et constats."""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("wifi_probe", os.path.join(HERE, "plugins", "wifi-probe", "wifi_probe.py"))
wp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wp)

LINK = """Connected to 02:11:22:33:44:55 (on wlan0)
\tSSID: Campus
\tfreq: 5240
\tRX: 1234567 bytes (8901 packets)
\tTX: 234567 bytes (1234 packets)
\tsignal: -61 dBm
\trx bitrate: 866.7 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 2
\ttx bitrate: 780.0 MBit/s VHT-MCS 8 80MHz short GI VHT-NSS 2
\tbss flags: short-slot-time
\tdtim period: 1
\tbeacon int: 100
"""
STATION = """Station 02:11:22:33:44:55 (on wlan0)
\tinactive time:\t10 ms
\trx bytes:\t1234567
\trx packets:\t8901
\ttx bytes:\t234567
\ttx packets:\t1000
\ttx retries:\t120
\ttx failed:\t3
\tbeacon loss:\t0
\trx drop misc:\t5
\tsignal:  \t-61 [-63, -65] dBm
\tsignal avg:\t-60 dBm
\ttx bitrate:\t780.0 MBit/s VHT-MCS 8 80MHz short GI VHT-NSS 2
\trx bitrate:\t866.7 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 2
\texpected throughput:\t300.0Mbps
\tauthorized:\tyes
\tconnected time:\t3600 seconds
"""
SURVEY = """Survey data from wlan0
\tfrequency:\t\t\t5240 MHz [in use]
\tnoise:\t\t\t\t-92 dBm
\tchannel active time:\t\t1000 ms
\tchannel busy time:\t\t450 ms
\tchannel receive time:\t\t300 ms
\tchannel transmit time:\t\t100 ms
Survey data from wlan0
\tfrequency:\t\t\t2412 MHz
\tnoise:\t\t\t\t-95 dBm
"""
SCAN = """BSS 02:11:22:33:44:55(on wlan0) -- associated
\tTSF: 1 usec
\tfreq: 5240
\tbeacon interval: 100 TUs
\tsignal: -61.00 dBm
\tSSID: Campus
\tBSS Load:
\t\t * station count: 12
\t\t * channel utilisation: 128/255
\t\t * available admission capacity: 31250 [*32us]
\tHT operation:
\t\t * primary channel: 48
BSS 02:11:22:33:55:66(on wlan0)
\tfreq: 5240
\tsignal: -75.00 dBm
\tSSID: Campus
\tBSS Load:
\t\t * station count: 3
\t\t * channel utilisation: 20/255
BSS 02:11:22:33:55:67(on wlan0)
\tfreq: 5240
\tsignal: -76.00 dBm
\tSSID: Campus-invites
BSS 02:11:22:33:44:56(on wlan0)
\tfreq: 5240
\tsignal: -61.00 dBm
\tSSID: Campus-invites
BSS 02:aa:bb:cc:dd:ee(on wlan0)
\tfreq: 2437
\tsignal: -70.00 dBm
\tSSID: Autre
\tDS Parameter set: channel 6
"""
PING = """PING 192.0.2.1 (192.0.2.1) from 192.0.2.50 wlan0: 56(84) bytes of data.

--- 192.0.2.1 ping statistics ---
20 packets transmitted, 19 received, 5% packet loss, time 3821ms
rtt min/avg/max/mdev = 2.100/18.500/120.300/35.200 ms
"""
IPERF = '{"end": {"sum": {"bits_per_second": 19980000.0, "jitter_ms": 4.2, "lost_percent": 0.5, "lost_packets": 8, "packets": 1600}}}'


class TestAnalyseurs(unittest.TestCase):
    def test_link(self):
        l = wp.parse_link(LINK)
        self.assertTrue(l["connected"])
        self.assertEqual((l["bssid"], l["ssid"], l["freq"], l["channel"], l["band"]), ("02:11:22:33:44:55", "Campus", 5240, 48, "5 GHz"))
        self.assertEqual((l["signal_dbm"], l["tx_mbit"], l["rx_mbit"]), (-61, 780.0, 866.7))
        self.assertFalse(wp.parse_link("Not connected.\n")["connected"])
        self.assertFalse(wp.parse_link("")["connected"])

    def test_channels(self):
        self.assertEqual([wp.freq_to_channel(f) for f in (2412, 2437, 2484, 5180, 5240, 5955)], [1, 6, 14, 36, 48, 1])

    def test_station_et_taux(self):
        s = wp.parse_station(STATION)
        self.assertEqual((s["tx_packets"], s["tx_retries"], s["tx_failed"], s["beacon_loss"], s["connected_s"]), (1000, 120, 3, 0, 3600))
        self.assertEqual(s["expected_mbit"], 300.0)
        r = wp.rates(s, None)
        self.assertEqual((r["retry_pct"], r["failed_pct"], r["delta"]), (12.0, 0.3, False))
        r = wp.rates(s, {"tx_packets": 800, "tx_retries": 60, "tx_failed": 3})
        self.assertEqual((r["retry_pct"], r["failed_pct"], r["window_packets"], r["delta"]), (30.0, 0.0, 200, True))
        # compteurs remis à zéro (réassociation) : on retombe sur l'absolu
        self.assertFalse(wp.rates(s, {"tx_packets": 5000, "tx_retries": 10})["delta"])

    def test_survey(self):
        sv = wp.parse_survey(SURVEY)
        self.assertEqual(len(sv), 2)
        u = wp.channel_usage(sv, None)
        self.assertEqual((u["freq"], u["busy_pct"], u["tx_pct"], u["rx_pct"], u["other_pct"], u["delta"]), (5240, 45.0, 10.0, 30.0, 5.0, False))
        u = wp.channel_usage(sv, [{"freq": 5240, "active_ms": 500, "busy_ms": 100, "rx_ms": 50, "tx_ms": 20}])
        self.assertEqual((u["busy_pct"], u["window_ms"], u["delta"]), (70.0, 500, True))
        self.assertIsNone(wp.channel_usage([], None))

    def test_scan_et_voisinage(self):
        sc = wp.parse_scan(SCAN)
        self.assertEqual(len(sc), 5)
        self.assertEqual((sc[0]["stations"], sc[0]["utilisation_pct"], sc[0]["channel"], sc[0]["associated"]), (12, 50.2, 48, True))
        self.assertEqual(sc[-1]["channel"], 6)
        n = wp.neighbourhood(sc, wp.parse_link(LINK))
        self.assertEqual(n["bss_count"], 5)
        self.assertEqual(n["channels"], {"6": 1, "48": 4})
        # 3 BSS co-canal, mais un seul appartient à une AUTRE radio (...:55:6x) ;
        # ...:44:56 est un second SSID de notre propre borne
        self.assertEqual((n["co_channel_bss"], n["co_channel_radios"]), (3, 1))
        self.assertEqual([b["bssid"] for b in n["co_channel"]], ["02:11:22:33:55:66"])
        self.assertEqual(n["same_ssid"][0]["signal_dbm"], -75.0)
        self.assertEqual(n["our_bss"], {"stations": 12, "utilisation_pct": 50.2})
        # balises sans BSS Load (Zyxel) : pas de bloc our_bss plutot que des « ? »
        sc2 = [{k: v for k, v in b.items() if k not in ("stations", "utilisation_pct")} for b in sc]
        self.assertIsNone(wp.neighbourhood(sc2, wp.parse_link(LINK))["our_bss"])

    def test_ping_iperf(self):
        p = wp.parse_ping(PING)
        self.assertEqual((p["sent"], p["received"], p["loss_pct"], p["avg_ms"], p["jitter_ms"]), (20, 19, 5.0, 18.5, 35.2))
        self.assertEqual(wp.parse_ping("")["sent"] if "sent" in wp.parse_ping("") else None, None)
        i = wp.parse_iperf(IPERF)
        self.assertEqual((i["mbit"], i["jitter_ms"], i["loss_pct"], i["lost"]), (20.0, 4.2, 0.5, 8))
        self.assertIn("error", wp.parse_iperf("pas du json"))


class TestConstats(unittest.TestCase):
    def test_non_associe(self):
        al = wp.evaluate({"connected": False}, {}, None, None, None, None)
        self.assertEqual([a["code"] for a in al], ["not-associated"])
        self.assertEqual(wp.summarize(al)["state"], "critical")

    def test_bon_lien(self):
        link = wp.parse_link(LINK)
        al = wp.evaluate(link, {"retry_pct": 3.0, "failed_pct": 0.0}, {"busy_pct": 20.0, "other_pct": 5.0}, {"our_bss": {"stations": 5, "utilisation_pct": 10}}, {"loss_pct": 0.0, "jitter_ms": 2.0, "avg_ms": 3.0}, None)
        self.assertEqual(al, [])
        self.assertEqual(wp.summarize(al)["state"], "ok")

    def test_lien_degrade(self):
        link = dict(wp.parse_link(LINK), signal_dbm=-72, tx_mbit=12.0, band="2.4 GHz")
        al = wp.evaluate(link, {"retry_pct": 35.0, "failed_pct": 2.0, "window_packets": 120}, {"busy_pct": 85.0, "other_pct": 60.0},
                         {"our_bss": {"stations": 30, "utilisation_pct": 70}, "co_channel": [1, 2, 3], "co_channel_radios": 3, "co_channel_bss": 9},
                         wp.parse_ping(PING), {"loss_pct": 2.0, "jitter_ms": 40.0})
        codes = {a["code"]: a["severity"] for a in al}
        self.assertEqual(codes["rssi"], "warning")
        self.assertEqual(codes["retries"], "critical")
        self.assertEqual(codes["busy"], "critical")
        self.assertEqual(codes["low-rate"], "warning")
        self.assertEqual(codes["band-2g4"], "info")
        self.assertEqual((codes["loss"], codes["jitter"]), ("critical", "warning"))
        self.assertEqual((codes["iperf-loss"], codes["iperf-jitter"], codes["bss-load"], codes["co-channel"]), ("warning", "warning", "warning", "info"))
        self.assertEqual(wp.summarize(al)["state"], "critical")

    def test_debit_bas_sans_trafic(self):
        # au repos le pilote annonce 6 Mbit/s : pas d'alerte sans echantillon de trafic
        link = dict(wp.parse_link(LINK), tx_mbit=6.0)
        self.assertEqual([a["code"] for a in wp.evaluate(link, {"window_packets": 19}, None, None, None, None)], [])
        self.assertIn("low-rate", [a["code"] for a in wp.evaluate(link, {"window_packets": 80}, None, None, None, None)])

    def test_survey_a_zero(self):
        # pilote qui liste toutes les frequences avec des compteurs nuls (mt76) : pas d'occupation
        sv = wp.parse_survey("Survey data from w\n\tfrequency: 5180 MHz [in use]\n\tchannel active time: 0 ms\n\tchannel busy time: 0 ms\n")
        self.assertIsNone(wp.channel_usage(sv, None))

    def test_seuils_personnalises(self):
        link = dict(wp.parse_link(LINK), signal_dbm=-66)
        self.assertEqual([a["code"] for a in wp.evaluate(link, {}, None, None, None, None, {"rssi_warn": -65})], ["rssi"])


if __name__ == "__main__":
    unittest.main()


class RadiosLoad(unittest.TestCase):
    """v3 (#529) : utilisation des canaux par borne, vue du poste."""

    def test_radios_grouped_by_prefix(self):
        sc = wp.parse_scan(SCAN)
        rad = wp.radios_load(sc)
        self.assertTrue(all("radio" in r and len(r["radio"]) == 14 for r in rad))
        # une radio = un préfixe ; plusieurs SSID d'une même radio comptés dans ssids
        self.assertEqual(sum(r["ssids"] for r in rad), len(sc))
        self.assertEqual(rad, sorted(rad, key=lambda r: -(r.get("signal_dbm") or -100)))
        self.assertIn("radios", wp.neighbourhood(sc, wp.parse_link(LINK)))

    def test_idle_busy_alert(self):
        neigh = {"radios": [
            {"bssid": "02:aa:aa:aa:aa:01", "ssid": "Exemple", "channel": 36, "signal_dbm": -60, "stations": 0, "utilisation_pct": 52.0},
            {"bssid": "02:bb:bb:bb:bb:01", "ssid": "Exemple", "channel": 48, "signal_dbm": -85, "stations": 0, "utilisation_pct": 70.0},  # trop faible : ignorée
            {"bssid": "02:cc:cc:cc:cc:01", "ssid": "Exemple", "channel": 36, "signal_dbm": -55, "stations": 12, "utilisation_pct": 55.0},  # chargée : normal
        ]}
        al = wp.evaluate({"connected": True, "signal_dbm": -50}, {}, None, neigh, None, None)
        codes = [a["code"] for a in al]
        self.assertIn("idle-busy-radio", codes)
        msg = next(a for a in al if a["code"] == "idle-busy-radio")["message"]
        self.assertIn("1 borne", msg)
        self.assertIn("canal 36", msg)
        self.assertNotIn("idle-busy-radio", [a["code"] for a in wp.evaluate({"connected": True, "signal_dbm": -50}, {}, None, {"radios": []}, None, None)])
