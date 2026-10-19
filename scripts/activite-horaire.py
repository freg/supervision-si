#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Activité réelle d'un conteneur Proxmox, heure par heure (#785) -- pour choisir le créneau d'une bascule.

Lancé en root sur le PVE qui porte le conteneur (Python 3.5+, aucune dépendance, lecture seule) :
    python3 activite-horaire.py 102 [semaines=8]
Lit, par la racine du conteneur vue de l'hôte, les journaux d'accès web (Apache, Nginx, y compris les rotations .gz),
écarte les robots, la supervision et les fichiers statiques, puis affiche :
  - la grille jour de la semaine × heure (requêtes par semaine en moyenne, et nombre de visiteurs distincts) ;
  - l'activité des 28 derniers jours ;
  - les adresses les plus actives (pour repérer une supervision ou un robot à écarter : --exclure 1.2.3.4,5.6.7.8) ;
  - les créneaux les plus calmes des jours ouvrés."""
import collections
import datetime
import glob
import gzip
import os
import re
import subprocess
import sys

LIGNE = re.compile(r'^(?:\S+:\d+ )?(\S+) \S+ (\S+) \[(\d{2})/(\w{3})/(\d{4}):(\d{2}):\d{2}:\d{2} [^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) \S+(?: "[^"]*" "([^"]*)")?')
MOIS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
ROBOTS = re.compile(r"bot|spider|crawl|slurp|monitor|uptime|pingdom|zabbix|nagios|check_http|curl|wget|python-requests|go-http|headless", re.I)
STATIQUE = re.compile(r"\.(css|js|png|jpe?g|gif|svg|ico|woff2?|ttf|map|webp)(\?|$)", re.I)
JOURS = "lun mar mer jeu ven sam dim".split()


def racine(ct):
    pid = subprocess.check_output(["lxc-info", "-n", str(ct), "-p", "-H"]).decode().strip()
    if not pid:
        sys.exit("conteneur %s arrêté (ou introuvable) : rien à lire" % ct)
    return "/proc/%s/root" % pid


def journaux(r):
    motifs = ["var/log/apache2/*access*", "var/log/nginx/*access*", "var/log/httpd/*access*", "var/www/*/logs/*access*", "var/log/*/*access*"]
    vus = []
    for m in motifs:
        for f in sorted(glob.glob(os.path.join(r, m))):
            if f not in vus and os.path.isfile(f):
                vus.append(f)
    return vus


def lire(f):
    op = gzip.open if f.endswith(".gz") else open
    with op(f, "rt", errors="replace") as fh:
        for l in fh:
            yield l


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ct, semaines = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8
    exclure = set()
    if "--exclure" in sys.argv:
        exclure = set(sys.argv[sys.argv.index("--exclure") + 1].split(","))
    r = racine(ct)
    fichiers = journaux(r)
    if not fichiers:
        sys.exit("aucun journal d'accès web trouvé dans le conteneur %s (chercher : find %s/var/log -name '*access*')" % (ct, r))
    depuis = datetime.datetime.now() - datetime.timedelta(weeks=semaines)
    grille = collections.Counter()
    visiteurs = collections.defaultdict(set)
    jours = collections.Counter()
    ips = collections.Counter()
    ecartees = refusees = lues = nonlues = anciennes = 0
    exemple = None
    comptes = collections.Counter()
    heures_compte = collections.defaultdict(set)
    premier = dernier = None
    for f in fichiers:
        for l in lire(f):
            lues += 1
            m = LIGNE.match(l)
            if not m:
                nonlues += 1
                exemple = exemple or l.strip()[:200]
                continue
            ip, user, j, mo, an, h, _meth, url, code, ua = m.groups()
            d = datetime.datetime(int(an), MOIS.get(mo, 1), int(j), int(h))
            if d < depuis:
                anciennes += 1
                continue
            if ip in exclure or ip in ("::1", "127.0.0.1") or ROBOTS.search(ua or "") or STATIQUE.search(url):
                ecartees += 1
                continue
            if int(code) >= 400:          # 401/403/404 en rafale : scanners (et mots de passe refusés)
                refusees += 1
                continue
            premier = d if premier is None or d < premier else premier
            dernier = d if dernier is None or d > dernier else dernier
            cle = (d.weekday(), d.hour)
            grille[cle] += 1
            visiteurs[cle].add(ip)
            jours[d.date()] += 1
            ips[ip] += 1
            if user != "-":
                comptes[user] += 1
                heures_compte[user].add(d.hour)
    print("CT %s · %d journal(aux) · %d dernières semaines" % (ct, len(fichiers), semaines))
    for f in fichiers:
        print("   " + f.replace(r, ""))
    print("Lignes lues : %d · format non reconnu : %d · antérieures à la période : %d · écartées (robots, supervision, local, "
          "statiques) : %d · en erreur ≥ 400 (scanners) : %d" % (lues, nonlues, anciennes, ecartees, refusees))
    if exemple:
        print("Exemple de ligne non reconnue : " + exemple)
    if not premier:
        print("Aucune requête humaine sur la période.")
        return
    nsem = max(1.0, ((dernier - premier).days + 1) / 7.0)
    print("Période lue : %s -> %s (%.1f semaine(s)) · %d requêtes retenues, %d écartées" % (premier.date(), dernier.date(), nsem, sum(grille.values()), ecartees))
    print("\nRequêtes par semaine en moyenne (jour × heure) ; [n] = visiteurs distincts sur la période")
    print("      " + "".join("%5dh" % h for h in range(24)))
    for wd in range(7):
        print("%-5s " % JOURS[wd] + "".join("%6s" % (("%.0f" % (grille[(wd, h)] / nsem)) if grille[(wd, h)] else ".") for h in range(24)))
        print("      " + "".join("%6s" % (("[%d]" % len(visiteurs[(wd, h)])) if visiteurs[(wd, h)] else "") for h in range(24)))
    print("\n28 derniers jours :")
    fin = dernier.date()
    for i in range(27, -1, -1):
        d = fin - datetime.timedelta(days=i)
        n = jours.get(d, 0)
        print("  %s %s %6d %s" % (JOURS[d.weekday()], d, n, "#" * min(60, int(n ** 0.5))))
    print("\nAdresses les plus actives (une supervision ou un robot ? relancer avec --exclure) :")
    for ip, n in ips.most_common(10):
        print("  %-40s %d" % (ip, n))
    if comptes:
        print("\nComptes authentifiés (WebDAV / synchronisation) : requêtes et heures où ils travaillent")
        for u, n in comptes.most_common(15):
            hs = sorted(heures_compte[u])
            print("  %-30s %7d   %s" % (u[:30], n, " ".join("%d" % h for h in hs)))
    print("\nPlage d'activité par jour (heures avec au moins 1 requête par semaine en moyenne) :")
    for wd in range(7):
        hs = [h for h in range(24) if grille[(wd, h)] / nsem >= 1]
        print("  %s : %s" % (JOURS[wd], "de %d h à %d h" % (hs[0], hs[-1] + 1) if hs else "aucune activité régulière"))
    ouvres = sorted(((grille[(wd, h)], wd, h) for wd in range(5) for h in range(7, 20)))
    print("\nCréneaux les plus calmes des jours ouvrés (7 h - 20 h) :")
    for n, wd, h in ouvres[:8]:
        print("  %s %02d h-%02d h : %.1f requête(s) par semaine" % (JOURS[wd], h, h + 1, n / nsem))


if __name__ == "__main__":
    main()
