# -*- coding: utf-8 -*-
"""Tests #714 : script pve-pull-backup.sh (ssh simulé) et sonde pulled-backups."""
import gzip
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pulled_backups as pb  # noqa: E402

SCRIPT = os.path.join(HERE, "..", "..", "..", "tools", "pve-pull-backup.sh")
FAKE_ZFS = '#!/bin/bash\nS="$FAKE_STATE"; touch "$S/vols" "$S/ds" "$S/snaps"\ncase "$1" in\n  list)\n    if [[ "$*" == *"-t snapshot"* ]]; then t="${@: -1}"; grep "^$t@" "$S/snaps" || true; exit 0; fi\n    if [[ "$*" == *"volume,filesystem"* ]]; then cat "$S/vols" "$S/ds"; exit 0; fi\n    t="${@: -1}"; grep -qx "$t" "$S/vols" "$S/ds" && echo "$t" || exit 1 ;;\n  create) echo "${@: -1}" >> "$S/ds" ;;\n  get) t="${@: -1}"; if [[ "$*" == *mountpoint* ]]; then mkdir -p "$S/mnt/$t"; echo "$S/mnt/$t"; else echo 1048576; fi ;;\n  snapshot) shift; for x in "$@"; do echo "$x" >> "$S/snaps"; done ;;\n  send) echo "SEND $*" >> "$S/log"; echo "${@: -1}" ;;\n  recv) d="${@: -1}"; read -r src; grep -qx "$d" "$S/ds" || echo "$d" >> "$S/ds"; echo "$d@${src##*@}" >> "$S/snaps"; echo "RECV $d" >> "$S/log" ;;\n  destroy) grep -vx "$2" "$S/snaps" > "$S/snaps.n"; mv "$S/snaps.n" "$S/snaps" ;;\nesac\n'
FAKE_ZPOOL = '#!/bin/bash\nS="$FAKE_STATE"\ncase "$1" in list) [ -f "$S/imported" ] ;; import) [ -f "$S/disk" ] && touch "$S/imported" ;; export) rm -f "$S/imported" ;; esac\n'


class Script(unittest.TestCase):
    def run_script(self, ssh_body, *args):
        d = tempfile.mkdtemp()
        fake = os.path.join(d, "bin"); os.makedirs(fake)
        with open(os.path.join(fake, "ssh"), "w") as fh:
            fh.write("#!/bin/bash\n" + ssh_body)
        os.chmod(os.path.join(fake, "ssh"), 0o755)
        env = dict(os.environ, PATH=fake + ":" + os.environ["PATH"], PULL_DEST=os.path.join(d, "dumps"), PULL_KEY="/nonexistent", PULL_NAME="pve-3")
        p = subprocess.run(["bash", SCRIPT] + list(args), env=env, capture_output=True, text=True)
        return p, os.path.join(d, "dumps")

    def test_succes_retention_et_echec(self):
        body = 'echo "INFO: sending archive to stdout" >&2; echo "contenu" | gzip -c\n'
        for _ in range(3):
            p, dest = self.run_script(body, "203.0.113.21", "113", "stop", "2")
            self.assertEqual(p.returncode, 0, p.stderr)
        files = sorted(f for f in os.listdir(os.path.join(dest, "pve-3")) if f.endswith(".tar.gz"))
        self.assertLessEqual(len(files), 2)
        rows = [json.loads(l) for l in open(os.path.join(dest, "pulls.jsonl"))]
        self.assertTrue(rows[-1]["ok"]); self.assertEqual((rows[-1]["host"], rows[-1]["vmid"], len(rows[-1]["sha256"])), ("pve-3", 113, 64))
        p, dest = self.run_script('echo "ERROR: CT 999 introuvable" >&2; exit 2\n', "203.0.113.21", "999")
        self.assertEqual(p.returncode, 1)
        row = json.loads(open(os.path.join(dest, "pulls.jsonl")).readlines()[-1])
        self.assertEqual((row["ok"], row["file"]), (False, "")); self.assertIn("introuvable", row["error"])
        p, dest = self.run_script('echo "pas du gzip"\n', "203.0.113.21", "113")
        self.assertEqual(json.loads(open(os.path.join(dest, "pulls.jsonl")).readlines()[-1])["error"], "archive gzip invalide")
        self.assertEqual(self.run_script(body, "h; rm -rf /", "1")[0].returncode, 2)                    # arguments refusés
        self.assertEqual(self.run_script(body, "h", "1", "fast")[0].returncode, 2)

    def test_campagne(self):
        """#717 : pve-pull-batch.sh -- en série, échec non bloquant, notify_ok, verrou, liste commentée."""
        d = tempfile.mkdtemp()
        fake = os.path.join(d, "bin"); os.makedirs(fake)
        with open(os.path.join(fake, "ssh"), "w") as fh:
            fh.write('#!/bin/bash\ncase "$*" in *"vzdump 999"*) echo "ERROR: CT 999 introuvable" >&2; exit 2;; esac\nread -t 1 x && echo "ssh a lu la liste" >&2\necho contenu | gzip -c\n')
        os.chmod(os.path.join(fake, "ssh"), 0o755)
        lst = os.path.join(d, "campagne.list")
        with open(lst, "w") as fh:
            fh.write("# CT arrêtés d'abord\n203.0.113.21 101 stop 1 pve-1\n\n203.0.113.21 999 stop 1 pve-1\n203.0.113.22 113\n")
        env = dict(os.environ, PATH=fake + ":" + os.environ["PATH"], PULL_DEST=os.path.join(d, "dumps"), PULL_KEY="/nonexistent", PULL_MIN_FREE_GB="0")
        p = subprocess.run(["bash", os.path.join(os.path.dirname(SCRIPT), "pve-pull-batch.sh"), lst], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)                        # un échec sur trois
        self.assertIn("2 réussie(s), 1 échec(s), 0 non faite(s)", p.stdout)
        rows = [json.loads(l) for l in open(os.path.join(d, "dumps", "pulls.jsonl"))]
        self.assertEqual([(r["host"], r["vmid"], r["ok"], r["notify_ok"]) for r in rows],
                         [("pve-1", 101, True, True), ("pve-1", 999, False, True), ("203.0.113.22", 113, True, True)])
        log = open([os.path.join(d, "dumps", f) for f in os.listdir(os.path.join(d, "dumps")) if f.startswith("campagne-")][0]).read()
        self.assertNotIn("ssh a lu la liste", log)                                      # ssh ne vole pas la liste (stdin)
        env["PULL_MIN_FREE_GB"] = "999999999"
        p = subprocess.run(["bash", os.path.join(os.path.dirname(SCRIPT), "pve-pull-batch.sh"), lst], env=env, capture_output=True, text=True)
        self.assertIn("ARRÊT", p.stdout); self.assertIn("3 non faite(s)", p.stdout)

    def test_secours_zfs(self):
        """#725 : zfs-secours.sh -- copie complète puis différentielle, instantanés communs, journal, pool exporté."""
        d = tempfile.mkdtemp(); fake = os.path.join(d, "bin"); st = os.path.join(d, "state"); os.makedirs(fake); os.makedirs(st)
        for name, body in (("zfs", FAKE_ZFS), ("zpool", FAKE_ZPOOL), ("qm", "#!/bin/bash\nexit 1\n")):
            with open(os.path.join(fake, name), "w") as fh:
                fh.write(body)
            os.chmod(os.path.join(fake, name), 0o755)
        with open(os.path.join(st, "vols"), "w") as fh:
            fh.write("rpool/data/vm-110-disk-0\nrpool/data/vm-110-disk-1\nrpool/data/vm-111-disk-0\n")
        env = dict(os.environ, PATH=fake + ":" + os.environ["PATH"], FAKE_STATE=st, SECOURS_JOURNAL=os.path.join(d, "secours.jsonl"), SECOURS_KEEP_SRC="1")
        script = os.path.join(os.path.dirname(SCRIPT), "zfs-secours.sh")
        p = subprocess.run(["bash", script, "secours", "110"], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 2); self.assertIn("brancher le disque", p.stderr)          # disque absent
        open(os.path.join(st, "disk"), "w").close()
        p = subprocess.run(["bash", script, "secours", "110"], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        log = open(os.path.join(st, "log")).read()
        self.assertNotIn(" -i ", log)                                                              # 1re fois : complète, les 2 disques
        self.assertEqual(log.count("RECV secours/secours/vm-110-disk-"), 2)
        self.assertFalse(os.path.exists(os.path.join(st, "imported")))                           # exporté
        import time; time.sleep(1.1)
        p = subprocess.run(["bash", script, "secours", "110", "111"], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        log = open(os.path.join(st, "log")).read().splitlines()
        self.assertEqual(sum(1 for l in log if l.startswith("SEND send -i @secours-")), 2)       # 2e fois : différentielle pour 110
        self.assertFalse(any("secours/secours/vm-110-disk-0@" in l for l in log if l.startswith("SEND")))   # jamais la copie elle-même
        snaps = open(os.path.join(st, "snaps")).read().split()
        self.assertEqual(sum(1 for x in snaps if x.startswith("rpool/data/vm-110-disk-0@")), 1)  # SECOURS_KEEP_SRC=1
        rows = [json.loads(l) for l in open(os.path.join(d, "secours.jsonl"))]
        self.assertEqual([(r["host"], r["job"], r["ok"], r["max_age_h"]) for r in rows],
                         [("secours-secours", "vm-110", True, 336), ("secours-secours", "vm-110", True, 336), ("secours-secours", "vm-111", True, 336)])
        self.assertEqual(subprocess.run(["bash", script, "bad pool!", "110"], env=env, capture_output=True).returncode, 2)


class Sonde(unittest.TestCase):
    def test_resume(self):
        now = 1_800_000_000
        rows = [{"host": "pve-3", "vmid": 113, "ok": True, "ended": now - 3600, "size": 10, "sha256": "a", "file": "/x/113.tar.gz"},
                {"host": "pve-3", "vmid": 113, "ok": False, "ended": now - 60, "error": "ssh"},
                {"host": "pve-1", "vmid": 108, "ok": True, "ended": now - 10 * 86400, "size": 5, "file": "/x/108.tar.gz"},
                {"host": "pve-1", "vmid": "x"}]
        backups, alerts = pb.summarize(rows, now, 8, exists=lambda p: p.endswith("113.tar.gz"))
        b = {(x["host"], x["vmid"]): x for x in backups}
        self.assertEqual((b[("pve-3", 113)]["ok"], b[("pve-3", 113)]["age_h"], b[("pve-3", 113)]["failures"], b[("pve-3", 113)]["present"]), (False, 1.0, 1, True))
        self.assertEqual(sorted(a["code"] for a in alerts), ["pull-failed:pve-3 / CT 113", "pull-missing:pve-1 / CT 108", "pull-old:pve-1 / CT 108"])   # #716 : un code par sauvegarde
        d = tempfile.mkdtemp(); idx = os.path.join(d, "pulls.jsonl")
        with open(idx, "w") as fh:
            fh.write(json.dumps(rows[0]) + "\nnon json\n")
        self.assertEqual(len(pb.read_index(idx)), 1); self.assertIsNone(pb.read_index(os.path.join(d, "absent")))

    def test_taches(self):
        """#716 : tâche de sauvegarde quelconque (job), délai propre en heures, réussite à notifier."""
        now = 1_800_000_000
        rows = [{"host": "appli", "job": "base+site", "ok": True, "ended": now - 30 * 3600, "size": 9, "file": "/d/a.sql", "max_age_h": 26, "notify_ok": True},
                {"host": "appli", "job": "base+site", "ok": True, "ended": now - 3 * 3600, "size": 9, "file": "/d/a.sql", "max_age_h": 26, "notify_ok": True},
                {"host": "autre", "job": "dump", "ok": True, "ended": now - 30 * 3600, "max_age_h": 26},
                {"host": "pve-3", "vmid": 113, "ok": True, "ended": now - 3600, "file": "/x/113.tar.gz"}]
        backups, alerts = pb.summarize(rows, now, 8, exists=lambda p: True)
        b = {(x["host"], x["job"] or x["vmid"]): x for x in backups}
        self.assertEqual((b[("appli", "base+site")]["age_h"], b[("appli", "base+site")]["notify_ok"], b[("appli", "base+site")]["vmid"]), (3.0, True, None))
        self.assertEqual([a["code"] for a in alerts], ["pull-old:autre / dump"])        # 30 h > 26 h ; le CT garde ses 8 jours
        self.assertIn("30 h", alerts[0]["message"])


if __name__ == "__main__":
    unittest.main()
