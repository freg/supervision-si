# -*- coding: utf-8 -*-
"""Défauts majeurs (livraison #975) -- logique pure + SQLite.

Un défaut majeur = un mécanisme du SI de supervision qui ne fait PLUS son travail (relève qui n'enregistre rien, tâche
périodique qui plante à chaque passage…), par opposition à une alerte passagère. Les services producteurs le signalent
(`notify_client.defaut`) et le lèvent quand ça remarche (`notify_client.defaut_leve`) ; le hub l'affiche en bandeau sur
TOUTES les vues jusqu'à résolution, avec « ignorer » (case à cocher) et « résoudre » (rapport complet à analyser ou à
transmettre). Clé = service + code : un même défaut qui se répète incrémente ses occurrences, il ne s'empile pas.
"""
import json
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS defauts (id INTEGER PRIMARY KEY AUTOINCREMENT, cle TEXT UNIQUE NOT NULL, service TEXT, code TEXT,
    titre TEXT, message TEXT, lien TEXT, contexte TEXT, journal TEXT, premiere REAL, derniere REAL, occurrences INTEGER DEFAULT 1,
    statut TEXT DEFAULT 'ouvert', ignore_par TEXT, ignore_le REAL, resolu_le REAL);
"""
MAX_JOURNAL = 60          # lignes de journal gardées par défaut
STATUTS = ("ouvert", "resolu")


def _txt(v, n):
    return str(v or "").strip()[:n] or None


def _json(v, defaut):
    try:
        return json.loads(v) if v else defaut
    except ValueError:
        return defaut


def ligne(r):
    d = dict(r)
    d["contexte"] = _json(d.get("contexte"), {})
    d["journal"] = _json(d.get("journal"), [])
    d["lien"] = _json(d.get("lien"), None)
    d["ignore"] = bool(d.get("ignore_par"))
    return d


def signaler(conn, service, corps, now=None):
    """corps : {code, titre, message, lien?: {view, …params}, contexte?: {}, journal?: [lignes]} -> (défaut, erreur)."""
    now = now or time.time()
    if not isinstance(corps, dict) or not _txt(corps.get("code"), 120) or not _txt(corps.get("titre"), 200):
        return None, "code et titre requis"
    code = _txt(corps["code"], 120)
    cle = "%s:%s" % (service, code)
    journal = [str(x)[:500] for x in (corps.get("journal") or []) if x][-MAX_JOURNAL:]
    lien = corps.get("lien") if isinstance(corps.get("lien"), dict) else None
    contexte = corps.get("contexte") if isinstance(corps.get("contexte"), dict) else {}
    conn.executescript(SCHEMA)
    r = conn.execute("SELECT * FROM defauts WHERE cle = ?", (cle,)).fetchone()
    if r is None:
        conn.execute("INSERT INTO defauts (cle, service, code, titre, message, lien, contexte, journal, premiere, derniere, occurrences, statut) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'ouvert')",
                     (cle, service, code, _txt(corps["titre"], 200), _txt(corps.get("message"), 4000), json.dumps(lien, ensure_ascii=False) if lien else None,
                      json.dumps(contexte, ensure_ascii=False, default=str), json.dumps(journal, ensure_ascii=False), now, now))
    else:
        ancien = _json(r["journal"], [])
        reapparu = r["statut"] == "resolu"
        conn.execute("UPDATE defauts SET titre = ?, message = ?, lien = COALESCE(?, lien), contexte = ?, journal = ?, derniere = ?, "
                     "occurrences = ?, statut = 'ouvert', premiere = ?, resolu_le = NULL, ignore_par = ?, ignore_le = ? WHERE cle = ?",
                     (_txt(corps["titre"], 200), _txt(corps.get("message"), 4000), json.dumps(lien, ensure_ascii=False) if lien else None,
                      json.dumps(contexte, ensure_ascii=False, default=str), json.dumps((ancien + journal)[-MAX_JOURNAL:], ensure_ascii=False), now,
                      1 if reapparu else (r["occurrences"] or 0) + 1, now if reapparu else r["premiere"],
                      None if reapparu else r["ignore_par"], None if reapparu else r["ignore_le"], cle))   # réapparu : de nouveau visible
    conn.commit()
    return ligne(conn.execute("SELECT * FROM defauts WHERE cle = ?", (cle,)).fetchone()), None


def lever(conn, service, code, now=None):
    """Le mécanisme remarche -> statut résolu (le défaut reste consultable 7 jours). -> True si un défaut ouvert a été levé."""
    conn.executescript(SCHEMA)
    n = conn.execute("UPDATE defauts SET statut = 'resolu', resolu_le = ? WHERE cle = ? AND statut = 'ouvert'",
                     (now or time.time(), "%s:%s" % (service, str(code or "")[:120]))).rowcount
    conn.commit()
    return n > 0


def lister(conn, now=None, jours_resolus=7):
    conn.executescript(SCHEMA)
    lim = (now or time.time()) - jours_resolus * 86400
    rows = conn.execute("SELECT * FROM defauts WHERE statut = 'ouvert' OR resolu_le >= ? ORDER BY statut = 'resolu', derniere DESC", (lim,)).fetchall()
    return [ligne(r) for r in rows]


def ignorer(conn, did, oui, par, now=None):
    conn.executescript(SCHEMA)
    n = conn.execute("UPDATE defauts SET ignore_par = ?, ignore_le = ? WHERE id = ?", ((par or "?") if oui else None, (now or time.time()) if oui else None, did)).rowcount
    conn.commit()
    return n > 0


def _date(t):
    return time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(t)) if t else "—"


def rapport(d):
    """Texte complet d'un défaut, à analyser ou à transmettre tel quel (aucun secret : les producteurs n'en envoient pas)."""
    l = ["DÉFAUT MAJEUR — %s" % d["titre"], "",
         "Service : %s   Code : %s" % (d["service"], d["code"]),
         "Statut : %s%s" % (d["statut"], " (ignoré par %s le %s)" % (d["ignore_par"], _date(d["ignore_le"])) if d.get("ignore_par") else ""),
         "Première occurrence : %s   Dernière : %s   Occurrences : %s" % (_date(d["premiere"]), _date(d["derniere"]), d["occurrences"])]
    if d.get("resolu_le"):
        l.append("Levé (remarche) le : %s" % _date(d["resolu_le"]))
    l += ["", "Message :", d.get("message") or "—"]
    if d.get("contexte"):
        l += ["", "Contexte :"] + ["  %s : %s" % (k, v if not isinstance(v, (dict, list)) else json.dumps(v, ensure_ascii=False)) for k, v in d["contexte"].items()]
    if d.get("journal"):
        l += ["", "Journal (dernières lignes) :"] + ["  " + x for x in d["journal"]]
    return "\n".join(l)
