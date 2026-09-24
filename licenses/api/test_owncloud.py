# -*- coding: utf-8 -*-
import unittest

import owncloud

XML = '''<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response><d:href>/remote.php/webdav/Secrets/Fiches/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
<d:response><d:href>/remote.php/webdav/Secrets/Fiches/alice%20a.txt</d:href><d:propstat><d:prop><d:getlastmodified>Mon, 01 Sep 2026 10:00:00 GMT</d:getlastmodified><d:getcontentlength>120</d:getcontentlength><d:resourcetype/></d:prop></d:propstat></d:response>
<d:response><d:href>/remote.php/webdav/Secrets/Fiches/anciens%20utilisateurs/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
<d:response><d:href>/remote.php/webdav/Secrets/Fiches/photo.jpg</d:href><d:propstat><d:prop><d:getcontentlength>9</d:getcontentlength><d:resourcetype/></d:prop></d:propstat></d:response></d:multistatus>'''
XML_OLD = XML.replace("Secrets/Fiches/alice%20a.txt", "Secrets/Fiches/anciens%20utilisateurs/bob%20b.txt").replace("Secrets/Fiches/photo.jpg", "Secrets/Fiches/anciens%20utilisateurs/x.txt")
FICHE = """Utilisateur : Alice A
Email: alice.a@exemple.test
Poste : PC-01
Licence Office 365 : ABCDE-12345-FGHIJ-67890-KLMNO
Mot de passe messagerie = Tr0pSecret!
Clé Windows: 1234567890ABCDEF
Note : préfère le clavier azerty
"""


class Resp:
    def __init__(self, status, text="", content=b""):
        self.status_code, self.text, self.content = status, text, content or text.encode("utf-8")


class FakeHttp:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw.get("headers")))
        if url.endswith("/Secrets/Fiches"):
            return Resp(207, XML)
        if url.endswith("/anciens%20utilisateurs"):
            return Resp(207, XML_OLD)
        return Resp(404)

    def get(self, url, **kw):
        self.calls.append(("GET", url, None))
        if "alice" in url:
            return Resp(200, FICHE)
        if "bob" in url:
            return Resp(200, "Email : bob@exemple.test\nLicence eDraw : QWERT-ASDFG-ZXCVB")
        return Resp(200, "rien")


class Parse(unittest.TestCase):
    def test_root_and_propfind(self):
        self.assertEqual(owncloud.webdav_root("https://cloud.exemple/"), "https://cloud.exemple/remote.php/webdav")
        self.assertEqual(owncloud.webdav_root("https://cloud.exemple/remote.php/dav/files/admin"), "https://cloud.exemple/remote.php/dav/files/admin")
        items = owncloud.parse_propfind(XML, "/remote.php/webdav/Secrets/Fiches")
        self.assertEqual([(i["path"], i["dir"]) for i in items if i["path"]], [("alice a.txt", False), ("anciens utilisateurs", True), ("photo.jpg", False)])

    def test_fiche_masks_secrets(self):
        f = owncloud.parse_fiche(FICHE, "Fiches/alice a.txt")
        self.assertEqual((f["name"], f["mails"]), ("alice a", ["alice.a@exemple.test"]))
        by = {x["label"]: x for x in f["fields"]}
        self.assertEqual(by["Poste"]["value"], "PC-01")
        self.assertTrue(by["Licence Office 365"]["secret"] and by["Licence Office 365"]["value"].endswith("LMNO") and "ABCDE" not in by["Licence Office 365"]["value"])
        self.assertTrue(by["Mot de passe messagerie"]["secret"] and "Tr0p" not in by["Mot de passe messagerie"]["value"])
        self.assertEqual(sorted(l["product"] for l in f["licenses"] if l["product"]), ["office 365", "windows"])
        self.assertEqual(f["software"], ["office 365", "windows"])
        self.assertNotIn("ABCDE-12345", str(f))

    def test_scan_root_and_former(self):
        http = FakeHttp()
        c = owncloud.OwnCloud("https://cloud.exemple", "svc", "pw", http=http)
        out = owncloud.scan(c, "Secrets/Fiches")
        self.assertEqual([(o["name"], o["former"]) for o in out], [("alice a", False), ("bob b", True), ("x", True)])
        self.assertEqual(out[1]["fiche"]["mails"], ["bob@exemple.test"])
        self.assertTrue(all("fiche" in o and "text" not in o for o in out))
        self.assertIn(("PROPFIND", "https://cloud.exemple/remote.php/webdav/Secrets/Fiches", {"Depth": "1"}), http.calls)


if __name__ == "__main__":
    unittest.main()
