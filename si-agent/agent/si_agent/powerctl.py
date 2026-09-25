# -*- coding: utf-8 -*-
"""Alimentation du poste et réveil réseau (livraison #613) -- commandes du
central `power_action` {action: reboot|shutdown|cancel, delay_seconds?,
message?, force?} et `wol` {mac, broadcast?, port?}.

Windows : `shutdown.exe /r|/s /t N /c "message" [/f]` ; `/a` pour annuler.
Linux : `shutdown -r|-h +M "message"` (M minutes, 0 = now), `shutdown -c`.
macOS : `shutdown -r|-h +M` (root). Le message est borné et sans guillemets.
`force` = fermer les applications sans attendre (Windows /f) -- refusé par
défaut quand une session console est active (paramètre `console_active`
fourni par l'agent) : on ne coupe pas un utilisateur sans le dire.

Réveil : paquet magique (6 × 0xFF + 16 × MAC) en UDP vers l'adresse de
diffusion (255.255.255.255 par défaut, ou celle du sous-réseau) port 9 --
émis par CET agent, donc vers un poste du MÊME segment. Le poste visé doit
avoir le Wake-on-LAN activé (BIOS + carte réseau, « Autoriser ce
périphérique à sortir l'ordinateur du mode veille ») ; le hub ne peut pas
le vérifier, il ne voit que si le poste revient.
"""
import re
import socket

ACTIONS = ("reboot", "shutdown", "cancel")
MAX_DELAY = 3600
MAC_RE = re.compile(r"^([0-9A-Fa-f]{2})[:\-]?([0-9A-Fa-f]{2})[:\-]?([0-9A-Fa-f]{2})[:\-]?([0-9A-Fa-f]{2})[:\-]?([0-9A-Fa-f]{2})[:\-]?([0-9A-Fa-f]{2})$")


def _clean_message(msg):
    msg = re.sub(r"[\"'\r\n\x00-\x1f]", " ", str(msg or "")).strip()
    return msg[:200]


def build_argv(params, platform="win32", console_active=False):
    """-> (argv, erreur, delay_seconds). Pure."""
    action = str((params or {}).get("action") or "").strip().lower()
    if action not in ACTIONS:
        return None, "action : reboot, shutdown ou cancel", 0
    try:
        delay = int((params or {}).get("delay_seconds", 60))
    except (TypeError, ValueError):
        return None, "delay_seconds entier", 0
    delay = max(0, min(MAX_DELAY, delay))
    force = bool((params or {}).get("force"))
    message = _clean_message((params or {}).get("message") or "Redémarrage demandé par la supervision")
    if action == "cancel":
        if platform == "win32":
            return ["shutdown.exe", "/a"], None, 0
        return ["shutdown", "-c"], None, 0
    if console_active and not force:
        return None, "une session est ouverte sur la console : ajouter force pour passer outre", delay
    if platform == "win32":
        argv = ["shutdown.exe", "/r" if action == "reboot" else "/s", "/t", str(delay), "/c", message]
        if force:
            argv.append("/f")
        return argv, None, delay
    minutes = "now" if delay < 60 else "+%d" % (delay // 60)
    argv = ["shutdown", "-r" if action == "reboot" else "-h", minutes]
    if platform != "darwin":
        argv.append(message)
    return argv, None, delay


def interpret(r, action, delay):
    rc = getattr(r, "returncode", -1)
    out = (getattr(r, "stdout", "") or "").strip()[-500:]
    err = (getattr(r, "stderr", "") or "").strip()[-500:]
    if rc == -127:
        return {"ok": False, "error": "commande shutdown absente", "returncode": rc}
    if rc == 1190 or "1190" in err:  # Windows : un arrêt est déjà programmé
        return {"ok": False, "error": "un arrêt est déjà programmé (annuler d'abord)", "returncode": rc}
    if rc == 1116 or "1116" in err:
        return {"ok": False, "error": "aucun arrêt à annuler", "returncode": rc}
    if rc != 0:
        return {"ok": False, "error": err or out or "code %s" % rc, "returncode": rc}
    what = {"reboot": "redémarrage", "shutdown": "arrêt", "cancel": "annulation"}[action]
    return {"ok": True, "error": None, "returncode": 0, "action": action, "delay_seconds": delay,
            "message": "%s programmé dans %d s" % (what, delay) if action != "cancel" else "arrêt programmé annulé"}


def run(cmd, params, platform="win32", console_active=False, timeout=30):
    argv, err, delay = build_argv(params or {}, platform, console_active)
    if err:
        return {"ok": False, "error": err}
    res = interpret(cmd(argv, timeout=timeout), str(params.get("action")).lower(), delay)
    res["argv"] = argv
    return {"ok": res["ok"], "error": res["error"], "result": res}


# -- Wake-on-LAN --------------------------------------------------------------

def normalize_mac(mac):
    m = MAC_RE.match(str(mac or "").strip())
    if not m:
        return None
    return ":".join(g.lower() for g in m.groups())


def magic_packet(mac):
    mac = normalize_mac(mac)
    if not mac:
        return None
    raw = bytes.fromhex(mac.replace(":", ""))
    return b"\xff" * 6 + raw * 16


def send_wol(params, sender=None):
    """{mac, broadcast?, port?, repeat?} -> résultat. `sender(packet, addr,
    port)` remplaçable pour les tests ; par défaut socket UDP broadcast."""
    mac = normalize_mac((params or {}).get("mac"))
    if not mac:
        return {"ok": False, "error": "mac : adresse MAC invalide (aa:bb:cc:dd:ee:ff)"}
    broadcast = str((params or {}).get("broadcast") or "255.255.255.255").strip()
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", broadcast):
        return {"ok": False, "error": "broadcast : adresse IPv4"}
    try:
        port = int((params or {}).get("port") or 9)
        repeat = max(1, min(5, int((params or {}).get("repeat") or 3)))
    except (TypeError, ValueError):
        return {"ok": False, "error": "port / repeat entiers"}
    pkt = magic_packet(mac)
    send = sender or _udp_send
    try:
        for _ in range(repeat):
            send(pkt, broadcast, port)
    except OSError as exc:
        return {"ok": False, "error": "émission impossible : %s" % exc}
    return {"ok": True, "error": None, "result": {"mac": mac, "broadcast": broadcast, "port": port, "sent": repeat,
                                                  "message": "paquet magique émis %d fois vers %s (le poste doit avoir le Wake-on-LAN activé)" % (repeat, mac)}}


def _udp_send(packet, addr, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(packet, (addr, port))
    finally:
        s.close()
