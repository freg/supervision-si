#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Miroir froid du hub (livraison #663, étape 3 de docs/architecture-clonage-distribution-hub.md) -- actif/passif :
le PRIMAIRE (ici) envoie ses sauvegardes totales/incrémentales (scripts/full_backup.py, chiffrées, #458-#460) à l'agent
de nœud du MIROIR (deploy/node_agent.py, VPN + jeton) qui les restaure par-dessus son dépôt, services arrêtés.
RPO = intervalle entre deux `sync` ; RTO = `failover` (regenerate + démarrage de tout + bascule de rôle).
Bibliothèque standard seulement. Configuration : deploy/mirror.local.json (modèle : deploy/mirror.example.json).

  deploy/mirror.py status              dernière synchro (âge, RPO), archives présentes sur le miroir, services qui y tournent
  deploy/mirror.py sync [--full]       sauvegarde (incrémentale si possible) -> envoi de la chaîne manquante -> restauration sur le miroir
  deploy/mirror.py failover            le miroir devient actif (takeover) ; la bascule de rôle est faite par la tour (si role_id)
  deploy/mirror.py failback            retour : sauvegarde du miroir -> restaurée ici (services arrêtés puis relancés) -> miroir en standby
  deploy/mirror.py prune               garde `keep` sauvegardes totales (et leurs incrémentales) dans backups/mirror-out/
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "deploy"))
CONFIG = os.path.join(ROOT, "deploy", "mirror.local.json")
OUT = os.path.join(ROOT, "backups", "mirror-out")
STATE = os.path.join(ROOT, "deploy", "generated", "mirror-primary.state.json")
DEFAULT_PORT = 6460


def load_config(path=CONFIG):
    if not os.path.exists(path):
        raise RuntimeError("deploy/mirror.local.json absent (modèle : deploy/mirror.example.json)")
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if not cfg.get("node"):
        raise RuntimeError("mirror.local.json : node (nom du nœud miroir dans nodes.json) requis")
    return cfg


def state(update=None):
    st = {}
    try:
        with open(STATE, encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        pass
    if update:
        st.update(update); os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as fh:
            json.dump(st, fh, indent=2, ensure_ascii=False)
    return st


def chain_files(archive):
    """Archive + manifeste + toute la chaîne (totale et incrémentales précédentes) : ce que le miroir doit posséder."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("full_backup", os.path.join(ROOT, "scripts", "full_backup.py"))
    fb = importlib.util.module_from_spec(spec); spec.loader.exec_module(fb)
    files = []
    for arc in fb.chain_for(archive):
        stem = os.path.basename(arc).replace(".tar.gz.enc", "").replace(".tar.gz", "")
        files.append(arc)
        mp = os.path.join(os.path.dirname(arc), stem + ".manifest.json")
        if os.path.exists(mp):
            files.append(mp)
    return files


def to_push(files, remote):
    """Fichiers de la chaîne que le miroir n'a pas encore (nom + taille identiques = déjà là). Pur."""
    have = {a["name"]: a["size"] for a in remote}
    return [f for f in files if have.get(os.path.basename(f)) != os.path.getsize(f)]


def age_text(iso, now=None):
    if not iso:
        return "jamais"
    try:
        t = time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return iso
    s = int((now or time.time()) - t)
    return "%d min" % (s // 60) if s < 3600 else "%.1f h" % (s / 3600)


class Mirror:
    def __init__(self, cfg):
        import node_agent as na
        env = na.load_env()
        self.token, self.port = env.get("SI_NODE_TOKEN", ""), int(env.get("SI_NODE_PORT") or DEFAULT_PORT)
        if not self.token:
            raise RuntimeError("SI_NODE_TOKEN absent du .env")
        nodes = na.read_json(na.NODES)
        n = next((x for x in nodes["nodes"] if x["name"] == cfg["node"]), None)
        if not n:
            raise RuntimeError("nœud miroir %s inconnu de deploy/nodes.json" % cfg["node"])
        self.base = "http://%s:%d" % (n["wg_address"], self.port)
        self.passphrase = env.get("SI_BACKUP_PASSPHRASE", "")

    def call(self, method, path, body=None, data=None, timeout=7200):
        req = urllib.request.Request(self.base + path, method=method, data=data if data is not None else (json.dumps(body).encode("utf-8") if body is not None else None),
                                     headers={"X-SI-Node-Token": self.token, "Content-Type": "application/octet-stream" if data is not None else "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError("%s %s : HTTP %d %s" % (method, path, e.code, e.read()[:300].decode("utf-8", "replace")))
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError("miroir injoignable (%s) : %s" % (self.base, e))

    def push(self, path):
        with open(path, "rb") as fh:
            return self.call("PUT", "/mirror/archive/" + os.path.basename(path), data=fh.read())

    def pull(self, name, dest_dir):
        req = urllib.request.Request(self.base + "/mirror/archive/" + name, headers={"X-SI-Node-Token": self.token})
        os.makedirs(dest_dir, exist_ok=True); dest = os.path.join(dest_dir, name)
        with urllib.request.urlopen(req, timeout=7200) as resp, open(dest + ".part", "wb") as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
        os.replace(dest + ".part", dest)
        return dest


def local_backup(full=False):
    os.makedirs(OUT, exist_ok=True)
    before = set(glob.glob(os.path.join(OUT, "*.tar.gz*")))
    env = dict(os.environ)
    import node_agent as na
    pw = na.load_env().get("SI_BACKUP_PASSPHRASE")
    if pw:
        env["SI_BACKUP_PASSPHRASE"] = pw
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "full_backup.py"), "backup", "--out", OUT] + ([] if full else ["--incremental"])
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("sauvegarde en échec : " + (r.stderr or r.stdout)[-500:])
    new = sorted(set(glob.glob(os.path.join(OUT, "*.tar.gz*"))) - before, key=os.path.getmtime)
    if not new:
        raise RuntimeError("aucune archive produite")
    return new[-1]


def cmd_sync(cfg, full=False):
    m = Mirror(cfg); t0 = time.time()
    remote = m.call("GET", "/mirror/status", timeout=30)
    if remote.get("running"):
        raise RuntimeError("le miroir fait tourner des services (%s) : il est actif ? standby d'abord" % ", ".join(remote["running"][:5]))
    archive = local_backup(full)
    files = chain_files(archive)
    pushed = []
    for f in to_push(files, remote.get("archives") or []):
        m.push(f); pushed.append(os.path.basename(f))
    r = m.call("POST", "/mirror/restore", {"archive": os.path.basename(archive)})
    st = {"last_sync": time.strftime("%Y-%m-%dT%H:%M:%S"), "last_archive": os.path.basename(archive), "pushed": pushed, "sync_seconds": int(time.time() - t0), "restore_seconds": r.get("restore_seconds")}
    state(st)
    return st


def cmd_status(cfg):
    st = state()
    out = {"primary": st, "age": age_text(st.get("last_sync")), "rpo_ok": None}
    if st.get("last_sync"):
        try:
            out["rpo_ok"] = (time.time() - time.mktime(time.strptime(st["last_sync"][:19], "%Y-%m-%dT%H:%M:%S"))) <= int(cfg.get("rpo_warning_s") or 7200)
        except ValueError:
            pass
    try:
        out["mirror"] = Mirror(cfg).call("GET", "/mirror/status", timeout=15)
    except RuntimeError as e:
        out["mirror"] = {"error": str(e)}
    return out


def cmd_failover(cfg):
    m = Mirror(cfg)
    r = m.call("POST", "/mirror/takeover", {"host_ip": cfg.get("host_ip") or ""})
    state({"failover_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mirror_active": True})
    return r


def cmd_failback(cfg):
    """Le miroir actif sauvegarde ; le primaire récupère, s'arrête, restaure, redémarre ; le miroir repasse en standby."""
    m = Mirror(cfg); t0 = time.time()
    b = m.call("POST", "/mirror/backup")
    files = [b["archive"], b["archive"].replace(".tar.gz.enc", "").replace(".tar.gz", "") + ".manifest.json"]
    got = []
    for name in files:
        try:
            got.append(m.pull(name, os.path.join(ROOT, "backups", "mirror-in")))
        except urllib.error.HTTPError:
            pass
    subprocess.run(["./scripts/run-all.sh", "all", "down"], cwd=ROOT, check=True)
    env = dict(os.environ)
    import node_agent as na
    pw = na.load_env().get("SI_BACKUP_PASSPHRASE")
    if pw:
        env["SI_BACKUP_PASSPHRASE"] = pw
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "full_backup.py"), "restore", got[0], "--into", ROOT, "--force"], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "full_backup.py"), "regenerate"], cwd=ROOT, check=True)
    subprocess.run(["./scripts/run-all.sh", "all", "up", "-d"], cwd=ROOT, check=True)
    m.call("POST", "/mirror/standby")
    st = {"failback_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "mirror_active": False, "failback_seconds": int(time.time() - t0), "restored_from": os.path.basename(got[0])}
    state(st)
    return st


def cmd_prune(cfg):
    keep = int(cfg.get("keep") or 3)
    fulls = sorted(f for f in glob.glob(os.path.join(OUT, "*.manifest.json")) if json.load(open(f, encoding="utf-8")).get("kind", "full") == "full")
    removed = []
    for mp in fulls[:-keep] if len(fulls) > keep else []:
        stem = mp[:-len(".manifest.json")]
        for f in glob.glob(stem + "*"):
            os.remove(f); removed.append(os.path.basename(f))
    return {"removed": removed, "kept_full": min(len(fulls), keep)}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        cfg = load_config()
        if cmd == "status":
            print(json.dumps(cmd_status(cfg), indent=2, ensure_ascii=False)); return 0
        if cmd == "sync":
            print(json.dumps(cmd_sync(cfg, "--full" in sys.argv), indent=2, ensure_ascii=False)); return 0
        if cmd == "failover":
            print(json.dumps(cmd_failover(cfg), indent=2, ensure_ascii=False)); return 0
        if cmd == "failback":
            print(json.dumps(cmd_failback(cfg), indent=2, ensure_ascii=False)); return 0
        if cmd == "prune":
            print(json.dumps(cmd_prune(cfg), indent=2, ensure_ascii=False)); return 0
    except RuntimeError as e:
        print("miroir : %s" % e, file=sys.stderr); return 1
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
