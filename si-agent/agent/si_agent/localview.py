# -*- coding: utf-8 -*-
"""Vue locale de transparence (livraison #819) : l'agent sert, sur le poste
lui-même (127.0.0.1 par défaut), une page en LECTURE SEULE qui montre à
l'administrateur du poste ce que l'agent relève et envoie au central, sa
configuration (secrets masqués) et les sondes qui y sont activées.

Aucune action possible depuis cette page. Écoute hors boucle locale
seulement si la configuration le demande, et alors seulement pour les
adresses de la liste `allow` (la boucle locale est toujours admise).
Logique pure testée (tests/test_localview.py) ; serveur http.server en fil
d'exécution, comme la publication locale (#547)."""
import ipaddress
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT = {"enabled": False, "port": 8090, "bind": "127.0.0.1", "allow": []}
MAX_TASKS = 200
MAX_EVENTS = 200
MASK = "•••• (masqué)"
_SECRET_KEY = re.compile(r"(secret|token|password|passwd|pwd|private|apikey|api_key|credential)", re.I)

# Libellés lisibles des tâches de l'agent (les sondes : « plugin:<id> »)
TASKS = {
    "host": "État du système : processeur, mémoire, disques, services, ports en écoute, journaux",
    "inventory": "Inventaire matériel et logiciel",
    "netview": "Vue réseau passive : interfaces, passerelle, routes, voisins",
    "agent-self": "Empreinte de l'agent lui-même (charge, durée des relevés)",
    "risks": "Constats de risque calculés sur le poste",
    "event": "Journal de l'agent (démarrage, configuration, erreurs)",
    "startup": "Lanceurs au démarrage",
    "watchdog": "Chien de garde applicatif",
    "winupdate": "Windows Update",
    "protection": "Protection (antivirus, pare-feu, chiffrement)",
    "rdp": "Bureau à distance",
    "ext-audit": "Audit extérieur",
}


def task_label(task):
    t = str(task or "")
    if t.startswith("plugin:"):
        return "Sonde « %s »" % t[7:]
    return TASKS.get(t, t)


def merged(cfg_value):
    """Configuration effective de la vue : valeurs par défaut + agent.json / central."""
    out = dict(DEFAULT)
    if isinstance(cfg_value, dict):
        out.update({k: v for k, v in cfg_value.items() if k in DEFAULT})
    try:
        out["port"] = int(out["port"])
    except (TypeError, ValueError):
        out["port"] = DEFAULT["port"]
    out["bind"] = str(out.get("bind") or "127.0.0.1")
    out["allow"] = [str(a) for a in (out.get("allow") or []) if a]
    out["enabled"] = bool(out.get("enabled"))
    return out


def allowed(client_ip, allow):
    """Boucle locale toujours admise ; sinon l'adresse doit figurer dans `allow` (IP ou CIDR)."""
    try:
        ip = ipaddress.ip_address(str(client_ip).split("%")[0])
    except ValueError:
        return False
    if ip.is_loopback or (getattr(ip, "ipv4_mapped", None) and ip.ipv4_mapped.is_loopback):
        return True
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    for a in allow or []:
        try:
            if ip in ipaddress.ip_network(str(a), strict=False):
                return True
        except ValueError:
            continue
    return False


def sanitize(value, key=""):
    """Copie de la configuration où toute clé d'allure secrète est masquée (récursif)."""
    if key and _SECRET_KEY.search(str(key)) and value not in (None, "", [], {}):
        return MASK
    if isinstance(value, dict):
        return {k: sanitize(v, k) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    return value


class Recorder(object):
    """Dernière mesure par tâche + derniers événements, tels que mis en file vers le central."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self._lock = threading.Lock()
        self.tasks = {}
        self.events = []

    def record(self, m):
        if not isinstance(m, dict):
            return
        task = str(m.get("task") or "?")
        try:
            size = len(json.dumps(m.get("data"), ensure_ascii=False, default=str).encode("utf-8"))
        except (TypeError, ValueError):
            size = 0
        with self._lock:
            if task == "event":
                d = m.get("data") or {}
                self.events.append({"at": m.get("at"), "kind": d.get("kind"), "severity": d.get("severity"), "message": d.get("message")})
                del self.events[:-MAX_EVENTS]
            cur = self.tasks.get(task)
            if cur is None and len(self.tasks) >= MAX_TASKS:
                return
            count = (cur or {}).get("count", 0) + 1
            self.tasks[task] = {"task": task, "label": task_label(task), "at": m.get("at"), "ok": bool(m.get("ok", True)),
                                "error": m.get("error"), "size": size, "count": count,
                                "data": m.get("data") if task != "event" else None}

    def snapshot(self):
        with self._lock:
            return [dict(v) for v in self.tasks.values()], list(self.events)


def plugin_rows(manifests, enabled_fn, blocked_fn, next_run, last):
    """Sondes présentes sur le poste : cadence, état, dernier passage (pure)."""
    rows = []
    for m in manifests or []:
        pid = m.get("id")
        lt = last.get("plugin:%s" % pid) or {}
        blocked = bool(blocked_fn(m))
        enabled = bool(enabled_fn(m))
        rows.append({"id": pid, "version": str(m.get("version") or ""), "description": m.get("description") or "",
                     "interval_seconds": m.get("interval_seconds"), "privileged": bool(m.get("privileged")),
                     "source": m.get("source") or "", "state": "bloquée" if blocked else ("active" if enabled else "inactive"),
                     "next_run": next_run.get(pid), "last_at": lt.get("at"), "last_ok": lt.get("ok"), "last_error": lt.get("error")})
    rows.sort(key=lambda r: (r["state"] != "active", str(r["id"])))
    return rows


def build_view(info, cfg, plugins, recorder, now=None):
    """JSON servi par /view.json."""
    tasks, events = recorder.snapshot() if recorder else ([], [])
    tasks.sort(key=lambda t: (t["task"] == "event", str(t["task"])))
    return {"now": now if now is not None else time.time(), "agent": info, "plugins": plugins,
            "tasks": tasks, "events": list(reversed(events)), "config": sanitize(cfg)}


PAGE = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent de supervision — ce qu'il relève</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--line:#2a2f3a;--ink:#e6e8ec;--muted:#9aa3b2;--accent:#5aa9ff;--ok:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:1.45rem;margin:0 0 4px}h2{font-size:1.1rem;margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.muted{color:var(--muted)}.lede{color:var(--muted);margin:0 0 14px;max-width:80ch}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.card b{display:block;font-size:.78rem;color:var(--muted);font-weight:500;text-transform:uppercase;letter-spacing:.05em}
nav{display:flex;gap:6px;flex-wrap:wrap;margin:16px 0 0}nav button{font:inherit;background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:5px 12px;cursor:pointer}
nav button.on{border-color:var(--accent);color:var(--accent)}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:8px}
th{text-align:left;font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:7px 8px;border-bottom:1px solid var(--line)}
td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
pre{white-space:pre-wrap;word-break:break-word;background:#0b0d11;border:1px solid var(--line);border-radius:6px;padding:8px;max-height:420px;overflow:auto;font-size:12.5px}
details summary{cursor:pointer;color:var(--accent)}code{font-size:.92em}
.note{background:var(--panel);border-left:3px solid var(--accent);padding:8px 12px;margin:14px 0;border-radius:4px}
footer{margin-top:30px;color:var(--muted);font-size:.85rem}
</style></head><body><main>
<h1 id="titre">Agent de supervision</h1>
<p class="lede">Cette page est servie par l'agent sur ce serveur, en <strong>lecture seule</strong>. Elle montre exactement ce que l'agent relève et envoie à son central, sa configuration (secrets masqués) et les sondes activées. Elle ne permet aucune action.</p>
<div class="cards" id="cartes"></div>
<div class="note" id="suspendre"></div>
<nav id="onglets"></nav>
<section id="vue"></section>
<footer id="pied">Chargement…</footer>
</main><script>
var V=null,ONG="remonte";
var ONGLETS=[["remonte","Ce qui remonte"],["sondes","Sondes"],["evenements","Journal"],["config","Configuration"]];
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function quand(v){if(v==null||v==="")return"—";var d=typeof v==="number"?new Date(v*1000):new Date(v);return isNaN(d)?esc(v):d.toLocaleString("fr-FR",{dateStyle:"short",timeStyle:"medium"})}
function taille(n){return n==null?"—":n<1024?n+" o":(n/1024).toFixed(1)+" Ko"}
function duree(s){if(!s)return"—";s=+s;return s<120?s+" s":s<7200?Math.round(s/60)+" min":Math.round(s/3600)+" h"}
function cartes(a){var c=[["Poste",a.host],["Agent",a.agent_id],["Version",a.version],["Site",a.site],["Central",a.central_url],
 ["Dernier contact central",quand(a.last_central_contact)],["Mesures en attente d'envoi",a.pending==null?"—":a.pending],["Démarré",quand(a.started_at)],
 ["État",a.blocked?'<span class="bad">suspendu</span> — '+esc(a.block_reason||""):'<span class="ok">actif</span>']];
 return c.map(function(x){return '<div class="card"><b>'+x[0]+'</b>'+(x[0]==="État"?x[1]:esc(x[1]))+'</div>'}).join("")}
function remonte(){if(!V.tasks.length)return '<p class="muted">Rien n\'a encore été relevé depuis le démarrage de l\'agent.</p>';
 return '<table><thead><tr><th>Relevé</th><th>Dernier envoi</th><th>Depuis le démarrage</th><th>Taille</th><th>Résultat</th></tr></thead><tbody>'+
 V.tasks.map(function(t){return '<tr><td>'+esc(t.label)+'<div class="muted"><code>'+esc(t.task)+'</code></div>'+(t.data!=null?'<details><summary>voir le contenu envoyé</summary><pre>'+esc(JSON.stringify(t.data,null,2))+'</pre></details>':'')+
 '</td><td>'+quand(t.at)+'</td><td>'+esc(t.count)+'</td><td>'+taille(t.size)+'</td><td>'+(t.ok?'<span class="ok">ok</span>':'<span class="bad">échec</span> '+esc(t.error||""))+'</td></tr>'}).join("")+'</tbody></table>'}
function sondes(){if(!V.plugins.length)return '<p class="muted">Aucune sonde installée : l\'agent ne fait que ses relevés de base (onglet « Ce qui remonte »).</p>';
 return '<table><thead><tr><th>Sonde</th><th>État</th><th>Cadence</th><th>Dernier passage</th><th>Résultat</th></tr></thead><tbody>'+
 V.plugins.map(function(p){var k=p.state==="active"?"ok":p.state==="bloquée"?"bad":"muted";return '<tr><td><strong>'+esc(p.id)+'</strong> <span class="muted">v'+esc(p.version)+(p.privileged?' · droits élevés':'')+'</span><div class="muted">'+esc(p.description)+'</div></td><td class="'+k+'">'+esc(p.state)+
 '</td><td>'+duree(p.interval_seconds)+'</td><td>'+quand(p.last_at)+'</td><td>'+(p.last_at==null?"—":p.last_ok?'<span class="ok">ok</span>':'<span class="bad">échec</span> '+esc(p.last_error||""))+'</td></tr>'}).join("")+'</tbody></table>'}
function evenements(){if(!V.events.length)return '<p class="muted">Aucun événement depuis le démarrage.</p>';
 return '<table><thead><tr><th>Quand</th><th>Gravité</th><th>Événement</th></tr></thead><tbody>'+V.events.map(function(e){var k=e.severity==="critical"?"bad":e.severity==="warning"?"warn":"muted";
 return '<tr><td>'+quand(e.at)+'</td><td class="'+k+'">'+esc(e.severity)+'</td><td>'+esc(e.message)+' <span class="muted"><code>'+esc(e.kind)+'</code></span></td></tr>'}).join("")+'</tbody></table>'}
function config(){return '<pre>'+esc(JSON.stringify(V.config,null,2))+'</pre>'}
function rendre(){document.getElementById("onglets").innerHTML=ONGLETS.map(function(o){return '<button type="button" class="'+(o[0]===ONG?"on":"")+'" onclick="ONG=\''+o[0]+'\';rendre()">'+o[1]+'</button>'}).join("");
 if(!V)return;var f={remonte:remonte,sondes:sondes,evenements:evenements,config:config}[ONG];document.getElementById("vue").innerHTML='<h2>'+ONGLETS.filter(function(o){return o[0]===ONG})[0][1]+'</h2>'+f()}
function charger(){fetch("view.json",{cache:"no-store"}).then(function(r){return r.json()}).then(function(v){V=v;var a=v.agent||{};
 document.getElementById("titre").textContent="Agent de supervision — "+(a.host||a.agent_id||"");
 document.getElementById("cartes").innerHTML=cartes(a);
 document.getElementById("suspendre").innerHTML="Pour <strong>suspendre toute collecte</strong> sans désinstaller : créer le fichier <code>"+esc(a.block_file||"BLOCKED")+"</code> (le supprimer pour reprendre). Pour désinstaller : <code>"+esc(a.uninstall||"")+"</code>";
 document.getElementById("pied").textContent="Mis à jour le "+quand(v.now)+" · rafraîchissement automatique toutes les 30 s.";rendre()})
 .catch(function(){document.getElementById("pied").textContent="L'agent ne répond pas."})}
rendre();charger();setInterval(charger,30000);
</script></body></html>
"""


class LocalViewServer(object):
    """Serveur HTTP minimal, lecture seule : `/` et `/view.json`. `provider()` rend le JSON à chaque requête."""

    def __init__(self, port, provider, bind="127.0.0.1", allow=None):
        self.port, self.provider, self.bind, self.allow = port, provider, bind, list(allow or [])
        self._srv = None
        self._thread = None

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY"); self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers(); self.wfile.write(body)

            def do_GET(self):
                if not allowed(self.client_address[0], owner.allow):
                    return self._send(403, b"interdit", "text/plain; charset=utf-8")
                path = self.path.split("?", 1)[0]
                if path in ("/", "/index.html"):
                    return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                if path == "/view.json":
                    try:
                        data = owner.provider()
                    except Exception as exc:  # noqa: BLE001 -- la page dit l'erreur, l'agent continue
                        data = {"error": str(exc)}
                    return self._send(200, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")
                return self._send(404, b"", "text/plain")

        self._srv = ThreadingHTTPServer((self.bind, self.port), Handler)
        self._srv.daemon_threads = True
        self.port = self._srv.server_address[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, name="si-agent-localview", daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        if self._srv:
            self._srv.shutdown(); self._srv.server_close(); self._srv = None
