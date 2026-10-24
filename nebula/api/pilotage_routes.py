# -*- coding: utf-8 -*-
"""Pilotage du réseau du campus (livraison #855) : routes /pilotage/* et boucle d'une minute (relevé, boucles de
rétroaction, avancement des bancs de test). Logique pure dans pilotage.py.

Stockage : clé-valeur de report_routes (boucles, bancs, réglages, exécutions, journal, recommandations) et table
pilotage_hist (relevés, 4 h). Sondes : netprobe-api (NETPROBE_API_URL) -- liste, dernières mesures, tâches (PUT
/agents/<id>), mesures d'une sonde depuis le début d'un banc. Notifications : action notify « nebula.pilotage »."""
import json
import os
import threading
import time
import urllib.parse
import urllib.request

from flask import jsonify, request

import pilotage as P
import report_routes as rr

NETPROBE = os.environ.get("NETPROBE_API_URL", "http://netprobe-api:5000").rstrip("/")
ACTIONS = [{"id": "nebula.pilotage", "label": "Pilotage du réseau du campus : boucle déclenchée, banc de test terminé", "severity": "warning"}]
_hooks = {}
_verrou = threading.RLock()
REGLAGES_DEFAUT = {"site_id": None, "sondes": [], "serveur_iperf": "", "cible_ping": "", "urls": [], "periode_s": 60}


# -- accès ---------------------------------------------------------------------------------------------------------
def _np(methode, chemin, corps=None, timeout=10):
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(NETPROBE + chemin, data=data, method=methode,
                                 headers={"Accept": "application/json", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(20_000_000).decode("utf-8", "replace") or "null")


def reglages():
    r = dict(REGLAGES_DEFAUT)
    r.update(rr.kv_get("pilotage_reglages", {}) or {})
    return r


def _kv(cle, defaut):
    v = rr.kv_get(cle, None)
    return defaut if v is None else v


def journal(evenement, texte, **extra):
    j = _kv("pilotage_journal", [])
    j.append(dict({"at": int(time.time()), "evenement": evenement, "texte": texte}, **extra))
    rr.kv_set("pilotage_journal", j[-300:])


def _notifier(sujet, corps):
    try:
        r = _hooks["notify"]("nebula.pilotage", sujet, corps)
        return rr._res_text(r)
    except Exception as e:  # noqa: BLE001 -- notify-api absent : journal seulement
        return "notification impossible : %s" % str(e)[:120]


def _hist_cnx():
    c = _hooks["conn"]()
    c.execute("CREATE TABLE IF NOT EXISTS pilotage_hist (at INTEGER PRIMARY KEY, valeurs TEXT NOT NULL)")
    return c


def historique():
    c = _hist_cnx()
    try:
        return [{"at": r[0], "valeurs": json.loads(r[1])} for r in c.execute("SELECT at, valeurs FROM pilotage_hist ORDER BY at")]
    finally:
        c.close()


def _hist_ajouter(inst):
    c = _hist_cnx()
    try:
        c.execute("INSERT OR REPLACE INTO pilotage_hist VALUES (?, ?)", (inst["at"], json.dumps(inst["valeurs"])))
        c.execute("DELETE FROM pilotage_hist WHERE at NOT IN (SELECT at FROM pilotage_hist ORDER BY at DESC LIMIT ?)", (P.HIST_MAX,))
        c.commit()
    finally:
        c.close()


def _site(cfg):
    sites = _hooks["sites"]() or []
    s = next((x for x in sites if x.get("siteId") == cfg.get("site_id")), None) or (sites[0] if sites else None)
    return s.get("siteId") if s else None


def sondes_netprobe():
    try:
        return [{"agent_id": a["agent_id"], "label": a.get("label") or a["agent_id"], "site": a.get("site"), "role": a.get("role"),
                 "active": a.get("active"), "last_seen_at": a.get("last_seen_at")} for a in _np("GET", "/agents").get("agents") or []
                if a.get("role") == "probe"], None
    except Exception as e:  # noqa: BLE001
        return [], "sondes injoignables : %s" % str(e)[:120]


def releve():
    """Relevé courant : charge Nebula (2 h), veille, dernières mesures des sondes."""
    cfg, errs = reglages(), []
    charge = veille = None
    try:
        sid = _site(cfg)
        charge = _hooks["charge"](sid) if sid else None
    except Exception as e:  # noqa: BLE001
        errs.append("charge Nebula : %s" % str(e)[:120])
    try:
        veille = _hooks["veille"]()
    except Exception as e:  # noqa: BLE001
        errs.append("veille : %s" % str(e)[:120])
    sondes, err = sondes_netprobe()
    latest = []
    if err:
        errs.append(err)
    else:
        try:
            latest = _np("GET", "/agents/latest").get("latest") or []
        except Exception as e:  # noqa: BLE001
            errs.append("mesures des sondes : %s" % str(e)[:120])
    return P.instantane(charge, veille, latest, {s["agent_id"]: s["label"] for s in sondes}), errs, charge, veille


# -- bancs -----------------------------------------------------------------------------------------------------------
def _plans():
    return _kv("pilotage_plans", [])


def _runs():
    return _kv("pilotage_runs", [])


def _run_en_cours():
    return next((r for r in _runs() if r.get("statut") == "en_cours"), None)


def _sauver_run(run):
    runs = [r for r in _runs() if r["id"] != run["id"]] + [run]
    rr.kv_set("pilotage_runs", runs[-30:])


def _taches(agent):
    return (_np("GET", "/agents/%s" % urllib.parse.quote(agent)) or {}).get("tasks") or []


def _poser(agent, taches):
    _np("PUT", "/agents/%s" % urllib.parse.quote(agent), {"tasks": taches})


def _demarrer_etape(run, plan, i, cfg):
    etape = plan["etapes"][i]
    engagees = P.sondes_etape(etape, cfg["sondes"])
    ajout = P.taches_banc(etape, cfg, run["id"])
    erreurs = []
    for agent in set(run.get("engagees") or []) - set(engagees):   # sondes qui sortent du banc à cette étape
        try:
            _poser(agent, P.restaurer(_taches(agent)))
        except Exception as e:  # noqa: BLE001
            erreurs.append("%s : %s" % (agent, str(e)[:80]))
    for agent in engagees:
        try:
            _poser(agent, P.fusionner(_taches(agent), ajout))
        except Exception as e:  # noqa: BLE001
            erreurs.append("%s : %s" % (agent, str(e)[:80]))
    run["engagees"] = engagees
    run["etape"] = i
    run["etapes"].append({"nom": etape["nom"], "duree_min": etape["duree_min"], "debut": int(time.time()), "fin": None, "sondes": engagees,
                          "taches": len(ajout), "erreurs": erreurs})
    journal("banc-etape", "Banc « %s » : étape « %s », %d sonde(s), %d tâche(s)%s" % (run["nom"], etape["nom"], len(engagees), len(ajout),
                                                                                    " ; erreurs : " + "; ".join(erreurs) if erreurs else ""), run=run["id"])


def lancer(plan_id, origine="manuel", par=None):
    with _verrou:
        if _run_en_cours():
            return None, "un banc est déjà en cours"
        plan = next((p for p in _plans() if p["id"] == plan_id), None)
        if not plan:
            return None, "banc inconnu"
        cfg = reglages()
        manque = P.manquants(plan, cfg)
        if manque:
            return None, "réglages manquants : %s" % ", ".join(manque)
        run = {"id": "r%d" % int(time.time() * 1000), "plan_id": plan_id, "nom": plan["nom"], "statut": "en_cours", "debut": int(time.time()),
               "origine": origine, "par": par, "etape": -1, "etapes": [], "engagees": [], "objectifs": plan.get("objectifs") or {},
               "arret_si_panne": plan.get("arret_si_panne", True)}
        journal("banc-lance", "Banc « %s » lancé (%s)" % (plan["nom"], origine), run=run["id"])
        _demarrer_etape(run, plan, 0, cfg)
        _sauver_run(run)
        return run, None


def terminer(run, statut, motif=""):
    with _verrou:
        now = int(time.time())
        if run["etapes"] and not run["etapes"][-1].get("fin"):
            run["etapes"][-1]["fin"] = now
        for agent in run.get("engagees") or []:
            try:
                _poser(agent, P.restaurer(_taches(agent)))
            except Exception as e:  # noqa: BLE001
                journal("banc-erreur", "restauration de %s impossible : %s" % (agent, str(e)[:120]), run=run["id"])
        mesures = []
        since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(run["debut"] - 5))
        for agent in sorted({a for e in run["etapes"] for a in e.get("sondes") or []}):
            try:
                mesures += [dict(m, agent_id=agent) for m in (_np("GET", "/agents/%s/measurements?limit=2000&since=%s" % (
                    urllib.parse.quote(agent), urllib.parse.quote(since))).get("measurements") or [])]
            except Exception as e:  # noqa: BLE001
                journal("banc-erreur", "mesures de %s illisibles : %s" % (agent, str(e)[:120]), run=run["id"])
        run.update(statut=statut, fin=now, motif=motif, engagees=[], synthese=P.synthese(run, mesures, run.get("objectifs")))
        _sauver_run(run)
        v = run["synthese"]["reussi"]
        texte = "Banc « %s » %s%s : %s" % (run["nom"], {"termine": "terminé", "arrete": "arrêté"}.get(statut, statut), (" (%s)" % motif) if motif else "",
                                          "objectifs atteints" if v else "objectifs NON atteints" if v is False else "sans objectif mesurable")
        journal("banc-fin", texte, run=run["id"])
        corps = texte + "\n\n" + "\n".join("  %s %s : %s (seuil %s)" % ("✓" if x["ok"] else "✗" if x["ok"] is False else "?", x["objectif"], x["mesure"], x["seuil"])
                                            for x in run["synthese"]["verdicts"]) + "\n\nDétail : tuile Nebula, onglet Pilotage."
        _notifier(texte, corps)
        return run


def avancer(hist):
    run = _run_en_cours()
    if not run:
        return
    plan = next((p for p in _plans() if p["id"] == run["plan_id"]), None)
    if not plan:
        terminer(run, "arrete", "banc supprimé")
        return
    der = (hist[-1]["valeurs"] if hist else {}).get("veille.niveau", {}).get("campus")
    if run.get("arret_si_panne") and der is not None and der >= 2:
        terminer(run, "arrete", "panne du réseau détectée par la veille")
        return
    e = run["etapes"][-1]
    now = int(time.time())
    if now >= e["debut"] + e["duree_min"] * 60:
        e["fin"] = now
        pts = [x for x in hist if e["debut"] <= x["at"] <= now]
        e["nebula_simultanes_max"] = max([v for x in pts for v in (x["valeurs"].get("borne.simultanes") or {}).values()] or [None], key=lambda v: -1 if v is None else v)
        if run["etape"] + 1 < len(plan["etapes"]):
            with _verrou:
                _demarrer_etape(run, plan, run["etape"] + 1, reglages())
                _sauver_run(run)
        else:
            terminer(run, "termine")
    else:
        _sauver_run(run)


# -- boucles ---------------------------------------------------------------------------------------------------------
def _boucles():
    return _kv("pilotage_boucles", [])


def evaluer_boucles(hist):
    etats, recos = _kv("pilotage_etats", {}), _kv("pilotage_recos", {})
    plans_ids = {p["id"] for p in _plans()}
    for b in _boucles():
        viol = P.violations(b["condition"], hist) if b.get("actif") else []
        ev, etats[b["id"]] = P.decider(b, viol, etats.get(b["id"]))
        if ev == "declenche":
            faits = []
            for a in P.actions_a_faire(b, viol, plans_ids):
                if a["type"] == "notifier":
                    faits.append("notification : " + _notifier("Pilotage : %s" % b["nom"], "%s\n\nValeurs : %s\nMode : %s\n\nTuile Nebula, onglet Pilotage." % (
                        b.get("description") or b["nom"], a["detail"], b["mode"])))
                elif a["type"] == "recommander":
                    recos[b["id"]] = {"boucle": b["nom"], "outil": a["outil"], "detail": a["detail"], "at": int(time.time())}
                    faits.append("recommandation : %s" % a["outil"])
                elif a["type"] == "banc":
                    if a["lancer"]:
                        run, err = lancer(a["plan"], origine="boucle « %s »" % b["nom"])
                        faits.append("banc %s : %s" % (a["plan"], "lancé" if run else err))
                    else:
                        recos[b["id"] + ":banc"] = {"boucle": b["nom"], "banc": a["plan"], "detail": a["detail"], "at": int(time.time())}
                        faits.append("banc %s proposé" % a["plan"])
            journal("boucle-declenchee", "%s (%s) : %s" % (b["nom"], b["mode"], "; ".join(faits)), boucle=b["id"])
        elif ev == "retour":
            recos.pop(b["id"], None)
            recos.pop(b["id"] + ":banc", None)
            journal("boucle-retour", "%s : retour à la normale" % b["nom"], boucle=b["id"])
    rr.kv_set("pilotage_etats", etats)
    rr.kv_set("pilotage_recos", recos)


def passage():
    inst, errs, _c, _v = releve()
    _hist_ajouter(inst)
    hist = historique()
    try:
        avancer(hist)
    except Exception as e:  # noqa: BLE001
        journal("banc-erreur", "avancement du banc : %s" % str(e)[:160])
    evaluer_boucles(hist)
    rr.kv_set("pilotage_dernier", {"at": inst["at"], "erreurs": errs})
    return inst, errs


def _boucle(lock_dir):
    import fcntl
    try:
        fh = open(os.path.join(lock_dir, "nebula-pilotage.lock"), "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    time.sleep(60)
    while True:
        try:
            passage()
        except Exception as e:  # noqa: BLE001 -- le pilotage ne meurt jamais
            try:
                journal("erreur", "passage en échec : %s" % str(e)[:160])
            except Exception:  # noqa: BLE001
                pass
        time.sleep(max(30, int(reglages().get("periode_s") or 60)))


# -- routes ----------------------------------------------------------------------------------------------------------
def register(app, hooks, start_loop=True):
    """hooks : sites(), charge(site_id), veille(), conn(), manage(body) -> (ok, err), notify(action, sujet, corps), lock_dir."""
    _hooks.update(hooks)

    def _droit():
        body = request.get_json(silent=True) or {}
        ok, err = _hooks["manage"](body)
        return body, (None if ok else (jsonify({"error": err or "droit insuffisant"}), 403))

    @app.route("/pilotage/tableau", methods=["GET"])
    def pilotage_tableau():
        hist = historique()
        dernier = hist[-1] if hist else None
        series = {}
        for m in ("borne.simultanes", "sonde.rtt_ms", "sonde.perte_udp_pct", "sonde.gigue_ms", "sonde.rssi_dbm", "site.clients_wifi"):
            for cible in ((dernier or {}).get("valeurs") or {}).get(m, {}):
                series.setdefault(m, {})[cible] = P.serie(hist[-120:], m, cible)
        runs = _runs()
        return jsonify({"dernier": dernier, "series": series, "etat": _kv("pilotage_dernier", {}), "boucles": _boucles(), "etats": _kv("pilotage_etats", {}),
                        "recommandations": _kv("pilotage_recos", {}), "run": _run_en_cours(),
                        "runs": [{k: r.get(k) for k in ("id", "nom", "statut", "debut", "fin", "origine", "motif")} | {"reussi": (r.get("synthese") or {}).get("reussi")}
                                 for r in reversed(runs[-10:])],
                        "journal": list(reversed(_kv("pilotage_journal", [])[-40:])), "reglages": reglages()}), 200

    @app.route("/pilotage/catalogue", methods=["GET"])
    def pilotage_catalogue():
        b_sc = {b.get("scenario") for b in _boucles()}
        p_ids = {p["id"] for p in _plans()}
        return jsonify({"outils": P.OUTILS, "metriques": P.METRIQUES, "plafonds": P.PLAFONDS, "plans": _plans(),
                        "scenarios": [dict(s, installe=(s["id"] in b_sc or (not s["boucles"] and all(p in p_ids for p in s["plans"])))) for s in P.SCENARIOS]}), 200

    @app.route("/pilotage/sondes", methods=["GET"])
    def pilotage_sondes():
        s, err = sondes_netprobe()
        return jsonify({"sondes": s, "erreur": err}), 200

    @app.route("/pilotage/reglages", methods=["PUT"])
    def pilotage_reglages():
        body, refus = _droit()
        if refus:
            return refus
        r = body.get("reglages") or {}
        cfg = reglages()
        cfg.update({"site_id": r.get("site_id") or None, "sondes": [str(x)[:64] for x in r.get("sondes") or []][:40],
                    "serveur_iperf": str(r.get("serveur_iperf") or "").strip()[:120], "cible_ping": str(r.get("cible_ping") or "").strip()[:120],
                    "urls": [u.strip()[:300] for u in r.get("urls") or [] if str(u).strip().startswith(("http://", "https://"))][:10]})
        rr.kv_set("pilotage_reglages", cfg)
        journal("reglages", "réglages enregistrés par %s" % (body.get("user") or "?"))
        return jsonify({"reglages": cfg}), 200

    @app.route("/pilotage/boucles", methods=["POST"])
    def pilotage_boucle_creer():
        body, refus = _droit()
        if refus:
            return refus
        with _verrou:
            b, err = P.valider_boucle(body.get("boucle"), {p["id"] for p in _plans()})
            if err:
                return jsonify({"error": err}), 400
            b["id"] = "b%d" % int(time.time() * 1000)
            rr.kv_set("pilotage_boucles", _boucles() + [b])
        journal("boucle-creee", "boucle « %s » créée par %s" % (b["nom"], body.get("user") or "?"), boucle=b["id"])
        return jsonify(b), 201

    @app.route("/pilotage/boucles/<bid>", methods=["PUT", "DELETE"])
    def pilotage_boucle(bid):
        body, refus = _droit()
        if refus:
            return refus
        with _verrou:
            lst = _boucles()
            old = next((b for b in lst if b["id"] == bid), None)
            if not old:
                return jsonify({"error": "boucle inconnue"}), 404
            if request.method == "DELETE":
                rr.kv_set("pilotage_boucles", [b for b in lst if b["id"] != bid])
                journal("boucle-supprimee", "boucle « %s » supprimée par %s" % (old["nom"], body.get("user") or "?"), boucle=bid)
                return jsonify({"ok": True}), 200
            b, err = P.valider_boucle(dict(old, **(body.get("boucle") or {})), {p["id"] for p in _plans()})
            if err:
                return jsonify({"error": err}), 400
            b["id"] = bid
            rr.kv_set("pilotage_boucles", [b if x["id"] == bid else x for x in lst])
        journal("boucle-modifiee", "boucle « %s » modifiée par %s" % (b["nom"], body.get("user") or "?"), boucle=bid)
        return jsonify(b), 200

    @app.route("/pilotage/boucles/<bid>/basculer", methods=["POST"])
    def pilotage_boucle_basculer(bid):
        """À chaud : actif / mode, pris en compte au passage suivant (moins d'une minute)."""
        body, refus = _droit()
        if refus:
            return refus
        with _verrou:
            lst = _boucles()
            b = next((x for x in lst if x["id"] == bid), None)
            if not b:
                return jsonify({"error": "boucle inconnue"}), 404
            if "actif" in body:
                b["actif"] = bool(body["actif"])
            if body.get("mode") in P.MODES:
                b["mode"] = body["mode"]
            rr.kv_set("pilotage_boucles", lst)
        journal("boucle-basculee", "« %s » : %s, mode %s (%s)" % (b["nom"], "active" if b["actif"] else "inactive", b["mode"], body.get("user") or "?"), boucle=bid)
        return jsonify(b), 200

    @app.route("/pilotage/scenarios/<sid>/installer", methods=["POST"])
    def pilotage_scenario(sid):
        body, refus = _droit()
        if refus:
            return refus
        with _verrou:
            boucles, plans, ajouts = P.installer_scenario(sid, _boucles(), _plans())
            if ajouts is None:
                return jsonify({"error": "scénario inconnu"}), 404
            rr.kv_set("pilotage_boucles", boucles)
            rr.kv_set("pilotage_plans", plans)
        journal("scenario", "scénario %s installé par %s : %s" % (sid, body.get("user") or "?", ajouts))
        return jsonify(ajouts), 200

    @app.route("/pilotage/plans", methods=["POST"])
    def pilotage_plan_creer():
        body, refus = _droit()
        if refus:
            return refus
        p, err = P.valider_plan(body.get("plan"))
        if err:
            return jsonify({"error": err}), 400
        with _verrou:
            rr.kv_set("pilotage_plans", [x for x in _plans() if x["id"] != p["id"]] + [p])
        journal("banc-enregistre", "banc « %s » enregistré par %s" % (p["nom"], body.get("user") or "?"))
        return jsonify(p), 201

    @app.route("/pilotage/plans/<pid>", methods=["DELETE"])
    def pilotage_plan_supprimer(pid):
        body, refus = _droit()
        if refus:
            return refus
        r = _run_en_cours()
        if r and r["plan_id"] == pid:
            return jsonify({"error": "banc en cours : l'arrêter d'abord"}), 409
        with _verrou:
            rr.kv_set("pilotage_plans", [x for x in _plans() if x["id"] != pid])
        return jsonify({"ok": True}), 200

    @app.route("/pilotage/plans/<pid>/lancer", methods=["POST"])
    def pilotage_lancer(pid):
        body, refus = _droit()
        if refus:
            return refus
        run, err = lancer(pid, "manuel", body.get("user"))
        if err:
            return jsonify({"error": err}), 409
        return jsonify(run), 200

    @app.route("/pilotage/runs/arreter", methods=["POST"])
    def pilotage_arreter():
        body, refus = _droit()
        if refus:
            return refus
        run = _run_en_cours()
        if not run:
            return jsonify({"error": "aucun banc en cours"}), 404
        return jsonify(terminer(run, "arrete", "arrêté par %s" % (body.get("user") or "?"))), 200

    @app.route("/pilotage/runs/<rid>", methods=["GET"])
    def pilotage_run(rid):
        r = next((x for x in _runs() if x["id"] == rid), None)
        return (jsonify(r), 200) if r else (jsonify({"error": "exécution inconnue"}), 404)

    @app.route("/pilotage/recommandations/<rid>/acquitter", methods=["POST"])
    def pilotage_acquitter(rid):
        body, refus = _droit()
        if refus:
            return refus
        recos = _kv("pilotage_recos", {})
        if recos.pop(rid, None):
            rr.kv_set("pilotage_recos", recos)
            journal("recommandation-acquittee", "recommandation %s acquittée par %s" % (rid, body.get("user") or "?"))
        return jsonify({"ok": True}), 200

    @app.route("/pilotage/passer", methods=["POST"])
    def pilotage_passer():
        inst, errs = passage()
        return jsonify({"at": inst["at"], "erreurs": errs}), 200

    try:
        import notify_client
        notify_client.register_actions(ACTIONS)
    except Exception:  # noqa: BLE001
        pass
    if start_loop:
        threading.Thread(target=_boucle, args=(hooks["lock_dir"],), name="nebula-pilotage", daemon=True).start()
