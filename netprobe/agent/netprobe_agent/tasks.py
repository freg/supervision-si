"""Tâches exécutables par une sonde. Une tâche = un dict de configuration
reçu du collecteur (ou lu des `default_tasks` locales) :

    {"type": "ping", "every": 60, "params": {"host": "192.168.10.1", "count": 3}}

Le NOM d'une mesure (`task`) combine le type et la cible pour que deux
pings vers deux hôtes ne se confondent pas : `ping:192.168.10.1`.

L'exécution passe par des binaires système matures (`iw`, `ping`,
`iperf3`) -- jamais une réimplémentation maison d'un protocole, même
principe que ping_probe.py/iperf3_probe.py côté central. `run_cmd` et
`read_file` sont INJECTABLES : les tests remplacent les sous-processus
par des sorties réelles capturées, sans Raspberry Pi.

Ajouter un type de tâche = ajouter une fonction `task_<type>` ici : la
sonde ne connaît que ce catalogue, mais la LISTE et les PARAMÈTRES
viennent du collecteur -- "un interprète minimal qui s'enrichit des
tâches reçues" (principe pmoteur discuté au backlog, item 48).
"""
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request

from . import parsers

DEFAULT_TIMEOUT = 20


class CmdResult(object):
    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode, stdout, stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def run_cmd(argv, timeout=DEFAULT_TIMEOUT):
    """Exécution réelle. Renvoie CmdResult ; jamais d'exception -- un
    binaire absent ou un délai dépassé deviennent un code de retour
    négatif et un message, et la mesure sera marquée en erreur."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return CmdResult(p.returncode, p.stdout, p.stderr)
    except FileNotFoundError:
        return CmdResult(-127, "", "binaire introuvable : %s" % argv[0])
    except subprocess.TimeoutExpired:
        return CmdResult(-124, "", "délai dépassé (%ss) : %s" % (timeout, " ".join(argv)))
    except OSError as exc:
        return CmdResult(-1, "", str(exc))


def read_file(path):
    try:
        with open(path, "r") as fh:
            return fh.read()
    except OSError:
        return ""


def task_name(spec):
    t = spec.get("type", "?")
    p = spec.get("params") or {}
    if t == "ping":
        return "ping:%s" % p.get("host", "?")
    if t == "dns":
        return "dns:%s" % p.get("name", "?")
    if t == "http":
        return "http:%s" % p.get("url", "?")
    if t == "iperf3":
        return "iperf3:%s" % p.get("host", "?")
    return t


# ----------------------------------------------------------------------
# Tâches
# ----------------------------------------------------------------------

def task_wifi_link(params, cmd=run_cmd, files=read_file):
    iface = params.get("interface", "wlan0")
    r = cmd(["iw", "dev", iface, "link"], timeout=10)
    if r.returncode not in (0, 1) and not r.stdout:
        return False, {"interface": iface}, r.stderr.strip() or "iw a échoué (%s)" % r.returncode
    data = parsers.parse_iw_link(r.stdout)
    data["interface"] = iface
    # Compteurs d'erreurs du pilote (sysfs) -- gratuits et parlants sur un
    # lien qui "semble coupé" : retransmissions, paquets abandonnés.
    for name in ("rx_errors", "tx_errors", "rx_dropped", "tx_dropped"):
        raw = files("/sys/class/net/%s/statistics/%s" % (iface, name)).strip()
        if raw.isdigit():
            data[name] = int(raw)
    return True, data, None


def task_wifi_scan(params, cmd=run_cmd, files=read_file):
    iface = params.get("interface", "wlan0")
    keep = int(params.get("keep_networks", 15))
    link = parsers.parse_iw_link(cmd(["iw", "dev", iface, "link"], timeout=10).stdout)
    r = cmd(["iw", "dev", iface, "scan"], timeout=30)
    if r.returncode != 0 and not r.stdout:
        # "Device or resource busy" : le pilote refuse un scan pendant un
        # trafic soutenu -- fréquent, pas grave, la mesure est juste absente.
        return False, {"interface": iface}, (r.stderr.strip() or "scan impossible")[:200]
    scan = parsers.parse_iw_scan(r.stdout, own_bssid=link.get("bssid"))
    # Liste tronquée aux `keep` plus fortes : la synthèse par canal est
    # complète, la liste sert au technicien à mettre un nom sur un voisin.
    return True, {"interface": iface, "summary": scan["summary"], "networks": scan["networks"][:keep]}, None


def task_ping(params, cmd=run_cmd, files=read_file):
    host = params.get("host")
    if not host:
        return False, {}, "paramètre 'host' manquant"
    count = max(1, min(int(params.get("count", 3)), 20))
    r = cmd(["ping", "-n", "-c", str(count), "-W", str(int(params.get("timeout", 2))), host],
            timeout=count * 3 + 5)
    data = parsers.parse_ping(r.stdout)
    data["host"] = host
    if data.get("sent") is None:
        return False, data, (r.stderr.strip() or r.stdout.strip() or "ping sans résultat")[:200]
    return True, data, None


def task_dns(params, cmd=run_cmd, files=read_file, resolver=None):
    name = params.get("name")
    if not name:
        return False, {}, "paramètre 'name' manquant"
    resolve = resolver or (lambda n: socket.getaddrinfo(n, None))
    t0 = time.monotonic()
    try:
        infos = resolve(name)
        ms = round((time.monotonic() - t0) * 1000, 1)
        addrs = sorted({i[4][0] for i in infos})
        return True, {"name": name, "resolve_ms": ms, "addresses": addrs[:8]}, None
    except (socket.gaierror, OSError) as exc:
        return False, {"name": name, "resolve_ms": round((time.monotonic() - t0) * 1000, 1)}, str(exc)[:200]


def task_http(params, cmd=run_cmd, files=read_file, opener=None):
    url = params.get("url")
    if not url:
        return False, {}, "paramètre 'url' manquant"
    timeout = int(params.get("timeout", 10))
    open_url = opener or (lambda u, t: urllib.request.urlopen(u, timeout=t))
    t0 = time.monotonic()
    try:
        resp = open_url(url, timeout)
        body = resp.read(65536)
        ms = round((time.monotonic() - t0) * 1000, 1)
        status = getattr(resp, "status", None) or resp.getcode()
        ok = 200 <= int(status) < 400
        return ok, {"url": url, "status": int(status), "time_ms": ms, "bytes": len(body)}, None if ok else "HTTP %s" % status
    except urllib.error.HTTPError as exc:
        return False, {"url": url, "status": exc.code, "time_ms": round((time.monotonic() - t0) * 1000, 1)}, "HTTP %s" % exc.code
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, {"url": url, "time_ms": round((time.monotonic() - t0) * 1000, 1)}, str(exc)[:200]


def task_iperf3(params, cmd=run_cmd, files=read_file):
    host = params.get("host")
    if not host:
        return False, {}, "paramètre 'host' manquant"
    duration = max(1, min(int(params.get("duration", 5)), 30))
    argv = ["iperf3", "-c", host, "-p", str(int(params.get("port", 5201))), "-t", str(duration), "-J"]
    if params.get("reverse"):
        argv.append("-R")
    r = cmd(argv, timeout=duration + 15)
    if r.returncode == -127:
        return False, {"host": host}, "iperf3 non installé sur cette sonde"
    data = parsers.parse_iperf3_json(r.stdout)
    data["host"] = host
    data["reverse"] = bool(params.get("reverse"))
    if not data.get("ok"):
        return False, data, data.pop("error", None) or (r.stderr.strip()[:200] or "iperf3 a échoué")
    data.pop("ok", None)
    return True, data, None


def task_sys(params, cmd=run_cmd, files=read_file):
    data = {}
    data.update(parsers.parse_loadavg(files("/proc/loadavg")))
    data.update(parsers.parse_uptime(files("/proc/uptime")))
    data.update(parsers.parse_thermal(files("/sys/class/thermal/thermal_zone0/temp")))
    data.update(parsers.parse_meminfo(files("/proc/meminfo")))
    # Sous-tension / limitation thermique (spécifique Raspberry Pi) : un Pi
    # Zero W mal alimenté voit son WiFi se dégrader -- une cause de plus à
    # distinguer d'un vrai problème radio.
    r = cmd(["vcgencmd", "get_throttled"], timeout=5)
    if r.returncode == 0 and "=" in r.stdout:
        try:
            flags = int(r.stdout.strip().split("=")[1], 16)
            data["throttled_flags"] = flags
            data["under_voltage_now"] = bool(flags & 0x1)
            data["under_voltage_occurred"] = bool(flags & 0x10000)
        except ValueError:
            pass
    return True, data, None


TASKS = {
    "wifi_link": task_wifi_link,
    "wifi_scan": task_wifi_scan,
    "ping": task_ping,
    "dns": task_dns,
    "http": task_http,
    "iperf3": task_iperf3,
    "sys": task_sys,
}


def run_task(spec, cmd=run_cmd, files=read_file, now=None):
    """Exécute une tâche et renvoie une MESURE (sans agent_id, ajouté par
    l'agent). Un type inconnu produit une mesure en erreur plutôt qu'un
    plantage : le collecteur peut pousser une tâche que cette version de
    sonde ne connaît pas encore, ce n'est pas une raison de s'arrêter.

    `now` (epoch) vient de l'HORLOGE DE L'AGENT, jamais lue ici : l'instant
    `at` fait partie de la clé de déduplication (agent, tâche, instant) --
    il doit être celui que l'agent contrôle (et que les tests pilotent)."""
    ttype = spec.get("type")
    fn = TASKS.get(ttype)
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time()))
    if fn is None:
        return {"task": task_name(spec), "at": at, "ok": False, "data": None,
                "error": "type de tâche inconnu : %s" % ttype}
    try:
        ok, data, error = fn(spec.get("params") or {}, cmd=cmd, files=files)
    except Exception as exc:  # noqa: BLE001 -- une tâche ne doit jamais tuer la boucle
        ok, data, error = False, None, "exception : %s" % str(exc)[:200]
    return {"task": task_name(spec), "at": at, "ok": bool(ok), "data": data, "error": error}


def validate_task_spec(spec):
    if not isinstance(spec, dict) or not isinstance(spec.get("type"), str):
        return False
    every = spec.get("every", 60)
    return isinstance(every, (int, float)) and every >= 5
