# -*- coding: utf-8 -*-
"""#857 : routes /etat-des-lieux (état, libellés, dates de fin, export Excel, historique quotidien)."""
import io
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ["ACCES_THREAD"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import test_z_etat as TE  # noqa: E402

REP = [("ag1", "deb13", "2026-10-26T10:00:00", {"nodes": [dict(v, name=k) for k, v in TE.NODES.items() if v.get("ok", True)]})]


class Routes(unittest.TestCase):
    def setUp(self):
        self.avant = appmod.infra.latest
        appmod.infra.latest = lambda conn, t: REP if t == "plugin:pve-preflight" else []
        self.c = appmod.app.test_client()

    def tearDown(self):
        appmod.infra.latest = self.avant

    def test_etat_libelles_eol_export(self):
        r = self.c.get("/etat-des-lieux").get_json()
        self.assertTrue(r["systemes"])
        self.assertEqual(len(r["tendance"]), 1)                                       # une ligne pour aujourd'hui
        self.assertEqual(self.c.put("/etat-des-lieux/libelles", json={"libelles": []}).status_code, 400)
        self.c.put("/etat-des-lieux/libelles", json={"libelles": {"pve-2/100": "Partage de fichiers"}})
        r = self.c.get("/etat-des-lieux").get_json()
        self.assertEqual(next(l for l in r["systemes"] if l["key"] == "pve-2/100")["libelle"], "Partage de fichiers")
        self.assertEqual(self.c.put("/etat-des-lieux/eol", json={"eol": {"debian": {"9": "demain"}}}).status_code, 400)
        self.assertEqual(self.c.put("/etat-des-lieux/eol", json={"eol": {"debian": {"9": "2030-01-01"}}}).get_json()["eol"]["debian"]["12"], "2028-06-30")
        r = self.c.get("/etat-des-lieux").get_json()
        self.assertEqual(next(l for l in r["systemes"] if l["key"] == "pve-2/100")["os"]["statut"], "supporté")
        x = self.c.get("/etat-des-lieux/export.xlsx")
        self.assertEqual(x.status_code, 200)
        self.assertIn("etat-des-lieux-", x.headers["Content-Disposition"])
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(x.data))
        self.assertIn("Partage de fichiers", [c.value for c in wb["Systèmes"]["A"]])


if __name__ == "__main__":
    unittest.main()
