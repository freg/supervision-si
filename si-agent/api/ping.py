"""#868 : test de connectivité rapide depuis le central (bouton « ping » à côté des IP du hub).

ICMP par la commande `ping` (paquet iputils-ping de l'image), puis repli TCP sur quelques ports usuels
quand l'ICMP est filtré ou indisponible. Aucun shell : arguments en liste, hôte validé avant tout appel.
"""
import ipaddress
import re
import shutil
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

HOSTNAME = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62})(?:\.[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,62}))*\.?$")
TCP_PORTS = (22, 443, 80, 3389, 8006, 161)
MAX_BATCH = 64
_cache = {}          # hôte -> (instant, résultat) : un clic répété ne relance pas tout (3 s)
CACHE_S = 3
RATE_MAX = 120       # hôtes testés par client et par minute : un bouton, pas un scanner du LAN
_rate = {}


def allow(client, n, now=None):
    """Fenêtre glissante d'une minute par client -> True si les n tests demandés passent."""
    now = time.time() if now is None else now
    hits = [t for t in _rate.get(client, []) if now - t < 60]
    if len(hits) + n > RATE_MAX:
        _rate[client] = hits
        return False
    _rate[client] = hits + [now] * n
    return True


def clean_host(raw):
    """« 192.0.2.4 », « 192.0.2.4:22 », « 192.0.2.4/24 », « [2001:db8::1] », « nom.exemple » -> hôte, ou None."""
    h = (raw or "").strip()
    if not h or len(h) > 255 or h.startswith("-"):
        return None
    if h.startswith("[") and "]" in h:
        h = h[1:h.index("]")]
    elif h.count(":") == 1:
        h = h.split(":")[0]
    h = h.split("/")[0]
    try:
        return str(ipaddress.ip_address(h))
    except ValueError:
        return h if HOSTNAME.match(h) else None


def _resolve(host):
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return None
    v4 = [i[4][0] for i in infos if i[0] == socket.AF_INET]
    return (v4 or [infos[0][4][0]])[0] if infos else None


def parse_ping(out):
    """Sortie iputils -> (reçus, envoyés, rtt moyen ms)."""
    m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received", out or "")
    sent, recv = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    r = re.search(r"= [\d.]+/([\d.]+)/", out or "")
    return recv, sent, (round(float(r.group(1)), 1) if r else None)


def icmp(ip, count=2, timeout=2):
    exe = shutil.which("ping")
    if not exe:
        return {"ok": None, "error": "commande ping absente"}
    args = [exe, "-n", "-c", str(count), "-W", str(timeout)]
    if ":" in ip:
        args.insert(1, "-6")
    try:
        p = subprocess.run(args + [ip], capture_output=True, text=True, timeout=count * timeout + 3)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "error": str(e)[:120]}
    recv, sent, rtt = parse_ping(p.stdout)
    if sent == 0:
        return {"ok": None, "error": (p.stderr or p.stdout).strip()[:160] or "ICMP indisponible"}
    return {"ok": recv > 0, "rtt_ms": rtt, "loss_pct": round(100 * (sent - recv) / sent)}


def tcp(ip, ports=TCP_PORTS, timeout=1.5):
    fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
    refused = []
    for port in ports:
        s = socket.socket(fam, socket.SOCK_STREAM)
        s.settimeout(timeout)
        t0 = time.monotonic()
        try:
            s.connect((ip, port))
            return {"ok": True, "port": port, "rtt_ms": round((time.monotonic() - t0) * 1000, 1)}
        except ConnectionRefusedError:
            refused.append(port)   # l'hôte répond (RST) : il est vivant, port simplement fermé
        except OSError:
            pass
        finally:
            s.close()
    if refused:
        return {"ok": True, "port": None, "note": "hôte joignable, ports testés fermés", "refused": refused}
    return {"ok": False, "ports": list(ports)}


def ping(raw, now=None):
    now = time.time() if now is None else now
    host = clean_host(raw)
    if not host:
        return {"host": raw, "ok": False, "state": "invalide", "error": "adresse ou nom invalide"}
    hit = _cache.get(host)
    if hit and now - hit[0] < CACHE_S:
        return hit[1]
    t0 = time.monotonic()
    ip = _resolve(host)
    if not ip:
        res = {"host": host, "ok": False, "state": "inconnu", "error": "nom non résolu"}
    else:
        i = icmp(ip)
        res = {"host": host, "ip": ip, "icmp": i}
        if i.get("ok"):
            res.update(ok=True, state="ok", rtt_ms=i.get("rtt_ms"), via="icmp")
        else:
            t = tcp(ip)
            res["tcp"] = t
            if t.get("ok"):
                res.update(ok=True, state="ok", rtt_ms=t.get("rtt_ms"), via="tcp/%s" % t["port"] if t.get("port") else "tcp")
            else:
                res.update(ok=False, state="injoignable")
    res["duree_ms"] = round((time.monotonic() - t0) * 1000)
    res["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    _cache[host] = (now, res)
    return res


def ping_many(hosts):
    hosts = [h for h in dict.fromkeys(hosts or []) if isinstance(h, str)][:MAX_BATCH]
    with ThreadPoolExecutor(max_workers=16) as ex:
        return list(ex.map(ping, hosts))
