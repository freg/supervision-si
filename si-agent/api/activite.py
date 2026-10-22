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


@bp.get("/etat-hub")
def etat_hub():
    t = time.time()
    c = _cnx()
    rows = [dict(r) for r in c.execute("SELECT * FROM activite WHERE debut > ? ORDER BY debut DESC LIMIT 200", (t - CONSERVATION_S,))]
    c.close()
    return jsonify(dict(resume(rows, t), maintenant=t))
