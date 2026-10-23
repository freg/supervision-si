# -*- coding: utf-8 -*-
"""Module d'action sur le réseau (livraison #852) : plan, impact immédiat, exécution par l'API avec sauvegarde, chien
de garde (contrôles à +60 s et +180 s), retour arrière automatique ou à la demande, plans manuels vérifiés par
relecture, journal (table nebula_actions) et alertes (notify-api, action « nebula.action-reseau »).

Routes : GET /sites/<site>/actions/plan/<aid> ; POST /sites/<site>/actions/executer {aid, confirm, confirm_impact} ;
POST /sites/<site>/actions/manuel {aid} ; POST /actions/<id>/verifier ; POST /actions/<id>/annuler ; GET /actions.
Écriture seulement si NEBULA_ALLOW_WRITE=1 et droit « manage » ; logique pure : actions.py."""
import json
import os
import threading
import time
import uuid

from flask import jsonify, request

import actions

SURVEILLANCE = [int(x) for x in os.environ.get("NEBULA_ACTION_SURVEILLANCE", "60,180").split(",") if x.strip().isdigit()] or [60, 180]
_hooks = {}


def _db():
    return _hooks["conn"]()


def _ecrire(a):
    conn = _db()
    try:
        conn.execute("INSERT OR REPLACE INTO nebula_actions (id, site_id, aid, at, etat, data) VALUES (?, ?, ?, ?, ?, ?)",
                     (a["id"], a["site_id"], a["aid"], a["at"], a["etat"], json.dumps(a, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def _lire(i):
    conn = _db()
    try:
        r = conn.execute("SELECT data FROM nebula_actions WHERE id = ?", (i,)).fetchone()
        return json.loads(r["data"]) if r else None
    finally:
        conn.close()


def _note(a, texte):
    a.setdefault("journal", []).append({"at": int(time.time()), "texte": texte})


def _impact(client, site_id, perimetre):
    errs = []

    def essai(f):
        try:
            r = f()
            return r.get("data", r) if isinstance(r, dict) and isinstance(r.get("data"), list) else r
        except Exception as e:  # noqa: BLE001
            errs.append(str(e)[:120])
            return None
    cl = essai(lambda: client.get_site_clients(site_id, features=["mac_address", "ipv4", "vlan", "last_seen", "os_hostname", "description"], period="2h"))
    sw = essai(lambda: client.sw_clients(site_id, "2h"))
    ap = essai(lambda: client.ap_clients_v2(site_id, "2h"))
    i = actions.impact(perimetre, cl if isinstance(cl, list) else None, sw if isinstance(sw, list) else None, ap if isinstance(ap, list) else None, _hooks["ssid_vlan"](site_id))
    i["erreurs"] = errs
    return i


def _port(client, site_id, dev, num):
    return next((p for p in client.sw_port_settings(site_id, dev) or [] if isinstance(p, dict) and str(p.get("portNum")) == str(num)), None)


def _statut(client, site_id, dev):
    for s in client.get_online_status(site_id) or []:
        if s.get("devId") == dev:
            v = str(s.get("currentStatus") or s.get("status") or "").lower()
            return "online" if v in ("online", "true", "1") else v or "inconnu"
    return "inconnu"


def _notifier(a, sujet):
    try:
        _hooks["notify"]("nebula.action-reseau", sujet, "%s\n\n%s\n" % (sujet, "\n".join("%s  %s" % (time.strftime("%d/%m %H:%M", time.localtime(j["at"])), j["texte"]) for j in a.get("journal") or [])))
    except Exception:  # noqa: BLE001 -- l'alerte ne bloque jamais l'action
        pass


def _retour(client, a, raison):
    p = a["plan"]["perimetre"]
    try:
        client.sw_set_port_settings(a["site_id"], p["dev"], a["avant"])
        a["etat"] = "annulee"
        _note(a, "RETOUR ARRIÈRE (%s) : port %s de %s remis dans son état sauvegardé" % (raison, p["port"], p["equipement"]))
    except Exception as e:  # noqa: BLE001
        a["etat"] = "echec_retour"
        _note(a, "RETOUR ARRIÈRE IMPOSSIBLE (%s) : %s -- remettre à la main : VLAN autorisés %s" % (raison, str(e)[:160], ", ".join(map(str, a["avant"].get("allowedVLAN") or []))))
    _hooks["invalidate"]()


def surveiller(i, attentes=None, dormir=time.sleep):
    """Chien de garde d'une action par l'API : contrôles successifs, retour arrière au premier commutateur hors ligne
    ou si le dernier contrôle échoue."""
    attentes = attentes or SURVEILLANCE
    precedent = 0
    for n, t in enumerate(attentes):
        dormir(max(0, t - precedent)); precedent = t
        a = _lire(i)
        if not a or a["etat"] != "surveillance":
            return a
        client = _hooks["client"]()
        p = a["plan"]["perimetre"]
        try:
            etat = {"dev_status": _statut(client, a["site_id"], p["dev"]), "port": _port(client, a["site_id"], p["dev"], p["port"]),
                    "clients_avant": a["impact"]["actifs"], "clients_apres": _impact(client, a["site_id"], p)["actifs"]}
        except Exception as e:  # noqa: BLE001
            etat = {"dev_status": "injoignable (%s)" % str(e)[:80]}
        ctrl = actions.controles(p, etat)
        a["controles"] = ctrl
        _note(a, "contrôle à +%d s : %s" % (t, " ; ".join("%s %s (%s)" % ("✓" if c["ok"] else "✗", c["nom"], c["detail"]) for c in ctrl)))
        dernier = n == len(attentes) - 1
        if etat.get("dev_status") != "online" or (dernier and not actions.bilan(ctrl)):
            _retour(client, a, "contrôle à +%d s en échec" % t)
            _ecrire(a)
            _notifier(a, "Réseau : action annulée -- %s" % a["element"])
            return a
        if dernier:
            a["etat"] = "verifiee"
            _note(a, "action vérifiée")
            _hooks["set_state"](a["site_id"], a["aid"], "applied", a["user"], a["plan"]["etapes"][1], "appliquée et vérifiée (action %s)" % a["id"])
            _hooks["invalidate"]()
            _notifier(a, "Réseau : action appliquée et vérifiée -- %s" % a["element"])
        _ecrire(a)
    return _lire(i)


def register(app, hooks, demarrer_surveillance=True):
    """hooks : conn() ; client() ; anomalies(site, refresh) -> (items, errors, vmap) ; ssid_vlan(site) ; manage(body) ;
    allow_write() ; set_state(site, aid, state, who, action, result) ; invalidate() ; notify(action, sujet, corps)."""
    _hooks.clear(); _hooks.update(hooks)
    conn = hooks["conn"]()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS nebula_actions (id TEXT PRIMARY KEY, site_id TEXT, aid TEXT, at INTEGER, etat TEXT, data TEXT)")
        conn.commit()
    finally:
        conn.close()
    lancer = (lambda i: threading.Thread(target=surveiller, args=(i,), name="nebula-action-%s" % i, daemon=True).start()) if demarrer_surveillance else (lambda i: None)

    def anomalie(site_id, aid, refresh=False):
        items, _e, _v = hooks["anomalies"](site_id, refresh)
        return next((x for x in items if x["id"] == aid), None)

    @app.route("/sites/<site_id>/actions/plan/<aid>", methods=["GET"])
    def action_plan(site_id, aid):
        a = anomalie(site_id, aid)
        if not a:
            return jsonify({"error": "anomalie introuvable (carte recalculée entre-temps ?)"}), 404
        pl = actions.plan(a)
        try:
            imp = _impact(hooks["client"](), site_id, pl["perimetre"])
        except Exception as e:  # noqa: BLE001
            imp = {"niveau": "inconnu", "texte": "impact non mesuré : %s" % str(e)[:160], "clients": [], "actifs": 0, "recents": 0, "octets_2h": 0}
        return jsonify({"anomalie": {k: a.get(k) for k in ("id", "kind", "element", "message", "severity", "action")}, "plan": pl, "impact": imp,
                        "ecriture_autorisee": bool(hooks["allow_write"]()), "surveillance_s": SURVEILLANCE}), 200

    @app.route("/sites/<site_id>/actions/executer", methods=["POST"])
    def action_executer(site_id):
        b = request.get_json(silent=True) or {}
        ok, err = hooks["manage"](b)
        if not ok:
            return jsonify({"error": err}), 403
        a = anomalie(site_id, b.get("aid") or "")
        if not a:
            return jsonify({"error": "anomalie introuvable"}), 404
        pl = actions.plan(a)
        if pl["mode"] != "api":
            return jsonify({"error": "pas d'écriture par l'API pour ce type : plan manuel"}), 400
        if not hooks["allow_write"]():
            return jsonify({"error": "écriture sur Nebula désactivée (NEBULA_ALLOW_WRITE=0 dans le .env)"}), 403
        if not b.get("confirm"):
            return jsonify({"error": "confirmation requise : l'action ÉCRIT la configuration", "needs_confirm": True}), 409
        client = hooks["client"]()
        imp = _impact(client, site_id, pl["perimetre"])
        if imp["niveau"] == "fort" and not b.get("confirm_impact"):
            return jsonify({"error": "impact fort : " + imp["texte"], "needs_confirm_impact": True, "impact": imp}), 409
        p = pl["perimetre"]
        avant = _port(client, site_id, p["dev"], p["port"])
        if not avant:
            return jsonify({"error": "port %s introuvable sur %s" % (p["port"], p["equipement"])}), 502
        apres = dict(avant, trunk=True, allowedVLAN=[str(v) for v in avant.get("allowedVLAN") or []])
        for v in p["vlans"]:
            if str(v) not in apres["allowedVLAN"]:
                apres["allowedVLAN"].append(str(v))
        act = {"id": uuid.uuid4().hex[:10], "site_id": site_id, "aid": a["id"], "kind": a["kind"], "element": a.get("element"), "message": a.get("message"),
               "at": int(time.time()), "user": b.get("user") or "?", "mode": "api", "plan": pl, "impact": imp, "avant": avant, "apres": apres, "etat": "en_cours", "controles": []}
        _note(act, "sauvegarde du port %s de %s : VLAN autorisés %s" % (p["port"], p["equipement"], ", ".join(map(str, avant.get("allowedVLAN") or [])) or "aucun"))
        try:
            client.sw_set_port_settings(site_id, p["dev"], apres)
        except Exception as e:  # noqa: BLE001
            act["etat"] = "echec"
            _note(act, "écriture refusée : %s (rien n'a changé)" % str(e)[:200])
            _ecrire(act)
            return jsonify(act), 502
        act["etat"] = "surveillance"
        _note(act, "écrit : VLAN autorisés %s ; chien de garde à +%s s" % (", ".join(apres["allowedVLAN"]), " s, +".join(map(str, SURVEILLANCE))))
        _ecrire(act)
        hooks["invalidate"]()
        lancer(act["id"])
        return jsonify(act), 202

    @app.route("/sites/<site_id>/actions/manuel", methods=["POST"])
    def action_manuel(site_id):
        b = request.get_json(silent=True) or {}
        ok, err = hooks["manage"](b)
        if not ok:
            return jsonify({"error": err}), 403
        a = anomalie(site_id, b.get("aid") or "")
        if not a:
            return jsonify({"error": "anomalie introuvable"}), 404
        pl = actions.plan(a)
        act = {"id": uuid.uuid4().hex[:10], "site_id": site_id, "aid": a["id"], "kind": a["kind"], "element": a.get("element"), "message": a.get("message"),
               "at": int(time.time()), "user": b.get("user") or "?", "mode": "manuel", "plan": pl, "impact": b.get("impact") or {}, "etat": "attente_manuel", "controles": []}
        _note(act, "plan manuel ouvert : %s" % " ; ".join(pl["etapes"][:2]))
        _ecrire(act)
        return jsonify(act), 201

    @app.route("/actions/<i>/verifier", methods=["POST"])
    def action_verifier(i):
        act = _lire(i)
        if not act:
            return jsonify({"error": "action inconnue"}), 404
        items, _e, _v = hooks["anomalies"](act["site_id"], True)
        encore = any(x["id"] == act["aid"] or (x["kind"] == act["kind"] and x.get("element") == act["element"]) for x in items)
        act["controles"] = actions.controles(act["plan"]["perimetre"] if act["mode"] == "manuel" else {"vlans": act["plan"]["perimetre"].get("vlans")}, {"anomalie_presente": encore})
        act["etat"] = "non_resolue" if encore else "verifiee"
        _note(act, "vérification par relecture : %s" % ("anomalie toujours signalée" if encore else "anomalie disparue"))
        if not encore:
            hooks["set_state"](act["site_id"], act["aid"], "applied", (request.get_json(silent=True) or {}).get("user") or act["user"], act["plan"]["etapes"][0], "corrigée (vérifiée, action %s)" % i)
        _ecrire(act)
        return jsonify(act), 200

    @app.route("/actions/<i>/annuler", methods=["POST"])
    def action_annuler(i):
        b = request.get_json(silent=True) or {}
        ok, err = hooks["manage"](b)
        if not ok:
            return jsonify({"error": err}), 403
        act = _lire(i)
        if not act:
            return jsonify({"error": "action inconnue"}), 404
        if act["mode"] != "api" or act["etat"] not in ("surveillance", "verifiee"):
            return jsonify({"error": "rien à annuler par l'API (mode %s, état %s) : %s" % (act["mode"], act["etat"], act["plan"].get("retour"))}), 400
        _retour(hooks["client"](), act, "demande de %s" % (b.get("user") or "?"))
        _ecrire(act)
        _notifier(act, "Réseau : action annulée à la demande -- %s" % act["element"])
        return jsonify(act), 200

    @app.route("/actions", methods=["GET"])
    def actions_liste():
        conn = _db()
        try:
            q, prm = "SELECT data FROM nebula_actions", []
            if request.args.get("site"):
                q += " WHERE site_id = ?"; prm.append(request.args["site"])
            rows = conn.execute(q + " ORDER BY at DESC LIMIT 100", prm).fetchall()
        finally:
            conn.close()
        return jsonify({"actions": [json.loads(r["data"]) for r in rows], "surveillance_s": SURVEILLANCE}), 200
