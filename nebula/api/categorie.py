# -*- coding: utf-8 -*-
"""Catégorisation des clients par leurs éléments et leur comportement (livraison #1003, identification des cibles
tranche 3) -- logique PURE, testée (tests/test_categorie.py).

On catégorise comme on le fait à vue : le système et le nom annoncés, le fabricant, une MAC aléatoire, puis le
comportement (présence continue ou aux heures ouvrées, nuits, week-ends, mobilité entre bornes, régularité et sens des
volumes). Chaque indice a un poids et une preuve ; ce qui est SINGULIER pour ce client par rapport à la population du
site pèse plus (un fabricant que 90 % des clients partagent ne distingue presque rien). Résultat : hypothèses classées,
catégorie proposée avec sa confiance, et les singularités du client -- jamais une affirmation sans preuve."""
import re
import unicodedata

CATEGORIES = ("mobile Android", "mobile Apple", "poste Windows", "poste Mac", "machine Linux / sans écran",
              "équipement réseau", "imprimante", "caméra / objet connecté", "casque VR")
MOBILES = ("mobile Android", "mobile Apple", "casque VR")
MACHINES = ("machine Linux / sans écran", "équipement réseau", "imprimante", "caméra / objet connecté")
POSTES = ("poste Windows", "poste Mac")
# compatibilité type d'élément d'une liste de surveillance -> catégories
COMPATIBLES = {"tablette": ("mobile Android", "mobile Apple"), "telephone": ("mobile Android", "mobile Apple"),
               "casque": ("casque VR", "mobile Android"), "poste": POSTES + ("machine Linux / sans écran",),
               "serveur": ("machine Linux / sans écran", "poste Windows"), "imprimante": ("imprimante",),
               "camera": ("caméra / objet connecté",), "borne": ("équipement réseau",)}

SYSTEME = ((r"android", "mobile Android", 40), (r"ipad|iphone|ios", "mobile Apple", 40), (r"windows", "poste Windows", 40),
           (r"mac ?os|os ?x|macos", "poste Mac", 40), (r"linux|ubuntu|debian|raspbian|centos|fedora", "machine Linux / sans écran", 30))
NOM = ((r"galaxy|android|^sm-|redmi|pixel|oppo|huawei|xiaomi|oneplus|motorola", "mobile Android", 25),
       (r"iphone|ipad", "mobile Apple", 30), (r"^(desktop|laptop|pc|portable)-", "poste Windows", 30),
       (r"macbook|imac|mac-?mini|mbp", "poste Mac", 30), (r"raspberry|^rpi|ubuntu|debian|\bnuc\b|mini-?pc|^pve|^srv|serveur|server", "machine Linux / sans écran", 20),
       (r"^npi|printer|imprim|^brw|epson|canon|kyocera|xerox", "imprimante", 30), (r"quest|oculus|pico", "casque VR", 35),
       (r"\bcam|^ipc|nvr|dvr", "caméra / objet connecté", 15), (r"zyxel|^usg|^nwa|^wax|^wbe|^gs\d|^xs\d|mikrotik|unifi", "équipement réseau", 30))
FABRICANT = ((r"samsung|xiaomi|oppo|huawei|google|motorola|oneplus|realme|vivo", (("mobile Android", 15),)),
             (r"apple", (("mobile Apple", 12), ("poste Mac", 8))),
             (r"intel|dell|lenovo|asustek|micro-star|liteon|azurewave|hon hai|foxconn|cloud network technology|gigabyte|microsoft",
              (("poste Windows", 10), ("machine Linux / sans écran", 8))),   # cartes Wi-Fi / réseau intégrées des PC et mini-PC
             (r"brother|epson|canon|kyocera|xerox|lexmark|ricoh|hewlett|hp inc", (("imprimante", 20), ("poste Windows", 5))),
             (r"zyxel|mikrotik|ubiquiti|cisco|tp-link|netgear|aruba|ruckus|fortinet", (("équipement réseau", 30),)),
             (r"hikvision|dahua|axis|espressif|tuya|shelly|sonoff|hanwha|reolink", (("caméra / objet connecté", 30),)),
             (r"meta platforms|oculus|pico", (("casque VR", 30),)),
             (r"raspberry", (("machine Linux / sans écran", 30),)))
ADAPTATEURS = r"edimax|asix|realtek semiconductor|ugreen|tp-link.*usb|d-link"


def plier(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def mac_aleatoire(mac):
    h = re.sub(r"[^0-9a-f]", "", str(mac or "").lower())
    return len(h) == 12 and int(h[1], 16) & 2 == 2


def _fam(regles, texte):
    t = plier(texte)
    return next((cat for rx, cat, _p in regles if t and re.search(rx, t)), None)


def comportement(p):
    """Profil d'activité -> classe de comportement (ou None si trop peu de données)."""
    if not p or not p.get("jours_vus"):
        return None
    if p.get("continu"):
        return "continu"
    if p.get("jours_vus", 0) >= 2 and (p.get("part_nuit") or 0) < 0.05:
        return "heures de jour"
    return "intermittent"


def traits(fiche, p):
    """Valeurs catégorielles d'un client, comparées à la population pour mesurer la singularité."""
    v = p.get("volumes") or {} if p else {}
    return {
        "fabricant": plier(fiche.get("manufacturer")) or None,
        "système": _fam(SYSTEME, fiche.get("os")),
        "famille de nom": _fam(NOM, fiche.get("name")),
        "MAC aléatoire": "oui" if mac_aleatoire(fiche.get("mac")) else "non",
        "comportement": comportement(p),
        "raccordement": ("filaire" if p and p.get("filaire") and not p.get("wifi") else "Wi-Fi" if p and p.get("wifi") else None),
        "mobilité": ("3 bornes ou plus" if p and len(p.get("bornes") or []) >= 3 else "2 bornes" if p and len(p.get("bornes") or []) == 2 else None),
        "volumes": ("très réguliers" if v.get("regularite_cv") is not None and v.get("mesures", 0) >= 6 and v["regularite_cv"] < 0.3
                    else "par rafales" if v.get("regularite_cv") is not None and v["regularite_cv"] > 1 else None),
        "SSID": ",".join(p.get("ssids") or []) or None if p else None,
        "VLAN": ",".join(p.get("vlans") or []) or None if p else None,
    }


def population(liste_traits):
    """[traits] -> {attribut: {valeur: part}} (parts sur les clients qui ont une valeur pour l'attribut) + « _n »."""
    out = {}
    liste_traits = list(liste_traits)
    for t in liste_traits:
        for k, v in t.items():
            if v is not None:
                out.setdefault(k, {}).setdefault(v, 0)
                out[k][v] += 1
    pop = {k: {v: n / sum(d.values()) for v, n in d.items()} for k, d in out.items()}
    pop["_n"] = len(liste_traits)
    return pop


POPULATION_MIN = 20     # en dessous, la singularité ne veut rien dire : poids neutres


def _rarete(pop, attr, val):
    """0 (tout le site partage cette valeur) .. 1 (unique) ; inconnu = 0,5."""
    if (pop or {}).get("_n", 0) < POPULATION_MIN:
        return 0.5
    part = ((pop or {}).get(attr) or {}).get(val)
    return 0.5 if part is None else 1.0 - part


NIVEAUX = (("confirmée", "confirmée par une personne"), ("forte", "certitude forte (≥ 70 %)"), ("moyenne", "certitude moyenne (40 à 69 %)"),
           ("faible", "certitude faible (< 40 %)"), ("aucune", "aucune catégorie proposée"))
APPRIS_MAX = 40          # contribution maximale de l'apprentissage à une catégorie (les autres indices gardent la parole)
APPRIS_SUPPORT = 3       # confirmations pour qu'un trait appris pèse de tout son poids


def niveau(r):
    if r.get("decision"):
        return "confirmée"
    if not r.get("categorie"):
        return "aucune"
    c = r.get("confiance") or 0
    return "forte" if c >= 70 else "moyenne" if c >= 40 else "faible"


def apprentissage(decisions):
    """#1004 : décisions humaines [{categorie, proposee, traits}] -> {(attribut, valeur): {"pos": {cat: n}, "neg": {cat: n}}}.
    Une confirmation renforce, pour chacun des traits du client, la catégorie choisie ; une correction affaiblit aussi la
    catégorie qui avait été proposée à tort. Les autres clients qui partagent ces traits en héritent (certitudes modifiées)."""
    st = {}
    for d in decisions or []:
        for k, v in (d.get("traits") or {}).items():
            if v is None or k in ("SSID",):
                continue
            e = st.setdefault((k, v), {"pos": {}, "neg": {}})
            e["pos"][d["categorie"]] = e["pos"].get(d["categorie"], 0) + 1
            if d.get("proposee") and d["proposee"] != d["categorie"]:
                e["neg"][d["proposee"]] = e["neg"].get(d["proposee"], 0) + 1
    return st


def categoriser(fiche, p=None, pop=None, appris=None, decision=None):
    """fiche (client vu) + profil d'activité + population du site (+ apprentissage, + décision humaine) ->
    {categorie, confiance, niveau, hypotheses, singularites}. Une décision humaine fixe la catégorie (niveau « confirmée »)."""
    t = traits(fiche, p)
    scores = {c: [] for c in CATEGORIES}

    def ajoute(cat, poids, texte, attr=None):
        mult = 0.5 + _rarete(pop, attr, t.get(attr)) if attr and pop else 1.0
        scores[cat].append({"poids": round(poids * mult), "texte": texte + ("" if mult == 1.0 else " (singularité ×%s)" % str(round(mult, 2)).replace(".", ","))})

    for rx, cat, poids in SYSTEME:
        if fiche.get("os") and re.search(rx, plier(fiche["os"])):
            ajoute(cat, poids, "système annoncé « %s »" % fiche["os"], "système"); break
    for rx, cat, poids in NOM:
        if fiche.get("name") and re.search(rx, plier(fiche["name"])):
            ajoute(cat, poids, "nom annoncé « %s »" % fiche["name"], "famille de nom"); break
    fab = plier(fiche.get("manufacturer"))
    if fab and re.search(ADAPTATEURS, fab):
        for c in MACHINES[:1] + POSTES[:1]:
            ajoute(c, 5, "fabricant « %s » : adaptateur réseau (souvent USB), pas la marque de la machine" % fiche["manufacturer"])
    elif fab:
        for rx, cibles in FABRICANT:
            if re.search(rx, fab):
                for cat, poids in cibles:
                    ajoute(cat, poids, "fabricant « %s »" % fiche["manufacturer"], "fabricant")
                break
    if t["MAC aléatoire"] == "oui":
        for cat, poids in (("mobile Android", 15), ("mobile Apple", 15), ("casque VR", 5), ("poste Windows", 5), ("machine Linux / sans écran", -15),
                           ("équipement réseau", -30), ("imprimante", -30), ("caméra / objet connecté", -20)):
            ajoute(cat, poids, "MAC aléatoire (protection de la vie privée des mobiles)" if poids > 0 else "MAC aléatoire : rare pour ce type", "MAC aléatoire")
    comp = t["comportement"]
    if comp == "continu":
        for c in MACHINES:
            ajoute(c, 20, "présent en continu (%s h / jour, week-ends compris)" % str(p.get("heures_par_jour")).replace(".", ","), "comportement")
        for c in MOBILES:
            ajoute(c, -20, "présent en continu : rare pour un mobile", "comportement")
    elif comp == "heures de jour":
        for c in MOBILES + POSTES:
            ajoute(c, 10, "présent aux heures de jour seulement (nuit %d %%)" % round(100 * (p.get("part_nuit") or 0)), "comportement")
        ajoute("machine Linux / sans écran", -10, "absent la nuit : rare pour une machine de service", "comportement")
    if t["mobilité"]:   # #1004 : deux bornes voisines suffisent à un poste fixe en Wi-Fi -- indice faible ; trois et plus : fort
        fort = t["mobilité"] == "3 bornes ou plus"
        for c in MOBILES:
            ajoute(c, 15 if fort else 5, "passe d'une borne à l'autre (%d équipements)" % len(p.get("bornes") or []), "mobilité")
        for c in MACHINES:
            ajoute(c, -15 if fort else -5, "change de borne : %s pour un équipement fixe" % ("rare" if fort else "possible (bornes voisines)"), "mobilité")
    if t["raccordement"] == "filaire":
        for c in MOBILES:
            ajoute(c, -25, "raccordé en filaire", "raccordement")
        ajoute("machine Linux / sans écran", 5, "raccordé en filaire", "raccordement")
    v = (p or {}).get("volumes") or {}
    if t["volumes"] == "très réguliers":
        ajoute("machine Linux / sans écran", 15, "volumes très réguliers d'heure en heure", "volumes")
        ajoute("caméra / objet connecté", 10, "volumes très réguliers d'heure en heure", "volumes")
    elif t["volumes"] == "par rafales":
        for c in MOBILES + POSTES:
            ajoute(c, 8, "volumes par rafales (usage humain)", "volumes")
    if v.get("part_descendant") is not None and v.get("mesures", 0) >= 3 and v["part_descendant"] < 0.3:
        ajoute("caméra / objet connecté", 20, "envoie bien plus qu'il ne reçoit (%d %% reçu)" % round(100 * v["part_descendant"]))

    if appris:   # #1004 : ce que les confirmations humaines ont appris sur des traits que ce client partage
        gains = {}
        for k, val in t.items():
            e = appris.get((k, val)) if val is not None else None
            if not e:
                continue
            npos = sum(e["pos"].values())
            sup = min(1.0, npos / float(APPRIS_SUPPORT))
            for cat, n in e["pos"].items():
                if cat in scores:
                    gains.setdefault(cat, []).append((round(25 * sup * n / npos), "appris : %d confirmation(s) avec %s « %s »" % (n, k, val)))
            for cat, n in e["neg"].items():
                if cat in scores:
                    gains.setdefault(cat, []).append((-round(15 * min(1.0, n / float(APPRIS_SUPPORT))), "appris : %d correction(s) écartant cette catégorie pour %s « %s »" % (n, k, val)))
        for cat, lst in gains.items():
            tot = 0
            for poids, txt in sorted(lst, key=lambda x: -abs(x[0])):
                poids = max(-APPRIS_MAX - tot, min(APPRIS_MAX - tot, poids))
                if poids:
                    scores[cat].append({"poids": poids, "texte": txt}); tot += poids

    hyp = []
    for c, pr in scores.items():
        s = max(0, min(100, sum(x["poids"] for x in pr)))
        if pr and s > 0:
            hyp.append({"categorie": c, "score": s, "preuves": sorted(pr, key=lambda x: -abs(x["poids"]))})
    hyp.sort(key=lambda h: -h["score"])
    if not hyp:
        cat, conf = None, 0
    else:
        top = hyp[0]["score"]
        second = hyp[1]["score"] if len(hyp) > 1 else 0
        conf = round(min(95, top) * (1 - 0.5 * second / top))
        cat = hyp[0]["categorie"]
    sing = []
    for k, val in t.items():
        if val is None or not pop or pop.get("_n", 0) < POPULATION_MIN:
            continue
        part = (pop.get(k) or {}).get(val)
        if part is not None and part <= 0.1:
            montre = fiche.get("manufacturer") if k == "fabricant" else val
            pc = ("%.1f" % (100 * part)).rstrip("0").rstrip(".").replace(".", ",")
            sing.append({"attribut": k, "valeur": val, "part": round(part, 3),
                         "texte": "%s « %s » : %s" % (k, montre, "seul client du site dans ce cas" if part <= 0.002 else "%s %% des clients du site" % pc)})
    r = {"categorie": cat, "confiance": conf, "incertain": bool(hyp) and conf < 40, "hypotheses": hyp[:4], "singularites": sing, "traits": t,
         "proposee": cat, "decision": None}
    if decision and decision.get("categorie"):
        r.update(categorie=decision["categorie"], confiance=100, incertain=False,
                 decision={k: decision.get(k) for k in ("categorie", "par", "at", "proposee")})
    r["niveau"] = niveau(r)
    return r


def compatible(type_element, cat):
    """Type d'élément d'une liste x catégorie proposée -> True / False / None (rien à dire)."""
    if not type_element or not cat or type_element not in COMPATIBLES:
        return None
    return cat in COMPATIBLES[type_element]
