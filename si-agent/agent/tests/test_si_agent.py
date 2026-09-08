"""Tests de si-agent (livraison #420) -- `cd si-agent/agent && python3 -m unittest`.
Collecteurs sur des contenus /proc réels capturés, risques, moteur de
plugins (signature, exécution réelle de scripts), boucle de l'agent avec
un faux central (client HTTP injecté) et une vraie file SQLite."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from si_agent import agent as agent_mod  # noqa: E402
from si_agent import control, host, plugins, protocol, risks  # noqa: E402
from si_agent.localqueue import LocalQueue  # noqa: E402

PROC = {
    "/etc/os-release": 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nNAME="Debian GNU/Linux"\nVERSION_ID="12"\nID=debian\n',
    "/etc/hostname": "srv-01\n",
    "/proc/uptime": "123456.78 456789.01\n",
    "/proc/sys/kernel/osrelease": "6.1.0-25-amd64\n",
    "/proc/cpuinfo": "processor\t: 0\nmodel name\t: Intel(R) Celeron(R) J4125\nprocessor\t: 1\nmodel name\t: Intel(R) Celeron(R) J4125\n",
    "/proc/stat": "cpu  1000 0 500 8000 200 0 50 0 0 0\ncpu0 500 0 250 4000 100 0 25 0 0 0\n",
    "/proc/loadavg": "0.42 0.31 0.25 1/312 12345\n",
    "/proc/meminfo": "MemTotal:        8000000 kB\nMemFree:          500000 kB\nMemAvailable:    6000000 kB\nBuffers:          100000 kB\nCached:          2000000 kB\nSwapTotal:       2000000 kB\nSwapFree:        1900000 kB\n",
    "/proc/mounts": "sysfs /sys sysfs rw 0 0\nproc /proc proc rw 0 0\n/dev/sda1 / ext4 rw,relatime 0 0\ntmpfs /run tmpfs rw 0 0\n/dev/sdb1 /data xfs rw 0 0\n/dev/sda1 /snap/core/1 squashfs ro 0 0\nnas:/export /mnt/nas nfs rw 0 0\n",
    "/etc/group": "root:x:0:\nsudo:x:27:freg,ops\nadm:x:4:freg\n",
    "/etc/passwd": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1::/usr/sbin:/usr/sbin/nologin\nfreg:x:1000:1000::/home/alice:/bin/bash\nbackdoor:x:0:0::/root:/bin/sh\nsvc:x:1001:1001::/var/svc:/bin/false\n",
}
SS_OUT = """tcp   LISTEN 0      128          0.0.0.0:22        0.0.0.0:*    users:(("sshd",pid=812,fd=3))
tcp   LISTEN 0      511        127.0.0.1:6379      0.0.0.0:*    users:(("redis-server",pid=900,fd=6))
tcp   LISTEN 0      128             [::]:3306         [::]:*    users:(("mariadbd",pid=950,fd=20))
udp   UNCONN 0      0            0.0.0.0:68        0.0.0.0:*    users:(("dhclient",pid=500,fd=6))
"""


class FakeCmd(object):
    def __init__(self, outputs):
        self.outputs, self.calls = outputs, []

    def __call__(self, argv, timeout=15, env=None):
        self.calls.append((list(argv), env))
        key = argv[0]
        if key in self.outputs:
            rc, out = self.outputs[key]
            return host.CmdResult(rc, out, "")
        if key in ("bash", "python3"):  # plugins : exécution réelle
            return host.run_cmd(argv, timeout=timeout, env=env)
        return host.CmdResult(-127, "", "binaire introuvable : %s" % key)


def files(mapping):
    return lambda path: mapping.get(path, "")


class Usage(object):
    def __init__(self, total, used):
        self.total, self.used, self.free = total, used, total - used


class HostTests(unittest.TestCase):
    def test_systeme_cpu_memoire(self):
        s = host.collect_system(files(PROC), exists=lambda p: p == "/var/run/reboot-required")
        self.assertEqual(s["hostname"], "srv-01")
        self.assertEqual(s["os"], "Debian GNU/Linux 12 (bookworm)")
        self.assertEqual(s["cpus"], 2)
        self.assertEqual(s["cpu_model"], "Intel(R) Celeron(R) J4125")
        self.assertEqual(s["uptime_seconds"], 123456.78)
        self.assertTrue(s["reboot_required"])
        self.assertFalse(host.collect_system(files(PROC), exists=lambda p: False)["reboot_required"], "l'existence compte, pas le contenu")
        before = host.parse_proc_stat(PROC["/proc/stat"])
        self.assertEqual(before, (1550, 9750))
        after = (1550 + 300, 9750 + 1000)
        self.assertEqual(host.cpu_percent(before, after), 30.0)
        self.assertIsNone(host.cpu_percent(before, before))
        cpu = host.collect_cpu(files(PROC), sleep=lambda s: None, previous=(1500, 9000))
        self.assertAlmostEqual(cpu["percent"], 100.0 * 50 / 750, places=1)
        self.assertEqual(cpu["load5"], 0.31)
        mem = host.collect_memory(files(PROC))
        self.assertEqual(mem["total_bytes"], 8000000 * 1024)
        self.assertEqual(mem["used_percent"], 25.0)
        self.assertEqual(mem["swap_used_percent"], 5.0)
        old = dict(PROC); old["/proc/meminfo"] = "MemTotal: 1000 kB\nMemFree: 100 kB\nBuffers: 50 kB\nCached: 250 kB\n"
        self.assertEqual(host.collect_memory(files(old))["available_bytes"], 400 * 1024, "noyau ancien sans MemAvailable")

    def test_disques_pseudo_fs_ecartes(self):
        mounts = host.parse_mounts(PROC["/proc/mounts"])
        self.assertEqual([m["mountpoint"] for m in mounts], ["/", "/data", "/mnt/nas"])
        disks = host.collect_disks(files(PROC), usage=lambda mp: Usage(100, 96) if mp == "/" else Usage(1000, 100))
        self.assertEqual(disks[0]["used_percent"], 96.0)
        self.assertEqual(len(disks), 3)
        def failing(mp):
            if mp == "/mnt/nas":
                raise OSError("stale")
            return Usage(10, 1)
        self.assertEqual(len(host.collect_disks(files(PROC), usage=failing)), 2, "un montage en erreur est ignoré")

    def test_services_ports_journaux_comptes(self):
        cmd = FakeCmd({"systemctl": (0, "● nginx.service loaded failed failed A high performance web server\nfoo.timer loaded failed failed Foo\n"),
                       "ss": (0, SS_OUT), "journalctl": (0, "2026-09-07T10:00:00+0200 srv kernel: EXT4-fs error\n-- No entries --\n2026-09-07T10:01:00+0200 srv sshd[1]: error: PAM\n")})
        self.assertEqual(host.collect_failed_services(cmd)["failed"], ["nginx.service", "foo.timer"])
        ports = host.collect_listening_ports(cmd)["ports"]
        self.assertEqual([(p["proto"], p["port"], p["exposed"], p["process"]) for p in ports],
                         [("tcp", 22, True, "sshd"), ("tcp", 6379, False, "redis-server"), ("tcp", 3306, True, "mariadbd"), ("udp", 68, True, "dhclient")])
        logs = host.collect_log_errors(cmd, files(PROC))
        self.assertEqual(logs["source"], "journald")
        self.assertEqual(len(logs["lines"]), 2, "les lignes '-- No entries --' sont écartées")
        nocmd = FakeCmd({})
        self.assertFalse(host.collect_failed_services(nocmd)["available"])
        self.assertFalse(host.collect_listening_ports(nocmd)["available"])
        syslog = dict(PROC); syslog["/var/log/syslog"] = "Sep 7 10:00 srv cron: ok\nSep 7 10:01 srv kernel: I/O error on sda\nSep 7 10:02 srv x: Failed to start y\n"
        logs2 = host.collect_log_errors(nocmd, files(syslog))
        self.assertEqual(logs2["source"], "/var/log/syslog")
        self.assertEqual(len(logs2["lines"]), 2)
        acc = host.collect_accounts(files(PROC))
        self.assertEqual(acc["sudoers"], ["freg", "ops"])
        self.assertEqual(acc["uid0_not_root"], ["backdoor"])
        self.assertEqual(acc["interactive"], ["root", "freg", "backdoor"])

    def test_outils_et_collecte_complete(self):
        which = lambda t: "/usr/bin/" + t if t in ("nmap", "python3", "ss") else None
        tools = host.collect_tools(which)
        self.assertEqual(tools["available"], ["nmap", "python3", "ss"])
        self.assertIn("iperf3", tools["missing"])
        cmd = FakeCmd({"ss": (0, SS_OUT)})
        data, stat = host.collect_all(files=files(PROC), cmd=cmd, usage=lambda mp: Usage(100, 10), which=which,
                                      sleep=lambda s: None, previous_cpu=(1500, 9000), exists=lambda p: False)
        self.assertEqual(stat, (1550, 9750))
        self.assertNotIn("_stat", data["cpu"])
        self.assertEqual(sorted(data["partial"]), ["logs", "systemctl"])
        self.assertEqual(len(data["ports"]["ports"]), 4)
        json.dumps(data)  # sérialisable
        empty, _ = host.collect_all(files=files({}), cmd=FakeCmd({}), usage=lambda mp: Usage(1, 0), which=lambda t: None,
                                    sleep=lambda s: None, exists=lambda p: False)
        self.assertIn("os-release", empty["partial"])
        self.assertIn("mounts", empty["partial"])


class RisksTests(unittest.TestCase):
    def test_constats(self):
        data = {
            "system": {"cpus": 2, "reboot_required": True, "uptime_seconds": 120},
            "cpu": {"load5": 5.0}, "memory": {"used_percent": 95, "swap_used_percent": 60},
            "disks": [{"mountpoint": "/", "used_percent": 96}, {"mountpoint": "/data", "used_percent": 88}, {"mountpoint": "/mnt", "used_percent": 10}],
            "services": {"failed": ["nginx.service"]},
            "ports": {"ports": [{"proto": "tcp", "port": 23, "exposed": True, "process": "telnetd"}, {"proto": "tcp", "port": 6379, "exposed": False}, {"proto": "tcp", "port": 22, "exposed": True}]},
            "accounts": {"uid0_not_root": ["backdoor"]},
            "logs": {"source": "journald", "lines": ["e"] * 25},
        }
        found = risks.evaluate(data)
        ids = sorted(r["id"] for r in found)
        self.assertEqual(ids, sorted(["disk-full", "disk-high", "memory-high", "swap-high", "load-high", "reboot-required",
                                      "recent-boot", "service-failed", "port-exposed", "uid0-account", "log-errors"]))
        by = {r["id"]: r for r in found}
        self.assertEqual(by["disk-full"]["severity"], "critical")
        self.assertEqual(by["uid0-account"]["severity"], "critical")
        self.assertIn("Telnet", by["port-exposed"]["message"])
        self.assertEqual(risks.summarize(found)["state"], "critical")
        self.assertEqual(risks.summarize(found)["counts"]["critical"], 2)
        self.assertEqual(risks.summarize([])["state"], "ok")
        self.assertEqual(risks.evaluate({}), [])
        # seuils surchargés
        calm = risks.evaluate({"disks": [{"mountpoint": "/", "used_percent": 88}]}, {"disk_warning_percent": 90})
        self.assertEqual(calm, [])


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = plugins.PluginStore(os.path.join(self.dir, "plugins"))
        self.secret = "s3cr3t"

    def _manifest(self, **over):
        m = {"id": "hello", "version": "1", "runner": "shell", "entry": "hello.sh", "interval_seconds": 60, "timeout_seconds": 5, "enabled": True}
        m.update(over)
        return m

    def test_validation(self):
        self.assertEqual(plugins.validate_manifest(self._manifest())[0], True)
        for bad in (self._manifest(id="Hello"), self._manifest(id="a/b"), self._manifest(runner="perl"),
                    self._manifest(entry="../x.sh"), self._manifest(entry=".hidden"), self._manifest(interval_seconds=5),
                    self._manifest(args="x"), "pas-un-dict"):
            self.assertFalse(plugins.validate_manifest(bad)[0], bad)

    def test_installation_centrale_signee(self):
        body = "#!/bin/bash\necho '{\"hello\": \"world\", \"n\": 1}'\n"
        digest = plugins.sha256_text(body)
        m = self._manifest(sha256=digest, signature=plugins.plugin_signature(self.secret, "hello", "1", digest))
        ok, why = self.store.install(m, body, source="central", secret=self.secret)
        self.assertTrue(ok, why)
        stored = self.store.get("hello")
        self.assertEqual(stored["source"], "central")
        self.assertTrue(stored["present"])
        self.assertTrue(os.access(stored["path"], os.X_OK))
        # mauvaise signature / mauvais sha / mauvais secret : refusés, rien d'écrit
        for bad_m, sec in ((self._manifest(id="evil", sha256=digest, signature="deadbeef"), self.secret),
                           (self._manifest(id="evil", sha256="0" * 64, signature=plugins.plugin_signature(self.secret, "evil", "1", "0" * 64)), self.secret),
                           (self._manifest(id="evil", sha256=digest, signature=plugins.plugin_signature("autre", "evil", "1", digest)), self.secret),
                           (self._manifest(id="evil", sha256=digest, signature=plugins.plugin_signature(self.secret, "evil", "1", digest)), None)):
            ok, why = self.store.install(bad_m, body, source="central", secret=sec)
            self.assertFalse(ok, why)
            self.assertIsNone(self.store.get("evil"))
        # bundled : pas de signature exigée
        ok, _ = self.store.install(self._manifest(id="local"), body, source="bundled")
        self.assertTrue(ok)
        self.assertEqual([m["id"] for m in self.store.list()], ["hello", "local"])
        self.assertTrue(self.store.set_enabled("local", False))
        self.assertFalse(self.store.get("local")["enabled"])
        self.assertTrue(self.store.remove("local"))
        self.assertFalse(self.store.remove("local"))

    def test_execution_reelle_shell_et_python(self):
        sh = "#!/bin/bash\necho \"{\\\"who\\\": \\\"$SI_AGENT_ID\\\", \\\"arg\\\": \\\"$1\\\"}\"\n"
        self.store.install(self._manifest(args=["x1"]), sh, source="bundled")
        m = plugins.run_plugin(self.store.get("hello"), host.run_cmd, now=1_800_000_000, env={"SI_AGENT_ID": "srv-01"})
        self.assertTrue(m["ok"], m)
        self.assertEqual(m["task"], "plugin:hello")
        self.assertEqual(m["data"]["who"], "srv-01")
        self.assertEqual(m["data"]["arg"], "x1")
        self.assertEqual(m["data"]["_plugin"]["id"], "hello")
        py = "import json, sys\nprint(json.dumps([1, 2, 3]))\nsys.exit(0)\n"
        self.store.install(self._manifest(id="py", runner="python", entry="p.py"), py, source="bundled")
        m2 = plugins.run_plugin(self.store.get("py"), host.run_cmd)
        self.assertEqual(m2["data"]["result"], [1, 2, 3], "liste JSON enveloppée")
        self.store.install(self._manifest(id="txt"), "#!/bin/bash\necho bonjour\n", source="bundled")
        m3 = plugins.run_plugin(self.store.get("txt"), host.run_cmd)
        self.assertEqual(m3["data"]["raw"], "bonjour")
        self.store.install(self._manifest(id="ko"), "#!/bin/bash\necho oups >&2\nexit 3\n", source="bundled")
        m4 = plugins.run_plugin(self.store.get("ko"), host.run_cmd)
        self.assertFalse(m4["ok"])
        self.assertIn("code 3", m4["error"])
        self.assertIn("oups", m4["error"])
        self.store.install(self._manifest(id="slow", timeout_seconds=1), "#!/bin/bash\nsleep 5\n", source="bundled")
        m5 = plugins.run_plugin(self.store.get("slow"), host.run_cmd)
        self.assertFalse(m5["ok"])
        self.assertIn("délai", m5["error"])
        gone = self.store.get("hello"); os.remove(gone["path"])
        m6 = plugins.run_plugin(self.store.get("hello"), host.run_cmd)
        self.assertIn("script absent", m6["error"])

    def test_activation_locale_prioritaire(self):
        self.assertTrue(plugins.is_enabled({"id": "a", "enabled": True}))
        self.assertFalse(plugins.is_enabled({"id": "a", "enabled": True}, {"a": {"enabled": False}}))
        self.assertTrue(plugins.is_enabled({"id": "a", "enabled": False}, {"a": {"enabled": True}}))
        self.assertFalse(plugins.is_enabled({"id": "a"}))

    def test_plugins_livres_valides(self):
        bundled = os.path.join(ROOT, "plugins")
        ids = sorted(os.listdir(bundled))
        self.assertEqual(ids, ["capture-relay", "docker-containers", "network-neighbors"])  # #436 : relais d'exploration
        for pid in ids:
            with open(os.path.join(bundled, pid, "manifest.json")) as fh:
                m = json.load(fh)
            ok, why = plugins.validate_manifest(m)
            self.assertTrue(ok, why)
            self.assertEqual(m["id"], pid)
            self.assertFalse(m["enabled"], "livrés désactivés")
            self.assertTrue(os.path.isfile(os.path.join(bundled, pid, m["entry"])))
        # exécution réelle du plugin réseau sans balayage : JSON valide
        with open(os.path.join(bundled, "network-neighbors", "manifest.json")) as fh:
            m = json.load(fh)
        m["path"] = os.path.join(bundled, "network-neighbors", m["entry"]); m["present"] = True
        meas = plugins.run_plugin(m, host.run_cmd, env={"SI_NEIGHBORS_SWEEP": "0"})
        self.assertTrue(meas["ok"], meas)
        self.assertIn("neighbors", meas["data"])
        self.assertFalse(meas["data"]["sweep"])


class FakeHttp(object):
    """Faux central : configuration versionnée, commandes, mesures reçues."""

    def __init__(self, secret):
        self.secret = secret
        self.config = {"version": "v1", "issued_at": 100, "host_interval_seconds": 30, "risk_thresholds": {"disk_warning_percent": 50},
                       "plugins": [], "remove_plugins": [], "blocked": False}
        self.commands = []
        self.received = []
        self.acks = []
        self.fail_measurements = False
        self.calls = []
        # #422 : réponses signées comme le vrai central ; `tamper` simule un
        # central usurpé (corps modifié après signature) ou non signé
        self.sign = True
        self.tamper = None
        self.last_raw = b""
        self.last_headers = {}

    def _reply(self, status, body):
        raw = protocol.canonical_json(body) if body is not None else b""
        headers = control.response_headers(self.secret, raw) if self.sign else {}
        if self.tamper == "body":  # corps modifié en chemin : la signature ne correspond plus
            body = dict(body, version="vX", blocked=False, plugins=[], commands=[{"id": "evil", "type": "collect_now"}])
            raw = protocol.canonical_json(body)
        self.last_raw, self.last_headers = raw, headers
        return status, body

    def signed_plugin(self, pid, body, enabled=True, version="1", runner="shell", entry=None):
        digest = plugins.sha256_text(body)
        return {"manifest": {"id": pid, "version": version, "runner": runner, "entry": entry or (pid + ".sh"), "interval_seconds": 60,
                             "timeout_seconds": 5, "enabled": enabled, "sha256": digest,
                             "signature": plugins.plugin_signature(self.secret, pid, version, digest)}, "body": body}

    def request(self, method, path, body=None):
        self.calls.append((method, path))
        if path.endswith("/config"):
            return self._reply(200, self.config)
        if path.endswith("/commands"):
            cmds, self.commands = self.commands, []
            return self._reply(200, {"commands": cmds})
        if "/commands/" in path and path.endswith("/ack"):
            self.acks.append((path.split("/")[-2], body))
            return 200, {"status": "ok"}
        if path.endswith("/measurements"):
            if self.fail_measurements:
                return 0, None
            self.received.extend(body["measurements"])
            return 201, {"accepted": len(body["measurements"])}
        return 404, None


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cfg = dict(agent_mod.DEFAULTS)
        self.cfg.update({"agent_id": "srv-01", "secret": "s3cr3t", "central_url": "http://central", "site": "siege",
                         "queue_path": os.path.join(self.dir, "q.db"), "plugins_dir": os.path.join(self.dir, "plugins"),
                         "state_path": os.path.join(self.dir, "state.json"), "block_file": os.path.join(self.dir, "BLOCKED")})
        self.http = FakeHttp("s3cr3t")
        self.clock = [1_800_000_000.0]
        self.cmd = FakeCmd({"ss": (0, SS_OUT)})
        self.agent = agent_mod.Agent(self.cfg, http=self.http, cmd=self.cmd, files=files(PROC), clock=lambda: self.clock[0],
                                     usage=lambda mp: Usage(100, 60), which=lambda t: "/usr/bin/" + t if t == "python3" else None,
                                     exists=lambda p: False)

    def test_passage_complet_et_envoi(self):
        out = self.agent.run_once()
        tasks = [m["task"] for m in out]
        self.assertEqual(tasks, ["host", "risks", "netview", "inventory"])  # #428 : netview
        self.assertIn("config-applied", [e["data"]["kind"] for e in self.agent.queue.latest(task="event")], "événement journalisé")
        self.assertEqual(self.agent.cfg["host_interval_seconds"], 30, "configuration du central appliquée")
        host_m = out[0]
        self.assertFalse(host_m["ok"], "collecte partielle (pas de systemctl) -> ok=false, jamais silencieux")
        self.assertIn("systemctl", host_m["error"])
        risks_m = out[1]
        ids = [r["id"] for r in risks_m["data"]["risks"]]
        self.assertIn("disk-high", ids, "seuil abaissé à 50 % par le central : 60 % -> warning")
        self.assertIn("port-exposed", ids, "mariadb exposé")
        self.assertIn("uid0-account", ids)
        self.assertEqual(self.agent.flush(force=True), 5, "4 mesures (host, risks, netview, inventory) + 1 événement")
        self.assertEqual([m["task"] for m in self.http.received if m["task"] != "event"], ["host", "risks", "netview", "inventory"])
        self.assertEqual(self.agent.queue.stats()["pending"], 0)
        st = self.agent.status()
        self.assertEqual(st["config_version"], "v1")
        self.assertEqual(st["last_risks"]["state"], "critical")

    def test_rythme_et_file_en_panne_reseau(self):
        self.agent.refresh_config(force=True)
        self.assertEqual(len(self.agent.collect_host()), 2)
        self.assertEqual(self.agent.collect_host(), [], "pas encore l'heure")
        self.clock[0] += 31
        self.assertEqual(len(self.agent.collect_host()), 2)
        self.http.fail_measurements = True
        self.assertEqual(self.agent.flush(force=True), 0)
        self.assertEqual(self.agent.queue.stats()["pending"], 5, "rien de perdu, tout en file (4 mesures + 1 événement)")
        self.http.fail_measurements = False
        self.assertEqual(self.agent.flush(force=True), 5)

    def test_plugin_pousse_par_le_central_puis_commandes(self):
        self.http.config["plugins"] = [self.http.signed_plugin("hello", "#!/bin/bash\necho '{\"hi\": 1}'\n")]
        self.agent.refresh_config(force=True)
        self.assertEqual([m["id"] for m in self.agent.store.list()], ["hello"])
        self.assertEqual(self.agent.store.get("hello")["source"], "central")
        # Exécution réelle du plugin (bash), mesure en file
        produced = self.agent.run_plugins()
        self.assertEqual(len(produced), 1)
        self.assertEqual(produced[0]["data"]["hi"], 1)
        self.assertEqual(self.agent.run_plugins(), [], "intervalle respecté")
        # Plugin non signé : refusé sans casser le reste
        bad = self.http.signed_plugin("evil", "#!/bin/bash\nrm -rf /\n")
        bad["manifest"]["signature"] = "0" * 64
        self.http.config = dict(self.http.config, version="v2", plugins=[bad])
        self.agent.refresh_config(force=True)
        self.assertIsNone(self.agent.store.get("evil"))
        self.assertEqual(self.agent.config_version, "v2")
        # Commandes du tableau de bord
        self.http.commands = [{"id": "c1", "type": "run_plugin", "params": {"id": "hello"}},
                              {"id": "c2", "type": "disable_plugin", "params": {"id": "hello"}},
                              {"id": "c3", "type": "collect_now"},
                              {"id": "c4", "type": "bidule"},
                              {"id": "c5", "type": "remove_plugin", "params": {"id": "hello"}}]
        done = self.agent.poll_commands(force=True)
        self.assertEqual(len(done), 5)
        acks = dict(self.http.acks)
        self.assertTrue(acks["c1"]["ok"])
        self.assertEqual(acks["c1"]["result"]["hi"], 1)
        self.assertTrue(acks["c2"]["ok"])
        self.assertTrue(acks["c3"]["ok"])
        self.assertFalse(acks["c4"]["ok"])
        self.assertTrue(acks["c5"]["ok"])
        self.assertEqual(self.agent.store.list(), [])
        # Suppression demandée par la configuration
        self.http.config = dict(self.http.config, version="v3", plugins=[self.http.signed_plugin("tmp", "#!/bin/bash\necho ok\n")])
        self.agent.refresh_config(force=True)
        self.assertIsNotNone(self.agent.store.get("tmp"))
        self.http.config = dict(self.http.config, version="v4", plugins=[], remove_plugins=["tmp"])
        self.agent.refresh_config(force=True)
        self.assertIsNone(self.agent.store.get("tmp"))

    def test_authentification_refusee_et_config_invalide(self):
        class Refusing(FakeHttp):
            def request(self, method, path, body=None):
                return 401, {"error": "nope"}
        a = agent_mod.Agent(self.cfg, http=Refusing("x"), cmd=self.cmd, files=files(PROC), clock=lambda: self.clock[0],
                            usage=lambda mp: Usage(100, 10), which=lambda t: None, exists=lambda p: False)
        self.assertFalse(a.refresh_config(force=True))
        self.assertIsNone(a.last_central_contact)
        p = os.path.join(self.dir, "bad.json")
        with open(p, "w") as fh:
            fh.write('{"agent_id": "x"}')
        with self.assertRaises(ValueError):
            agent_mod.load_config(p)
        p = os.path.join(self.dir, "ok.json")
        with open(p, "w") as fh:
            fh.write('{"agent_id": "x", "secret": "y", "central_url": "http://c/"}')
        cfg = agent_mod.load_config(p)
        self.assertEqual(cfg["central_url"], "http://c")
        self.assertEqual(cfg["host_interval_seconds"], 60)

    def test_signature_des_requetes(self):
        body = protocol.canonical_json({"measurements": []})
        h = protocol.auth_headers("srv-01", "s3cr3t", "POST", "/api/v1/agents/srv-01/measurements", body)
        self.assertEqual(protocol.verify("s3cr3t", "POST", "/api/v1/agents/srv-01/measurements", h, body), (True, "ok"))
        self.assertFalse(protocol.verify("autre", "POST", "/api/v1/agents/srv-01/measurements", h, body)[0])


class SecurityTests(unittest.TestCase):
    """Livraison #422 : réponses signées, rejeu, blocage, confinement."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cfg = dict(agent_mod.DEFAULTS)
        self.cfg.update({"agent_id": "srv-01", "secret": "s3cr3t", "central_url": "http://central", "site": "siege",
                         "queue_path": os.path.join(self.dir, "q.db"), "plugins_dir": os.path.join(self.dir, "plugins"),
                         "state_path": os.path.join(self.dir, "state.json"), "block_file": os.path.join(self.dir, "BLOCKED")})
        self.http = FakeHttp("s3cr3t")
        self.clock = [1_800_000_000.0]
        self.blocked_file = [False]
        self.make_agent()

    def make_agent(self, **kw):
        cmd = kw.pop("cmd", FakeCmd({"ss": (0, SS_OUT)}))
        self.agent = agent_mod.Agent(self.cfg, http=self.http, cmd=cmd, files=files(PROC), clock=lambda: self.clock[0],
                                     usage=lambda mp: Usage(100, 10), which=lambda t: None,
                                     exists=lambda p: p == self.cfg["block_file"] and self.blocked_file[0], **kw)
        return self.agent

    def events(self):
        return [e["data"]["kind"] for e in self.agent.queue.latest(task="event", limit=100)]

    def test_reponse_non_signee_ou_alteree_refusee(self):
        self.http.sign = False
        self.assertFalse(self.agent.refresh_config(force=True), "central non signé : configuration ignorée")
        self.assertIsNone(self.agent.config_version)
        self.assertIn("central-response-rejected", self.events())
        self.http.sign = True
        self.http.tamper = "body"
        self.http.commands = [{"id": "c1", "type": "collect_now"}]
        self.assertEqual(self.agent.poll_commands(force=True), [], "corps altéré après signature : rien n'est exécuté")
        self.assertEqual(self.http.acks, [])
        self.http.tamper = None
        self.assertTrue(self.agent.refresh_config(force=True))
        self.assertEqual(self.agent.config_version, "v1")
        # mauvais secret côté central = signature invalide
        bad = FakeHttp("autre")
        a = agent_mod.Agent(self.cfg, http=bad, cmd=FakeCmd({}), files=files(PROC), clock=lambda: self.clock[0],
                            usage=lambda mp: Usage(100, 10), which=lambda t: None, exists=lambda p: False)
        self.assertFalse(a.refresh_config(force=True))
        # centraux anciens : tolérés seulement si explicitement demandé
        self.http.sign = False
        cfg2 = dict(self.cfg, require_signed_responses=False, state_path=os.path.join(self.dir, "s2.json"), queue_path=os.path.join(self.dir, "q2.db"))
        a2 = agent_mod.Agent(cfg2, http=self.http, cmd=FakeCmd({}), files=files(PROC), clock=lambda: self.clock[0],
                             usage=lambda mp: Usage(100, 10), which=lambda t: None, exists=lambda p: False)
        self.assertTrue(a2.refresh_config(force=True))

    def test_rejeu_configuration_et_commandes(self):
        self.assertTrue(self.agent.refresh_config(force=True))
        self.assertEqual(self.agent.state["last_config_issued_at"], 100)
        self.http.config = dict(self.http.config, version="v0", issued_at=50, host_interval_seconds=10)
        self.assertFalse(self.agent.refresh_config(force=True), "configuration plus ancienne = rejeu, ignorée")
        self.assertEqual(self.agent.cfg["host_interval_seconds"], 30)
        self.assertIn("config-replayed", self.events())
        # l'état survit à un redémarrage
        self.make_agent()
        self.assertEqual(self.agent.state["last_config_issued_at"], 100)
        self.http.config = dict(self.http.config, version="v2", issued_at=200, host_interval_seconds=45)
        self.assertTrue(self.agent.refresh_config(force=True))
        self.assertEqual(self.agent.cfg["host_interval_seconds"], 45)
        # commande rejouée
        self.http.commands = [{"id": "c1", "type": "collect_now"}]
        self.assertEqual(len(self.agent.poll_commands(force=True)), 1)
        self.http.commands = [{"id": "c1", "type": "collect_now"}, {"id": "c2", "type": "flush"}]
        done = self.agent.poll_commands(force=True)
        self.assertEqual([c["id"] for c, _ in done], ["c2"], "c1 déjà exécutée : ignorée, c2 passe")
        self.assertIn("command-replayed", self.events())
        self.make_agent()
        self.assertIn("c1", self.agent.state["done_commands"], "identifiants mémorisés sur disque")

    def test_blocage_general_et_individuel(self):
        self.http.config["plugins"] = [self.http.signed_plugin("hello", "#!/bin/bash\necho '{\"hi\": 1}'\n"),
                                       self.http.signed_plugin("other", "#!/bin/bash\necho '{\"o\": 1}'\n")]
        self.agent.refresh_config(force=True)
        self.assertEqual(len(self.agent.run_plugins()), 2)
        # commande de blocage général : plus rien ne tourne, état persistant
        self.http.commands = [{"id": "b1", "type": "block_all", "params": {"reason": "incident"}}]
        self.agent.poll_commands(force=True)
        self.assertTrue(self.agent.is_blocked())
        self.assertEqual(self.agent.block_reason(), "incident")
        self.clock[0] += 120
        self.assertEqual(self.agent.run_plugins(), [], "bloqué : aucune sonde exécutée")
        self.http.commands = [{"id": "r1", "type": "run_plugin", "params": {"id": "hello"}}]
        done = self.agent.poll_commands(force=True)
        self.assertFalse(done[0][1]["ok"], "exécution à la demande refusée aussi")
        self.make_agent()
        self.assertTrue(self.agent.is_blocked(), "blocage persistant après redémarrage")
        # nouvelle sonde poussée pendant le blocage : pas installée
        self.http.config = dict(self.http.config, version="v2", issued_at=200,
                                plugins=self.http.config["plugins"] + [self.http.signed_plugin("late", "#!/bin/bash\necho 1\n")])
        self.agent.refresh_config(force=True)
        self.assertIsNone(self.agent.store.get("late"))
        # déblocage
        self.http.commands = [{"id": "u1", "type": "unblock_all"}]
        self.agent.poll_commands(force=True)
        self.assertFalse(self.agent.is_blocked())
        self.clock[0] += 120
        self.assertEqual(len(self.agent.run_plugins()), 2)
        # blocage individuel
        self.http.commands = [{"id": "p1", "type": "block_plugin", "params": {"id": "hello", "reason": "suspect"}}]
        self.agent.poll_commands(force=True)
        self.clock[0] += 120
        self.assertEqual([m["task"] for m in self.agent.run_plugins()], ["plugin:other"])
        inv = self.agent.collect_inventory(force=True)
        self.assertEqual(inv["data"]["blocked_plugins"], ["hello"])
        self.http.commands = [{"id": "p2", "type": "unblock_plugin", "params": {"id": "hello"}}]
        self.agent.poll_commands(force=True)
        # blocage déclaratif par la configuration du central
        self.http.config = dict(self.http.config, version="v3", issued_at=300, blocked=True, blocked_reason="maintenance")
        self.agent.refresh_config(force=True)
        self.assertTrue(self.agent.is_blocked())
        self.assertEqual(self.agent.block_reason(), "maintenance")
        self.http.config = dict(self.http.config, version="v3", blocked=False)
        self.agent.refresh_config(force=True)
        self.assertFalse(self.agent.is_blocked(), "levé par le central même sans nouvelle version")
        # blocage d'une sonde par le manifeste
        self.http.config = dict(self.http.config, version="v4", issued_at=400,
                                plugins=[dict(self.http.config["plugins"][0], manifest=dict(self.http.config["plugins"][0]["manifest"], blocked=True)),
                                         self.http.config["plugins"][1]])
        self.agent.refresh_config(force=True)
        self.clock[0] += 120
        self.assertEqual([m["task"] for m in self.agent.run_plugins()], ["plugin:other"])
        # fichier BLOCKED local : le technicien sur place gagne
        self.blocked_file[0] = True
        self.assertTrue(self.agent.is_blocked())
        self.assertEqual(self.agent.block_reason(), "fichier BLOCKED local")
        kinds = self.events()
        for k in ("blocked", "unblocked", "plugin-blocked", "plugin-unblocked"):
            self.assertIn(k, kinds)

    def test_privilege_signe(self):
        body = "#!/bin/bash\nid -u\n"
        item = self.http.signed_plugin("root-only", body)
        item["manifest"]["privileged"] = True  # drapeau ajouté APRÈS signature
        self.http.config["plugins"] = [item]
        self.agent.refresh_config(force=True)
        self.assertIsNone(self.agent.store.get("root-only"), "privileged non couvert par la signature : refusé")
        digest = plugins.sha256_text(body)
        item["manifest"]["signature"] = plugins.plugin_signature("s3cr3t", "root-only", "1", digest, privileged=True)
        self.http.config = dict(self.http.config, version="v2", issued_at=200, plugins=[item])
        self.agent.refresh_config(force=True)
        self.assertTrue(self.agent.store.get("root-only")["privileged"])

    def test_confinement_reel(self):
        """Exécution RÉELLE confinée : environnement minimal, utilisateur non
        privilégié si possible, délai qui tue tout le groupe."""
        os.chmod(self.dir, 0o755)  # mkdtemp crée en 0700 : l'utilisateur non privilégié doit traverser
        self.make_agent(cmd=host.run_cmd)
        self.http.config["plugins"] = [
            self.http.signed_plugin("whoami", "#!/bin/bash\nprintf '{\"uid\": %s, \"home\": \"%s\", \"secret\": \"%s\"}' \"$(id -u)\" \"$HOME\" \"${SI_SECRET:-none}\"\n"),
            self.http.signed_plugin("slow", "#!/bin/bash\nsleep 30 &\nsleep 30\n"),
        ]
        self.http.config["plugins"][1]["manifest"]["timeout_seconds"] = 1
        self.http.config["plugins"][1]["manifest"]["signature"] = plugins.plugin_signature("s3cr3t", "slow", "1", plugins.sha256_text("#!/bin/bash\nsleep 30 &\nsleep 30\n"))
        os.environ["SI_SECRET"] = "leak"
        try:
            self.agent.refresh_config(force=True)
            started = __import__("time").monotonic()
            out = {m["task"]: m for m in self.agent.run_plugins()}
        finally:
            os.environ.pop("SI_SECRET", None)
        who = out["plugin:whoami"]
        self.assertTrue(who["ok"], who.get("error"))
        self.assertEqual(who["data"]["secret"], "none", "environnement du service jamais transmis")
        self.assertEqual(who["data"]["home"], "/tmp")
        if os.geteuid() == 0 and agent_mod.Agent._lookup_user("nobody"):
            self.assertNotEqual(who["data"]["uid"], 0, "sonde non privilégiée exécutée sans root")
        slow = out["plugin:slow"]
        self.assertFalse(slow["ok"])
        self.assertIn("délai dépassé", slow["error"])
        self.assertLess(__import__("time").monotonic() - started, 10, "le groupe de processus est tué, pas seulement le shell")
        self.assertIn("plugin-failed", self.events())

    def test_etat_et_evenements_purs(self):
        st = control.load_state(os.path.join(self.dir, "absent.json"))
        self.assertEqual(st["blocked"], False)
        self.assertTrue(control.remember_command(st, "a"))
        self.assertFalse(control.remember_command(st, "a"))
        for i in range(control.MAX_DONE_COMMANDS + 10):
            control.remember_command(st, "x%d" % i)
        self.assertEqual(len(st["done_commands"]), control.MAX_DONE_COMMANDS)
        control.save_state(os.path.join(self.dir, "s.json"), st)
        self.assertEqual(control.load_state(os.path.join(self.dir, "s.json"))["done_commands"][-1], "x%d" % (control.MAX_DONE_COMMANDS + 9))
        ev = control.make_event("a", "k", "bizarre", "m", now=1.5)
        self.assertEqual(ev["data"]["severity"], "info")
        self.assertEqual(ev["task"], "event")
        env = control.plugin_env("a", "s", "p", {"SI_X": "1", "PATH": "/evil", "HOME": "/root"})
        self.assertEqual(env["SI_X"], "1")
        self.assertNotEqual(env["PATH"], "/evil")
        self.assertEqual(env["HOME"], "/tmp")
        self.assertIsNone(control.resolve_run_user({"privileged": True}, "nobody", 0, lambda n: (65534, 65534)))
        self.assertEqual(control.resolve_run_user({}, "nobody", 0, lambda n: (65534, 65534)), (65534, 65534))
        self.assertIsNone(control.resolve_run_user({}, "nobody", 1000, lambda n: (65534, 65534)), "seul root change d'utilisateur")
        h = control.response_headers("s", b"body", timestamp=5)
        self.assertEqual(control.verify_response("s", h, b"body"), (True, "ok"))
        self.assertFalse(control.verify_response("s", h, b"other")[0])
        self.assertFalse(control.verify_response("s", {}, b"body")[0])


class SharedCopyTests(unittest.TestCase):
    def test_copies_identiques_a_la_source_canonique(self):
        src = os.path.join(ROOT, "..", "..", "netprobe", "agent", "netprobe_agent")
        for name in ("protocol.py", "localqueue.py"):
            with open(os.path.join(src, name)) as a, open(os.path.join(ROOT, "si_agent", name)) as b:
                self.assertEqual(a.read(), b.read(), "%s diverge : relancer sync-shared.sh" % name)


if __name__ == "__main__":
    unittest.main()
