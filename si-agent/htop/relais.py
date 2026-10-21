#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""si-htop : relais (#800). Reçoit en UDP les relevés signés des émetteurs (VM, CT, Proxmox), garde le dernier état
et l'historique (10 min à pleine résolution, 24 h par minute : moyenne et pic), calcule les constats soutenus
(CPU, iowait, steal, mémoire, swap, charge par cœur, partitions, pools ZFS, mémoire d'un CT proche de sa limite,
hôte muet) et sert :
  - en HTTP (réseau interne) : GET /etat, GET /hote/<nom>, GET /constats -- en-tête X-Htop-Token si HTOP_JETON_INTERNE ;
  - en UDP aux clients abonnés (client.py, poste d'exploitation) : un abonnement signé « SH1S » toutes les 5 s suffit,
    le relais répond à l'adresse source (aucun port à ouvrir côté client, NAT compris).
Clés : HTOP_CLE_EMETTEURS (émetteurs), HTOP_CLE_CLIENTS (clients) -- 16 caractères au moins chacune.
Seuils : HTOP_SEUILS (JSON partiel, voir SEUILS). Historique conservé dans HTOP_ETAT (redémarrage sans perte)."""
import collections
import hashlib
import hmac
import json
import os
import re
import socket
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

MAGIE_E, MAGIE_S, MAGIE_R = b"SH1E", b"SH1S", b"SH1R"
SEUILS = {"cpu": 90, "iowait": 30, "steal": 20, "memoire": 92, "swap": 60, "charge": 2.0, "disque": 90, "pool": 85,
          "invite_memoire": 95, "swap_activite": 50, "duree_s": 60, "muet_s": 30, "oubli_s": 86400}
CRITIQUE = {"cpu": 98, "iowait": 50, "steal": 40, "memoire": 97, "swap": 90, "charge": 4.0, "disque": 97, "pool": 95, "invite_memoire": 99}
DERIVE_S = 300          # horloge d'un émetteur / client tolérée
MAX_CLIENTS = 8


def emballer(magie, cle, obj):
    corps = zlib.compress(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 6)
    return magie + hmac.new(cle, magie + corps, hashlib.sha256).digest()[:16] + corps


def deballer(paquet, cle, magie, limite=262144):
    """-> objet, ou None (magie, signature, taille ou contenu invalides)."""
    if len(paquet) < 21 or paquet[:4] != magie or not cle:
        return None
    mac, corps = paquet[4:20], paquet[20:]
    if not hmac.compare_digest(mac, hmac.new(cle, magie + corps, hashlib.sha256).digest()[:16]):
        return None
    try:
        d = zlib.decompressobj()
        brut = d.decompress(corps, limite)
        if d.unconsumed_tail:
            return None
        obj = json.loads(brut.decode("utf-8"))
    except (zlib.error, ValueError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def pct(a, b):
    return round(100.0 * a / b, 1) if a is not None and b else None


def resume(s):
    """Relevé brut -> mesures utiles (mémoire hors ARC ZFS : l'ARC se réduit sous la pression)."""
    m = s.get("m") or [0, 0, 0]
    tot, used, arc = (list(m) + [0, 0, 0])[:3]
    if s.get("k") in ("ct", "vm"):   # #803 : l'ARC vu depuis un CT est celui de l'hôte (émetteurs antérieurs)
        arc = 0
    sw = s.get("sw") or [0, 0]
    l1 = (s.get("l") or [None])[0]
    return {"cpu": s.get("c"), "iowait": s.get("io"), "steal": s.get("st"), "memoire": pct(max(0, (used or 0) - (arc or 0)), tot),
            "memoire_brute": pct(used, tot), "swap": pct(sw[1], sw[0]) if sw and sw[0] else None,
            "charge": round(l1 / s["n"], 2) if l1 is not None and s.get("n") else None}


def consommateurs(s, cle):
    """Les trois plus gros consommateurs (invités d'un Proxmox, sinon processus) pour le message d'un constat."""
    if cle in ("cpu", "charge", "iowait", "memoire") and s.get("g"):
        i = 4 if cle != "memoire" else 6
        top = sorted([g for g in s["g"] if g[i] is not None], key=lambda g: -g[i])[:3]
        if top:
            return " -- " + ", ".join("%s %s (%s)" % (g[0], g[1] or "", "%.1f cœurs" % g[4] if i == 4 else "%.1f Go" % (g[6] / 1e9)) for g in top)
    pr = s.get("pr") or []
    if cle in ("cpu", "charge", "memoire") and pr:
        i = 2 if cle != "memoire" else 3
        top = sorted(pr, key=lambda p: -p[i])[:3]
        return " -- " + ", ".join("%s%s (%s)" % (p[1], " [%s]" % p[4] if len(p) > 4 and p[4] else "", "%s %%" % p[2] if i == 2 else "%.1f Go" % (p[3] / 1e9)) for p in top)
    return ""


LIBELLE = {"cpu": "CPU", "iowait": "attente disque (iowait)", "steal": "temps volé par l'hyperviseur (steal)", "memoire": "mémoire",
           "swap": "swap actif (pages échangées en continu)", "charge": "charge par cœur"}


class Relais(object):
    def __init__(self, cle_e, cle_c, seuils=None, horloge=time.time):
        self.cle_e, self.cle_c = cle_e, cle_c
        self.seuils = dict(SEUILS, **(seuils or {}))
        self.horloge = horloge
        self.verrou = threading.RLock()
        self.hotes = {}          # nom -> {s, recu, adresse, brut: deque, minute: deque, minute_cours, invites: {id: deque}}
        self.depasse = {}        # code -> début du dépassement
        self.actifs = {}         # code -> constat
        self.dernier_seq = {}    # (hôte, démarrage) -> numéro
        self.clients = {}        # adresse -> {expire, voir}
        self.rejets = collections.Counter()

    # ---------------------------------------------------------------- réception
    def recevoir(self, paquet, adresse):
        tete = paquet[:4]
        if tete == MAGIE_E:
            return self._releve(deballer(paquet, self.cle_e, MAGIE_E), adresse)
        if tete == MAGIE_S:
            return self._abonnement(deballer(paquet, self.cle_c, MAGIE_S, 4096), adresse)
        self.rejets["inconnu"] += 1
        return False

    def _releve(self, s, adresse):
        maintenant = self.horloge()
        if not s or not re.match(r"^[A-Za-z0-9._-]{1,64}$", str(s.get("h") or "")):
            self.rejets["signature"] += 1
            return False
        if abs(maintenant - float(s.get("t") or 0)) > DERIVE_S:
            self.rejets["horloge"] += 1
            return False
        cle = (s["h"], str(s.get("b")))
        with self.verrou:
            if int(s.get("s") or 0) <= self.dernier_seq.get(cle, 0):
                self.rejets["rejeu"] += 1
                return False
            self.dernier_seq[cle] = int(s.get("s") or 0)
            h = self.hotes.setdefault(s["h"], {"brut": collections.deque(maxlen=300), "minute": collections.deque(maxlen=1440), "minute_cours": None,
                                               "invites": {}})
            h.update(s=s, recu=maintenant, adresse=adresse[0])
            r = resume(s)
            h["brut"].append([round(maintenant), r["cpu"], r["memoire"], r["iowait"], r["steal"], r["charge"]])
            self._minute(h, maintenant, r, s)
        return True

    def _minute(self, h, maintenant, r, s):
        """Agrégat par minute : [minute, cpu moy, cpu max, mem moy, mem max, iowait max, steal max, charge max] ; invités : pic cœurs, pic mémoire."""
        mn = int(maintenant // 60) * 60
        c = h["minute_cours"]
        if c and c["mn"] != mn:
            h["minute"].append(self._clore(c))
            for vid, (cmax, mmax) in c["inv"].items():
                h["invites"].setdefault(vid, collections.deque(maxlen=1440)).append([c["mn"], cmax, mmax])
            c = None
        if c is None:
            c = h["minute_cours"] = {"mn": mn, "n": 0, "cpu": [], "mem": [], "io": [], "st": [], "ch": [], "inv": {}}
        for k, v in (("cpu", r["cpu"]), ("mem", r["memoire"]), ("io", r["iowait"]), ("st", r["steal"]), ("ch", r["charge"])):
            if v is not None:
                c[k].append(v)
        for g in s.get("g") or []:
            p = c["inv"].get(str(g[0]), (0, 0))
            c["inv"][str(g[0])] = (max(p[0], g[4] or 0), max(p[1], g[6] or g[5] or 0))

    @staticmethod
    def _clore(c):
        moy = lambda v: round(sum(v) / len(v), 1) if v else None   # noqa: E731
        mx = lambda v: max(v) if v else None   # noqa: E731
        return [c["mn"], moy(c["cpu"]), mx(c["cpu"]), moy(c["mem"]), mx(c["mem"]), mx(c["io"]), mx(c["st"]), mx(c["ch"])]

    def _abonnement(self, o, adresse):
        if not o or abs(self.horloge() - float(o.get("t") or 0)) > DERIVE_S:
            self.rejets["abonnement"] += 1
            return False
        with self.verrou:
            if adresse not in self.clients and len(self.clients) >= MAX_CLIENTS:
                self.purger_clients()
                if len(self.clients) >= MAX_CLIENTS:
                    return False
            self.clients[adresse] = {"expire": self.horloge() + 30, "voir": str(o.get("voir") or "")[:64]}
        return True

    def purger_clients(self):
        t = self.horloge()
        for a in [a for a, c in self.clients.items() if c["expire"] < t]:
            del self.clients[a]

    # ---------------------------------------------------------------- constats
    def evaluer(self):
        """Dépassements soutenus (duree_s) -> constats actifs ; renvoie la liste triée (critiques d'abord)."""
        t, S = self.horloge(), self.seuils
        vus = {}
        with self.verrou:
            for nom in list(self.hotes):
                h = self.hotes[nom]
                age = t - h["recu"]
                if age > S["oubli_s"]:
                    del self.hotes[nom]
                    continue
                if age > S["muet_s"]:
                    vus["htop-muet:%s" % nom] = ("warning", "%s : plus de relevé depuis %d s (émetteur arrêté, hôte saturé ou réseau)" % (nom, age), True)
                    continue
                s, r = h["s"], resume(h["s"])
                for cle in ("cpu", "iowait", "steal", "memoire", "swap", "charge"):
                    v = r.get(cle)
                    if v is None:
                        continue
                    code = "htop-%s:%s" % (cle, nom)
                    actif = code in self.actifs
                    if cle == "swap":   # #803 : swap rempli mais inerte (pages anciennes jamais relues) = pas un engorgement
                        act = sum(s["swio"]) if isinstance(s.get("swio"), list) else None
                        if (act is not None and act < S["swap_activite"]) or (act is None and (r.get("memoire") or 0) < S["memoire"] - 10):
                            continue
                    if v >= S[cle] or (actif and v >= S[cle] - (0.3 if cle == "charge" else 5)):   # hystérésis
                        unite = "" if cle == "charge" else " %"
                        vus[code] = ("critical" if v >= CRITIQUE[cle] else "warning",
                                     "%s : %s à %s%s (seuil %s%s)%s" % (nom, LIBELLE[cle], v, unite, S[cle], unite, consommateurs(s, cle)), False)
                for mp, taille, util in s.get("d") or []:
                    p = pct(util, taille)
                    if p is not None and p >= S["disque"]:
                        vus["htop-disque:%s:%s" % (nom, mp)] = ("critical" if p >= CRITIQUE["disque"] else "warning", "%s : %s plein à %s %%" % (nom, mp, p), True)
                for z in s.get("z") or []:
                    p = pct(z[2], z[1])
                    if p is not None and p >= S["pool"]:
                        vus["htop-pool:%s:%s" % (nom, z[0])] = ("critical" if p >= CRITIQUE["pool"] else "warning", "%s : pool ZFS %s à %s %%" % (nom, z[0], p), True)
                    if len(z) > 3 and z[3] not in ("ONLINE", ""):
                        vus["htop-pool-etat:%s:%s" % (nom, z[0])] = ("critical", "%s : pool ZFS %s %s" % (nom, z[0], z[3]), True)
                for g in s.get("g") or []:
                    p = pct(g[6], g[7]) if len(g) > 7 else None   # mémoire anonyme : le cache se libère
                    if p is not None and p >= S["invite_memoire"]:
                        vus["htop-invite-memoire:%s:%s" % (nom, g[0])] = ("critical" if p >= CRITIQUE["invite_memoire"] else "warning",
                                                                         "%s : %s %s à %s %% de sa mémoire hors cache (%.1f / %.1f Go)" % (nom, g[0], g[1], p, g[6] / 1e9, g[7] / 1e9), False)
            for code in list(self.depasse):
                if code not in vus:
                    del self.depasse[code]
            actifs = {}
            for code, (sev, msg, immediat) in vus.items():
                debut = self.depasse.setdefault(code, t)
                if immediat or t - debut >= S["duree_s"] or code in self.actifs:
                    actifs[code] = {"code": code, "severity": sev, "message": msg, "hote": code.split(":")[1], "depuis": round(self.actifs.get(code, {}).get("depuis") or debut)}
            self.actifs = actifs
            return sorted(actifs.values(), key=lambda a: (a["severity"] != "critical", a["code"]))

    # ---------------------------------------------------------------- vues
    def sommaire(self, nom, h, t):
        s, r = h["s"], resume(h["s"])
        return {"nom": nom, "nature": s.get("k"), "ncpu": s.get("n"), "cpu": r["cpu"], "coeurs": s.get("cc") or [], "iowait": r["iowait"], "steal": r["steal"],
                "charge": s.get("l"), "charge_coeur": r["charge"], "memoire": s.get("m"), "memoire_pct": r["memoire"], "memoire_brute_pct": r["memoire_brute"],
                "swap": s.get("sw"), "swap_pct": r["swap"], "uptime": s.get("up"), "processus": s.get("np"), "age_s": round(t - h["recu"], 1),
                "adresse": h.get("adresse"), "disques": s.get("d") or [], "pools": s.get("z") or [], "invites": s.get("g") or [],
                "pic_24h": self._pics(h), "muet": t - h["recu"] > self.seuils["muet_s"]}

    @staticmethod
    def _pics(h):
        mins = list(h["minute"])
        if not mins:
            return None
        def mx(i):   # noqa: E306
            v = [m[i] for m in mins if m[i] is not None]
            return max(v) if v else None
        cpu = sorted(m[1] for m in mins if m[1] is not None)
        return {"cpu": mx(2), "cpu_p95": cpu[int(0.95 * (len(cpu) - 1))] if cpu else None, "memoire": mx(4), "iowait": mx(5), "steal": mx(6),
                "charge": mx(7), "minutes": len(mins)}

    def etat(self):
        constats = self.evaluer()
        t = self.horloge()
        with self.verrou:
            self.purger_clients()
            hotes = [self.sommaire(n, h, t) for n, h in sorted(self.hotes.items())]
            for x in hotes:
                pi = {}
                for vid, dq in self.hotes[x["nom"]]["invites"].items():
                    c = [v[1] for v in dq if v[1] is not None]
                    m = [v[2] for v in dq if v[2] is not None]
                    pi[vid] = [max(c) if c else None, max(m) if m else None]
                x["pics_invites"] = pi
            return {"at": round(t), "hotes": hotes, "constats": constats, "seuils": self.seuils, "abonnes": len(self.clients), "rejets": dict(self.rejets)}

    def detail(self, nom):
        t = self.horloge()
        with self.verrou:
            h = self.hotes.get(nom)
            if not h:
                return None
            d = self.sommaire(nom, h, t)
            d.update(processus_top=h["s"].get("pr") or [], brut=list(h["brut"]), minutes=list(h["minute"]) + ([self._clore(h["minute_cours"])] if h["minute_cours"] else []))
            return d

    # ---------------------------------------------------------------- envoi aux clients
    def paquets_clients(self):
        """-> [(adresse, paquet)] : un paquet par hôte (sommaire), un paquet de constats, le détail de l'hôte regardé."""
        e = self.etat()
        out = []
        with self.verrou:
            clients = list(self.clients.items())
        if not clients or not self.cle_c:
            return out
        base = [emballer(MAGIE_R, self.cle_c, {"y": "c", "t": e["at"], "c": e["constats"][:30], "n": [h["nom"] for h in e["hotes"]]})]
        for h in e["hotes"]:
            leger = dict(h, invites=h["invites"][:12], disques=h["disques"][:6], pics_invites=None)
            base.append(emballer(MAGIE_R, self.cle_c, {"y": "h", "t": e["at"], "h": leger}))
        for adr, c in clients:
            for p in base:
                out.append((adr, p))
            if c.get("voir"):
                d = self.detail(c["voir"])
                if d:
                    d = dict(d, brut=d["brut"][-150:], minutes=[], pics_invites=None)
                    out.append((adr, emballer(MAGIE_R, self.cle_c, {"y": "d", "t": e["at"], "h": d})))
        return out

    # ---------------------------------------------------------------- persistance
    def sauver(self, chemin):
        with self.verrou:
            d = {n: {"s": h["s"], "recu": h["recu"], "minute": list(h["minute"]), "invites": {k: list(v) for k, v in h["invites"].items()}}
                 for n, h in self.hotes.items()}
        tmp = chemin + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh)
        os.replace(tmp, chemin)

    def charger(self, chemin):
        try:
            with open(chemin) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            return 0
        with self.verrou:
            for n, x in d.items():
                h = self.hotes.setdefault(n, {"brut": collections.deque(maxlen=300), "minute": collections.deque(x.get("minute") or [], maxlen=1440),
                                              "minute_cours": None, "invites": {}})
                h.update(s=x["s"], recu=x["recu"], adresse=None)
                h["invites"] = {k: collections.deque(v, maxlen=1440) for k, v in (x.get("invites") or {}).items()}
        return len(d)


def serveur_http(relais, port, jeton):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):   # noqa: N802
            if jeton and not hmac.compare_digest(self.headers.get("X-Htop-Token", ""), jeton):
                return self._json(401, {"error": "jeton"})
            chemin = self.path.split("?")[0]
            if chemin == "/etat":
                return self._json(200, relais.etat())
            if chemin == "/constats":
                return self._json(200, {"constats": relais.evaluer()})
            if chemin.startswith("/hote/"):
                d = relais.detail(unquote(chemin[6:]))
                return self._json(200 if d else 404, d or {"error": "hôte inconnu"})
            if chemin == "/sante":
                return self._json(200, {"ok": True})
            return self._json(404, {"error": "inconnu"})

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    srv.daemon_threads = True
    return srv


def main():
    cle_e = os.environ.get("HTOP_CLE_EMETTEURS", "").encode("utf-8")
    cle_c = os.environ.get("HTOP_CLE_CLIENTS", "").encode("utf-8")
    if len(cle_e) < 16:
        sys.stderr.write("HTOP_CLE_EMETTEURS absente ou trop courte (16 caractères au moins) : relais en attente de configuration\n")
    try:
        seuils = json.loads(os.environ.get("HTOP_SEUILS") or "{}")
    except ValueError:
        seuils = {}
    r = Relais(cle_e if len(cle_e) >= 16 else b"", cle_c if len(cle_c) >= 16 else b"", seuils if isinstance(seuils, dict) else {})
    etat = os.environ.get("HTOP_ETAT", "/data/htop-etat.json")
    print("relais htop : %d hôte(s) repris de %s" % (r.charger(etat), etat), flush=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", int(os.environ.get("HTOP_UDP_PORT", "8399"))))
    srv = serveur_http(r, int(os.environ.get("HTOP_HTTP_PORT", "8400")), os.environ.get("HTOP_JETON_INTERNE", ""))
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def diffusion():
        derniere_sauvegarde = time.time()
        while True:
            time.sleep(2)
            try:
                for adr, p in r.paquets_clients():
                    sock.sendto(p, adr)
                if time.time() - derniere_sauvegarde > 300:
                    r.sauver(etat)
                    derniere_sauvegarde = time.time()
            except Exception as e:  # noqa: BLE001
                sys.stderr.write("diffusion : %s\n" % e)
    threading.Thread(target=diffusion, daemon=True).start()
    while True:
        paquet, adr = sock.recvfrom(65535)
        try:
            r.recevoir(paquet, adr)
        except Exception as e:  # noqa: BLE001 -- un paquet malformé n'arrête pas le relais
            r.rejets["erreur"] += 1
            sys.stderr.write("paquet de %s : %s\n" % (adr[0], e))


if __name__ == "__main__":
    main()
