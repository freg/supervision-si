"""Logique pure du module datasync (testée à part) :
- profil d'une colonne depuis un échantillon de valeurs (type observé, formats : email, téléphone, date, identifiant, booléen…) ;
- normalisation des noms de champs (id_contact ~ contact_id ~ contactId ~ IDCONTACT) ;
- correspondances entre champs de tables (même source ou sources différentes) : nom, format, recouvrement des valeurs ;
- déduction des relations : une colonne « id_x » / « x_id » dont les valeurs se retrouvent dans la clé d'une table x."""
import re, datetime

STOP = {"id", "num", "no", "numero", "code", "ref", "the", "le", "la", "les", "de", "du", "des", "d", "l"}
SYN = {"contact": "contact", "contacts": "contact", "personne": "contact", "client": "contact", "customer": "contact", "user": "user", "users": "user",
       "utilisateur": "user", "utilisateurs": "user", "login": "user", "site": "site", "sites": "site", "lieu": "site", "location": "site", "ticket": "ticket",
       "tickets": "ticket", "demande": "ticket", "demandes": "ticket", "incident": "ticket", "societe": "company", "company": "company", "entreprise": "company",
       "org": "company", "organisation": "company", "mail": "email", "email": "email", "courriel": "email", "tel": "phone", "telephone": "phone", "phone": "phone",
       "mobile": "phone", "date": "date", "ts": "date", "timestamp": "date", "created": "date", "creation": "date", "nom": "name", "name": "name", "libelle": "name",
       "label": "name", "titre": "name", "title": "name", "subject": "name", "sujet": "name", "adresse": "address", "address": "address", "ville": "city", "city": "city",
       "cp": "zip", "zip": "zip", "codepostal": "zip", "categorie": "category", "category": "category", "statut": "status", "status": "status", "etat": "status"}

def tokens(name):
    """'id_Contact' -> ['contact'] ; 'contactId' -> ['contact'] ; 'tts_tickets' -> ['ticket'] (préfixes courts et mots vides retirés, synonymes repliés)."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name or "")).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    parts = [p for p in s.split("_") if p]
    if len(parts) > 1 and len(parts[0]) <= 4 and parts[0] not in SYN: parts = parts[1:]        # préfixe d'application (tts_, gu_, t_)
    out = []
    for p in parts:
        if p in STOP or p.isdigit(): continue
        p = re.sub(r"s$", "", p) if len(p) > 4 and p not in SYN else p
        out.append(SYN.get(p, p))
    return out or [s.strip("_")]

def bare_id(name):
    """Colonne dont le nom ne porte aucun concept (id, num, code, ref…)."""
    s = re.sub(r"[^a-z0-9]+", "_", str(name or "").lower()).strip("_")
    return all(p in STOP or p.isdigit() for p in s.split("_") if p)

def is_id_like(name):
    s = str(name or "").lower()
    return bool(re.search(r"(^|_)id($|_)|_?id$|^id[a-z]", s)) or s in ("userid", "ticketid")

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
PHONE = re.compile(r"^\+?[\d .()-]{8,20}$")
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?|\d{2}/\d{2}/\d{4})$")
TS = re.compile(r"^\d{9,10}$")
BIGTS = re.compile(r"^\d{12,14}$")

def profile(values):
    """Profil d'un échantillon : {kind, n, distinct, null_ratio, formats: {email, phone, date, int, bool, text…: part}, avg_len, sample}."""
    vals = [v for v in values if v is not None and str(v).strip() != ""]; n = len(values); nn = len(vals)
    if not nn: return dict(kind="empty", n=n, distinct=0, null_ratio=1.0, formats={}, avg_len=0, sample=[])
    counts = dict(email=0, phone=0, date=0, int=0, float=0, bool=0, text=0, ts=0, bigts=0)
    for v in vals:
        s = str(v).strip()
        if EMAIL.match(s): counts["email"] += 1
        elif DATE.match(s): counts["date"] += 1
        elif isinstance(v, bool) or s.lower() in ("0", "1", "true", "false", "oui", "non", "yes", "no") and len(set(str(x).strip().lower() for x in vals)) <= 2: counts["bool"] += 1
        elif BIGTS.match(s): counts["bigts"] += 1
        elif TS.match(s): counts["ts"] += 1
        elif re.fullmatch(r"-?\d+", s): counts["int"] += 1
        elif re.fullmatch(r"-?\d+[.,]\d+", s): counts["float"] += 1
        elif PHONE.match(s) and re.search(r"\d{6}", re.sub(r"\D", "", s)): counts["phone"] += 1
        else: counts["text"] += 1
    formats = {k: round(c / nn, 2) for k, c in counts.items() if c}
    kind = max(formats, key=formats.get)
    if kind == "int" and formats["int"] >= 0.95: kind = "int"
    return dict(kind=kind, n=n, distinct=len(set(str(v).strip() for v in vals)), null_ratio=round(1 - nn / n, 2) if n else 0, formats=formats,
                avg_len=round(sum(len(str(v)) for v in vals) / nn, 1), sample=[str(v)[:40] for v in vals[:5]])

def name_score(a, b):
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb: return 0.0
    if ta == tb: return 1.0
    j = len(ta & tb) / len(ta | tb)
    return round(j, 2)

def overlap(values_a, values_b):
    """Recouvrement des valeurs distinctes (part de A présente dans B et inversement), insensible à la casse/espaces."""
    A = {str(v).strip().lower() for v in values_a if v not in (None, "")}; B = {str(v).strip().lower() for v in values_b if v not in (None, "")}
    if not A or not B: return 0.0, 0.0
    inter = len(A & B); return round(inter / len(A), 2), round(inter / len(B), 2)

def match_fields(fields, min_score=0.5):
    """fields : [{source, table, column, profile, values}] -> correspondances [{a, b, score, reasons}] entre champs de TABLES DIFFÉRENTES
    (score = 0.5·nom + 0.2·format + 0.3·recouvrement ; les identifiants purs sans recouvrement ne sont pas proposés)."""
    out = []
    for i in range(len(fields)):
        for j in range(i + 1, len(fields)):
            a, b = fields[i], fields[j]
            if (a["source"], a["table"]) == (b["source"], b["table"]): continue
            ns = name_score(a["column"], b["column"]); pa, pb = a.get("profile") or {}, b.get("profile") or {}
            fs = 1.0 if pa.get("kind") and pa.get("kind") == pb.get("kind") and pa["kind"] not in ("empty",) else 0.0
            oa, ob = overlap(a.get("values") or [], b.get("values") or []); ov = max(oa, ob)
            if bare_id(a["column"]) or bare_id(b["column"]): continue                       # « id » nu : la clé, pas un concept
            if pa.get("kind") in ("int", "ts", "bigts") and pb.get("kind") in ("int", "ts", "bigts") and ns < 0.5: continue   # identifiants : c'est le rôle des relations
            score = round(0.5 * ns + 0.2 * fs + 0.3 * ov, 2)
            if score >= min_score:
                reasons = [r for r, ok in (("nom", ns >= 0.5), ("format " + str(pa.get("kind")), fs == 1.0), (f"valeurs {int(ov * 100)} %", ov >= 0.3)) if ok]
                out.append(dict(a=dict(source=a["source"], table=a["table"], column=a["column"]), b=dict(source=b["source"], table=b["table"], column=b["column"]), score=score, reasons=reasons))
    return sorted(out, key=lambda x: -x["score"])

def deduce_relations(tables):
    """tables : {(source, table): {"pk": col, "columns": {col: {profile, values}}}} -> relations [{from, column, to, to_column, score, reason}] :
    une colonne id_x / x_id (ou de même racine que la table x) dont les valeurs se retrouvent dans la clé de x (même source d'abord, puis autres sources)."""
    rels = []
    for (src, tname), t in tables.items():
        for col, info in t["columns"].items():
            if col == t.get("pk") or not is_id_like(col): continue
            tk = set(tokens(col))
            for (src2, tname2), t2 in tables.items():
                if (src2, tname2) == (src, tname) or not t2.get("pk"): continue
                if not (tk & set(tokens(tname2))): continue
                pkv = (t2["columns"].get(t2["pk"]) or {}).get("values") or []
                oa, _ = overlap(info.get("values") or [], pkv)
                if oa >= 0.5:
                    rels.append(dict(**{"from": dict(source=src, table=tname)}, column=col, to=dict(source=src2, table=tname2), to_column=t2["pk"],
                                     score=round(oa * (1.0 if src == src2 else 0.9), 2), reason=f"{col} → {tname2}.{t2['pk']} : {int(oa * 100)} % des valeurs résolues" + ("" if src == src2 else " (source différente)")))
    return sorted(rels, key=lambda x: -x["score"])

def flatten_for_fts(row):
    """Contenu indexé d'une ligne : valeurs texte concaténées (clés incluses pour les recherches « champ:valeur »)."""
    parts = []
    for k, v in (row or {}).items():
        if v is None: continue
        s = str(v).strip()
        if s and not re.fullmatch(r"-?\d+(\.\d+)?", s): parts.append(f"{k} {s}")
        elif s: parts.append(s)
    return " ".join(parts)[:20000]
