# -*- coding: utf-8 -*-
"""Historique des clients Nebula (livraison #872) : relève horaire, relève immédiate, requête filtrée et triée.

- GET  /client-history                  : ?site= &q= &manufacturer= &device= &since= &until= &absent_since= (epoch s)
                                          &sort=last_seen|first_seen|mac|ip|name|manufacturer|device|seen_count &order=asc|desc
                                          &limit= &offset=  -> {total, rows}
- GET  /client-history/sessions         : ?site= &mac=  -> périodes de présence (raccordement : IP, équipement, port, SSID, VLAN)
- GET  /client-history/manufacturers    : ?site=  -> fabricants vus (liste du filtre)
- GET  /client-history/status           : dernières relèves, fréquence, prochaine relève
- POST /client-history/poll             : relève immédiate (au plus une par minute)
- GET  /client-history/export.csv       : mêmes filtres, 20 000 lignes max
Logique : client_history.py. Appels Nebula : v2 clients, v2 ap-clients, v2 sw-clients, période 2 h."""
import csv
import io
import json
import os
import threading
import time
import traceback

from flask import Response, jsonify, request

import client_history as ch

INTERVAL_S = int(os.environ.get("NEBULA_CLIENT_HISTORY_SECONDS", "3600"))
MIN_GAP_S = 60
_etat = {"running": False, "last": 0, "next": 0, "echecs": {}}
LIEN = {"view": "nebula", "tab": "historique"}
SEUIL_INJOIGNABLE = 3     # relèves consécutives sans aucune source Nebula avant de signaler un défaut majeur
_verrou = threading.Lock()


def relever(deps, trigger="horaire", now=None):
    """Une relève de tous les sites -> [{site, clients, sources, error}]. Un échec de source n'empêche pas les autres."""
    if not _verrou.acquire(blocking=False):
        return {"busy": True}
    _etat["running"] = True
    out = []
    try:
        client = deps["client"]()
        for site in deps["sites"]():
            sid = site.get("siteId") or site.get("id")
            t0 = time.time()
            res, errs = {}, []
            # #974 : première relève réussie du site -> on reprend les 24 h que Nebula garde encore
            conn = deps["conn"]()
            try:
                ch.ensure_columns(conn)
                deja = conn.execute("SELECT 1 FROM nebula_client_polls WHERE site_id = ? AND clients IS NOT NULL LIMIT 1", (sid,)).fetchone()
            finally:
                conn.close()
            periode = "2h" if deja else "1d"
            for nom, fn in (("clients", lambda: client.get_site_clients(sid, period=periode)),
                            ("bornes", lambda: client.ap_clients_v2(sid, periode)),
                            ("commutateurs", lambda: client.sw_clients(sid, periode))):
                try:
                    r = fn()
                    res[nom] = r if isinstance(r, list) else (r or {}).get("data", []) if isinstance(r, dict) else []
                except Exception as e:  # noqa: BLE001 -- une source en échec n'empêche pas les autres
                    errs.append("%s : %s" % (nom, str(e)[:150]))
            stats, n, trace = ch.nouveautes_vides(), None, None
            conn = deps["conn"]()
            try:
                try:
                    noms = {ch.norm_nom(x) for x in (deps.get("noms_registre") or (lambda _s: []))(sid) if x}
                except Exception:  # noqa: BLE001 -- registre absent : pas de correspondances, la relève continue
                    noms = set()
                try:
                    fiches = ch.merge(res.get("clients"), res.get("bornes"), res.get("commutateurs"), deps["device_names"](sid), now=now)
                    n = ch.ingest(conn, sid, fiches, now=now, stats=stats, noms_registre=noms)
                except Exception as e:  # noqa: BLE001 -- #974 : un échec d'écriture est une relève en erreur, enregistrée (diode rouge)
                    conn.rollback()
                    errs.append("enregistrement : %s" % str(e)[:200])
                    trace = traceback.format_exc().splitlines()[-15:]
                if periode == "1d" and n is not None:
                    stats["rattrapage_24h"] = True
                conn.execute("INSERT INTO nebula_client_polls (at, site_id, clients, sources, error, duration_ms, trigger, nouveautes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             (int(now or time.time()), sid, n, ",".join(sorted(res)), "; ".join(errs) or None, int((time.time() - t0) * 1000), trigger,
                              json.dumps(stats, ensure_ascii=False)))
                conn.commit()
            finally:
                conn.close()
            _signaler(deps, sid, trigger, res, errs, n, trace)
            if n is not None and deps.get("apres_releve"):   # #1001 : liste de surveillance rapprochée de la relève
                try:
                    deps["apres_releve"](sid, int(now or time.time()))
                except Exception:  # noqa: BLE001 -- la surveillance ne casse jamais la relève
                    traceback.print_exc()
            out.append({"site": sid, "clients": n, "sources": sorted(res), "error": "; ".join(errs) or None, "nouveautes": stats.get("n") or {}})
        _etat["last"] = int(time.time())
        return {"sites": out}
    finally:
        _etat["running"] = False
        _verrou.release()


def _signaler(deps, sid, trigger, res, errs, n, trace):
    """#975 : défauts majeurs -- relève non enregistrée (immédiat), Nebula muet SEUIL_INJOIGNABLE fois de suite ; levés dès que ça remarche."""
    defaut = deps.get("defaut") or (lambda *a, **k: None)
    leve = deps.get("defaut_leve") or (lambda *a, **k: None)
    ctx = {"site": sid, "declencheur": trigger, "sources_ok": ",".join(sorted(res)) or "aucune"}
    if n is None:
        defaut("historique-clients.enregistrement", "Historique des clients Nebula : les relèves ne sont pas enregistrées",
               "La relève a interrogé Nebula mais n'a rien pu écrire dans la base : aucune donnée de clients n'est conservée "
               "tant que ce défaut dure (Nebula n'en garde que 24 h).", lien=LIEN, contexte=ctx, journal=list(errs) + list(trace or []))
    else:
        leve("historique-clients.enregistrement")
    if not res:
        _etat["echecs"][sid] = _etat["echecs"].get(sid, 0) + 1
        if _etat["echecs"][sid] >= SEUIL_INJOIGNABLE:
            defaut("historique-clients.nebula", "Historique des clients : Nebula ne répond plus",
                   "%d relèves consécutives sans aucune réponse de Nebula (clients, bornes, commutateurs)." % _etat["echecs"][sid],
                   lien=LIEN, contexte=dict(ctx, relèves_en_échec=_etat["echecs"][sid]), journal=list(errs))
    else:
        _etat["echecs"][sid] = 0
        leve("historique-clients.nebula")


def _boucle(deps, log):
    import fcntl
    try:
        fh = open(os.path.join(os.path.dirname(deps["db_path"]) or ".", "nebula-client-history.lock"), "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return      # un autre processus relève déjà
    time.sleep(90)
    jour = None
    while True:
        _etat["next"] = int(time.time()) + INTERVAL_S
        try:
            if deps["configured"]():
                relever(deps, "horaire")
            if jour != time.strftime("%Y-%m-%d"):
                jour = time.strftime("%Y-%m-%d")
                conn = deps["conn"]()
                try:
                    ch.purge(conn)
                finally:
                    conn.close()
        except Exception as e:  # noqa: BLE001 -- la relève ne meurt jamais
            log("historique des clients : %s" % e)
            (deps.get("defaut") or (lambda *a, **k: None))(
                "historique-clients.boucle", "Historique des clients Nebula : la relève horaire plante",
                "La relève horaire s'est arrêtée sur une erreur ; elle sera retentée à l'heure suivante.", lien=LIEN,
                journal=traceback.format_exc().splitlines()[-20:])
        time.sleep(max(300, INTERVAL_S))


def _filtres():
    a = request.args

    def num(k):
        v = a.get(k)
        return int(float(v)) if v not in (None, "") and str(v).replace(".", "", 1).isdigit() else None
    return {"site_id": a.get("site") or None, "q": a.get("q") or None, "manufacturer": a.get("manufacturer") or None,
            "device": a.get("device") or None, "since": num("since"), "until": num("until"), "absent_since": num("absent_since"),
            "sort": a.get("sort") or "last_seen", "order": a.get("order") or "desc"}


def register(app, deps):
    log = deps.get("log") or (lambda m: app.logger.warning(m))

    @app.route("/client-history", methods=["GET"])
    def client_history_query():
        conn = deps["conn"]()
        try:
            return jsonify(ch.query(conn, limit=request.args.get("limit", 200), offset=request.args.get("offset", 0), **_filtres())), 200
        finally:
            conn.close()

    @app.route("/client-history/sessions", methods=["GET"])
    def client_history_sessions():
        conn = deps["conn"]()
        try:
            return jsonify({"sessions": ch.sessions(conn, request.args.get("site", ""), request.args.get("mac", ""))}), 200
        finally:
            conn.close()

    @app.route("/client-history/manufacturers", methods=["GET"])
    def client_history_manufacturers():
        conn = deps["conn"]()
        try:
            return jsonify({"manufacturers": ch.manufacturers(conn, request.args.get("site") or None)}), 200
        finally:
            conn.close()

    @app.route("/client-history/status", methods=["GET"])
    def client_history_status():
        conn = deps["conn"]()
        try:
            conn.executescript(ch.SCHEMA)
            polls = [dict(zip(("at", "site_id", "clients", "sources", "error", "duration_ms", "trigger"), r)) for r in
                     conn.execute("SELECT at, site_id, clients, sources, error, duration_ms, trigger FROM nebula_client_polls ORDER BY id DESC LIMIT 20")]
            n = conn.execute("SELECT COUNT(*), MIN(first_seen) FROM nebula_client_seen").fetchone()
        finally:
            conn.close()
        return jsonify({"interval_s": INTERVAL_S, "running": _etat["running"], "next": _etat["next"] or None, "configured": deps["configured"](),
                        "clients": n[0], "depuis": n[1], "retention_days": ch.RETENTION_DAYS, "polls": polls}), 200

    @app.route("/client-history/calendar", methods=["GET"])
    def client_history_calendar():
        """#974 : relèves (une diode chacune) sur `jours` jours -> {premiere, derniere, interval_s, releves}."""
        try:
            jours = max(1, min(400, int(request.args.get("jours", 60))))
        except ValueError:
            jours = 60
        conn = deps["conn"]()
        try:
            rel = ch.calendrier(conn, request.args.get("site") or None, int(time.time()) - jours * 86400)
            prem = conn.execute("SELECT MIN(at) FROM nebula_client_polls" + (" WHERE site_id = ?" if request.args.get("site") else ""),
                                ((request.args.get("site"),) if request.args.get("site") else ())).fetchone()[0]
        finally:
            conn.close()
        return jsonify({"jours": jours, "premiere": prem, "derniere": rel[-1]["at"] if rel else None, "interval_s": INTERVAL_S, "releves": rel}), 200

    @app.route("/client-history/poll/<int:pid>", methods=["GET"])
    def client_history_poll_detail(pid):
        """#974 : détail d'une relève (nouveautés : listes limitées à 40 par catégorie, comptes complets)."""
        conn = deps["conn"]()
        try:
            ch.ensure_columns(conn)
            r = conn.execute("SELECT id, at, site_id, clients, sources, error, duration_ms, trigger, nouveautes FROM nebula_client_polls WHERE id = ?", (pid,)).fetchone()
        finally:
            conn.close()
        if not r:
            return jsonify({"error": "relève inconnue : %s" % pid}), 404
        try:
            nv = json.loads(r[8]) if r[8] else {}
        except ValueError:
            nv = {}
        return jsonify({"id": r[0], "at": r[1], "site_id": r[2], "clients": r[3], "sources": r[4], "error": r[5], "duration_ms": r[6],
                        "trigger": r[7], "etat": ch.etat_releve(r[5], r[3], nv), "nouveautes": nv}), 200

    @app.route("/client-history/poll", methods=["POST"])
    def client_history_poll():
        if not deps["configured"]():
            return jsonify({"error": "NEBULA_API_KEY non configuré"}), 503
        if _etat["running"] or time.time() - _etat["last"] < MIN_GAP_S:
            return jsonify({"error": "relève déjà en cours ou faite il y a moins d'une minute", "busy": True}), 429
        r = relever(deps, "à la demande")
        return (jsonify({"error": "relève déjà en cours", "busy": True}), 429) if r.get("busy") else (jsonify(r), 200)

    @app.route("/client-history/export.csv", methods=["GET"])
    def client_history_export():
        conn = deps["conn"]()
        try:
            r = ch.query(conn, limit=2000, offset=0, **_filtres())
            rows, off = list(r["rows"]), 2000
            while off < min(r["total"], 20000):
                rows += ch.query(conn, limit=2000, offset=off, **_filtres())["rows"]
                off += 2000
        finally:
            conn.close()
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        cols = ["site_id", "mac", "ip", "name", "manufacturer", "os", "device", "port", "ssid", "vlan", "first_seen", "last_seen", "seen_count", "sources"]
        w.writerow(cols)
        fmt = lambda v: time.strftime("%Y-%m-%d %H:%M", time.localtime(v)) if isinstance(v, int) else v
        for x in rows:
            w.writerow([fmt(x[c]) if c in ("first_seen", "last_seen") else x.get(c) for c in cols])
        return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=historique-clients-nebula.csv"})

    if INTERVAL_S > 0 and os.environ.get("NEBULA_POLL_DISABLED") != "1":
        threading.Thread(target=_boucle, args=(deps, log), name="nebula-client-history", daemon=True).start()
