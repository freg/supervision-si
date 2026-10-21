# -*- coding: utf-8 -*-
"""#801 : sondes radio du Raspberry -- wifi-monitor (radiotap, 802.11, balises, canaux, constats) et rf-spectrum
(sortie hackrf_sweep, bruit de fond, occupation par canal, garde-fou d'émission)."""
import importlib.util
import json
import os
import struct
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def charger(nom, dossier, fichier):
    spec = importlib.util.spec_from_file_location(nom, os.path.join(HERE, "..", "plugins", dossier, fichier))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


wm = charger("wifi_monitor", "wifi-monitor", "wifi_monitor.py")
rf = charger("rf_spectrum", "rf-spectrum", "rf_spectrum.py")
BSSID, CLIENT = bytes.fromhex("020000000001"), bytes.fromhex("020000000099")


def rt(signal=-50, freq=2437, rate=12, flags=0):
    corps = struct.pack("<BB", flags, rate) + struct.pack("<HH", freq, 0x00a0) + struct.pack("<b", signal)
    return struct.pack("<BBHI", 0, 0, 8 + len(corps), (1 << 1) | (1 << 2) | (1 << 3) | (1 << 5)) + corps


def balise(ssid=b"Campus", canal=6, bssid=BSSID, **kw):
    ies = b"\x00" + bytes([len(ssid)]) + ssid + b"\x03\x01" + bytes([canal]) + b"\x0b\x05" + struct.pack("<HBH", 12, 128, 0)
    return rt(**kw) + b"\x80\x00\x00\x00" + b"\xff" * 6 + bssid + bssid + b"\x00\x00" + b"\x00" * 12 + ies


def donnees(retry=False, **kw):
    return rt(**kw) + bytes([0x08, 0x01 | (0x08 if retry else 0)]) + b"\x00\x00" + BSSID + CLIENT + b"\xff" * 6 + b"\x00\x00" + b"x" * 100


def deauth(**kw):
    return rt(**kw) + b"\xc0\x00\x00\x00" + CLIENT + BSSID + BSSID + b"\x00\x00\x07\x00"


class Radiotap(unittest.TestCase):
    def test_entete_et_trames(self):
        lg, r = wm.radiotap(balise())
        self.assertEqual((lg, r["signal"], r["freq"], r["rate_mbps"]), (15, -50, 2437, 6.0))
        b = wm.trame(balise())
        self.assertEqual((b["type"], b["sous"], b["bssid"]), ("gestion", 8, "02:00:00:00:00:01"))
        self.assertEqual(b["ie"], {"ssid": "Campus", "canal": 6, "stations": 12, "util_pct": 50.2})
        d = wm.trame(donnees(retry=True))
        self.assertEqual((d["type"], d["retry"], d["bssid"], d["client"]), ("donnees", True, "02:00:00:00:00:01", "02:00:00:00:00:99"))
        self.assertIsNone(wm.trame(balise(flags=0x40)))           # FCS faux écarté
        self.assertIsNotNone(wm.trame(balise(flags=0x10) + b"\x00" * 4))
        self.assertIsNone(wm.trame(b"\x00\x00\x08\x00"))
        self.assertEqual(wm.radiotap(b"\x01" * 10), (None, {}))
        self.assertEqual((wm.canal_freq(2412), wm.canal_freq(5180), wm.freq_canal(13), wm.freq_canal(100)), (1, 36, 2472, 5500))
        self.assertAlmostEqual(wm.temps_antenne({"lg": 150, "rate": 6.0}), 20e-6 + 1200 / 6e6)

    def test_canal_bornes_constats(self):
        k, b = wm.Canal(6), wm.Bornes()
        for p in [balise()] * 5 + [balise(canal=1, bssid=bytes.fromhex("020000000002"), signal=-80)] + [donnees(retry=i % 2 == 0) for i in range(60)] + [deauth()] * 12:
            d = wm.trame(p)
            k.ajouter(d)
            b.ajouter(d, 6)
        k.sejour = 0.5
        v = k.vue()
        self.assertEqual((v["trames"], v["deauth"], v["retry_pct"], v["signal_max"]), (78, 12, 38.5, -50))
        bs = {x["bssid"]: x for x in b.vue()}
        self.assertEqual(bs["02:00:00:00:00:01"]["clients"], 1)
        self.assertEqual(bs["02:00:00:00:00:01"]["stations_borne"], 12)
        self.assertEqual(bs["02:00:00:00:00:02"]["canal"], 1)            # entendue sur 6, canal réel 1
        self.assertIsNone(bs["02:00:00:00:00:02"]["signal_max"])         # signal d'un canal voisin non retenu
        v["occupation_pct"] = 92.0
        cs = {c["code"]: c for c in wm.constats([v], b.vue(), {"ssid": ["Campus"], "bssid_connus": ["02:00:00:00:00:01"]}, "alfa0")}
        self.assertEqual(cs["monitor-sature:6"]["severity"], "critical")
        self.assertIn("monitor-retry:6", cs)
        self.assertEqual(cs["monitor-deauth:6"]["severity"], "warning")
        self.assertNotIn("monitor-inconnu:02:00:00:00:00:01", cs)
        cs = wm.constats([], [{"bssid": "02:00:00:00:00:66", "ssid": "Campus", "canal": 11, "signal_max": -40}], {"ssid": ["Campus"], "bssid_connus": ["02:00:00:00:00:01"]}, "x")
        self.assertEqual(cs[0]["code"], "monitor-inconnu:02:00:00:00:00:66")

    def test_collecte_simulee(self):
        appels = []

        def run(args, timeout=10):
            appels.append(args)
            if args[:2] == ["iw", "dev"] and args[-1] == "info":
                return 0, "Interface alfa0\n\ttype managed", ""
            return 0, "", ""
        orig = wm.choisir_iface
        wm.choisir_iface = lambda d: "alfa0"
        try:
            r = wm.collecter(config="/nonexistent", run=run, ecoute=lambda i, s, c, run: ([dict(wm.Canal(1).vue(), occupation_pct=75.0)], []))
        finally:
            wm.choisir_iface = orig
        self.assertIn(["iw", "dev", "alfa0", "set", "type", "monitor"], appels)
        wm.choisir_iface = lambda d: "alfa0"
        try:
            def ecoute_refus(i, s, c, run):
                ecoute_refus.refus = ["1 : command failed: Device or resource busy (-16)"]
                return [], []
            r2 = wm.collecter(config="/nonexistent", run=run, ecoute=ecoute_refus)
        finally:
            wm.choisir_iface = orig
        self.assertEqual(r2["alerts"][-1]["code"], "monitor-canaux")                # cause du relevé vide remontée
        self.assertIn("busy", r2["alerts"][-1]["message"])
        self.assertEqual(r["alerts"][0]["code"], "monitor-sature:1")
        out = "Survey data from alfa0\n\tfrequency:\t\t\t2437 MHz [in use]\n\tchannel active time:\t\t1000 ms\n\tchannel busy time:\t\t400 ms\n"
        self.assertEqual(wm.survey("alfa0", 2437, run=lambda a, timeout=10: (0, out, "")), (1000, 400))
        self.assertIsNone(wm.survey("alfa0", 2412, run=lambda a, timeout=10: (0, out, "")))
        if not os.path.exists("/sys/class/net/alfa0"):
            self.assertEqual(wm.collecter(iface="alfa0", config="/nonexistent")["alerts"][0]["code"], "monitor-absente")


SWEEP = "\n".join(
    ["2026-10-21, 10:00:00.1, %d, %d, 500000.00, 20, %s" % (f * 1000000, (f + 5) * 1000000, ", ".join(
        ("-40.0" if 2432 <= f + i * 0.5 < 2442 else "-90.0") for i in range(10))) for f in range(2400, 2500, 5)] * 3)


class Spectre(unittest.TestCase):
    def test_analyse(self):
        m = rf.lire_balayage(SWEEP + "\nligne invalide\n2026, x, a, b, c, d, nan")
        self.assertEqual(len(m), 20 * 10 * 3)
        bandes, canaux, spectre = rf.analyser(m, ["2.4"])
        self.assertEqual(bandes[0]["bruit_db"], -90.0)
        c = {x["canal"]: x for x in canaux}
        self.assertEqual(c[6]["occupation_pct"], 50.0)       # 2437 ± 10 MHz : la moitié des cases à -40
        self.assertEqual(c[1]["occupation_pct"], 0.0)
        self.assertEqual(c[6]["max_db"], -40.0)
        self.assertEqual(spectre[0][0], 2400)
        self.assertEqual([a["code"] for a in rf.constats([dict(c[6], occupation_pct=90.0)])], ["spectre-occupe:6"])

    def test_bruit_seul_peu_occupe(self):   # #805 : premier relevé réel, ~35 % partout avec le 10e centile
        import random
        rnd = random.Random(4)
        lignes = []
        for _ in range(20):
            for f in range(2400, 2500, 5):
                v = ", ".join("%.1f" % (-75 + 10 * __import__("math").log10(rnd.expovariate(1.0) + 1e-9)) for _ in range(10))
                lignes.append("d, t, %d, %d, 500000.00, 20, %s" % (f * 1000000, (f + 5) * 1000000, v))
        _b, canaux, _s = rf.analyser(rf.lire_balayage("\n".join(lignes)), ["2.4"])
        self.assertTrue(all(c["occupation_pct"] < 3 for c in canaux), [c["occupation_pct"] for c in canaux])

    def test_collecte_et_garde_fou(self):
        def run(args, timeout=60):
            if args[0] == "hackrf_info":
                return 0, "Found HackRF\nSerial number: 0000000000000000a\nFirmware Version: 2024.02.1 (API:1.08)\n", ""
            self.assertEqual(args[0], "hackrf_sweep")
            self.assertNotIn("-a", args)
            return 0, SWEEP, ""
        r = rf.collecter(bandes="2.4", run=run)
        self.assertEqual(r["hackrf"]["micrologiciel"], "2024.02.1 (API:1.08)")
        self.assertTrue(r["canaux"])
        r = rf.collecter(run=lambda a, timeout=60: (1, "", "hackrf_open() failed: HACKRF_ERROR_NOT_FOUND (-5)"))
        self.assertFalse(r["present"])
        self.assertIn("NOT_FOUND", r["alerts"][0]["message"])
        with self.assertRaises(AssertionError):
            rf.lancer(["hackrf_transfer", "-t", "x"])

    def test_manifestes(self):
        for d in ("wifi-monitor", "rf-spectrum"):
            with open(os.path.join(HERE, "..", "plugins", d, "manifest.json")) as fh:
                m = json.load(fh)
            self.assertEqual((m["id"], m["enabled"], m["privileged"]), (d, False, True))
            self.assertLess(m["interval_seconds"] - m["timeout_seconds"], m["interval_seconds"])


if __name__ == "__main__":
    unittest.main()
