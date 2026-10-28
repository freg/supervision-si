# -*- coding: utf-8 -*-
"""Tests #906 : sonde sockets (parse ss Linux, relevé Windows, analyse)."""
import json, os, sys, types, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sockets as sk  # noqa: E402

SS = (
 'tcp   LISTEN 0 128 0.0.0.0:22   0.0.0.0:* users:(("sshd",pid=800,fd=3)) uid:0 ino:1 sk:1\n'
 'tcp   ESTAB  0 0   192.168.0.20:22 192.168.0.5:51234 users:(("sshd",pid=1200,fd=4)) uid:0 ino:2\n'
 'udp   UNCONN 0 0   127.0.0.1:53 0.0.0.0:* users:(("named",pid=900,fd=5)) uid:107 ino:3\n'
 'tcp   LISTEN 0 10  127.0.0.1:3306 0.0.0.0:* users:(("mysqld",pid=1000,fd=6)) uid:109 ino:4\n'
)

class Sockets(unittest.TestCase):
    def test_parse_ss(self):
        r = sk.parse_ss(SS, user_de_uid=lambda u: {"0":"root","107":"bind","109":"mysql"}.get(str(u), str(u)),
                        user_de_pid=lambda pid: {800:"root",1200:"root",900:"bind",1000:"mysql"}.get(pid))
        self.assertEqual(len(r), 4)
        s0 = r[0]
        self.assertEqual((s0["proto"], s0["etat"], s0["local_port"], s0["process"], s0["pid"], s0["user"], s0["ecoute"], s0["expose"]),
                         ("tcp", "LISTEN", 22, "sshd", 800, "root", True, True))
        estab = r[1]
        self.assertEqual((estab["etat"], estab["remote_ip"], estab["remote_port"], estab["ecoute"]), ("ESTAB", "192.168.0.5", 51234, False))
        mysql = r[3]
        self.assertFalse(mysql["expose"])          # 127.0.0.1 : pas exposé
        self.assertEqual(mysql["user"], "mysql")

    def test_user_par_pid(self):
        # ss récent sans uid: (ino/sk/cgroup seulement) -> utilisateur résolu via le PID
        ligne = 'udp UNCONN 0 0 0.0.0.0:111 0.0.0.0:* users:(("rpcbind",pid=2374804,fd=5),("systemd",pid=1,fd=164)) ino:94 sk:3 cgroup:/system.slice/rpcbind.socket\n'
        r = sk.parse_ss(ligne, user_de_pid=lambda pid: "root" if pid == 2374804 else None)
        self.assertEqual((r[0]["process"], r[0]["pid"], r[0]["user"], r[0]["expose"]), ("rpcbind", 2374804, "root", True))

    def test_analyse(self):
        a = sk.analyse(sk.parse_ss(SS, user_de_uid=str))
        self.assertEqual((a["counts"]["total"], a["counts"]["ecoute"], a["counts"]["etablies"], a["counts"]["exposes"], a["counts"]["udp"]), (4, 3, 1, 1, 1))

    def test_windows(self):
        payload = {"sockets": [
            {"proto": "tcp", "etat": "Listen", "local_ip": "0.0.0.0", "local_port": 445, "remote_ip": "0.0.0.0", "remote_port": 0, "pid": 4, "process": "System", "user": "NT AUTHORITY\\SYSTEM"},
            {"proto": "tcp", "etat": "Established", "local_ip": "192.168.0.10", "local_port": 50012, "remote_ip": "20.1.2.3", "remote_port": 443, "pid": 5000, "process": "msedge", "user": "PC\\paul"},
        ]}
        out = sk.collect_windows(runner=lambda *a, **k: types.SimpleNamespace(stdout=("\ufeff"+json.dumps(payload)).encode(), stderr=b"", returncode=0))
        self.assertEqual(out[0]["expose"], True)
        self.assertEqual((out[1]["etat"], out[1]["ecoute"], out[1]["user"]), ("Established", False, "PC\\paul"))
        res = sk.main(runner=lambda *a, **k: types.SimpleNamespace(stdout=("\ufeff"+json.dumps(payload)).encode(), stderr=b"", returncode=0), plateforme="win32")
        self.assertEqual(res["counts"]["total"], 2)

    def test_ss_absent(self):
        res = sk.main(runner=lambda *a, **k: types.SimpleNamespace(stdout=b"", stderr=b"not found", returncode=127), plateforme="linux")
        self.assertEqual(res["alerts"][0]["code"], "sockets-ss")

if __name__ == "__main__":
    unittest.main()
