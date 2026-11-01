# -*- coding: utf-8 -*-
"""Tests des interpréteurs imap-connectors (#489) — purs, aucun réseau.
Corps Zenoss repris du format réel documenté dans
pixel-grid/data-generator/parse_zenoss_emails.py."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import interpreters  # noqa: E402

ACTIVE_BODY = """Alert generated at 2026/08/11 10:30:12.000 Equipement : sw-coeur
Message : Ping degrade au-dela du seuil Localisation : /Parc/Siege Composants : 
Severite : Warning"""

CLEARED_BODY = """Event Cleared At: 2026/08/11 11:05:00.000 Alert generated at
2026/08/11 10:30:12.000 Clear Message : retour a la normale Message : Ping degrade
Localisation : /Parc/Siege Composants : 
Severite : Warning"""


class TestZenoss(unittest.TestCase):
    def test_alerte_active(self):
        p = interpreters.parse_message("zenoss", {
            "subject": "[Site A] sw-coeur Ping degrade", "from_addr": "zenoss@exemple.fr",
            "date": "Tue, 11 Aug 2026 12:31:00 +0200", "body": ACTIVE_BODY})
        self.assertTrue(p["ok"])
        self.assertEqual(p["kind"], "zenoss-active")
        ev = p["zenoss_event"]
        self.assertEqual(ev["valeur"], 1)
        self.assertEqual(ev["nom"], "sw-coeur")
        self.assertEqual(ev["type"], "alerte_zenoss_email")
        self.assertEqual(ev["ts"], 1786444212, "horodatage du corps, pas du mail")
        fields = json.loads(ev["data"])
        self.assertEqual(fields["severite"], "Warning")
        self.assertIn("alerte sw-coeur", p["summary"])

    def test_resolution(self):
        p = interpreters.parse_message("zenoss", {
            "subject": "[Site A] clear: sw-coeur Ping degrade", "from_addr": "zenoss@exemple.fr",
            "date": "Tue, 11 Aug 2026 13:05:00 +0200", "body": CLEARED_BODY})
        self.assertTrue(p["ok"])
        self.assertEqual(p["kind"], "zenoss-clear")
        ev = p["zenoss_event"]
        self.assertEqual(ev["valeur"], 0)
        self.assertEqual(ev["ts"], 1786446300, "clear : horodaté à Event Cleared At")
        self.assertEqual(ev["nom"], "sw-coeur", "corps clear muet sur l'équipement : le sujet")

    def test_corps_non_reconnu_mais_sujet_zenoss(self):
        p = interpreters.parse_message("zenoss", {
            "subject": "[Site A] routeur-x lien FH tombe", "from_addr": "zenoss@exemple.fr",
            "date": "Tue, 11 Aug 2026 12:31:00 +0200", "body": "format exotique"})
        self.assertTrue(p["ok"], "une alerte mal parsée vaut mieux qu'une alerte perdue")
        self.assertEqual(p["kind"], "zenoss-partial")
        self.assertEqual(p["zenoss_event"]["valeur"], 1)
        self.assertEqual(p["zenoss_event"]["nom"], "routeur-x")

    def test_pas_une_alerte(self):
        p = interpreters.parse_message("zenoss", {"subject": "Newsletter", "body": "bonjour"})
        self.assertFalse(p["ok"])


class TestSmsNotificationTicket(unittest.TestCase):
    def test_sms_numero_dans_sujet(self):
        p = interpreters.parse_message("sms", {
            "subject": "SMS de +33 6 12 34 56 78", "from_addr": "gw@sms.local",
            "body": "Le serveur est redemarre"})
        self.assertTrue(p["ok"])
        self.assertEqual(p["sms"]["sender"], "+33 6 12 34 56 78")
        self.assertEqual(p["sms"]["text"], "Le serveur est redemarre")

    def test_sms_repli_expediteur(self):
        p = interpreters.parse_message("sms", {"subject": "nouveau message", "from_addr": "0622334455@gw.local", "body": "ok"})
        self.assertEqual(p["sms"]["sender"], "0622334455@gw.local")

    def test_notification(self):
        p = interpreters.parse_message("notification", {"subject": "Sauvegarde terminee", "from_addr": "backup@lan"})
        self.assertTrue(p["ok"])
        self.assertEqual(p["summary"], "Sauvegarde terminee")

    def test_ticket(self):
        p = interpreters.parse_message("tickets", {
            "subject": "Imprimante HS", "from_addr": "user@exemple.fr", "body": "Plus de toner"})
        self.assertTrue(p["ok"])
        self.assertEqual(p["ticket"]["subject"], "[IMAP] Imprimante HS")
        self.assertIn("user@exemple.fr", p["ticket"]["description"])

    def test_demande_projeqtor(self):
        p = interpreters.parse_message("projeqtor", {
            "subject": "Acces VPN", "from_addr": "user@exemple.fr", "body": "pour mardi"})
        self.assertEqual(p["demande"]["sujet"], "Acces VPN")
        self.assertEqual(p["demande"]["demandeur"], "user@exemple.fr")

    def test_cible_inconnue(self):
        p = interpreters.parse_message("nope", {"subject": "x"})
        self.assertFalse(p["ok"])

    def test_message_tordu_ne_leve_pas(self):
        p = interpreters.parse_message("zenoss", {"subject": None, "body": None})
        self.assertIn("ok", p)  # jamais d'exception


if __name__ == "__main__":
    unittest.main()
