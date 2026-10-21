#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde Wi-Fi en écoute passive (livraison #801) : une seconde carte Wi-Fi USB en mode moniteur (Alfa AWUS036ACM,
MediaTek MT7612U, pilote mt76x2u du noyau : 2,4 et 5 GHz) parcourt les canaux et relève, sans jamais émettre ni
s'associer, ce que l'air transporte vraiment :

- par canal : trames par seconde, part de retransmissions, occupation du canal (temps « occupé » vu par la puce,
  `iw survey dump`, ou à défaut estimation par le temps d'antenne des trames reçues), gestion / contrôle / données,
  désauthentifications et désassociations, signal le plus fort ;
- par borne (BSSID) : SSID, canal réel (élément DS des balises, pas le canal écouté : en 2,4 GHz on entend les canaux
  voisins), signal moyen et max, balises, clients vus, et l'élément BSS Load (stations, utilisation vues par la borne).

Constats (jamais d'action) : canal saturé, retransmissions élevées, rafale de désauthentifications, SSID surveillé
diffusé par un BSSID inconnu (borne pirate / jumeau), carte absente. Réglage facultatif dans
/etc/si-agent/wifi-monitor.json : {"ssid": ["SSID surveillé"], "bssid_connus": ["02:00:00:00:00:01"], "canaux": [1, 6, 11, 36]}.

Usage : wifi_monitor.py [--iface auto|alfa0] [--bandes 2.4,5] [--sejour 0.35] [--config FICHIER]
Root requis (mode moniteur, socket brute). Bibliothèque standard ; `iw` et `ip` requis."""
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time

CANAUX_24 = list(range(1, 14))
CANAUX_5 = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]   # France, intérieur
CONFIG_DEFAUT = "/etc/si-agent/wifi-monitor.json"
PILOTES_MONITEUR = ("mt76x2u", "mt76x0u", "mt7921u", "rt2800usb", "ath9k_htc", "rtl8812au", "88XXau", "rtl88xxau")
# radiotap : bit -> (alignement, taille)
RT_CHAMPS = {0: (8, 8), 1: (1, 1), 2: (1, 1), 3: (2, 4), 4: (2, 2), 5: (1, 1), 6: (1, 1), 7: (2, 2), 8: (2, 2), 9: (2, 2),
             10: (1, 1), 11: (1, 1), 12: (1, 1), 13: (1, 1), 14: (2, 2), 15: (2, 2), 16: (1, 1), 17: (1, 1), 18: (4, 8),
             19: (1, 3), 20: (4, 8), 21: (2, 12), 22: (8, 12)}


def freq_canal(c):
    return 2484 if c == 14 else 2407 + 5 * c if c <= 13 else 5000 + 5 * c


def canal_freq(f):
    if f == 2484:
        return 14
    if 2412 <= f <= 2472:
        return (f - 2407) // 5
    if 5000 < f < 5900:
        return (f - 5000) // 5
    return None


def radiotap(p):
    """En-tête radiotap -> (longueur, {signal, rate_mbps, freq, mcs, vht, fcs, fcs_bad}) ; champs inconnus : arrêt propre."""
    if len(p) < 8 or p[0] != 0:
        return None, {}
    lg = struct.unpack_from("<H", p, 2)[0]
    presents, o = [], 4
    while True:
        if o + 4 > lg:
            return lg, {}
        w = struct.unpack_from("<I", p, o)[0]
        presents.append(w)
        o += 4
        if not w & 0x80000000:
            break
    out, w = {}, presents[0]
    for bit in range(29):
        if not w & (1 << bit):
            continue
        if bit not in RT_CHAMPS:
            break
        al, t = RT_CHAMPS[bit]
        o = (o + al - 1) // al * al
        if o + t > lg:
            break
        if bit == 1:
            fl = p[o]
            out["fcs"], out["fcs_bad"] = bool(fl & 0x10), bool(fl & 0x40)
        elif bit == 2:
            out["rate_mbps"] = p[o] / 2.0 if p[o] else None
        elif bit == 3:
            out["freq"] = struct.unpack_from("<H", p, o)[0]
        elif bit == 5:
            out["signal"] = struct.unpack_from("<b", p, o)[0]
        elif bit == 19:
            out["mcs"] = p[o + 2]
        elif bit == 21:
            out["vht"] = True
        o += t
    return lg, out


def mac(b):
    return ":".join("%02x" % x for x in b)


def elements(corps):
    """Éléments d'information d'une balise -> {ssid, canal, stations, util_pct}."""
    out, i = {}, 0
    while i + 2 <= len(corps):
        eid, n = corps[i], corps[i + 1]
        v = corps[i + 2:i + 2 + n]
        if len(v) < n:
            break
        if eid == 0:
            out["ssid"] = v.decode("utf-8", "replace") if v and v.strip(b"\x00") else ""
        elif eid == 3 and n >= 1:
            out["canal"] = v[0]
        elif eid == 61 and n >= 1 and "canal" not in out:   # HT operation : canal primaire
            out["canal"] = v[0]
        elif eid == 11 and n >= 3:
            out["stations"], out["util_pct"] = struct.unpack_from("<H", v, 0)[0], round(100.0 * v[2] / 255, 1)
        i += 2 + n
    return out


def trame(p):
    """Paquet capturé (radiotap + 802.11) -> dict décrit, ou None (trop court, FCS faux)."""
    lg, rt = radiotap(p)
    if lg is None or rt.get("fcs_bad"):
        return None
    f = p[lg:-4] if rt.get("fcs") else p[lg:]
    if len(f) < 10:
        return None
    fc, fl = f[0], f[1]
    typ, sous = (fc >> 2) & 3, fc >> 4
    d = {"type": ("gestion", "controle", "donnees", "?")[typ], "sous": sous, "retry": bool(fl & 0x08), "lg": len(p) - lg,
         "signal": rt.get("signal"), "rate": rt.get("rate_mbps"), "mcs": rt.get("mcs"), "vht": rt.get("vht", False)}
    if typ == 0 and len(f) >= 24:
        d["bssid"], d["source"] = mac(f[16:22]), mac(f[10:16])
        if sous in (8, 5) and len(f) >= 36:      # balise, réponse de sonde
            d["ie"] = elements(f[36:])
    elif typ == 2 and len(f) >= 24:
        tods, fromds = fl & 1, fl & 2
        a1, a2, a3 = f[4:10], f[10:16], f[16:22]
        if tods and not fromds:
            d["bssid"], d["client"] = mac(a1), a2
        elif fromds and not tods:
            d["bssid"], d["client"] = mac(a2), a1
        elif not tods and not fromds:
            d["bssid"], d["client"] = mac(a3), a2
        if "client" in d:
            d["client"] = mac(d["client"]) if not d["client"][0] & 1 else None
    return d


def temps_antenne(d):
    """Estimation du temps d'antenne d'une trame (s) : débit connu (ancien débit) ou approximation HT / VHT."""
    if d.get("rate"):
        debit = d["rate"] * 1e6
    elif d.get("vht"):
        debit = 200e6
    elif d.get("mcs") is not None:
        debit = 6.5e6 * ((d["mcs"] % 8) + 1) * (d["mcs"] // 8 + 1) * 0.9
    else:
        debit = 24e6
    return 20e-6 + d["lg"] * 8.0 / debit


class Canal(object):
    def __init__(self, c):
        self.c, self.trames, self.retry, self.gestion, self.controle, self.donnees = c, 0, 0, 0, 0, 0
        self.deauth, self.signal_max, self.antenne, self.sejour = 0, None, 0.0, 0.0
        self.survey = None

    def ajouter(self, d):
        self.trames += 1
        self.retry += 1 if d["retry"] else 0
        if d["type"] == "gestion":
            self.gestion += 1
            if d["sous"] in (10, 12):
                self.deauth += 1
        elif d["type"] == "controle":
            self.controle += 1
        elif d["type"] == "donnees":
            self.donnees += 1
        if d.get("signal") is not None:
            self.signal_max = d["signal"] if self.signal_max is None else max(self.signal_max, d["signal"])
        self.antenne += temps_antenne(d)

    def vue(self):
        s = self.sejour or 1e-9
        return {"canal": self.c, "freq": freq_canal(self.c), "sejour_s": round(self.sejour, 2), "trames": self.trames, "par_s": round(self.trames / s, 1),
                "retry_pct": round(100.0 * self.retry / self.trames, 1) if self.trames else None, "gestion": self.gestion, "controle": self.controle,
                "donnees": self.donnees, "deauth": self.deauth, "signal_max": self.signal_max,
                "occupation_pct": self.survey, "occupation_estimee_pct": round(min(100.0, 100.0 * self.antenne / s), 1)}


class Bornes(object):
    def __init__(self):
        self.b = {}

    def ajouter(self, d, canal_ecoute):
        bs = d.get("bssid")
        if not bs or int(bs[:2], 16) & 1:
            return
        x = self.b.setdefault(bs, {"bssid": bs, "ssid": None, "canal": None, "signaux": [], "balises": 0, "clients": set(), "deauth": 0,
                                    "stations_borne": None, "util_borne_pct": None, "canal_ecoute": canal_ecoute})
        ie = d.get("ie")
        if ie is not None:
            x["balises"] += 1
            if ie.get("ssid") is not None:
                x["ssid"] = ie["ssid"]
            if ie.get("canal"):
                x["canal"] = ie["canal"]
            if "stations" in ie:
                x["stations_borne"], x["util_borne_pct"] = ie["stations"], ie["util_pct"]
            if d.get("signal") is not None and (x["canal"] is None or x["canal"] == canal_ecoute):   # signal mesuré sur son canal
                x["signaux"].append(d["signal"])
        if d.get("client") and d["client"] != bs:
            x["clients"].add(d["client"])
        if d["type"] == "gestion" and d["sous"] in (10, 12):
            x["deauth"] += 1

    def vue(self):
        out = []
        for x in self.b.values():
            if not x["balises"] and not x["clients"]:
                continue
            s = x["signaux"]
            out.append({"bssid": x["bssid"], "ssid": x["ssid"], "canal": x["canal"] or x["canal_ecoute"], "signal_max": max(s) if s else None,
                        "signal_moy": round(sum(s) / len(s), 1) if s else None, "balises": x["balises"], "clients": len(x["clients"]),
                        "deauth": x["deauth"], "stations_borne": x["stations_borne"], "util_borne_pct": x["util_borne_pct"]})
        return sorted(out, key=lambda b: (b["canal"] or 0, -(b["signal_max"] or -200)))


def constats(canaux, bornes, conf, iface):
    out = []
    for c in canaux:
        occ = c["occupation_pct"] if c["occupation_pct"] is not None else (c["occupation_estimee_pct"] if c["trames"] >= 20 else None)
        if occ is not None and occ >= 70:
            out.append({"code": "monitor-sature:%s" % c["canal"], "severity": "critical" if occ >= 90 else "warning",
                        "message": "canal %s occupé à %s %%%s (%s trames/s)" % (c["canal"], occ, "" if c["occupation_pct"] is not None else " (estimation)", c["par_s"])})
        if c["retry_pct"] is not None and c["trames"] >= 50 and c["retry_pct"] >= 25:
            out.append({"code": "monitor-retry:%s" % c["canal"], "severity": "warning",
                        "message": "canal %s : %s %% de trames retransmises (interférences, signal faible ou canal encombré)" % (c["canal"], c["retry_pct"])})
        if c["deauth"] >= 10:
            out.append({"code": "monitor-deauth:%s" % c["canal"], "severity": "critical" if c["deauth"] >= 50 else "warning",
                        "message": "canal %s : %s désauthentifications / désassociations en %s s (borne qui expulse ou attaque)" % (c["canal"], c["deauth"], c["sejour_s"])})
    surveilles = set(conf.get("ssid") or [])
    connus = set(x.lower() for x in conf.get("bssid_connus") or [])
    if surveilles and connus:
        for b in bornes:
            if b["ssid"] in surveilles and b["bssid"] not in connus:
                out.append({"code": "monitor-inconnu:%s" % b["bssid"], "severity": "warning",
                            "message": "SSID « %s » diffusé par une borne inconnue %s (canal %s, %s dBm) : borne pirate ou oubli de la liste"
                                       % (b["ssid"], b["bssid"], b["canal"], b["signal_max"])})
    return out


# ---------------------------------------------------------------- système
def lancer(args, timeout=10):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)


def pilote(iface):
    try:
        return os.path.basename(os.readlink("/sys/class/net/%s/device/driver" % iface))
    except OSError:
        return ""


def choisir_iface(demande):
    if demande != "auto":
        return demande if os.path.exists("/sys/class/net/%s" % demande) else None
    noms = sorted(os.listdir("/sys/class/net")) if os.path.isdir("/sys/class/net") else []
    if "alfa0" in noms:
        return "alfa0"
    for n in noms:
        if os.path.isdir("/sys/class/net/%s/wireless" % n) and pilote(n) in PILOTES_MONITEUR:
            return n
    return None


def mettre_en_moniteur(iface, run=lancer):
    rc, out, _ = run(["iw", "dev", iface, "info"])
    if "type monitor" in out:
        run(["ip", "link", "set", iface, "up"])
        return True
    run(["ip", "link", "set", iface, "down"])
    rc, _, err = run(["iw", "dev", iface, "set", "type", "monitor"])
    run(["ip", "link", "set", iface, "up"])
    return rc == 0


def survey(iface, freq, run=lancer):
    """-> (actif ms, occupé ms) du canal en cours, ou None (pilote sans survey)."""
    rc, out, _ = run(["iw", "dev", iface, "survey", "dump"])
    for bloc in out.split("Survey data from")[1:]:
        if re.search(r"frequency:\s+%d MHz" % freq, bloc):
            a = re.search(r"channel active time:\s+(\d+) ms", bloc)
            b = re.search(r"channel busy time:\s+(\d+) ms", bloc)
            if a and b:
                return int(a.group(1)), int(b.group(1))
    return None


def ecouter(iface, sejour, canaux, run=lancer):
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(3))
    s.bind((iface, 0))
    s.settimeout(0.05)
    bornes, res = Bornes(), []
    ecouter.refus = []
    try:
        for c in canaux:
            rc, _, err = run(["iw", "dev", iface, "set", "channel", str(c)])
            if rc != 0:
                ecouter.refus.append("%s : %s" % (c, (err or "code %d" % rc).strip()[:120]))
                continue
            k = Canal(c)
            sv0 = survey(iface, freq_canal(c), run)
            while True:          # vider ce qui précède le changement de canal
                try:
                    s.recv(65535)
                except (socket.timeout, BlockingIOError):
                    break
            t0 = time.time()
            while time.time() - t0 < sejour:
                try:
                    p = s.recv(65535)
                except (socket.timeout, BlockingIOError):
                    continue
                d = trame(p)
                if d:
                    k.ajouter(d)
                    bornes.ajouter(d, c)
            k.sejour = time.time() - t0
            sv1 = survey(iface, freq_canal(c), run)
            if sv0 and sv1 and sv1[0] > sv0[0]:
                k.survey = round(100.0 * (sv1[1] - sv0[1]) / (sv1[0] - sv0[0]), 1)
            res.append(k.vue())
    finally:
        s.close()
    return res, bornes.vue()


def collecter(iface="auto", bandes="2.4,5", sejour=0.35, config=CONFIG_DEFAUT, run=lancer, ecoute=ecouter):
    try:
        with open(config) as fh:
            conf = json.load(fh)
    except (OSError, ValueError):
        conf = {}
    ifc = choisir_iface(iface)
    if not ifc:
        return {"iface": None, "alerts": [{"code": "monitor-absente", "severity": "warning",
                                           "message": "aucune carte Wi-Fi USB capable du mode moniteur (Alfa AWUS036ACM débranchée, hub USB non alimenté ?)"}]}
    canaux = conf.get("canaux") or ((CANAUX_24 if "2.4" in bandes else []) + (CANAUX_5 if "5" in bandes.replace("2.4", "") else []))
    if not mettre_en_moniteur(ifc, run):
        return {"iface": ifc, "pilote": pilote(ifc), "alerts": [{"code": "monitor-mode", "severity": "warning",
                                                                  "message": "%s refuse le mode moniteur (gérée par NetworkManager ?)" % ifc}]}
    t0 = time.time()
    res, bornes = ecoute(ifc, sejour, canaux, run)
    refus = list(getattr(ecoute, "refus", []) or [])
    alertes = constats(res, bornes, conf, ifc)
    if canaux and not res:   # #808 : aucun canal réglable -- la cause (iw) est remontée au lieu d'un relevé vide
        alertes.append({"code": "monitor-canaux", "severity": "warning",
                        "message": "%s : aucun canal réglable (%s)" % (ifc, refus[0] if refus else "cause inconnue")})
    return {"iface": ifc, "pilote": pilote(ifc), "duree_s": round(time.time() - t0, 1), "canaux": res, "bornes": bornes,
            "clients": sum(b["clients"] for b in bornes), "refus": refus[:5], "alerts": alertes}


def main(argv):
    o = {"iface": "auto", "bandes": "2.4,5", "sejour": 0.35, "config": CONFIG_DEFAUT}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-")
        if k in o and i + 1 < len(argv):
            o[k] = float(argv[i + 1]) if k == "sejour" else argv[i + 1]
            i += 2
            continue
        i += 1
    try:
        print(json.dumps(collecter(**o), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 -- une sonde ne plante jamais l'agent
        print(json.dumps({"error": "écoute échouée : %s" % e}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
