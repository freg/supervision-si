# -*- coding: utf-8 -*-
"""si-onglets (#848) : lecture de /proc simulé, onglets relevés (ordre, dossier, commande, titre), argv du terminal."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import si_onglets as O  # noqa: E402

M = "/home/alice"
P = lambda pid, ppid, comm, cmd, cwd=M: {"pid": pid, "ppid": ppid, "comm": comm, "cmd": cmd, "cwd": cwd}
PROCS = {p["pid"]: p for p in [
    P(100, 1, "gnome-terminal-", ["/usr/libexec/gnome-terminal-server"]),
    P(110, 100, "bash", ["bash"], M + "/SRC/data2"),
    P(111, 110, "ssh", ["ssh", "-A", "super"]),
    P(120, 100, "bash", ["bash"], M),
    P(130, 100, "bash", ["bash"], M + "/Téléchargements"),
    P(131, 130, "htop", ["htop", "-d", "10"]),
    P(140, 100, "bash", ["bash"], "/etc"),
    P(141, 140, "sh", ["/bin/sh", M + "/.local/bin/si-onglets", "--capturer"]),
    P(200, 1, "bash", ["bash"], "/tmp"),                    # shell hors terminal : ignoré
]}


class Onglets(unittest.TestCase):
    def test_releve(self):
        o = O.onglets_de(PROCS, M)
        self.assertEqual(o, [{"titre": "super", "dossier": "~/SRC/data2", "commande": "ssh -A super"},
                             {"titre": "alice", "dossier": "~", "commande": ""},
                             {"titre": "htop", "dossier": "~/Téléchargements", "commande": "htop -d 10"},
                             {"titre": "etc", "dossier": "/etc", "commande": ""}])

    def test_terminal(self):
        a = O.commande_terminal({"plein_ecran": True, "onglets": O.onglets_de(PROCS, M)}, M)
        self.assertEqual(a[:5], ["gnome-terminal", "--window", "--full-screen", "--working-directory", M + "/SRC/data2"])
        self.assertEqual(a[5:7], ["--command", "bash -c 'ssh -A super; exec bash'"])
        self.assertEqual(a.count("--tab"), 3)
        self.assertIn(M + "/Téléchargements", a)
        self.assertEqual(O.commande_terminal({"plein_ecran": False, "onglets": []}, M), ["gnome-terminal", "--window", "--maximize", "--working-directory", M])
        q = O.commande_terminal({"onglets": [{"dossier": "~", "commande": "echo 'a b'"}]}, M)
        self.assertEqual(q[-1], "bash -c 'echo '\"'\"'a b'\"'\"'; exec bash'")

    def test_proc_reel(self):
        moi = O.processus_lus()
        self.assertEqual(moi[os.getpid()]["ppid"], os.getppid())
        d = tempfile.mkdtemp()
        os.environ["SI_ONGLETS_CONF"] = os.path.join(d, "o.json")
        O.CONF = os.environ["SI_ONGLETS_CONF"]
        O.ecrire({"onglets": [{"titre": "x", "dossier": "~", "commande": ""}]})
        O.ecrire(dict(O.lire(), plein_ecran=False))
        self.assertTrue(os.path.exists(O.CONF + ".avant"))
        self.assertEqual((O.lire()["plein_ecran"], O.lire()["attente_s"]), (False, 5))


if __name__ == "__main__":
    unittest.main()
