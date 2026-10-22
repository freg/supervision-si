# -*- coding: utf-8 -*-
"""#830 : activité de si-agent-api pour le pied de page permanent du hub -- travaux en cours (IA qui réfléchit :
priorités, essais de skills, évaluations ; sources consultées : veille des modèles) et derniers terminés.
Même module que le hub maison (activite.py) ; table `activite` de modeles.db, partagée entre les workers.
Jamais bloquant. Pur et testé : resume."""
import time
from contextlib import contextmanager

from flask import Blueprint, jsonify

import modeles_stockage as stockage

bp = Blueprint("activite", __name__)
DB_PATH = None          # #837 : base des agents (commandes suivies), fourni par app.py
SUIVIES = {"emulation": ("émulation", "emulation"), "orchestration": ("orchestration", "orchestration")}   # type -> (libellé, vue du hub)
SCHEMA = """CREATE TABLE IF NOT EXISTS activite (id INTEGER PRIMARY KEY, genre TEXT, detail TEXT, debut REAL, fin REAL, ok INTEGER, erreur TEXT);
CREATE INDEX IF NOT EXISTS activite_debut ON activite (debut);"""
ABANDON_S = 3600
CONSERVATION_S = 2 * 86400


def _cnx():
    c = stockage.cnx()
    c.executescript(SCHEMA)
    return c


def debut(genre, detail):
    try:
        c = _cnx()
        t = time.time()
        aid = c.execute("INSERT INTO activite (genre, detail, debut) VALUES (?,?,?)", (genre, str(detail)[:200], t)).lastrowid
        if aid % 200 == 0:
            c.execute("DELETE FROM activite WHERE debut < ?", (t - CONSERVATION_S,))
        c.commit(); c.close()
        return aid
    except Exception:  # noqa: BLE001
        return None


def fin(aid, ok=True, erreur=None):
    if not aid:
        return
    try:
        c = _cnx()
        c.execute("UPDATE activite SET fin=?, ok=?, erreur=? WHERE id=?", (time.time(), 1 if ok else 0, (str(erreur)[:300] if erreur else None), aid))
        c.commit(); c.close()
    except Exception:  # noqa: BLE001
        pass


@contextmanager
def suivre(genre, detail):
    aid = debut(genre, detail)
    try:
        yield
    except BaseException as e:
        fin(aid, False, e)
        raise
    fin(aid, True)


def resume(lignes_, maintenant):
    en_cours = [dict(r, depuis_s=int(maintenant - r["debut"])) for r in lignes_ if r.get("fin") is None and maintenant - r["debut"] < ABANDON_S]
    recentes = [dict(r, duree_s=round(r["fin"] - r["debut"], 1)) for r in lignes_ if r.get("fin") is not None][:8]
    return {"en_cours": sorted(en_cours, key=lambda r: r["debut"]), "recentes": recentes}


def _ts(iso):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def commandes_suivies(rows, maintenant):
    """#837 Commandes d'agent des tuiles Émulation / Orchestration -> travaux du pied de page (lien vers la tuile)."""
    import json as _json
    en_cours, recentes = [], []
    for r in rows:
        lib, vue = SUIVIES.get(r["type"], (r["type"], None))
        try:
            p = _json.loads(r["params"] or "{}")
        except ValueError:
            p = {}
        quoi = " ".join(str(x) for x in (p.get("action"), p.get("moteur"), p.get("nom") or p.get("instance") or p.get("profil")) if x)
        d = {"id": "cmd-%s" % r["id"], "genre": r["type"], "detail": "%s : %s · %s" % (lib, quoi, r["agent_id"]), "vue": vue,
             "debut": _ts(r["created_at"]) or maintenant}
        if r["status"] == "pending":
            if maintenant - d["debut"] < 6 * 3600:
                en_cours.append(dict(d, depuis_s=int(maintenant - d["debut"])))
        else:
            fin = _ts(r["acked_at"]) or d["debut"]
            try:
                err = (_json.loads(r["result"] or "{}") or {}).get("error")
            except ValueError:
                err = None
            recentes.append(dict(d, fin=fin, ok=r["status"] == "done" and not err, erreur=err, duree_s=round(max(0, fin - d["debut"]), 1)))
    return en_cours, sorted(recentes, key=lambda x: -x["fin"])


@bp.get("/etat-hub")
def etat_hub():
    t = time.time()
    c = _cnx()
    rows = [dict(r) for r in c.execute("SELECT * FROM activite WHERE debut > ? ORDER BY debut DESC LIMIT 200", (t - CONSERVATION_S,))]
    c.close()
    out = resume(rows, t)
    if DB_PATH:
        try:
            import store
            conn = store._connect(DB_PATH)
            try:
                cmds = [dict(r) for r in conn.execute("SELECT id, agent_id, type, params, created_at, status, result, acked_at FROM commands WHERE type IN (%s) "
                                                         "ORDER BY created_at DESC LIMIT 60" % ",".join("?" * len(SUIVIES)), tuple(SUIVIES))]
            finally:
                conn.close()
            ec, rc = commandes_suivies(cmds, t)
            out["en_cours"] = out["en_cours"] + ec
            out["recentes"] = sorted(out["recentes"] + [x for x in rc if t - x["fin"] < 2 * 86400], key=lambda x: -(x.get("fin") or 0))[:10]
        except Exception:  # noqa: BLE001 -- jamais bloquant
            pass
    return jsonify(dict(out, maintenant=t))
