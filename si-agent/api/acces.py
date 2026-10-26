# -*- coding: utf-8 -*-
"""#856 : accessibilité des services des CT / VM (Migration › Risques).

- DÉCOUVERTE (une fois par jour et par invité en marche) : connexion TCP aux ports usuels de chaque adresse fixe de
  la configuration (relevé pve-preflight) ; un port ouvert devient un service ATTENDU.
- CONTRÔLE (toutes les 5 min) : chaque service attendu, et chaque cible saisie à la main (https://…, tcp://hôte:port)
  -> joignable ou non, temps de réponse, depuis quand dans cet état.
Depuis le serveur du hub (si-agent-api), comme un usager. Rien n'est envoyé aux invités : une connexion, fermée aussitôt
(HTTP : une requête GET, réponse < 500 = joignable). Logique pure testée dans test_z_acces.py ; réseau injectable."""
import concurrent.futures
import socket
import ssl
import time
import urllib.request

PORTS = (22, 25, 80, 443, 465, 587, 993, 995, 3306, 5432, 8006, 8007, 8080, 8443)
DECOUVERTE_S = 24 * 3600
TIMEOUT = 3.0


def invites_en_marche(nodes):
    """{nœud: relevé pve-preflight} -> {clé nœud/vmid: {name, ips}} des invités en marche."""
    out = {}
    for n, node in (nodes or {}).items():
        for g in node.get("guests") or []:
            if g.get("status") == "running":
                out["%s/%s" % (n, g["vmid"])] = {"name": g.get("name"), "ips": list((g.get("conf") or {}).get("ips") or [])}
    return out


def a_decouvrir(invites, decouvertes, maintenant):
    d = decouvertes or {}
    return [k for k, v in invites.items() if v["ips"] and (k not in d or maintenant - (d.get(k) or 0) >= DECOUVERTE_S)]


def cibles(invites, attendus, manuels):
    """-> {clé: [cible]} : services découverts + cibles manuelles (même pour un invité sans adresse fixe)."""
    out = {}
    for k in set(invites) | set(manuels or {}):
        c = list((attendus or {}).get(k) or []) + [x for x in (manuels or {}).get(k) or [] if x not in ((attendus or {}).get(k) or [])]
        if c:
            out[k] = c
    return out


def tcp(hote, port, timeout=TIMEOUT):
    t = time.time()
    try:
        with socket.create_connection((hote, int(port)), timeout=timeout):
            return True, round((time.time() - t) * 1000), None
    except OSError as e:
        return False, None, str(e)[:120]


def http(url, timeout=8.0):
    t = time.time()
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE      # on mesure l'accès, pas le certificat
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "supervision-si/acces"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # noqa: BLE001
        return False, None, str(e)[:120]
    return code < 500, round((time.time() - t) * 1000), None if code < 500 else "HTTP %d" % code


def verifier(cible, f_tcp=tcp, f_http=http):
    if cible.startswith(("http://", "https://")):
        return f_http(cible)
    hp = cible[6:] if cible.startswith("tcp://") else cible
    hote, _, port = hp.rpartition(":")
    if not hote or not port.isdigit():
        return False, None, "cible illisible"
    return f_tcp(hote, int(port))


def decouvrir(ips, f_tcp=tcp, ports=PORTS):
    """-> cibles « tcp://ip:port » ouvertes."""
    jobs = [(ip, p) for ip in ips for p in ports]
    with concurrent.futures.ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda j: f_tcp(j[0], j[1], 2.0)[0], jobs))
    return ["tcp://%s:%d" % j for j, ok in zip(jobs, res) if ok]


def etat_invite(res):
    if not res:
        return "non surveillé"
    ok = sum(1 for r in res if r["ok"])
    return "ok" if ok == len(res) else "panne" if ok == 0 else "partiel"


def passage(invites, etat, f_tcp=tcp, f_http=http, maintenant=None):
    """etat = {attendus, decouvertes, manuels, resultats} -> nouvel état (découvertes dues + contrôle de toutes les cibles)."""
    now = maintenant or time.time()
    e = {k: dict(etat.get(k) or {}) for k in ("attendus", "decouvertes", "manuels", "resultats")}
    for k in a_decouvrir(invites, e["decouvertes"], now):
        trouves = decouvrir(invites[k]["ips"], f_tcp)
        e["attendus"][k] = sorted(set(e["attendus"].get(k) or []) | set(trouves))
        e["decouvertes"][k] = now
    cib = cibles(invites, e["attendus"], e["manuels"])
    jobs = [(k, c) for k, l in cib.items() for c in l]
    with concurrent.futures.ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda j: verifier(j[1], f_tcp, f_http), jobs))
    nouveaux = {}
    for (k, c), (ok, ms, err) in zip(jobs, res):
        prec = next((r for r in ((e["resultats"].get(k) or {}).get("cibles") or []) if r["cible"] == c), None)
        depuis = prec["depuis"] if prec and prec["ok"] == ok else now
        nouveaux.setdefault(k, []).append({"cible": c, "ok": ok, "ms": ms, "erreur": err, "depuis": depuis,
                                           "manuel": c in (e["manuels"].get(k) or [])})
    e["resultats"] = {k: {"at": now, "cibles": v, "etat": etat_invite(v)} for k, v in nouveaux.items()}
    return e
