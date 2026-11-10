# -*- coding: utf-8 -*-
"""Liste de surveillance et concordance des cibles (livraison #1001) -- logique PURE + stockage SQLite, testée
(tests/test_surveillance.py).

Principe (BACKLOG 2026-11-10) : une cible s'identifie sur CHACUN des éléments qui la caractérisent ou la singularisent
(MAC déclarée ou apprise, préfixe constructeur, nom annoncé, fabricant, système, raccordement) ; chacun apporte sa part
d'indice, avec sa preuve. Les DISCORDANCES ne sont pas écartées : quand la MAC concorde mais que le fabricant ou le
système contredisent l'élément, c'est soit un changement à apprendre (carte remplacée), soit une usurpation possible
(MAC clonée) -- statut « discordant », alerte avec preuves. Une décision (confirmer / rejeter / attribuer) APPREND :
la MAC confirmée devient une MAC connue de l'élément (une MAC aléatoire Android reste stable pour un même réseau Wi-Fi).

Les listes déposées (ex. tablettes d'un client : n° de série, MAC) vivent dans la base du hub, jamais dans le dépôt."""
import json
import re
import time
import unicodedata

SCHEMA = """
CREATE TABLE IF NOT EXISTS nebula_surv_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT, liste TEXT NOT NULL, libelle TEXT, type TEXT, modele TEXT, reference TEXT,
    serie TEXT, mac TEXT, fabricant TEXT, notes TEXT, macs_apprises TEXT, cree_at INTEGER NOT NULL, cree_par TEXT);
CREATE INDEX IF NOT EXISTS idx_nse_liste ON nebula_surv_elements(liste);
CREATE TABLE IF NOT EXISTS nebula_surv_reperes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, liste TEXT NOT NULL, element_id INTEGER NOT NULL, site_id TEXT NOT NULL,
    mac TEXT NOT NULL, premier INTEGER NOT NULL, dernier INTEGER NOT NULL, score INTEGER NOT NULL, statut TEXT NOT NULL,
    preuves TEXT, discordances TEXT, client TEXT, decision TEXT, decide_par TEXT, decide_at INTEGER,
    UNIQUE (liste, element_id, site_id, mac));
CREATE INDEX IF NOT EXISTS idx_nsr_dernier ON nebula_surv_reperes(site_id, dernier);
"""

LOT = 0          # element_id d'un repère « du lot » : membre probable de la liste, élément pas encore déterminé
STATUTS = ("reconnu", "probable", "lot", "discordant")
TYPES = {"tablette": "tablette", "tablettes": "tablette", "tab": "tablette", "telephone": "telephone", "smartphone": "telephone",
         "mobile": "telephone", "pc": "poste", "poste": "poste", "ordinateur": "poste", "portable": "poste", "laptop": "poste",
         "imprimante": "imprimante", "camera": "camera", "casque": "casque", "casque vr": "casque", "borne": "borne",
         "ecran": "ecran", "serveur": "serveur", "console": "console"}
SYSTEMES = {"tablette": ("android", "ios", "ipados", "samsung", "apple"), "telephone": ("android", "ios", "samsung", "apple"),
            "casque": ("android",), "poste": ("windows", "linux", "mac", "ubuntu", "debian")}
FAB_REF = (("SM-", "Samsung"), ("GT-", "Samsung"), ("GALAXY", "Samsung"), ("IPAD", "Apple"), ("IPHONE", "Apple"),
           ("MACBOOK", "Apple"), ("TB-", "Lenovo"), ("LENOVO", "Lenovo"), ("QUEST", "Meta"), ("PICO", "Pico"))
ENTETES = {"mac", "adresse mac", "serie", "n serie", "no serie", "numero de serie", "s/n", "sn", "modele", "type", "nom",
           "libelle", "reference", "ref", "designation", "fabricant", "marque"}

RE_MAC = re.compile(r"^(?:[0-9a-f]{2}[:\-.]?){5}[0-9a-f]{2}$", re.I)
RE_REF = re.compile(r"^[A-Z]{1,5}-[A-Z0-9]{2,}[A-Z0-9-]*$")
RE_SERIE = re.compile(r"^[A-Z0-9]{8,20}$")


def plier(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def compact(s):
    return re.sub(r"[^0-9a-z]", "", plier(s))


def mots(s):
    """« Galaxy-Tab-A11+ » -> « galaxy tab a11 » (séparateurs uniformisés pour chercher une suite de mots)."""
    return re.sub(r"[^0-9a-z]+", " ", plier(s)).strip()


def mac_norm(s):
    h = re.sub(r"[^0-9a-f]", "", str(s or "").lower())
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else None


def mac_aleatoire(mac):
    """MAC « administrée localement » (bit 0x02 du premier octet) : MAC aléatoire d'Android / iOS / Windows, ou virtuelle."""
    m = mac_norm(mac)
    return bool(m) and int(m[1], 16) & 2 == 2


def oui(mac):
    m = mac_norm(mac)
    return m[:8] if m else None


def fabricant_de(*textes):
    for t in textes:
        u = str(t or "").upper()
        for pre, fab in FAB_REF:
            if (u.startswith(pre) if pre.endswith("-") else pre in u):
                return fab
    return None


# --------------------------------------------------------------------------------------------- dépôt d'une liste

def _champs(ligne):
    if "\t" in ligne:
        parts = ligne.split("\t")
    elif ";" in ligne:
        parts = ligne.split(";")
    elif ligne.count(",") >= 2:
        parts = ligne.split(",")
    else:
        parts = re.split(r"\s{2,}", ligne)
    return [p.strip().strip('"').strip() for p in parts if p.strip().strip('"').strip()]


def analyser_ligne(ligne):
    """Une ligne collée (tableur, CSV, texte aligné) -> élément ; chaque champ est reconnu à sa forme, pas à sa colonne."""
    el = {"libelle": None, "type": None, "modele": None, "reference": None, "serie": None, "mac": None}
    notes = []
    for p in _champs(ligne):
        if not el["mac"] and RE_MAC.match(p) and mac_norm(p):
            el["mac"] = mac_norm(p)
        elif not el["reference"] and RE_REF.match(p):
            el["reference"] = p
        elif not el["type"] and plier(p) in TYPES:
            el["type"] = TYPES[plier(p)]
        elif (not el["serie"] and RE_SERIE.match(p) and re.search(r"[A-Z]", p) and re.search(r"\d", p)
              and not re.match(r"^[0-9A-F]{12}$", p)):
            el["serie"] = p
        elif not el["libelle"]:
            el["libelle"] = p
        elif not el["modele"]:
            el["modele"] = p
        else:
            notes.append(p)
    el["notes"] = " ; ".join(notes) or None
    el["fabricant"] = fabricant_de(el["reference"], el["modele"], el["libelle"])
    return el


def analyser_texte(texte):
    """-> {elements, ignorees: [{ligne, texte, raison}]} ; une ligne d'en-tête ou sans identifiant est écartée, avec la raison."""
    elements, ignorees = [], []
    for n, ligne in enumerate(str(texte or "").splitlines(), 1):
        if not ligne.strip():
            continue
        champs = [plier(c).replace("°", "").strip(" .:") for c in _champs(ligne)]
        if sum(1 for c in champs if c in ENTETES) >= 2:
            ignorees.append({"ligne": n, "texte": ligne.strip()[:200], "raison": "ligne d'en-tête"})
            continue
        el = analyser_ligne(ligne)
        if not (el["mac"] or el["serie"] or (el["libelle"] and (el["reference"] or el["modele"] or el["type"]))):
            ignorees.append({"ligne": n, "texte": ligne.strip()[:200], "raison": "aucun identifiant reconnu (MAC, n° de série, ou nom + modèle)"})
            continue
        elements.append(dict(el, ligne=n))
    return {"elements": elements, "ignorees": ignorees}


def ouvrir(conn):
    conn.executescript(SCHEMA)


def _dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _cle(el):
    return ("mac", el.get("mac")) if el.get("mac") else ("serie", el.get("serie")) if el.get("serie") else ("libelle", compact(el.get("libelle")))


CHAMPS = ("libelle", "type", "modele", "reference", "serie", "mac", "fabricant", "notes")


def enregistrer(conn, liste, elements_, par=None, now=None):
    """Ajoute ou met à jour (même MAC, sinon même n° de série, sinon même libellé dans la liste) -> {ajoutes, maj}."""
    ouvrir(conn)
    liste = str(liste or "").strip()[:80]
    if not liste:
        raise ValueError("nom de liste manquant")
    now = int(now or time.time())
    existants = {_cle(e): e["id"] for e in elements(conn, liste)}
    aj = maj = 0
    for el in elements_:
        el = {k: (str(el.get(k)).strip()[:200] if el.get(k) not in (None, "") else None) for k in CHAMPS}
        el["mac"] = mac_norm(el["mac"]) if el["mac"] else None
        eid = existants.get(_cle(el))
        if eid:
            conn.execute("UPDATE nebula_surv_elements SET %s WHERE id = ?" % ", ".join("%s = COALESCE(?, %s)" % (k, k) for k in CHAMPS),
                         [el[k] for k in CHAMPS] + [eid])
            maj += 1
        else:
            cur = conn.execute("INSERT INTO nebula_surv_elements (liste, %s, macs_apprises, cree_at, cree_par) VALUES (?, %s, '[]', ?, ?)"
                               % (", ".join(CHAMPS), ", ".join("?" * len(CHAMPS))), [liste] + [el[k] for k in CHAMPS] + [now, par])
            existants[_cle(el)] = cur.lastrowid
            aj += 1
    conn.commit()
    return {"ajoutes": aj, "maj": maj}


def elements(conn, liste=None):
    ouvrir(conn)
    q = "SELECT * FROM nebula_surv_elements" + (" WHERE liste = ?" if liste else "") + " ORDER BY liste, libelle, id"
    out = _dicts(conn.execute(q, (liste,) if liste else ()))
    for e in out:
        try:
            e["macs_apprises"] = json.loads(e.get("macs_apprises") or "[]")
        except ValueError:
            e["macs_apprises"] = []
    return out


def listes(conn):
    ouvrir(conn)
    return _dicts(conn.execute("SELECT liste, COUNT(*) AS elements FROM nebula_surv_elements GROUP BY liste ORDER BY liste"))


def supprimer_element(conn, eid):
    ouvrir(conn)
    n = conn.execute("DELETE FROM nebula_surv_elements WHERE id = ?", (int(eid),)).rowcount
    conn.execute("DELETE FROM nebula_surv_reperes WHERE element_id = ?", (int(eid),))
    conn.commit()
    return n


def supprimer_liste(conn, liste):
    ouvrir(conn)
    n = conn.execute("DELETE FROM nebula_surv_elements WHERE liste = ?", (liste,)).rowcount
    conn.execute("DELETE FROM nebula_surv_reperes WHERE liste = ?", (liste,))
    conn.commit()
    return n


# ---------------------------------------------------------------------------------------------------- concordance

def contexte(conn, site_id):
    """Préfixe constructeur -> fabricant le plus annoncé sur le site (MAC non aléatoires) : déduit le fabricant attendu
    d'un élément dont la liste ne donne que la MAC."""
    par = {}
    try:
        for mac, fab in conn.execute("SELECT mac, manufacturer FROM nebula_client_seen WHERE site_id = ? AND manufacturer IS NOT NULL", (site_id,)):
            if not mac_aleatoire(mac):
                par.setdefault(oui(mac), {}).setdefault(fab, 0)
                par[oui(mac)][fab] += 1
    except Exception:  # noqa: BLE001 -- historique absent : pas de déduction
        pass
    return {"oui": {o: max(d, key=d.get) for o, d in par.items()}}


def _preuve(element, poids, texte):
    return {"element": element, "poids": poids, "texte": texte}


def concorder(el, cl, ctx=None):
    """Élément de liste x client vu -> {score 0-100, statut|None, par_mac, preuves, discordances}.
    Chaque élément concordant ajoute son poids ; un élément contredit retire du score, ou -- si la MAC concorde --
    devient une DISCORDANCE (forte : fabricant, système ; faible : nom)."""
    ctx = ctx or {}
    P, D = [], []
    cmac = mac_norm(cl.get("mac"))
    declaree = mac_norm(el.get("mac"))
    connues = ({declaree} | set(el.get("macs_apprises") or [])) - {None}
    par_mac = bool(cmac) and cmac in connues
    if par_mac:
        P.append(_preuve("MAC", 60, "MAC %s %s" % (cmac, "déclarée dans la liste" if cmac == declaree else "apprise (repère confirmé)")))
    elif cmac and mac_aleatoire(cmac):
        P.append(_preuve("MAC", 0, "MAC aléatoire %s : reconnaissance par les autres éléments" % cmac))
    elif declaree and cmac and oui(cmac) == oui(declaree):
        P.append(_preuve("préfixe", 8, "même préfixe constructeur %s que la MAC déclarée" % oui(cmac)))
    nom_c, nom_m = compact(cl.get("name")), " %s " % mots(cl.get("name"))
    n_nom = 0
    if nom_c:
        if el.get("serie") and compact(el["serie"]) in nom_c:
            P.append(_preuve("nom", 40, "n° de série %s dans le nom annoncé « %s »" % (el["serie"], cl.get("name")))); n_nom += 1
        lib = compact(el.get("libelle"))
        if len(lib) >= 3 and lib in nom_c:
            P.append(_preuve("nom", 30, "libellé « %s » dans le nom annoncé « %s »" % (el["libelle"], cl.get("name")))); n_nom += 1
        ref = compact(el.get("reference"))
        if len(ref) >= 4 and ref in nom_c:
            P.append(_preuve("nom", 20, "référence %s dans le nom annoncé « %s »" % (el["reference"], cl.get("name")))); n_nom += 1
        mod = mots(el.get("modele"))
        if len(mod) >= 3 and " %s " % mod in nom_m:
            P.append(_preuve("nom", 15, "modèle « %s » dans le nom annoncé « %s »" % (el["modele"], cl.get("name")))); n_nom += 1
        if par_mac and not n_nom and (el.get("libelle") or el.get("serie") or el.get("modele")):
            D.append({"force": "faible", "texte": "nom annoncé « %s » sans lien avec l'élément (renommage, ou autre appareil ?)" % cl.get("name")})
    attendu = el.get("fabricant") or (ctx.get("oui") or {}).get(oui(declaree))
    fab = cl.get("manufacturer")
    if attendu and fab:
        a, f = compact(attendu)[:5], compact(fab)[:5]
        if a and f and (a in compact(fab) or f in compact(attendu)):
            P.append(_preuve("fabricant", 15, "fabricant annoncé « %s » (attendu %s)" % (fab, attendu)))
        elif par_mac:
            D.append({"force": "forte", "texte": "fabricant annoncé « %s », attendu « %s » : MAC clonée, ou carte réseau remplacée ?" % (fab, attendu)})
        else:
            P.append(_preuve("fabricant", -15, "fabricant annoncé « %s », attendu %s" % (fab, attendu)))
    sys_c, typ = plier(cl.get("os")), el.get("type")
    if sys_c and typ in SYSTEMES:
        if any(s in sys_c for s in SYSTEMES[typ]):
            P.append(_preuve("système", 10, "système « %s » cohérent avec : %s" % (cl.get("os"), typ)))
        elif par_mac:
            D.append({"force": "forte", "texte": "système « %s » inattendu pour : %s" % (cl.get("os"), typ)})
        else:
            P.append(_preuve("système", -10, "système « %s » inattendu pour : %s" % (cl.get("os"), typ)))
    score = max(0, min(100, sum(p["poids"] for p in P)))
    fortes = [d for d in D if d["force"] == "forte"]
    statut = ("discordant" if par_mac and fortes else "reconnu" if score >= 60 else "probable" if score >= 35 else None)
    return {"score": score, "statut": statut, "par_mac": par_mac, "preuves": P, "discordances": D}


def traits_lot(els):
    """Ce que TOUS les éléments d'une liste partagent (fabricant, modèle, référence, type) -> pseudo-élément, ou None."""
    if len(els) < 2:
        return None
    t = {}
    for k in ("fabricant", "modele", "reference", "type"):
        vals = {compact(e.get(k)) for e in els}
        if len(vals) == 1 and next(iter(vals)):
            t[k] = els[0].get(k)
    return t if (t.get("modele") or t.get("reference")) else None


def concorder_lot(traits, cl, ctx=None):
    """Membre probable d'une liste homogène (17 tablettes identiques) : le nom annoncé doit porter le modèle ou la référence."""
    r = concorder(dict(traits), cl, ctx)
    nom = any(p["element"] == "nom" for p in r["preuves"])
    r["statut"] = "lot" if nom and r["score"] >= 25 else None
    return r


def _client_resume(cl):
    return {k: cl.get(k) for k in ("name", "ip", "manufacturer", "os", "device", "port", "ssid", "vlan", "last_seen") if cl.get(k) not in (None, "")}


def _noter(conn, liste, eid, site_id, cl, r, now):
    """Insère ou met à jour un repère ; -> 'nouveau' | 'discordance' (devenu discordant) | None. Une décision n'est jamais écrasée."""
    mac = mac_norm(cl.get("mac"))
    seen = int(cl.get("last_seen") or now)
    row = conn.execute("SELECT id, statut, decision FROM nebula_surv_reperes WHERE liste = ? AND element_id = ? AND site_id = ? AND mac = ?",
                       (liste, eid, site_id, mac)).fetchone()
    vals = (r["score"], r["statut"], json.dumps(r["preuves"], ensure_ascii=False), json.dumps(r["discordances"], ensure_ascii=False),
            json.dumps(_client_resume(cl), ensure_ascii=False))
    if row is None:
        conn.execute("INSERT INTO nebula_surv_reperes (liste, element_id, site_id, mac, premier, dernier, score, statut, preuves, discordances, client) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (liste, eid, site_id, mac, seen, seen) + vals)
        return "nouveau"
    conn.execute("UPDATE nebula_surv_reperes SET dernier = MAX(dernier, ?), score = ?, statut = ?, preuves = ?, discordances = ?, client = ? WHERE id = ?",
                 (seen,) + vals + (row[0],))
    return "discordance" if r["statut"] == "discordant" and row[1] != "discordant" and row[2] != "rejete" else None


def rapprocher(conn, site_id, depuis, now=None):
    """Clients du site vus depuis `depuis` x éléments des listes -> [{type: nouveau|discordance, liste, element, mac, statut, score}].
    Par liste, le meilleur élément gagne ; une égalité sans MAC concordante (lot homogène) devient un repère « du lot »."""
    ouvrir(conn)
    now = int(now or time.time())
    els = elements(conn)
    if not els:
        return []
    ctx = contexte(conn, site_id)
    rejets = {(r[0], r[1], r[2]) for r in conn.execute(
        "SELECT liste, element_id, mac FROM nebula_surv_reperes WHERE site_id = ? AND decision = 'rejete'", (site_id,))}
    par_liste = {}
    for e in els:
        par_liste.setdefault(e["liste"], []).append(e)
    lots = {li: traits_lot(es) for li, es in par_liste.items()}
    try:
        clients = _dicts(conn.execute("SELECT mac, ip, name, manufacturer, os, device, port, ssid, vlan, last_seen FROM nebula_client_seen "
                                      "WHERE site_id = ? AND last_seen >= ?", (site_id, int(depuis))))
    except Exception:  # noqa: BLE001 -- pas encore d'historique des clients
        clients = []
    evts = []
    for cl in clients:
        mac = mac_norm(cl.get("mac"))
        if not mac:
            continue
        for li, es in par_liste.items():
            res = [(e, concorder(e, cl, ctx)) for e in es if (li, e["id"], mac) not in rejets]
            res = [(e, r) for e, r in res if r["statut"]]
            choix = None
            if res:
                top = max(r["score"] + (100 if r["par_mac"] else 0) for _e, r in res)
                ex = [(e, r) for e, r in res if r["score"] + (100 if r["par_mac"] else 0) == top]
                if len(ex) == 1:
                    choix = (ex[0][0]["id"], ex[0][0].get("libelle") or ex[0][0].get("serie") or ex[0][0].get("mac"), ex[0][1])
                else:
                    r = dict(ex[0][1], statut="lot")
                    r["preuves"] = r["preuves"] + [_preuve("lot", 0, "%d éléments de la liste concordent autant : à attribuer" % len(ex))]
                    choix = None if (li, LOT, mac) in rejets else (LOT, None, r)
            elif lots.get(li) and (li, LOT, mac) not in rejets:
                r = concorder_lot(lots[li], cl, ctx)
                if r["statut"]:
                    choix = (LOT, None, r)
            if choix:
                quoi = _noter(conn, li, choix[0], site_id, cl, choix[2], now)
                if quoi:
                    evts.append({"type": quoi, "liste": li, "element_id": choix[0], "element": choix[1], "mac": mac,
                                 "nom": cl.get("name"), "statut": choix[2]["statut"], "score": choix[2]["score"],
                                 "borne": cl.get("device"), "discordances": [d["texte"] for d in choix[2]["discordances"]]})
    conn.commit()
    return evts


def reperes(conn, site_id=None, liste=None, depuis=0):
    ouvrir(conn)
    q = ("SELECT r.*, e.libelle, e.serie, e.modele FROM nebula_surv_reperes r LEFT JOIN nebula_surv_elements e ON e.id = r.element_id "
         "WHERE r.dernier >= ?")
    args = [int(depuis)]
    if site_id:
        q += " AND r.site_id = ?"; args.append(site_id)
    if liste:
        q += " AND r.liste = ?"; args.append(liste)
    out = _dicts(conn.execute(q + " ORDER BY r.dernier DESC LIMIT 2000", args))
    for r in out:
        for k in ("preuves", "discordances", "client"):
            try:
                r[k] = json.loads(r.get(k) or ("{}" if k == "client" else "[]"))
            except ValueError:
                r[k] = {} if k == "client" else []
    return out


def decider(conn, rid, decision, element_id=None, par=None, now=None):
    """confirme (la MAC devient connue de l'élément -- apprentissage) | rejete (plus jamais proposé) | annule.
    Un repère « du lot » se confirme en l'ATTRIBUANT à un élément (element_id)."""
    ouvrir(conn)
    if decision not in ("confirme", "rejete", "annule"):
        raise ValueError("décision inconnue : confirme, rejete ou annule")
    row = conn.execute("SELECT id, liste, element_id, site_id, mac FROM nebula_surv_reperes WHERE id = ?", (int(rid),)).fetchone()
    if row is None:
        raise LookupError("repère introuvable")
    rid, liste, eid, site_id, mac = row
    now = int(now or time.time())
    if decision == "annule" and eid != LOT:   # défaire une confirmation : la MAC apprise est oubliée
        e = conn.execute("SELECT macs_apprises FROM nebula_surv_elements WHERE id = ?", (eid,)).fetchone()
        if e is not None:
            try:
                appr = [m for m in json.loads(e[0] or "[]") if m != mac]
            except ValueError:
                appr = []
            conn.execute("UPDATE nebula_surv_elements SET macs_apprises = ? WHERE id = ?", (json.dumps(appr), eid))
    if decision == "confirme":
        cible = int(element_id) if element_id not in (None, "") else eid
        if cible == LOT:
            raise ValueError("un repère du lot se confirme en choisissant l'élément (element_id)")
        e = conn.execute("SELECT macs_apprises, liste FROM nebula_surv_elements WHERE id = ?", (cible,)).fetchone()
        if e is None or e[1] != liste:
            raise LookupError("élément introuvable dans la liste %s" % liste)
        if cible != eid:
            conn.execute("DELETE FROM nebula_surv_reperes WHERE liste = ? AND element_id = ? AND site_id = ? AND mac = ? AND id != ?",
                         (liste, cible, site_id, mac, rid))
            conn.execute("UPDATE nebula_surv_reperes SET element_id = ? WHERE id = ?", (cible, rid))
        try:
            appr = json.loads(e[0] or "[]")
        except ValueError:
            appr = []
        if mac not in appr:
            appr.append(mac)
        conn.execute("UPDATE nebula_surv_elements SET macs_apprises = ? WHERE id = ?", (json.dumps(appr[-20:]), cible))
    conn.execute("UPDATE nebula_surv_reperes SET decision = ?, decide_par = ?, decide_at = ? WHERE id = ?",
                 (None if decision == "annule" else decision, par, now, rid))
    conn.commit()
    return {"id": rid, "decision": None if decision == "annule" else decision}
