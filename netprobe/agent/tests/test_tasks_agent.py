"""Tâches et boucle de la sonde -- sous-processus, fichiers, horloge et
HTTP simulés : aucun Raspberry Pi, aucun réseau."""
import os
import tempfile
import unittest

from netprobe_agent import tasks
from netprobe_agent.agent import Agent, DEFAULT_TASKS
from netprobe_agent.localqueue import LocalQueue
from netprobe_agent.tasks import CmdResult
from tests.test_parsers import IW_LINK_CONNECTED, IW_SCAN, PING_OK, PING_DEAD


class FakeCmd:
    """Répond selon argv[0] (+ sous-commande iw) ; enregistre les appels."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, argv, timeout=20):
        self.calls.append(list(argv))
        key = argv[0] if argv[0] != "iw" else "iw " + argv[3]
        r = self.table.get(key)
        if r is None:
            return CmdResult(-127, "", "binaire introuvable : %s" % argv[0])
        if callable(r):
            return r(argv)
        return r


def fake_files(table):
    return lambda path: table.get(path, "")


class Tasks(unittest.TestCase):
    def test_wifi_link_with_driver_counters(self):
        cmd = FakeCmd({"iw link": CmdResult(0, IW_LINK_CONNECTED)})
        files = fake_files({"/sys/class/net/wlan0/statistics/tx_errors": "12\n", "/sys/class/net/wlan0/statistics/rx_dropped": "abc"})
        ok, data, err = tasks.task_wifi_link({}, cmd=cmd, files=files)
        self.assertTrue(ok)
        self.assertEqual(data["bssid"], "9c:8e:cd:12:34:56")
        self.assertEqual(data["tx_errors"], 12)
        self.assertNotIn("rx_dropped", data, "valeur non numérique ignorée")
        self.assertEqual(cmd.calls[0], ["iw", "dev", "wlan0", "link"])

    def test_wifi_link_missing_iw(self):
        ok, data, err = tasks.task_wifi_link({"interface": "wlan1"}, cmd=FakeCmd({}), files=fake_files({}))
        self.assertFalse(ok)
        self.assertIn("introuvable", err)
        self.assertEqual(data, {"interface": "wlan1"})

    def test_wifi_scan_marks_ours_and_truncates(self):
        cmd = FakeCmd({"iw link": CmdResult(0, IW_LINK_CONNECTED), "iw scan": CmdResult(0, IW_SCAN)})
        ok, data, err = tasks.task_wifi_scan({"keep_networks": 2}, cmd=cmd, files=fake_files({}))
        self.assertTrue(ok)
        self.assertEqual(len(data["networks"]), 2, "liste tronquée")
        self.assertEqual(data["summary"]["total"], 4, "mais la synthèse reste complète")
        self.assertEqual(data["summary"]["our_channel"], "2.4/6")

    def test_wifi_scan_busy(self):
        cmd = FakeCmd({"iw link": CmdResult(0, ""), "iw scan": CmdResult(240, "", "command failed: Device or resource busy (-16)")})
        ok, data, err = tasks.task_wifi_scan({}, cmd=cmd, files=fake_files({}))
        self.assertFalse(ok)
        self.assertIn("busy", err)

    def test_ping_ok_dead_and_params(self):
        cmd = FakeCmd({"ping": lambda argv: CmdResult(0, PING_OK) if argv[-1] == "192.168.10.1" else CmdResult(1, PING_DEAD)})
        ok, data, err = tasks.task_ping({"host": "192.168.10.1", "count": 3}, cmd=cmd, files=fake_files({}))
        self.assertTrue(ok)
        self.assertEqual(data["rtt_avg_ms"], 1.56)
        self.assertEqual(cmd.calls[0][:4], ["ping", "-n", "-c", "3"])
        ok, data, err = tasks.task_ping({"host": "10.0.0.9", "count": 500}, cmd=cmd, files=fake_files({}))
        self.assertTrue(ok, "le ping a répondu (statistiques présentes) même si tout est perdu")
        self.assertFalse(data["ok"])
        self.assertEqual(cmd.calls[1][3], "20", "count borné à 20")
        self.assertFalse(tasks.task_ping({}, cmd=cmd, files=fake_files({}))[0])

    def test_ping_no_output(self):
        cmd = FakeCmd({"ping": CmdResult(2, "", "ping: unknown host foo")})
        ok, data, err = tasks.task_ping({"host": "foo"}, cmd=cmd, files=fake_files({}))
        self.assertFalse(ok)
        self.assertIn("unknown host", err)

    def test_dns_and_http_with_injected_io(self):
        ok, data, err = tasks.task_dns({"name": "example.org"}, resolver=lambda n: [(2, 1, 6, "", ("93.184.216.34", 0))])
        self.assertTrue(ok)
        self.assertEqual(data["addresses"], ["93.184.216.34"])
        import socket
        def failing(n):
            raise socket.gaierror("Name or service not known")
        ok, data, err = tasks.task_dns({"name": "nope.invalid"}, resolver=failing)
        self.assertFalse(ok)

        class Resp:
            status = 200
            def read(self, n): return b"x" * 10
        ok, data, err = tasks.task_http({"url": "http://ref/"}, opener=lambda u, t: Resp())
        self.assertTrue(ok)
        self.assertEqual(data["bytes"], 10)
        self.assertEqual(data["status"], 200)
        class Resp503(Resp):
            status = 503
        ok, data, err = tasks.task_http({"url": "http://ref/"}, opener=lambda u, t: Resp503())
        self.assertFalse(ok)
        self.assertEqual(err, "HTTP 503")

    def test_iperf3_absent_vs_result(self):
        ok, data, err = tasks.task_iperf3({"host": "ref"}, cmd=FakeCmd({}), files=fake_files({}))
        self.assertFalse(ok)
        self.assertIn("non installé", err)
        cmd = FakeCmd({"iperf3": CmdResult(0, '{"end":{"sum_sent":{"bits_per_second":20e6,"retransmits":0},"sum_received":{"bits_per_second":19e6}}}')})
        ok, data, err = tasks.task_iperf3({"host": "ref", "reverse": True, "duration": 99}, cmd=cmd, files=fake_files({}))
        self.assertTrue(ok)
        self.assertEqual(data["sent_mbps"], 20.0)
        self.assertIn("-R", cmd.calls[0])
        self.assertEqual(cmd.calls[0][cmd.calls[0].index("-t") + 1], "30", "durée bornée à 30 s")

    def test_sys_with_throttling(self):
        cmd = FakeCmd({"vcgencmd": CmdResult(0, "throttled=0x50005\n")})
        files = fake_files({"/proc/loadavg": "0.5 0.4 0.3 1/50 100", "/proc/uptime": "100.5 200",
                            "/sys/class/thermal/thermal_zone0/temp": "51234", "/proc/meminfo": "MemTotal: 10 kB\nMemAvailable: 5 kB\n"})
        ok, data, err = tasks.task_sys({}, cmd=cmd, files=files)
        self.assertTrue(ok)
        self.assertEqual(data["cpu_temp_c"], 51.2)
        self.assertTrue(data["under_voltage_now"])
        self.assertTrue(data["under_voltage_occurred"])
        self.assertEqual(data["uptime_s"], 100)

    def test_run_task_unknown_type_and_exception(self):
        m = tasks.run_task({"type": "batimentation"}, cmd=FakeCmd({}), files=fake_files({}))
        self.assertFalse(m["ok"])
        self.assertIn("inconnu", m["error"])
        self.assertEqual(m["task"], "batimentation")
        def boom(argv, timeout=20):
            raise RuntimeError("kaboom")
        m = tasks.run_task({"type": "wifi_link"}, cmd=boom, files=fake_files({}))
        self.assertFalse(m["ok"])
        self.assertIn("kaboom", m["error"])
        self.assertRegex(m["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_task_name_and_validation(self):
        self.assertEqual(tasks.task_name({"type": "ping", "params": {"host": "1.2.3.4"}}), "ping:1.2.3.4")
        self.assertEqual(tasks.task_name({"type": "wifi_link"}), "wifi_link")
        self.assertTrue(tasks.validate_task_spec({"type": "ping", "every": 60}))
        self.assertFalse(tasks.validate_task_spec({"type": "ping", "every": 1}), "jamais plus d'une exécution toutes les 5 s")
        self.assertFalse(tasks.validate_task_spec({"every": 60}))
        self.assertFalse(tasks.validate_task_spec("ping"))


class FakeHttp:
    """Simule le collecteur vu de la sonde : liste de tâches + accusés."""

    def __init__(self, tasks_body=None, post_status=200):
        self.tasks_body = tasks_body
        self.post_status = post_status
        self.posts = []
        self.gets = 0

    def request(self, method, path, body=None):
        if method == "GET":
            self.gets += 1
            return (200, self.tasks_body) if self.tasks_body is not None else (0, None)
        self.posts.append(body)
        status = self.post_status() if callable(self.post_status) else self.post_status
        return status, {"accepted": len(body["measurements"])} if status == 200 else {"error": "x"}


class AgentLoop(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.now = [1000.0]
        self.cfg = {"agent_id": "s1", "secret": "k", "collector_url": "http://c", "site": "alpha",
                    "poll_config_seconds": 300, "flush_seconds": 30, "batch_size": 2,
                    "queue_path": os.path.join(self.dir, "q.db"),
                    "default_tasks": [{"type": "wifi_link", "every": 30}, {"type": "ping", "every": 60, "params": {"host": "192.168.10.1"}}]}
        self.cmd = FakeCmd({"iw link": CmdResult(0, IW_LINK_CONNECTED), "ping": CmdResult(0, PING_OK)})

    def agent(self, http):
        return Agent(self.cfg, http=http, cmd=self.cmd, files=fake_files({}), clock=lambda: self.now[0])

    def test_local_tasks_then_collector_overrides(self):
        http = FakeHttp(tasks_body={"tasks": [{"type": "sys", "every": 60}, {"type": "bad", "every": 1}], "version": "v7"})
        a = self.agent(http)
        self.assertEqual(a.tasks_source, "local")
        self.assertTrue(a.refresh_tasks(force=True))
        self.assertEqual(a.tasks_source, "collector")
        self.assertEqual([t["type"] for t in a.tasks], ["sys"], "la tâche invalide (every=1) est écartée")
        self.assertEqual(a.tasks_version, "v7")
        # Pas de nouvel appel avant poll_config_seconds
        self.assertFalse(a.refresh_tasks())
        self.assertEqual(http.gets, 1)

    def test_collector_unreachable_keeps_local_tasks(self):
        a = self.agent(FakeHttp(tasks_body=None))
        self.assertFalse(a.refresh_tasks(force=True))
        self.assertEqual(a.tasks_source, "local")
        self.assertEqual(len(a.tasks), 2)

    def test_tick_respects_every_and_queues(self):
        a = self.agent(FakeHttp())
        produced = a.tick()
        self.assertEqual(sorted(m["task"] for m in produced), ["ping:192.168.10.1", "wifi_link"])
        self.assertTrue(all(m["agent_id"] == "s1" for m in produced))
        self.assertEqual(a.tick(), [], "rien n'est échu une seconde plus tard")
        self.now[0] += 31
        self.assertEqual([m["task"] for m in a.tick()], ["wifi_link"], "seul wifi_link (30 s) est échu")
        self.assertEqual(a.queue.pending_count(), 3)

    def test_flush_batches_and_store_and_forward(self):
        http = FakeHttp(post_status=0)  # collecteur injoignable
        a = self.agent(http)
        a.tick(); self.now[0] += 61; a.tick(); self.now[0] += 61; a.tick()
        self.assertEqual(a.queue.pending_count(), 6, "3 passages x 2 tâches (30 s et 60 s, toutes deux échues à +61)")
        self.assertEqual(a.flush(force=True), 0)
        self.assertEqual(a.queue.pending_count(), 6, "rien n'est perdu quand le collecteur est absent")
        self.assertEqual(len(http.posts), 1, "un seul essai par flush quand ça échoue")
        # Le collecteur revient : tout part par lots de batch_size=2
        http.post_status = 200
        self.assertEqual(a.flush(force=True), 6)
        self.assertEqual(a.queue.pending_count(), 0)
        self.assertEqual([len(p["measurements"]) for p in http.posts[1:]], [2, 2, 2])
        self.assertNotIn("_id", http.posts[1]["measurements"][0], "identifiant interne jamais envoyé")
        self.assertEqual(a.last_collector_contact, self.now[0])

    def test_flush_400_abandons_batch(self):
        a = self.agent(FakeHttp(post_status=400))
        a.tick()
        self.assertEqual(a.flush(force=True), 0)
        self.assertEqual(a.queue.pending_count(), 0, "lot mal formé : abandonné, pas réémis à l'infini")

    def test_flush_rate_limited(self):
        http = FakeHttp()
        a = self.agent(http)
        a.tick()
        a.flush(force=True)
        a.tick(); self.now[0] += 5
        self.assertEqual(a.flush(), 0, "pas de nouvel envoi avant flush_seconds")
        self.now[0] += 30
        self.assertEqual(a.flush(), 0, "rien de nouveau depuis")

    def test_status(self):
        a = self.agent(FakeHttp())
        s = a.status()
        self.assertEqual(s["agent_id"], "s1")
        self.assertEqual(s["tasks"], ["wifi_link", "ping:192.168.10.1"])
        self.assertEqual(s["queue"]["pending"], 0)


if __name__ == "__main__":
    unittest.main()
