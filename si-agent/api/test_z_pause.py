# -*- coding: utf-8 -*-
"""#853 : pauses planifiées -- un événement d'agent du site en pause n'est pas notifié par les canaux directs."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notify  # noqa: E402

P = [{"debut": 100, "fin": 200, "consommateurs": "si-agent, nebula", "contexte": {"site": "site-alpha"}},
     {"debut": 100, "fin": 200, "consommateurs": "mikrotik", "contexte": {}}]


class Pause(unittest.TestCase):
    def test_en_pause(self):
        notify._pauses_cache.update(at=0, pauses=[])
        self.assertTrue(notify.en_pause({"site": "site-alpha", "agent_id": "pc-a"}, now=150, lire=lambda: P))
        self.assertFalse(notify.en_pause({"site": "bureau", "agent_id": "pc-b"}, now=150, lire=lambda: P))
        self.assertFalse(notify.en_pause({"site": "site-alpha"}, now=250, lire=lambda: P))     # cache relu : fenêtre finie
        notify._pauses_cache.update(at=0, pauses=[])
        def ko():
            raise OSError("notify-api injoignable")
        self.assertFalse(notify.en_pause({"site": "site-alpha"}, now=150, lire=ko))            # injoignable : on alerte


if __name__ == "__main__":
    unittest.main()
