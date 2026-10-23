# -*- coding: utf-8 -*-
"""si-veille : ordre et dépendances, seuil d'échecs, cause probable, silence si tout va bien, notification graphique
récurrente et courriel unique, fin d'incident, vérifications réelles (tcp, commande, http) sur des cibles locales."""
import http.server
import os
import socket
import sys
import tempfile
import threading
import unittest

d = tempfile.mkdtemp()
os.environ["SI_VEILLE_ETAT"], os.environ["SI_VEILLE_JOURNAL"] = os.path.join(d, "etat.json"), os.path.join(d, "j.log")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import si_veille as V  # noqa: E402

CONF = V.valider({"rappel_min": 5, "seuil_echecs": 2, "verifs": [
    {"id": "bastion", "type": "commande", "commande": "true", "depend_de": ["ssh"], "nom": "Bastion"},
    {"id": "dns", "type": "dns", "nom_hote": "x", "nom": "DNS"},
    {"id": "ssh", "type": "commande", "commande": "true", "nom": "SSH"},
    {"id": "frontal", "type": "http", "url": "https://x/", "depend_de": ["dns"], "nom": "Frontal"}]})[0]


class Pur(unittest.TestCase):
    def test_validation_ordre(self):
        self.assertEqual([v["id"] for v in V.ordonner(CONF["verifs"])], ["ssh", "bastion", "dns", "frontal"])
        self.assertIn("boucle", V.valider({"verifs": [{"id": "a", "type": "tcp", "depend_de": ["b"]}, {"id": "b", "type": "tcp", "depend_de": ["a"]}]})[1])
        self.assertIn("inconnu", V.valider({"verifs": [{"id": "a", "type": "tcp", "depend_de": ["z"]}]})[1])
        self.assertIn("type", V.valider({"verifs": [{"id": "a", "type": "ping"}]})[1])

    def test_incident_complet(self):
        etat, panne = {}, {"dns"}
        verif = lambda v, t: (v["id"] not in panne, "injoignable" if v["id"] in panne else "ok")  # noqa: E731
        # 1er tour : un échec isolé = douteux, rien n'est notifié (seuil 2)
        r = V.passer(CONF, etat, 1000, verif)
        self.assertEqual((r["dns"]["statut"], r["frontal"]["statut"]), ("doute", "ok"))
        self.assertIsNone(V.evaluer_incident(CONF, r))
        self.assertEqual(V.decider_notifications(CONF, etat, None, 1000), [])          # silence
        # 2e tour : panne confirmée -> notification graphique + courriel ; aval non testé
        r = V.passer(CONF, etat, 1120, verif)
        inc = V.evaluer_incident(CONF, r)
        self.assertEqual((inc["cause"][0], r["frontal"]["statut"]), ("dns", "non_teste"))
        g = V.decider_notifications(CONF, etat, inc, 1120)
        self.assertEqual([x[0] for x in g], ["graphique", "mail"])
        self.assertIn("Cause probable : DNS", g[0][2])
        # 3e tour 2 min plus tard : rien (rappel toutes les 5 min, courriel déjà envoyé)
        self.assertEqual(V.decider_notifications(CONF, etat, inc, 1240), [])
        # 4e tour 6 min après : rappel graphique seulement
        self.assertEqual([x[0] for x in V.decider_notifications(CONF, etat, inc, 1480)], ["graphique"])
        # rétabli : une notification graphique, pas de courriel (mail_retabli faux)
        panne.clear()
        r = V.passer(CONF, etat, 1600, verif)
        self.assertIsNone(V.evaluer_incident(CONF, r))
        g = V.decider_notifications(CONF, etat, None, 1600)
        self.assertEqual([(x[0], x[1]) for x in g], [("graphique", "Chaîne du hub rétablie")])
        self.assertIsNone(etat["incident"])
        self.assertEqual(V.decider_notifications(dict(CONF, mail_retabli=True), {"incident": {"debut": 0, "mail": True}}, None, 60)[1][0], "mail")


class Reel(unittest.TestCase):
    def test_tcp_commande_http(self):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        p = srv.server_address[1]
        self.assertTrue(V.verifier({"type": "tcp", "hote": "127.0.0.1", "port": p})[0])
        self.assertTrue(V.verifier({"type": "http", "url": "http://127.0.0.1:%d/" % p})[0])
        ok, det = V.verifier({"type": "http", "url": "http://127.0.0.1:%d/" % p, "contient": "texte-introuvable-xyz"})
        self.assertFalse(ok)
        srv.shutdown()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        libre = s.getsockname()[1]
        s.close()
        self.assertFalse(V.verifier({"type": "tcp", "hote": "127.0.0.1", "port": libre, "delai_s": 2})[0])
        self.assertEqual(V.verifier({"type": "commande", "commande": "echo bonjour"}), (True, "bonjour"))
        ok, det = V.verifier({"type": "commande", "commande": "echo raté >&2; exit 3"})
        self.assertEqual((ok, det), (False, "code 3 : raté"))
        self.assertIn("délai", V.verifier({"type": "commande", "commande": "sleep 5", "delai_s": 1})[1])


class Tour(unittest.TestCase):
    def test_courriel_rate_reessaye(self):
        conf = V.valider({"seuil_echecs": 1, "verifs": [{"id": "a", "type": "commande", "commande": "false", "nom": "A"}]})[0]
        envois, graph = [], []
        def mail(_c, sujet, _t):
            envois.append(sujet)
            if len(envois) == 1:
                raise OSError("réseau coupé")
            return True
        V.envoyer_mail, V.notifier_graphique = mail, lambda t, x: graph.append(t)
        if os.path.exists(V.ETAT):
            os.remove(V.ETAT)
        V.tour(conf)
        V.tour(conf)
        V.tour(conf)
        self.assertEqual(len(envois), 2)  # raté, puis réussi, puis plus rien
        self.assertEqual(len(graph), 1)   # rappel graphique seulement toutes les rappel_min minutes
        self.assertIn("ERREUR mail", open(V.JOURNAL).read())


if __name__ == "__main__":
    unittest.main()
