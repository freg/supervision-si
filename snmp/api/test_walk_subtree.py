# -*- coding: utf-8 -*-
"""take_subtree (livraison #506) -- logique pure du WALK de sous-arbre,
testée sans réseau avec de faux var_binds. `python3 -m unittest
test_walk_subtree` (pysnmp installé : le module l'importe)."""
import unittest

import snmp_client


class VB:
    def __init__(self, oid, text):
        self._oid, self._text = oid, text

    def __getitem__(self, i):
        return self if i == 0 else _V(self._text)

    def __str__(self):
        return self._oid


class _V:
    def __init__(self, t):
        self.t = t

    def prettyPrint(self):
        return self.t


class TakeSubtreeTests(unittest.TestCase):
    def test_stops_when_leaving_prefix(self):
        acc = []
        done, last = snmp_client.take_subtree([VB("1.3.6.1.2.1.47.1.1.1.1.2.1", "WS-C2950"), VB("1.3.6.1.2.1.47.1.1.1.1.5.1", "3"),
                                               VB("1.3.6.1.2.1.48.1.0", "hors sujet")], "1.3.6.1.2.1.47.1.1.1.1", acc, 100)
        self.assertTrue(done)
        self.assertEqual(last, "1.3.6.1.2.1.47.1.1.1.1.5.1")
        self.assertEqual([r["value"] for r in acc], ["WS-C2950", "3"])

    def test_continues_when_all_inside(self):
        acc = []
        done, last = snmp_client.take_subtree([VB("1.3.6.1.2.1.17.4.3.1.2.0.1.2.3.4.5", "1")], "1.3.6.1.2.1.17.4.3.1.2", acc, 100)
        self.assertFalse(done)
        self.assertEqual(last, "1.3.6.1.2.1.17.4.3.1.2.0.1.2.3.4.5")

    def test_max_rows_and_end_of_mib(self):
        acc = []
        done, _ = snmp_client.take_subtree([VB("1.3.6.1.2.1.2.2.1.2.1", "a"), VB("1.3.6.1.2.1.2.2.1.2.2", "b")], "1.3.6.1.2.1.2.2.1.2", acc, 1)
        self.assertTrue(done)
        self.assertEqual(len(acc), 1)
        acc = []
        done, last = snmp_client.take_subtree([VB("1.3.6.1.2.1.2.2.1.2.1", "No more variables left in this MIB View")], "1.3.6.1.2.1.2.2.1.2", acc, 10)
        self.assertTrue(done)
        self.assertEqual(acc, [])
        self.assertTrue(snmp_client.take_subtree([], "1.3.6", acc, 10)[0])

    def test_leading_dot_and_prefix_boundary(self):
        acc = []
        # 1.3.6.1.2.1.17 ne doit pas englober 1.3.6.1.2.1.170
        done, _ = snmp_client.take_subtree([VB(".1.3.6.1.2.1.17.1.0", "x"), VB("1.3.6.1.2.1.170.1.0", "y")], "1.3.6.1.2.1.17", acc, 10)
        self.assertTrue(done)
        self.assertEqual(len(acc), 1)


if __name__ == "__main__":
    unittest.main()
