"""Tests du rendu nginx (#574 : relais HTTPS sur port dédié)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_nginx_conf as r  # noqa: E402


class Relays(unittest.TestCase):
    def test_navigateurs(self):   # #798
        self.assertEqual(r.navigateurs_from_env({"NAVIGATEURS": "ovh1=6490, campus=6491"}), [("ovh1", 6490), ("campus", 6491)])
        self.assertEqual(r.navigateurs_from_env({}), [])
        for bad in ({"NAVIGATEURS": "OVH=6490"}, {"NAVIGATEURS": "a=80"}, {"NAVIGATEURS": "a=6490,a=6491"}, {"NAVIGATEURS": "a/../b=6490"}):
            with self.assertRaises(ValueError):
                r.navigateurs_from_env(bad)
        conf, _ = r.build_config({"NAVIGATEURS": "ovh1=6490"})
        self.assertIn("location /navigateur/ovh1/", conf)
        self.assertIn("set $nav_upstream_0 http://si-proxy:6490;", conf)
        self.assertIn('proxy_set_header Connection "upgrade";', conf)

    def test_ia_noeuds(self):   # #988
        J = "a" * 32
        env = {"IA_NOEUDS": "prodia=http://si-proxy:6491, preprodia=http://192.0.2.20:8092/", "IA_NOEUDS_JETONS": "prodia=%s,preprodia=%s" % (J, "b" * 32)}
        self.assertEqual(r.ia_noeuds_from_env(env), [("prodia", "http://si-proxy:6491", J), ("preprodia", "http://192.0.2.20:8092", "b" * 32)])
        self.assertEqual(r.ia_noeuds_from_env({}), [])
        for bad in ({"IA_NOEUDS": "prodia=http://x:8092"},                                      # pas de jeton
                    {"IA_NOEUDS": "prodia=http://x:8092", "IA_NOEUDS_JETONS": "prodia=court"},
                    {"IA_NOEUDS": "Prodia=http://x:8092", "IA_NOEUDS_JETONS": "Prodia=" + J},
                    {"IA_NOEUDS": "prodia=http://x:8092/chemin", "IA_NOEUDS_JETONS": "prodia=" + J},
                    {"IA_NOEUDS": "prodia=http://x;rm:8092", "IA_NOEUDS_JETONS": "prodia=" + J},
                    {"IA_NOEUDS": "prodia=http://x:8092,prodia=http://y:8092", "IA_NOEUDS_JETONS": "prodia=" + J}):
            with self.assertRaises(ValueError):
                r.ia_noeuds_from_env(bad)
        conf, summary = r.build_config(env)
        self.assertEqual(conf.count("location = /_ia_acces"), 1)
        self.assertIn("location /ia/prodia/", conf); self.assertIn("location /ia/preprodia/", conf)
        self.assertEqual(conf.count("auth_request /_ia_acces;"), 2)
        self.assertIn('proxy_set_header X-Hermes-Jeton "%s";' % J, conf)
        self.assertIn('proxy_set_header Cookie "";', conf)   # le jeton Keycloak de la personne ne part pas vers le nœud
        self.assertNotIn(J, "\n".join(summary))              # jamais dans le résumé affiché
        conf, _ = r.build_config({})
        self.assertNotIn("_ia_acces", conf)

    def test_ia_registre_996(self):   # #996 : nœuds déployés depuis le hub, jeton dérivé du secret
        import json as _j, tempfile as _t
        f = os.path.join(_t.mkdtemp(), "ia.json")
        with open(f, "w") as fh:
            _j.dump({"noeuds": [{"nom": "prodia", "acces": "bastion", "adresse": "192.0.2.30", "port": 8092, "shim": "campus", "publie": 6491},
                                {"nom": "preprodia", "acces": "direct", "adresse": "192.0.2.20", "port": 8092},
                                {"nom": "attente", "acces": "bastion", "adresse": "192.0.2.31", "shim": "campus"}]}, fh)
        reg = r.ia_registre(f)
        self.assertEqual(reg, ["prodia=http://si-proxy:6491", "preprodia=http://192.0.2.20:8092"])
        sec = "s3cr3t-de-test"
        n = r.ia_noeuds_from_env({"IA_NOEUDS_SECRET": sec}, registre=reg)
        self.assertEqual([x[:2] for x in n], [("prodia", "http://si-proxy:6491"), ("preprodia", "http://192.0.2.20:8092")])
        self.assertEqual(n[0][2], r.ia_jeton(sec, "prodia"))
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "si-agent", "api"))
        import noeudia
        self.assertEqual(r.ia_jeton(sec, "prodia"), noeudia.jeton(sec, "prodia"))   # même jeton que celui remis à l'agent
        # IA_NOEUDS du .env prioritaire sur le registre pour un même nom
        n = r.ia_noeuds_from_env({"IA_NOEUDS": "prodia=http://192.0.2.9:8092", "IA_NOEUDS_SECRET": sec}, registre=reg)
        self.assertEqual(n[0][:2], ("prodia", "http://192.0.2.9:8092")); self.assertEqual(len(n), 2)
        with self.assertRaises(ValueError):   # registre sans secret ni jeton : refus explicite
            r.ia_noeuds_from_env({}, registre=reg)

    def test_relays(self):
        env = {"GATEWAY_PORT": "6443", "HOST_IP": "192.0.2.1", "RELAY1_PORT": "6486", "RELAY1_TARGET": "ssh-tunnels-api:18006", "RELAY1_LABEL": "hyperviseur du site"}
        conf, summary = r.build_config(env)
        self.assertEqual(conf.count("listen 6486 ssl"), 1)
        self.assertIn("https://ssh-tunnels-api:18006", conf); self.assertIn("Upgrade $http_upgrade", conf)
        self.assertTrue(any("6486" in l for l in summary))
        self.assertEqual(r.relays_from_env({"RELAY1_PORT": "6486"}), [])  # cible absente = pas de relais
        for bad in ({"RELAY1_PORT": "80", "RELAY1_TARGET": "x:1"}, {"RELAY1_PORT": "6486", "RELAY1_TARGET": "x"}, {"RELAY1_PORT": "6486", "RELAY1_TARGET": "x:1; rm"}):
            with self.assertRaises(ValueError):
                r.relays_from_env(bad)


if __name__ == "__main__":
    unittest.main()
