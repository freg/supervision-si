#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Central LOCAL de test pour si-agent (livraison #624) -- remplace le hub sur
un poste de travail (Mac, Linux) pour piloter un ou quelques agents sans
Docker, sans Keycloak, sans réseau d'entreprise : stdlib seulement.

Cas d'usage : essayer l'agent Windows (image P2V à chaud, redémarrage,
lanceurs, chien de garde, banc de charge, réveil réseau) depuis un
portable à la maison ; démonstration hors ligne ; dépannage d'un agent.

    cd si-agent/local-central && python3 local_central.py            # https://<ip du poste>:6444
    python3 local_central.py --http --port 8080                       # HTTP clair (test seulement)
    python3 local_central.py --plugins web-audit,windows-probe --plugin-arg web-audit="--urls https://exemple.test"

Au démarrage : PKI auto-signée (openssl, dossier data/pki, servie sur /ca
et épinglée par l'installeur), archive de l'agent (si-agent/make-archive.sh),
jeton d'enrôlement, puis la ligne PowerShell / shell à coller sur le poste.
Face agents = même contrat que si-agent-api (protocol.py / control.py
importés du paquet si_agent, jamais réimplémentés) : /api/v1/enroll,
config et commandes SIGNÉES, mesures, acquittements, /package, /deploy.
Interface locale sur / (sans authentification : à n'exposer que sur un
réseau de confiance ; --listen 127.0.0.1 pour le seul poste).
État dans data/state.json (secrets d'agents : ne pas partager le dossier).
"""
import argparse
import hashlib
import hmac
import html
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(os.path.dirname(HERE), "agent")
sys.path.insert(0, AGENT_DIR)
from si_agent import control, protocol  # noqa: E402
from si_agent import imagectl  # noqa: E402

COMMAND_TYPES = ("collect_now", "power_action", "wol", "startup_action", "watchdog_config", "bench", "image_host",
                 "block_all", "unblock_all", "block_plugin", "unblock_plugin", "update")
KEPT_TASKS = 40
MAX_EVENTS = 500
MAX_COMMANDS = 200


# ---------------------------------------------------------------------------
# état (JSON sur disque, verrou global : quelques agents, pas une flotte)
# ---------------------------------------------------------------------------
class State:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.data = {"token": None, "agents": {}, "commands": [], "measurements": {}, "events": [], "next_cmd": 1}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    self.data.update(json.load(fh))
            except (OSError, ValueError):
                pass
        if not self.data.get("token"):
            self.data["token"] = secrets.token_urlsafe(18)
        self.save()

    def save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    # -- agents --
    def enroll(self, hostname, platform, site):
        with self.lock:
            base = "".join(c if c.isalnum() or c in "-" else "-" for c in (hostname or "poste").lower()).strip("-")[:40] or "poste"
            aid = base
            n = 2
            while aid in self.data["agents"] and self.data["agents"][aid].get("hostname") != hostname:
                aid = "%s-%d" % (base, n)
                n += 1
            secret = secrets.token_urlsafe(32)
            self.data["agents"][aid] = {"agent_id": aid, "secret": secret, "site": site, "hostname": hostname, "platform": platform,
                                        "enrolled_at": _now_iso(), "last_seen": None, "ip": None, "config_version": None}
            self.save()
            return self.data["agents"][aid]

    def touch(self, aid, ip, version=None):
        with self.lock:
            a = self.data["agents"].get(aid)
            if a:
                a["last_seen"] = _now_iso(); a["ip"] = ip
                if version:
                    a["config_version"] = version

    # -- commandes --
    def create_command(self, aid, ctype, params):
        with self.lock:
            cid = "c%d" % self.data["next_cmd"]
            self.data["next_cmd"] += 1
            c = {"id": cid, "agent_id": aid, "type": ctype, "params": params or {}, "status": "pending", "created_at": _now_iso(), "result": None, "acked_at": None}
            self.data["commands"].append(c)
            self.data["commands"] = self.data["commands"][-MAX_COMMANDS:]
            self.save()
            return c

    def pending(self, aid):
        with self.lock:
            return [{"id": c["id"], "type": c["type"], "params": c["params"]} for c in self.data["commands"] if c["agent_id"] == aid and c["status"] == "pending"]

    def ack(self, aid, cid, result):
        with self.lock:
            for c in self.data["commands"]:
                if c["id"] == cid and c["agent_id"] == aid:
                    c["status"] = "done" if (result or {}).get("ok") else "failed"
                    c["result"] = result; c["acked_at"] = _now_iso()
                    self.save()
                    return True
            return False

    # -- mesures --
    def store_measurements(self, aid, items):
        with self.lock:
            m = self.data["measurements"].setdefault(aid, {})
            n = 0
            for it in items or []:
                if not isinstance(it, dict) or not it.get("task"):
                    continue
                n += 1
                if it["task"] == "event":
                    ev = dict(it.get("data") or {}); ev["agent_id"] = aid; ev["at"] = it.get("at")
                    self.data["events"].append(ev)
                else:
                    m[it["task"]] = {"at": it.get("at"), "ok": it.get("ok"), "error": it.get("error"), "data": it.get("data")}
            self.data["events"] = self.data["events"][-MAX_EVENTS:]
            if len(m) > KEPT_TASKS:
                for k in sorted(m, key=lambda t: m[t].get("at") or "")[: len(m) - KEPT_TASKS]:
                    m.pop(k, None)
            self.save()
            return n


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# PKI auto-signée, archive, plugins
# ---------------------------------------------------------------------------
def ensure_pki(pki_dir, ip, hostname):
    key, crt = os.path.join(pki_dir, "server.key"), os.path.join(pki_dir, "server.crt")
    if not (os.path.isfile(key) and os.path.isfile(crt)):
        os.makedirs(pki_dir, exist_ok=True)
        san = "IP:%s,IP:127.0.0.1,DNS:localhost,DNS:%s" % (ip, hostname)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "825", "-keyout", key, "-out", crt,
                        "-subj", "/CN=si-agent local central", "-addext", "subjectAltName=" + san,
                        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.chmod(key, 0o600)
    with open(crt, "rb") as fh:
        pem = fh.read()
    der = ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))
    return key, crt, pem, hashlib.sha256(der).hexdigest()


def ensure_archive(data_dir, rebuild=False):
    files = sorted(f for f in os.listdir(data_dir) if f.startswith("si-agent-agent-") and f.endswith(".tar.gz"))
    if files and not rebuild:
        return os.path.join(data_dir, files[-1])
    script = os.path.join(os.path.dirname(HERE), "make-archive.sh")
    out = subprocess.run(["bash", script, data_dir], check=True, capture_output=True, text=True).stdout.strip().splitlines()
    return out[0] if out else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_plugins(ids, plugin_args):
    """Plugins livrés dans si-agent/agent/plugins : manifeste + corps (entrée) ;
    signés par agent au moment de servir la configuration."""
    out = []
    for pid in ids:
        d = os.path.join(AGENT_DIR, "plugins", pid)
        with open(os.path.join(d, "manifest.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        with open(os.path.join(d, raw["entry"]), encoding="utf-8") as fh:
            body = fh.read()
        man = {k: raw[k] for k in ("id", "version", "runner", "entry", "interval_seconds", "timeout_seconds", "args", "description") if k in raw}
        man["privileged"] = bool(raw.get("privileged"))
        if pid in plugin_args:
            man["args"] = plugin_args[pid]
        man["enabled"] = True; man["blocked"] = False
        man["sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        out.append({"manifest": man, "body": body})
    return out


def config_for(agent, plugins, interval):
    assigned = []
    fp = [str(interval)]
    for p in plugins:
        man = dict(p["manifest"])
        msg = control.plugin_signature_message(man["id"], man["version"], man["sha256"], man.get("privileged", False))
        man["signature"] = hmac.new(agent["secret"].encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
        assigned.append({"manifest": man, "body": p["body"]})
        fp.append("%s@%s:%s" % (man["id"], man["version"], man["sha256"][:12]))
    version = hashlib.sha256("\n".join(fp).encode("utf-8")).hexdigest()[:16]
    return {"version": version, "issued_at": int(time.time()), "host_interval_seconds": interval, "risk_thresholds": {},
            "plugins": assigned, "remove_plugins": [], "blocked": False, "blocked_reason": None, "publish": None}


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def bootstrap_lines(base, token, site, ca_sha, plugins):
    win = (r"""# si-agent -- amorçage Windows (central local)
$ErrorActionPreference = "Stop"
$base = "%(base)s"; $token = "%(token)s"
$tmp = Join-Path $env:TEMP ("si-agent-" + [guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Path $tmp | Out-Null
""" + (r"""[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
if (-not ("SiAgentTrustAll" -as [type])) { Add-Type -TypeDefinition "using System.Net.Security; public static class SiAgentTrustAll { public static RemoteCertificateValidationCallback Callback() { return delegate { return true; }; } }" }
[Net.ServicePointManager]::ServerCertificateValidationCallback = [SiAgentTrustAll]::Callback()
""" if ca_sha else "") + r"""Write-Host "si-agent : téléchargement de l'archive depuis $base ..."
(New-Object System.Net.WebClient).DownloadFile("$base/package", (Join-Path $tmp "agent.tgz"))
tar -xzf (Join-Path $tmp "agent.tgz") -C $tmp
$dir = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
$ps = Join-Path $dir.FullName "windows\install.ps1"
$args = @("-EnrollToken", $token, "-Central", $base, "-Site", "%(site)s")
if ("%(ca)s") { $args += @("-CaFingerprint", "%(ca)s") } else { $args += "-SystemCa" }
if ("%(plugins)s") { $args += @("-EnablePlugin", ("%(plugins)s" -split ",")) }
& powershell -NoProfile -ExecutionPolicy Bypass -File $ps @args
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
""") % {"base": base, "token": token, "site": site, "ca": ca_sha or "", "plugins": ",".join(plugins)}
    lin = r"""#!/bin/sh
set -e
BASE="%(base)s"; TOKEN="%(token)s"
TMP=$(mktemp -d /tmp/si-agent.XXXXXX)
curl -fsSL %(k)s "$BASE/package" -o "$TMP/agent.tgz"
tar -xzf "$TMP/agent.tgz" -C "$TMP"
DIR=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)
cd "$DIR"
SI_AGENT_ENROLL_TOKEN="$TOKEN" SI_AGENT_CENTRAL="$BASE" SI_AGENT_SITE="%(site)s" SI_AGENT_CA_SHA256="%(ca)s" SI_AGENT_PLUGINS="%(plugins)s" ./install.sh
rm -rf "$TMP"
""" % {"base": base, "token": token, "site": site, "ca": ca_sha or "", "plugins": " ".join(plugins), "k": "-k" if ca_sha else ""}
    return win, lin


# ---------------------------------------------------------------------------
# serveur HTTP
# ---------------------------------------------------------------------------
class Central:
    def __init__(self, args):
        self.args = args
        self.data_dir = os.path.abspath(args.data)
        os.makedirs(self.data_dir, exist_ok=True)
        self.state = State(os.path.join(self.data_dir, "state.json"))
        self.ip = args.advertise_ip or local_ip()
        self.hostname = socket.gethostname().split(".")[0]
        self.scheme = "http" if args.http else "https"
        self.base = "%s://%s:%d" % (self.scheme, self.ip, args.port)
        self.ca_pem, self.ca_sha, self.key, self.crt = b"", None, None, None
        if not args.http:
            self.key, self.crt, self.ca_pem, self.ca_sha = ensure_pki(os.path.join(self.data_dir, "pki"), self.ip, self.hostname)
        self.package = ensure_archive(self.data_dir, args.rebuild_archive) if not args.no_archive else None
        self.package_info = {"name": os.path.basename(self.package), "size": os.path.getsize(self.package), "sha256": sha256_file(self.package)} if self.package else None
        pa = {}
        for item in args.plugin_arg or []:
            pid, _, val = item.partition("=")
            pa[pid.strip()] = val.split()
        self.plugin_ids = [p.strip() for p in (args.plugins or "").split(",") if p.strip()]
        self.plugins = load_plugins(self.plugin_ids, pa)
        self.interval = args.interval
        self.site = args.site
        self.started = time.time()

    def bootstraps(self):
        return bootstrap_lines(self.base, self.state.data["token"], self.site, self.ca_sha, self.plugin_ids)

    def one_liners(self):
        tok = self.state.data["token"]
        if self.ca_sha:
            # PS 5.1 : un ScriptBlock en ServerCertificateValidationCallback échoue (autre thread) -> délégué C#, comme install.ps1
            win = ("powershell -NoProfile -ExecutionPolicy Bypass -Command \"Add-Type -TypeDefinition 'using System.Net.Security; public static class SiAgentTrustAll { public static RemoteCertificateValidationCallback Callback() { return delegate { return true; }; } }'; "
                   "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; [Net.ServicePointManager]::ServerCertificateValidationCallback = [SiAgentTrustAll]::Callback(); "
                   "iex (New-Object Net.WebClient).DownloadString('%s/deploy/windows?token=%s')\"" % (self.base, tok))
        else:
            win = "powershell -NoProfile -ExecutionPolicy Bypass -Command \"iex (New-Object Net.WebClient).DownloadString('%s/deploy/windows?token=%s')\"" % (self.base, tok)
        lin = "curl -fsSL %s'%s/deploy/linux?token=%s' | sudo sh" % ("-k " if self.ca_sha else "", self.base, tok)
        return {"windows": win, "linux": lin}

    def ui_state(self):
        st = self.state
        with st.lock:
            agents = [{k: v for k, v in a.items() if k != "secret"} for a in st.data["agents"].values()]
            return {"base": self.base, "token": st.data["token"], "ca_sha256": self.ca_sha, "site": self.site, "package": self.package_info,
                    "plugins": self.plugin_ids, "one_liners": self.one_liners(), "agents": agents,
                    "commands": list(reversed(st.data["commands"][-60:])), "events": list(reversed(st.data["events"][-150:])),
                    "measurements": st.data["measurements"], "runbook": imagectl.PROXMOX_RUNBOOK, "uptime": int(time.time() - self.started)}


class Handler(BaseHTTPRequestHandler):
    server_version = "si-agent-local-central/1"
    central = None  # type: Central

    def log_message(self, fmt, *args):  # journal sobre
        if self.central.args.verbose:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # -- utilitaires --
    def _send(self, status, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _signed(self, secret, payload, status=200):
        raw = protocol.canonical_json(payload)
        self._send(status, raw, extra=control.response_headers(secret, raw))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _json(self, raw):
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            return None

    def _verify(self, aid, raw):
        a = self.central.state.data["agents"].get(aid)
        if not a or self.headers.get(protocol.HEADER_ID) != aid:
            return None, "agent inconnu"
        ok, why = protocol.verify(a["secret"], self.command, self.path, self.headers, raw)
        return (a, None) if ok else (None, why)

    # -- GET --
    def do_GET(self):
        c = self.central
        url = urllib.parse.urlsplit(self.path)
        path, qs = url.path, urllib.parse.parse_qs(url.query)
        parts = path.strip("/").split("/")
        if path in ("/", "/index.html"):
            return self._send(200, UI_HTML, "text/html; charset=utf-8")
        if path == "/ui/state":
            return self._send(200, c.ui_state())
        if path == "/ca":
            return self._send(200, c.ca_pem, "application/x-pem-file") if c.ca_pem else self._send(404, {"error": "central en HTTP clair : pas de CA"})
        if path == "/package":
            if not c.package:
                return self._send(404, {"error": "archive absente"})
            with open(c.package, "rb") as fh:
                return self._send(200, fh.read(), "application/gzip", {"Content-Disposition": "attachment; filename=%s" % os.path.basename(c.package)})
        if path == "/package/info":
            return self._send(200, dict(c.package_info or {}, url=c.base + "/package")) if c.package_info else self._send(404, {"error": "archive absente"})
        if parts[0] == "deploy" and len(parts) == 2:
            if (qs.get("token") or [""])[0] != c.state.data["token"]:
                return self._send(403, "jeton d'enrôlement inconnu\n", "text/plain; charset=utf-8")
            win, lin = c.bootstraps()
            if parts[1] == "windows":
                return self._send(200, win, "text/plain; charset=utf-8")
            if parts[1] == "linux":
                return self._send(200, lin, "text/plain; charset=utf-8")
            return self._send(404, {"error": "windows ou linux"})
        if parts[:3] == ["api", "v1", "agents"] and len(parts) >= 5:
            aid, leaf = parts[3], parts[4]
            a, why = self._verify(aid, b"")
            if a is None:
                return self._send(401, {"error": why})
            if leaf == "config":
                cfg = config_for(a, c.plugins, c.interval)
                c.state.touch(aid, self.client_address[0], cfg["version"])
                return self._signed(a["secret"], cfg)
            if leaf == "commands":
                c.state.touch(aid, self.client_address[0])
                return self._signed(a["secret"], {"commands": c.state.pending(aid)})
            if leaf == "publish":
                return self._signed(a["secret"], {"publish": None, "items": []})
        if path in ("/health", "/version"):
            return self._send(200, {"ok": True, "local_central": True, "agents": len(c.state.data["agents"])})
        return self._send(404, {"error": "inconnu"})

    # -- POST --
    def do_POST(self):
        c = self.central
        raw = self._body()
        path = urllib.parse.urlsplit(self.path).path
        parts = path.strip("/").split("/")
        if path == "/api/v1/enroll":
            body = self._json(raw) or {}
            if body.get("token") != c.state.data["token"]:
                return self._send(403, {"error": "jeton d'enrôlement invalide"})
            a = c.state.enroll(str(body.get("hostname") or "poste")[:60], body.get("platform"), c.site)
            c.state.data["events"].append({"kind": "agent-enrolled", "severity": "info", "agent_id": a["agent_id"], "at": _now_iso(),
                                           "message": "agent %s enrôlé (%s)" % (a["agent_id"], body.get("platform") or "?"), "details": {}})
            c.state.save()
            print("* agent enrôlé : %s (%s)" % (a["agent_id"], body.get("platform")))
            return self._send(201, {"agent_id": a["agent_id"], "secret": a["secret"], "site": c.site, "central_url": c.base,
                                    "ca_sha256": c.ca_sha, "plugins": c.plugin_ids})
        if parts[:3] == ["api", "v1", "agents"] and len(parts) >= 5:
            aid, leaf = parts[3], parts[4]
            a, why = self._verify(aid, raw)
            if a is None:
                return self._send(401, {"error": why})
            body = self._json(raw)
            if body is None:
                return self._send(400, {"error": "JSON invalide"})
            c.state.touch(aid, self.client_address[0])
            if leaf == "measurements":
                n = c.state.store_measurements(aid, body.get("measurements"))
                return self._send(201, {"stored": n})
            if leaf == "commands" and len(parts) == 7 and parts[6] == "ack":
                ok = c.state.ack(aid, parts[5], body)
                return self._send(200 if ok else 404, {"ok": ok})
        if path == "/ui/command":
            body = self._json(raw) or {}
            aid, ctype = body.get("agent_id"), body.get("type")
            if aid not in c.state.data["agents"]:
                return self._send(404, {"error": "agent inconnu"})
            if ctype not in COMMAND_TYPES:
                return self._send(400, {"error": "type inconnu (%s)" % ", ".join(COMMAND_TYPES)})
            params = body.get("params") or {}
            if ctype == "image_host":
                _, err = imagectl.validate(params)
                if err:
                    return self._send(400, {"error": err})
            return self._send(201, c.state.create_command(aid, ctype, params))
        if path == "/ui/token":
            c.state.data["token"] = secrets.token_urlsafe(18); c.state.save()
            return self._send(200, {"token": c.state.data["token"]})
        if path == "/ui/forget":
            body = self._json(raw) or {}
            with c.state.lock:
                c.state.data["agents"].pop(body.get("agent_id"), None); c.state.data["measurements"].pop(body.get("agent_id"), None); c.state.save()
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "inconnu"})

    def do_HEAD(self):
        self.do_GET()


# ---------------------------------------------------------------------------
# interface locale (une page, sans dépendance)
# ---------------------------------------------------------------------------
UI_HTML = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>si-agent — central local</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--ink:#1d2330;--muted:#6b7280;--line:#e3e6eb;--acc:#2563eb;--warn:#b45309;--crit:#b91c1c;--ok:#15803d}
@media(prefers-color-scheme:dark){:root{--bg:#111418;--card:#1a1f26;--ink:#e6e8ec;--muted:#9aa3b2;--line:#2a313b;--acc:#60a5fa}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:12px 16px;border-bottom:1px solid var(--line);background:var(--card);display:flex;gap:16px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0}main{display:grid;grid-template-columns:minmax(280px,1fr) minmax(320px,2fr);gap:12px;padding:12px;max-width:1500px}
@media(max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:12px}
.card h2{font-size:14px;margin:0 0 8px}.muted{color:var(--muted)}code,pre{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px;overflow:auto;max-height:260px;white-space:pre-wrap;word-break:break-all}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:4px 6px;border-bottom:1px solid var(--line);vertical-align:top}th{font-weight:600;color:var(--muted);font-size:12px}
button{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:6px 10px;cursor:pointer;font:inherit}button.sec{background:transparent;color:var(--acc);border:1px solid var(--acc)}
button:disabled{opacity:.5;cursor:default}input,select,textarea{font:inherit;padding:5px 7px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink);width:100%}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin:6px 0}.row>label{flex:1 1 140px;font-size:12px;color:var(--muted)}.row>label input,.row>label select{margin-top:2px}
.pill{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;border:1px solid var(--line)}.ok{color:var(--ok)}.warning{color:var(--warn)}.critical{color:var(--crit)}.info{color:var(--muted)}
.agent{cursor:pointer}.agent.sel{outline:2px solid var(--acc)}details summary{cursor:pointer;color:var(--muted);font-size:12px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.tabs button{background:transparent;color:var(--ink);border:1px solid var(--line)}.tabs button.on{border-color:var(--acc);color:var(--acc)}
</style></head><body>
<header><h1>si-agent — central local</h1><span class="muted" id="hdr">…</span><span style="flex:1"></span><button class="sec" onclick="load()">Rafraîchir</button></header>
<main>
<div>
 <div class="card"><h2>Enrôler un poste</h2>
  <div class="muted">Jeton : <code id="tok"></code> <button class="sec" onclick="post('/ui/token',{}).then(load)">Renouveler</button></div>
  <div class="muted" style="margin-top:6px">Windows (PowerShell administrateur) :</div><pre id="ol-win"></pre><button class="sec" onclick="copy('ol-win')">Copier</button>
  <div class="muted" style="margin-top:6px">Linux / macOS (racine) :</div><pre id="ol-lin"></pre><button class="sec" onclick="copy('ol-lin')">Copier</button>
  <div class="muted" id="pkg" style="margin-top:6px"></div>
 </div>
 <div class="card"><h2>Agents</h2><table><thead><tr><th>agent</th><th>vu</th><th>IP</th><th>hôte</th></tr></thead><tbody id="agents"></tbody></table></div>
 <div class="card"><h2>Événements</h2><div id="events" style="max-height:420px;overflow:auto"></div></div>
</div>
<div id="panel"><div class="card muted">Choisir un agent dans la liste (il apparaît après son enrôlement et sa première prise de configuration, ~1 min).</div></div>
</main>
<script>
let S=null, sel=null, tab='poste';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function post(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});const j=await r.json();if(!r.ok){alert(j.error||r.status);throw j}return j}
function copy(id){navigator.clipboard&&navigator.clipboard.writeText($(id).textContent)}
function ago(iso){if(!iso)return '—';const d=(Date.now()-Date.parse(iso))/1000;return d<90?Math.round(d)+' s':d<5400?Math.round(d/60)+' min':Math.round(d/3600)+' h'}
async function load(){S=await (await fetch('/ui/state')).json();render()}
function cmd(type,params){if(!sel)return;return post('/ui/command',{agent_id:sel,type,params}).then(load)}
function fv(id){const e=$(id);return e?(e.type==='checkbox'?e.checked:e.value):undefined}
function render(){
 $('hdr').textContent=S.base+' · site '+S.site+' · '+S.agents.length+' agent(s)'+(S.ca_sha256?' · CA '+S.ca_sha256.slice(0,16)+'…':' · HTTP clair');
 $('tok').textContent=S.token;$('ol-win').textContent=S.one_liners.windows;$('ol-lin').textContent=S.one_liners.linux;
 $('pkg').textContent=S.package?('archive '+S.package.name+' ('+Math.round(S.package.size/1024)+' Ko)'):'archive absente (--no-archive)';
 $('agents').innerHTML=S.agents.map(a=>`<tr class="agent ${a.agent_id===sel?'sel':''}" onclick="sel='${esc(a.agent_id)}';render()"><td><b>${esc(a.agent_id)}</b><br><span class="muted">${esc(a.platform||'')}</span></td><td>${ago(a.last_seen)}</td><td>${esc(a.ip||'')}</td><td>${esc(a.hostname||'')}</td></tr>`).join('')||'<tr><td colspan=4 class="muted">aucun</td></tr>';
 $('events').innerHTML=S.events.map(e=>`<div><span class="muted">${esc((e.at||'').replace('T',' ').slice(0,19))}</span> <span class="pill ${esc(e.severity)}">${esc(e.kind)}</span> <b>${esc(e.agent_id)}</b> ${esc(e.message)}${e.details&&Object.keys(e.details).length?` <details><summary>détails</summary><pre>${esc(JSON.stringify(e.details,null,1))}</pre></details>`:''}</div>`).join('')||'<span class="muted">aucun</span>';
 if(!sel||!S.agents.find(a=>a.agent_id===sel)){return}
 const m=S.measurements[sel]||{}, host=(m.host||{}).data||{}, st=(m.startup||{}).data||{}, self=(m['agent-self']||{}).data||{}, wd=(m.watchdog||{}).data||{};
 const cmds=S.commands.filter(c=>c.agent_id===sel);
 const img=S.events.filter(e=>e.agent_id===sel&&/^image-/.test(e.kind));
 const tabs=['poste','image','lanceurs','watchdog','sondes','commandes'];
 const pt=self.point||{};
 let h=`<div class="card"><h2>${esc(sel)} <span class="muted">— ${esc(host.hostname||'')} ${esc(typeof host.os==='string'?host.os:(host.os||{}).name||'')} · CPU ${esc((host.cpu||{}).percent??'?')} % · mémoire ${esc((host.memory||{}).used_percent??'?')} % · empreinte agent ${esc(pt.cpu_core_percent??'?')} % d'un cœur / ${pt.rss_bytes?Math.round(pt.rss_bytes/1048576):'?'} Mo</span>
 <button class="sec" style="float:right" onclick="if(confirm('Oublier cet agent (il devra être réenrôlé) ?'))post('/ui/forget',{agent_id:sel}).then(()=>{sel=null;load()})">Oublier</button></h2>
 <div class="tabs">${tabs.map(t=>`<button class="${t===tab?'on':''}" onclick="tab='${t}';render()">${t}</button>`).join('')}</div>`;
 if(tab==='poste'){h+=`<div class="row"><button onclick="cmd('collect_now',{})">Collecter maintenant</button></div>
  <h2>Alimentation</h2><div class="row"><label>action<select id="p-act"><option value="reboot">redémarrer</option><option value="shutdown">arrêter</option><option value="cancel">annuler</option></select></label>
  <label>délai (s)<input id="p-delay" value="60"></label><label>message<input id="p-msg" value="Redémarrage demandé par la supervision"></label><label><input type="checkbox" id="p-force" style="width:auto"> forcer (session ouverte)</label>
  <button onclick="cmd('power_action',{action:fv('p-act'),delay:+fv('p-delay'),message:fv('p-msg'),force:fv('p-force')})">Envoyer</button></div>
  <h2>Réveil réseau (paquet magique émis par cet agent)</h2><div class="row"><label>MAC du poste à réveiller<input id="w-mac" placeholder="AA:BB:CC:DD:EE:FF"></label><label>diffusion<input id="w-bc" value="255.255.255.255"></label>
  <button onclick="cmd('wol',{mac:fv('w-mac'),broadcast:fv('w-bc')})">Réveiller</button></div>
  <h2>Banc de charge (introspection)</h2><div class="row"><label>minutes<input id="b-min" value="10"></label><label>facteur de cadence<input id="b-f" value="6"></label>
  <button onclick="cmd('bench',{minutes:+fv('b-min'),factor:+fv('b-f')})">Lancer</button><button class="sec" onclick="cmd('bench',{stop:true})">Arrêter</button></div>
  <details><summary>dernière collecte hôte (brut)</summary><pre>${esc(JSON.stringify(host,null,1))}</pre></details>
  <details><summary>empreinte de l'agent (brut)</summary><pre>${esc(JSON.stringify(self,null,1))}</pre></details>`}
 if(tab==='image'){const last=img[0];h+=`<h2>Image complète du poste à chaud (Disk2vhd, VSS)</h2>
  <div class="row"><label>dossier cible (partage ou disque local)<input id="i-target" placeholder="\\\\nas\\images\\p2v ou D:\\images"></label><label>nom<input id="i-name" placeholder="(nom du poste)"></label>
  <label>lecteurs<input id="i-drives" value="*"></label></div><div class="row"><label>URL de disk2vhd64.exe<input id="i-url" value="https://live.sysinternals.com/disk2vhd64.exe"></label><label>SHA-256 attendu (optionnel)<input id="i-sha"></label>
  <label><input type="checkbox" id="i-force" style="width:auto"> forcer (ignorer l'espace)</label><button onclick="cmd('image_host',{target:fv('i-target'),name:fv('i-name')||undefined,drives:fv('i-drives'),tool_url:fv('i-url'),tool_sha256:fv('i-sha')||undefined,force:fv('i-force')})">Lancer l'image</button></div>
  <div class="muted">Refusé si BitLocker protège un volume visé, si la cible manque d'espace (utilisé × 1,1) ou si une image est déjà en cours. 30 à 60 min pour 200-300 Go en Gigabit ; le poste reste en service.</div>
  <h2 style="margin-top:10px">Suivi</h2>${last?`<div><span class="pill ${esc(last.severity)}">${esc(last.kind)}</span> ${esc(last.message)} <span class="muted">${ago(last.at)}</span></div>`:'<div class="muted">aucune image lancée</div>'}
  ${img.slice(0,12).map(e=>`<div class="muted">${esc((e.at||'').replace('T',' ').slice(0,19))} ${esc(e.kind)} — ${esc(e.message)}</div>`).join('')}
  <h2 style="margin-top:10px">Import Proxmox</h2><pre>${esc(S.runbook)}</pre>`}
 if(tab==='lanceurs'){const items=st.items||[];h+=`<h2>Lanceurs au démarrage <span class="muted">(${items.length}, collecte ${ago((m.startup||{}).at)})</span></h2>
  <table><thead><tr><th>type</th><th>nom</th><th>commande</th><th>état</th><th></th></tr></thead><tbody>${items.map(it=>`<tr><td>${esc(it.kind)}<br><span class="muted">${esc(it.scope||'')}</span></td><td>${esc(it.name)}</td><td><code>${esc((it.command||'').slice(0,120))}</code></td><td>${it.enabled===false?'<span class="warning">désactivé</span>':'<span class="ok">actif</span>'}</td>
  <td>${['run','folder','task','service'].includes(it.kind)?`<button class="sec" onclick='cmd("startup_action",{kind:"${esc(it.kind)}",name:${JSON.stringify(it.name).replace(/'/g,"&#39;")},scope:"${esc(it.scope||'machine')}",enable:${it.enabled===false}})'>${it.enabled===false?'activer':'désactiver'}</button>`:''}</td></tr>`).join('')||'<tr><td colspan=5 class="muted">pas encore collecté (Windows seulement)</td></tr>'}</tbody></table>`}
 if(tab==='watchdog'){const lw=cmds.find(c=>c.type==='watchdog_config'&&c.result&&c.result.result&&c.result.result.config);const apps=lw?lw.result.result.config.apps:[];h+=`<h2>Chien de garde applicatif</h2><div class="muted">Une application par ligne : <code>identifiant | processus attendu | commande de relance | heures HH:MM-HH:MM (optionnel)</code></div>
  <textarea id="wd-txt" rows="5" placeholder="pilotage | pilotage.exe | C:\\Apps\\pilotage.exe | 07:00-20:00">${esc(apps.map(a=>[a.id,a.process,a.command||'',a.hours||''].join(' | ')).join('\n'))}</textarea>
  <div class="row"><button onclick="cmd('watchdog_config',{apps:fv('wd-txt').split('\\n').filter(l=>l.trim()).map(l=>{const p=l.split('|').map(s=>s.trim());return {id:p[0],label:p[0],process:p[1],command:p[2]||null,hours:p[3]||null}})})">Appliquer</button><button class="sec" onclick="cmd('watchdog_config',{apps:[]})">Tout retirer</button></div>
  <details open><summary>dernier état</summary><pre>${esc(JSON.stringify(wd,null,1))}</pre></details>`}
 if(tab==='sondes'){h+=`<h2>Mesures reçues</h2>`+Object.keys(m).sort().map(t=>`<details><summary>${esc(t)} — ${ago(m[t].at)} ${m[t].ok===false?'<span class="warning">erreur</span>':''}</summary><pre>${esc(JSON.stringify(m[t].data??m[t].error,null,1))}</pre></details>`).join('')||'<span class="muted">rien encore</span>'}
 if(tab==='commandes'){h+=`<h2>Commande brute</h2><div class="row"><label>type<select id="r-type">${['collect_now','power_action','wol','startup_action','watchdog_config','bench','image_host','block_all','unblock_all','update'].map(t=>`<option>${t}</option>`).join('')}</select></label><label>paramètres (JSON)<input id="r-params" value="{}"></label><button onclick="cmd(fv('r-type'),JSON.parse(fv('r-params')||'{}'))">Envoyer</button></div>
  <h2>Historique</h2><table><thead><tr><th>id</th><th>type</th><th>état</th><th>résultat</th></tr></thead><tbody>${cmds.map(c=>`<tr><td>${esc(c.id)}<br><span class="muted">${ago(c.created_at)}</span></td><td>${esc(c.type)}<br><code>${esc(JSON.stringify(c.params)).slice(0,100)}</code></td><td class="${c.status==='done'?'ok':c.status==='failed'?'critical':'muted'}">${esc(c.status)}</td><td><pre style="max-height:120px">${esc(c.result?JSON.stringify(c.result.result??c.result.error??c.result,null,1):'')}</pre></td></tr>`).join('')||'<tr><td colspan=4 class="muted">aucune</td></tr>'}</tbody></table>`}
 h+='</div>';$('panel').innerHTML=h;
}
load();setInterval(load,5000);
</script></body></html>"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="central local de test pour si-agent")
    ap.add_argument("--listen", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=6444)
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--site", default="local")
    ap.add_argument("--http", action="store_true", help="HTTP clair (test seulement)")
    ap.add_argument("--advertise-ip", help="adresse annoncée aux agents (défaut : IP de sortie du poste)")
    ap.add_argument("--interval", type=int, default=60, help="host_interval_seconds servi aux agents")
    ap.add_argument("--plugins", default="", help="plugins livrés à activer : web-audit,windows-probe,...")
    ap.add_argument("--plugin-arg", action="append", help='arguments d\'un plugin : web-audit="--urls https://x"')
    ap.add_argument("--rebuild-archive", action="store_true")
    ap.add_argument("--no-archive", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    central = Central(args)
    Handler.central = central
    httpd = ThreadingHTTPServer((args.listen, args.port), Handler)
    httpd.daemon_threads = True
    if not args.http:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(central.crt, central.key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    ol = central.one_liners()
    print("si-agent central local : %s  (interface : %s/ ; données : %s)" % (central.base, central.base, central.data_dir))
    if central.ca_sha:
        print("CA auto-signée, empreinte SHA-256 : %s" % central.ca_sha)
    print("archive : %s" % (central.package or "aucune"))
    print("jeton d'enrôlement : %s" % central.state.data["token"])
    print("\nWindows (PowerShell administrateur) :\n  %s\n\nLinux / macOS :\n  %s\n" % (ol["windows"], ol["linux"]))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
