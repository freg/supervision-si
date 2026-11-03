# -*- coding: utf-8 -*-
"""Routes du repérage physique (livraison #949) -- voir reperage.py pour la logique et le pourquoi.

GET  /sites/<site>/reperage/inventaire?period=1d        clients fusionnés (filaire : commutateur + port ; wifi : borne + signal), cache 60 s
GET  /sites/<site>/reperage/recherche?q=                 MAC / IP / nom / fabricant / « p12 » / prise / local
GET  /sites/<site>/reperage/prises                       prises relevées (brassage, position, photos)
PUT  /sites/<site>/reperage/prises                       {prise, local, commutateur, port, panneau, equipement, mac, long_cordon, wifi, defaut, note, x, y, photos}
DELETE /sites/<site>/reperage/prises/<libelle>
GET  /sites/<site>/reperage/prises.csv
POST /sites/<site>/reperage/photos  (multipart `file`, ≤ 6 Mo, image)  → {id}   ;  GET …/photos/<id>
GET  /sites/<site>/reperage/mobile?mac=                  ce que la borne voit du téléphone (signal, bande, canal, ssid), période 2h
GET/POST /sites/<site>/reperage/releves                  points de couverture {x, y, mac, note, rssi_mobile} ; DELETE …/releves/<id>
Données : tables reperage_prises / reperage_releves (SQLite du module), photos dans <dossier de la base>/reperage/<site>/."""
import json
import os
import re
import time
import uuid

from flask import jsonify, request, send_from_directory, Response

import reperage as lib

SCHEMA = """
CREATE TABLE IF NOT EXISTS reperage_prises (
    site_id TEXT NOT NULL, prise TEXT NOT NULL, data TEXT NOT NULL, updated_at INTEGER NOT NULL, updated_by TEXT,
    PRIMARY KEY (site_id, prise)
);
CREATE TABLE IF NOT EXISTS reperage_appareils (
    mac TEXT PRIMARY KEY, nom TEXT NOT NULL, genre TEXT NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reperage_radar (
    id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, scan_id TEXT NOT NULL, source TEXT NOT NULL, at REAL NOT NULL,
    x REAL, y REAL, bssid TEXT NOT NULL, ssid TEXT, rssi INTEGER NOT NULL, frequence INTEGER, canal INTEGER, bande TEXT, distance_m REAL,
    connecte INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reperage_radar_site_at ON reperage_radar (site_id, at);
CREATE TABLE IF NOT EXISTS reperage_radar_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, source TEXT NOT NULL, at REAL NOT NULL, x REAL NOT NULL, y REAL NOT NULL, note TEXT
);
CREATE TABLE IF NOT EXISTS reperage_releves (
    id TEXT PRIMARY KEY, site_id TEXT NOT NULL, data TEXT NOT NULL, at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reperage_sonde (
    id INTEGER PRIMARY KEY AUTOINCREMENT, site_id TEXT NOT NULL, source TEXT NOT NULL, mode TEXT NOT NULL, at INTEGER NOT NULL, maj INTEGER NOT NULL,
    data TEXT NOT NULL, prise TEXT, ack_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reperage_sonde_site ON reperage_sonde (site_id, at);
CREATE TABLE IF NOT EXISTS reperage_equipements (
    site_id TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, updated_by TEXT,
    PRIMARY KEY (site_id, id)
);
"""
CACHE_S = 60
_cache = {}   # site_id -> {"at", "inv"}
_mac_test = {}   # MAC du téléphone vue en dernier sur le site de test (pour que la recherche l'affiche aussi)


def register(app, hooks):
    conn_fn, connect, db_path = hooks["conn"], hooks["client"], hooks["db_path"]
    device_names = hooks.get("devices") or (lambda sid: [])
    dossier_photos = os.path.join(os.path.dirname(db_path), "reperage")

    conn = conn_fn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    def _appareils():
        conn = conn_fn()
        try:
            rows = conn.execute("SELECT mac, nom, genre, updated_at FROM reperage_appareils ORDER BY nom").fetchall()
        finally:
            conn.close()
        out = [{"mac": r["mac"], "nom": r["nom"], "genre": r["genre"], "maj": r["updated_at"]} for r in rows]
        # amorçage par l'environnement (jamais dans le dépôt) : REPERAGE_APPAREILS="aa:bb:cc:dd:ee:ff=Téléphone X;…"
        for item in (os.environ.get("REPERAGE_APPAREILS") or "").split(";"):
            if "=" in item:
                m, n = item.split("=", 1)
                a, err = lib.valider_appareil({"mac": m.strip(), "nom": n.strip()})
                if a and not any(x["mac"] == a["mac"] for x in out):
                    out.append(dict(a, maj=None, env=True))
        return out

    def _inventaire(site_id, period="1d", force=False, mac_mobile=None):
        if site_id == lib.SITE_TEST:        # bureau : pas de Nebula, inventaire simulé (jamais mis en cache : le signal bouge)
            inv = lib.inventaire_test(mac_mobile=mac_mobile or _mac_test.get("mac"), appareils=_appareils()); inv["erreurs"] = []; inv["period"] = period
            return lib.enrichir_connus(inv, _appareils())
        c = _cache.get(site_id)
        if c and not force and time.time() - c["at"] < CACHE_S and c["period"] == period:
            return lib.enrichir_connus(c["inv"], _appareils())
        client = connect()
        erreurs = []
        sw = ap = sc = []
        try:
            sw = client.sw_clients(site_id, period=period)
            sw = sw.get("data", []) if isinstance(sw, dict) else sw
        except Exception as e:  # noqa: BLE001
            erreurs.append("commutateurs : %s" % str(e)[:160])
        try:
            ap = client.ap_clients_v2(site_id, period=period)
        except Exception as e:  # noqa: BLE001
            erreurs.append("bornes : %s" % str(e)[:160])
        try:
            sc = client.get_site_clients(site_id, period=period, features=["mac_address", "ipv4", "vlan", "last_seen", "connected_device_id", "status", "description", "os_hostname", "manufacturer"])
        except Exception as e:  # noqa: BLE001
            erreurs.append("clients : %s" % str(e)[:160])
        inv = lib.inventaire(sw, ap, sc, device_names(site_id))
        inv["erreurs"] = erreurs
        inv["period"] = period
        _cache[site_id] = {"at": time.time(), "inv": inv, "period": period}
        return lib.enrichir_connus(inv, _appareils())

    def _prises(site_id):
        conn = conn_fn()
        try:
            rows = conn.execute("SELECT prise, data, updated_at, updated_by FROM reperage_prises WHERE site_id = ? ORDER BY prise", (site_id,)).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            d = json.loads(r["data"])
            d.update(maj=r["updated_at"], par=r["updated_by"])
            out.append(d)
        return out

    @app.route("/reperage/sites", methods=["GET"])
    def reperage_sites():
        """Sites du repérage : ceux de Nebula (inventaire) + le site de test du bureau, toujours présent."""
        sites = []
        try:
            for s in hooks.get("sites", lambda: [])():
                sites.append({"site_id": s.get("siteId") or s.get("site_id"), "name": s.get("name") or s.get("siteId")})
        except Exception:  # noqa: BLE001
            pass
        sites.append({"site_id": lib.SITE_TEST, "name": "Bureau — test sans Nebula", "test": True})
        return jsonify({"sites": sites}), 200

    # -- appareils connus (téléphones de test…) : dans la base du module, jamais dans le dépôt ---------------------------
    @app.route("/reperage/appareils", methods=["GET"])
    def reperage_appareils():
        return jsonify({"appareils": _appareils()}), 200

    @app.route("/reperage/appareils", methods=["PUT"])
    def reperage_appareil_put():
        a, err = lib.valider_appareil(request.get_json(silent=True) or {})
        if err:
            return jsonify({"error": err}), 400
        conn = conn_fn()
        try:
            conn.execute("INSERT INTO reperage_appareils (mac, nom, genre, updated_at) VALUES (?, ?, ?, ?) "
                         "ON CONFLICT(mac) DO UPDATE SET nom = excluded.nom, genre = excluded.genre, updated_at = excluded.updated_at", (a["mac"], a["nom"], a["genre"], int(time.time())))
            conn.commit()
        finally:
            conn.close()
        return jsonify(a), 200

    @app.route("/reperage/appareils/<mac>", methods=["DELETE"])
    def reperage_appareil_del(mac):
        conn = conn_fn()
        try:
            n = conn.execute("DELETE FROM reperage_appareils WHERE mac = ?", (lib.norm_mac(mac) or "",)).rowcount
            conn.commit()
        finally:
            conn.close()
        return jsonify({"supprime": n}), 200

    @app.route("/sites/<site_id>/reperage/inventaire", methods=["GET"])
    def reperage_inventaire(site_id):
        try:
            inv = _inventaire(site_id, request.args.get("period", "1d"), force=request.args.get("refresh") == "1")
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": "Nebula injoignable : %s" % str(e)[:200]}), 502
        return jsonify(inv), 200

    @app.route("/sites/<site_id>/reperage/recherche", methods=["GET"])
    def reperage_recherche(site_id):
        try:
            inv = _inventaire(site_id, request.args.get("period", "1d"))
        except Exception as e:  # noqa: BLE001
            inv = {"clients": [], "erreurs": [str(e)[:160]]}
        res = lib.rechercher(inv, _prises(site_id), request.args.get("q") or "")
        return jsonify({"q": request.args.get("q"), "resultats": res, "erreurs": inv.get("erreurs") or []}), 200

    @app.route("/sites/<site_id>/reperage/prises", methods=["GET"])
    def reperage_prises(site_id):
        return jsonify({"site_id": site_id, "prises": _prises(site_id)}), 200

    @app.route("/sites/<site_id>/reperage/prises.csv", methods=["GET"])
    def reperage_prises_csv(site_id):
        return Response(lib.prises_csv(_prises(site_id)), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=prises-%s.csv" % re.sub(r"[^A-Za-z0-9_-]", "_", site_id)})

    @app.route("/sites/<site_id>/reperage/prises", methods=["PUT"])
    def reperage_prise_put(site_id):
        body = request.get_json(silent=True) or {}
        p, err = lib.valider_prise(body)
        if err:
            return jsonify({"error": err}), 400
        now = int(time.time())
        conn = conn_fn()
        try:
            conn.execute("INSERT INTO reperage_prises (site_id, prise, data, updated_at, updated_by) VALUES (?, ?, ?, ?, ?) "
                         "ON CONFLICT(site_id, prise) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                         (site_id, p["prise"], json.dumps(p, ensure_ascii=False), now, (body.get("par") or "")[:80] or None))
            conn.commit()
        finally:
            conn.close()
        p.update(maj=now, par=body.get("par"))
        return jsonify(p), 200

    @app.route("/sites/<site_id>/reperage/prises/<path:prise>", methods=["DELETE"])
    def reperage_prise_del(site_id, prise):
        conn = conn_fn()
        try:
            n = conn.execute("DELETE FROM reperage_prises WHERE site_id = ? AND prise = ?", (site_id, prise)).rowcount
            conn.commit()
        finally:
            conn.close()
        return jsonify({"supprime": n}), 200

    # -- photos -------------------------------------------------------------------------------------------------
    @app.route("/sites/<site_id>/reperage/photos", methods=["POST"])
    def reperage_photo_post(site_id):
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "fichier `file` attendu (image)"}), 400
        data = f.read(6 * 1024 * 1024 + 1)
        if len(data) > 6 * 1024 * 1024:
            return jsonify({"error": "photo trop lourde (> 6 Mo) : réduire la taille côté téléphone"}), 413
        ext = ".jpg" if (f.mimetype or "").endswith(("jpeg", "jpg")) else ".png" if (f.mimetype or "").endswith("png") else ".webp" if (f.mimetype or "").endswith("webp") else None
        if not ext:
            return jsonify({"error": "format non pris en charge (jpeg, png, webp)"}), 415
        pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6] + ext
        d = os.path.join(dossier_photos, re.sub(r"[^A-Za-z0-9_-]", "_", site_id))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, pid), "wb") as fh:
            fh.write(data)
        return jsonify({"id": pid, "taille": len(data)}), 201

    @app.route("/sites/<site_id>/reperage/photos/<pid>", methods=["GET"])
    def reperage_photo_get(site_id, pid):
        if not re.fullmatch(r"[0-9A-Za-z_.-]+", pid):
            return jsonify({"error": "identifiant invalide"}), 400
        return send_from_directory(os.path.join(dossier_photos, re.sub(r"[^A-Za-z0-9_-]", "_", site_id)), pid, max_age=3600)

    # -- couverture Wi-Fi ----------------------------------------------------------------------------------------
    def _mobile(site_id, mac):
        mac = lib.norm_mac(mac)
        if not mac:
            return None
        if site_id == lib.SITE_TEST:
            _mac_test["mac"] = mac
        try:
            inv = _inventaire(site_id, "2h", mac_mobile=mac)
        except Exception:  # noqa: BLE001
            return None
        return next((c for c in inv["clients"] if c["mac"] == mac), None)

    @app.route("/sites/<site_id>/reperage/mobile", methods=["GET"])
    def reperage_mobile(site_id):
        mac = request.args.get("mac") or ""
        if not lib.norm_mac(mac):
            return jsonify({"error": "MAC du téléphone attendue (Réglages › À propos › Adresse MAC Wi-Fi ; attention aux MAC aléatoires par réseau)"}), 400
        if request.args.get("refresh") == "1":
            _cache.pop(site_id, None)
        m = _mobile(site_id, mac)
        return jsonify({"mac": lib.norm_mac(mac), "vu": m is not None, "mobile": m, "classe": lib.signal_couleur((m or {}).get("signal")),
                        "note": "signal vu par la borne (Nebula, rafraîchi avec un retard de l'ordre de la minute)"}), 200

    # -- radar Wi-Fi mobile (#954) : balayages envoyés par le téléphone (Termux) ou une sonde portée --------------------
    @app.route("/sites/<site_id>/reperage/radar", methods=["POST"])
    def reperage_radar_post(site_id):
        b, err = lib.valider_balayage(request.get_json(silent=True) or {})
        if err:
            return jsonify({"error": err, "aide": "corps attendu : {source, at?, x?, y?, scan: [{bssid, ssid, rssi, frequency_mhz}]} (sortie de termux-wifi-scaninfo acceptée dans `scan`)"}), 400
        sid = uuid.uuid4().hex[:10]
        conn = conn_fn()
        try:
            try:
                conn.execute("ALTER TABLE reperage_radar ADD COLUMN connecte INTEGER NOT NULL DEFAULT 0")   # bases créées en #954
            except Exception:  # noqa: BLE001
                pass
            conn.executemany("INSERT INTO reperage_radar (site_id, scan_id, source, at, x, y, bssid, ssid, rssi, frequence, canal, bande, distance_m, connecte) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             [(site_id, sid, b["source"], b["at"], b["x"], b["y"], k["bssid"], k["ssid"], k["rssi"], k["frequence"], k["canal"], k["bande"], k["distance_m"], 1 if k.get("connecte") else 0) for k in b["bornes"]])
            conn.commit()
        finally:
            conn.close()
        return jsonify({"scan_id": sid, "bornes": len(b["bornes"]), "at": b["at"], "plus_forte": b["bornes"][0]}), 201

    @app.route("/sites/<site_id>/reperage/radar/position", methods=["POST"])
    def reperage_radar_position(site_id):
        """Marque de position du porteur (toucher le plan) : rapprochée des balayages par le temps en post-traitement."""
        b = request.get_json(silent=True) or {}
        try:
            x, y = min(1.0, max(0.0, float(b.get("x")))), min(1.0, max(0.0, float(b.get("y"))))
        except (TypeError, ValueError):
            return jsonify({"error": "position (x, y) attendue"}), 400
        src = (str(b.get("source") or "")).strip()[:80] or "?"
        at = time.time()
        conn = conn_fn()
        try:
            conn.execute("INSERT INTO reperage_radar_positions (site_id, source, at, x, y, note) VALUES (?, ?, ?, ?, ?, ?)", (site_id, src, at, x, y, (b.get("note") or "")[:200] or None))
            conn.commit()
        finally:
            conn.close()
        return jsonify({"source": src, "at": at, "x": x, "y": y}), 201

    @app.route("/sites/<site_id>/reperage/radar", methods=["GET"])
    def reperage_radar_get(site_id):
        """Dernier balayage de `source` (ou de chaque source) + compteurs ; `?depuis=<epoch>` pour l'historique brut (post-traitement)."""
        src = request.args.get("source")
        depuis = request.args.get("depuis")
        conn = conn_fn()
        try:
            if depuis:
                rows = conn.execute("SELECT * FROM reperage_radar WHERE site_id = ? AND at >= ? ORDER BY at, rssi DESC LIMIT 20000", (site_id, float(depuis))).fetchall()
                pos = conn.execute("SELECT source, at, x, y, note FROM reperage_radar_positions WHERE site_id = ? AND at >= ? ORDER BY at", (site_id, float(depuis))).fetchall()
                return jsonify({"lignes": [dict(r) for r in rows], "positions": [dict(r) for r in pos]}), 200
            derniers = {}
            q = "SELECT source, MAX(at) AS at FROM reperage_radar WHERE site_id = ?" + (" AND source = ?" if src else "") + " GROUP BY source"
            for r in conn.execute(q, (site_id, src) if src else (site_id,)).fetchall():
                rows = conn.execute("SELECT * FROM reperage_radar WHERE site_id = ? AND source = ? AND at = ? ORDER BY rssi DESC", (site_id, r["source"], r["at"])).fetchall()
                derniers[r["source"]] = {"at": r["at"], "bornes": [dict(x) for x in rows]}
            n = conn.execute("SELECT COUNT(*) AS n, COUNT(DISTINCT scan_id) AS scans, COUNT(DISTINCT bssid) AS bssids, MIN(at) AS debut FROM reperage_radar WHERE site_id = ?", (site_id,)).fetchone()
            npos = conn.execute("SELECT COUNT(*) AS n FROM reperage_radar_positions WHERE site_id = ?", (site_id,)).fetchone()["n"]
            pos = [dict(r) for r in conn.execute("SELECT source, at, x, y, note FROM reperage_radar_positions WHERE site_id = ? ORDER BY at DESC LIMIT 60", (site_id,)).fetchall()]
        finally:
            conn.close()
        return jsonify({"derniers": derniers, "total": n["n"], "scans": n["scans"], "bssids": n["bssids"], "debut": n["debut"], "positions": npos,
                        "positions_recentes": pos, "maintenant": time.time()}), 200

    @app.route("/sites/<site_id>/reperage/radar.csv", methods=["GET"])
    def reperage_radar_csv(site_id):
        conn = conn_fn()
        try:
            rows = [dict(r) for r in conn.execute("SELECT * FROM reperage_radar WHERE site_id = ? ORDER BY at, rssi DESC", (site_id,)).fetchall()]
        finally:
            conn.close()
        return Response(lib.radar_csv(rows), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=radar-%s.csv" % re.sub(r"[^A-Za-z0-9_-]", "_", site_id)})

    @app.route("/sites/<site_id>/reperage/releves", methods=["GET"])
    def reperage_releves(site_id):
        conn = conn_fn()
        try:
            rows = conn.execute("SELECT id, data, at FROM reperage_releves WHERE site_id = ? ORDER BY at", (site_id,)).fetchall()
        finally:
            conn.close()
        return jsonify({"releves": [dict(json.loads(r["data"]), id=r["id"]) for r in rows]}), 200

    @app.route("/sites/<site_id>/reperage/releves", methods=["POST"])
    def reperage_releve_post(site_id):
        b = request.get_json(silent=True) or {}
        m = _mobile(site_id, b.get("mac")) if b.get("mac") else None
        r = lib.releve_depuis_mobile(m or {"mac": lib.norm_mac(b.get("mac") or "")}, b.get("x"), b.get("y"), b.get("note"), b.get("rssi_mobile"))
        if not r:
            return jsonify({"error": "position (x, y) attendue"}), 400
        rid = uuid.uuid4().hex[:10]
        conn = conn_fn()
        try:
            conn.execute("INSERT INTO reperage_releves (id, site_id, data, at) VALUES (?, ?, ?, ?)", (rid, site_id, json.dumps(r, ensure_ascii=False), r["at"]))
            conn.commit()
        finally:
            conn.close()
        return jsonify(dict(r, id=rid)), 201

    @app.route("/sites/<site_id>/reperage/releves/<rid>", methods=["DELETE"])
    def reperage_releve_del(site_id, rid):
        conn = conn_fn()
        try:
            n = conn.execute("DELETE FROM reperage_releves WHERE site_id = ? AND id = ?", (site_id, rid)).rowcount
            conn.commit()
        finally:
            conn.close()
        return jsonify({"supprime": n}), 200

    # -- sonde filaire (#959) : Raspberry Pi branché prise par prise (LLDP) ou en sortie de panneau de brassage ---------------
    def _sonde_row(r):
        d = json.loads(r["data"]); d.update(id=r["id"], source=r["source"], mode=r["mode"], at=r["at"], maj=r["maj"], prise=r["prise"], ack=bool(r["ack_at"]), ack_at=r["ack_at"])
        return d

    def _sonde_rapprocher(site_id, rel, force=False):
        """Nebula met ~1 min à voir un nouveau client : si la MAC n'est pas dans l'inventaire en cache et que le cache a
        plus de 20 s, on relit (une relecture par relevé au plus, le script renvoie le relevé toutes les 15 s)."""
        inv = _inventaire(site_id, mac_mobile=rel.get("mac"))
        r = lib.rapprocher_sonde(rel, inv, _prises(site_id))
        c = _cache.get(site_id)
        if r["confirme"] is None and (force or (c and time.time() - c["at"] > 20)) and site_id != lib.SITE_TEST:
            inv = _inventaire(site_id, force=True, mac_mobile=rel.get("mac"))
            r = lib.rapprocher_sonde(rel, inv, _prises(site_id))
        return r

    @app.route("/sites/<site_id>/reperage/sonde", methods=["POST"])
    def reperage_sonde_post(site_id):
        rel, err = lib.valider_sonde(request.get_json(silent=True) or {})
        if err:
            return jsonify({"error": err}), 400
        now = int(time.time())
        r = _sonde_rapprocher(site_id, rel, force=request.args.get("refresh") == "1")
        conn = conn_fn()
        try:
            row = conn.execute("SELECT * FROM reperage_sonde WHERE site_id = ? AND id = ? AND ack_at IS NULL", (site_id, rel["id"])).fetchone() if rel.get("id") else None
            stock = {k: v for k, v in r.items() if k not in ("id", "prise_connue")}
            if row:
                conn.execute("UPDATE reperage_sonde SET data = ?, maj = ? WHERE id = ?", (json.dumps(stock, ensure_ascii=False), now, row["id"])); rid = row["id"]; at = row["at"]
            else:
                rid = conn.execute("INSERT INTO reperage_sonde (site_id, source, mode, at, maj, data) VALUES (?, ?, ?, ?, ?, ?)",
                                   (site_id, rel["source"], rel["mode"], now, now, json.dumps(stock, ensure_ascii=False))).lastrowid; at = now
            conn.commit()
        finally:
            conn.close()
        r.update(id=rid, at=at, maj=now, ack=False)
        return jsonify(r), 200

    @app.route("/sites/<site_id>/reperage/sonde", methods=["GET"])
    def reperage_sonde_get(site_id):
        lim = max(1, min(int(request.args.get("limit") or 50), 500)); src = request.args.get("source")
        conn = conn_fn()
        try:
            q = "SELECT * FROM reperage_sonde WHERE site_id = ?" + (" AND source = ?" if src else "") + " ORDER BY at DESC LIMIT ?"
            rows = conn.execute(q, (site_id, src, lim) if src else (site_id, lim)).fetchall()
        finally:
            conn.close()
        out = [_sonde_row(x) for x in rows]
        prises = _prises(site_id)
        for d in out:
            sw, po = (d.get("commutateur") or "").lower(), d.get("port")
            d["prise_connue"] = next((p for p in prises if po is not None and p.get("port") == po and (p.get("commutateur") or "").lower() == sw), None)
        return jsonify({"releves": out, "en_attente": [d["id"] for d in out if not d["ack"]]}), 200

    @app.route("/sites/<site_id>/reperage/sonde/etat", methods=["GET"])
    def reperage_sonde_etat(site_id):
        """Pour la sonde (sans écran) : son dernier relevé est-il validé sur le téléphone ?"""
        src = request.args.get("source") or ""
        conn = conn_fn()
        try:
            row = conn.execute("SELECT * FROM reperage_sonde WHERE site_id = ? AND source = ? ORDER BY at DESC LIMIT 1", (site_id, src)).fetchone()
        finally:
            conn.close()
        if not row:
            return jsonify({"derniere": None}), 200
        d = _sonde_row(row)
        return jsonify({"derniere": {"id": d["id"], "ack": d["ack"], "prise": d["prise"], "commutateur": d.get("commutateur"), "port": d.get("port"), "confirme": d.get("confirme")}}), 200

    @app.route("/sites/<site_id>/reperage/sonde/<int:rid>/valider", methods=["POST"])
    def reperage_sonde_valider(site_id, rid):
        """Le téléphone nomme la prise (ou la position de brassage) : enregistre la prise, acquitte le relevé (la sonde voit `ack`)."""
        body = request.get_json(silent=True) or {}
        conn = conn_fn()
        try:
            row = conn.execute("SELECT * FROM reperage_sonde WHERE site_id = ? AND id = ?", (site_id, rid)).fetchone()
        finally:
            conn.close()
        if not row:
            return jsonify({"error": "relevé inconnu"}), 404
        rel = _sonde_row(row)
        now = int(time.time())
        prise = None
        if not body.get("ignorer"):
            existante = next((p for p in _prises(site_id) if p.get("prise") == (body.get("prise") or "").strip()), None)
            p, err = lib.valider_prise(lib.fusion_prise_sonde(existante, rel, body))
            if err:
                return jsonify({"error": err}), 400
            conn = conn_fn()
            try:
                conn.execute("INSERT INTO reperage_prises (site_id, prise, data, updated_at, updated_by) VALUES (?, ?, ?, ?, ?) "
                             "ON CONFLICT(site_id, prise) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                             (site_id, p["prise"], json.dumps(p, ensure_ascii=False), now, (body.get("par") or "sonde")[:80]))
                conn.commit()
            finally:
                conn.close()
            prise = p["prise"]
        conn = conn_fn()
        try:
            conn.execute("UPDATE reperage_sonde SET ack_at = ?, prise = ? WHERE id = ?", (now, prise, rid)); conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True, "id": rid, "prise": prise, "ack_at": now}), 200

    @app.route("/sites/<site_id>/reperage/sonde/<int:rid>", methods=["DELETE"])
    def reperage_sonde_suppr(site_id, rid):
        conn = conn_fn()
        try:
            n = conn.execute("DELETE FROM reperage_sonde WHERE site_id = ? AND id = ?", (site_id, rid)).rowcount; conn.commit()
        finally:
            conn.close()
        return jsonify({"supprime": n}), 200

    # -- registre des équipements du site (#960) : nom, rôle, IP, MAC, position, local, prise, étiquettes ------------------
    def _equipements(site_id):
        conn = conn_fn()
        try:
            rows = conn.execute("SELECT id, data, created_at, updated_at, updated_by FROM reperage_equipements WHERE site_id = ?", (site_id,)).fetchall()
        finally:
            conn.close()
        out = []
        for r in rows:
            d = json.loads(r["data"]); d.update(id=r["id"], cree=r["created_at"], maj=r["updated_at"], par=r["updated_by"]); out.append(d)
        out.sort(key=lambda e: ((e.get("local") or "~").lower(), (e.get("nom") or e.get("ip") or "").lower()))
        return out

    def _enregistrer_eq(site_id, e, par):
        now = int(time.time())
        eid = e.get("id") or uuid.uuid4().hex[:12]
        data = {k: v for k, v in e.items() if k not in ("id", "nebula", "alertes", "cree", "maj", "par")}
        conn = conn_fn()
        try:
            conn.execute("INSERT INTO reperage_equipements (site_id, id, data, created_at, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?) "
                         "ON CONFLICT(site_id, id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                         (site_id, eid, json.dumps(data, ensure_ascii=False), now, now, (par or "")[:80] or None))
            conn.commit()
        finally:
            conn.close()
        return eid

    def _eq_enrichis(site_id):
        eqs = _equipements(site_id)
        try:
            inv = _inventaire(site_id)
            err = inv.get("erreurs") or []
        except Exception as exc:  # noqa: BLE001 -- sans Nebula, le registre reste utilisable
            inv, err = {"clients": []}, ["Nebula : %s" % str(exc)[:160]]
        return lib.enrichir_equipements(eqs, inv), err

    @app.route("/sites/<site_id>/reperage/equipements", methods=["GET"])
    def reperage_equipements_get(site_id):
        eqs, err = _eq_enrichis(site_id)
        roles = sorted({e["role"] for e in eqs if e.get("role")}, key=str.lower)
        tags = sorted({t for e in eqs for t in e.get("tags") or []})
        locaux = sorted({e["local"] for e in eqs if e.get("local")}, key=str.lower)
        return jsonify({"site_id": site_id, "equipements": eqs, "roles": roles, "tags": tags, "locaux": locaux, "erreurs": err}), 200

    @app.route("/sites/<site_id>/reperage/equipements", methods=["PUT"])
    def reperage_equipement_put(site_id):
        body = request.get_json(silent=True) or {}
        e, err = lib.valider_equipement(body)
        if err:
            return jsonify({"error": err}), 400
        eid = _enregistrer_eq(site_id, e, body.get("par"))
        eqs, _ = _eq_enrichis(site_id)
        return jsonify(next(x for x in eqs if x["id"] == eid)), 200

    @app.route("/sites/<site_id>/reperage/equipements/<eid>", methods=["DELETE"])
    def reperage_equipement_delete(site_id, eid):
        conn = conn_fn()
        try:
            n = conn.execute("DELETE FROM reperage_equipements WHERE site_id = ? AND id = ?", (site_id, eid)).rowcount; conn.commit()
        finally:
            conn.close()
        return jsonify({"supprime": n}), 200

    @app.route("/sites/<site_id>/reperage/equipements.csv", methods=["GET"])
    def reperage_equipements_csv(site_id):
        eqs, _ = _eq_enrichis(site_id)
        return Response(lib.equipements_csv(eqs), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": "attachment; filename=equipements-%s.csv" % re.sub(r"[^A-Za-z0-9_-]", "_", site_id)})

    @app.route("/sites/<site_id>/reperage/equipements/import", methods=["POST"])
    def reperage_equipements_import(site_id):
        """CSV (fichier `file` ou texte JSON {texte}) : ajoute ; une ligne dont la MAC ou l'IP existe déjà met à jour la fiche."""
        texte = request.files["file"].read().decode("utf-8", "replace") if "file" in request.files else (request.get_json(silent=True) or {}).get("texte", "")
        lignes, erreurs = lib.lire_csv_equipements(texte)
        existants = _equipements(site_id)
        ajout = maj = 0
        for e in lignes:
            prev = next((x for x in existants if (e["mac"] and x.get("mac") == e["mac"]) or (e["ip"] and x.get("ip") == e["ip"])), None)
            if prev:
                fusion = dict(prev); fusion.update({k: v for k, v in e.items() if v not in (None, [], "") and k != "id"})
                fusion["tags"] = lib.norm_tags((prev.get("tags") or []) + (e.get("tags") or []))
                _enregistrer_eq(site_id, fusion, "import"); maj += 1
            else:
                _enregistrer_eq(site_id, e, "import"); ajout += 1
        return jsonify({"ajoutes": ajout, "mis_a_jour": maj, "erreurs": erreurs}), 200
