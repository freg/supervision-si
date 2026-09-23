# -*- coding: utf-8 -*-
"""Auto-mise à jour de l'agent (livraison #522), déclenchée par une commande
`update` du central -- jamais spontanée.

Demandé : « que les agents soient en mesure de s'auto mettre à jour, que
dans le front on voie l'état des mises à jour, avec un contrôle sur le
déploiement : un premier qui bêta-teste, puis activation volontaire de
l'administrateur ; auto-installation mais déploiement contrôlé depuis le
central ». Le CENTRAL décide (canal bêta, activation générale, cadence) et
envoie `update {version, sha256, url}` ; l'AGENT télécharge l'archive par
le même TLS que ses dépôts, vérifie le SHA-256, l'extrait et lance
l'installeur de sa plateforme en mode `--upgrade` (configuration, secret,
CA et sondes conservés), DÉTACHÉ de son propre processus (systemd-run /
nouvelle session) puisque l'installeur le redémarre. Il acquitte
« démarré » avant de s'arrêter ; au redémarrage, un marqueur permet
d'émettre `agent-updated` (ou `agent-update-failed` si la version n'a pas
changé). Logique pure séparée (vérification, choix de l'installeur,
marqueur) : tests/test_updater.py."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

def verify_archive(data, expected_sha256):
    """SHA-256 de l'archive téléchargée == annoncé par le central."""
    got = hashlib.sha256(data).hexdigest()
    exp = (expected_sha256 or "").lower().replace("sha256:", "")
    return got == exp, got


def safe_extract(tar, dest):
    """Extraction refusant tout chemin sortant de dest."""
    base = os.path.abspath(dest)
    for m in tar.getmembers():
        target = os.path.abspath(os.path.join(base, m.name))
        if not (target == base or target.startswith(base + os.sep)):
            raise ValueError("chemin refusé dans l'archive : %s" % m.name)
        if m.issym() or m.islnk():
            raise ValueError("lien refusé dans l'archive : %s" % m.name)
    tar.extractall(base)


def find_root(dest):
    """Le dossier si-agent-agent-<version>/ extrait (un seul attendu)."""
    dirs = [d for d in os.listdir(dest) if d.startswith("si-agent-agent-") and os.path.isdir(os.path.join(dest, d))]
    return os.path.join(dest, dirs[0]) if len(dirs) == 1 else None


def installer_command(root, platform=None, which=None):
    """Commande DÉTACHÉE de l'installeur en mode --upgrade, selon la plateforme."""
    platform = platform or sys.platform
    which = which or shutil.which
    if platform == "win32":
        ps1 = os.path.join(root, "windows", "install.ps1")
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-Upgrade"], "detached"
    if platform == "darwin":
        return ["/bin/bash", os.path.join(root, "install-macos.sh"), "--upgrade"], "setsid"
    script = os.path.join(root, "install.sh")
    if which("systemd-run"):
        unit = "si-agent-update-%d" % int(time.time())
        return ["systemd-run", "--unit", unit, "--collect", "--quiet", "/bin/bash", script, "--upgrade"], "systemd-run"
    return ["/bin/bash", script, "--upgrade"], "setsid"


def pending_path(state_path):
    return os.path.join(os.path.dirname(state_path or "/var/lib/si-agent/state.json"), "update-pending.json")


def write_pending(path, from_version, to_version, command_id, now=None, log_path=None):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"from": from_version, "to": to_version, "command": command_id, "at": int(now or time.time()), "log": log_path}, fh)


def log_tail(path, lines=30):
    """#576 : dernières lignes du journal de l'installeur (diagnostic d'une mise à jour qui n'a rien donné)."""
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:])[-4000:]
    except OSError:
        return ""


STALL_SECONDS = 900


def check_stalled(path, current_version, now=None):
    """#576 : l'installeur a été lancé mais l'agent tourne toujours, même
    version, après STALL_SECONDS -> événement agent-update-failed avec la fin
    du journal de l'installeur ; le marqueur est consommé. None sinon."""
    try:
        with open(path, encoding="utf-8") as fh:
            p = json.load(fh)
    except (OSError, ValueError):
        return None
    if (now or time.time()) - int(p.get("at") or 0) < STALL_SECONDS or p.get("to") == current_version:
        return None
    try:
        os.unlink(path)
    except OSError:
        pass
    tail = log_tail(p.get("log"))
    return ("agent-update-failed", "warning", "mise à jour %s → %s : l'installeur n'a pas relancé l'agent (toujours en %s)%s"
            % (p.get("from"), p.get("to"), current_version, (" -- " + tail.strip().splitlines()[-1][:200]) if tail.strip() else " -- journal vide"),
            dict(p, log_tail=tail))


def check_pending(path, current_version, now=None):
    """Au démarrage : (événement, détails) ou None ; le marqueur est consommé."""
    try:
        with open(path, encoding="utf-8") as fh:
            p = json.load(fh)
    except (OSError, ValueError):
        return None
    try:
        os.unlink(path)
    except OSError:
        pass
    if p.get("to") == current_version:
        return ("agent-updated", "info", "agent mis à jour %s → %s" % (p.get("from"), current_version), p)
    return ("agent-update-failed", "warning", "mise à jour %s → %s non appliquée (version courante %s)" % (p.get("from"), p.get("to"), current_version), dict(p, log_tail=log_tail(p.get("log"))))


def run_update(agent, params, fetch, spawn=None, current_version=None):
    """Exécute la commande `update`. `fetch(path) -> bytes` télécharge par le
    client HTTP de l'agent (même TLS, même CA) ; `spawn(cmd, mode)` lance
    l'installeur détaché (injectable pour les tests)."""
    current_version = current_version or __import__("si_agent").__version__
    target = str(params.get("version") or "")
    if not target:
        return {"ok": False, "error": "params.version requis"}
    if target == current_version:
        return {"ok": True, "result": {"already": True, "version": current_version}}
    url = params.get("url") or "/package"
    try:
        data = fetch(url)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "téléchargement impossible : %s" % exc}
    ok, got = verify_archive(data, params.get("sha256"))
    if not ok:
        return {"ok": False, "error": "SHA-256 différent (reçu %s…) : archive refusée" % got[:16]}
    dest = tempfile.mkdtemp(prefix="si-agent-update-")
    try:
        with tarfile.open(fileobj=__import__("io").BytesIO(data), mode="r:gz") as tar:
            safe_extract(tar, dest)
        root = find_root(dest)
        if not root:
            return {"ok": False, "error": "archive sans dossier si-agent-agent-<version>"}
    except (tarfile.TarError, ValueError, OSError) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        return {"ok": False, "error": "archive illisible : %s" % exc}
    cmd, mode = installer_command(root)
    pend = pending_path(agent.cfg.get("state_path"))
    log_path = os.path.join(os.path.dirname(pend), "update-%d.log" % int(time.time()))  # #576 : sortie de l'installeur conservée
    write_pending(pend, current_version, target, params.get("command_id"), log_path=log_path)
    try:
        (spawn or _spawn)(cmd, mode, log_path)
    except Exception as exc:  # noqa: BLE001 -- lancement impossible (droits, binaire) : dit tout de suite
        try:
            os.unlink(pend)
        except OSError:
            pass
        return {"ok": False, "error": "lancement de l'installeur impossible : %s" % exc}
    return {"ok": True, "result": {"started": True, "from": current_version, "to": target, "installer": mode, "log": log_path}}


def _spawn(cmd, mode, log_path=None):
    try:
        out = open(log_path, "ab") if log_path else subprocess.DEVNULL
    except OSError:
        out = subprocess.DEVNULL
    kw = {"stdin": subprocess.DEVNULL, "stdout": out, "stderr": subprocess.STDOUT if out is not subprocess.DEVNULL else subprocess.DEVNULL, "close_fds": True}
    if mode == "detached" and sys.platform == "win32":
        kw["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    elif mode == "setsid":
        kw["start_new_session"] = True
    subprocess.Popen(cmd, **kw)
