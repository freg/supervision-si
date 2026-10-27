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
ROLES_LOURDS = ("site ou application web", "application web", "base de données", "messagerie", "partage de fichiers", "annuaire")
PHASES = (("1", "Mesures immédiates de sécurité"), ("2", "Systèmes urgents et ce qui en dépend"),
          ("3", "Mises à niveau à planifier"), ("4", "Systèmes à surveiller"), ("5", "Nettoyage (systèmes inutilisés)"))
IMMEDIAT = ("appliquer les mises à jour de sécurité", "mettre à jour les paquets", "limiter l'accès depuis internet")   # en minuscules : comparé à l'action en minuscules


# #882 : barème façon planning poker -- un poids en POINTS par type d'action ; heures = points × heures_par_point ×
# marge. Tout est réglable (réglage `etat_bareme`, page « Barème » de l'état des lieux) ; valeurs ci-dessous = défaut.
ECHELLE = (0.5, 1, 2, 3, 5, 8, 13, 20, 40)
TYPES = (  # (identifiant, libellé, points par défaut)
    ("os_base", "Mise à niveau du système : socle (sauvegarde, première version, vérification)", 3),
    ("os_version", "Mise à niveau du système : par version supplémentaire", 2),
    ("os_reconstruction", "Reconstruction sur un système neuf (écart de versions au-delà du seuil)", 8),
    ("os_windows", "Mise à niveau ou réinstallation Windows", 8),
    ("os_inconnu", "Mise à niveau d'un système non identifié", 5),
    ("hyperviseur", "Hyperviseur : déplacer les machines, mettre à niveau, remettre en place", 13),
    ("role_lourd", "Par service à revérifier (web, base de données, messagerie, partage, annuaire)", 1),
    ("log_php", "Logiciel : PHP", 3), ("log_nextcloud", "Logiciel : Nextcloud", 5), ("log_owncloud", "Logiciel : ownCloud (vers Nextcloud)", 8),
    ("log_mysql", "Logiciel : MySQL / MariaDB", 3), ("log_postgresql", "Logiciel : PostgreSQL", 3), ("log_apache", "Logiciel : Apache", 2),
    ("log_tomcat", "Logiciel : Tomcat", 3), ("log_proxmox", "Logiciel : Proxmox", 5), ("log_samba", "Logiciel : Samba", 2),
    ("log_autre", "Logiciel : autre", 2),
    ("securite", "Appliquer les correctifs de sécurité", 1), ("paquets", "Mettre à jour les paquets", 1),
    ("filtrage", "Limiter l'accès depuis Internet", 2), ("identifier", "Identifier un appareil découvert", 1),
    ("agent_invite", "Installer l'agent invité d'une VM", 1), ("declarer", "Déclarer un système à la main", 0.5),
    ("archiver", "Archiver puis supprimer un système inutilisé", 1), ("defaut", "Autre action", 2),
)
LIBELLES = {k: l for k, l, _ in TYPES}
CATEGORIES = (("physique", "Serveur physique (pas d'instantané, matériel)", 1.5), ("virtuel", "Machine virtuelle", 1.0),
              ("conteneur", "Conteneur", 0.8), ("sgbd", "Base de données (SGBD) : export, cohérence, reprise -- s'ajoute", 1.5))
AUTOMATISABLES = ("securite", "paquets", "agent_invite", "os_base", "os_version", "declarer")
DEFAUT_BAREME = {"points": {k: p for k, _, p in TYPES}, "heures_par_point": 1.0, "marge": MARGE, "seuil_reconstruction": 3,
                 "logiciel_avec_os": 0.5, "categories": {k: f for k, _, f in CATEGORIES},
                 "automatisable": {k: k in AUTOMATISABLES for k, _, _ in TYPES}, "facteur_repetition": 0.3}


def categories(l):
    """#882 : catégories d'un système -> [physique | virtuel | conteneur] (+ sgbd)."""
    base = {"VM": "virtuel", "CT": "conteneur"}.get(l.get("type"), "physique")
    return [base] + (["sgbd"] if "base de données" in (l.get("roles") or []) else [])
LOG_TYPE = {"php": "log_php", "nextcloud": "log_nextcloud", "owncloud": "log_owncloud", "mysql": "log_mysql", "mariadb": "log_mysql",
            "postgresql": "log_postgresql", "apache-httpd": "log_apache", "tomcat": "log_tomcat", "proxmox-ve": "log_proxmox",
            "proxmox-backup": "log_proxmox", "samba": "log_samba"}


def bareme_normalise(b=None):
    """Réglage (partiel) -> barème complet et borné."""
    b = b or {}
    out = {"points": dict(DEFAUT_BAREME["points"])}
    for k, v in (b.get("points") or {}).items():
        if k in out["points"]:
            try:
                out["points"][k] = max(0.0, min(100.0, float(v)))
            except (TypeError, ValueError):
                pass

    def borne(k, lo, hi):
        try:
            return max(lo, min(hi, float(b.get(k, DEFAUT_BAREME[k]))))
        except (TypeError, ValueError):
            return DEFAUT_BAREME[k]
    out["heures_par_point"] = borne("heures_par_point", 0.1, 16)
    out["marge"] = borne("marge", 1, 10)
    out["seuil_reconstruction"] = int(borne("seuil_reconstruction", 1, 20))
    out["logiciel_avec_os"] = borne("logiciel_avec_os", 0, 1)
    out["facteur_repetition"] = borne("facteur_repetition", 0, 1)
    out["categories"] = dict(DEFAUT_BAREME["categories"])
    for k, v in (b.get("categories") or {}).items():
        if k in out["categories"]:
            try:
                out["categories"][k] = max(0.1, min(10.0, float(v)))
            except (TypeError, ValueError):
                pass
    out["automatisable"] = dict(DEFAUT_BAREME["automatisable"])
    for k, v in (b.get("automatisable") or {}).items():
        if k in out["automatisable"]:
            out["automatisable"][k] = bool(v)
    return out


def _ecart(l):
    fam, ver = (l["os"].get("famille") or ""), str(l["os"].get("version") or "")
    m = re.match(r"^(\d+)", ver)
    if fam in CIBLE and m:
        return max(1, CIBLE[fam] - int(m.group(1)))
    return None


def poids(action, l, bareme=None, mise_a_niveau_os=False):
    """-> (points, détail, [(type, quantité)]) : composition du poids d'une action d'après le barème."""
    b = bareme or bareme_normalise()
    P = b["points"]
    a = action.lower()
    roles = sum(1 for r in l.get("roles") or [] if r in ROLES_LOURDS)
    if a.startswith("mettre à niveau le système") or a.startswith("planifier la mise à niveau du système"):
        ecart = _ecart(l)
        if l["type"] == "nœud":
            parts = [("hyperviseur", 1), ("role_lourd", roles)]
            det = "hyperviseur"
        elif (l["os"].get("famille") or "").startswith("windows"):
            parts, det = [("os_windows", 1), ("role_lourd", roles)], "Windows"
        elif ecart is not None and ecart > b["seuil_reconstruction"]:
            parts, det = [("os_reconstruction", 1), ("role_lourd", roles)], "écart de %d versions : reconstruction" % ecart
        elif ecart:
            parts, det = [("os_base", 1), ("os_version", ecart - 1), ("role_lourd", roles)], "%d version(s) d'écart" % ecart
        else:
            parts, det = [("os_inconnu", 1), ("role_lourd", roles)], "système à identifier"
        parts = [(t, q) for t, q in parts if q]
        return sum(P[t] * q for t, q in parts), det, parts
    m = re.match(r"^(?:remplacer|planifier le remplacement de) (\S+)", a)
    if m:
        t = LOG_TYPE.get(m.group(1), "log_autre")
        f = b["logiciel_avec_os"] if mise_a_niveau_os else 1.0
        return P[t] * f, ("mis à jour avec le système (×%s)" % f if mise_a_niveau_os else "mise à jour du logiciel"), [(t, f)]
    for prefixe, t in (("appliquer les mises à jour de sécurité", "securite"), ("mettre à jour les paquets", "paquets"),
                       ("limiter l'accès depuis internet", "filtrage"), ("identifier l'hôte", "identifier"),
                       ("installer l'agent invité", "agent_invite"), ("déclarer le système", "declarer"), ("archiver puis supprimer", "archiver")):
        if a.startswith(prefixe):
            return P[t], LIBELLES[t], [(t, 1)]
    return P["defaut"], LIBELLES["defaut"], [("defaut", 1)]


def heures_action(action, l, mise_a_niveau_os=False, bareme=None):
    """Compatibilité : estimation BRUTE en heures (points × heures par point), sans marge."""
    b = bareme or bareme_normalise()
    pts, det, _ = poids(action, l, b, mise_a_niveau_os)
    return pts * b["heures_par_point"], det


def taches(l, marge=None, bareme=None, vus=None):
    """Actions d'une ligne -> [{action, points, brut, heures, detail, parts, coef}] : points du barème × coefficient des
    catégories du système (physique / virtuel / conteneur, SGBD) ; un type AUTOMATISABLE déjà rencontré (`vus`, partagé
    sur tout le plan) ne compte plus que pour le facteur de répétition. brut = points × h/point ; heures = brut × marge."""
    b = bareme or bareme_normalise()
    marge = b["marge"] if marge is None else marge
    vus = {} if vus is None else vus
    coef = 1.0
    for c in categories(l):
        coef *= b["categories"].get(c, 1.0)
    os_ = any(x.lower().startswith(("mettre à niveau le système", "planifier la mise à niveau du système")) for x in l.get("actions") or [])
    out = []
    for a in dict.fromkeys(l.get("actions") or []):
        _pts, det, parts = poids(a, l, b, mise_a_niveau_os=os_)
        pts, eff = 0.0, []
        for t, q in parts:
            rep = b["facteur_repetition"] if b["automatisable"].get(t) and vus.get(t) else 1.0
            vus[t] = vus.get(t, 0) + 1
            eff.append((t, q * rep))
            pts += b["points"][t] * q * rep
        pts *= coef
        brut = pts * b["heures_par_point"]
        out.append({"action": a, "points": round(pts, 2), "brut": round(brut, 2), "heures": round(brut * marge, 1), "detail": det,
                    "parts": eff, "coef": round(coef, 2), "categories": categories(l)})
    return out


def groupes(etat):
    """Systèmes à traiter regroupés par dépendances (union des liens « utilise ») -> [{pivot, membres (ordonnés)}].
    Pivot = le membre dont dépendent le plus d'autres systèmes ; il passe en premier, puis les autres par score."""
    lignes = {l["key"]: l for l in etat["systemes"] if not l.get("variante_de")}   # #879 : copies / clones / tests hors planning
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


def plan(etat, marge=None, personnes=1, debut=None, heures_jour=HEURES_JOUR, bareme=None):
    """-> {hypotheses, taches: [{phase, phase_nom, groupe, systeme, key, action, brut, heures, jours, debut, fin, personne}],
    phases: [{phase, nom, heures, jours, debut, fin, systemes}], total: {brut, heures, jours, fin}}."""
    b = bareme_normalise(bareme)
    if marge is not None:
        b["marge"] = marge
    marge = b["marge"]
    debut = _suivant_ouvre(debut or (dt.date.today() + dt.timedelta(days=1)))
    personnes = max(1, int(personnes or 1))
    lots = {p: [] for p, _ in PHASES}           # phase -> [(libellé du groupe, [tâches dans l'ordre])]
    vus = {}                                     # #882 : types automatisables déjà rencontrés (répétition)
    for g in groupes(etat):
        pire = min(("urgent", "à planifier", "à surveiller", "ok", "inactif").index(m["niveau"]) for m in g["membres"])
        phase = {0: "2", 1: "3", 2: "4", 3: "4", 4: "5"}[pire]
        nom_g = g["pivot"].get("libelle") or g["pivot"]["name"] or g["pivot"]["key"]
        lib = nom_g if len(g["membres"]) == 1 else "%s et %d système(s) qui en dépendent" % (nom_g, len(g["membres"]) - 1)
        seq, imm = [], []
        for m in g["membres"]:
            for t in taches(m, marge, b, vus):
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
    return {"hypotheses": {"marge": marge, "personnes": personnes, "heures_jour": heures_jour, "debut": debut.isoformat(),
                           "heures_par_point": b["heures_par_point"], "points": round(sum(t["points"] for t in out), 1)},
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


def pesage(etat, bareme=None):
    """#882 : pour la page du barème -- par type : libellé, points, nombre d'occurrences dans l'état actuel, points et heures
    totaux (avec et sans marge). Sert à calibrer : voir où part le temps et ajuster le poids des types les plus fréquents."""
    b = bareme_normalise(bareme)
    occ = {k: 0.0 for k in b["points"]}
    nb = {k: 0 for k in b["points"]}
    cat = {k: {"systemes": 0, "points": 0.0} for k, _, _ in CATEGORIES}
    vus = {}
    for l in etat["systemes"]:
        if l.get("variante_de"):
            continue
        ts = taches(l, None, b, vus)
        if not ts:
            continue
        for c in categories(l):
            cat[c]["systemes"] += 1
            cat[c]["points"] += sum(t["points"] for t in ts)
        for t in ts:
            for typ, q in t["parts"]:
                occ[typ] += q * t["coef"]
                nb[typ] += 1
    lignes = []
    for k, lib, defaut in TYPES:
        pts = occ[k] * b["points"][k]
        lignes.append({"type": k, "libelle": lib, "points": b["points"][k], "defaut": defaut, "occurrences": nb[k], "quantite": round(occ[k], 2),
                       "automatisable": b["automatisable"].get(k, False),
                       "total_points": round(pts, 1), "heures": round(pts * b["heures_par_point"], 1),
                       "heures_marge": round(pts * b["heures_par_point"] * b["marge"], 1)})
    tp = sum(x["total_points"] for x in lignes)
    return {"bareme": b, "echelle": list(ECHELLE), "types": lignes,
            "categories": [{"categorie": k, "libelle": lib, "coef": b["categories"][k], "defaut": d, "systemes": cat[k]["systemes"],
                            "points": round(cat[k]["points"], 1)} for k, lib, d in CATEGORIES],
            "total": {"points": round(tp, 1), "heures": round(tp * b["heures_par_point"], 1), "heures_marge": round(tp * b["heures_par_point"] * b["marge"], 1),
                      "jours_marge": round(tp * b["heures_par_point"] * b["marge"] / HEURES_JOUR, 1)}}
