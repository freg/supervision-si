# -*- coding: utf-8 -*-
"""Veille de santé du réseau du campus (livraison #847) : routes, passage périodique et alertes.

- GET  /veille              : état courant (évalué au plus toutes les 30 s), vérifications, suivi des alertes ;
- GET  /veille/etat         : « OK … » (200) ou « PANNE … » / « DEGRADE … » (503), texte court pour un veilleur
                              extérieur (si-veille) ; jeton `?jeton=` exigé si NEBULA_VEILLE_TOKEN est réglé ;
- GET/PUT /veille/reglages  : agents internes, VLAN suivis (connexion / sous-réseau, DHCP attendus, créneaux d'usage),
                              postes suivis, heures ouvrées, alerte (délai, rappel, retour à la normale) ;
- POST /veille/passer       : passage immédiat.
Alertes par notify-api : « nebula.veille-campus » (usage interne) et « nebula.veille-campus-externe » (créneau d'un
organisme extérieur : destinataires distincts réglés dans la tuile Notifications), retour à la normale.
Logique pure : veille.py."""
import hmac
import json
import os
import threading
import time
import urllib.request
from datetime import datetime

from flask import jsonify, request

import alerting
import report_routes as rr
import veille

ACTIONS = [{"id": "nebula.veille-campus", "label": "Veille du réseau du campus : panne (usage interne)", "severity": "critical"},
           {"id": "nebula.veille-campus-externe", "label": "Veille du réseau du campus : panne pendant un créneau d'organisme extérieur", "severity": "warning"},
           {"id": "nebula.veille-campus-retabli", "label": "Veille du réseau du campus : retour à la normale", "severity": "info"}]
SI_AGENT_API_URL = os.environ.get("SI_AGENT_API_URL", "http://si-agent-api:5000").rstrip("/")
_hooks = {}
_cache = {"at": 0, "res": None}
_clients = {"at": 0, "site": None, "items": None}
_verrou = threading.Lock()


def reglages():
    return veille.normalize(rr.kv_get("veille_reglages", {}))[0]


def _get(url, timeout=8):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as r:
        return json.loads(r.read(20_000_000).decode("utf-8", "replace"))


def _agents(cfg):
    """Agents internes : ceux listés, plus ceux du site choisi ; avec leurs dernières mesures."""
    if not cfg["agents"] and not cfg["agent_site"]:
        return [], None
    try:
        lst = _get(SI_AGENT_API_URL + "/agents").get("agents") or []
    except Exception as e:  # noqa: BLE001
        return [], "agents hôtes injoignables : %s" % str(e)[:120]
    out = []
    for a in lst:
        if a.get("agent_id") in cfg["agents"] or (cfg["agent_site"] and a.get("site") == cfg["agent_site"]):
            try:
                latest = _get("%s/agents/%s/latest" % (SI_AGENT_API_URL, a["agent_id"])).get("latest") or {}
            except Exception:  # noqa: BLE001
                latest = {}
            out.append({"agent_id": a["agent_id"], "hostname": a.get("hostname"), "site": a.get("site"),
                        "last_seen_at": a.get("last_seen_at"), "latest": {k: v for k, v in latest.items() if k in ("plugin:path-probe", "plugin:broadcast-probe")}})
    return out, None


def _site(cfg):
    sites = _hooks["sites"]() or []
    s = next((x for x in sites if x.get("siteId") == cfg["site_id"]), None) or (sites[0] if sites else None)
    return (s.get("siteId"), s.get("name") or s.get("siteId")) if s else (None, None)


def entrees(cfg):
    errs = []
    try:
        site_id, site = _site(cfg)
    except Exception as e:  # noqa: BLE001 -- clé absente, Nebula injoignable : la veille continue avec les agents
        site_id, site, errs = None, None, ["Nebula : %s" % str(e)[:160]]
    neb = {"ok": site_id is not None, "erreur": errs[0] if errs else "aucun site Nebula", "devices": []}
    clients = None
    if site_id:
        try:
            neb["devices"] = _hooks["board"](site_id)
        except Exception as e:  # noqa: BLE001
            neb.update(ok=False, erreur="santé Nebula : %s" % str(e)[:160])
        if cfg["postes"]:
            if _clients["site"] != site_id or time.time() - _clients["at"] > 600:   # clients : coûteux, au plus toutes les 10 min
                try:
                    _clients.update(at=time.time(), site=site_id, items=_hooks["clients"](site_id))
                except Exception as e:  # noqa: BLE001
                    errs.append("clients Nebula : %s" % str(e)[:120])
            clients = _clients["items"]
    agents, err = _agents(cfg)
    if err:
        errs.append(err)
    return {"nebula": neb, "agents": agents, "clients": clients}, site_id or "campus", site or "Campus", errs


def evaluer(force=False):
    with _verrou:
        if not force and _cache["res"] and time.time() - _cache["at"] < 30:
            return _cache["res"]
        cfg = reglages()
        e, site_id, site, errs = entrees(cfg)
        res = veille.evaluer(cfg, e)
        res.update(site_id=site_id, site=site, erreurs=errs)
        _cache.update(at=time.time(), res=res)
        return res


def passage(now=None):
    """Évaluation + suivi des alertes (délai avant alerte, rappel, retour à la normale)."""
    cfg = reglages()
    res = evaluer(force=True)
    if not cfg["enabled"]:
        return res
    now = now or time.time()
    al = dict(cfg["alerte"], min_severity=cfg["alerte"]["min_severity"])
    state, urgentes, retablies = alerting.track(rr.kv_get("veille_state", {}), veille.lignes_alerte(res, res["site_id"], res["site"]), now, al)
    rr.kv_set("veille_state", state)
    for usage, action, sev in (("interne", "nebula.veille-campus", "critical"), ("externe", "nebula.veille-campus-externe", "warning")):
        sel = [u for u in urgentes if (u.get("kind") or "interne") == usage]
        if sel:
            corps = "%s\n\n%s\n\nDétail dans le hub : tuile Nebula, onglet Veille.\n" % (res["resume"], "\n".join(
                "  ✗ %s — %s (depuis le %s)" % (u["element"], u["message"], datetime.fromtimestamp(u["first_seen"]).strftime("%d/%m %H:%M")) for u in sel))
            r = rr._notify(action, "Réseau du campus%s : %s" % (" (créneau extérieur)" if usage == "externe" else "", ", ".join(u["element"] for u in sel)[:150]),
                           corps, rr.settings(), severity=sev)
            rr.log("veille-" + usage, "%d alerte(s) : %s" % (len(sel), rr._res_text(r)))
    if retablies:
        corps = "Retour à la normale :\n\n" + "\n".join("  ✓ %s — %s" % (e.get("element"), e.get("message")) for e in retablies)
        r = rr._notify("nebula.veille-campus-retabli", "Réseau du campus : %d vérification(s) rétablie(s)" % len(retablies), corps, rr.settings(), severity="info")
        rr.log("veille-retabli", "%d : %s" % (len(retablies), rr._res_text(r)))
    return res


def _boucle(lock_dir):
    import fcntl
    try:
        fh = open(os.path.join(lock_dir, "nebula-veille.lock"), "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    time.sleep(45)
    while True:
        try:
            passage()
        except Exception as e:  # noqa: BLE001 -- la veille ne meurt jamais
            try:
                rr.log("veille-erreur", "passage en échec : %s" % e)
            except Exception:  # noqa: BLE001
                pass
        try:
            time.sleep(reglages()["periode_s"])
        except Exception:  # noqa: BLE001
            time.sleep(120)


def register(app, hooks, start_loop=True):
    """hooks : sites() ; board(site_id) -> [{dev_id, name, type, status, since}] ; clients(site_id) -> [{mac, ip, status}] ;
    manage(body) -> (ok, err) ; lock_dir. Le stockage (clé-valeur) et l'envoi sont ceux de report_routes."""
    _hooks.clear(); _hooks.update(hooks)

    @app.route("/veille", methods=["GET"])
    def veille_get():
        res = evaluer(force=request.args.get("refresh") == "1")
        state = rr.kv_get("veille_state", {})
        return jsonify(dict(res, suivi=sorted((state.get("open") or {}).values(), key=lambda e: e.get("first_seen", 0)),
                            retablies_24h=alerting.resolved_since(state, time.time() - 86400)[-30:], reglages=reglages())), 200

    @app.route("/veille/etat", methods=["GET"])
    def veille_etat():
        jeton = os.environ.get("NEBULA_VEILLE_TOKEN", "")
        if jeton and not hmac.compare_digest(request.args.get("jeton", ""), jeton):
            return "jeton requis\n", 401, {"Content-Type": "text/plain; charset=utf-8"}
        res = evaluer()
        code = 200 if res["etat"] in ("ok", "inconnu") else 503
        return "%s %s\n" % ({"ok": "OK", "inconnu": "INCONNU", "degrade": "DEGRADE", "panne": "PANNE"}[res["etat"]], res["resume"]), code, \
            {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}

    @app.route("/veille/reglages", methods=["GET"])
    def veille_reglages_get():
        return jsonify({"reglages": reglages(), "defaut": veille.DEFAUT}), 200

    @app.route("/veille/reglages", methods=["PUT"])
    def veille_reglages_put():
        body = request.get_json(silent=True) or {}
        ok, err = hooks["manage"](body)
        if not ok:
            return jsonify({"error": err}), 403
        cfg, errs = veille.normalize(body.get("reglages") or {})
        if errs:
            return jsonify({"error": " ; ".join(errs), "erreurs": errs}), 400
        rr.kv_set("veille_reglages", cfg)
        rr.log("veille-reglages", "réglages de la veille enregistrés par %s" % (body.get("user") or "?"))
        return jsonify({"reglages": cfg, "resultat": evaluer(force=True)}), 200

    @app.route("/veille/suggestions", methods=["GET"])
    def veille_suggestions():
        """Pré-remplissage : carte des VLAN, fiches Matériels, agents (aucun enregistrement)."""
        cfg, errs = reglages(), []
        vmap = assets = agents = None
        try:
            site_id = _site(cfg)[0]
            vmap = hooks["vlanmap"](site_id) if site_id else None
        except Exception as e:  # noqa: BLE001
            errs.append("carte des VLAN : %s" % str(e)[:160])
        try:
            assets = hooks["assets"]()
        except Exception as e:  # noqa: BLE001
            errs.append("fiches du campus : %s" % str(e)[:160])
        try:
            agents = _get(SI_AGENT_API_URL + "/agents").get("agents") or []
        except Exception as e:  # noqa: BLE001
            errs.append("agents : %s" % str(e)[:160])
        return jsonify(dict(veille.suggestions(vmap, assets, agents, cfg["agent_site"]), erreurs=errs)), 200

    @app.route("/veille/passer", methods=["POST"])
    def veille_passer():
        return jsonify(passage()), 200

    try:
        import notify_client
        notify_client.register_actions(ACTIONS)
    except Exception:  # noqa: BLE001 -- notify-api absent : la veille reste consultable
        pass
    if start_loop:
        threading.Thread(target=_boucle, args=(hooks["lock_dir"],), name="nebula-veille", daemon=True).start()
