# -*- coding: utf-8 -*-
"""Noyau groupware (livraison #664, item 115) -- logique PURE, inspirée des mécanismes transverses d'eGroupware :
- grants : un propriétaire accorde à un utilisateur ou un groupe des droits sur SES données, application par application
  (r lecture, a ajout, e modification, d suppression, p privé = voir les entrées marquées privées) ;
- préférences à quatre niveaux : forcée (admin) > utilisateur > groupe > défaut ;
- droits Radicale : les grants des applications `calendar` et `addressbook` deviennent le fichier `rights` du serveur
  CalDAV/CardDAV (les groupes sont développés en membres par l'appelant).
Aucune dépendance : testable sans Flask ni base."""
import re

RIGHTS = {"r": 1, "a": 2, "e": 4, "d": 8, "p": 16}
APPS = ("calendar", "addressbook", "infolog", "timesheet", "resources", "files", "notes")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,120}$")


def parse_rights(text):
    """'read' / 'r' / 'rae' / entier -> masque ; lettres inconnues refusées."""
    if isinstance(text, int):
        return text & 31
    t = str(text or "").strip().lower()
    if t.isdigit():
        return int(t) & 31
    if t in ("read", "lecture"):
        t = "r"
    if t in ("write", "ecriture", "écriture"):
        t = "raed"
    if t in ("all", "tout"):
        t = "raedp"
    mask = 0
    for ch in t:
        if ch not in RIGHTS:
            raise ValueError("droit inconnu : %s (r a e d p)" % ch)
        mask |= RIGHTS[ch]
    return mask


def rights_text(mask):
    return "".join(k for k, v in RIGHTS.items() if mask & v)


def effective(grants, app, user, groups=()):
    """Droits effectifs de `user` (membre de `groups`) sur les données de chaque propriétaire pour `app` : union des grants
    nominatifs et de groupe ; le propriétaire a toujours tout sur ses données. -> {owner: masque}."""
    groups = set(groups or [])
    out = {user: 31}
    for g in grants:
        if g.get("app") != app:
            continue
        kind, who = g.get("grantee_kind"), g.get("grantee")
        if (kind == "user" and who == user) or (kind == "group" and who in groups) or (kind == "all"):
            out[g["owner"]] = out.get(g["owner"], 0) | int(g.get("rights") or 0)
    return out


def validate_grant(body):
    owner = str(body.get("owner") or "").strip()
    app = str(body.get("app") or "").strip()
    kind = str(body.get("grantee_kind") or "user").strip()
    grantee = str(body.get("grantee") or "").strip()
    if not NAME_RE.match(owner):
        return None, "owner (propriétaire) requis"
    if app not in APPS:
        return None, "app : " + ", ".join(APPS)
    if kind not in ("user", "group", "all"):
        return None, "grantee_kind : user, group ou all"
    if kind != "all" and not NAME_RE.match(grantee):
        return None, "grantee (utilisateur ou groupe) requis"
    try:
        rights = parse_rights(body.get("rights", "r"))
    except ValueError as e:
        return None, str(e)
    if kind == "all":
        grantee = "*"
    if owner == grantee and kind == "user":
        return None, "un propriétaire a déjà tous les droits sur ses données"
    return {"owner": owner, "app": app, "grantee_kind": kind, "grantee": grantee, "rights": rights}, None


def resolve_prefs(rows, app, user, groups=()):
    """rows = [{level, subject, app, key, value}] ; level : default | group | user | forced. -> {key: value}, la source
    la plus forte gagne : forced > user > group (dans l'ordre des groupes donnés) > default ; app '*' = toutes."""
    groups = list(groups or [])
    rank = {"default": 0, "group": 1, "user": 2, "forced": 3}
    best = {}
    for r in rows:
        if r.get("app") not in (app, "*"):
            continue
        lvl = r.get("level")
        if lvl == "group" and r.get("subject") not in groups:
            continue
        if lvl == "user" and r.get("subject") != user:
            continue
        if lvl not in rank:
            continue
        score = (rank[lvl], 1 if r.get("app") == app else 0, (-groups.index(r["subject"]) if lvl == "group" else 0))
        if r["key"] not in best or score > best[r["key"]][0]:
            best[r["key"]] = (score, r.get("value"))
    return {k: v for k, (_, v) in best.items()}


# Radicale ne connaît pas le type d'une collection dans son fichier de droits : la distinction agenda / carnet passe par
# une CONVENTION DE NOM des collections (agenda-… ou cal… pour les agendas, contacts-… / carnet… / ab… pour les carnets).
DAV_APPS = {"calendar": "(agenda|cal|calendar)[^/]*", "addressbook": "(contacts|carnet|ab|addressbook)[^/]*"}


def radicale_rights(grants, members_of, users=()):
    """Fichier `rights` de Radicale (type from_file) : chacun est maître de sa collection ; un grant calendar/addressbook
    lecture -> r (collection) + R (contenu), ajout/modification/suppression -> w/W. Les grants de groupe sont développés
    avec `members_of(group) -> [uid]`. `all` -> tout utilisateur authentifié. Radicale évalue les sections dans l'ordre :
    la première qui correspond (utilisateur ET collection) décide -- d'où les partages avant la règle « soi-même »."""
    lines = ["# GÉNÉRÉ par groupware-api depuis les partages (grants) -- ne pas éditer, voir la tuile Groupware.", ""]
    n = 0
    for g in sorted(grants, key=lambda x: (x["owner"], x["app"], x["grantee_kind"], x["grantee"])):
        if g["app"] not in DAV_APPS:
            continue
        perms = "rR" if g["rights"] & RIGHTS["r"] else ""
        if g["rights"] & (RIGHTS["a"] | RIGHTS["e"] | RIGHTS["d"]):
            perms = "rRwW"
        if not perms:
            continue
        if g["grantee_kind"] == "user":
            who = [g["grantee"]]
        elif g["grantee_kind"] == "group":
            who = sorted(set(members_of(g["grantee"]) or []))
        else:
            who = [".+"]
        for u in who:
            if u == g["owner"]:
                continue
            n += 1
            lines += ["[grant-%d]" % n, "user: ^%s$" % (u if u == ".+" else re.escape(u)), "collection: ^%s/%s(/.*)?$" % (re.escape(g["owner"]), DAV_APPS[g["app"]]), "permissions: %s" % perms, ""]
    lines += ["[owner-write]", "user: .+", "collection: ^{user}(/.*)?$", "permissions: RW", "", "[root]", "user: .+", "collection: ^$", "permissions: R", ""]
    return "\n".join(lines)


def dav_urls(public_base, user):
    base = (public_base or "").rstrip("/")
    return {"principal": "%s/%s/" % (base, user), "caldav": "%s/%s/" % (base, user), "carddav": "%s/%s/" % (base, user),
            "discovery": base + "/", "note": "Les clients (Thunderbird, DAVx5, iOS, macOS) découvrent les agendas et carnets à partir de l'URL du principal ; une collection se crée depuis le client ou l'interface Radicale (%s/.web/)." % base}
