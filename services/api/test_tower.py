# -*- coding: utf-8 -*-
import unittest

import tower


class Delivery(unittest.TestCase):
    def test_prefix_and_safe(self):
        names = ["supervision-si/a.py", "supervision-si/x/b.py", "supervision-si/d/"]
        self.assertEqual(tower.strip_prefix(names), "supervision-si/")
        self.assertEqual(tower.strip_prefix(["a.py", "x/b.py"]), "")
        self.assertEqual(tower.safe_member("supervision-si/x/b.py", "supervision-si/"), "x/b.py")
        for bad in ("supervision-si/../etc/passwd", "/etc/passwd", "C:/x", "supervision-si/d/", ""):
            self.assertIsNone(tower.safe_member(bad, "supervision-si/"), bad)

    def test_classify(self):
        self.assertEqual(tower.classify(".env", "a", "b"), "protected")
        self.assertEqual(tower.classify("cisco/switches.local.json", "a", None), "protected")
        self.assertEqual(tower.classify("cisco/app.py", "a", None), "added")
        self.assertEqual(tower.classify("cisco/app.py", "a", "a"), "unchanged")
        self.assertEqual(tower.classify("cisco/app.py", "a", "b"), "changed")
        self.assertEqual(tower.classify("assistant/data/cases.json", "a", "b"), "kept")
        self.assertEqual(tower.classify("assistant/data/cases.json", "a", None), "added")
        self.assertEqual(tower.classify(".env.example", "a", "b"), "changed")


DOCKERFILE = """FROM python:3.12-slim AS base
COPY cisco/requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=app cisco/app.py \\
     cisco/parsers.py ./
COPY ["shared/version_endpoint.py", "."]
COPY --from=builder /x /y
ADD https://example.org/f.tgz /tmp/
COPY cisco/static/*.html static/
"""


class Plan(unittest.TestCase):
    def test_dockerfile_sources(self):
        self.assertEqual(tower.dockerfile_sources(DOCKERFILE),
                         ["cisco/requirements.txt", "cisco/app.py", "cisco/parsers.py", "shared/version_endpoint.py", "cisco/static"])

    def test_service_paths_and_plan(self):
        files = {"cisco/Dockerfile": DOCKERFILE, "hub/Dockerfile": "COPY hub/ .\nCOPY shared/theme.css src/theme.css\n"}
        services = {
            "cisco-api": {"build": {"context": ".", "dockerfile": "cisco/Dockerfile"}, "volumes": ["./cisco:/app/registry:ro", "${CISCO_DATA_DIR:-./cisco/data}:/data"]},
            "hub": {"build": {"context": ".", "dockerfile": "hub/Dockerfile"}},
            "nginx-like": {"image": "nginx", "volumes": ["./conf/site.conf:/etc/nginx/conf.d/site.conf:ro", "/var/run/docker.sock:/var/run/docker.sock"]},
            "pg": {"image": "postgres"},
        }
        paths = tower.service_paths(services, "", files.get)
        self.assertIn("cisco/app.py", paths["cisco-api"]["build"])
        self.assertEqual(paths["cisco-api"]["mounts"], ["cisco"])
        self.assertEqual(paths["nginx-like"]["mounts"], ["conf/site.conf"])
        self.assertEqual(paths["pg"], {"build": [], "mounts": []})
        running = ["cisco-api", "nginx-like", "pg"]  # hub arrêté (profil allégé)
        p = tower.plan_for_changes(["cisco/app.py", "shared/theme.css", "conf/site.conf", "CHANGELOG.md", "shared/VERSION.json"], paths, running)
        self.assertEqual(p["rebuild"], ["cisco-api"])
        self.assertEqual(p["restart"], ["nginx-like"])
        self.assertEqual(p["not_running"], ["hub"])
        self.assertEqual([s["cmd"] for s in p["steps"]], ["./scripts/run.sh up -d --build cisco-api", "./scripts/run.sh restart nginx-like"])
        # registre d'exemple seul modifié : monté -> redémarrage, pas de rebuild
        p = tower.plan_for_changes(["cisco/switches.json"], paths, running)
        self.assertEqual((p["rebuild"], p["restart"]), ([], ["cisco-api"]))
        # compose, .env.example, passerelle
        p = tower.plan_for_changes(["docker-compose.yml", ".env.example", "tls-proxy/render_nginx_conf.py"], paths, running)
        cmds = [s["cmd"] for s in p["steps"]]
        self.assertEqual(cmds[0], "python3 scripts/sync-env.py")
        self.assertIn("./scripts/run.sh up -d cisco-api nginx-like pg", cmds)
        self.assertEqual(cmds[-1], "./gateway/scripts/run.sh up -d --force-recreate tls-proxy")
        self.assertEqual(tower.plan_for_changes(["README.md", "CHANGELOG.md"], paths, running)["steps"], [])

    def test_rebuild_steps(self):
        self.assertEqual(tower.rebuild_steps(["hub", "x; rm -rf /"])[0]["cmd"], "./scripts/run.sh up -d --build hub")
        self.assertEqual(tower.rebuild_steps(["; ls"]), [])


class Configs(unittest.TestCase):
    def test_validate_cisco(self):
        doc, errs, warns = tower.validate_config("cisco", {"switches": [
            {"name": "routeur-bureau", "host": "192.0.2.249", "transport": "TELNET", "credential": "rb", "enable_credential": "rb-en", "extra": 1},
            {"name": "sw2", "host": "192.0.2.2", "port": "22"}]})
        self.assertEqual(errs, [])
        self.assertEqual(doc["switches"][0]["transport"], "telnet")
        self.assertEqual(doc["switches"][0]["platform"], "ios") if "platform" in doc["switches"][0] else None
        self.assertEqual(doc["switches"][1]["credential"], "cisco")
        self.assertEqual(doc["switches"][1]["port"], 22)
        self.assertTrue(any("extra" in w for w in warns))

    def test_validate_errors(self):
        _, errs, _ = tower.validate_config("cisco", [{"name": "a b", "host": "x"}, {"host": "y"}, {"name": "c", "host": "z", "transport": "rsh"},
                                                     {"name": "d", "host": "h h"}, {"name": "e", "host": "1", "port": 70000}, {"name": "e", "host": "2"}])
        self.assertEqual(len(errs), 6)
        _, errs, _ = tower.validate_config("mikrotik", {"autre": []})
        self.assertTrue(errs)
        doc, errs, _ = tower.validate_config("mikrotik", [{"name": "mt", "host": "192.0.2.253"}])
        self.assertEqual(doc, {"routers": [{"name": "mt", "host": "192.0.2.253", "credential": "default"}]})

    def test_merge(self):
        cur = [{"name": "a", "host": "1"}, {"name": "b", "host": "2"}]
        out, st = tower.merge_items(cur, [{"name": "b", "host": "3"}, {"name": "c", "host": "4"}, {"name": "a", "host": "1"}])
        self.assertEqual([x["host"] for x in out], ["1", "3", "4"])
        self.assertEqual(st, {"added": 1, "updated": 1, "unchanged": 1, "removed": 0})
        out, st = tower.merge_items(cur, [{"name": "z"}], mode="replace")
        self.assertEqual((out, st["removed"]), ([{"name": "z"}], 2))


class Heal(unittest.TestCase):
    def test_threshold_and_cap(self):
        rows = [{"service": "ged-api", "light": "red", "text": "HTTP 502"}, {"service": "hub", "light": "red", "protected": True},
                {"service": "x", "light": "red"}]
        st, restarts, events = {}, [], []
        t = 1000.0
        for i in range(20):
            todo, st, ev = tower.heal_decide(st, rows, t + i * 60, threshold=3, max_per_hour=2, ignored=["x"])
            restarts += todo
            events += ev
        self.assertEqual(restarts, ["ged-api", "ged-api"])
        self.assertEqual([e["event"] for e in events], ["heal-restart", "heal-restart", "heal-gave-up"])
        todo, st, ev = tower.heal_decide(st, [{"service": "ged-api", "light": "green"}], t + 3000)
        self.assertEqual([e["event"] for e in ev], ["heal-recovered"])
        todo, st, ev = tower.heal_decide(st, rows[:1], t + 9000, threshold=1, max_per_hour=2)
        self.assertEqual(todo, ["ged-api"])  # une heure plus tard, de nouveau autorisé


if __name__ == "__main__":
    unittest.main()
