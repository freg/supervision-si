"""Routes de l'audit de sécurité réseau (#958) -- voir audit_securite.py pour la logique.

GET  /sites/<s>/audit                      constats cotés + matrice + préconisations (dernière collecte en base)
POST /sites/<s>/audit/collecter            relève Nebula (API) + historiques accumulés, mémorise la collecte
POST /sites/<s>/audit/importer             {source: proxmox|hote|manuel, donnees: {...}} (sortie des scripts tools/audit-*.sh, ou constat saisi)
GET  /sites/<s>/audit/collectes            liste des collectes mémorisées (source, date, taille)
DELETE /sites/<s>/audit/collectes/<id>
PUT  /sites/<s>/audit/constats/<id>        {etat, probabilite, impact, note} : cotation / suivi
GET  /sites/<s>/audit/reglages  PUT        {vlans_serveurs[], vlans_iot[]}
GET  /sites/<s>/audit.md  /audit.csv       exports
Aucune donnée de site dans le code ; les collectes vivent en base (hors dépôt).
"""
import json
import time

from flask import jsonify, request, Response

import audit_securite as lib

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_collectes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, source TEXT NOT NULL, at INTEGER NOT NULL, libelle TEXT, donnees TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_audit_collectes_site ON audit_collectes (site_id, source, at);
CREATE TABLE IF NOT EXISTS audit_constats (
    site_id TEXT NOT NULL, constat_id TEXT NOT NULL, etat TEXT, probabilite INTEGER, impact INTEGER, note TEXT, updated_at INTEGER NOT NULL,
    PRIMARY KEY (site_id, constat_id));
CREATE TABLE IF NOT EXISTS audit_reglages (site_id TEXT PRIMARY KEY, donnees TEXT NOT NULL);
"""


def register(app, hooks):
    conn_fn, connect = hooks["conn"], hooks["client"]
    devices_of = hooks.get("devices") or (lambda sid: [])
    sites_fn = hooks.get("sites") or (lambda: [])
    vlan_map = hooks.get("vlan_map") or (lambda sid: {})
    anomalies_fn = hooks.get("anomalies") or (lambda sid: [])
    org_of = hooks.get("org_of") or (lambda sid: (None, None))

    conn = conn_fn()
    try:
        conn.executescript(SCHEMA); conn.commit()
    finally:
        conn.close()

    def _site_nom(sid):
        return next((s.get("name") for s in sites_fn() if s.get("siteId") == sid), sid)

    def _enregistrer(sid, source, donnees, libelle=None, remplacer=True):
        conn = conn_fn()
        try:
            if remplacer:
                conn.execute("DELETE FROM audit_collectes WHERE site_id = ? AND source = ? AND (libelle = ? OR (libelle IS NULL AND ? IS NULL))", (sid, source, libelle, libelle))
            conn.execute("INSERT INTO audit_collectes (site_id, source, at, libelle, donnees) VALUES (?, ?, ?, ?, ?)", (sid, source, int(time.time()), libelle, json.dumps(donnees)))
            conn.commit()
        finally:
            conn.close()

    def _collectes(sid):
        conn = conn_fn()
        try:
            rows = conn.execute("SELECT id, source, at, libelle, donnees FROM audit_collectes WHERE site_id = ? ORDER BY at", (sid,)).fetchall()
        finally:
            conn.close()
        return [{"id": r["id"], "source": r["source"], "at": r["at"], "libelle": r["libelle"], "donnees": json.loads(r["donnees"])} for r in rows]

    def _etats(sid):
        conn = conn_fn()
        try:
            rows = conn.execute("SELECT constat_id, etat, probabilite, impact, note FROM audit_constats WHERE site_id = ?", (sid,)).fetchall()
        finally:
            conn.close()
        return {r["constat_id"]: {"etat": r["etat"], "probabilite": r["probabilite"], "impact": r["impact"], "note": r["note"]} for r in rows}

    def _reglages(sid):
        conn = conn_fn()
        try:
            r = conn.execute("SELECT donnees FROM audit_reglages WHERE site_id = ?", (sid,)).fetchone()
        finally:
            conn.close()
        return json.loads(r["donnees"]) if r else {"vlans_serveurs": [], "vlans_iot": []}

    def _assembler(sid):
        col = {"nebula": {}, "historiques": {}, "proxmox": [], "hotes": [], "manuels": []}
        sources = []
        for c in _collectes(sid):
            d = c["donnees"]
            if c["source"] == "nebula":
                col["nebula"] = d
            elif c["source"] == "historiques":
                col["historiques"] = d
            elif c["source"] == "proxmox":
                col["proxmox"].append(d)
            elif c["source"] == "hote":
                col["hotes"].append(d)
            elif c["source"] == "manuel":
                col["manuels"].append(d)
            sources.append({"id": c["id"], "source": c["source"], "at": c["at"], "libelle": c["libelle"] or (d.get("hostname") or d.get("nom") or d.get("titre") or ""),
                            "erreurs": (d.get("erreurs") if isinstance(d, dict) else None) or []})
        return col, sources

    def _collecter_nebula(sid):
        """Lecture seule, chaque appel tolérant : un appel qui échoue est noté dans `erreurs`, le reste continue."""
        import anticipation
        import gwpolicy
        client = connect()
        devices = devices_of(sid) or []
        d, err = {"devices": [{"devId": x.get("devId"), "name": x.get("name"), "model": x.get("model"), "type": x.get("type")} for x in devices], "erreurs": []}, []

        def tol(nom, fn, defaut):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001
                err.append("%s : %s" % (nom, str(exc)[:160])); return defaut
        d["vlan_map"] = tol("carte VLAN", lambda: vlan_map(sid), {})
        d["wlans"] = tol("SSID", lambda: client.ap_wlan_settings(sid), [])
        for w in d["wlans"] if isinstance(d["wlans"], list) else []:     # jamais de clé Wi-Fi en base
            if isinstance(w, dict):
                for k in list(w):
                    if "key" in k.lower() or "passphrase" in k.lower() or "password" in k.lower():
                        w[k] = "***"
        d["online"] = {}
        for s in tol("état en ligne", lambda: client.get_online_status(sid), []) or []:
            if isinstance(s, dict) and s.get("devId"):
                d["online"][s["devId"]] = str(s.get("currentStatus") or "").lower() == "online"
        d["ports_by_sw"], d["nat"] = {}, []
        for x in devices:
            t = str(x.get("type") or "").upper()
            if t in ("SW", "SWITCH") and x.get("devId"):
                d["ports_by_sw"][x["devId"]] = tol("ports %s" % x.get("name"), lambda x=x: client.sw_port_settings(sid, x["devId"]) or [], [])
            if t in ("GW", "GATEWAY", "FIREWALL") and x.get("devId"):
                d["nat"] += gwpolicy.parse_nat(tol("NAT %s" % x.get("name"), lambda x=x: client.gw_nat_settings(sid, x["devId"]), {}))
        d["firmware"], _ = anticipation.firmware(devices)
        org_id, org_info = tol("organisation", lambda: org_of(sid), (None, None))
        d["licenses"], _ = anticipation.licenses(str(org_id or "organisation"), org_info, time.time()) if org_info else ([], [])
        d["clients"] = tol("clients", lambda: client.get_site_clients(sid, period="7d"), [])
        d["erreurs"] = err
        return d

    def _collecter_historiques(sid):
        import client_history
        conn = conn_fn()
        try:
            vus = client_history.query(conn, site_id=sid, limit=2000)["rows"]
        finally:
            conn.close()
        try:
            anom = anomalies_fn(sid)
        except Exception as exc:  # noqa: BLE001
            anom = [{"severity": "info", "message": "anomalies non lues : %s" % str(exc)[:100]}]
        return {"clients_vus": [{k: v for k, v in r.items() if k != "site_id"} for r in vus],
                "anomalies": [{"severity": a.get("severity"), "message": a.get("message")} for a in anom if isinstance(a, dict) and not a.get("state")]}

    @app.route("/sites/<site_id>/audit", methods=["GET"])
    def audit_get(site_id):
        col, sources = _assembler(site_id)
        constats = lib.analyser(col, _etats(site_id), _reglages(site_id))
        return jsonify({"site": _site_nom(site_id), "constats": constats, "matrice": lib.matrice(constats), "preconisations": lib.preconisations(constats),
                        "sources": sources, "domaines": lib.DOMAINES, "etats": lib.LIBELLE_ETAT, "niveaux": lib.LIBELLE_NIVEAU}), 200

    @app.route("/sites/<site_id>/audit/collecter", methods=["POST"])
    def audit_collecter(site_id):
        quoi = (request.get_json(silent=True) or {}).get("quoi") or ["nebula", "historiques"]
        res = {}
        if "nebula" in quoi:
            try:
                d = _collecter_nebula(site_id)
                _enregistrer(site_id, "nebula", d, "API Nebula")
                res["nebula"] = {"ok": True, "erreurs": d["erreurs"], "ssids": len(d["wlans"] or []), "clients": len(d["clients"] or []), "nat": len(d["nat"])}
            except Exception as exc:  # noqa: BLE001
                res["nebula"] = {"ok": False, "erreur": str(exc)[:300]}
        if "historiques" in quoi:
            d = _collecter_historiques(site_id)
            _enregistrer(site_id, "historiques", d, "historiques accumulés")
            res["historiques"] = {"ok": True, "clients_vus": len(d["clients_vus"]), "anomalies": len(d["anomalies"])}
        return jsonify(res), 200

    @app.route("/sites/<site_id>/audit/importer", methods=["POST"])
    def audit_importer(site_id):
        body = request.get_json(silent=True) or {}
        source, d = body.get("source"), body.get("donnees")
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except ValueError:
                return jsonify({"error": "JSON invalide"}), 400
        if source not in ("proxmox", "hote", "manuel") or not isinstance(d, dict):
            return jsonify({"error": "source attendue : proxmox | hote | manuel, donnees = objet JSON"}), 400
        if source == "manuel":
            c, err = lib.valider_manuel(d)
            if err:
                return jsonify({"error": err}), 400
            libelle = c["id"]
        else:
            libelle = d.get("hostname") or d.get("nom") or d.get("ip") or source
        _enregistrer(site_id, source, d, libelle)
        return jsonify({"ok": True, "source": source, "libelle": libelle}), 200

    @app.route("/sites/<site_id>/audit/collectes", methods=["GET"])
    def audit_collectes(site_id):
        return jsonify([{k: v for k, v in c.items() if k != "donnees"} | {"taille": len(json.dumps(c["donnees"]))} for c in _collectes(site_id)]), 200

    @app.route("/sites/<site_id>/audit/collectes/<int:cid>", methods=["DELETE"])
    def audit_collecte_suppr(site_id, cid):
        conn = conn_fn()
        try:
            conn.execute("DELETE FROM audit_collectes WHERE site_id = ? AND id = ?", (site_id, cid)); conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True}), 200

    @app.route("/sites/<site_id>/audit/constats/<path:cid>", methods=["PUT"])
    def audit_constat_put(site_id, cid):
        b = request.get_json(silent=True) or {}
        etat = b.get("etat") if b.get("etat") in lib.ETATS else None
        p = int(b["probabilite"]) if str(b.get("probabilite") or "").isdigit() else None
        i = int(b["impact"]) if str(b.get("impact") or "").isdigit() else None
        conn = conn_fn()
        try:
            conn.execute("INSERT INTO audit_constats (site_id, constat_id, etat, probabilite, impact, note, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                         "ON CONFLICT(site_id, constat_id) DO UPDATE SET etat = COALESCE(excluded.etat, etat), probabilite = COALESCE(excluded.probabilite, probabilite), "
                         "impact = COALESCE(excluded.impact, impact), note = COALESCE(excluded.note, note), updated_at = excluded.updated_at",
                         (site_id, cid, etat, p, i, b.get("note"), int(time.time())))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True}), 200

    @app.route("/sites/<site_id>/audit/reglages", methods=["GET", "PUT"])
    def audit_reglages(site_id):
        if request.method == "PUT":
            b = request.get_json(silent=True) or {}
            r = {"vlans_serveurs": [str(x) for x in b.get("vlans_serveurs") or []][:20], "vlans_iot": [str(x) for x in b.get("vlans_iot") or []][:20]}
            conn = conn_fn()
            try:
                conn.execute("INSERT OR REPLACE INTO audit_reglages (site_id, donnees) VALUES (?, ?)", (site_id, json.dumps(r))); conn.commit()
            finally:
                conn.close()
            return jsonify(r), 200
        return jsonify(_reglages(site_id)), 200

    @app.route("/sites/<site_id>/audit.md", methods=["GET"])
    def audit_md(site_id):
        col, sources = _assembler(site_id)
        constats = lib.analyser(col, _etats(site_id), _reglages(site_id))
        src = ["%s — %s (%s)" % (s["source"], s["libelle"], time.strftime("%d/%m/%Y %H:%M", time.localtime(s["at"]))) for s in sources]
        md = lib.rapport_markdown(_site_nom(site_id), constats, src, time.strftime("%d/%m/%Y"))
        return Response(md, mimetype="text/markdown; charset=utf-8", headers={"Content-Disposition": "attachment; filename=audit-securite-%s.md" % site_id[:8]})

    @app.route("/sites/<site_id>/audit.csv", methods=["GET"])
    def audit_csv(site_id):
        col, _ = _assembler(site_id)
        constats = lib.analyser(col, _etats(site_id), _reglages(site_id))
        return Response(lib.constats_csv(constats), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=audit-securite-%s.csv" % site_id[:8]})
