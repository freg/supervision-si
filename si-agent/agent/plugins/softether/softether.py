#!/usr/bin/env python3
"""Plugin si-agent « softether » (#885) : sessions d'un serveur SoftEther VPN, en LECTURE SEULE de ses journaux.

Aucun mot de passe d'administration n'est nécessaire : on lit les journaux de sécurité (security_log/<hub>/sec_AAAAMMJJ.log)
que SoftEther écrit lui-même. Lecture incrémentale (position mémorisée par fichier), sessions conservées localement
(--keep-days) et renvoyées sur --emit-days. Par session : hub, utilisateur, adresse et nom d'origine, protocole (L2TP,
SSTP, OpenVPN, SoftEther…), poste client, adresse VPN attribuée (DHCP SecureNAT), début, fin, volumes, en cours.
Constats : échecs d'authentification répétés depuis une même adresse (--fail-threshold sur une heure).
Heures : celles du serveur (heure locale des journaux).

Arguments : [--dir /usr/local/vpnserver] [--state /var/lib/si-agent/softether-state.json] [--emit-days 90]
            [--keep-days 400] [--fail-threshold 5]
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+ (.*)$")
ESSAI = re.compile(r'The connection "(CID-\d+)" \(IP address: ([^,]+), Host name: ([^,]*), Port number: \d+, Client name: "([^"]*)".*the user name is "([^"]*)"')
CREEE = re.compile(r'Connection "(CID-\d+)": The new session "([^"]+)" has been created\. \(IP address: ([^,]+),.*Physical underlying protocol: "([^"]*)"')
DETAILS = re.compile(r'Session "([^"]+)": VPN Client details: .*Client host name: "([^"]*)"')
DHCP = re.compile(r'for host "([^"]+)" on another session .*the new IP address (\d+(?:\.\d+){3})')
FIN = re.compile(r'Session "([^"]+)": The session has been terminated\..*outgoing data size: (\d+) bytes, Total incoming data size: (\d+) bytes')
ECHEC = re.compile(r'Connection "(CID-\d+)": .*(?:fail|denied|refus|incorrect|invalid)', re.I)


def _iso(s):
    return s.replace(" ", "T")


class Analyse:
    """État de lecture : sessions ouvertes / closes, tentatives par connexion, échecs."""
    def __init__(self, etat=None):
        etat = etat or {}
        self.sessions = etat.get("sessions") or {}          # clé hub|sid|debut -> session
        self.ouvertes = etat.get("ouvertes") or {}          # hub|sid -> clé
        self.essais = etat.get("essais") or {}              # hub|cid -> {ip, nom, client, user}
        self.echecs = etat.get("echecs") or []              # [{at, hub, ip, user}]

    def ligne(self, hub, ligne):
        m = TS.match(ligne.strip())
        if not m:
            return
        at, txt = _iso(m.group(1)), m.group(2)
        if txt.startswith("SecureNAT:"):
            return
        e = ESSAI.search(txt)
        if e:
            self.essais["%s|%s" % (hub, e.group(1))] = {"ip": e.group(2), "nom_origine": e.group(3), "client": e.group(4), "utilisateur": e.group(5)}
            return
        c = CREEE.search(txt)
        if c:
            ess = self.essais.pop("%s|%s" % (hub, c.group(1)), {})
            cle = "%s|%s|%s" % (hub, c.group(2), at)
            self.sessions[cle] = {"hub": hub, "sid": c.group(2), "utilisateur": ess.get("utilisateur") or _user_sid(c.group(2)), "origine": c.group(3),
                                  "nom_origine": ess.get("nom_origine") or "", "client": ess.get("client") or "", "protocole": c.group(4),
                                  "poste": "", "adresse_vpn": "", "debut": at, "fin": None, "emis": None, "recu": None, "en_cours": True}
            self.ouvertes["%s|%s" % (hub, c.group(2))] = cle
            return
        d = DETAILS.search(txt) or DHCP.search(txt)
        if d:
            s = self.sessions.get(self.ouvertes.get("%s|%s" % (hub, d.group(1)), ""))
            if s is not None:
                s["poste" if d.re is DETAILS else "adresse_vpn"] = d.group(2)
            return
        f = FIN.search(txt)
        if f:
            s = self.sessions.get(self.ouvertes.pop("%s|%s" % (hub, f.group(1)), ""))
            if s is not None:
                s.update(fin=at, emis=int(f.group(2)), recu=int(f.group(3)), en_cours=False)
            return
        x = ECHEC.search(txt)
        if x and "Successfully" not in txt:
            ess = self.essais.get("%s|%s" % (hub, x.group(1)), {})
            self.echecs.append({"at": at, "hub": hub, "ip": ess.get("ip") or "", "utilisateur": ess.get("utilisateur") or "", "message": txt[:200]})

    def purger(self, keep_days, now):
        limite = (now - timedelta(days=keep_days)).strftime("%Y-%m-%dT%H:%M:%S")
        self.sessions = {k: s for k, s in self.sessions.items() if s["debut"] >= limite or s["en_cours"]}
        self.ouvertes = {k: v for k, v in self.ouvertes.items() if v in self.sessions}
        self.echecs = [e for e in self.echecs if e["at"] >= limite][-5000:]
        if len(self.essais) > 500:   # tentatives sans suite : on ne garde que les plus récentes (CID croissants)
            garde = sorted(self.essais, key=lambda k: int(k.rsplit("-", 1)[-1]) if k.rsplit("-", 1)[-1].isdigit() else 0)[-500:]
            self.essais = {k: self.essais[k] for k in garde}

    def etat(self):
        return {"sessions": self.sessions, "ouvertes": self.ouvertes, "essais": self.essais, "echecs": self.echecs}


def _date(s):
    """« AAAA-MM-JJTHH:MM:SS » -> datetime (fromisoformat n'existe qu'à partir de Python 3.7 ; r2d2 est en 3.5)."""
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")


def _user_sid(sid):
    m = re.match(r"SID-(.+?)-(?:\[[^\]]*\]-)?\d+$", sid)
    return m.group(1).lower() if m else ""


def lire_journaux(base, analyse, positions, depuis=None):
    """Lit la suite de chaque security_log/<hub>/sec_*.log depuis la position mémorisée (fichiers datés avant `depuis` ignorés)."""
    for chemin in sorted(glob.glob(os.path.join(base, "security_log", "*", "sec_*.log")), key=lambda c: os.path.basename(c)):
        hub = os.path.basename(os.path.dirname(chemin))
        m = re.search(r"sec_(\d{8})", os.path.basename(chemin))
        if depuis and m and m.group(1) < depuis and chemin not in positions:
            continue
        pos = positions.get(chemin, 0)
        try:
            taille = os.path.getsize(chemin)
            if taille < pos:
                pos = 0
            if taille == pos:
                continue
            with open(chemin, "rb") as fh:
                fh.seek(pos)
                for brut in fh:
                    analyse.ligne(hub, brut.decode("utf-8", "replace"))
                positions[chemin] = fh.tell()
        except OSError:
            continue
    return positions


def main(argv=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/usr/local/vpnserver")
    ap.add_argument("--state", default="/var/lib/si-agent/softether-state.json")
    ap.add_argument("--emit-days", type=int, default=90)
    ap.add_argument("--keep-days", type=int, default=400)
    ap.add_argument("--fail-threshold", type=int, default=5)
    a = ap.parse_args(argv)
    now = now or datetime.now()
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "type": "softether", "hubs": [], "sessions": [], "echecs": [], "alerts": []}
    if not os.path.isdir(os.path.join(a.dir, "security_log")):
        out["alerts"].append({"code": "vpn-softether-journaux", "severity": "warning", "message": "journaux SoftEther introuvables (%s/security_log)" % a.dir})
        return out
    try:
        with open(a.state, encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    an = Analyse(st.get("analyse"))
    positions = lire_journaux(a.dir, an, st.get("positions") or {}, (now - timedelta(days=a.keep_days)).strftime("%Y%m%d"))
    an.purger(a.keep_days, now)
    positions = {k: v for k, v in positions.items() if os.path.exists(k)}
    try:
        os.makedirs(os.path.dirname(a.state), exist_ok=True)
        tmp = a.state + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"positions": positions, "analyse": an.etat()}, fh)
        os.chmod(tmp, 0o600)
        os.replace(tmp, a.state)
    except OSError as e:
        out["alerts"].append({"code": "vpn-softether-etat", "severity": "info", "message": "état non mémorisé : %s" % e})
    limite = (now - timedelta(days=a.emit_days)).strftime("%Y-%m-%dT%H:%M:%S")
    sess = sorted((s for s in an.sessions.values() if s["debut"] >= limite or s["en_cours"]), key=lambda s: s["debut"], reverse=True)
    for s in sess:
        if s.get("fin"):
            s["duree_s"] = int((_date(s["fin"]) - _date(s["debut"])).total_seconds())
        else:
            s["duree_s"] = int((now - _date(s["debut"])).total_seconds())
    out["sessions"] = sess[:5000]
    out["hubs"] = sorted({os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(a.dir, "security_log", "*", "sec_*.log"))})
    out["echecs"] = [e for e in an.echecs if e["at"] >= limite][-500:]
    heure = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    par_ip = {}
    for e in an.echecs:
        if e["at"] >= heure:
            par_ip[e["ip"] or "?"] = par_ip.get(e["ip"] or "?", 0) + 1
    for ip, n in sorted(par_ip.items()):
        if n >= a.fail_threshold:
            out["alerts"].append({"code": "vpn-echecs@" + ip, "severity": "warning", "message": "%d échec(s) d'authentification VPN depuis %s en une heure" % (n, ip)})
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
