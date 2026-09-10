# -*- coding: utf-8 -*-
"""Essai de bout en bout LOCAL du bastion si-proxy (#452) : genere une CA +
un cert serveur, lance relais + shim + client (client.py), et verifie un shell
qui repond, le proxy CONNECT et HTTP, le rejet d'un mauvais jeton, puis (#453)
le bannissement apres N echecs, l'interface de controle (/status, /audit,
/unban, /disable, /enable, /sessions/<id>/kill) et le journal d'audit. Purement
local (loopback, certs jetables) ; a lancer a la main : python3 tests/e2e_local.py
"""
import os, socket, ssl, subprocess, sys, threading, time, http.server, http.client, json, tempfile

import pathlib
ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
TMP = tempfile.mkdtemp(prefix="siproxy-e2e-")
HOST_TOKEN, CLIENT_TOKEN = "HTOKEN-abc", "CTOKEN-freg"
RELAY_PORT, PROXY_PORT, TARGET_PORT, CTRL_PORT = 6450, 6451, 6470, 6452
ADMIN_TOKEN = "ADMIN-xyz"
AUDIT = os.path.join(TMP, "audit.jsonl")

def sh(cmd): subprocess.check_call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Une IP NON-loopback pour la cible « hub/LAN » (127.0.0.1 est refusé par le
# shim). Selon l'environnement (VM isolée...) il peut n'y en avoir aucune :
# on saute alors proprement les tests de navigation plutôt que de planter.
def _pick_ip():
    try:
        h = socket.gethostbyname(socket.gethostname())
        if h and not h.startswith("127."):
            return h
    except OSError:
        pass
    try:
        for tok in subprocess.check_output("hostname -I", shell=True).split():
            ip = tok.decode()
            if ip and not ip.startswith("127.") and ":" not in ip:
                return ip
    except Exception:  # noqa: BLE001
        pass
    return None
IP = _pick_ip()
print("IP cible (simule hub/LAN):", IP or "(aucune IP routable -- tests navigation sautés)")

# --- certs : CA + cert serveur (SAN localhost) ---
sh(f"openssl req -x509 -newkey rsa:2048 -nodes -keyout {TMP}/ca.key -out {TMP}/ca.crt -days 2 -subj '/CN=si-proxy-CA'")
sh(f"openssl req -newkey rsa:2048 -nodes -keyout {TMP}/s.key -out {TMP}/s.csr -subj '/CN=localhost'")
open(f"{TMP}/ext.cnf","w").write("subjectAltName=DNS:localhost,IP:127.0.0.1\n")
sh(f"openssl x509 -req -in {TMP}/s.csr -CA {TMP}/ca.crt -CAkey {TMP}/ca.key -CAcreateserial -out {TMP}/s.crt -days 2 -extfile {TMP}/ext.cnf")

# --- serveur cible factice (le "hub"/"LAN") ---
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body=b"PAGE-DU-HUB-OK"; self.send_response(200); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,*a): pass
httpd = http.server.HTTPServer(("0.0.0.0", TARGET_PORT), H)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

env = dict(os.environ, PYTHONPATH=ROOT)
relay = subprocess.Popen([sys.executable,"-m","siproxy.relay","--cert",f"{TMP}/s.crt","--key",f"{TMP}/s.key",
    "--bind","127.0.0.1","--port",str(RELAY_PORT),"--host-token",HOST_TOKEN,"--client-token",CLIENT_TOKEN,"--log-level","WARNING",
    "--audit-log",AUDIT,"--control-port",str(CTRL_PORT),"--admin-token",ADMIN_TOKEN,
    "--ban-threshold","3","--ban-window","60","--ban-minutes","1"],
    env=env, cwd=".", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
shim = subprocess.Popen([sys.executable,"-m","siproxy.hostshim","--relay",f"localhost:{RELAY_PORT}","--ca",f"{TMP}/ca.crt",
    "--token",HOST_TOKEN,"--shell-user","root","--log-level","WARNING"], env=env, cwd=".", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2.0)

fails=[]

# --- Test 1 : shell via client.py (stdin gardé ouvert pour maîtriser le tempo) ---
cli = subprocess.Popen([sys.executable,"-m","siproxy.client","shell","--relay",f"localhost:{RELAY_PORT}",
    "--ca",f"{TMP}/ca.crt","--token",CLIENT_TOKEN], env=env, cwd=".",
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
buf=bytearray()
def rd():
    while True:
        b=cli.stdout.read(1)
        if not b: break
        buf.extend(b)
threading.Thread(target=rd, daemon=True).start()
time.sleep(1.0)
cli.stdin.write(b"echo BASTION_OK_$((6*7))\n"); cli.stdin.flush()
time.sleep(1.5)
out=bytes(buf).decode("utf-8","replace")
if "BASTION_OK_42" in out: print("Test 1 shell : OK (commande exécutée sous le shell du host)")
else: fails.append("shell"); print("Test 1 shell : ECHEC ; sortie=",repr(out[-200:]))
try: cli.stdin.write(b"exit\n"); cli.stdin.flush()
except OSError: pass
time.sleep(0.3); cli.terminate()

# --- Test 2 : proxy CONNECT + http absolu ---
proxy = subprocess.Popen([sys.executable,"-m","siproxy.client","proxy","--relay",f"localhost:{RELAY_PORT}",
    "--ca",f"{TMP}/ca.crt","--token",CLIENT_TOKEN,"--listen",f"127.0.0.1:{PROXY_PORT}"], env=env, cwd=".", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)

def proxy_connect_get():
    c=socket.create_connection(("127.0.0.1",PROXY_PORT),5)
    c.sendall(f"CONNECT {IP}:{TARGET_PORT} HTTP/1.1\r\nHost: {IP}\r\n\r\n".encode())
    resp=c.recv(200)
    if b"200" not in resp: return "CONNECT refusé: "+repr(resp)
    c.sendall(f"GET / HTTP/1.0\r\nHost: {IP}\r\n\r\n".encode())
    data=b""
    while True:
        b=c.recv(4096)
        if not b: break
        data+=b
    c.close()
    return "OK" if b"PAGE-DU-HUB-OK" in data else "corps inattendu: "+repr(data[-120:])

def proxy_abs_get():
    c=socket.create_connection(("127.0.0.1",PROXY_PORT),5)
    c.sendall(f"GET http://{IP}:{TARGET_PORT}/ HTTP/1.1\r\nHost: {IP}\r\nConnection: close\r\n\r\n".encode())
    data=b""
    while True:
        b=c.recv(4096)
        if not b: break
        data+=b
    c.close()
    return "OK" if b"PAGE-DU-HUB-OK" in data else "corps inattendu: "+repr(data[-120:])

if IP:
    r1=proxy_connect_get()
    print("Test 2a proxy CONNECT (https-style) :", "OK" if r1=="OK" else "ECHEC "+r1)
    if r1!="OK": fails.append("connect")
    r2=proxy_abs_get()
    print("Test 2b proxy HTTP absolu :", "OK" if r2=="OK" else "ECHEC "+r2)
    if r2!="OK": fails.append("http")
else:
    print("Test 2 proxy CONNECT/HTTP : SAUTÉ (pas d'IP routable dans cet environnement)")

# --- Test 3 : refus (mauvais jeton, cible loopback) ---
def bad_token():
    try:
        ctx=ssl.create_default_context(cafile=f"{TMP}/ca.crt")
        c=ctx.wrap_socket(socket.create_connection(("127.0.0.1",RELAY_PORT),5), server_hostname="localhost")
        c.sendall(b'{"role":"client","type":"data","token":"MAUVAIS","kind":"shell"}\n')
        resp=c.recv(200); c.close()
        return b"refus" in resp or b"error" in resp
    except Exception as e: return False
print("Test 3 jeton refusé :", "OK" if bad_token() else "ECHEC")
if not bad_token(): fails.append("auth")


# --- #453 : interface de contrôle ---
def ctrl(method, path, token=ADMIN_TOKEN):
    ctx=ssl.create_default_context(cafile=f"{TMP}/ca.crt")
    c=http.client.HTTPSConnection("localhost", CTRL_PORT, context=ctx, timeout=5)
    c.request(method, path, headers={"X-Si-Proxy-Admin": token} if token else {})
    r=c.getresponse(); body=r.read(); c.close()
    try: return r.status, json.loads(body.decode("utf-8"))
    except ValueError: return r.status, body

# Test 4 : /status + /audit (le refus du test 3 doit y figurer, sans jeton)
st, body = ctrl("GET","/status")
ok4 = st==200 and body.get("host_connected") is True and body.get("enabled") is True and body["counters"]["refused"]>=2
print("Test 4a contrôle /status :", "OK" if ok4 else "ECHEC %s %s"%(st,body))
if not ok4: fails.append("status")
st, body = ctrl("GET","/audit?limit=50")
evs=[e["event"] for e in body.get("audit",[])]
raw=open(AUDIT,encoding="utf-8").read()
ok4b = st==200 and "refused" in evs and "session-start" in evs and "session-end" in evs and "CTOKEN" not in raw and "HTOKEN" not in raw and "MAUVAIS" not in raw
print("Test 4b contrôle /audit + journal sans secret :", "OK" if ok4b else "ECHEC %s %s"%(st,evs))
if not ok4b: fails.append("audit")
st,_ = ctrl("GET","/status", token="FAUX")
print("Test 4c contrôle sans jeton admin -> 403 :", "OK" if st==403 else "ECHEC %s"%st)
if st!=403: fails.append("ctrl-auth")

# Test 5 : bannissement maison (seuil 3 : 2 refus du test 3 + 1 = ban), puis /unban
bad_token()
def banned_now():
    try:
        ctx=ssl.create_default_context(cafile=f"{TMP}/ca.crt")
        c=ctx.wrap_socket(socket.create_connection(("127.0.0.1",RELAY_PORT),5), server_hostname="localhost")
        c.settimeout(3)
        c.sendall(b'{"role":"client","type":"data","token":"'+CLIENT_TOKEN.encode()+b'","kind":"shell"}\n')
        resp=c.recv(200); c.close()
        return resp==b""      # connexion fermée sans un mot = bannie (même avec le BON jeton)
    except (ssl.SSLError, OSError):
        return True
st, body = ctrl("GET","/status")
ips=[b["ip"] for b in body.get("banned",[])]
ok5 = banned_now() and "127.0.0.1" in ips
print("Test 5a ban après 3 échecs (bon jeton rejeté, IP listée) :", "OK" if ok5 else "ECHEC bannis=%s"%ips)
if not ok5: fails.append("ban")
st, body = ctrl("POST","/unban/127.0.0.1")
ok5b = st==200 and body.get("unbanned") is True and not banned_now()
print("Test 5b /unban puis accès rétabli :", "OK" if ok5b else "ECHEC %s %s"%(st,body))
if not ok5b: fails.append("unban")

# Test 6 : /disable refuse les nouvelles sessions, /enable les rétablit
def shell_refused_msg():
    ctx=ssl.create_default_context(cafile=f"{TMP}/ca.crt")
    c=ctx.wrap_socket(socket.create_connection(("127.0.0.1",RELAY_PORT),5), server_hostname="localhost")
    c.settimeout(5)
    c.sendall(b'{"role":"client","type":"data","token":"'+CLIENT_TOKEN.encode()+b'","kind":"shell"}\n')
    resp=c.recv(300); c.close(); return resp
ctrl("POST","/disable")
r=shell_refused_msg()
ok6 = "d\u00e9sactiv" in r.decode("utf-8","replace") or "désactiv" in r.decode("utf-8","replace")
st, body = ctrl("POST","/enable")
ok6 = ok6 and body.get("enabled") is True
print("Test 6 /disable refuse, /enable rétablit :", "OK" if ok6 else "ECHEC %r"%r)
if not ok6: fails.append("disable")

# Test 7 : session en cours visible dans /status puis tuée par /sessions/<id>/kill
cli2 = subprocess.Popen([sys.executable,"-m","siproxy.client","shell","--relay",f"localhost:{RELAY_PORT}",
    "--ca",f"{TMP}/ca.crt","--token",CLIENT_TOKEN], env=env, cwd=".",
    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
st, body = ctrl("GET","/status")
sess=body.get("sessions",[])
sid = sess[-1]["session"] if sess else None
ok7 = st==200 and sid is not None and sess[-1]["kind"]=="shell"
st, body = ctrl("POST","/sessions/%s/kill"%sid)
try: cli2.wait(5); exited=True
except subprocess.TimeoutExpired: exited=False; cli2.kill()
st2, body2 = ctrl("GET","/status")
ok7 = ok7 and body.get("killed") is True and exited and body2["counters"]["active"]==0
print("Test 7 session listée puis tuée (client sorti) :", "OK" if ok7 else "ECHEC sid=%s killed=%s exited=%s active=%s"%(sid,body.get("killed"),exited,body2["counters"]))
if not ok7: fails.append("kill")

for p in (proxy,cli,shim,relay):
    try: p.kill()
    except Exception: pass
httpd.shutdown()
print("\nRESULTAT:", "TOUT VERT" if not fails else "ECHECS: "+",".join(fails))
sys.exit(1 if fails else 0)
