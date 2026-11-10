# -*- coding: utf-8 -*-
"""Liste de surveillance (livraison #1001) -- routes ; logique : surveillance.py.

- GET    /surveillance                    : ?site= &jours=30 -> {listes, elements (avec leur dernier repère), reperes}
- POST   /surveillance/importer           : {liste, texte, apercu} -> aperçu de l'analyse, ou enregistrement (droit manage)
- DELETE /surveillance/elements/<id>      : {groups} (droit manage)
- DELETE /surveillance/listes/<nom>       : {groups} (droit manage)
- POST   /surveillance/rapprocher         : {site?, jours=7} -> rapprochement immédiat sur l'historique des clients
- POST   /surveillance/reperes/<id>/decision : {decision: confirme|rejete|annule, element_id?, groups, user} (droit manage)
Rapprochement automatique : après chaque relève de l'historique des clients (apres_releve), alerte par notify-api
pour un nouvel élément repéré ou une discordance (usurpation possible)."""
import time

from flask import jsonify, request

import surveillance as sv

LIEN = {"view": "nebula", "tab": "surveillance"}
REGLAGE_DROIT = {"view": "rights", "texte": "Droits › nebula-api › action « manage » : groupe admin_hub, ou un octroi explicite à ton groupe"}
FENETRE_RELEVE_S = 3 * 3600


def _refus(err):
    return jsonify({"error": err, "reglage": REGLAGE_DROIT}), 403


def resume_alerte(evts):
    """Évènements d'un rapprochement -> (sujet, corps, gravité) ou None."""
    if not evts:
        return None
    disc = [e for e in evts if e["type"] == "discordance" or e["statut"] == "discordant"]
    lignes = []
    for e in evts:
        quoi = e["element"] or "élément à attribuer (du lot)"
        lignes.append("- [%s] %s : %s — %s, MAC %s%s%s" % (e["liste"], e["statut"], quoi, e.get("nom") or "sans nom", e["mac"],
                                                            ", borne %s" % e["borne"] if e.get("borne") else "",
                                                            (" — " + " ; ".join(e["discordances"])) if e.get("discordances") else ""))
    sujet = ("Liste de surveillance : %d discordance(s) — usurpation possible ou changement à valider" % len(disc) if disc
             else "Liste de surveillance : %d élément(s) repéré(s)" % len(evts))
    return sujet, "\n".join(lignes[:50]) + "\n\nÀ valider dans le hub : Nebula › Surveillance.", ("warning" if disc else "info")


def register(app, deps):
    """deps : conn(), manage(body) -> (ok, erreur), notify(sujet, corps, gravite), sites() -> [{siteId}]"""

    def _sites(body_site=None):
        if body_site:
            return [body_site]
        return [s.get("siteId") for s in (deps["sites"]() or []) if s.get("siteId")]

    def apres_releve(site_id, now=None):
        now = int(now or time.time())
        conn = deps["conn"]()
        try:
            evts = sv.rapprocher(conn, site_id, now - FENETRE_RELEVE_S, now=now)
        finally:
            conn.close()
        a = resume_alerte(evts)
        if a:
            try:
                deps["notify"](*a)
            except Exception:  # noqa: BLE001 -- une alerte non envoyée ne casse pas la relève ; les repères restent dans l'onglet
                pass
        return evts

    @app.route("/surveillance", methods=["GET"])
    def surveillance_get():
        jours = max(1, min(400, int(request.args.get("jours", 30) or 30)))
        conn = deps["conn"]()
        try:
            els = sv.elements(conn)
            reps = sv.reperes(conn, request.args.get("site") or None, depuis=int(time.time()) - jours * 86400)
            lst = sv.listes(conn)
        finally:
            conn.close()
        dernier = {}
        for r in reps:                     # triés du plus récent au plus ancien
            if r["element_id"] != sv.LOT and r.get("decision") != "rejete":
                dernier.setdefault(r["element_id"], r)
        for e in els:
            e["dernier_repere"] = dernier.get(e["id"])
        return jsonify({"listes": lst, "elements": els, "reperes": reps, "jours": jours}), 200

    @app.route("/surveillance/importer", methods=["POST"])
    def surveillance_importer():
        body = request.get_json(silent=True) or {}
        analyse = sv.analyser_texte(body.get("texte") or "")
        if body.get("apercu"):
            return jsonify(analyse), 200
        ok, err = deps["manage"](body)
        if not ok:
            return _refus(err)
        if not analyse["elements"]:
            return jsonify({"error": "aucun élément reconnu dans le texte", "ignorees": analyse["ignorees"]}), 400
        conn = deps["conn"]()
        try:
            res = sv.enregistrer(conn, body.get("liste"), analyse["elements"], par=str(body.get("user") or "")[:64] or None)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        finally:
            conn.close()
        evts = []
        for sid in _sites():
            try:
                evts += apres_releve(sid)
            except Exception:  # noqa: BLE001 -- l'enregistrement est fait ; le rapprochement se refera à la relève
                pass
        return jsonify(dict(res, ignorees=analyse["ignorees"], reperes=len(evts))), 200

    @app.route("/surveillance/elements/<int:eid>", methods=["DELETE"])
    def surveillance_suppr_element(eid):
        ok, err = deps["manage"](request.get_json(silent=True) or {})
        if not ok:
            return _refus(err)
        conn = deps["conn"]()
        try:
            n = sv.supprimer_element(conn, eid)
        finally:
            conn.close()
        return (jsonify({"supprime": n}), 200) if n else (jsonify({"error": "élément introuvable"}), 404)

    @app.route("/surveillance/listes/<path:nom>", methods=["DELETE"])
    def surveillance_suppr_liste(nom):
        ok, err = deps["manage"](request.get_json(silent=True) or {})
        if not ok:
            return _refus(err)
        conn = deps["conn"]()
        try:
            n = sv.supprimer_liste(conn, nom)
        finally:
            conn.close()
        return (jsonify({"supprimes": n}), 200) if n else (jsonify({"error": "liste introuvable"}), 404)

    @app.route("/surveillance/rapprocher", methods=["POST"])
    def surveillance_rapprocher():
        body = request.get_json(silent=True) or {}
        jours = max(1, min(400, int(body.get("jours") or 7)))
        now = int(time.time())
        out = []
        conn = deps["conn"]()
        try:
            for sid in _sites(body.get("site")):
                out += sv.rapprocher(conn, sid, now - jours * 86400, now=now)
        finally:
            conn.close()
        return jsonify({"evenements": out, "jours": jours}), 200

    @app.route("/surveillance/reperes/<int:rid>/decision", methods=["POST"])
    def surveillance_decision(rid):
        body = request.get_json(silent=True) or {}
        ok, err = deps["manage"](body)
        if not ok:
            return _refus(err)
        conn = deps["conn"]()
        try:
            return jsonify(sv.decider(conn, rid, body.get("decision"), body.get("element_id"), par=str(body.get("user") or "")[:64] or None)), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except LookupError as e:
            return jsonify({"error": str(e)}), 404
        finally:
            conn.close()

    return apres_releve
