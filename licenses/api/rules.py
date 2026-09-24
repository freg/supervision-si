# -*- coding: utf-8 -*-
"""Gestionnaire de licences (livraison #595) -- logique PURE :

- correspondance logiciel du catalogue <-> logiciel installé (motifs) ;
- écarts : installé sans contrat, contrat dépassé (attributions ou
  installations > quantité), contrat non utilisé, échéances, attribué mais
  non installé, installé mais non attribué ;
- import des tableurs d'inventaire (matrice logiciel × personne, export
  Microsoft 365, comparatif licence × initiales) ;
- grille poste / utilisateur × logiciel.
Rien ici ne touche la base ni le réseau."""
import datetime as _dt
import re
import unicodedata

KINDS = ("per-user", "per-device", "subscription", "perpetual", "site", "free")


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def matches(software, installed_name, publisher=""):
    """Le logiciel du catalogue correspond-il au nom installé ? `software["patterns"]`
    = motifs (début de mot ou sous-chaîne, insensibles aux accents / casse) ;
    sans motif, le nom du logiciel lui-même."""
    name = fold(installed_name)
    pats = [fold(p) for p in (software.get("patterns") or []) if p and str(p).strip()] or [fold(software.get("name"))]
    for p in pats:
        if not p:
            continue
        if p.startswith("re:"):
            try:
                if re.search(p[3:], name):
                    return True
            except re.error:
                continue
        elif p in name:
            return True
    pub = fold(software.get("vendor"))
    return bool(pub and publisher and pub == fold(publisher) and fold(software.get("name")) in name)


def match_installations(catalog, inventories):
    """-> {software_id: [{"host", "agent_id", "site", "name", "version", "publisher", "users"}]}
    et la liste des installations sans logiciel du catalogue (nom, hôtes)."""
    found = {s["id"]: [] for s in catalog}
    unknown = {}
    for inv in inventories or []:
        for it in inv.get("installed") or []:
            hit = False
            for s in catalog:
                if matches(s, it.get("name"), it.get("publisher")):
                    found[s["id"]].append({"host": inv.get("hostname"), "agent_id": inv.get("agent_id"), "site": inv.get("site"), "name": it.get("name"),
                                           "version": it.get("version"), "publisher": it.get("publisher"), "installed_at": it.get("installed_at"), "users": inv.get("users") or []})
                    hit = True
            if not hit and it.get("publisher") and not _system_noise(it):
                unknown.setdefault(it["name"], {"name": it["name"], "publisher": it.get("publisher"), "hosts": set()})["hosts"].add(inv.get("hostname"))
    for u in unknown.values():
        u["hosts"] = sorted(h for h in u["hosts"] if h)
    return found, sorted(unknown.values(), key=lambda u: (-len(u["hosts"]), fold(u["name"])))


NOISE_PUBLISHERS = ("microsoft corporation", "debian", "ubuntu", "fedora project", "canonical", "homebrew", "apple", "intel", "nvidia", "realtek", "amd", "lenovo", "dell", "hp")
NOISE_NAMES = ("update", "redistributable", "runtime", "driver", "pilote", "lib", "kb", "security", "hotfix")


def _system_noise(it):
    pub, name = fold(it.get("publisher")), fold(it.get("name"))
    if it.get("source") in ("dpkg", "rpm"):
        return True  # paquets système : seuls les motifs du catalogue les font ressortir
    return pub in NOISE_PUBLISHERS and any(n in name for n in NOISE_NAMES)


def days_until(date_str, today=None):
    try:
        d = _dt.date.fromisoformat(str(date_str)[:10])
    except (TypeError, ValueError):
        return None
    return (d - (today or _dt.date.today())).days


def gaps(catalog, contracts, assignments, found, today=None, expiring_days=60):
    """Écarts par contrat et par logiciel -> liste de {kind, severity, software, contract, text, detail}."""
    out = []
    by_sw_contracts = {}
    for c in contracts:
        by_sw_contracts.setdefault(c["software_id"], []).append(c)
    for s in catalog:
        insts = found.get(s["id"], [])
        hosts = sorted({i["host"] for i in insts if i.get("host")})
        cs = by_sw_contracts.get(s["id"], [])
        active = [c for c in cs if c.get("kind") != "free" and (days_until(c.get("end"), today) is None or days_until(c.get("end"), today) >= 0)]
        if hosts and not cs:
            out.append({"kind": "installed-no-contract", "severity": "warning", "software": s["name"], "software_id": s["id"], "contract": None,
                        "text": "%s installé sur %d poste(s) sans contrat déclaré" % (s["name"], len(hosts)), "detail": hosts})
        for c in cs:
            asg = [a for a in assignments if a["contract_id"] == c["id"]]
            qty = c.get("quantity") or 0
            d = days_until(c.get("end"), today)
            if d is not None and d < 0:
                out.append({"kind": "expired", "severity": "critical", "software": s["name"], "software_id": s["id"], "contract": c["id"],
                            "text": "%s : contrat « %s » expiré depuis %d jour(s)" % (s["name"], c.get("label") or c["id"], -d), "detail": {"end": c.get("end")}})
            elif d is not None and d <= expiring_days:
                out.append({"kind": "expiring", "severity": "warning", "software": s["name"], "software_id": s["id"], "contract": c["id"],
                            "text": "%s : contrat « %s » expire dans %d jour(s)" % (s["name"], c.get("label") or c["id"], d), "detail": {"end": c.get("end")}})
            if qty and c.get("kind") in ("per-user", "subscription") and len(asg) > qty:
                out.append({"kind": "over-assigned", "severity": "critical", "software": s["name"], "software_id": s["id"], "contract": c["id"],
                            "text": "%s : %d attribution(s) pour %d licence(s)" % (s["name"], len(asg), qty), "detail": [a["subject"] for a in asg]})
            if qty and c.get("kind") == "per-device" and len(hosts) > qty:
                out.append({"kind": "over-installed", "severity": "critical", "software": s["name"], "software_id": s["id"], "contract": c["id"],
                            "text": "%s : installé sur %d poste(s) pour %d licence(s) par poste" % (s["name"], len(hosts), qty), "detail": hosts})
            if qty and c.get("kind") in ("per-user", "subscription", "per-device") and not asg and not hosts and (d is None or d >= 0):
                out.append({"kind": "unused", "severity": "info", "software": s["name"], "software_id": s["id"], "contract": c["id"],
                            "text": "%s : %d licence(s) payée(s), aucune attribution ni installation" % (s["name"], qty), "detail": None})
            if qty and c.get("kind") in ("per-user", "subscription") and asg and len(asg) < qty:
                out.append({"kind": "spare", "severity": "info", "software": s["name"], "software_id": s["id"], "contract": c["id"],
                            "text": "%s : %d licence(s) disponible(s) sur %d" % (s["name"], qty - len(asg), qty), "detail": None})
        # attribué à un poste mais non installé / installé sur un poste non attribué (par poste seulement)
        assigned_hosts = {fold(a["subject"]) for c in cs for a in assignments if a["contract_id"] == c["id"] and a.get("subject_kind") == "host"}
        if assigned_hosts:
            missing = sorted(h for h in assigned_hosts if h not in {fold(x) for x in hosts})
            extra = sorted(h for h in hosts if fold(h) not in assigned_hosts)
            if missing:
                out.append({"kind": "assigned-not-installed", "severity": "info", "software": s["name"], "software_id": s["id"], "contract": None,
                            "text": "%s : attribué à %d poste(s) où il n'est pas installé" % (s["name"], len(missing)), "detail": missing})
            if extra:
                out.append({"kind": "installed-not-assigned", "severity": "warning", "software": s["name"], "software_id": s["id"], "contract": None,
                            "text": "%s : installé sur %d poste(s) non attribué(s)" % (s["name"], len(extra)), "detail": extra})
    sev = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda g: (sev[g["severity"]], g["software"]))
    return out


# -- import des tableurs ------------------------------------------------------------
YES = ("n", "o", "x", "oui", "yes", "1", "true", "✓")


NO = ("", "non", "no", "n/a", "0", "false", "-", "—", "x?")


def _people_from_cell(v):
    """Colonne « personnes / utilisateurs » : noms séparés par , ; / ou retour à la ligne."""
    return [p.strip() for p in re.split(r"[,;/\n]", str(v or "")) if p.strip()]


def import_matrix(rows):
    """Tableau « Logiciel | Éditeur | Licence | Date Fin | personne1 | … » (une
    ligne par logiciel, une marque par personne : croix, « n », « oui », 1,
    date… -- toute cellule non vide hors « non / 0 / - » compte). Les noms
    des personnes viennent de la ligne d'en-tête, ou de la ligne juste
    au-dessus quand la cellule d'en-tête est vide (en-têtes fusionnés). Une
    colonne « Personnes » / « Utilisateurs » listant des noms est aussi
    acceptée. -> [{software, vendor, kind_label, end, people:[...]}]."""
    rows = [list(r) for r in rows or []]
    hdr_i = next((i for i, r in enumerate(rows) if r and fold(r[0]).startswith("logiciel")), None)
    if hdr_i is None:
        return [], "en-tête « Logiciel » introuvable"
    hdr = [fold(h) for h in rows[hdr_i]]
    above = rows[hdr_i - 1] if hdr_i > 0 else []
    fixed, list_col = {"logiciel": 0}, None
    for i, h in enumerate(hdr):
        if h.startswith("editeur"):
            fixed["editeur"] = i
        elif h.startswith("licence") or h.startswith("type"):
            fixed["licence"] = i
        elif h.startswith("date") or h.startswith("fin") or h.startswith("echeance"):
            fixed["date"] = i
        elif h.startswith(("personne", "utilisateur", "affect", "attribu", "user")) and list_col is None:
            list_col = i
    def name_of(i):
        v = rows[hdr_i][i] if i < len(rows[hdr_i]) else None
        if v in (None, "") and i < len(above):
            v = above[i]
        return str(v).strip() if v not in (None, "") else ""
    people_cols = [(i, name_of(i)) for i in range(max(len(hdr), len(above))) if i not in fixed.values() and i != list_col and name_of(i)]
    out = []
    for r in rows[hdr_i + 1:]:
        if not r or r[0] in (None, ""):
            continue
        people = [p for i, p in people_cols if i < len(r) and fold(r[i]) not in NO]
        if list_col is not None:
            people += [p for p in _people_from_cell(_cell(r, list_col)) if p not in people]
        rec = {"software": str(r[0]).strip(), "vendor": _cell(r, fixed.get("editeur")), "kind_label": _cell(r, fixed.get("licence")), "end": _date(_cell(r, fixed.get("date"))), "people": people}
        out.append(rec)
    return out, None


def import_m365(rows):
    """Export du centre d'administration Microsoft 365 (colonnes « Nom
    complet », « Nom d'utilisateur », « Licences ») -> [{user, upn, licenses:[...]}]."""
    rows = [list(r) for r in rows or []]
    hdr_i = next((i for i, r in enumerate(rows) if any(fold(c) in ("licences", "licenses") or fold(c).startswith("nom complet") for c in r if c)), None)
    if hdr_i is None:
        return [], "colonne « Licences » introuvable"
    hdr = [fold(h) for h in rows[hdr_i]]
    col = lambda *names: next((i for i, h in enumerate(hdr) if any(h.startswith(n) for n in names)), None)  # noqa: E731
    c_name, c_upn, c_lic = col("nom complet", "display name"), col("nom d'utilisateur", "user principal", "nom d’utilisateur"), col("licences", "licenses")
    out = []
    for r in rows[hdr_i + 1:]:
        lic = _cell(r, c_lic)
        if not lic and not _cell(r, c_name):
            continue
        out.append({"user": _cell(r, c_name), "upn": _cell(r, c_upn), "licenses": [x.strip() for x in re.split(r"[+;,\n]", lic or "") if x.strip()]})
    return out, None


def import_comparatif(rows):
    """« Licence … » en lignes × initiales en colonnes (croix). -> [{software, people:[initiales]}]."""
    rows = [list(r) for r in rows or []]
    hdr_i = next((i for i, r in enumerate(rows) if r and r[0] in (None, "") and sum(1 for c in r[1:] if c not in (None, "")) >= 2), None)
    if hdr_i is None:
        return [], "ligne des initiales introuvable"
    people = [(i, str(c).strip()) for i, c in enumerate(rows[hdr_i]) if i > 0 and c not in (None, "")]
    out = []
    for r in rows[hdr_i + 1:]:
        if not r or r[0] in (None, ""):
            continue
        out.append({"software": str(r[0]).strip(), "people": [p for i, p in people if i < len(r) and fold(r[i]) not in NO]})
    return out, None


def detect_format(rows):
    rows = [list(r) for r in rows or []]
    for r in rows[:5]:
        if any(fold(c) in ("licences", "licenses") or fold(c).startswith("nom complet") for c in r if c):
            return "m365"
        if r and fold(r[0]).startswith("logiciel"):
            return "matrix"
    return "comparatif"


def _cell(r, i):
    if i is None or i >= len(r) or r[i] is None:
        return ""
    return str(r[i]).strip()


def _date(v):
    if not v:
        return None
    s = str(v)[:10]
    try:
        return _dt.date.fromisoformat(s).isoformat()
    except ValueError:
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", str(v))
        return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else None


# -- grille --------------------------------------------------------------------------
def grid(catalog, contracts, assignments, inventories, users=None):
    """Lignes = sujets (utilisateurs de la table users, attributions, postes des
    inventaires), colonnes = logiciels sous contrat ; case = {assigned, contract_id, installed}."""
    subjects = {}
    for u in users or []:
        subjects.setdefault(("user", u["login"]), {"kind": "user", "subject": u["login"], "site": u.get("site"), "name": u.get("name")})
    for a in assignments:
        subjects.setdefault((a["subject_kind"], a["subject"]), {"kind": a["subject_kind"], "subject": a["subject"], "site": a.get("site")})
    for inv in inventories or []:
        if inv.get("hostname"):
            subjects.setdefault(("host", inv["hostname"]), {"kind": "host", "subject": inv["hostname"], "site": inv.get("site")})
        for u in inv.get("users") or []:
            subjects.setdefault(("user", u), {"kind": "user", "subject": u, "site": inv.get("site")})
    found, _ = match_installations(catalog, inventories)
    installed_hosts = {sid: {fold(i["host"]) for i in insts if i.get("host")} for sid, insts in found.items()}
    contracts_by_sw = {}
    for c in contracts:
        contracts_by_sw.setdefault(c["software_id"], []).append(c)
    cols = [s for s in catalog if contracts_by_sw.get(s["id"])]
    asg_idx = {(a["contract_id"], a["subject_kind"], fold(a["subject"])): a for a in assignments}
    rows = []
    for (kind, subj), meta in sorted(subjects.items(), key=lambda kv: (kv[0][0], fold(kv[0][1]))):
        cells = []
        for s in cols:
            cell = {"software_id": s["id"], "assigned": None, "contract_id": None, "installed": kind == "host" and fold(subj) in installed_hosts.get(s["id"], set())}
            for c in contracts_by_sw[s["id"]]:
                a = asg_idx.get((c["id"], kind, fold(subj)))
                if a:
                    cell.update(assigned=a["id"], contract_id=c["id"])
                    break
            cells.append(cell)
        rows.append(dict(meta, cells=cells))
    return {"columns": [{"id": s["id"], "name": s["name"], "contracts": [{"id": c["id"], "label": c.get("label"), "kind": c.get("kind"), "quantity": c.get("quantity")} for c in contracts_by_sw[s["id"]]]} for s in cols], "rows": rows}


# -- utilisateurs et annuaire (#597) ------------------------------------------------------------
def initials(name):
    parts = [p for p in re.split(r"[\s\-_.]+", fold(name)) if p]
    return "".join(p[0] for p in parts)


def resolve_person(person, users):
    """Rapproche un nom / UPN / identifiant / initiales avec la table des
    utilisateurs (login, name, mail, aliases). -> login ou None."""
    q = fold(person)
    if not q:
        return None
    for u in users:
        if q in (fold(u.get("login")), fold(u.get("mail")), fold(u.get("name"))) or q in [fold(a) for a in (u.get("aliases") or [])]:
            return u["login"]
    # « prenom.nom » ↔ « Prénom Nom », « M. NOM » ↔ nom de famille, initiales
    q_words = [w for w in re.split(r"[\s.\-_@]+", q) if w and w not in ("m", "mme", "mr", "mlle", "dr")]
    if not q_words:
        return None
    for u in users:
        n_words = [w for w in re.split(r"[\s.\-_@]+", fold(u.get("name"))) if w]
        l_words = [w for w in re.split(r"[\s.\-_@]+", fold(u.get("login"))) if w]
        if q_words and (set(q_words) <= set(n_words) or set(q_words) <= set(l_words) or (len(q_words) >= 2 and set(n_words) and set(n_words) <= set(q_words))):
            return u["login"]
    if len(q) <= 3 and q.isalpha():
        hits = [u for u in users if initials(u.get("name")) == q or initials(u.get("login").replace(".", " ")) == q]
        if len(hits) == 1:
            return hits[0]["login"]
    return None


def login_from(person):
    """Identifiant local pour une personne inconnue de l'annuaire : partie
    locale d'une adresse, sinon « prenom.nom » replié."""
    p = str(person or "").strip()
    if "@" in p:
        return fold(p.split("@", 1)[0])
    words = [w for w in re.split(r"[\s.\-_]+", fold(p)) if w and w not in ("m", "mme", "mr", "mlle", "dr")]
    return ".".join(words)[:64]


# -- #598 : analyse croisée utilisateurs ↔ annuaire -------------------------------------------------
def user_gaps(users, assignments, former_groups=("anciens",)):
    """Écarts « type logiciel » sur les personnes : membre d'un groupe
    « anciens » (ne travaille plus avec nous) mais licences attribuées
    (critique), compte disparu de l'annuaire avec attributions (alerte),
    compte désactivé avec attributions (alerte), personne hors annuaire
    (info seulement) avec attributions (info). -> même forme que gaps()."""
    fg = {fold(g) for g in former_groups if g}
    counts = {}
    for a in assignments:
        if a.get("subject_kind") == "user":
            counts[a["subject"]] = counts.get(a["subject"], 0) + 1
    out = []
    for u in users:
        n = counts.get(u["login"], 0)
        groups = [fold(g) for g in (u.get("groups") or [])]
        former = bool(fg & set(groups)) or bool(u.get("fiche_former"))
        if former:
            where = "dans le groupe « %s »" % next((g for g in groups if g in fg), "") if fg & set(groups) else "fiche dans « anciens utilisateurs » (ownCloud)"
            out.append({"kind": "user-former", "severity": "critical" if n else "info", "software": None, "user": u["login"], "contract": None,
                        "text": "%s : %s%s" % (u["login"], where, " mais %d licence(s) attribuée(s) -- à retirer" % n if n else ", aucune licence"), "detail": None})
        if u.get("fiche_former") and u.get("directory") and u.get("enabled") != 0 and not (fg & set(groups)):
            out.append({"kind": "user-former-active", "severity": "warning", "software": None, "user": u["login"], "contract": None,
                        "text": "%s : fiche rangée dans « anciens utilisateurs » mais compte LDAP actif hors groupe anciens -- à vérifier" % u["login"], "detail": None})
        elif u.get("missing") and n:
            out.append({"kind": "user-missing", "severity": "warning", "software": None, "user": u["login"], "contract": None,
                        "text": "%s : absent de l'annuaire depuis la dernière synchronisation, %d licence(s) attribuée(s)" % (u["login"], n), "detail": None})
        elif u.get("directory") and u.get("enabled") == 0 and n:
            out.append({"kind": "user-disabled", "severity": "warning", "software": None, "user": u["login"], "contract": None,
                        "text": "%s : compte désactivé, %d licence(s) attribuée(s)" % (u["login"], n), "detail": None})
        elif not u.get("directory") and n:
            out.append({"kind": "user-unknown", "severity": "info", "software": None, "user": u["login"], "contract": None,
                        "text": "%s : hors annuaire (%s), %d licence(s) attribuée(s)" % (u["login"], u.get("source") or "info", n), "detail": None})
    sev = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda g: (sev[g["severity"]], g["user"]))
    return out


def user_alert(u, former_groups=("anciens",)):
    """Alerte à afficher sur la ligne d'un utilisateur : (code, libellé) ou None."""
    fg = {fold(g) for g in former_groups if g}
    if fg & {fold(g) for g in (u.get("groups") or [])}:
        return "former", "ancien"
    if u.get("fiche_former"):
        return "former", "ancien (fiche ownCloud)"
    if u.get("missing"):
        return "missing", "absent de l'annuaire"
    if u.get("directory") and u.get("enabled") == 0:
        return "disabled", "désactivé"
    if not u.get("directory"):
        return "unknown", "hors annuaire"
    return None
