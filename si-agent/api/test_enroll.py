import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "agent"))
# store.py importe les modules partagés sous leur nom de build (si_agent_*.py copiés par le Dockerfile)
import importlib
for name in ("plugins", "protocol", "control", "publish"):
    sys.modules.setdefault("si_agent_" + name, importlib.import_module("si_agent." + name))
import store  # noqa: E402


class EnrollTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.db = os.path.join(self.d, "t.sqlite"); store.ensure_schema(self.db)

    def test_slug(self):
        self.assertEqual(store.slug_agent_id("PC-CAISSE 01.Campus"), "pc-caisse-01.campus")
        self.assertEqual(store.slug_agent_id("---"), "poste")
        self.assertTrue(store.valid_agent_id(store.slug_agent_id("Éric's Laptop")))

    def test_token_cycle(self):
        t = store.create_enroll_token(self.db, "numeria", label="campus", central_url="https://hub.exemple.fr/api/si-agent/", plugins=["windows-probe"], max_uses=2, expires_hours=1)
        self.assertTrue(t["token"].startswith("enr-")); self.assertTrue(t["usable"]); self.assertEqual(t["central_url"], "https://hub.exemple.fr/api/si-agent")
        a, tt = store.enroll_with_token(self.db, t["token"], "PC-ACCUEIL", "windows")
        self.assertEqual(a["agent_id"], "pc-accueil"); self.assertEqual(a["site"], "numeria"); self.assertTrue(a["secret"])
        first = a["secret"]
        a2, _ = store.enroll_with_token(self.db, t["token"], "PC-ACCUEIL", "windows")  # relance : secret neuf, pas d'échec
        self.assertNotEqual(a2["secret"], first)
        store.enroll_with_token(self.db, t["token"], "PC-AMPHI", "windows")
        t2 = store.get_enroll_token(self.db, t["token"])
        self.assertEqual(t2["uses"], 2); self.assertTrue(t2["exhausted"]); self.assertFalse(t2["usable"])
        with self.assertRaises(ValueError):
            store.enroll_with_token(self.db, t["token"], "PC-3", "windows")
        lst = store.list_enroll_tokens(self.db)
        self.assertEqual(lst[0]["agents"], 2)
        self.assertTrue(store.revoke_enroll_token(self.db, t["token"]))
        self.assertFalse(store.get_enroll_token(self.db, t["token"])["usable"])
        with self.assertRaises(ValueError):
            store.enroll_with_token(self.db, "enr-inconnu", "x", None)

    def test_autre_jeton_refuse(self):
        t1 = store.create_enroll_token(self.db, "a"); t2 = store.create_enroll_token(self.db, "b")
        store.enroll_with_token(self.db, t1["token"], "PC1")
        with self.assertRaises(ValueError):
            store.enroll_with_token(self.db, t2["token"], "PC1")


if __name__ == "__main__":
    unittest.main()
