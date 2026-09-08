"""Tests de ups-monitor-api (livraison #415) :
`cd ups-monitor/api && UPS_POLL_ENABLED=false python3 -m unittest test_ups_monitor.py`

Parseur sur la page RÉELLE copiée par la personne (samples/), store et
automate sur base SQLite temporaire, routes via app.test_client() avec un
faux serveur HTTP (opener injecté) -- aucun onduleur réel ici.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["UPS_POLL_ENABLED"] = "false"
os.environ["UPS_MONITOR_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "ups.db")

import ups_parser  # noqa: E402
import store  # noqa: E402
import alerts  # noqa: E402
import poller  # noqa: E402
import app as app_module  # noqa: E402

SAMPLE = open(os.path.join(HERE, "samples", "netys_rt_index.htm"), encoding="iso-8859-1").read()


class FakeResponse(io.BytesIO):
    def __init__(self, body, charset="iso-8859-1"):
        super().__init__(body)
        self.headers = self
        self._charset = charset

    def get_content_charset(self):
        return self._charset

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make_opener(pages, seen=None):
    """pages : {url: html | Exception}. `seen` reçoit les requêtes."""
    def opener(req, timeout=None):
        if seen is not None:
            seen.append(req)
        target = pages.get(req.full_url)
        if isinstance(target, Exception):
            raise target
        if target is None:
            raise urllib.error.HTTPError(req.full_url, 404, "not found", {}, None)
        return FakeResponse(target.encode("iso-8859-1"))
    return opener


class ParserTests(unittest.TestCase):
    def test_page_reelle_tous_les_champs(self):
        r = ups_parser.parse_ups_page(SAMPLE)
        self.assertEqual(r["title"], "UPS Management Web")
        self.assertEqual(r["system_time"], "09/07/2026 Monday 09:00:58")
        self.assertEqual([s["title"] for s in r["sections"]], ["UPS Status", "UPS Measurement", "Schedule", "Countdown Timer"])
        self.assertEqual(r["field_count"], 14)
        f = r["fields"]
        self.assertEqual(f["model"]["value"], "NETYS RT 1/1 UPS")
        self.assertEqual(f["input_voltage"]["number"], 236.0)
        self.assertEqual(f["input_voltage"]["unit"], "V")
        self.assertEqual(f["output_frequency"]["number"], 49.9)
        self.assertEqual(f["output_load"]["number"], 8.0)
        self.assertEqual(f["battery_capacity"]["value"], "100 %")
        self.assertEqual(f["next_power_off"]["value"], "", "champ vide conservé : rien de programmé")
        self.assertEqual(f["next_test"]["value"], "09/07/2026 15:00")
        self.assertEqual(f["model"]["css"], "bold")
        self.assertEqual(f["communication"]["css"], "normal")
        self.assertEqual(f["input_voltage"]["section"], "UPS Measurement")

    def test_etat_global(self):
        f = ups_parser.parse_ups_page(SAMPLE)["fields"]
        self.assertEqual(ups_parser.derive_state(f), ("ok", []))
        degraded = SAMPLE.replace('<td CLASS="normal">Normal</td>', '<td CLASS="alarm">On Battery</td>', 1)
        state, reasons = ups_parser.derive_state(ups_parser.parse_ups_page(degraded)["fields"])
        self.assertEqual(state, "alarm")
        self.assertEqual(reasons, ["Output Source : On Battery"])
        self.assertEqual(ups_parser.derive_state({}), ("unknown", []))

    def test_libelles_inconnus_et_nombres(self):
        html = """<table><tr><td class="title">Battery Parameters</td></tr>
        <tr><td align="right">Battery Voltage:</td><td>27,4 V</td></tr>
        <tr><td align="right">Température interne:</td><td>31 °C</td></tr>
        <tr><td>pas un champ</td><td>x</td></tr></table>"""
        r = ups_parser.parse_ups_page(html)
        self.assertEqual(r["field_count"], 2)
        self.assertEqual(r["fields"]["battery_voltage"]["number"], 27.4, "virgule décimale acceptée")
        self.assertIn("temperature_interne", r["fields"])
        self.assertEqual(r["fields"]["temperature_interne"]["unit"], "°C")
        self.assertEqual(ups_parser.parse_number("OK"), (None, None))
        self.assertEqual(ups_parser.parse_number(None), (None, None))

    def test_page_sans_forme_connue(self):
        r = ups_parser.parse_ups_page("<html><body><h1>Login</h1><form></form></body></html>")
        self.assertEqual(r["field_count"], 0)
        self.assertEqual(r["sections"], [])
        self.assertEqual(ups_parser.parse_ups_page("")["field_count"], 0)
        self.assertEqual(ups_parser.parse_ups_page(None)["field_count"], 0)


class StoreAndPollerTests(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "ups.db")
        store.ensure_schema(self.db)
        self.dev, err = store.create_device(self.db, {
            "name": "Onduleur salle serveurs", "site": "Siège", "host": "192.168.1.107",
            "username": "admin", "password": "secret",
        })
        self.assertIsNone(err)

    def test_validation_et_masquage_du_mot_de_passe(self):
        self.assertEqual(self.dev["path"], "/index.htm")
        self.assertTrue(self.dev["has_password"])
        self.assertNotIn("password", self.dev)
        self.assertEqual(store.create_device(self.db, {"name": "x"})[1], "'host' requis (IP ou nom)")
        self.assertIn("sans schéma", store.create_device(self.db, {"name": "x", "host": "http://1.2.3.4"})[1])
        self.assertIn("30 s minimum", store.create_device(self.db, {"name": "x", "host": "1.2.3.4", "poll_interval_seconds": 5})[1])
        self.assertIn("entier", store.create_device(self.db, {"name": "x", "host": "1.2.3.4", "poll_interval_seconds": "abc"})[1])
        # Mise à jour sans mot de passe = inchangé ; clear_password = effacé
        updated, err = store.update_device(self.db, self.dev["id"], {"site": "Annexe", "password": ""})
        self.assertIsNone(err)
        self.assertEqual(updated["site"], "Annexe")
        self.assertEqual(store.get_device(self.db, self.dev["id"], include_secret=True)["password"], "secret")
        store.update_device(self.db, self.dev["id"], {"clear_password": True})
        self.assertFalse(store.get_device(self.db, self.dev["id"])["has_password"])
        self.assertEqual(store.update_device(self.db, 999, {"name": "x"})[1], "onduleur inconnu")

    def test_releve_reussi_archive_et_denormalise(self):
        seen = []
        opener = make_opener({"http://192.168.1.107/index.htm": SAMPLE}, seen)
        device = store.get_device(self.db, self.dev["id"], include_secret=True)
        result = poller.poll_device(device, opener=opener, now_iso="2026-09-07T09:00:00Z")
        self.assertTrue(result["ok"])
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["summary"]["input_voltage"], "236.0 V")
        self.assertEqual(seen[0].get_header("Authorization"), "Basic YWRtaW46c2VjcmV0", "user:password@ → Basic")
        store.record_reading(self.db, device["id"], result)
        d = store.get_device(self.db, device["id"])
        self.assertEqual(d["last_polled_at"], "2026-09-07T09:00:00Z")
        self.assertTrue(d["last_ok"])
        self.assertEqual(d["last_state"], "ok")
        latest = store.latest_reading(self.db, device["id"])
        self.assertEqual(latest["input_voltage"], 236.0)
        self.assertEqual(latest["battery_capacity"], 100.0)
        self.assertEqual(latest["fields"]["model"]["value"], "NETYS RT 1/1 UPS")
        self.assertEqual(len(latest["sections"]), 4)

    def test_echecs_archives_avec_raison(self):
        device = store.get_device(self.db, self.dev["id"], include_secret=True)
        cases = {
            "http://192.168.1.107/index.htm": urllib.error.HTTPError("u", 401, "unauthorized", {}, None),
        }
        r = poller.poll_device(device, opener=make_opener(cases))
        self.assertFalse(r["ok"])
        self.assertIn("401", r["error"])
        r2 = poller.poll_device(device, opener=make_opener({"http://192.168.1.107/index.htm": urllib.error.URLError("timed out")}))
        self.assertIn("injoignable", r2["error"])
        r3 = poller.poll_device(device, opener=make_opener({"http://192.168.1.107/index.htm": "<html><body>Login</body></html>"}))
        self.assertFalse(r3["ok"])
        self.assertIn("aucun champ reconnu", r3["error"])
        store.record_reading(self.db, device["id"], r3)
        d = store.get_device(self.db, device["id"])
        self.assertFalse(d["last_ok"])
        self.assertIn("aucun champ", d["last_error"])
        self.assertIsNone(store.latest_ok_reading(self.db, device["id"]), "aucune fiche complète encore")

    def test_automate_respecte_intervalle_et_activation(self):
        opener = make_opener({"http://192.168.1.107/index.htm": SAMPLE, "http://10.0.0.9/index.htm": SAMPLE})
        other, _ = store.create_device(self.db, {"name": "B", "host": "10.0.0.9", "poll_interval_seconds": 120})
        t0 = 1_800_000_000
        r = poller.run_tick(self.db, now_ts=t0, opener=opener, default_interval=3600)
        self.assertEqual((r["checked"], r["polled"], r["skipped"]), (2, 2, 0), "jamais relevés : dus")
        r = poller.run_tick(self.db, now_ts=t0 + 30, opener=opener, default_interval=3600)
        self.assertEqual(r["polled"], 0)
        # Le second a un intervalle propre de 120 s : dû après 120 s, le premier (3600 s) non.
        # (last_polled_at est à la seconde : on simule en réécrivant l'horodatage)
        conn = store.get_connection(self.db)
        conn.execute("UPDATE ups_devices SET last_polled_at = '2026-01-01T00:00:00Z' WHERE id = ?", [other["id"]])
        conn.commit(); conn.close()
        r = poller.run_tick(self.db, now_ts=t0 + 30, opener=opener, default_interval=3600)
        self.assertEqual(r["polled"], 1)
        # Désactivé : jamais relevé, sauf forcé
        store.update_device(self.db, other["id"], {"enabled": False})
        conn = store.get_connection(self.db)
        conn.execute("UPDATE ups_devices SET last_polled_at = NULL"); conn.commit(); conn.close()
        r = poller.run_tick(self.db, now_ts=t0 + 10_000, opener=opener, default_interval=3600)
        self.assertEqual(r["polled"], 1)
        r = poller.run_tick(self.db, now_ts=t0 + 10_000, opener=opener, default_interval=3600, force_ids=[other["id"]])
        self.assertEqual(r["polled"], 1)
        self.assertEqual(len(store.list_readings(self.db, other["id"])), 3)

    def test_timeline_et_serie(self):
        device = store.get_device(self.db, self.dev["id"], include_secret=True)
        for i, volt in enumerate([236.0, 238.5, None, 231.0]):
            if volt is None:
                res = poller.poll_device(device, opener=make_opener({}), now_iso=f"2026-09-07T{10 + i:02d}:00:00Z")
            else:
                page = SAMPLE.replace("236.0 V", f"{volt} V")
                res = poller.poll_device(device, opener=make_opener({"http://192.168.1.107/index.htm": page}), now_iso=f"2026-09-07T{10 + i:02d}:00:00Z")
            store.record_reading(self.db, device["id"], res)
        rows = store.list_readings(self.db, device["id"])
        self.assertEqual([r["polled_at"][11:13] for r in rows], ["10", "11", "12", "13"], "du plus ancien au plus récent")
        self.assertEqual([r["ok"] for r in rows], [True, True, False, True])
        self.assertNotIn("fields", rows[0], "compact par défaut")
        window = store.list_readings(self.db, device["id"], start="2026-09-07T11:00:00Z", end="2026-09-07T12:30:00Z")
        self.assertEqual(len(window), 2)
        self.assertEqual(len(store.list_readings(self.db, device["id"], limit=2)), 2)
        self.assertEqual(store.list_readings(self.db, device["id"], limit=2)[0]["polled_at"][11:13], "12", "les plus récents")
        s = store.field_series(self.db, device["id"], "input_voltage")
        self.assertEqual([p["number"] for p in s], [236.0, 238.5, 231.0], "l'échec n'a pas de point")
        self.assertEqual(s[0]["unit"], "V")
        latest_ok = store.latest_ok_reading(self.db, device["id"])
        self.assertEqual(latest_ok["input_voltage"], 231.0)
        self.assertEqual(store.purge_readings(self.db, "2026-09-07T11:30:00Z"), 2)
        self.assertEqual(store.counts(self.db)["readings"], 2)

    def test_suppression_en_cascade(self):
        device = store.get_device(self.db, self.dev["id"], include_secret=True)
        store.record_reading(self.db, device["id"], poller.poll_device(device, opener=make_opener({"http://192.168.1.107/index.htm": SAMPLE})))
        self.assertTrue(store.delete_device(self.db, device["id"]))
        self.assertFalse(store.delete_device(self.db, device["id"]))
        self.assertEqual(store.counts(self.db), {"devices": 0, "enabled": 0, "readings": 0, "alarms": 0, "unreachable": 0})


class AlertsTests(unittest.TestCase):
    """Livraison #433 : alertes et seuils."""

    def setUp(self):
        os.environ["UPS_NOTIFY_SYNC"] = "1"
        os.environ["UPS_NOTIFY_MIN_SEVERITY"] = "none"
        self.db = os.path.join(tempfile.mkdtemp(), "ups.db")
        store.ensure_schema(self.db)
        self.dev, err = store.create_device(self.db, {"name": "UPS A", "site": "Siège", "host": "192.168.1.107",
                                                     "thresholds": {"input_voltage_min": 235, "output_load_max": 10}, "unreachable_after": 2})
        self.assertIsNone(err, err)

    def test_seuils_valides_et_renvoyes(self):
        d = store.get_device(self.db, self.dev["id"])
        self.assertEqual(d["thresholds"], {"input_voltage_min": 235.0, "output_load_max": 10.0})
        self.assertEqual((d["unreachable_after"], d["notify"]), (2, True))
        _, err = store.create_device(self.db, {"name": "x", "host": "h", "thresholds": {"bizarre": 1}})
        self.assertIn("clé inconnue", err)
        _, err = store.create_device(self.db, {"name": "x", "host": "h", "unreachable_after": 0})
        self.assertIn("1 minimum", err)
        merged = alerts.parse_thresholds({"input_voltage_min": None, "temperature_max": "45"})
        self.assertIsNone(merged["input_voltage_min"]); self.assertEqual(merged["temperature_max"], 45.0); self.assertEqual(merged["output_load_max"], 80.0)

    def test_evaluation_pure(self):
        dev = {"thresholds": {"input_voltage_min": 235, "output_load_max": 10}, "unreachable_after": 2}
        ok_low = {"ok": True, "state": "ok", "input_voltage": 230.0, "output_load": 5}
        to_open, to_close, kept = alerts.evaluate(dev, ok_low, 0, {})
        self.assertEqual([a["kind"] for a in to_open], ["threshold:input_voltage_min"])
        self.assertIn("230 < 235", to_open[0]["message"])
        opened = {"threshold:input_voltage_min": {"kind": "threshold:input_voltage_min"}}
        # 236 V : dans l'hystérésis (235 + 2 % = 239,7) -> reste ouverte
        _, to_close, kept = alerts.evaluate(dev, {"ok": True, "state": "ok", "input_voltage": 236.0}, 0, opened)
        self.assertEqual((to_close, kept), ([], ["threshold:input_voltage_min"]))
        _, to_close, _ = alerts.evaluate(dev, {"ok": True, "state": "ok", "input_voltage": 241.0}, 0, opened)
        self.assertEqual(to_close, ["threshold:input_voltage_min"])
        # échec : rien ne se ferme, injoignable après 2
        to_open, to_close, kept = alerts.evaluate(dev, {"ok": False, "error": "timeout"}, 1, opened)
        self.assertEqual((to_open, to_close, kept), ([], [], ["threshold:input_voltage_min"]))
        to_open, _, _ = alerts.evaluate(dev, {"ok": False, "error": "timeout"}, 2, opened)
        self.assertEqual([a["kind"] for a in to_open], ["unreachable"])
        # alarme de la carte, puis retour
        to_open, _, _ = alerts.evaluate(dev, {"ok": True, "state": "alarm", "state_reasons": ["Battery : Low"]}, 0, {})
        self.assertEqual(to_open[0]["kind"], "alarm"); self.assertEqual(to_open[0]["severity"], "critical")
        _, to_close, _ = alerts.evaluate(dev, {"ok": True, "state": "ok"}, 0, {"alarm": {}, "unreachable": {}})
        self.assertEqual(sorted(to_close), ["alarm", "unreachable"])
        self.assertEqual(alerts.stale_check({"enabled": True, "poll_interval_seconds": 60}, 1000, 800, 3600), (True, "aucun relevé depuis 3 min (intervalle 60 s)"))
        self.assertEqual(alerts.stale_check({"enabled": True, "poll_interval_seconds": 60}, 1000, 900, 3600)[0], False)

    def test_automate_ouvre_ferme_et_notifie(self):
        sent = []
        import notify as notify_mod
        notify_mod.secrets_alert = None
        os.environ["UPS_NOTIFY_MIN_SEVERITY"] = "warning"
        os.environ["UPS_NOTIFY_WEBHOOK_URL"] = "http://webhook.test/x"
        real_send = notify_mod.send_all
        notify_mod.send_all = lambda device, alert, closing=False: (sent.append((device["name"], alert["kind"], closing)) or {"webhook": True, "at": "now"})
        try:
            t0 = 1_700_000_000
            page_ok = SAMPLE  # 236 V > 235, charge 0 % : rien ; puis seuil de charge à 10 % franchi par la page ? non -> on force par un seuil bas
            store.update_device(self.db, self.dev["id"], {"thresholds": {"input_voltage_min": 240, "output_load_max": 80}})
            opener = make_opener({"http://192.168.1.107/index.htm": page_ok})
            r = poller.run_tick(self.db, now_ts=t0, opener=opener, default_interval=3600)
            self.assertEqual((r["polled"], r["alerts_opened"]), (1, 1), "236 V < 240 V : seuil ouvert")
            active = store.list_alerts(self.db, active_only=True)
            self.assertEqual([a["kind"] for a in active], ["threshold:input_voltage_min"])
            self.assertEqual(active[0]["notified"], {"webhook": True, "at": "now"})
            self.assertEqual(sent, [("UPS A", "threshold:input_voltage_min", False)])
            # deux échecs -> injoignable ; le seuil reste ouvert
            bad = make_opener({"http://192.168.1.107/index.htm": urllib.error.URLError("timed out")})
            poller.run_tick(self.db, now_ts=t0 + 4000, opener=bad, default_interval=3600)
            r = poller.run_tick(self.db, now_ts=t0 + 8000, opener=bad, default_interval=3600)
            self.assertEqual(r["alerts_opened"], 1)
            self.assertEqual(sorted(a["kind"] for a in store.list_alerts(self.db)), ["threshold:input_voltage_min", "unreachable"])
            # acquittement, puis retour : injoignable fermée (pas de notification de rétablissement car acquittée)
            ua = next(a for a in store.list_alerts(self.db) if a["kind"] == "unreachable")
            self.assertEqual(store.ack_alert(self.db, ua["id"], "freg"), 1)
            store.update_device(self.db, self.dev["id"], {"thresholds": {"input_voltage_min": 200}})
            r = poller.run_tick(self.db, now_ts=t0 + 12000, opener=opener, default_interval=3600)
            self.assertEqual(r["alerts_closed"], 2, "injoignable et seuil (236 > 200 + 2 %) fermés")
            self.assertEqual(store.list_alerts(self.db), [])
            closed = store.list_alerts(self.db, active_only=False)
            self.assertEqual(len(closed), 2); self.assertTrue(all(a["closed_at"] for a in closed))
            self.assertEqual([x for x in sent if x[2]], [("UPS A", "threshold:input_voltage_min", True)], "rétablissement notifié seulement pour l'alerte non acquittée")
        finally:
            notify_mod.send_all = real_send
            os.environ.pop("UPS_NOTIFY_WEBHOOK_URL", None)


class RoutesTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        # Base propre par test
        conn = store.get_connection(app_module.DB_PATH)
        conn.execute("DELETE FROM ups_readings"); conn.execute("DELETE FROM ups_devices"); conn.commit(); conn.close()
        self._orig_open = poller.urllib.request.urlopen
        poller.urllib.request.urlopen = make_opener({"http://192.168.1.107/index.htm": SAMPLE})

    def tearDown(self):
        poller.urllib.request.urlopen = self._orig_open

    def test_cycle_complet(self):
        r = self.client.post("/ups", json={"name": "Salle serveurs", "site": "Siège", "host": "192.168.1.107", "username": "admin", "password": "pw"})
        self.assertEqual(r.status_code, 201, r.get_json())
        ups_id = r.get_json()["id"]
        self.assertNotIn("password", r.get_json())
        self.assertEqual(self.client.post("/ups", json={"name": "x"}).status_code, 400)

        listing = self.client.get("/ups").get_json()
        self.assertEqual(len(listing), 1)
        self.assertIsNone(listing[0]["last_polled_at"])

        r = self.client.post(f"/ups/{ups_id}/poll")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        self.assertNotIn("url", r.get_json())
        self.assertEqual(r.get_json()["fields"]["battery_capacity"]["number"], 100.0)

        fiche = self.client.get(f"/ups/{ups_id}").get_json()
        self.assertEqual(fiche["device"]["last_state"], "ok")
        self.assertEqual(fiche["latest"]["fields"]["model"]["value"], "NETYS RT 1/1 UPS")
        self.assertEqual(fiche["latest_ok"]["id"], fiche["latest"]["id"])
        self.assertEqual(fiche["url"], "http://192.168.1.107/index.htm")

        rows = self.client.get(f"/ups/{ups_id}/readings").get_json()["readings"]
        self.assertEqual(len(rows), 1)
        self.assertNotIn("fields", rows[0])
        rows = self.client.get(f"/ups/{ups_id}/readings?fields=1").get_json()["readings"]
        self.assertIn("fields", rows[0])
        series = self.client.get(f"/ups/{ups_id}/series?key=output_load").get_json()
        self.assertEqual(series["points"][0]["number"], 8.0)
        self.assertEqual(self.client.get(f"/ups/{ups_id}/series").status_code, 400)

        r = self.client.put(f"/ups/{ups_id}", json={"poll_interval_seconds": 600, "enabled": False})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["poll_interval_seconds"], 600)
        self.assertFalse(r.get_json()["enabled"])
        self.assertTrue(r.get_json()["has_password"], "mot de passe conservé")

        st = self.client.get("/status").get_json()
        self.assertEqual(st["counts"]["devices"], 1)
        self.assertEqual(st["settings"]["default_interval_seconds"], 3600)
        self.assertFalse(st["settings"]["poll_enabled"])

        self.assertEqual(self.client.delete(f"/ups/{ups_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"/ups/{ups_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/ups/{ups_id}").status_code, 404)
        self.assertEqual(self.client.post(f"/ups/{ups_id}/poll").status_code, 404)

    def test_essai_sans_enregistrement(self):
        r = self.client.post("/ups/test", json={"name": "essai", "host": "192.168.1.107", "username": "u", "password": "p"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual(self.client.get("/ups").get_json(), [], "rien d'enregistré")
        r = self.client.post("/ups/test", json={"name": "essai", "host": "10.9.9.9"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["ok"])
        self.assertIn("HTTP 404", r.get_json()["error"])
        self.assertEqual(self.client.post("/ups/test", json={"host": "10.9.9.9"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()


class RealHttpTests(unittest.TestCase):
    """Un vrai serveur HTTP local avec authentification Basic, interrogé par
    le vrai urllib : vérifie le chemin réseau complet (en-tête Authorization,
    401 sans identifiants, décodage iso-8859-1), pas seulement le faux opener."""

    @classmethod
    def setUpClass(cls):
        import base64
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        expected = "Basic " + base64.b64encode(b"admin:pw").decode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.headers.get("Authorization") != expected:
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", 'Basic realm="UPS"')
                    self.end_headers()
                    return
                body = SAMPLE.encode("iso-8859-1")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=iso-8859-1")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_basic_reel(self):
        device = {"host": f"127.0.0.1:{self.port}", "path": "/index.htm", "username": "admin", "password": "pw"}
        r = poller.poll_device(device)
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["fields"]["input_voltage"]["number"], 236.0)
        bad = poller.poll_device(dict(device, password="mauvais"))
        self.assertFalse(bad["ok"])
        self.assertIn("401", bad["error"])
        nobody = poller.poll_device({"host": "127.0.0.1:1", "path": "/index.htm"})
        self.assertIn("injoignable", nobody["error"])


class CredentialCryptoTests(unittest.TestCase):
    """Chiffrement optionnel des mots de passe (UPS_CRED_PASSPHRASE / SALT)."""

    def setUp(self):
        import credential_crypto
        self.cc = credential_crypto
        self.db = os.path.join(tempfile.mkdtemp(), "ups.db")
        store.ensure_schema(self.db)
        self._env = {k: os.environ.get(k) for k in ("UPS_CRED_PASSPHRASE", "UPS_CRED_SALT")}

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_clair_sans_configuration_puis_chiffre_avec(self):
        os.environ.pop("UPS_CRED_PASSPHRASE", None); os.environ.pop("UPS_CRED_SALT", None)
        self.assertFalse(self.cc.is_configured())
        dev, _ = store.create_device(self.db, {"name": "A", "host": "1.2.3.4", "password": "clair"})
        self.assertFalse(dev["password_encrypted"])
        raw = store.get_connection(self.db).execute("SELECT password FROM ups_devices").fetchone()[0]
        self.assertEqual(raw, "clair")
        if self.cc.sc is None:
            self.skipTest("cryptography absent ici")
        import base64, secrets
        os.environ["UPS_CRED_PASSPHRASE"] = "phrase-de-test"
        os.environ["UPS_CRED_SALT"] = base64.b64encode(secrets.token_bytes(16)).decode()
        self.assertTrue(self.cc.is_configured())
        # Une modification rechiffre l'ancien mot de passe en clair
        upd, _ = store.update_device(self.db, dev["id"], {"site": "S"})
        self.assertTrue(upd["password_encrypted"])
        raw = store.get_connection(self.db).execute("SELECT password FROM ups_devices").fetchone()[0]
        self.assertTrue(raw.startswith("enc:"))
        self.assertNotIn("clair", raw)
        self.assertEqual(store.get_device(self.db, dev["id"], include_secret=True)["password"], "clair")
        # Phrase de passe retirée : relevé en échec explicite, jamais un mot de passe faux
        os.environ["UPS_CRED_PASSPHRASE"] = ""
        secret = store.get_device(self.db, dev["id"], include_secret=True)
        self.assertEqual(secret["password"], "")
        self.assertIn("absents", secret["password_error"])
        r = poller.poll_device(secret, opener=make_opener({}))
        self.assertFalse(r["ok"])
        self.assertIn("absents", r["error"])
        # Mauvaise phrase de passe
        os.environ["UPS_CRED_PASSPHRASE"] = "autre"
        self.assertIn("échoué", store.get_device(self.db, dev["id"], include_secret=True)["password_error"])
        # Une modification sans nouveau mot de passe ne détruit pas le jeton
        store.update_device(self.db, dev["id"], {"site": "T"})
        raw2 = store.get_connection(self.db).execute("SELECT password FROM ups_devices").fetchone()[0]
        self.assertEqual(raw2, raw, "jeton conservé tel quel")
        os.environ["UPS_CRED_PASSPHRASE"] = "phrase-de-test"
        self.assertEqual(store.get_device(self.db, dev["id"], include_secret=True)["password"], "clair", "relisible une fois la phrase revenue")


class FramesetTests(unittest.TestCase):
    """Livraison #416 : « une partie des onduleurs répond avec une frame et
    l'extraction est en échec » -- la page demandée n'est qu'un conteneur
    <frameset>, la fiche est dans une sous-page."""

    FRAMESET = open(os.path.join(HERE, "samples", "frameset_index.htm"), encoding="iso-8859-1").read()
    MENU = "<html><body><table><tr><td><a href='/index.htm'>UPS Information</a></td></tr></table></body></html>"
    TOP = "<html><body><img src='/logo.jpg'></body></html>"

    def setUp(self):
        self.device = {"host": "192.168.1.108", "path": "/index.htm", "username": "admin", "password": "pw"}

    def test_sources_extraites(self):
        srcs = ups_parser.extract_frame_sources(self.FRAMESET)
        self.assertEqual(srcs, ["/top.htm", "/menu.htm", "/ups_status.htm?lang=en"])
        meta = '<html><head><meta http-equiv="Refresh" content="0; URL=/login_ok.htm"></head></html>'
        self.assertEqual(ups_parser.extract_frame_sources(meta), ["/login_ok.htm"])
        iframe = "<html><body><iframe src='status.htm'></iframe><iframe src='javascript:void(0)'></iframe><iframe src='status.htm'></iframe></body></html>"
        self.assertEqual(ups_parser.extract_frame_sources(iframe), ["status.htm"])
        self.assertEqual(ups_parser.extract_frame_sources(SAMPLE), [])
        self.assertEqual(ups_parser.extract_frame_sources(None), [])

    def test_frameset_suivi_jusqu_a_la_fiche(self):
        seen = []
        opener = make_opener({
            "http://192.168.1.108/index.htm": self.FRAMESET,
            "http://192.168.1.108/top.htm": self.TOP,
            "http://192.168.1.108/menu.htm": self.MENU,
            "http://192.168.1.108/ups_status.htm?lang=en": SAMPLE,
        }, seen)
        r = poller.poll_device(self.device, opener=opener)
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["fields"]["input_voltage"]["number"], 236.0)
        self.assertEqual(r["resolved_path"], "/ups_status.htm")
        self.assertEqual(r["pages_visited"], 4)
        self.assertEqual([q.full_url.split("/")[-1] for q in seen], ["index.htm", "top.htm", "menu.htm", "ups_status.htm?lang=en"], "largeur d'abord, dans l'ordre du document")
        self.assertTrue(all(q.get_header("Authorization") for q in seen), "Basic sur chaque sous-page")

    def test_page_directe_pas_de_frame_suivie(self):
        r = poller.poll_device(self.device, opener=make_opener({"http://192.168.1.108/index.htm": SAMPLE}))
        self.assertTrue(r["ok"])
        self.assertEqual(r["resolved_path"], "/index.htm")
        self.assertEqual(r["pages_visited"], 1)

    def test_meta_refresh_et_profondeur(self):
        pages = {
            "http://192.168.1.108/index.htm": '<html><head><meta http-equiv="refresh" content="0;url=/frames.htm"></head></html>',
            "http://192.168.1.108/frames.htm": '<frameset><frame src="/deep.htm"></frameset>',
            "http://192.168.1.108/deep.htm": '<frameset><frame src="/status.htm"></frameset>',  # profondeur 3 : hors limite
            "http://192.168.1.108/status.htm": SAMPLE,
        }
        r = poller.poll_device(self.device, opener=make_opener(pages))
        self.assertFalse(r["ok"], "profondeur 3 non suivie -- borne volontaire")
        self.assertIn("frame(s)", r["error"])
        self.assertIn("fixer « Page »", r["error"])
        # Avec la page d'état fixée à la main : direct
        r2 = poller.poll_device(dict(self.device, path="/status.htm"), opener=make_opener(pages))
        self.assertTrue(r2["ok"])

    def test_frame_vers_autre_hote_ignoree_et_echec_partiel_explique(self):
        pages = {
            "http://192.168.1.108/index.htm": '<frameset><frame src="http://evil.example/x.htm"><frame src="/menu.htm"><frame src="/missing.htm"></frameset>',
            "http://192.168.1.108/menu.htm": self.MENU,
        }
        seen = []
        r = poller.poll_device(self.device, opener=make_opener(pages, seen))
        self.assertFalse(r["ok"])
        self.assertNotIn("evil.example", " ".join(q.full_url for q in seen), "jamais un autre hôte")
        self.assertIn("/missing.htm : HTTP 404", r["error"])
        self.assertIn("/menu.htm", r["error"])

    def test_chemin_effectif_archive_et_conserve_sur_echec(self):
        db = os.path.join(tempfile.mkdtemp(), "ups.db")
        store.ensure_schema(db)
        dev, _ = store.create_device(db, {"name": "F", "host": "192.168.1.108", "username": "admin", "password": "pw"})
        d = store.get_device(db, dev["id"], include_secret=True)
        pages = {"http://192.168.1.108/index.htm": self.FRAMESET, "http://192.168.1.108/ups_status.htm?lang=en": SAMPLE}
        store.record_reading(db, d["id"], poller.poll_device(d, opener=make_opener(pages)))
        self.assertEqual(store.get_device(db, d["id"])["last_resolved_path"], "/ups_status.htm")
        self.assertEqual(store.latest_reading(db, d["id"])["resolved_path"], "/ups_status.htm")
        store.record_reading(db, d["id"], poller.poll_device(d, opener=make_opener({})))
        self.assertEqual(store.get_device(db, d["id"])["last_resolved_path"], "/ups_status.htm", "conservé sur échec")
        # Base créée AVANT #416 (sans les colonnes) : ensure_schema les ajoute
        old = os.path.join(tempfile.mkdtemp(), "old.db")
        import sqlite3
        c = sqlite3.connect(old)
        c.executescript(store.SCHEMA.replace(",\n    resolved_path TEXT", ""))
        c.close()
        store.ensure_schema(old)
        cols = [r[1] for r in sqlite3.connect(old).execute("PRAGMA table_info(ups_readings)")]
        self.assertIn("resolved_path", cols)


class NetVisionV6Tests(unittest.TestCase):
    """Livraison #417 : pages RÉELLES d'une carte SOCOMEC Net Vision v6.01
    (ITYS 3 kVA) copiées par la personne -- frameset Logo/Menu/Content, menu
    en JavaScript, « Synthèse ASI » mêlant lignes HTML (TD ID=TH1 + table
    imbriquée) et lignes écrites par CheckParameter()."""

    INDEX = open(os.path.join(HERE, "samples", "netvision_v6_index.html"), encoding="iso-8859-1").read()
    MENU = open(os.path.join(HERE, "samples", "netvision_v6_menu.html"), encoding="iso-8859-1").read()
    CONTENT = open(os.path.join(HERE, "samples", "netvision_v6_comprehensive.html"), encoding="iso-8859-1").read()

    def test_synthese_asi_complete(self):
        r = ups_parser.parse_ups_page(self.CONTENT)
        self.assertEqual(r["flavor"], "netvision-v6")
        self.assertEqual(r["title"], "Comprehensive View")
        self.assertEqual([s["title"] for s in r["sections"]], ["Identification", "Synthèse ASI"])
        self.assertEqual(r["field_count"], 12)
        f = r["fields"]
        self.assertEqual(f["model"]["value"], "ITYS 3 kVA")
        self.assertEqual(f["serial_number"]["value"], "3I13B00169")
        self.assertEqual(f["ups_state"]["value"], "Utilisation sur Onduleur")
        self.assertEqual(f["ups_state"]["label"], "État de l'ASI")
        self.assertEqual((f["output_load"]["number"], f["output_load"]["unit"]), (5.0, "%"), "unité prise dans le libellé")
        self.assertEqual((f["output_voltage"]["number"], f["output_voltage"]["unit"]), (230.0, "V"))
        self.assertEqual((f["input_voltage"]["number"], f["input_voltage"]["unit"]), (235.0, "V"))
        self.assertEqual(f["input_voltage"]["label"], "Tension d'entrée Redresseur")
        self.assertEqual((f["battery_capacity"]["number"], f["battery_capacity"]["unit"]), (0.0, "%"))
        self.assertEqual((f["temperature"]["number"], f["temperature"]["unit"]), (33.0, "°C"), "<SUP>o</SUP>C → °C")
        self.assertEqual(f["battery_runtime"]["value"], "", "<BR> = non disponible, conservé vide")
        self.assertEqual(f["battery_runtime"]["unit"], "minutes")
        self.assertEqual(f["battery_voltage"]["value"], "")
        self.assertEqual(f["device_date"]["value"], "07/09/2026")
        self.assertEqual(f["device_date"]["unit"], None, "(dd/mm/yyyy) est un format, pas une unité")
        self.assertEqual(f["device_time"]["value"], "14:21:49")
        self.assertEqual(r["system_time"], "07/09/2026 14:21:49")
        self.assertEqual(ups_parser.display_value(f["output_voltage"]), "230.0 V")
        self.assertEqual(ups_parser.display_value(f["ups_state"]), "Utilisation sur Onduleur")
        self.assertEqual(ups_parser.display_value(f["battery_runtime"]), "")
        # Ordre du document conservé (HTML, puis JS, puis HTML)
        keys = [x["key"] for x in r["sections"][1]["fields"]]
        self.assertEqual(keys, ["ups_state", "output_load", "output_voltage", "battery_capacity", "battery_runtime",
                                "battery_voltage", "input_voltage", "temperature", "device_date", "device_time"])

    def test_etat_asi(self):
        f = ups_parser.parse_ups_page(self.CONTENT)["fields"]
        self.assertEqual(ups_parser.derive_state(f), ("ok", []))
        degraded = self.CONTENT.replace("Utilisation sur Onduleur", "Utilisation sur Batterie")
        state, reasons = ups_parser.derive_state(ups_parser.parse_ups_page(degraded)["fields"])
        self.assertEqual(state, "alarm")
        self.assertEqual(reasons, ["État de l'ASI : Utilisation sur Batterie"])

    def test_menu_et_logo_sans_champ_ni_frame(self):
        self.assertEqual(ups_parser.parse_ups_page(self.MENU)["field_count"], 0)
        self.assertEqual(ups_parser.extract_frame_sources(self.MENU), [])
        self.assertEqual(ups_parser.extract_frame_sources(self.INDEX), ["./Logo.html", "./Menu.html", "./PageMonComprehensive.html"])
        # META REFRESH CONTENT="15" sans url : pas une redirection
        self.assertEqual(ups_parser.extract_frame_sources(self.CONTENT), [])

    def test_chaine_complete_depuis_index(self):
        seen = []
        opener = make_opener({
            "http://192.168.1.99/index.htm": self.INDEX,
            "http://192.168.1.99/Logo.html": "<html><body><img src='logo.gif'></body></html>",
            "http://192.168.1.99/Menu.html": self.MENU,
            "http://192.168.1.99/PageMonComprehensive.html": self.CONTENT,
        }, seen)
        r = poller.poll_device({"host": "192.168.1.99", "path": "/index.htm", "username": "admin", "password": "pw"}, opener=opener)
        self.assertTrue(r["ok"], r["error"])
        self.assertEqual(r["resolved_path"], "/PageMonComprehensive.html")
        self.assertEqual(r["pages_visited"], 4)
        self.assertEqual(r["flavor"], "netvision-v6")
        self.assertEqual(r["summary"]["output_voltage"], "230.0 V")
        self.assertEqual(r["summary"]["ups_state"], "Utilisation sur Onduleur")
        self.assertEqual(r["summary"]["temperature"], "33 °C")
        self.assertEqual(r["system_time"], "07/09/2026 14:21:49")
        # Page fixée à la main : une seule lecture
        r2 = poller.poll_device({"host": "192.168.1.99", "path": "/PageMonComprehensive.html", "username": "admin", "password": "pw"}, opener=opener)
        self.assertTrue(r2["ok"])
        self.assertEqual(r2["pages_visited"], 1)
        # Archivage : colonnes extraites et série
        db = os.path.join(tempfile.mkdtemp(), "ups.db")
        store.ensure_schema(db)
        dev, _ = store.create_device(db, {"name": "ITYS", "host": "192.168.1.99", "path": "/PageMonComprehensive.html"})
        store.record_reading(db, dev["id"], r2)
        latest = store.latest_reading(db, dev["id"])
        self.assertEqual((latest["input_voltage"], latest["output_voltage"], latest["output_load"], latest["battery_capacity"]), (235.0, 230.0, 5.0, 0.0))
        self.assertEqual(store.field_series(db, dev["id"], "temperature")[0]["number"], 33.0)
