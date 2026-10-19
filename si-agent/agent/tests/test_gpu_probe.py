# -*- coding: utf-8 -*-
"""#782 : sonde gpu -- inventaire lspci, nvidia-smi, capteurs sysfs, constats."""
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("gpu_probe", os.path.join(HERE, "..", "plugins", "gpu", "gpu_probe.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

LSPCI = """0000:03:00.0 VGA compatible controller [0300]: ASPEED Technology, Inc. ASPEED Graphics Family [1a03:2000] (rev 41)
0000:65:00.0 VGA compatible controller [0300]: NVIDIA Corporation GA102GL [RTX A4500] [10de:2232] (rev a1)
0000:65:00.1 Audio device [0403]: NVIDIA Corporation GA102 High Definition Audio Controller [10de:1aef] (rev a1)
0000:b3:00.0 VGA compatible controller [0300]: Intel Corporation Device [8086:e211]
0000:17:00.0 VGA compatible controller [0300]: NVIDIA Corporation GM107GL [Quadro K2200] [10de:13ba] (rev a2)
"""
NV = "0, NVIDIA RTX A4500, GPU-aaa, 00000000:65:00.0, 570.86, 20470, 19800, 87, 88, 180.5, 200.00, 65, P2\nmal, formé\n"
APPS = "GPU-aaa, 4242, /usr/local/bin/ollama, 18000\n"


class Probe(unittest.TestCase):
    def test_parsers(self):
        cards = G.parse_lspci(LSPCI)
        self.assertEqual([c["slot"] for c in cards], ["65:00.0", "b3:00.0", "17:00.0"])   # ASPEED et audio ignorés
        self.assertEqual(cards[1]["vendor"], "Intel")
        nv = G.parse_nvidia(NV)
        self.assertEqual(len(nv), 1)
        self.assertEqual((nv[0]["slot"], nv[0]["vram_pct"], nv[0]["temp_c"], nv[0]["power_w"]), ("65:00.0", 96.7, 88.0, 180.5))
        self.assertIsNone(G.parse_nvidia("0, X, u, 00000000:01:00.0, 1, [N/A], [N/A], [N/A], 40, [N/A], [N/A], [N/A], P8")[0]["vram_pct"])
        self.assertEqual(G.parse_nvidia_apps(APPS)["GPU-aaa"][0], {"pid": 4242, "name": "ollama", "vram": 18000 * 1048576})

    def test_collect(self):
        root = tempfile.mkdtemp()
        intel = os.path.join(root, "bus", "pci", "devices", "0000:b3:00.0")
        os.makedirs(os.path.join(intel, "hwmon", "hwmon3"))
        os.makedirs(os.path.join(root, "drivers", "xe"))
        os.symlink(os.path.join(root, "drivers", "xe"), os.path.join(intel, "driver"))
        with open(os.path.join(intel, "hwmon", "hwmon3", "temp1_input"), "w") as fh:
            fh.write("52000\n")
        with open(os.path.join(intel, "hwmon", "hwmon3", "power1_input"), "w") as fh:
            fh.write("35500000\n")
        os.makedirs(os.path.join(root, "bus", "pci", "devices", "0000:17:00.0"))   # K2200 sans pilote

        def run(args):
            if args[0] == "lspci":
                return LSPCI
            return APPS if "--query-compute-apps" in args[1] else NV
        out = G.collect(run=run, root=root, which=lambda x: "/usr/bin/" + x)
        by = {g["slot"]: g for g in out["gpus"]}
        self.assertEqual(by["65:00.0"]["processes"][0]["name"], "ollama")
        self.assertEqual((by["b3:00.0"]["driver"], by["b3:00.0"]["temp_c"], by["b3:00.0"]["power_w"]), ("xe", 52.0, 35.5))
        codes = sorted(a["code"].split("@")[0] for a in out["alerts"])
        self.assertEqual(codes, ["gpu-hot", "gpu-no-driver", "gpu-vram-full"])
        self.assertEqual(next(a for a in out["alerts"] if a["code"].startswith("gpu-hot"))["severity"], "critical")
        quiet = G.collect(run=run, root=root, which=lambda x: "/usr/bin/" + x, ignore=("10de:13ba",))
        self.assertNotIn("gpu-no-driver", [a["code"].split("@")[0] for a in quiet["alerts"]])

    def test_nvidia_smi_en_echec(self):
        def run(args):
            if args[0] == "lspci":
                return LSPCI
            raise RuntimeError("NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver")
        out = G.collect(run=run, root=tempfile.mkdtemp(), which=lambda x: "/usr/bin/" + x)
        self.assertIn("nvidia-smi", [a["code"] for a in out["alerts"]])
        none = G.collect(run=lambda a: "", root=tempfile.mkdtemp(), which=lambda x: None)
        self.assertEqual((none["gpus"], none["alerts"]), ([], []))
        with open(os.path.join(HERE, "..", "plugins", "gpu", "manifest.json")) as fh:
            m = json.load(fh)
        self.assertFalse(m["enabled"]); self.assertFalse(m["privileged"])


if __name__ == "__main__":
    unittest.main()
