# -*- coding: utf-8 -*-
"""#881 : chaque module local importé par l'API (directement ou non) est copié dans l'image -- le Dockerfile liste ses
fichiers un par un ; etat_plan.py oublié (#878) donnait un 500 sur l'Excel des décideurs."""
import os
import re
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))


class DockerfileModules(unittest.TestCase):
    def test_modules_copies(self):
        with open(os.path.join(ICI, "Dockerfile"), encoding="utf-8") as fh:
            d = fh.read()
        copies = set(re.findall(r"COPY si-agent/api/([A-Za-z0-9_]+\.py) ", d))
        vus, a_voir = set(), ["app.py"]
        while a_voir:
            f = a_voir.pop()
            if f in vus:
                continue
            vus.add(f)
            with open(os.path.join(ICI, f), encoding="utf-8") as fh:
                for m in re.findall(r"^\s*(?:import|from) ([A-Za-z0-9_]+)", fh.read(), re.M):
                    if os.path.exists(os.path.join(ICI, m + ".py")):
                        a_voir.append(m + ".py")
        self.assertEqual(sorted(vus - copies - {"app.py"}), [], "modules à ajouter au Dockerfile (COPY si-agent/api/<module>.py .)")


if __name__ == "__main__":
    unittest.main()
