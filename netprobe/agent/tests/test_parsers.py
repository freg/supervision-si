"""Analyseurs de sorties système -- sorties RÉELLES d'iw (Raspberry Pi
OS, brcmfmac / mt76) et d'iputils-ping reproduites ci-dessous.
Lancer : python3 -m unittest discover -s netprobe/agent/tests"""
import unittest

from netprobe_agent import parsers as P

IW_LINK_CONNECTED = """Connected to 9c:8e:cd:12:34:56 (on wlan0)
\tSSID: Alpha-Prod
\tfreq: 2437
\tRX: 20539485 bytes (145203 packets)
\tTX: 3130862 bytes (30516 packets)
\tsignal: -61 dBm
\trx bitrate: 65.0 MBit/s MCS 7
\ttx bitrate: 72.2 MBit/s MCS 7 short GI

\tbss flags:\tshort-slot-time
\tdtim period:\t1
\tbeacon int:\t100
"""

IW_LINK_5GHZ = """Connected to 9c:8e:cd:aa:bb:cc (on wlan0)
\tSSID: Alpha-5G
\tfreq: 5220
\tRX: 1 bytes (1 packets)
\tTX: 2 bytes (2 packets)
\tsignal: -55 dBm
\trx bitrate: 390.0 MBit/s VHT-MCS 9 80MHz VHT-NSS 1
\ttx bitrate: 433.3 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 1
"""

IW_LINK_NOT_CONNECTED = "Not connected.\n"

IW_SCAN = """BSS 9c:8e:cd:12:34:56(on wlan0) -- associated
\tlast seen: 120 ms ago
\tTSF: 0 usec (0d, 00:00:00)
\tfreq: 2437
\tbeacon interval: 100 TUs
\tcapability: ESS Privacy ShortSlotTime (0x0411)
\tsignal: -61.00 dBm
\tSSID: Alpha-Prod
\tSupported rates: 1.0* 2.0* 5.5* 11.0* 6.0 9.0 12.0 18.0
\tDS Parameter set: channel 6
\tHT operation:
\t\t * primary channel: 6
\t\t * secondary channel offset: no secondary
\tRSN:\t * Version: 1
\t\t * Group cipher: CCMP
BSS 34:56:78:9a:bc:de(on wlan0)
\tlast seen: 340 ms ago
\tfreq: 2437
\tcapability: ESS Privacy (0x0411)
\tsignal: -48.00 dBm
\tSSID: Freebox-Voisin
\tDS Parameter set: channel 6
\tHT operation:
\t\t * primary channel: 6
\t\t * secondary channel offset: above
\tRSN:\t * Version: 1
BSS 11:22:33:44:55:66(on wlan0)
\tfreq: 2462
\tcapability: ESS (0x0401)
\tsignal: -80.00 dBm
\tSSID:\x20
\tDS Parameter set: channel 11
BSS 9c:8e:cd:aa:bb:cc(on wlan0)
\tfreq: 5220
\tcapability: ESS Privacy (0x0411)
\tsignal: -70.00 dBm
\tSSID: Alpha-5G
\tHT operation:
\t\t * primary channel: 44
\t\t * secondary channel offset: above
\tVHT operation:
\t\t * channel width: 1 (80 MHz)
\t\t * center freq segment 1: 42
\tRSN:\t * Version: 1
"""

PING_OK = """PING 192.168.10.1 (192.168.10.1) 56(84) bytes of data.
64 bytes from 192.168.10.1: icmp_seq=1 ttl=64 time=1.23 ms
64 bytes from 192.168.10.1: icmp_seq=2 ttl=64 time=2.35 ms
64 bytes from 192.168.10.1: icmp_seq=3 ttl=64 time=1.10 ms

--- 192.168.10.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 1.102/1.560/2.345/0.412 ms
"""

PING_LOSS = """PING 10.0.0.9 (10.0.0.9) 56(84) bytes of data.
64 bytes from 10.0.0.9: icmp_seq=1 ttl=64 time=40.1 ms

--- 10.0.0.9 ping statistics ---
5 packets transmitted, 1 received, 80% packet loss, time 4090ms
rtt min/avg/max/mdev = 40.100/40.100/40.100/0.000 ms
"""

PING_DEAD = """PING 10.0.0.9 (10.0.0.9) 56(84) bytes of data.

--- 10.0.0.9 ping statistics ---
3 packets transmitted, 0 received, +2 errors, 100% packet loss, time 2050ms
"""


class FreqChannel(unittest.TestCase):
    def test_2_4_ghz(self):
        self.assertEqual(P.freq_to_channel(2412), 1)
        self.assertEqual(P.freq_to_channel(2437), 6)
        self.assertEqual(P.freq_to_channel(2472), 13)
        self.assertEqual(P.freq_to_channel(2484), 14)

    def test_5_and_6_ghz(self):
        self.assertEqual(P.freq_to_channel(5180), 36)
        self.assertEqual(P.freq_to_channel(5220), 44)
        self.assertEqual(P.freq_to_channel(5745), 149)
        self.assertEqual(P.freq_to_channel(5955), 1)

    def test_unknown(self):
        self.assertIsNone(P.freq_to_channel(None))
        self.assertIsNone(P.freq_to_channel("abc"))
        self.assertIsNone(P.freq_to_channel(900))
        self.assertEqual(P.band_of(2437), "2.4")
        self.assertEqual(P.band_of(5220), "5")
        self.assertIsNone(P.band_of(None))


class IwLink(unittest.TestCase):
    def test_connected_2_4(self):
        r = P.parse_iw_link(IW_LINK_CONNECTED)
        self.assertTrue(r["connected"])
        self.assertEqual(r["bssid"], "9c:8e:cd:12:34:56")
        self.assertEqual(r["ssid"], "Alpha-Prod")
        self.assertEqual(r["freq_mhz"], 2437)
        self.assertEqual(r["channel"], 6)
        self.assertEqual(r["band"], "2.4")
        self.assertEqual(r["signal_dbm"], -61.0)
        self.assertEqual(r["rx_bitrate_mbps"], 65.0)
        self.assertEqual(r["tx_bitrate_mbps"], 72.2)
        self.assertEqual(r["tx_extra"], {"mcs": 7, "short_gi": True})

    def test_connected_5ghz_vht(self):
        r = P.parse_iw_link(IW_LINK_5GHZ)
        self.assertEqual(r["channel"], 44)
        self.assertEqual(r["band"], "5")
        self.assertEqual(r["tx_extra"], {"mcs": 9, "nss": 1, "width_mhz": 80, "short_gi": True})

    def test_not_connected_and_empty(self):
        self.assertEqual(P.parse_iw_link(IW_LINK_NOT_CONNECTED), {"connected": False})
        self.assertEqual(P.parse_iw_link(""), {"connected": False})
        self.assertEqual(P.parse_iw_link(None), {"connected": False})

    def test_partial_output_keeps_none(self):
        r = P.parse_iw_link("Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n\tSSID: X\n")
        self.assertTrue(r["connected"])
        self.assertIsNone(r["freq_mhz"])
        self.assertIsNone(r["signal_dbm"])
        self.assertIsNone(r["channel"])


class IwScan(unittest.TestCase):
    def test_networks_sorted_by_signal(self):
        r = P.parse_iw_scan(IW_SCAN, own_bssid="9C:8E:CD:12:34:56")
        bssids = [n["bssid"] for n in r["networks"]]
        self.assertEqual(bssids[0], "34:56:78:9a:bc:de", "le plus fort d'abord")
        self.assertEqual(len(bssids), 4)

    def test_channel_width_security_hidden(self):
        r = P.parse_iw_scan(IW_SCAN, own_bssid="9c:8e:cd:12:34:56")
        by = {n["bssid"]: n for n in r["networks"]}
        ours = by["9c:8e:cd:12:34:56"]
        self.assertTrue(ours["is_ours"])
        self.assertEqual(ours["channel"], 6)
        self.assertEqual(ours["width_mhz"], 20)
        self.assertEqual(ours["security"], "WPA2")
        self.assertEqual(ours["last_seen_ms"], 120)
        voisin = by["34:56:78:9a:bc:de"]
        self.assertEqual(voisin["width_mhz"], 40, "secondary channel offset: above -> 40 MHz")
        hidden = by["11:22:33:44:55:66"]
        self.assertTrue(hidden["hidden"])
        self.assertIsNone(hidden["ssid"])
        self.assertEqual(hidden["security"], "open")
        self.assertEqual(hidden["channel"], 11)
        five = by["9c:8e:cd:aa:bb:cc"]
        self.assertEqual(five["channel"], 44)
        self.assertEqual(five["width_mhz"], 80)
        self.assertEqual(five["band"], "5")

    def test_summary_co_channel(self):
        r = P.parse_iw_scan(IW_SCAN, own_bssid="9c:8e:cd:12:34:56")
        s = r["summary"]
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["hidden"], 1)
        self.assertEqual(s["by_band"], {"2.4": 3, "5": 1})
        self.assertEqual(s["by_channel"], {"2.4/6": 2, "2.4/11": 1, "5/44": 1})
        self.assertEqual(s["our_channel"], "2.4/6")
        self.assertEqual(s["co_channel_count"], 1)
        self.assertEqual(s["strongest_co_channel"]["bssid"], "34:56:78:9a:bc:de")
        self.assertEqual(s["strongest_co_channel"]["signal_dbm"], -48.0)

    def test_summary_without_own_bssid(self):
        s = P.parse_iw_scan(IW_SCAN)["summary"]
        self.assertNotIn("our_channel", s)
        self.assertEqual(s["total"], 4)

    def test_hidden_ssid_variants(self):
        # Cas réel qui a révélé un bug : "SSID: " suivi de RIEN faisait capturer
        # la ligne suivante comme nom de réseau (`\s*` avalait le saut de ligne).
        text = "BSS aa:aa:aa:aa:aa:aa(on wlan0)\n\tfreq: 2412\n\tSSID: \n\tDS Parameter set: channel 1\n" \
               "BSS bb:bb:bb:bb:bb:bb(on wlan0)\n\tfreq: 2412\n\tSSID: \\x00\\x00\\x00\n"
        r = P.parse_iw_scan(text)
        self.assertTrue(all(n["hidden"] for n in r["networks"]))
        self.assertTrue(all(n["ssid"] is None for n in r["networks"]))
        self.assertEqual(r["networks"][0]["channel"], 1)

    def test_empty(self):
        r = P.parse_iw_scan("")
        self.assertEqual(r["networks"], [])
        self.assertEqual(r["summary"]["total"], 0)


class Ping(unittest.TestCase):
    def test_ok(self):
        r = P.parse_ping(PING_OK)
        self.assertTrue(r["ok"])
        self.assertEqual((r["sent"], r["received"], r["loss_pct"]), (3, 3, 0.0))
        self.assertEqual(r["rtt_avg_ms"], 1.56)
        self.assertEqual(r["rtt_max_ms"], 2.345)
        self.assertEqual(r["rtt_mdev_ms"], 0.412)

    def test_loss(self):
        r = P.parse_ping(PING_LOSS)
        self.assertTrue(r["ok"], "1 réponse sur 5 : joignable, mais dégradé")
        self.assertEqual(r["loss_pct"], 80.0)

    def test_dead(self):
        r = P.parse_ping(PING_DEAD)
        self.assertFalse(r["ok"])
        self.assertEqual((r["sent"], r["received"], r["loss_pct"]), (3, 0, 100.0))
        self.assertIsNone(r["rtt_avg_ms"])

    def test_garbage(self):
        r = P.parse_ping("ping: unknown host foo")
        self.assertFalse(r["ok"])
        self.assertIsNone(r["sent"])


class Iperf3(unittest.TestCase):
    def test_ok(self):
        r = P.parse_iperf3_json('{"end":{"sum_sent":{"bits_per_second":52000000,"retransmits":3},"sum_received":{"bits_per_second":50500000}}}')
        self.assertEqual(r, {"ok": True, "sent_mbps": 52.0, "received_mbps": 50.5, "retransmits": 3})

    def test_error_and_invalid(self):
        self.assertEqual(P.parse_iperf3_json('{"error":"unable to connect to server: Connection refused"}')["ok"], False)
        self.assertFalse(P.parse_iperf3_json("not json")["ok"])
        self.assertFalse(P.parse_iperf3_json("[]")["ok"])
        self.assertFalse(P.parse_iperf3_json('{"end":{}}')["ok"])


class SysFiles(unittest.TestCase):
    def test_proc(self):
        self.assertEqual(P.parse_loadavg("0.52 0.31 0.12 1/98 4321"), {"load1": 0.52, "load5": 0.31, "load15": 0.12})
        self.assertEqual(P.parse_uptime("12345.67 23456.78"), {"uptime_s": 12345})
        self.assertEqual(P.parse_thermal("48312\n"), {"cpu_temp_c": 48.3})
        self.assertEqual(P.parse_meminfo("MemTotal:  443000 kB\nMemFree: 1 kB\nMemAvailable: 300000 kB\n"),
                         {"mem_total_kb": 443000, "mem_available_kb": 300000})
        self.assertEqual(P.parse_loadavg(""), {})
        self.assertEqual(P.parse_thermal("x"), {})


if __name__ == "__main__":
    unittest.main()
