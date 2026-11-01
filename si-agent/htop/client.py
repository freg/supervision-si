#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""si-htop : client UDP du poste d'exploitation (#800). S'abonne au relais (paquet signé toutes les 5 s) et affiche
en continu, façon htop, tous les hôtes (Proxmox, VM, CT) : CPU, iowait, steal, mémoire, swap, charge, disques,
constats ; Entrée sur un hôte : cœurs, processus, invités d'un Proxmox. Aucun port à ouvrir côté poste (le relais
répond à l'adresse source de l'abonnement). Bibliothèque standard seule (Windows : pip install windows-curses,
ou --texte).

Usage : client.py --relais supervision.example.org:8399 --cle-fichier ~/.si-htop-cle [--son] [--texte]
Touches : ↑ ↓ choisir, Entrée détail / liste, c trier par CPU, m par mémoire, n par nom, s son on/off, q quitter."""
import argparse
import hashlib
import hmac
import json
import os
import socket
import sys
import time
import zlib

MAGIE_S, MAGIE_R = b"SH1S", b"SH1R"
TRI = {"c": ("cpu", True), "m": ("memoire_pct", True), "n": ("nom", False)}


def emballer(magie, cle, obj):
    corps = zlib.compress(json.dumps(obj, separators=(",", ":")).encode("utf-8"), 6)
    return magie + hmac.new(cle, magie + corps, hashlib.sha256).digest()[:16] + corps


def deballer(paquet, cle, magie, limite=1048576):
    if len(paquet) < 21 or paquet[:4] != magie:
        return None
    mac, corps = paquet[4:20], paquet[20:]
    if not hmac.compare_digest(mac, hmac.new(cle, magie + corps, hashlib.sha256).digest()[:16]):
        return None
    try:
        d = zlib.decompressobj()
        obj = json.loads(d.decompress(corps, limite).decode("utf-8"))
    except (zlib.error, ValueError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


class Vue(object):
    def __init__(self):
        self.hotes, self.constats, self.noms, self.detail = {}, [], None, None
        self.recu, self.connus = 0, set()

    def integrer(self, o):
        """Paquet du relais -> état ; renvoie les nouveaux constats critiques (pour le signal sonore)."""
        self.recu = time.time()
        nouveaux = []
        if o.get("y") == "h" and isinstance(o.get("h"), dict):
            self.hotes[o["h"]["nom"]] = o["h"]
        elif o.get("y") == "d" and isinstance(o.get("h"), dict):
            self.detail = o["h"]
        elif o.get("y") == "c":
            self.constats = o.get("c") or []
            self.noms = set(o.get("n") or [])
            for n in [n for n in self.hotes if n not in self.noms]:
                del self.hotes[n]
            codes = set(a["code"] for a in self.constats)
            nouveaux = [a for a in self.constats if a["code"] not in self.connus and a.get("severity") == "critical"]
            self.connus = codes
        return nouveaux

    def liste(self, tri="c"):
        cle, desc = TRI.get(tri, TRI["c"])
        def k(h):   # noqa: E306
            v = h.get(cle)
            return (v is None, -(v or 0) if desc and not isinstance(v, str) else (v or ""))
        hs = sorted(self.hotes.values(), key=k)
        pve = [h for h in hs if h.get("nature") == "pve"]
        noms = {}
        for p in pve:
            for g in p.get("invites") or []:
                if g[1]:
                    noms[str(g[1]).lower()] = p["nom"]
        out = []
        for p in pve:   # invités sous leur Proxmox (rapprochés par le nom)
            out.append((0, p))
            out += [(1, h) for h in hs if h.get("nature") != "pve" and noms.get(h["nom"].lower()) == p["nom"]]
        return out + [(0, h) for h in hs if h.get("nature") != "pve" and h["nom"].lower() not in noms]


def barre(p, largeur=10):
    if p is None:
        return "·" * largeur
    n = max(0, min(largeur, int(round(p * largeur / 100.0))))
    return "|" * n + " " * (largeur - n)


def fmt(v, suffixe=""):
    return "—" if v is None else ("%.0f%s" % (v, suffixe) if isinstance(v, float) and v >= 10 else "%s%s" % (v, suffixe))


def go(n):
    return "—" if n is None else "%.1fG" % (n / 1e9)


def niveau(h, seuils=None):
    s = seuils or {"cpu": 90, "memoire_pct": 92, "swap_pct": 60, "iowait": 30, "steal": 20}
    if h.get("muet"):
        return "alerte"
    if any((h.get(k) or 0) >= v for k, v in s.items()):
        return "alerte"
    if any((h.get(k) or 0) >= v * 0.8 for k, v in s.items()):
        return "attention"
    return "normal"


def lignes_liste(vue, choix, largeur, tri="c"):
    """-> [(texte, niveau)] de l'écran liste (pur, testé)."""
    out = [("%-22s %-3s %-16s %6s %6s %-16s %6s %7s %6s" % ("HÔTE", "NAT", "CPU", "IOW", "STEAL", "MÉMOIRE", "SWAP", "CHARGE", "ÂGE"), "titre")]
    for i, (ind, h) in enumerate(vue.liste(tri)):
        nom = ("└ " if ind else "") + h["nom"]
        t = "%-22s %-3s [%s]%4s %6s %6s [%s]%4s %6s %7s %5ss" % (
            nom[:22], (h.get("nature") or "?")[:3], barre(h.get("cpu")), fmt(h.get("cpu")), fmt(h.get("iowait"), "%"), fmt(h.get("steal"), "%"),
            barre(h.get("memoire_pct")), fmt(h.get("memoire_pct")), fmt(h.get("swap_pct"), "%"), fmt(h.get("charge_coeur")), int(h.get("age_s") or 0))
        out.append((("> " if i == choix else "  ") + t, "choix" if i == choix else niveau(h)))
    if not vue.hotes:
        out.append(("  en attente du relais… (clé client, port UDP du relais, pare-feu)", "attention"))
    out.append(("", "normal"))
    out.append(("CONSTATS (%d)" % len(vue.constats), "titre"))
    for a in vue.constats[:12]:
        out.append(("  %s %s" % ("!!" if a.get("severity") == "critical" else " !", a.get("message", "")), "alerte" if a.get("severity") == "critical" else "attention"))
    return [(t[:largeur - 1], n) for t, n in out]


def lignes_detail(d, largeur):
    if not d:
        return [("détail en attente…", "attention")]
    m, sw = d.get("memoire") or [0, 0, 0], d.get("swap") or [0, 0]
    out = [("%s (%s, %s cœurs) -- CPU %s %%  iowait %s %%  steal %s %%  charge %s" % (d["nom"], d.get("nature"), d.get("ncpu"), fmt(d.get("cpu")), fmt(d.get("iowait")),
                                                                                     fmt(d.get("steal")), " ".join(str(x) for x in d.get("charge") or [])), "titre"),
           ("mémoire %s / %s%s (%s %%%s)   swap %s / %s" % (go(m[1]), go(m[0]), " dont ARC %s" % go(m[2]) if len(m) > 2 and m[2] and d.get("nature") in ("pve", "hote") else "", fmt(d.get("memoire_pct")),
                                                                  " hors ARC" if len(m) > 2 and m[2] and d.get("nature") in ("pve", "hote") else "",
                                                                  go(sw[1]), go(sw[0])), "normal")]
    cc = d.get("coeurs") or [] if d.get("nature") != "ct" else []   # #803 : cœurs d'un CT (lxcfs) non significatifs
    for i in range(0, len(cc), 4):
        out.append(("  ".join("%2d[%s]%4s" % (i + j, barre(v, 8), fmt(v)) for j, v in enumerate(cc[i:i + 4])), "normal"))
    pic = d.get("pic_24h") or {}
    if pic:
        out.append(("pics 24 h : CPU %s %% (p95 %s)  mémoire %s %%  iowait %s %%  steal %s %%" % (fmt(pic.get("cpu")), fmt(pic.get("cpu_p95")), fmt(pic.get("memoire")),
                                                                                            fmt(pic.get("iowait")), fmt(pic.get("steal"))), "normal"))
    for mp, t, u in d.get("disques") or []:
        out.append(("disque %-20s [%s] %s %%  %s / %s" % (mp[:20], barre(100.0 * u / t if t else None), fmt(round(100.0 * u / t, 1) if t else None), go(u), go(t)), "normal"))
    for z in d.get("pools") or []:
        out.append(("pool   %-20s [%s] %s %%  %s" % (z[0], barre(100.0 * z[2] / z[1] if z[1] else None), fmt(round(100.0 * z[2] / z[1], 1) if z[1] else None), z[3]), "normal"))
    if d.get("invites"):
        out.append(("", "normal"))
        out.append(("%-6s %-20s %-3s %8s %7s %9s %9s %9s" % ("ID", "INVITÉ", "", "% NŒUD", "CŒURS", "MÉM", "HORS CACHE", "LIMITE"), "titre"))
        for g in d["invites"][:20]:
            out.append(("%-6s %-20s %-3s %8s %7s %9s %9s %9s" % (g[0], (g[1] or "")[:20], g[2], fmt(g[3]), fmt(g[4]), go(g[5]), go(g[6]), go(g[7] if len(g) > 7 else None)), "normal"))
    out.append(("", "normal"))
    out.append(("%-8s %-24s %7s %9s %s" % ("PID", "PROCESSUS", "CPU %", "RSS", "INVITÉ"), "titre"))
    for p in d.get("processus_top") or []:
        out.append(("%-8s %-24s %7s %9s %s" % (p[0], p[1][:24], fmt(p[2]), go(p[3]), p[4] if len(p) > 4 and p[4] else ""), "normal"))
    return [(t[:largeur - 1], n) for t, n in out]


def adresse(spec):
    h, _, p = spec.rpartition(":")
    return socket.getaddrinfo(h.strip("[]"), int(p or 8399), socket.AF_INET, socket.SOCK_DGRAM)[0][4]


def boucle(sock, cle, relais, vue, sur_tick, voir=lambda: ""):
    dernier, vu = 0, None
    while True:
        v = voir()
        if time.time() - dernier > 5 or v != vu:     # abonnement renouvelé, ou hôte regardé changé : tout de suite
            try:
                sock.sendto(emballer(MAGIE_S, cle, {"t": time.time(), "voir": v}), relais)
            except OSError:
                pass
            dernier, vu = time.time(), v
        nouveaux = []
        try:
            while True:
                p, _ = sock.recvfrom(65535)
                o = deballer(p, cle, MAGIE_R)
                if o:
                    nouveaux += vue.integrer(o)
        except (socket.timeout, BlockingIOError):
            pass
        if sur_tick(nouveaux) is False:
            return


def main(argv=None):
    ap = argparse.ArgumentParser(description="si-htop : client UDP (#800)")
    ap.add_argument("--relais", required=True, help="hôte:port du relais (port UDP publié, 8399 par défaut)")
    ap.add_argument("--cle-fichier", default=os.path.expanduser("~/.si-htop-cle"))
    ap.add_argument("--son", action="store_true", help="signal sonore à chaque nouveau constat critique")
    ap.add_argument("--texte", action="store_true", help="sans curses : tableau réimprimé toutes les 2 s")
    a = ap.parse_args(argv)
    try:
        with open(a.cle_fichier) as fh:
            cle = fh.read().strip().encode("utf-8")
    except OSError as e:
        sys.exit("clé client illisible (%s) : %s" % (a.cle_fichier, e))
    relais = adresse(a.relais)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    vue = Vue()
    if a.texte:
        def tick(nouveaux):
            if a.son and nouveaux:
                sys.stdout.write("\a")
            sys.stdout.write("\033[2J\033[H" + "\n".join(t for t, _ in lignes_liste(vue, -1, 200)) + "\n")
            sys.stdout.flush()
        return boucle(sock, cle, relais, vue, tick)
    try:
        import curses
    except ImportError:
        sys.exit("curses absent (Windows : pip install windows-curses), ou relancer avec --texte")

    def ecran(scr):
        curses.curs_set(0)
        scr.nodelay(True)
        curses.start_color()
        curses.use_default_colors()
        for i, c in enumerate((curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_GREEN), 1):
            curses.init_pair(i, c, -1)
        attr = {"normal": curses.color_pair(1), "titre": curses.color_pair(2) | curses.A_BOLD, "attention": curses.color_pair(3),
                "alerte": curses.color_pair(4) | curses.A_BOLD, "choix": curses.color_pair(5) | curses.A_REVERSE}
        etat = {"choix": 0, "detail": False, "tri": "c", "son": a.son}

        def voir():
            l = vue.liste(etat["tri"])
            return l[etat["choix"]][1]["nom"] if etat["detail"] and 0 <= etat["choix"] < len(l) else ""

        def tick(nouveaux):
            k = scr.getch()
            n = len(vue.liste(etat["tri"]))
            if k in (ord("q"), 27):
                return False
            if k == curses.KEY_DOWN:
                etat["choix"] = min(n - 1, etat["choix"] + 1)
            elif k == curses.KEY_UP:
                etat["choix"] = max(0, etat["choix"] - 1)
            elif k in (10, 13, curses.KEY_ENTER):
                etat["detail"] = not etat["detail"]
                vue.detail = None
            elif k in (ord("c"), ord("m"), ord("n")):
                etat["tri"] = chr(k)
            elif k == ord("s"):
                etat["son"] = not etat["son"]
            if etat["son"] and nouveaux:
                curses.beep()
            hh, ww = scr.getmaxyx()
            scr.erase()
            entete = "si-htop -- relais %s:%s -- %s -- son %s -- %s" % (relais[0], relais[1], time.strftime("%H:%M:%S"), "on" if etat["son"] else "off",
                                                                       "liaison perdue" if time.time() - vue.recu > 10 else "en direct")
            scr.addnstr(0, 0, entete, ww - 1, attr["titre"])
            ls = lignes_detail(vue.detail, ww) if etat["detail"] else lignes_liste(vue, etat["choix"], ww, etat["tri"])
            for i, (t, niv) in enumerate(ls[:hh - 2]):
                scr.addnstr(i + 1, 0, t, ww - 1, attr.get(niv, attr["normal"]))
            scr.addnstr(hh - 1, 0, "↑↓ choisir  Entrée détail/liste  c/m/n tri  s son  q quitter", ww - 1, attr["titre"])
            scr.refresh()
        boucle(sock, cle, relais, vue, tick, voir)
    curses.wrapper(ecran)
    return 0


if __name__ == "__main__":
    sys.exit(main())
