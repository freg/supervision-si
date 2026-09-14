# -*- coding: utf-8 -*-
"""Tests du plugin si-agent « proxmox » (livraison #487) : parseurs purs
sur sorties représentatives de PVE 8 + collecte complète contre un FAUX
runner (aucun pvesh/zpool réel, aucun sous-processus)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", "proxmox"))

import proxmox  # noqa: E402

NOW = 1_780_000_000


class TestParseurs(unittest.TestCase):
    def test_agent_enabled(self):
        self.assertTrue(proxmox.agent_enabled({"agent": "1"}))
        self.assertTrue(proxmox.agent_enabled({"agent": "enabled=1,fstrim_cloned_disks=1"}))
        self.assertFalse(proxmox.agent_enabled({"agent": "0"}))
        self.assertFalse(proxmox.agent_enabled({"agent": "enabled=0"}))
        self.assertFalse(proxmox.agent_enabled({}))

    def test_extract_ips_qemu(self):
        data = {"result": [
            {"name": "lo", "ip-addresses": [{"ip-address": "127.0.0.1", "ip-address-type": "inet"}]},
            {"name": "eth0", "ip-addresses": [{"ip-address": "10.0.0.5", "ip-address-type": "inet"},
                                              {"ip-address": "fe80::1", "ip-address-type": "inet6"},
                                              {"ip-address": "2a01:cb00::5", "ip-address-type": "inet6"}]}]}
        self.assertEqual(proxmox.extract_ips_qemu(data), ["10.0.0.5", "2a01:cb00::5"])
        # Forme déballée (liste directe) acceptée aussi
        self.assertEqual(proxmox.extract_ips_qemu(data["result"]), ["10.0.0.5", "2a01:cb00::5"])
        self.assertEqual(proxmox.extract_ips_qemu(None), [])

    def test_extract_ips_lxc(self):
        rows = [{"name": "eth0", "hwaddr": "aa:bb", "inet": "10.0.0.6/24", "inet6": "fe80::1/64"},
                {"name": "lo", "inet": "127.0.0.1/8"}]
        self.assertEqual(proxmox.extract_ips_lxc(rows), ["10.0.0.6"])

    def test_newest_backups(self):
        rows = [
            {"volid": "store:backup/vzdump-qemu-100-2026_09_10-02_00_00.vma.zst", "ctime": NOW - 86400},
            {"volid": "store:backup/vzdump-qemu-100-2026_09_12-02_00_00.vma.zst", "ctime": NOW - 3600},
            {"volid": "store:backup/vzdump-lxc-101-2026_09_01-02_00_00.vma.zst", "ctime": NOW - 11 * 86400},
            {"volid": "store:iso/debian.iso", "ctime": NOW},
        ]
        b = proxmox.newest_backups(rows, NOW)
        self.assertEqual(set(b), {100, 101})
        self.assertEqual(b[100]["age_s"], 3600, "le plus récent des deux l'emporte")
        self.assertEqual(b[101]["age_s"], 11 * 86400)
        # Champ vmid explicite (PVE récents) prioritaire, pas de regex nécessaire
        b2 = proxmox.newest_backups([{"vmid": 100, "volid": "x", "ctime": NOW - 10}], NOW)
        self.assertEqual(b2[100]["age_s"], 10)

    def test_parse_zpool_list(self):
        text = "rpool\t960000000000\t480000000000\t480000000000\t12%\t50%\tONLINE\n" \
               "backup\t4000000000000\t3900000000000\t100000000000\t-\t97%\tDEGRADED\n"
        pools = proxmox.parse_zpool_list(text)
        self.assertEqual(len(pools), 2)
        self.assertEqual(pools[0]["pool"], "rpool")
        self.assertEqual(pools[0]["cap_pct"], 50)
        self.assertEqual(pools[1]["health"], "DEGRADED")
        self.assertIsNone(pools[1]["frag_pct"], "« - » n'est pas un chiffre")

    def test_parse_zpool_status(self):
        text = ("  pool: rpool\n state: ONLINE\n  scan: scrub repaired 0B\n"
                "errors: No known data errors\n\n  pool: backup\n state: DEGRADED\n"
                "errors: Permanent errors have been detected\n")
        st = proxmox.parse_zpool_status(text)
        self.assertEqual(st["rpool"]["state"], "ONLINE")
        self.assertEqual(st["rpool"]["errors"], "No known data errors")
        self.assertEqual(st["backup"]["state"], "DEGRADED")


# -- collecte complète contre un faux runner ------------------------------

def _j(obj):
    return json.dumps(obj)


FAKE = {
    "/nodes": [{"node": "pve1", "status": "online"}],
    "/nodes/pve1/status": {"pveversion": "pve-manager/8.2.4", "kversion": "Linux 6.8", "uptime": 400000,
                           "cpu": 0.12, "memory": {"used": 8_000_000_000, "total": 32_000_000_000}},
    "/nodes/pve1/storage": [
        {"storage": "local-zfs", "type": "zfspool", "active": 1, "enabled": 1, "content": "images,rootdir",
         "used": 100, "total": 200, "avail": 100},
        {"storage": "nas", "type": "nfs", "active": 1, "enabled": 1, "content": "backup,iso",
         "used": 300, "total": 400, "avail": 100},
        {"storage": "off", "type": "dir", "active": 0, "enabled": 0, "content": "backup"},
    ],
    "/nodes/pve1/storage/nas/content?content=backup": [
        {"volid": "nas:backup/vzdump-qemu-100-2026_09_12-02_00_00.vma.zst", "ctime": NOW - 3600},
    ],
    "/nodes/pve1/qemu": [
        {"vmid": 100, "name": "ged", "status": "running", "cpu": 0.03, "mem": 1_000_000, "maxmem": 4_000_000_000,
         "disk": 5_000_000, "maxdisk": 40_000_000_000, "uptime": 100000},
        {"vmid": 102, "name": "vieux", "status": "stopped"},
    ],
    "/nodes/pve1/qemu/100/snapshot": [
        {"name": "current", "description": "You are here!"},
        {"name": "avant-maj", "snaptime": NOW - 40 * 86400, "description": "avant migration"},
    ],
    "/nodes/pve1/qemu/102/snapshot": [{"name": "current"}],
    "/nodes/pve1/qemu/100/config": {"agent": "enabled=1", "memory": "4096"},
    "/nodes/pve1/qemu/100/agent/network-get-interfaces": {"result": [
        {"name": "eth0", "ip-addresses": [{"ip-address": "10.0.0.5", "ip-address-type": "inet"}]}]},
    "/nodes/pve1/lxc": [
        {"vmid": 101, "name": "cloud", "status": "running", "mem": 500_000, "maxmem": 1_000_000_000},
    ],
    "/nodes/pve1/lxc/101/snapshot": [],
    "/nodes/pve1/lxc/101/interfaces": [{"name": "eth0", "inet": "10.0.0.6/24"}],
}

TASKS = [
    {"upid": "UPID:pve1:0001:0002:%X:vzdump:100:root@pam:" % (NOW - 3600), "type": "vzdump", "id": "100", "user": "root@pam",
     "starttime": NOW - 3600, "endtime": NOW - 3500, "status": "OK"},
    {"upid": "UPID:pve1:0003:0004:%X:vzdump:102:root@pam:" % (NOW - 7200), "type": "vzdump", "id": "102", "user": "root@pam",
     "starttime": NOW - 7200, "endtime": NOW - 7100, "status": "job errors"},
    {"upid": "UPID:pve1:0005:0006:%X:vzdump::root@pam:" % (NOW - 600), "type": "vzdump", "id": "", "user": "root@pam",
     "starttime": NOW - 600, "status": "RUNNING"},
    {"upid": "UPID:pve1:0007:0008:%X:qmstart:100:root@pam:" % (NOW - 50), "type": "qmstart", "id": "100", "starttime": NOW - 50, "endtime": NOW - 49, "status": "OK"},
]
JOBS = [{"id": "backup-nightly", "enabled": 1, "schedule": "02:00", "storage": "nas", "vmid": "100,102", "mode": "snapshot", "compress": "zstd"},
        {"id": "backup-all", "enabled": 0, "schedule": "sun 03:00", "storage": "nas", "all": 1}]
FAKE["/nodes/pve1/tasks?typefilter=vzdump&limit=200&source=all"] = TASKS
FAKE["/cluster/backup"] = JOBS

ACCESS_LOG = """192.0.2.10 - root@pam [13/Sep/2026:10:22:01 +0000] "GET /api2/json/nodes/pve1/qemu/100/status/current HTTP/1.1" 200 1234
192.0.2.10 - root@pam [13/Sep/2026:10:22:05 +0000] "POST /api2/json/nodes/pve1/qemu/100/vncproxy HTTP/1.1" 200 300
192.0.2.11 - alice@pve [13/Sep/2026:10:30:00 +0000] "PUT /api2/json/nodes/pve1/lxc/101/config HTTP/1.1" 200 20
192.0.2.12 - - [13/Sep/2026:10:31:00 +0000] "POST /api2/json/access/ticket HTTP/1.1" 401 13
192.0.2.10 - root@pam [01/Jan/2020:00:00:00 +0000] "POST /api2/json/nodes/pve1/qemu/100/vncproxy HTTP/1.1" 200 300
ligne illisible
"""
SSH_JOURNAL = """2026-09-13T09:00:00+0000 pve1 sshd[100]: Accepted publickey for alice from 192.0.2.20 port 5000 ssh2: ED25519 SHA256:x
2026-09-13T09:05:00+0000 pve1 sshd[101]: Failed password for invalid user admin from 198.51.100.7 port 5001 ssh2
2026-09-13T09:05:01+0000 pve1 sshd[101]: Invalid user admin from 198.51.100.7 port 5001
2026-09-13T09:06:00+0000 pve1 sshd[102]: Failed password for root from 198.51.100.7 port 5002 ssh2
2026-09-13T09:10:00+0000 pve1 sshd[103]: Accepted password for bob from 192.0.2.21 port 5003 ssh2
"""
WEB_LOG = """192.0.2.30 - - [13/Sep/2026:10:00:00 +0000] "GET /index.php HTTP/1.1" 200 512 "-" "Mozilla"
192.0.2.30 - - [13/Sep/2026:10:00:01 +0000] "GET /login HTTP/1.1" 302 0 "-" "Mozilla"
192.0.2.31 - - [13/Sep/2026:10:00:02 +0000] "GET /admin HTTP/1.1" 404 0 "-" "curl"
192.0.2.31 - - [13/Sep/2026:10:00:03 +0000] "POST /api HTTP/1.1" 500 0 "-" "curl"
"""

ZPOOL_LIST = "rpool\t960000000000\t480000000000\t480000000000\t12%\t50%\tONLINE\n"
ZPOOL_STATUS = "  pool: rpool\n state: ONLINE\nerrors: No known data errors\n"


def fake_runner(cmd, timeout):
    if cmd[0] == "pvesh":
        path = cmd[2]
        if cmd[1] == "create" and path.endswith("/agent/exec"):
            # exécution invitée (#504) : le pid encode la commande demandée
            return 0, _j({"pid": 7 if "sshd" in " ".join(cmd) else 8}), ""
        if path.endswith("/agent/exec-status"):
            pid = cmd[cmd.index("--pid") + 1]
            return 0, _j({"exited": 1, "out-data": SSH_JOURNAL if pid == "7" else WEB_LOG}), ""
        if path in FAKE:
            return 0, _j(FAKE[path]), ""
        return 1, "", "no such path"
    if cmd[0] == "zpool":
        return 0, ZPOOL_LIST if "list" in cmd else ZPOOL_STATUS, ""
    if cmd[0] == "pct" and cmd[1] == "exec":
        return 0, SSH_JOURNAL if "sshd" in " ".join(cmd) else WEB_LOG, ""
    if cmd[0] == "journalctl":
        return (0, SSH_JOURNAL, "") if "-u" in cmd else (0, "pvedaemon[1]: authentication failure; rhost=198.51.100.7 user=root@pam msg=x\n", "")
    return 1, "", "commande inconnue"


class FakePve(proxmox.Pve):
    """Pve avec journal pveproxy en mémoire (pas de /var/log ici)."""
    def __init__(self, runner=fake_runner, access_log=None):
        proxmox.Pve.__init__(self, runner=runner)
        self._access = access_log

    def tail_file(self, path, max_bytes=None):
        return self._access


class TestCollecte(unittest.TestCase):
    def test_collecte_complete(self):
        # shutil.which("zpool") dépend de la machine de test : on force
        # le chemin ZFS en patchant which.
        orig_which = proxmox.shutil.which
        proxmox.shutil.which = lambda c: "/sbin/zpool" if c == "zpool" else orig_which(c)
        try:
            m = proxmox.collect(FakePve(access_log=ACCESS_LOG), hostname="pve1", now=NOW)
        finally:
            proxmox.shutil.which = orig_which

        self.assertEqual(m["node"]["name"], "pve1")
        self.assertEqual(m["node"]["pveversion"], "pve-manager/8.2.4")
        self.assertEqual(m["warnings"], [])

        vms = {v["vmid"]: v for v in m["vms"]}
        self.assertEqual(set(vms), {100, 101, 102})
        ged = vms[100]
        self.assertEqual(ged["ips"], ["10.0.0.5"], "IP via qemu-guest-agent")
        self.assertTrue(ged["agent"])
        self.assertEqual(len(ged["snapshots"]), 1, "« current » exclu")
        self.assertEqual(ged["snapshots"][0]["age_s"], 40 * 86400)
        self.assertEqual(ged["last_backup"]["age_s"], 3600)
        cloud = vms[101]
        self.assertEqual(cloud["ips"], ["10.0.0.6"], "IP via interfaces LXC")
        self.assertIsNone(cloud["last_backup"], "jamais sauvegardé : None explicite")
        self.assertEqual(vms[102]["ips"], [], "VM arrêtée : pas d'appel agent")

        self.assertEqual([s["storage"] for s in m["storages"]], ["local-zfs", "nas"],
                         "stockage désactivé exclu")
        self.assertEqual(m["zfs"][0]["health"], "ONLINE")
        self.assertEqual(m["zfs"][0]["errors"], "No known data errors")

        # #504 : sauvegardes -- tâches par VM, job en cours sans VM, jobs planifiés
        self.assertEqual(ged["last_backup_run"]["ok"], True)
        self.assertEqual(ged["last_backup_run"]["duration_s"], 100)
        self.assertEqual(vms[102]["last_backup_run"]["status"], "job errors")
        self.assertEqual(ged["backup_jobs"], ["backup-nightly", "backup-all"])
        self.assertEqual(m["backups"]["failed_24h"], 1)
        self.assertEqual(m["backups"]["ok_24h"], 1)
        self.assertEqual(m["backups"]["runs"][0]["status"], "en cours")
        self.assertIsNone(m["backups"]["runs"][0]["vmid"])
        self.assertEqual([j["id"] for j in m["backups"]["jobs"] if j["enabled"]], ["backup-nightly"])
        # #504 : accès -- console sur la VM 100 (ligne de 2020 hors fenêtre), modification sur 101, 401 hôte
        self.assertEqual(ged["access"]["console_sessions"], 1)
        self.assertEqual(ged["access"]["views"], 1)
        self.assertEqual(ged["access"]["users"][0]["key"], "root@pam")
        self.assertEqual(cloud["access"]["changes"], 1)
        self.assertEqual(m["access"]["host"]["auth_failures"], 1)
        self.assertEqual(m["access"]["host"]["requests"], 4)
        self.assertEqual(m["access"]["ssh"]["accepted"], 2)
        self.assertEqual(m["access"]["ssh"]["failed_by_ip"][0], {"key": "198.51.100.7", "count": 2})
        self.assertEqual(m["access"]["auth_failures_24h"], 1)
        # #504 : journaux internes -- VM avec agent (exec) et conteneur (pct), VM arrêtée exclue
        self.assertEqual(ged["guest_logs"]["ssh"]["accepted"], 2)
        self.assertEqual(ged["guest_logs"]["web"]["hits"], 4)
        self.assertEqual(ged["guest_logs"]["web"]["status"]["5xx"], 1)
        self.assertIn("Accepted publickey", ged["guest_logs"]["raw"]["ssh"])
        self.assertEqual(cloud["guest_logs"]["ssh"]["invalid_users"], 1)
        self.assertNotIn("guest_logs", vms[102])

    def test_pannes_partielles_listees(self):
        def runner_panne(cmd, timeout):
            if cmd[0] == "pvesh" and cmd[2] == "/nodes":
                return 0, _j(FAKE["/nodes"]), ""
            if cmd[0] == "pvesh" and "storage" in cmd[2]:
                return 1, "", "permission denied"
            if cmd[0] == "pvesh":
                return 0, _j(FAKE.get(cmd[2], {})), ""
            return 1, "", "boom"
        orig_which = proxmox.shutil.which
        proxmox.shutil.which = lambda c: None  # pas de zpool sur cette machine
        try:
            m = proxmox.collect(proxmox.Pve(runner=runner_panne), hostname="pve1", now=NOW)
        finally:
            proxmox.shutil.which = orig_which
        self.assertTrue(any("stockages" in w for w in m["warnings"]),
                        "panne partielle listée, jamais silencieuse")
        self.assertEqual(m["zfs"], [])
        self.assertTrue(any("journaux de" in w for w in m["warnings"]), "exec invité sans pid : signalé, jamais bloquant")


class TestSuiviAcces(unittest.TestCase):
    """#504 : parseurs purs du suivi des sauvegardes, des accès et des journaux."""

    def test_upid_et_backup_runs(self):
        info = proxmox.parse_upid("UPID:pve1:000A:000B:%X:vzdump:100:root@pam:" % NOW)
        self.assertEqual((info["node"], info["type"], info["id"], info["starttime"]), ("pve1", "vzdump", "100", NOW))
        self.assertIsNone(proxmox.parse_upid("n'importe quoi"))
        runs = proxmox.backup_runs(TASKS, now=NOW)
        self.assertEqual([r["vmid"] for r in runs], [None, 100, 102], "plus récentes d'abord, qmstart exclu")
        self.assertEqual(runs[1]["ok"], True)
        self.assertEqual(runs[2]["ok"], False)
        self.assertIsNone(runs[0]["ok"])
        jobs = proxmox.backup_jobs(JOBS)
        self.assertEqual(jobs[0]["vmids"], [100, 102])
        self.assertTrue(jobs[1]["all"] and not jobs[1]["enabled"])

    def test_pveproxy_access(self):
        p = proxmox.parse_pveproxy_access(ACCESS_LOG, now=1_789_300_000)
        self.assertEqual(p["host"]["requests"], 4, "ligne de 2020 hors fenêtre, ligne illisible ignorée")
        self.assertEqual(p["by_vm"][100]["console_sessions"], 1)
        self.assertEqual(p["by_vm"][100]["last_console_at"], p["by_vm"][100]["last_at"])
        self.assertEqual(p["by_vm"][101]["changes"], 1)
        self.assertEqual(p["by_vm"][101]["users"], {"alice@pve": 1})
        self.assertEqual(p["host"]["auth_failures"], 1)

    def test_ssh_et_web(self):
        s = proxmox.parse_ssh_journal(SSH_JOURNAL)
        self.assertEqual((s["accepted"], s["failed"], s["invalid_users"]), (2, 2, 1))
        self.assertEqual(s["last_accepted"]["user"], "bob")
        self.assertEqual(s["accepted_by_user"][0]["key"], "alice@192.0.2.20")
        w = proxmox.parse_web_access(WEB_LOG)
        self.assertEqual(w["hits"], 4)
        self.assertEqual(w["status"], {"2xx": 1, "3xx": 1, "4xx": 1, "5xx": 1})
        self.assertEqual(w["top_ips"][0]["count"], 2)
        self.assertIsNotNone(w["last_at"])
        self.assertEqual(proxmox.parse_web_access("")["hits"], 0)

    def test_tourniquet_et_disponibilite(self):
        ids = list(range(100, 140))
        b1 = proxmox.pick_guest_batch(ids, now=0)
        b2 = proxmox.pick_guest_batch(ids, now=1800)
        self.assertEqual(len(b1), 15)
        self.assertNotEqual(b1, b2)
        self.assertEqual(proxmox.pick_guest_batch([1, 2], now=0), [1, 2])
        a = proxmox.availability_from_states([(1, "running"), (2, "running"), (3, "stopped"), (4, "running"), (None, "running")])
        self.assertEqual((a["samples"], a["running"], a["availability_percent"]), (4, 3, 75.0))
        self.assertEqual([t["to"] for t in a["transitions"]], ["stopped", "running"])
        self.assertIsNone(proxmox.availability_from_states([])["availability_percent"])

    def test_guest_exec_borne(self):
        # exec-status jamais « exited » : délai dépassé, jamais une boucle infinie
        def runner(cmd, timeout):
            if cmd[1] == "create":
                return 0, _j({"pid": 5}), ""
            return 0, _j({"exited": 0}), ""
        pve = proxmox.Pve(runner=runner)
        with self.assertRaises(RuntimeError):
            pve.guest_exec("pve1", 100, "qemu", ["true"], timeout=0.5)




# -- apprentissage par exploration (#488) ----------------------------------

class FakeConnector(object):
    """Aucun réseau : ports, certificats, pages, PTR et DNS en mémoire."""

    OPEN = {"10.0.0.5": [22, 80, 443], "10.0.0.6": [443]}
    CERTS = {("10.0.0.5", 443): {"cn": "ged.example.lan", "sans": ["ged.example.lan", "docs.example.lan"],
                                 "days_left": 210, "self_signed": False},
             ("10.0.0.6", 443): {"cn": "cloud.example.lan", "sans": [], "days_left": -12, "self_signed": True}}
    PAGES = {("10.0.0.5", 80): {"status": 302, "server": "nginx", "title": None, "redirect_host": "ged.example.lan"}}
    PTRS = {"10.0.0.5": "ged.internal.lan"}
    DNS = {"ged.example.lan": ["10.0.0.5"], "docs.example.lan": ["10.0.0.5"],
           "cloud.example.lan": ["192.0.2.9"], "ged.internal.lan": ["10.0.0.5"]}

    def scan(self, ip, ports=None, timeout=0.4):
        return list(self.OPEN.get(ip, []))

    def tls_cert(self, ip, port, timeout=3.0):
        return self.CERTS.get((ip, port))

    def http_get(self, ip, port, timeout=3.0):
        return self.PAGES.get((ip, port))

    def ptr(self, ip, timeout=3.0):
        return self.PTRS.get(ip)

    def resolve(self, host, timeout=3.0):
        return self.DNS.get(host, [])


class TestApprentissage(unittest.TestCase):
    def test_learn_urls(self):
        urls = proxmox.learn_urls(
            [("ged.example.lan", "cert-san"), ("ged.example.lan", "redirect"),
             ("docs.example.lan", "cert-san"), ("introuvable.lan", "ptr"), ("*.wild.lan", "cert-san")],
            ["10.0.0.5"], FakeConnector().resolve)
        by_host = {u["host"]: u for u in urls}
        self.assertNotIn("*.wild.lan", by_host, "joker ignoré")
        self.assertEqual(by_host["ged.example.lan"]["sources"], ["cert-san", "redirect"])
        self.assertTrue(by_host["ged.example.lan"]["matches_vm"])
        self.assertFalse(by_host["introuvable.lan"]["resolves"], "trou DNS rapporté, pas masqué")
        self.assertFalse(by_host["introuvable.lan"]["matches_vm"])

    def test_assemble_services(self):
        svcs = proxmox.assemble_services([22, 443], {443: {"cn": "x", "days_left": 3}}, {})
        self.assertEqual([s["service"] for s in svcs], ["ssh", "https"])
        self.assertEqual(svcs[1]["tls"]["days_left"], 3)

    def test_learn_host(self):
        vms = [
            {"vmid": 100, "name": "ged", "status": "running", "ips": ["10.0.0.5"]},
            {"vmid": 101, "name": "cloud", "status": "running", "ips": ["10.0.0.6"]},
            {"vmid": 102, "name": "eteinte", "status": "stopped", "ips": ["10.0.0.7"]},
            {"vmid": 103, "name": "sans-ip", "status": "running", "ips": []},
        ]
        warnings = []
        proxmox.learn_host(vms, FakeConnector(), warnings)
        self.assertEqual(warnings, [])
        ged, cloud, eteinte, sans_ip = vms
        self.assertEqual([s["port"] for s in ged["services"]], [22, 80, 443])
        self.assertEqual(ged["services"][2]["tls"]["cn"], "ged.example.lan")
        self.assertEqual(ged["services"][1]["http"]["status"], 302)
        hosts = {u["host"]: u for u in ged["urls"]}
        self.assertTrue(hosts["ged.example.lan"]["matches_vm"], "URL apprise par SAN + redirection")
        self.assertIn("ptr", hosts["ged.internal.lan"]["sources"])
        self.assertEqual(cloud["services"][0]["tls"]["days_left"], -12,
                         "certificat expiré : constat négatif explicite")
        self.assertFalse({u["host"]: u for u in cloud["urls"]}["cloud.example.lan"]["matches_vm"],
                         "le nom résout ailleurs : l'URL ne pointe PAS vers cette VM")
        self.assertNotIn("services", eteinte, "VM arrêtée : pas de balayage")
        self.assertNotIn("services", sans_ip, "sans IP : pas de balayage")


if __name__ == "__main__":
    unittest.main()
