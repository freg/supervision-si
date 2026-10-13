"""Pilotage d'Ollama sur l'hôte de l'agent (livraison #746) -- déploiement de modèles depuis le hub.

Commande `ollama` du central, params {action, model?} :
  status   version, modèles présents, modèles chargés (mémoire GPU), téléchargement en cours
  pull     télécharge un modèle (détaché ; progression dans status, événement à la fin)
  delete   supprime un modèle
  load     charge un modèle en mémoire (keep_alive, défaut 30m)
  unload   le décharge
  test     courte génération : débit (tokens/s) et part GPU
Ollama est joint en local (OLLAMA_URL, défaut http://127.0.0.1:11434) ; stdlib seulement.
"""
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434"
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
ACTIONS = ("status", "pull", "delete", "load", "unload", "test")


def base_url(cfg=None):
    return ((cfg or {}).get("ollama_url") or os.environ.get("OLLAMA_URL") or DEFAULT_URL).rstrip("/")


def _req(url, path, body=None, method=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url + path, data=data, method=method or ("POST" if data else "GET"),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw) if raw.strip() else {}


def valid_model(name):
    return bool(name) and bool(MODEL_RE.match(name)) and ".." not in name


def models_dir():
    """Dossier des modèles : OLLAMA_MODELS du service systemd, sinon emplacements usuels."""
    try:
        out = subprocess.run(["systemctl", "show", "ollama", "-p", "Environment", "--value"], capture_output=True,
                             text=True, timeout=5).stdout
        for tok in out.split():
            if tok.startswith("OLLAMA_MODELS="):
                return tok.split("=", 1)[1]
    except Exception:  # noqa: BLE001
        pass
    for d in ("/usr/share/ollama/.ollama/models", os.path.expanduser("~/.ollama/models")):
        if os.path.isdir(d):
            return d
    return None


def status(url, pull=None):
    out = {"url": url, "up": False, "pull": pull}
    try:
        out["version"] = _req(url, "/api/version", timeout=5).get("version")
        out["up"] = True
    except Exception as exc:  # noqa: BLE001
        out["error"] = "Ollama injoignable (%s)" % str(exc)[:120]
        return out
    tags = _req(url, "/api/tags").get("models") or []
    ps = {m.get("name"): m for m in (_req(url, "/api/ps").get("models") or [])}
    models = []
    for m in tags:
        d = m.get("details") or {}
        loaded = ps.get(m.get("name"))
        row = {"name": m.get("name"), "size": m.get("size"), "modified": m.get("modified_at"), "family": d.get("family"),
               "params": d.get("parameter_size"), "quant": d.get("quantization_level"), "loaded": bool(loaded)}
        if loaded:
            size, vram = loaded.get("size") or 0, loaded.get("size_vram") or 0
            row.update({"loaded_size": size, "vram": vram, "gpu_pct": round(100.0 * vram / size) if size else None,
                        "expires": loaded.get("expires_at"), "context": loaded.get("context_length")})
        models.append(row)
    out["models"] = sorted(models, key=lambda r: r["name"] or "")
    d = models_dir()
    if d and os.path.isdir(d):
        u = shutil.disk_usage(d)
        out["models_dir"] = {"path": d, "free": u.free, "total": u.total}
    return out


def pull(url, model, progress=None, timeout=6 * 3600):
    """Téléchargement en flux ; `progress(dict)` reçoit {status, completed, total}. Renvoie (ok, erreur)."""
    r = urllib.request.Request(url + "/api/pull", data=json.dumps({"model": model, "stream": True}).encode(),
                               headers={"Content-Type": "application/json"})
    last = 0.0
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            for line in resp:
                if not line.strip():
                    continue
                ev = json.loads(line)
                if ev.get("error"):
                    return False, ev["error"][:300]
                if progress and (time.time() - last > 2 or ev.get("status") == "success"):
                    progress({"status": ev.get("status"), "completed": ev.get("completed"), "total": ev.get("total")})
                    last = time.time()
                if ev.get("status") == "success":
                    return True, None
    except urllib.error.HTTPError as exc:
        return False, "HTTP %s : %s" % (exc.code, exc.read()[:200].decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:300]
    return False, "flux interrompu avant la fin"


def run_action(params, url, pull_state=None, start_pull=None):
    """Exécute une action synchrone ; `pull` est délégué à start_pull(model) (fil détaché côté agent)."""
    action = (params or {}).get("action") or "status"
    model = ((params or {}).get("model") or "").strip()
    if action not in ACTIONS:
        return {"ok": False, "error": "action inconnue (%s)" % ", ".join(ACTIONS)}
    if action == "status":
        st = status(url, pull_state)
        return {"ok": st["up"], "error": st.get("error"), "status": st}
    if not valid_model(model):
        return {"ok": False, "error": "nom de modèle invalide : %r" % model[:80]}
    try:
        if action == "pull":
            if pull_state and pull_state.get("running"):
                return {"ok": False, "error": "téléchargement déjà en cours : %s" % pull_state.get("model")}
            start_pull(model)
            return {"ok": True, "message": "téléchargement de %s lancé (suivi : État, et événement à la fin)" % model}
        if action == "delete":
            _req(url, "/api/delete", {"model": model}, method="DELETE")
            return {"ok": True, "message": "%s supprimé" % model}
        if action == "load":
            keep = str((params or {}).get("keep_alive") or "30m")
            _req(url, "/api/generate", {"model": model, "keep_alive": keep}, timeout=600)
            st = status(url, pull_state)
            row = next((m for m in st.get("models") or [] if m["name"] == model), {})
            return {"ok": True, "message": "%s chargé (%s %% GPU, garde %s)" % (model, row.get("gpu_pct", "?"), keep), "model": row}
        if action == "unload":
            _req(url, "/api/generate", {"model": model, "keep_alive": 0}, timeout=60)
            return {"ok": True, "message": "%s déchargé" % model}
        if action == "test":
            prompt = str((params or {}).get("prompt") or "Réponds en une phrase : à quoi sert une sonde réseau ?")[:500]
            r = _req(url, "/api/generate", {"model": model, "prompt": prompt, "stream": False,
                                            "options": {"num_predict": 64}}, timeout=900)
            ec, ed = r.get("eval_count") or 0, r.get("eval_duration") or 0
            rate = round(ec / (ed / 1e9), 1) if ed else None
            st = status(url, pull_state)
            row = next((m for m in st.get("models") or [] if m["name"] == model), {})
            return {"ok": True, "message": "%s : %s tokens/s, %s %% GPU" % (model, rate, row.get("gpu_pct", "?")),
                    "rate": rate, "gpu_pct": row.get("gpu_pct"), "load_s": round((r.get("load_duration") or 0) / 1e9, 1),
                    "answer": (r.get("response") or "")[:400]}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": "HTTP %s : %s" % (exc.code, exc.read()[:200].decode("utf-8", "replace"))}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": False, "error": "action non traitée"}
