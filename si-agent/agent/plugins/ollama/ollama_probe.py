#!/usr/bin/env python3
"""Sonde ollama (#746) : état d'Ollama sur l'hôte, en lecture seule (API locale, stdlib).
Usage : ollama_probe.py [--url http://127.0.0.1:11434] [--min-free-gb 20]
Sortie JSON : {at, url, up, version, models[], loaded, models_dir, alerts[], error}."""
import json
import os
import shutil
import sys
import time
import urllib.request


def get(url, path, timeout=8):
    with urllib.request.urlopen(url + path, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def _systemd_models_dir():
    try:
        import subprocess
        env = subprocess.run(["systemctl", "show", "ollama", "-p", "Environment", "--value"], capture_output=True,
                             text=True, timeout=5).stdout
        return next((t.split("=", 1)[1] for t in env.split() if t.startswith("OLLAMA_MODELS=")), None)
    except Exception:  # noqa: BLE001
        return None


def collect(url, min_free_gb=20.0, models_dir=None):
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "url": url, "up": False, "models": [], "loaded": 0,
           "alerts": [], "error": None}
    try:
        out["version"] = get(url, "/api/version", 5).get("version")
        out["up"] = True
    except Exception as exc:  # noqa: BLE001
        out["error"] = "Ollama injoignable : %s" % str(exc)[:150]
        out["alerts"].append({"code": "ollama-down", "severity": "critical", "message": out["error"]})
        return out
    ps = {m.get("name"): m for m in get(url, "/api/ps").get("models") or []}
    for m in get(url, "/api/tags").get("models") or []:
        d = m.get("details") or {}
        row = {"name": m.get("name"), "size": m.get("size"), "modified": m.get("modified_at"), "family": d.get("family"),
               "params": d.get("parameter_size"), "quant": d.get("quantization_level"), "loaded": m.get("name") in ps}
        p = ps.get(m.get("name"))
        if p:
            size, vram = p.get("size") or 0, p.get("size_vram") or 0
            row.update({"loaded_size": size, "vram": vram, "gpu_pct": round(100.0 * vram / size) if size else None,
                        "expires": p.get("expires_at"), "context": p.get("context_length")})
            if row["gpu_pct"] is not None and row["gpu_pct"] < 100:
                out["alerts"].append({"code": "model-off-gpu@%s" % row["name"], "severity": "warning",
                                      "message": "%s chargé à %s %% sur GPU (le reste sur processeur : réponses lentes)" % (row["name"], row["gpu_pct"])})
        out["models"].append(row)
    out["models"].sort(key=lambda r: r["name"] or "")
    out["loaded"] = sum(1 for r in out["models"] if r["loaded"])
    d = models_dir or os.environ.get("OLLAMA_MODELS") or _systemd_models_dir()
    if not d:
        for c in ("/usr/share/ollama/.ollama/models", "/var/lib/ollama/models"):
            if os.path.isdir(c):
                d = c
                break
    if d and os.path.isdir(d):
        u = shutil.disk_usage(d)
        out["models_dir"] = {"path": d, "free": u.free, "total": u.total}
        if u.free < min_free_gb * 1e9:
            out["alerts"].append({"code": "models-dir-full", "severity": "warning",
                                  "message": "dossier des modèles %s : %.0f Go libres" % (d, u.free / 1e9)})
    return out


def main(argv):
    url, min_free, mdir, i = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"), 20.0, None, 0
    while i < len(argv):
        a, v = argv[i], argv[i + 1] if i + 1 < len(argv) else None
        if a == "--url" and v:
            url = v
        elif a == "--min-free-gb" and v:
            min_free = float(v)
        elif a == "--models-dir" and v:
            mdir = v
        i += 2
    print(json.dumps(collect(url.rstrip("/"), min_free, mdir)))


if __name__ == "__main__":
    main(sys.argv[1:])
