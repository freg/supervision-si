"""Contrôle sécurisé des sondes (livraison #422) -- logique PURE partagée
par l'agent et le central (copiée au build de si-agent-api sous le nom
si_agent_control.py, jamais réimplémentée).

Trois sujets :

1. **Réponses signées du central.** Le protocole netprobe authentifie
   l'AGENT auprès du central (en-têtes X-Netprobe-*), pas l'inverse : la
   configuration et les commandes reçues n'étaient protégées que par TLS.
   Ici le central signe chaque réponse de la face agents :
   `X-Netprobe-Response-Timestamp` + `X-Netprobe-Response-Signature` =
   HMAC-SHA256(secret de l'agent, "response\\n" + timestamp + "\\n" +
   SHA256(corps)). L'agent refuse toute configuration / commande non
   signée ou mal signée -- même sur un central usurpé derrière un TLS
   accepté en `insecure`, rien ne s'exécute.
   Rejeu : le central pose `issued_at` (compteur de temps du central)
   dans la configuration, l'agent n'accepte jamais une configuration plus
   ancienne que la dernière appliquée ; les commandes ont un identifiant
   unique et l'agent mémorise ceux déjà exécutés.

2. **Blocage général et individuel.** État persistant de l'agent
   (`state.json`) : `blocked` (plus aucune sonde exécutée ni installée,
   la collecte hôte et les remontées continuent -- on voit toujours
   l'agent) et `blocked_plugins` (par identifiant). Vient de trois sources,
   la plus restrictive gagne : la configuration du central (déclaratif),
   une commande (immédiat), un fichier local `BLOCKED` à côté de la
   configuration (technicien sur place, sans réseau).

3. **Exécution confinée des sondes.** Environnement minimal, session
   propre (le délai tue tout le groupe de processus), priorité abaissée,
   limites de ressources (CPU, mémoire, fichiers), umask 077, et -- si
   l'agent tourne en root -- abandon des privilèges vers `plugins_user`
   sauf pour un plugin dont le manifeste signé porte `privileged: true`
   (la signature couvre ce drapeau : le central seul peut l'accorder).
"""
import hashlib
import hmac
import json
import os
import time

HEADER_RESP_TS = "X-Netprobe-Response-Timestamp"
HEADER_RESP_SIG = "X-Netprobe-Response-Signature"

BLOCK_COMMANDS = ("block_all", "unblock_all", "block_plugin", "unblock_plugin")

EVENT_SEVERITIES = ("info", "warning", "critical")


def _sha256(b):
    return hashlib.sha256(b or b"").hexdigest()


# -- réponses signées -------------------------------------------------------

def response_signature(secret, timestamp, body_bytes):
    msg = "response\n%s\n%s" % (int(timestamp), _sha256(body_bytes))
    return hmac.new((secret or "").encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def response_headers(secret, body_bytes, timestamp=None):
    ts = int(timestamp if timestamp is not None else time.time())
    return {HEADER_RESP_TS: str(ts), HEADER_RESP_SIG: response_signature(secret, ts, body_bytes)}


def verify_response(secret, headers, body_bytes):
    """(ok, raison). `headers` : dict ou objet à .get() insensible à la casse."""
    def get(name):
        if headers is None:
            return None
        v = headers.get(name)
        if v is None:
            v = headers.get(name.lower())
        return v
    ts, sig = get(HEADER_RESP_TS), get(HEADER_RESP_SIG)
    if not ts or not sig:
        return False, "réponse non signée par le central"
    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        return False, "horodatage de réponse invalide"
    if not secret:
        return False, "secret absent"
    expected = response_signature(secret, ts_int, body_bytes)
    if not hmac.compare_digest(expected, str(sig)):
        return False, "signature de réponse invalide"
    return True, "ok"


# -- signature de plugin étendue (drapeau privileged) ------------------------

def plugin_signature_message(plugin_id, version, digest, privileged=False):
    msg = "%s\n%s\n%s" % (plugin_id, version, digest)
    if privileged:
        msg += "\nprivileged"
    return msg


# -- état persistant (blocage, commandes vues, dernière configuration) ------

DEFAULT_STATE = {"blocked": False, "blocked_reason": None, "blocked_at": None, "blocked_plugins": {},
                 "last_config_issued_at": 0, "done_commands": []}
MAX_DONE_COMMANDS = 500


def load_state(path):
    try:
        with open(path, "r") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    st = dict(DEFAULT_STATE)
    st.update({k: v for k, v in (data or {}).items() if k in DEFAULT_STATE})
    if not isinstance(st.get("blocked_plugins"), dict):
        st["blocked_plugins"] = {}
    if not isinstance(st.get("done_commands"), list):
        st["done_commands"] = []
    return st


def save_state(path, state):
    tmp = path + ".tmp"
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def remember_command(state, cid):
    done = state.setdefault("done_commands", [])
    if cid in done:
        return False
    done.append(cid)
    if len(done) > MAX_DONE_COMMANDS:
        del done[: len(done) - MAX_DONE_COMMANDS]
    return True


def is_blocked(state, local_block_file_exists=False, central_blocked=False):
    """Blocage général effectif : local (fichier), état persistant
    (commande) ou configuration du central -- le plus restrictif gagne."""
    return bool(local_block_file_exists or (state or {}).get("blocked") or central_blocked)


def plugin_blocked(state, manifest):
    pid = (manifest or {}).get("id")
    if pid in ((state or {}).get("blocked_plugins") or {}):
        return True
    return bool((manifest or {}).get("blocked"))


def block_reason(state, local_block_file_exists=False, central_reason=None):
    if local_block_file_exists:
        return "fichier BLOCKED local"
    if (state or {}).get("blocked"):
        return (state or {}).get("blocked_reason") or "commande de blocage"
    return central_reason or "configuration du central"


# -- événements ---------------------------------------------------------------

_last_event_at = [None, 0]


def make_event(agent_id, kind, severity, message, details=None, now=None):
    """Mesure `event` : un fait de sécurité / d'exploitation horodaté,
    remonté comme n'importe quelle mesure (file locale, envoi signé).
    Plusieurs événements peuvent naître dans la même seconde : `at` porte
    les millisecondes et un même instant est incrémenté, pour que la
    déduplication (agent, tâche, instant) de la file et du central ne
    confonde jamais deux événements distincts."""
    if severity not in EVENT_SEVERITIES:
        severity = "info"
    ts = now if now is not None else time.time()
    base = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts))
    ms = int((ts * 1000) % 1000)
    if _last_event_at[0] == base and ms <= _last_event_at[1]:
        ms = _last_event_at[1] + 1
    _last_event_at[0], _last_event_at[1] = base, ms
    at = "%s.%03dZ" % (base, ms % 1000)
    return {"agent_id": agent_id, "task": "event", "at": at, "ok": severity != "critical", "error": None,
            "data": {"kind": kind, "severity": severity, "message": message, "details": details or {}}}


# -- confinement de l'exécution ----------------------------------------------

_WINDOWS_ENV_KEEP = ("SystemRoot", "windir", "SystemDrive", "ProgramData", "ProgramFiles", "PATH", "Path", "PATHEXT", "COMSPEC", "ComSpec",
                     "TEMP", "TMP", "PSModulePath", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "COMPUTERNAME", "USERPROFILE")


def plugin_env(agent_id, site, plugin_id, extra=None, base_env=None):
    """Environnement MINIMAL : jamais l'environnement du service (qui peut
    porter des chemins ou variables sensibles). `base_env` (#440,
    Windows) : environnement dont seules les variables système
    indispensables (SystemRoot, PATH, TEMP…) sont reprises."""
    if base_env is not None:
        env = {k: str(v) for k, v in base_env.items() if k in _WINDOWS_ENV_KEEP}
        env.update({"SI_AGENT_ID": str(agent_id), "SI_AGENT_SITE": str(site or ""), "SI_PLUGIN_ID": str(plugin_id)})
    else:
        env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8",
               "HOME": "/tmp", "SI_AGENT_ID": str(agent_id), "SI_AGENT_SITE": str(site or ""), "SI_PLUGIN_ID": str(plugin_id)}
    for k, v in (extra or {}).items():
        if isinstance(k, str) and k.startswith("SI_") and isinstance(v, str):
            env[k] = v
    return env


def resolve_run_user(manifest, plugins_user, current_uid, lookup):
    """(uid, gid) à adopter, ou None pour rester tel quel. `lookup(name)`
    renvoie (uid, gid) ou None. Seul root peut changer d'utilisateur ; un
    plugin `privileged` reste root."""
    if current_uid != 0 or not plugins_user or (manifest or {}).get("privileged"):
        return None
    ids = lookup(plugins_user)
    if not ids:
        return None
    return ids


def make_preexec(timeout_seconds, max_memory_mb=512, run_as=None, nice=10):
    """Fonction exécutée dans l'enfant AVANT exec : session propre,
    priorité, limites, umask, abandon de privilèges. Toute erreur ici fait
    échouer le lancement (jamais un plugin lancé « à moitié confiné »)."""
    def _preexec():
        import resource  # noqa: PLC0415 -- Linux seulement
        os.setsid()
        try:
            os.nice(nice)
        except OSError:
            pass
        cpu = int(timeout_seconds) + 5
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 5))
        if max_memory_mb:
            lim = int(max_memory_mb) * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (lim, lim))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except (ValueError, OSError):
            pass
        os.umask(0o077)
        if run_as:
            uid, gid = run_as
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
    return _preexec
