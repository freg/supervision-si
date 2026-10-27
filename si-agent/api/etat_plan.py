# -*- coding: utf-8 -*-
"""Plan estimé de l'état des lieux (livraison #878) : temps de réalisation action par action (tests compris) avec marge,
regroupement des systèmes par dépendances (un serveur de base de données et les applications qui en dépendent sont
traités ensemble), phases et calendrier (Gantt) pour les décideurs.

Hypothèses (réglables, `etat_plan` dans les réglages) : estimation BRUTE en heures, tests compris, multipliée par la
MARGE (3 par défaut) ; 7 h de travail par jour, du lundi au vendredi ; N personnes (1 par défaut) ; un groupe de
dépendances est confié à une seule personne, dans l'ordre : le système dont les autres dépendent d'abord.
"""
import datetime as dt
import re

MARGE = 3
HEURES_JOUR = 7
CIBLE = {"debian": 13, "ubuntu": 24, "centos": 9, "rocky": 9, "almalinux": 9, "proxmox-ve": 9, "proxmox-backup": 4}
COMPOSANT_H = {"php": 4, "nextcloud": 6, "owncloud": 8, "mysql": 6, "mariadb": 5, "postgresql": 6, "apache-httpd": 3, "tomcat": 4,
               "proxmox-ve": 8, "proxmox-backup": 4, "samba": 3}
ROLES_LOURDS = ("site ou application web", "application web", "base de données", "messagerie", "partage de fichiers", "annuaire")
PHASES = (("1", "Mesures immédiates de sécurité"), ("2", "Systèmes urgents et ce qui en dépend"),
          ("3", "Mises à niveau à planifier"), ("4", "Systèmes à surveiller"), ("5", "Nettoyage (systèmes inutilisés)"))
IMMEDIAT = ("appliquer les mises à jour de sécurité", "mettre à jour les paquets", "limiter l'accès depuis internet")   # en minuscules : comparé à l'action en minuscules


def _ecart(l):
    fam, ver = (l["os"].get("famille") or ""), str(l["os"].get("version") or "")
    m = re.match(r"^(\d+)", ver)
    if fam in CIBLE and m:
        return max(1, CIBLE[fam] - int(m.group(1)))
    return None


def heures_action(action, l, mise_a_niveau_os=False):
    """Estimation BRUTE (heures, tests compris) d'une action d'une ligne d'état des lieux -> (heures, détail)."""
    a = action.lower()
    roles = sum(1 for r in l.get("roles") or [] if r in ROLES_LOURDS)
    if a.startswith("mettre à niveau le système") or a.startswith("planifier la mise à niveau du système"):
        ecart = _ecart(l)
        if l["type"] == "nœud":
            return 16.0 + 4 * roles, "hyperviseur : déplacer les machines hébergées, mettre à niveau, vérifier, remettre en place"
        if (l["os"].get("famille") or "").startswith("windows"):
            return 12.0 + 2 * roles, "Windows : sauvegarde, mise à niveau ou réinstallation, vérification des applications"
        if ecart is not None and ecart >= 3:
            return 16.0 + 3 * roles, "écart de %d versions : reconstruction sur un système neuf et reprise des données" % ecart
        if ecart:
            return 4.0 + 3 * ecart + 2 * roles, "%d version(s) d'écart : sauvegarde, mise à niveau pas à pas, vérification des services" % ecart
        return 8.0 + 2 * roles, "système à identifier : estimation par défaut"
    m = re.match(r"^(?:remplacer|planifier le remplacement de) (\S+)", a)
    if m:
        h = COMPOSANT_H.get(m.group(1), 3)
        return (h / 2.0, "logiciel mis à jour avec le système (moitié du temps)") if mise_a_niveau_os else (float(h), "mise à jour du logiciel et vérification")
    if a.startswith("appliquer les mises à jour de sécurité"):
        return 1.5, "correctifs, redémarrage, vérification"
    if a.startswith("mettre à jour les paquets"):
        return 1.0, "mise à jour, vérification"
    if a.startswith("limiter l'accès depuis internet"):
        return 2.0, "règles de filtrage, vérification des accès légitimes"
    if a.startswith("identifier l'hôte"):
        return 1.0, "identification, puis agent ou déclaration"
    if a.startswith("installer l'agent invité"):
        return 1.0, "installation et vérification"
    if a.startswith("déclarer le système"):
        return 0.5, "déclaration"
    if a.startswith("archiver puis supprimer"):
        return 2.0, "archivage vérifié, puis suppression"
    return 2.0, "estimation par défaut"


def taches(l, marge=MARGE):
    """Actions d'une ligne -> [{action, brut, heures, detail}] (heures = brut × marge)."""
    os_ = any(x.lower().startswith(("mettre à niveau le système", "planifier la mise à niveau du système")) for x in l.get("actions") or [])
    out = []
    for a in dict.fromkeys(l.get("actions") or []):
        h, det = heures_action(a, l, mise_a_niveau_os=os_)
        out.append({"action": a, "brut": h, "heures": round(h * marge, 1), "detail": det})
    return out


def groupes(etat):
    """Systèmes à traiter regroupés par dépendances (union des liens « utilise ») -> [{pivot, membres (ordonnés)}].
    Pivot = le membre dont dépendent le plus d'autres systèmes ; il passe en premier, puis les autres par score."""
    lignes = {l["key"]: l for l in etat["systemes"]}
    parent = {k: k for k in lignes}

    def racine(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for d in etat.get("dependances") or []:
        if d["de"] in parent and d["vers"] in parent:
            parent[racine(d["de"])] = racine(d["vers"])
    paquets = {}
    for k in lignes:
        paquets.setdefault(racine(k), []).append(lignes[k])
    out = []
    for membres in paquets.values():
        if not any(m.get("actions") for m in membres):
            continue
        pivot = max(membres, key=lambda m: (len(m.get("dependants") or []), m["score"]))
        autres = sorted((m for m in membres if m is not pivot), key=lambda m: (-m["score"], m["key"]))
        out.append({"pivot": pivot, "membres": [pivot] + autres})
    return out


def _jours_ouvres(debut, n):
    """Date de fin après n jours ouvrés entamés à partir de `debut` (date), week-ends exclus."""
    d, reste = debut, n
    while True:
        if d.weekday() < 5:
            reste -= 1
            if reste <= 0:
                return d
        d += dt.timedelta(days=1)


def _suivant_ouvre(d):
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def plan(etat, marge=MARGE, personnes=1, debut=None, heures_jour=HEURES_JOUR):
    """-> {hypotheses, taches: [{phase, phase_nom, groupe, systeme, key, action, brut, heures, jours, debut, fin, personne}],
    phases: [{phase, nom, heures, jours, debut, fin, systemes}], total: {brut, heures, jours, fin}}."""
    debut = _suivant_ouvre(debut or (dt.date.today() + dt.timedelta(days=1)))
    personnes = max(1, int(personnes or 1))
    lots = {p: [] for p, _ in PHASES}           # phase -> [(libellé du groupe, [tâches dans l'ordre])]
    for g in groupes(etat):
        pire = min(("urgent", "à planifier", "à surveiller", "ok", "inactif").index(m["niveau"]) for m in g["membres"])
        phase = {0: "2", 1: "3", 2: "4", 3: "4", 4: "5"}[pire]
        nom_g = g["pivot"].get("libelle") or g["pivot"]["name"] or g["pivot"]["key"]
        lib = nom_g if len(g["membres"]) == 1 else "%s et %d système(s) qui en dépendent" % (nom_g, len(g["membres"]) - 1)
        seq, imm = [], []
        for m in g["membres"]:
            for t in taches(m, marge):
                t = dict(t, systeme=m.get("libelle") or m["name"] or m["key"], key=m["key"])
                (imm if t["action"].lower().startswith(IMMEDIAT) and m["niveau"] in ("urgent", "à planifier") else seq).append(t)
        if imm:
            lots["1"].append((lib, imm))
        if seq:
            lots["5" if all(m["niveau"] == "inactif" for m in g["membres"]) else phase].append((lib, seq))
    libre = [debut] * personnes                 # prochain jour libre de chaque personne
    reste_h = [0.0] * personnes                  # heures déjà prises ce jour-là
    out = []
    for p, pnom in PHASES:
        for lib, seq in sorted(lots[p], key=lambda x: -sum(t["heures"] for t in x[1])):
            i = min(range(personnes), key=lambda k: (libre[k], reste_h[k]))
            for t in seq:
                d0, h0 = libre[i], reste_h[i]
                total = h0 + t["heures"]
                jours = int(-(-total // heures_jour))          # jours entamés depuis d0
                fin = _jours_ouvres(d0, max(1, jours))
                reste = total - (jours - 1) * heures_jour
                if reste >= heures_jour:
                    libre[i], reste_h[i] = _suivant_ouvre(fin + dt.timedelta(days=1)), 0.0
                else:
                    libre[i], reste_h[i] = fin, reste
                out.append(dict(t, phase=p, phase_nom=pnom, groupe=lib, jours=round(t["heures"] / heures_jour, 1),
                                debut=d0.isoformat(), fin=fin.isoformat(), personne=i + 1))
    phases = []
    for p, pnom in PHASES:
        ts = [t for t in out if t["phase"] == p]
        if ts:
            h = sum(t["heures"] for t in ts)
            phases.append({"phase": p, "nom": pnom, "heures": round(h, 1), "jours": round(h / heures_jour, 1), "debut": min(t["debut"] for t in ts),
                           "fin": max(t["fin"] for t in ts), "systemes": len({t["key"] for t in ts}), "groupes": len({t["groupe"] for t in ts})})
    brut = sum(t["brut"] for t in out)
    h = sum(t["heures"] for t in out)
    return {"hypotheses": {"marge": marge, "personnes": personnes, "heures_jour": heures_jour, "debut": debut.isoformat()},
            "taches": out, "phases": phases,
            "total": {"brut": round(brut, 1), "heures": round(h, 1), "jours": round(h / heures_jour, 1), "fin": max((t["fin"] for t in out), default=None)}}


def par_systeme(pl):
    """{key: {heures, jours, brut}} pour la colonne « temps estimé » du tableau des systèmes."""
    out = {}
    for t in pl["taches"]:
        x = out.setdefault(t["key"], {"heures": 0.0, "brut": 0.0})
        x["heures"] += t["heures"]
        x["brut"] += t["brut"]
    for x in out.values():
        x["jours"] = round(x["heures"] / HEURES_JOUR, 1)
    return out
