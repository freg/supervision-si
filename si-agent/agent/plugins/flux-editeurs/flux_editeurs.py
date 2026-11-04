#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « flux éditeurs » (livraison #965) : les flux sortants exigés par les éditeurs (Google Android Enterprise,
Idruide…) sont-ils ouverts depuis CHAQUE interface / VLAN de ce poste ?

Même test que nebula/tools/test-flux.sh, mais tenu par l'agent : à chaque passage, pour chaque interface IPv4 retenue,
la sonde lit les listes de cibles dans le hub (tuile « Flux éditeurs »), teste chaque cible EN SORTANT PAR CETTE
INTERFACE (source liée à son adresse ; interface sans route par défaut : table de routage temporaire vers sa
passerelle), puis envoie le passage au hub sous la source « <poste>-<interface> ». Le hub garde l'historique, ouvre
et ferme les alertes, croise avec Nebula (VLAN couverts) et envoie le récapitulatif quotidien.

Tests, en lecture seule : résolution DNS, connexion TCP, TLS (certificat vérifié ; non reconnu = inspection SSL
probable ; expiration < 14 jours = CERT), NTP (UDP/123). Ports attendus fermés (5e champ « ferme ») : OUVERT s'ils
répondent. Stdlib seulement (`ip` pour les routes, `openssl` facultatif pour l'émetteur d'un certificat non reconnu).

Réglages, du plus fort au plus faible (#966 : AUCUN argument n'est nécessaire dans le cas courant) :
  1. arguments --hub / --site / --listes / --ifaces ;
  2. fichier /etc/si-agent/flux-editeurs.json : {"hub": "...", "site": "...", "listes": ["google"], "ifaces": ["auto"]} ;
  3. déduits de l'agent : hub = son central (…/api/si-agent → …/api/nebula, variable SI_AGENT_CENTRAL), site = son
     réglage « site » (SI_AGENT_SITE), retrouvé dans la liste des sites du hub par identifiant ou par nom ; listes = google.

Usage : flux_editeurs.py [--hub URL] [--site ID] [--listes google,idruide] [--ifaces auto|eth0,wlan0] [--nom POSTE]
                         [--timeout 5] [--cache /var/lib/si-agent/flux-editeurs] [--alertes hub|agent] [--conf FICHIER]
"""
import datetime
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.request

VERSION = "1"
CACHE_DEFAUT = "/var/lib/si-agent/flux-editeurs"
CONF_DEFAUT = "/etc/si-agent/flux-editeurs.json"
TABLE_BASE = 270
FERME = ("ferme", "fermé", "closed", "close", "!")
SENSIBLES_TLS = (443,)


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


# ------------------------------------------------------------------ listes
def ports(spec):
    out = []
    for p in str(spec or "").replace(" ", "").split(","):
        m = re.match(r"^(\d+)-(\d+)$", p)
        if m and 1 <= int(m.group(1)) <= int(m.group(2)) <= 65535 and int(m.group(2)) - int(m.group(1)) <= 200:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
        elif p.isdigit() and 1 <= int(p) <= 65535:
            out.append(int(p))
    return sorted(set(out))


def lire_liste(texte):
    """Format du hub : groupe;hôte;proto;ports[;ferme] (commentaires #)."""
    out = []
    for l in str(texte or "").splitlines():
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        c = [x.strip() for x in l.split(";")]
        if len(c) < 4 or c[2].lower() not in ("tcp", "udp") or not c[1]:
            continue
        out.append({"groupe": c[0] or "cibles", "hote": c[1].lower(), "proto": c[2].lower(), "ports": ports(c[3]),
                    "attendu": "ferme" if len(c) > 4 and c[4].lower() in FERME else "ouvert"})
    return [x for x in out if x["ports"]]


def charger_listes(hub, ids, cache, timeout=15):
    """Listes lues dans le hub ; copie locale en cas d'indisponibilité du hub (dernière liste connue)."""
    cibles, erreurs = [], []
    os.makedirs(cache, exist_ok=True)
    for lid in ids:
        if not re.match(r"^[a-z0-9-]{1,40}$", lid):
            erreurs.append("identifiant de liste invalide : %s" % lid); continue
        f = os.path.join(cache, "%s.txt" % lid)
        texte = None
        try:
            with urllib.request.urlopen("%s/flux/listes/%s.txt" % (hub.rstrip("/"), lid), timeout=timeout) as r:
                texte = r.read().decode("utf-8", "replace")
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(texte)
        except Exception as exc:  # noqa: BLE001
            if os.path.exists(f):
                texte = open(f, encoding="utf-8").read()
                erreurs.append("liste %s : hub injoignable (%s), copie locale utilisée" % (lid, str(exc)[:80]))
            else:
                erreurs.append("liste %s : hub injoignable et pas de copie locale (%s)" % (lid, str(exc)[:80]))
        cibles += lire_liste(texte)
    return cibles, erreurs


# ------------------------------------------------------------------ interfaces et routes
def interfaces(choix):
    """[{iface, ip, gw}] : interfaces IPv4 globales (hors docker, ponts virtuels, tunnels) ou la liste demandée."""
    code, out, _ = run(["ip", "-4", "-o", "addr", "show", "scope", "global"])
    vues = []
    for l in out.splitlines():
        m = re.match(r"^\d+:\s+(\S+)\s+inet\s+([\d.]+)/(\d+)", l)
        if m:
            vues.append({"iface": m.group(1), "ip": m.group(2), "prefixe": int(m.group(3))})
    if choix and choix != ["auto"]:
        vues = [v for v in vues if v["iface"] in choix]
    else:
        vues = [v for v in vues if not re.match(r"^(docker|br-|veth|virbr|lo|tun|tap|wg|tailscale|zt|vmbr|fwbr|fwln|fwpr)", v["iface"])]
    _, routes, _ = run(["ip", "-4", "route", "show", "default"])
    for v in vues:
        m = re.search(r"default via ([\d.]+) dev %s\b" % re.escape(v["iface"]), routes)
        v["gw"], v["defaut"] = (m.group(1), True) if m else (passerelle_nm(v["iface"]), False)
    return vues


def passerelle_nm(iface):
    code, out, _ = run(["nmcli", "-g", "IP4.GATEWAY", "device", "show", iface])
    g = out.strip().split("\n")[0] if code == 0 else ""
    return g if re.match(r"^\d+\.\d+\.\d+\.\d+$", g) else None


class RouteTemporaire:
    """Interface sans route par défaut : `ip rule from <ip> table N` + `default via <gw> dev <iface> table N` le temps du passage."""
    def __init__(self, v, n):
        self.v, self.table, self.posee = v, TABLE_BASE + n, False

    def __enter__(self):
        if not self.v.get("defaut") and self.v.get("gw"):
            a = run(["ip", "route", "replace", "default", "via", self.v["gw"], "dev", self.v["iface"], "table", str(self.table)])[0]
            b = run(["ip", "rule", "add", "from", self.v["ip"], "table", str(self.table), "priority", str(self.table)])[0]
            self.posee = a == 0 and b == 0
        return self

    def __exit__(self, *e):
        if self.posee:
            run(["ip", "rule", "del", "from", self.v["ip"], "table", str(self.table), "priority", str(self.table)])
            run(["ip", "route", "flush", "table", str(self.table)])


# ------------------------------------------------------------------ tests
def resoudre(hote):
    try:
        return sorted({a[4][0] for a in socket.getaddrinfo(hote, None, socket.AF_INET, socket.SOCK_STREAM)})[0]
    except (OSError, IndexError):
        return None


def tcp(ip, port, src, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        if src:
            s.bind((src, 0))
        s.connect((ip, port))
        return s
    except OSError:
        s.close()
        return None


def emetteur_openssl(der):
    if not der:
        return None
    try:
        pem = ssl.DER_cert_to_PEM_cert(der)
        r = subprocess.run(["openssl", "x509", "-noout", "-issuer", "-enddate"], input=pem, capture_output=True, text=True, timeout=5)
        iss = re.search(r"O\s*=\s*([^,/\n]+)", r.stdout)
        fin = re.search(r"notAfter=(.+)", r.stdout)
        return (iss.group(1).strip() if iss else None), (fin.group(1).strip() if fin else None)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def jours_avant(not_after, maintenant=None):
    try:
        fin = datetime.datetime.strptime(not_after.replace("  ", " "), "%b %d %H:%M:%S %Y %Z")
    except (ValueError, AttributeError):
        return None
    return int((fin.replace(tzinfo=datetime.timezone.utc).timestamp() - (maintenant or time.time())) // 86400)


def tls(hote, ip, port, src, timeout):
    """-> (statut, détail) pour une connexion TLS : OK, INSPECTE (certificat non reconnu), CERT (expiration)."""
    s = tcp(ip, port, src, timeout)
    if s is None:
        return "KO", "connexion refusée ou filtrée"
    ctx = ssl.create_default_context()
    try:
        with ctx.wrap_socket(s, server_hostname=hote) as t:
            c = t.getpeercert()
            org = next((v for rdn in c.get("issuer", ()) for k, v in rdn if k == "organizationName"), None)
            j = jours_avant(c.get("notAfter"))
    except ssl.SSLCertVerificationError as exc:
        s2 = tcp(ip, port, src, timeout)
        info = None
        if s2 is not None:
            try:
                ctx2 = ssl._create_unverified_context()  # noqa: S323 -- lecture de l'émetteur seulement, aucun échange de données
                with ctx2.wrap_socket(s2, server_hostname=hote) as t2:
                    info = emetteur_openssl(t2.getpeercert(binary_form=True))
            except (OSError, ssl.SSLError):
                pass
        org = (info or (None, None))[0]
        return "INSPECTE", "certificat non reconnu%s : inspection SSL probable (%s)" % (" (émis par « %s »)" % org if org else "", str(exc.verify_message or exc)[:80])
    except (OSError, ssl.SSLError) as exc:
        return "KO", "échec TLS : %s" % str(exc)[:100]
    if j is not None and j < 0:
        return "CERT", "certificat EXPIRÉ depuis %d j%s" % (-j, " (%s)" % org if org else "")
    if j is not None and j < 14:
        return "CERT", "certificat expire dans %d j%s" % (j, " (%s)" % org if org else "")
    return "OK", "TLS ok%s%s" % (", émetteur %s" % org if org else "", ", certificat %d j" % j if j is not None else "")


def ntp(ip, src, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        if src:
            s.bind((src, 0))
        s.sendto(b"\x1b" + 47 * b"\0", (ip, 123))
        d, _ = s.recvfrom(48)
        return ("OK", "réponse NTP") if len(d) >= 48 else ("KO", "réponse NTP invalide")
    except OSError:
        return "KO", "pas de réponse NTP (UDP/123 filtré ?)"
    finally:
        s.close()


def tester(cibles, src, timeout):
    lignes, ips = [], {}
    for c in cibles:
        ip = ips.get(c["hote"]) if c["hote"] in ips else ips.setdefault(c["hote"], resoudre(c["hote"]))
        for p in c["ports"]:
            base = {"groupe": c["groupe"], "hote": c["hote"], "ip": ip or "", "proto": c["proto"], "port": p, "attendu": c["attendu"]}
            if not ip:
                lignes.append(dict(base, statut="KO", detail="nom non résolu (DNS)")); continue
            if c["proto"] == "udp":
                st, det = ntp(ip, src, timeout) if p == 123 else ("?", "UDP sans réponse attendue : non vérifiable d'ici")
            elif c["attendu"] == "ouvert" and p in SENSIBLES_TLS:
                st, det = tls(c["hote"], ip, p, src, timeout)
            else:
                s = tcp(ip, p, src, timeout)
                st, det = ("OK", "connexion TCP") if s else ("KO", "connexion refusée ou filtrée")
                if s:
                    s.close()
            if c["attendu"] == "ferme" and st in ("OK", "KO"):
                st, det = ("OUVERT", "OUVERT alors qu'il devrait être fermé vu d'ici") if st == "OK" else ("OK", "fermé comme attendu")
            lignes.append(dict(base, statut=st, detail=det))
    return lignes


def reclasser_ns(lignes):
    ouverts = {(l["proto"], l["port"]) for l in lignes if l["statut"] == "OK" and l["attendu"] != "ferme"}
    for l in lignes:
        if l["statut"] == "KO" and l["attendu"] != "ferme" and "DNS" not in l["detail"] and (l["proto"], l["port"]) in ouverts:
            l["statut"], l["detail"] = "NS", "port ouvert vers d'autres hôtes : non servi par celui-ci (pas un blocage)"
    return lignes


def bilan(lignes):
    b = {}
    for l in lignes:
        b[l["statut"]] = b.get(l["statut"], 0) + 1
    return b


def envoyer(hub, site, corps, timeout=30):
    req = urllib.request.Request("%s/sites/%s/flux/resultats" % (hub.rstrip("/"), site), data=json.dumps(corps).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ip_publique(src, timeout):
    """IP de sortie vue d'Internet (par cette interface) : requête HTTP minimale, sans dépendance."""
    s = tcp(resoudre("ifconfig.me") or "", 80, src, timeout) if resoudre("ifconfig.me") else None
    if not s:
        return None
    try:
        s.sendall(b"GET / HTTP/1.0\r\nHost: ifconfig.me\r\nUser-Agent: curl/8\r\n\r\n")
        d = s.recv(4096).decode("latin-1", "replace")
        m = re.search(r"\r\n\r\n\s*([\d.]+)", d)
        return m.group(1) if m else None
    except OSError:
        return None
    finally:
        s.close()


def collect(hub, site, listes, ifaces, nom, timeout, cache, alertes_agent):
    res = {"plugin": "flux-editeurs", "version": VERSION, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "site": site, "passages": [], "alerts": []}
    if not hub or not site:
        res["error"] = "réglages manquants : hub ou site introuvables (site de l'agent vide ?) — régler « site » dans la fiche de l'agent ou écrire /etc/si-agent/flux-editeurs.json (voir la tuile « Flux éditeurs », onglet Mise en place)"
        return res
    cibles, err = charger_listes(hub, listes, cache)
    res["erreurs"] = err
    if not cibles:
        res["error"] = "aucune cible : " + ("; ".join(err) or "listes vides")
        res["alerts"].append({"code": "flux-sans-cibles", "severity": "warning", "message": res["error"]})
        return res
    for n, v in enumerate(interfaces(ifaces)):
        with RouteTemporaire(v, n) as rt:
            if not v.get("defaut") and not rt.posee:
                res["passages"].append({"iface": v["iface"], "ip": v["ip"], "erreur": "pas de route de sortie (ni route par défaut ni passerelle connue)"}); continue
            lignes = reclasser_ns(tester(cibles, v["ip"], timeout))
            corps = {"source": "%s-%s" % (nom, v["iface"]), "iface": v["iface"], "ip_source": v["ip"], "ip_publique": ip_publique(v["ip"], timeout), "resultats": lignes}
        p = {"iface": v["iface"], "ip": v["ip"], "source": corps["source"], "bilan": bilan(lignes), "ip_publique": corps["ip_publique"]}
        try:
            r = envoyer(hub, site, corps)
            p["hub"] = {"passage": r.get("passage"), "alertes": r.get("alertes")}
        except Exception as exc:  # noqa: BLE001
            p["hub"] = {"erreur": str(exc)[:160]}
            res["alerts"].append({"code": "flux-hub-injoignable", "severity": "warning", "message": "résultats non envoyés au hub (%s) : %s" % (hub, str(exc)[:120])})
        if alertes_agent:       # sinon les alertes sont tenues par le hub (tuile Flux éditeurs) : pas de double notification
            for l in lignes:
                if l["statut"] in ("KO", "OUVERT", "CERT", "INSPECTE"):
                    res["alerts"].append({"code": "flux-%s-%s-%s-%d" % (v["iface"], l["hote"], l["proto"], l["port"])[:64], "severity": "warning",
                                          "message": "%s : %s %s/%d — %s" % (v["iface"], l["statut"], l["hote"], l["port"], l["detail"])})
        res["passages"].append(p)
    res["summary"] = "; ".join("%s : %s" % (p["iface"], ", ".join("%d %s" % (n, s) for s, n in sorted((p.get("bilan") or {}).items()))) for p in res["passages"] if "bilan" in p) or "aucun passage"
    return res


def hub_depuis_central(central):
    """https://hôte/api/si-agent -> https://hôte/api/nebula (même frontal que le central de l'agent)."""
    c = str(central or "").rstrip("/")
    if not c:
        return ""
    if re.search(r"/api/si-agent$", c):
        return re.sub(r"/api/si-agent$", "/api/nebula", c)
    m = re.match(r"^(https?://[^/]+)", c)
    return (m.group(1) + "/api/nebula") if m else ""


def resoudre_site(hub, site, timeout=15):
    """Site de l'agent (identifiant ou nom libre) -> identifiant du hub : identique, ou nom de site Nebula (sans casse,
    contenu dans l'un ou l'autre). Sans correspondance : le nom tel quel (le hub en fait un onglet hors Nebula)."""
    if not site:
        return site, None
    try:
        with urllib.request.urlopen("%s/flux/sites" % hub.rstrip("/"), timeout=timeout) as r:
            sites = json.loads(r.read().decode("utf-8")).get("sites") or []
    except Exception:  # noqa: BLE001
        return site, None
    s = site.strip().lower()
    for x in sites:
        if x.get("site_id") == site:
            return site, x.get("nom")
    for x in sites:
        n = str(x.get("nom") or "").lower()
        if n and (n == s or s in n or n in s):
            return x["site_id"], x.get("nom")
    return re.sub(r"[^A-Za-z0-9_-]+", "-", site).strip("-")[:64], None


def reglages(o, env, conf_path):
    """Fusionne arguments > fichier > environnement de l'agent."""
    conf = {}
    try:
        with open(conf_path, encoding="utf-8") as fh:
            conf = json.load(fh) or {}
    except (OSError, ValueError):
        conf = {}
    out = dict(o)
    out["hub"] = o.get("hub") or conf.get("hub") or hub_depuis_central(env.get("SI_AGENT_CENTRAL"))
    out["site"] = o.get("site") or conf.get("site") or env.get("SI_AGENT_SITE") or ""
    for k, d in (("listes", ["google"]), ("ifaces", ["auto"])):
        v = o.get(k) or conf.get(k) or d
        out[k] = v if isinstance(v, list) else [x for x in str(v).split(",") if x]
    out["origine"] = "arguments" if o.get("site") else "fichier" if conf.get("site") else "agent"
    return out


def main(argv):
    o = {"hub": "", "site": "", "listes": None, "ifaces": None, "nom": socket.gethostname().split(".")[0], "timeout": 5.0, "cache": CACHE_DEFAUT, "alertes": "hub", "conf": CONF_DEFAUT}
    i = 0
    while i < len(argv):
        a, v = argv[i], argv[i + 1] if i + 1 < len(argv) else None
        if a in ("--hub", "--site", "--nom", "--cache", "--alertes", "--conf") and v is not None:
            o[a[2:]] = v; i += 2; continue
        if a in ("--listes", "--ifaces") and v is not None:
            o[a[2:]] = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--timeout" and v is not None:
            o["timeout"] = float(v); i += 2; continue
        i += 1
    try:
        r = reglages(o, os.environ, o["conf"])
        site, nom_site = resoudre_site(r["hub"], r["site"]) if r["hub"] else (r["site"], None)
        res = collect(r["hub"], site, r["listes"], r["ifaces"], o["nom"], o["timeout"], o["cache"], o["alertes"] == "agent")
        res["reglages"] = {"hub": r["hub"], "site": site, "site_nom": nom_site, "site_agent": r["site"], "listes": r["listes"], "ifaces": r["ifaces"], "origine": r["origine"]}
        print(json.dumps(res))
    except Exception as exc:  # noqa: BLE001 -- une sonde ne doit jamais planter l'agent
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
