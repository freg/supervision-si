# -*- coding: utf-8 -*-
"""Essai de bout en bout LOCAL du bastion si-proxy (#452) : genere une CA +
un cert serveur, lance relais + shim + client (client.py), et verifie un shell
qui repond, le proxy CONNECT et HTTP, et le rejet d'un mauvais jeton. Purement
local (loopback, certs jetables) ; a lancer a la main : python3 tests/e2e_local.py
"""
import os, socket, ssl, subprocess, sys, threading, time, http.server, tempfile

import pathlib
ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
TMP = tempfile.mkdtemp(prefix="siproxy-e2e-")
HOST_TOKEN, CLIENT_TOKEN = "HTOKEN-abc", "CTOKEN-freg"
RELAY_PORT, PROXY_PORT, TARGET_PORT = 6450, 6451, 6470

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
    "--bind","127.0.0.1","--port",str(RELAY_PORT),"--host-token",HOST_TOKEN,"--client-token",CLIENT_TOKEN,"--log-level","WARNING"],
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

for p in (proxy,cli,shim,relay):
    try: p.kill()
    except Exception: pass
httpd.shutdown()
print("\nRESULTAT:", "TOUT VERT" if not fails else "ECHECS: "+",".join(fails))
sys.exit(1 if fails else 0)
