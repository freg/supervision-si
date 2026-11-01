import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import campus  # noqa: E402


class Campus(unittest.TestCase):
    def test_assets(self):
        rows = [["Nom", "Type", "Modèle", "Numero de série", "Adresse MAC", "Lab", "Localisation", "Commentaire"],
                ["PC01 Alpha", "Ordinateur portable", "Book 4", "S123", "AA-BB-CC-DD-EE-01,aa:bb:cc:dd:ee:02", "Lab Alpha", "Stockage", "ok"],
                ["", "Ordi fixe", "", "", "", "Allée", "", ""], ["", "Ordi fixe", "", "", "", "Allée", "", ""], ["", "", "", "", "", "", "", ""]]
        recs = campus.parse_records(rows, "assets")
        self.assertEqual(len(recs), 3)
        self.assertNotEqual(recs[1]["key"], recs[2]["key"])  # deux matériels non identifiés du même lab = deux fiches
        self.assertEqual(recs[0]["macs"], ["aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"]); self.assertEqual(recs[0]["comment"], "ok"); self.assertEqual(recs[0]["fields"], {})
        self.assertEqual(recs[1]["kind"], "Ordi fixe"); self.assertEqual(recs[1]["lab"], "Allée")
        m = campus.match_assets(recs, [{"mac": "AA:BB:CC:DD:EE:02", "ip": "192.0.2.5", "status": "online", "connected_to": "AP-1"}])
        self.assertEqual(m[0]["nebula"]["ip"], "192.0.2.5"); self.assertIsNone(m[1]["nebula"])
        # rapprochement par IP (#571)
        r2 = campus.parse_records([["Nom", "Type", "Adresse IP"], ["LED-9", "Ordi fixe", "192.0.2.50"]], "assets")
        self.assertEqual(r2[0]["ip"], "192.0.2.50")
        self.assertEqual(campus.match_assets(r2, [{"ip": "192.0.2.50", "status": "online"}])[0]["nebula"]["status"], "online")

    def test_services_inherit(self):
        rows = [["Parcours", "Lab", "Nom de l’atelier", "Matériel", "Wifi", "Lan", "Internet", "Site", "Idruide"],
                ["Robots", "Lab Robotique", "Promenade", "WAF", "", "", "", "", ""],
                ["", "", "Exploration", "PC portable", "X", "", "x", "vittascience", "X"],
                ["Bien-être", "Mini-Lab", "", "", "", "", "", "", ""]]
        recs = campus.parse_records(rows, "services")
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[1]["course"], "Robots"); self.assertEqual(recs[1]["lab"], "Lab Robotique")
        self.assertTrue(recs[1]["wifi"]); self.assertFalse(recs[1]["lan"]); self.assertTrue(recs[1]["internet"]); self.assertEqual(recs[1]["fields"], {"Idruide": "X"})

    def test_csv_and_ods(self):
        rows = campus.read_table("Nom;Type\nA;PC\n".encode("utf-8"), "x.csv")
        self.assertEqual(rows, [["Nom", "Type"], ["A", "PC"]])
        import zipfile, io
        content = ('<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
                   '<office:body><office:spreadsheet><table:table><table:table-row><table:table-cell><text:p>Nom</text:p></table:table-cell><table:table-cell><text:p>Type</text:p></table:table-cell></table:table-row>'
                   '<table:table-row><table:table-cell><text:p>B</text:p></table:table-cell><table:table-cell table:number-columns-repeated="2"><text:p>x</text:p></table:table-cell><table:table-cell table:number-columns-repeated="1000"/></table:table-row></table:table></office:spreadsheet></office:body></office:document-content>')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("content.xml", content)
        self.assertEqual(campus.read_table(buf.getvalue(), "y.ods"), [["Nom", "Type"], ["B", "x", "x"]])
        with self.assertRaises(ValueError):
            campus.read_table(b"", "z.pdf")


if __name__ == "__main__":
    unittest.main()
