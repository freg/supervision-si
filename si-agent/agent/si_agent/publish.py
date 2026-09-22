# -*- coding: utf-8 -*-
"""Publication locale d'un tableau (livraison #547) : l'agent sert sur le
LAN de son site une page « État du réseau » (charte Simple du hub, sans
aucune dépendance) et le JSON qu'il relève chaque minute au central par
son canal signé. Rien d'autre n'est exposé : deux chemins, lecture seule,
pas de clé, pas d'identifiant interne. Logique pure testée
(tests/test_publish.py) ; le serveur est un http.server en fil d'exécution."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STALE_AFTER = 300  # secondes : au-delà, la page dit que l'information n'est plus fraîche

PAGE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--ink:#111;--paper:#fff;--rule:#222;--grey:#666;--soft:#f2f2f2;--alert:#a00}
*{box-sizing:border-box}html,body{margin:0;background:var(--paper);color:var(--ink);font-family:Georgia,"Times New Roman",serif;font-size:17px;line-height:1.45}
main{max-width:760px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:1.9rem;margin:0;border-bottom:3px double var(--rule);padding-bottom:6px}
.kicker{font-family:system-ui,sans-serif;font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;color:var(--grey);margin:0 0 4px}
.stamp{font-family:system-ui,sans-serif;font-size:.8rem;color:var(--grey);margin:8px 0 0}
.stamp.stale{color:var(--alert)}
.summary{font-size:1.35rem;margin:18px 0 6px}
.phrases{list-style:none;padding:0;margin:0 0 12px}.phrases li{border-left:3px solid var(--alert);padding:6px 10px;margin:8px 0;background:var(--soft)}
table{width:100%;border-collapse:collapse;margin-top:8px}
th{text-align:left;font-family:system-ui,sans-serif;font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;color:var(--grey);border-bottom:1px solid var(--rule);padding:6px 4px}
td{padding:8px 4px;border-bottom:1px solid #ddd;vertical-align:top}td.r{text-align:right}
.etat{font-family:system-ui,sans-serif;font-size:.85rem;text-transform:uppercase;letter-spacing:.06em;border-bottom:3px solid var(--rule);white-space:nowrap}
.etat.panne{border-color:var(--alert);color:var(--alert)}.etat.degrade{border-color:var(--grey);color:var(--grey);border-style:dashed}
footer{margin-top:30px;font-family:system-ui,sans-serif;font-size:.8rem;color:var(--grey);border-top:1px solid var(--rule);padding-top:10px}
@media (max-width:640px){td:nth-child(2),th:nth-child(2){display:none}}
</style></head><body><main>
<p class="kicker">Réseau du site</p><h1>__TITLE__</h1>
<p class="stamp" id="stamp">Chargement…</p>
<div id="sites"></div>
<footer>Page servie sur le réseau local par la sonde de supervision ; se rafraîchit toute seule. Un problème qui n'y figure pas ? Prévenez le service informatique.</footer>
</main><script>
var MOTS={online:"en ligne",offline:"hors ligne",alerting:"en alerte",inconnu:"sans relevé"};
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function when(ts){return ts?new Date(ts*1000).toLocaleString("fr-FR",{dateStyle:"long",timeStyle:"short"}):"—"}
function pct(v){return v==null?"—":(v*100).toFixed(2)+" %"}
function load(){fetch("board.json",{cache:"no-store"}).then(function(r){return r.json()}).then(function(b){
 var st=document.getElementById("stamp");
 if(!b||!b.at){st.textContent="Aucune information reçue pour le moment.";return}
 st.className="stamp"+(b.stale?" stale":"");st.textContent="Situation au "+when(b.at)+(b.stale?" — information ancienne, la sonde n'a pas pu se mettre à jour":"")+(b.error?" — "+b.error:"");
 document.getElementById("sites").innerHTML=(b.sites||[]).map(function(s){return '<section>'+(s.name?'<p class="kicker">'+esc(s.name)+'</p>':'')+'<p class="summary">'+esc(s.resume)+'</p>'+
  '<ul class="phrases">'+(s.phrases||[]).map(function(p){return '<li>'+esc(p)+'</li>'}).join("")+'</ul>'+
  '<p>Disponibilité sur '+esc(s.hours||24)+' h : <strong>'+pct(s.availability)+'</strong> · incidents : <strong>'+esc(s.incidents)+'</strong> · '+esc(s.online)+' en ligne sur '+esc(s.total)+'.</p>'+
  '<table><thead><tr><th>Équipement</th><th>Modèle</th><th>État</th><th>Depuis</th><th class="r">Disponibilité</th></tr></thead><tbody>'+
  (s.devices||[]).map(function(d){var k=d.status==="online"?"ok":d.status==="offline"?"panne":"degrade";return '<tr><td>'+esc(d.name)+'</td><td>'+esc(d.model)+'</td><td><span class="etat '+k+'">'+esc(MOTS[d.status]||d.status)+'</span></td><td>'+when(d.since)+'</td><td class="r">'+pct(d.availability)+'</td></tr>'}).join("")+
  '</tbody></table></section>'}).join("");
}).catch(function(){document.getElementById("stamp").textContent="La sonde ne répond pas."})}
load();setInterval(load,60000);
</script></body></html>
"""


def with_age(payload, now=None):
    """Le JSON servi : le dernier contenu reçu + son âge et un drapeau
    `stale` (plus de STALE_AFTER secondes)."""
    now = now if now is not None else time.time()
    if not payload or not payload.get("at"):
        return {"at": None, "stale": True, "sites": []}
    age = max(0, int(now - payload.get("received_at", payload["at"])))
    out = dict(payload)
    out["age_seconds"] = age
    out["stale"] = age > STALE_AFTER
    return out


def render_page(title):
    return PAGE.replace("__TITLE__", (title or "État du réseau").replace("<", "&lt;").replace(">", "&gt;"))


class PublishServer(object):
    """Serveur HTTP minimal, lecture seule, deux chemins. `payload` est
    remplacé par l'agent à chaque relevé ; `stop()` libère le port."""

    def __init__(self, port, title, bind="0.0.0.0", clock=time.time):
        self.port, self.title, self.bind, self.clock = port, title, bind, clock
        self.payload = None
        self._srv = None
        self._thread = None
        self.started_at = None

    def set_payload(self, payload):
        self.payload = payload

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence : le journal de l'agent suffit
                pass

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path in ("/", "/index.html"):
                    body = render_page(owner.title).encode("utf-8"); ctype = "text/html; charset=utf-8"
                elif path == "/board.json":
                    body = json.dumps(with_age(owner.payload, owner.clock()), ensure_ascii=False).encode("utf-8"); ctype = "application/json; charset=utf-8"
                else:
                    self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
                self.send_response(200)
                self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers(); self.wfile.write(body)

        self._srv = ThreadingHTTPServer((self.bind, self.port), Handler)
        self._srv.daemon_threads = True
        self.port = self._srv.server_address[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, name="si-agent-publish", daemon=True)
        self._thread.start()
        self.started_at = self.clock()
        return self.port

    def stop(self):
        if self._srv:
            self._srv.shutdown(); self._srv.server_close(); self._srv = None
