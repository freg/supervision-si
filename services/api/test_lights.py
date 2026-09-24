# -*- coding: utf-8 -*-
import unittest

import lights


class Classify(unittest.TestCase):
    def test_states(self):
        self.assertEqual(lights.classify("exited", None, None, 5000)[0], "red")
        self.assertEqual(lights.classify("restarting", None, None, 5000)[0], "orange")
        self.assertEqual(lights.classify("running", "unhealthy", None, None)[0], "red")
        self.assertEqual(lights.classify("running", "starting", None, None)[0], "orange")
        self.assertEqual(lights.classify("running", "healthy", None, None), ("green", "en marche (healthcheck OK)"))
        self.assertEqual(lights.classify("running", None, None, None)[0], "green")

    def test_http(self):
        ok = {"code": 200, "ms": 12, "content": "json", "status": "ok"}
        self.assertEqual(lights.classify("running", None, ok, 5000), ("green", "HTTP 200 en 12 ms"))
        self.assertEqual(lights.classify("running", None, {"error": "connexion refusée"}, 5000)[0], "red")
        self.assertEqual(lights.classify("running", None, {"code": 502, "ms": 5}, 5000)[0], "red")
        self.assertEqual(lights.classify("running", None, {"code": 200, "ms": 5, "status": "degraded"}, 5000)[0], "orange")
        self.assertEqual(lights.classify("running", None, {"code": 200, "ms": 4500}, 5000)[0], "orange")
        self.assertEqual(lights.classify("running", None, {"code": 401, "ms": 5}, 5000)[0], "green")
        self.assertEqual(lights.classify("running", None, {"code": 404, "ms": 5}, 5000)[0], "orange")

    def test_ports_and_kind(self):
        self.assertEqual(lights.exposed_port({"Config": {"ExposedPorts": {"5173/tcp": {}, "5000/tcp": {}, "53/udp": {}}}}), 5000)
        self.assertIsNone(lights.exposed_port({"Config": {}}))
        self.assertEqual(lights.guess_kind("pixel-grid-postgres", 5432, None), "db")
        self.assertEqual(lights.guess_kind("hub", 5173, {"content": "html"}), "front")
        self.assertEqual(lights.guess_kind("nebula-api", 5000, {"content": "json"}), "api")
        self.assertEqual(lights.guess_kind("rsyslog-listener", None, None), "service")

    def test_summary(self):
        s = lights.summarize([{"light": "green"}, {"light": "red"}, {"light": "orange"}])
        self.assertEqual(s["verdict"], "red")
        self.assertEqual(s["counts"]["green"], 1)
        self.assertEqual(lights.summarize([{"light": "green"}])["verdict"], "green")
        self.assertEqual(lights.summarize([])["verdict"], "grey")


if __name__ == "__main__":
    unittest.main()
