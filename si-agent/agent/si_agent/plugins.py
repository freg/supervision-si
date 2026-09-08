"""Moteur de plugins / sondes (livraison #420) -- « l'agent sert de
machine-moteur pour la gestion de plugins / sondes », « déployer des
sondes futures en Python ou en shell/bash ».

Un plugin = un dossier `<plugins_dir>/<id>/` contenant `manifest.json` et
le script d'entrée :

    {"id": "network-neighbors", "version": "1", "runner": "shell",
     "entry": "network_neighbors.sh", "interval_seconds": 3600,
     "timeout_seconds": 60, "args": [], "enabled": false,
     "description": "...", "sha256": "<sha256 du script>",
     "signature": "<hmac>", "source": "bundled"|"central"}

Deux origines, deux niveaux de confiance :
  - `bundled` : livré avec le paquet (voir ../plugins/), installé par
    install.sh -- confiance du paquet lui-même ;
  - `central` : reçu du central. JAMAIS écrit sur le disque sans
    vérification : `sha256` du corps reçu = manifeste, et `signature` =
    HMAC-SHA256(secret de l'agent, id + "\\n" + version + "\\n" + sha256)
    -- même secret que l'authentification des mesures, donc seul le
    central qui connaît cet agent peut lui pousser du code.

Exécution : `bash entry args` ou `python3 entry args`, délai borné, sortie
standard attendue en JSON (sinon conservée en texte brut tronqué), code de
retour ≠ 0 = mesure en erreur. Chaque exécution devient une mesure
`plugin:<id>` dans la file, comme n'importe quel relevé.

`enabled` vient du manifeste (donc du central pour les siens) ; la
configuration locale de l'agent (`plugins: {"id": {"enabled": true}}`)
l'emporte -- le technicien sur place garde la main.
"""
import hashlib
import hmac
import json
import os
import shutil
import time

try:
    from . import control
except ImportError:  # copie à plat dans l'image du central (si_agent_plugins.py)
    import si_agent_control as control  # noqa: N813

RUNNERS = ("shell", "python", "powershell")  # powershell : #440 (Windows ; pwsh sous Linux s'il est installé)
MAX_RAW_OUTPUT = 4000


def sha256_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def plugin_signature(secret, plugin_id, version, digest, privileged=False):
    """HMAC du central sur (id, version, sha256) -- et sur le drapeau
    `privileged` quand il est levé (#422) : un plugin ne tourne en root
    que si le central l'a signé ainsi."""
    msg = control.plugin_signature_message(plugin_id, version, digest, privileged)
    return hmac.new((secret or "").encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_manifest(m):
    """(ok, raison). Identifiant = [a-z0-9-_], entrée = nom de fichier
    simple (jamais un chemin), runner connu, intervalle ≥ 30 s."""
    if not isinstance(m, dict):
        return False, "manifeste non-objet"
    pid = m.get("id")
    if not isinstance(pid, str) or not pid or any(c for c in pid if not (c.isalnum() or c in "-_")) or pid != pid.lower():
        return False, "id invalide (minuscules, chiffres, - et _)"
    if m.get("runner") not in RUNNERS:
        return False, "runner inconnu (shell|python|powershell)"
    entry = m.get("entry")
    if not isinstance(entry, str) or not entry or "/" in entry or entry.startswith(".") or "\\" in entry:
        return False, "entry invalide (nom de fichier simple)"
    try:
        interval = int(m.get("interval_seconds", 3600))
    except (TypeError, ValueError):
        return False, "interval_seconds non entier"
    if interval < 30:
        return False, "interval_seconds : 30 s minimum"
    if m.get("args") is not None and (not isinstance(m["args"], list) or any(not isinstance(a, str) for a in m["args"])):
        return False, "args : liste de chaînes"
    if m.get("max_memory_mb") is not None:
        try:
            if int(m["max_memory_mb"]) < 16:
                return False, "max_memory_mb : 16 Mo minimum"
        except (TypeError, ValueError):
            return False, "max_memory_mb non entier"
    return True, "ok"


class PluginStore(object):
    def __init__(self, plugins_dir):
        self.dir = plugins_dir

    def _path(self, pid):
        return os.path.join(self.dir, pid)

    def list(self):
        out = []
        if not os.path.isdir(self.dir):
            return out
        for name in sorted(os.listdir(self.dir)):
            mp = os.path.join(self.dir, name, "manifest.json")
            try:
                with open(mp, "r") as fh:
                    m = json.load(fh)
            except (OSError, ValueError):
                continue
            ok, _ = validate_manifest(m)
            if not ok or m.get("id") != name:
                continue
            entry_path = os.path.join(self.dir, name, m["entry"])
            m["present"] = os.path.isfile(entry_path)
            m["path"] = entry_path
            out.append(m)
        return out

    def ensure_permissions(self):
        """Sondes installées AVANT le confinement (#420/#421, scripts en 0750
        root) : l'utilisateur non privilégié doit pouvoir traverser le dossier
        et lire le script -- normalisé au démarrage, best-effort."""
        fixed = 0
        try:
            if os.path.isdir(self.dir) and (os.stat(self.dir).st_mode & 0o055) != 0o055:
                os.chmod(self.dir, 0o755); fixed += 1
            for m in self.list():
                d = os.path.dirname(m["path"])
                for path, want in ((d, 0o755), (m["path"], 0o755)):
                    if os.path.exists(path) and (os.stat(path).st_mode & 0o777) != want:
                        os.chmod(path, want); fixed += 1
        except OSError:
            pass
        return fixed

    def get(self, pid):
        for m in self.list():
            if m["id"] == pid:
                return m
        return None

    def install(self, manifest, body, source="central", secret=None):
        """Écrit un plugin. `central` exige sha256 + signature valides
        (voir en-tête) ; `bundled` exige seulement un manifeste valide.
        Renvoie (ok, raison)."""
        ok, why = validate_manifest(manifest)
        if not ok:
            return False, why
        digest = sha256_text(body)
        if source == "central":
            if manifest.get("sha256") != digest:
                return False, "sha256 du script différent du manifeste"
            expected = plugin_signature(secret, manifest["id"], str(manifest.get("version", "")), digest,
                                        privileged=bool(manifest.get("privileged")))
            if not secret or not hmac.compare_digest(expected, str(manifest.get("signature") or "")):
                return False, "signature du central invalide"
        target = self._path(manifest["id"])
        os.makedirs(target, exist_ok=True)
        try:
            os.chmod(self.dir, 0o755)
        except OSError:
            pass
        os.chmod(target, 0o755)  # lisible par l'utilisateur non privilégié qui exécute la sonde (#422)
        entry_path = os.path.join(target, manifest["entry"])
        with open(entry_path, "w") as fh:
            fh.write(body)
        os.chmod(entry_path, 0o755)
        stored = dict(manifest)
        stored["sha256"] = digest
        stored["source"] = source
        stored["installed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        stored.pop("path", None)
        stored.pop("present", None)
        with open(os.path.join(target, "manifest.json"), "w") as fh:
            json.dump(stored, fh, indent=2, ensure_ascii=False)
        return True, "ok"

    def remove(self, pid):
        p = self._path(pid)
        if not os.path.isdir(p):
            return False
        shutil.rmtree(p)
        return True

    def set_enabled(self, pid, enabled):
        return self.set_flag(pid, "enabled", bool(enabled))

    def set_flag(self, pid, key, value):
        """Met à jour un drapeau du manifeste stocké (enabled, blocked)."""
        m = self.get(pid)
        if m is None:
            return False
        m = {k: v for k, v in m.items() if k not in ("path", "present")}
        m[key] = value
        with open(os.path.join(self._path(pid), "manifest.json"), "w") as fh:
            json.dump(m, fh, indent=2, ensure_ascii=False)
        return True


def is_enabled(manifest, local_overrides=None):
    """Le manifeste décide, la configuration locale l'emporte."""
    local = (local_overrides or {}).get(manifest.get("id")) or {}
    if "enabled" in local:
        return bool(local["enabled"])
    return bool(manifest.get("enabled", False))


def run_plugin(manifest, cmd, now=None, env=None, python="python3", shell="bash", confine=None):
    """Exécute un plugin ; renvoie une mesure `plugin:<id>`. `confine`
    (#422) : {"env", "preexec_fn", "cwd"} transmis à run_cmd -- session,
    limites, utilisateur non privilégié ; absent = exécution simple (tests,
    faux cmd)."""
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time()))
    task = "plugin:%s" % manifest["id"]
    if not manifest.get("present", True):
        return {"task": task, "at": at, "ok": False, "error": "script absent : %s" % manifest.get("entry"), "data": None}
    runner = manifest.get("runner")
    if runner == "powershell":
        ps = "powershell.exe" if os.name == "nt" else "pwsh"
        argv = [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", manifest["path"]] + list(manifest.get("args") or [])
    elif runner == "shell" and os.name == "nt":
        return {"task": task, "at": at, "ok": False, "data": None,
                "error": "sonde shell (bash) non exécutable sous Windows -- prévoir un runner python ou powershell"}
    else:
        argv = [shell if runner == "shell" else python, manifest["path"]] + list(manifest.get("args") or [])
    timeout = int(manifest.get("timeout_seconds") or 60)
    started = time.monotonic()
    if confine is not None:
        r = cmd(argv, timeout=timeout, confined=confine)
    elif env is not None:
        r = cmd(argv, timeout=timeout, env=env)
    else:
        r = cmd(argv, timeout=timeout)
    duration = round(time.monotonic() - started, 3)
    stdout = (r.stdout or "").strip()
    data = None
    if stdout:
        try:
            parsed = json.loads(stdout)
            data = parsed if isinstance(parsed, dict) else {"result": parsed}
        except ValueError:
            data = {"raw": stdout[:MAX_RAW_OUTPUT], "truncated": len(stdout) > MAX_RAW_OUTPUT}
    ok = r.returncode == 0
    error = None if ok else ("code %s : %s" % (r.returncode, (r.stderr or stdout or "")[:500].strip()))
    m = {"task": task, "at": at, "ok": ok, "data": data, "error": error}
    if data is not None:
        data.setdefault("_plugin", {"id": manifest["id"], "version": str(manifest.get("version", "")), "duration_seconds": duration,
                                    "privileged": bool(manifest.get("privileged"))})
    return m
