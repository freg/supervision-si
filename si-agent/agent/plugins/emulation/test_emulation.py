# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emulation as E  # noqa: E402


class Sonde(unittest.TestCase):
    def test_capacites_et_instances(self):
        cap = E.capacites(which=lambda n: n in ("docker", "qemu-system-arm"), exists=lambda p: p == "/dev/kvm",
                          run=lambda argv, timeout=20: (0, "rpios-lite:armhf\nubuntu:24.04\n"))
        self.assertEqual((cap["kvm"], cap["docker"], cap["qemu_arm"], cap["qemu_aarch64"], cap["images_raspberry"]), (True, True, True, False, ["rpios-lite:armhf"]))
        l = E.instances([{"id": "emu-rpi0w-1", "mode": "conteneur"}, {"id": "emu-x-2", "mode": "systeme", "etat": "demarre"}],
                        [{"Names": "emu-rpi0w-1", "State": "exited", "Status": "Exited (0)"}])
        self.assertEqual([(x["id"], x["etat"]) for x in l], [("emu-rpi0w-1", "arrete"), ("emu-x-2", "arrete")])


if __name__ == "__main__":
    unittest.main()
