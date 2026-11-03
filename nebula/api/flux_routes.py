"""Routes de la supervision des flux éditeurs (#962) -- logique : flux.py.

Listes de cibles   GET /flux/listes · PUT /flux/listes · DELETE /flux/listes/<id> · GET /flux/listes/<id>.txt (pour le script)
Sites              GET /flux/sites (sites Nebula + sites ayant envoyé des résultats, état du dernier passage)
Résultats          POST /sites/<s>/flux/resultats  (envoyés par nebula/tools/test-flux.sh : HUB=… SITE=…)
Consultation       GET /sites/<s>/flux · GET /sites/<s>/flux/passages/<id>[.csv] · GET /sites/<s>/flux/alertes?etat=
Alertes            POST /sites/<s>/flux/alertes/<id>/acquitter
Analyse Nebula     GET /sites/<s>/flux/analyse  (terminaux mobiles par VLAN / SSID d'après l'historique des clients, VLAN testés)
"""
import json
import re
import time

from flask import jsonify, request, Response

import flux as lib

try:
    import notify_client
except ImportError:  # pragma: no cover
    notify_client = None

ACTIONS = [{"id": "flux.ferme", "label": "Flux éditeur fermé ou inspecté (Google, Idruide…)", "severity": "warning"},
           {"id": "flux.retabli", "label": "Flux éditeur rétabli", "severity": "info"}]

SCHEMA = """
CREATE TABLE IF NOT EXISTS flux_listes (id TEXT PRIMARY KEY, data TEXT NOT NULL, maj INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS flux_sites (id TEXT PRIMARY KEY, nom TEXT NOT NULL, description TEXT, maj INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS flux_passages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, source TEXT NOT NULL, at INTEGER NOT NULL, data TEXT NOT NULL, bilan TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_flux_passages ON flux_passages (site_id, source, at);
CREATE TABLE IF NOT EXISTS flux_alertes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, cle TEXT NOT NULL, source TEXT NOT NULL, data TEXT NOT NULL,
    debut INTEGER NOT NULL, dernier INTEGER NOT NULL, fin INTEGER, acquitte_par TEXT, acquitte_at INTEGER, note TEXT);
CREATE INDEX IF NOT EXISTS idx_flux_alertes ON flux_alertes (site_id, fin);
"""
SITE_RX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
RETENTION_PASSAGES = 2000          # par site : les plus anciens sont purgés


def register(app, hooks):
    conn_fn = hooks["conn"]
    sites_fn = hooks.get("sites") or (lambda: [])
    vlan_map = hooks.get("vlan_map") or (lambda sid: {})
    log = hooks.get("log") or (lambda m: app.logger.warning(m))
    c = conn_fn()
    try:
        c.executescript(SCHEMA); c.commit()
    finally:
        c.close()
    if notify_client is not None:
        try:
            notify_client.register_actions(ACTIONS)
        except Exception:  # noqa: BLE001
            pass

    def q(sql, args=(), un=False, ecrit=False):
        c = conn_fn()
        try:
            cur = c.execute(sql, args)
            if ecrit:
                c.commit(); return cur.lastrowid
            return cur.fetchone() if un else cur.fetchall()
        finally:
            c.close()

    def _listes():
        out = dict(lib.LISTES_INTEGREES)
        for r in q("SELECT id, data, maj FROM flux_listes ORDER BY id"):
            d = json.loads(r["data"]); d.update(id=r["id"], maj=r["maj"], integree=False); out[r["id"]] = d
        for d in out.values():
            lignes, err = lib.lire_liste(d.get("texte"))
            d["n_cibles"], d["n_tests"] = len(lignes), sum(len(lib.ports(x["ports"])) for x in lignes)
        return out

    def _site_ok(s):
        return bool(SITE_RX.match(s or ""))

    def _passage_row(r, avec_lignes=True):
        d = json.loads(r["data"])
        out = {"id": r["id"], "site_id": r["site_id"], "source": r["source"], "at": r["at"], "bilan": json.loads(r["bilan"]),
               "iface": d.get("iface"), "ip_source": d.get("ip_source"), "ip_publique": d.get("ip_publique")}
        if avec_lignes:
            out["lignes"] = d["lignes"]
        return out

    def _alerte_row(r):
        d = json.loads(r["data"])
        d.update(id=r["id"], cle=r["cle"], source=r["source"], debut=r["debut"], dernier=r["dernier"], fin=r["fin"],
                 acquitte_par=r["acquitte_par"], acquitte_at=r["acquitte_at"], note=r["note"])
        return d

    def _notifier(action, sujet, corps, severite):
        if notify_client is None:
            return
        try:
            notify_client.notify(action, sujet, corps, context={"module": "nebula-flux"}, severity=severite, wait=False)
        except Exception as exc:  # noqa: BLE001
            log("flux: notification impossible : %s" % str(exc)[:160])

    # -- listes ------------------------------------------------------------------------------------------------------
    @app.route("/flux/listes", methods=["GET"])
    def flux_listes():
        return jsonify({"listes": sorted(_listes().values(), key=lambda d: (not d.get("integree"), d["nom"].lower()))}), 200

    @app.route("/flux/listes", methods=["PUT"])
    def flux_liste_put():
        b = request.get_json(silent=True) or {}
        nom = str(b.get("nom") or "").strip()[:80]
        if not nom:
            return jsonify({"error": "nom requis (ex. « Idruide »)"}), 400
        lignes, err = lib.lire_liste(b.get("texte"))
        if not lignes:
            return jsonify({"error": "aucune cible valide", "erreurs": err}), 400
        lid = re.sub(r"[^a-z0-9-]+", "-", (b.get("id") or nom).lower()).strip("-")[:40]
        if lid in lib.LISTES_INTEGREES:
            return jsonify({"error": "« %s » est une liste intégrée : choisir un autre nom" % lid}), 400
        d = {"nom": nom, "editeur": str(b.get("editeur") or nom)[:80], "source": str(b.get("source") or "")[:300], "texte": lib.texte_liste(lignes)}
        q("INSERT OR REPLACE INTO flux_listes (id, data, maj) VALUES (?, ?, ?)", (lid, json.dumps(d, ensure_ascii=False), int(time.time())), ecrit=True)
        return jsonify({"ok": True, "id": lid, "cibles": len(lignes), "erreurs": err}), 200

    @app.route("/flux/listes/<lid>", methods=["DELETE"])
    def flux_liste_suppr(lid):
        if lid in lib.LISTES_INTEGREES:
            return jsonify({"error": "liste intégrée : non supprimable"}), 400
        q("DELETE FROM flux_listes WHERE id = ?", (lid,), ecrit=True)
        return jsonify({"ok": True}), 200

    @app.route("/flux/listes/<lid>.txt", methods=["GET"])
    def flux_liste_txt(lid):
        d = _listes().get(lid)
        if not d:
            return jsonify({"error": "liste inconnue : %s" % lid}), 404
        lignes, _ = lib.lire_liste(d["texte"])
        return Response("# %s — %s\n" % (d["nom"], d.get("source") or "") + lib.texte_liste(lignes), mimetype="text/plain; charset=utf-8")

    # -- sites ---------------------------------------------------------------------------------------------------------
    @app.route("/flux/sites", methods=["GET"])
    def flux_sites():
        sites = {}
        try:
            for s in sites_fn():
                sid = s.get("siteId") or s.get("site_id")
                if sid:
                    sites[sid] = {"site_id": sid, "nom": s.get("name") or sid, "nebula": True}
        except Exception:  # noqa: BLE001 -- sans Nebula, les sites viennent des résultats reçus
            pass
        for r in q("SELECT id, nom, description FROM flux_sites"):
            sites.setdefault(r["id"], {"site_id": r["id"], "nebula": False}).update(nom=r["nom"], description=r["description"], declare=True)
        for r in q("SELECT site_id, MAX(at) AS at FROM flux_passages GROUP BY site_id"):
            sites.setdefault(r["site_id"], {"site_id": r["site_id"], "nom": r["site_id"], "nebula": False})["dernier_at"] = r["at"]
        for s in sites.values():
            s["alertes"] = q("SELECT COUNT(*) AS n FROM flux_alertes WHERE site_id = ? AND fin IS NULL", (s["site_id"],), un=True)["n"]
        return jsonify({"sites": sorted(sites.values(), key=lambda s: (not s.get("nebula"), s["nom"].lower()))}), 200

    @app.route("/flux/sites", methods=["PUT"])
    def flux_site_put():
        """Déclare un SI / site hors Nebula (ex. « optline » : SI de l'entreprise, sources = agent OVH + agent du LAN)."""
        b = request.get_json(silent=True) or {}
        sid = re.sub(r"[^A-Za-z0-9_-]+", "-", str(b.get("id") or b.get("nom") or "").strip().lower()).strip("-")[:64]
        nom = str(b.get("nom") or sid).strip()[:80]
        if not sid:
            return jsonify({"error": "identifiant ou nom requis (ex. « optline »)"}), 400
        q("INSERT OR REPLACE INTO flux_sites (id, nom, description, maj) VALUES (?, ?, ?, ?)",
          (sid, nom, str(b.get("description") or "")[:300] or None, int(time.time())), ecrit=True)
        return jsonify({"ok": True, "site_id": sid, "nom": nom}), 200

    @app.route("/flux/sites/<sid>", methods=["DELETE"])
    def flux_site_suppr(sid):
        q("DELETE FROM flux_sites WHERE id = ?", (sid,), ecrit=True)
        return jsonify({"ok": True, "note": "déclaration retirée ; les passages déjà reçus restent consultables"}), 200

    # -- résultats envoyés par le script ---------------------------------------------------------------------------------
    @app.route("/sites/<site_id>/flux/resultats", methods=["POST"])
    def flux_resultats(site_id):
        if not _site_ok(site_id):
            return jsonify({"error": "identifiant de site invalide"}), 400
        p, err = lib.valider_resultats(request.get_json(silent=True))
        if err:
            return jsonify({"error": err}), 400
        now = int(time.time())
        b = lib.bilan(p["lignes"])
        pid = q("INSERT INTO flux_passages (site_id, source, at, data, bilan) VALUES (?, ?, ?, ?, ?)",
                (site_id, p["source"], now, json.dumps(p, ensure_ascii=False), json.dumps(b)), ecrit=True)
        ouvertes = {r["cle"]: _alerte_row(r) for r in q("SELECT * FROM flux_alertes WHERE site_id = ? AND source = ? AND fin IS NULL", (site_id, p["source"]))}
        nouv, ret, maint = lib.diff_alertes(ouvertes, p["lignes"], p["source"], now)
        c = conn_fn()
        try:
            for a in nouv:
                c.execute("INSERT INTO flux_alertes (site_id, cle, source, data, debut, dernier) VALUES (?, ?, ?, ?, ?, ?)",
                          (site_id, a["cle"], a["source"], json.dumps({k: a.get(k) for k in ("hote", "proto", "port", "groupe", "statut", "detail")}, ensure_ascii=False), now, now))
            for a in maint:
                c.execute("UPDATE flux_alertes SET dernier = ?, data = ? WHERE id = ?",
                          (now, json.dumps({k: a[k] for k in ("hote", "proto", "port", "groupe", "statut", "detail")}, ensure_ascii=False), a["id"]))
            for a in ret:
                c.execute("UPDATE flux_alertes SET fin = ?, dernier = ? WHERE id = ?", (now, now, a["id"]))
            ids = [r[0] for r in c.execute("SELECT id FROM flux_passages WHERE site_id = ? ORDER BY at DESC LIMIT -1 OFFSET ?", (site_id, RETENTION_PASSAGES))]
            if ids:
                c.execute("DELETE FROM flux_passages WHERE id IN (%s)" % ",".join("?" * len(ids)), ids)
            c.commit()
        finally:
            c.close()
        if nouv:
            _notifier("flux.ferme", "[flux] %s : %d flux fermé(s) ou inspecté(s) depuis %s" % (site_id, len(nouv), p["source"]),
                      "\n".join("%s %s/%d : %s" % (a["statut"], a["hote"], a["port"], a["detail"]) for a in nouv[:40]), "warning")
        if ret:
            _notifier("flux.retabli", "[flux] %s : %d flux rétabli(s) depuis %s" % (site_id, len(ret), p["source"]),
                      "\n".join("%s/%d" % (a["hote"], a["port"]) for a in ret[:40]), "info")
        return jsonify({"ok": True, "passage": pid, "bilan": b, "alertes": {"nouvelles": len(nouv), "retablies": len(ret), "ouvertes": len(nouv) + len(maint)}}), 200

    # -- consultation ----------------------------------------------------------------------------------------------------
    @app.route("/sites/<site_id>/flux", methods=["GET"])
    def flux_site(site_id):
        derniers = q("SELECT p.* FROM flux_passages p JOIN (SELECT source, MAX(at) AS at FROM flux_passages WHERE site_id = ? GROUP BY source) m "
                     "ON p.source = m.source AND p.at = m.at WHERE p.site_id = ? ORDER BY p.source", (site_id, site_id))
        sources = []
        for r in derniers:
            p = _passage_row(r)
            p["matrice"] = lib.matrice(p.pop("lignes"))
            sources.append(p)
        hist = [_passage_row(r, False) for r in q("SELECT * FROM flux_passages WHERE site_id = ? ORDER BY at DESC LIMIT 60", (site_id,))]
        ouvertes = [_alerte_row(r) for r in q("SELECT * FROM flux_alertes WHERE site_id = ? AND fin IS NULL ORDER BY debut DESC", (site_id,))]
        return jsonify({"site_id": site_id, "sources": sources, "historique": hist, "alertes_ouvertes": ouvertes}), 200

    @app.route("/sites/<site_id>/flux/passages/<int:pid>", methods=["GET"])
    def flux_passage(site_id, pid):
        r = q("SELECT * FROM flux_passages WHERE site_id = ? AND id = ?", (site_id, pid), un=True)
        if not r:
            return jsonify({"error": "passage inconnu"}), 404
        p = _passage_row(r); p["matrice"] = lib.matrice(p["lignes"])
        return jsonify(p), 200

    @app.route("/sites/<site_id>/flux/passages/<int:pid>.csv", methods=["GET"])
    def flux_passage_csv(site_id, pid):
        r = q("SELECT * FROM flux_passages WHERE site_id = ? AND id = ?", (site_id, pid), un=True)
        if not r:
            return jsonify({"error": "passage inconnu"}), 404
        return Response(lib.csv_passage(_passage_row(r)["lignes"]), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=flux-%s-%d.csv" % (site_id[:20], pid)})

    @app.route("/sites/<site_id>/flux/alertes", methods=["GET"])
    def flux_alertes(site_id):
        etat = request.args.get("etat") or "toutes"
        sql = "SELECT * FROM flux_alertes WHERE site_id = ?" + (" AND fin IS NULL" if etat == "ouvertes" else " AND fin IS NOT NULL" if etat == "retablies" else "")
        return jsonify({"alertes": [_alerte_row(r) for r in q(sql + " ORDER BY COALESCE(fin, dernier) DESC LIMIT 500", (site_id,))]}), 200

    @app.route("/sites/<site_id>/flux/alertes/<int:aid>/acquitter", methods=["POST"])
    def flux_acquitter(site_id, aid):
        b = request.get_json(silent=True) or {}
        q("UPDATE flux_alertes SET acquitte_par = ?, acquitte_at = ?, note = ? WHERE site_id = ? AND id = ?",
          ((b.get("par") or "")[:80] or None, int(time.time()), (b.get("note") or "")[:300] or None, site_id, aid), ecrit=True)
        return jsonify({"ok": True}), 200

    # -- analyse Nebula ----------------------------------------------------------------------------------------------------
    @app.route("/sites/<site_id>/flux/analyse", methods=["GET"])
    def flux_analyse(site_id):
        erreurs = []
        try:
            vmap = vlan_map(site_id) or {}
        except Exception as exc:  # noqa: BLE001
            vmap = {}; erreurs.append("carte des VLAN Nebula : %s" % str(exc)[:160])
        jours = max(1, min(int(request.args.get("jours") or 7), 60))
        clients = []
        try:
            import client_history
            c = conn_fn()
            try:
                clients = client_history.query(c, site_id=site_id, since=int(time.time()) - jours * 86400, limit=2000)["rows"]
            finally:
                c.close()
        except Exception as exc:  # noqa: BLE001
            erreurs.append("historique des clients : %s" % str(exc)[:160])
        derniers = q("SELECT p.* FROM flux_passages p JOIN (SELECT source, MAX(at) AS at FROM flux_passages WHERE site_id = ? GROUP BY source) m "
                     "ON p.source = m.source AND p.at = m.at WHERE p.site_id = ?", (site_id, site_id))
        a = lib.analyse_nebula(vmap, [{"fabricant": r.get("manufacturer"), "os": r.get("os"), "nom": r.get("name"), "ip": r.get("ip"),
                                       "ssid": r.get("ssid"), "vlan": r.get("vlan")} for r in clients],
                               [_passage_row(r, False) for r in derniers], (vmap.get("anomalies_detail") or []))
        a.update(erreurs=erreurs, jours=jours, clients_lus=len(clients))
        return jsonify(a), 200
