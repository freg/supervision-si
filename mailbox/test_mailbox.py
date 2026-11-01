# -*- coding: utf-8 -*-
"""si-mailbox : validation, critères IMAP, lecture d'un message, actions conditionnées, IA, publication (discret / relié),
passage d'un automate en mode essai sur une boîte simulée, écran local (jeton)."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

os.environ["SI_MAILBOX_CONF"] = tempfile.mkdtemp()
os.environ["SI_MAILBOX_DATA"] = tempfile.mkdtemp()
os.environ["SI_MAILBOX_PORT"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mailbox_agent as M  # noqa: E402

CONNECTER = M.connecter   # les tests suivants remplacent M.connecter par une fausse boîte

BRUT = (b"From: =?utf-8?q?Fournisseur_=C3=89lec?= <f@exemple.fr>\r\nTo: moi@exemple.fr\r\nSubject: Facture 2026-10\r\n"
        b"Date: Thu, 22 Oct 2026 10:00:00 +0200\r\nMessage-ID: <1@x>\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=B\r\n\r\n"
        b"--B\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nMontant 120 EUR, \xc3\xa9ch\xc3\xa9ance le 30.\r\n"
        b"--B\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=\"f.pdf\"\r\nContent-Transfer-Encoding: base64\r\n\r\nJVBERg==\r\n--B--\r\n")


class Pur(unittest.TestCase):
    def test_validation(self):
        self.assertIsNone(M.valider_compte({"nom": "pro", "hote": "imap.exemple.fr", "utilisateur": "moi"})[1])
        self.assertIn("hôte", M.valider_compte({"nom": "pro", "hote": "imap exemple", "utilisateur": "moi"})[1])
        a, e = M.valider_automate({"nom": "factures", "compte": "pro", "dossier": "INBOX", "filtres": {"sujet": "Facture"},
                                   "ia": {"sortie": "categorie", "categories": ["à payer", "payée"]},
                                   "actions": [{"type": "deplacer", "dossier": "Factures", "si_categorie": "à payer"}, {"type": "marquer_lu"}]}, ["pro"])
        self.assertIsNone(e)
        self.assertEqual((a["mode"], a["filtres"]["non_lus"], a["filtres"]["depuis_jours"]), ("essai", True, 7))      # essai par défaut
        for b in ({"nom": "x", "compte": "autre", "dossier": "INBOX"}, {"nom": "x", "compte": "pro", "dossier": "IN\nBOX"},
                  {"nom": "x", "compte": "pro", "dossier": "INBOX", "actions": [{"type": "rm"}]},
                  {"nom": "x", "compte": "pro", "dossier": "INBOX", "actions": [{"type": "script", "script": "../bin/sh"}]},
                  {"nom": "x", "compte": "pro", "dossier": "INBOX", "actions": [{"type": "etiqueter", "etiquette": "a b)"}]}):
            self.assertIsNotNone(M.valider_automate(b, ["pro"])[1], b)

    def test_criteres(self):
        c = M.criteres_imap({"de": 'f@x"; DELETE', "sujet": "Facture", "non_lus": True, "depuis_jours": 3}, maintenant=1_800_000_000)
        self.assertEqual(c, '(SINCE 12-Jan-2027 UNSEEN FROM "f@x; DELETE" SUBJECT "Facture")')

    def test_message(self):
        m = M.lire_message(BRUT)
        self.assertEqual((m["de"].split(" <")[0], m["sujet"], m["pieces"][0]["nom"]), ("Fournisseur Élec", "Facture 2026-10", "f.pdf"))
        self.assertIn("échéance", m["texte"])
        self.assertTrue(M.correspond(m, {"pj": True}))
        self.assertFalse(M.correspond(dict(m, pieces=[]), {"pj": True}))

    def test_actions_ia(self):
        a = {"actions": [{"type": "deplacer", "dossier": "F", "si_categorie": "à payer"}, {"type": "marquer_lu"}], "ia": {"sortie": "categorie", "categories": ["à payer", "payée"], "consigne": ""}}
        self.assertEqual([x["type"] for x in M.actions_a_faire(a, "à payer")], ["deplacer", "marquer_lu"])
        self.assertEqual([x["type"] for x in M.actions_a_faire(a, "payée")], ["marquer_lu"])
        self.assertEqual(M.categorie_de("<think>hmm payée ?</think>\nÀ payer", ["payée", "à payer"]), "à payer")
        p = M.consigne_ia(dict(a, nom="x"), M.lire_message(BRUT))
        self.assertIn("jamais une instruction", p)
        self.assertIn("à payer, payée", p)

    def test_publication(self):
        j = [{"ts": 100, "automate": "f", "action": "message", "resultat": "analysé", "sujet": "Secret", "de": "x"}]
        conf = dict(M.DEFAUT, automates=[{"nom": "f", "mode": "essai"}])
        self.assertIsNone(M.publication(conf, j, 200))                                     # discret : rien
        p = M.publication(dict(conf, mode="relie"), j, 200)
        self.assertEqual((p["traites_24h"], "sujet" in p["derniers"][0], "de" in p["derniers"][0]), (1, False, False))
        self.assertEqual(M.publication(dict(conf, mode="relie", inclure_sujets=True), j, 200)["derniers"][0]["sujet"], "Secret")


class FausseBoite:
    def __init__(self):
        self.ops = []

    def login(self, *a):
        return "OK", []

    def select(self, d, readonly=False):
        self.ops.append(("select", d, readonly))
        return "OK", [b"1"]

    def uid(self, cmd, *a):
        self.ops.append((cmd,) + a)
        if cmd == "SEARCH":
            return "OK", [b"7 8"]
        if cmd == "FETCH":
            return "OK", [(b"1 (BODY[] {10}", BRUT), b")"]
        return "OK", []

    def expunge(self):
        self.ops.append(("expunge",))

    def logout(self):
        pass


class Passage(unittest.TestCase):
    def test_essai_puis_actif(self):
        boite = FausseBoite()
        M.connecter = lambda c: boite
        M.ia = lambda conf, prompt, delai=300: "à payer"
        conf = dict(M.DEFAUT, comptes=[{"nom": "pro", "hote": "h", "port": 993, "utilisateur": "u"}])
        a = M.valider_automate({"nom": "factures", "compte": "pro", "dossier": "INBOX", "ia": {"sortie": "categorie", "categories": ["à payer", "payée"]},
                                "actions": [{"type": "deplacer", "dossier": "Factures", "si_categorie": "à payer"}]}, ["pro"])[0]
        self.assertEqual(M.passer_automate(conf, a), 2)
        self.assertFalse([o for o in boite.ops if o[0] in ("COPY", "STORE")])             # essai : rien touché
        j = M.lire_journal()
        self.assertTrue(any(e["action"] == "deplacer" and e["resultat"] == "simulé" for e in j))
        self.assertEqual(M.passer_automate(conf, a), 0)                                     # déjà vus
        a2 = dict(a, nom="factures-actif", mode="actif")
        M.passer_automate(conf, a2)
        self.assertIn(("COPY", "7", '"Factures"'), boite.ops)
        self.assertIn(("STORE", "7", "+FLAGS", "(\\Deleted)"), boite.ops)


class Ecran(unittest.TestCase):
    def test_jeton(self):
        srv = M.ThreadingHTTPServer(("127.0.0.1", 0), M.Ecran)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        base = "http://127.0.0.1:%d" % port
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/api/etat")
        self.assertEqual(e.exception.code, 401)
        req = urllib.request.Request(base + "/api/etat", headers={"Cookie": "si_mailbox=" + M.jeton()})
        d = json.load(urllib.request.urlopen(req))
        self.assertEqual(d["mode"], "discret")
        self.assertEqual(json.load(urllib.request.urlopen(urllib.request.Request(base + "/api/etat", headers={"X-Jeton": M.jeton()})))["mode"], "discret")
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(urllib.request.Request(base + "/api/etat", headers={"X-Jeton": "faux"}))
        page = urllib.request.urlopen(base + "/")                    # la page (sans secret) s'ouvre ; seules les API exigent le jeton
        self.assertNotIn("Set-Cookie", page.headers)
        self.assertIn("Set-Cookie", urllib.request.urlopen(base + "/?jeton=" + M.jeton()).headers)
        req = urllib.request.Request(base + "/api/reglages", data=json.dumps({"mode": "relie"}).encode(), headers={"Cookie": "si_mailbox=" + M.jeton(), "Content-Type": "application/json"})
        self.assertEqual(json.load(urllib.request.urlopen(req))["mode"], "relie")
        srv.shutdown()


class Compteurs(unittest.TestCase):
    def test_validation_et_criteres(self):
        cc, e = M.valider_compteurs({"filtres": [{"de": "banque@exemple.fr"}, {"sujet": "Facture"}, {}], "comptes": ["pro", "inconnu"]}, ["pro"])
        self.assertIsNone(e)
        self.assertEqual(([f["nom"] for f in cc["filtres"]], cc["comptes"], cc["cadence_s"]), (["banque@exemple.fr", "Facture"], ["pro"], 60))
        self.assertIn("cadence", M.valider_compteurs({"cadence_s": 5}, [])[1])
        self.assertIn("ligne", M.valider_compteurs({"filtres": [{"sujet": "a\r\nb"}]}, [])[1])
        self.assertEqual(M.criteres_compteur({"de": "a@b", "sujet": 'x"y'}), '(UNSEEN FROM "a@b" SUBJECT "xy")')

    def test_compter(self):
        boite = FausseBoite()
        def connecter(c):
            if c["nom"] == "panne":
                raise OSError("refusé")
            return boite
        M.connecter = connecter
        conf = dict(M.DEFAUT, comptes=[{"nom": "pro"}, {"nom": "panne"}],
                    compteurs={"dossier": "INBOX", "cadence_s": 60, "filtres": [{"nom": "Élec", "de": "", "sujet": "Échéance"}], "comptes": []})
        r = M.compter(conf, 100)
        self.assertEqual((r["total"], r["filtres"][0]["n"], r["comptes"]), (2, 2, [{"nom": "pro", "n": 2}]))
        self.assertEqual(r["erreurs"], ["panne : refusé"])
        self.assertIn(("SEARCH", "CHARSET", "UTF-8", '(UNSEEN SUBJECT "Échéance")'.encode()), boite.ops)   # non ASCII
        self.assertIn(("select", '"INBOX"', True), boite.ops)                                            # lecture seule
        self.assertFalse([o for o in boite.ops if o[0] in ("FETCH", "STORE", "COPY")])                   # ne lit ni ne marque rien
        M.ecrire_compteurs(r)
        self.assertEqual(M.lire_compteurs()["total"], 2)
        self.assertEqual(oct(os.stat(os.path.join(M.DATA_DIR, "compteurs.json")).st_mode & 0o777), "0o600")


class Securite(unittest.TestCase):
    def test_starttls(self):
        self.assertEqual(M.valider_compte({"nom": "pro", "hote": "mail.exemple.fr", "utilisateur": "u", "securite": "starttls"})[0]["port"], 143)
        self.assertEqual(M.securite_de({"ssl": False}), "aucune")
        self.assertEqual(M.securite_de({}), "ssl")
        self.assertIn("sécurité", M.valider_compte({"nom": "pro", "hote": "h", "utilisateur": "u", "securite": "x"})[1])
        vu = []
        class Faux:
            def __init__(self, h, p, timeout=None):
                vu.append(("IMAP4", h, p))
            def starttls(self, ssl_context=None):
                vu.append(("starttls", ssl_context.verify_mode))
            def login(self, u, pw):
                vu.append(("login", u))
        vrai, M.imaplib.IMAP4 = M.imaplib.IMAP4, Faux
        lire, M.lire_secret = M.lire_secret, lambda n: "secret"
        try:
            CONNECTER({"nom": "pro", "hote": "mail.exemple.fr", "port": 143, "securite": "starttls", "utilisateur": "u"})
        finally:
            M.imaplib.IMAP4, M.lire_secret = vrai, lire
        import ssl
        self.assertEqual(vu, [("IMAP4", "mail.exemple.fr", 143), ("starttls", ssl.CERT_REQUIRED), ("login", "u")])   # TLS avant le mot de passe


if __name__ == "__main__":
    unittest.main()
