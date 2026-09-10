#!/usr/bin/env python3
"""Plugin si-agent « docker-containers » (livraison #420) -- exemple de
sonde Python : liste les conteneurs de l'hôte via `docker ps`. Sortie
JSON sur stdout ; code de retour 2 si docker est absent (mesure en
erreur, explicite)."""
import json
import shutil
import subprocess
import sys


def main():
    if not shutil.which("docker"):
        print(json.dumps({"error": "docker absent"}))
        return 2
    try:
        p = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    if p.returncode != 0:
        print(json.dumps({"error": (p.stderr or "").strip()[:300]}))
        return 2
    containers = []
    for line in p.stdout.splitlines():
        try:
            c = json.loads(line)
        except ValueError:
            continue
        containers.append({"name": c.get("Names"), "image": c.get("Image"), "state": c.get("State"),
                           "status": c.get("Status"), "ports": c.get("Ports")})
    running = sum(1 for c in containers if c.get("state") == "running")
    print(json.dumps({"containers": containers, "total": len(containers), "running": running,
                      "not_running": [c["name"] for c in containers if c.get("state") != "running"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
