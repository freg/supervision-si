"""Protocole sonde <-> collecteur <-> central : authentification et
forme des messages. Logique PURE (aucun réseau ici), partagée par les
trois côtés -- `netprobe-api` central en reçoit une COPIE au build
(voir netprobe/api/Dockerfile), jamais une réimplémentation.

Authentification -- réponse à la question laissée ouverte dans le backlog
(item 45 : "jamais un agent anonyme pouvant écrire n'importe quoi dans la
base commune") :

- Chaque appareil (sonde OU collecteur) possède un identifiant et un
  secret, provisionnés à la construction de son image (voir image/).
- Chaque requête porte trois en-têtes : `X-Netprobe-Id`,
  `X-Netprobe-Timestamp` (epoch entier, informatif) et
  `X-Netprobe-Signature` = HMAC-SHA256(secret, méthode + "\\n" + chemin +
  "\\n" + timestamp + "\\n" + SHA256(corps)).
- Le destinataire recalcule la signature avec le secret qu'il connaît
  pour cet identifiant, et compare en temps constant.

Pas de fenêtre temporelle stricte : un Pi Zero W n'a PAS d'horloge
temps réel -- au démarrage, tant que NTP n'a pas répondu, son heure est
fausse de plusieurs années. Refuser ses messages à ce moment-là
reviendrait à perdre précisément les premières mesures après une
coupure (ce que l'on veut observer). Le rejeu est neutralisé autrement :
chaque mesure est dédupliquée à l'insertion sur (agent, tâche, instant),
voir `measurement_key`.
"""
import hashlib
import hmac
import json
import time

HEADER_ID = "X-Netprobe-Id"
HEADER_TS = "X-Netprobe-Timestamp"
HEADER_SIG = "X-Netprobe-Signature"

API_PREFIX = "/api/v1"


def canonical_json(obj):
    """Sérialisation DÉTERMINISTE (clés triées, sans espaces) -- le corps
    signé doit être exactement celui transmis, octet pour octet."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def body_digest(body_bytes):
    return hashlib.sha256(body_bytes or b"").hexdigest()


def string_to_sign(method, path, timestamp, body_bytes):
    return "\n".join([method.upper(), path, str(int(timestamp)), body_digest(body_bytes)]).encode("utf-8")


def sign(secret, method, path, timestamp, body_bytes):
    if not secret:
        raise ValueError("secret vide -- signature impossible")
    return hmac.new(secret.encode("utf-8"), string_to_sign(method, path, timestamp, body_bytes), hashlib.sha256).hexdigest()


def auth_headers(device_id, secret, method, path, body_bytes, timestamp=None):
    ts = int(timestamp if timestamp is not None else time.time())
    return {
        HEADER_ID: device_id,
        HEADER_TS: str(ts),
        HEADER_SIG: sign(secret, method, path, ts, body_bytes),
        "Content-Type": "application/json; charset=utf-8",
    }


def verify(secret, method, path, headers, body_bytes):
    """Renvoie (ok, raison). `headers` : dict insensible à la casse OU
    objet avec .get() (Flask / http.server les fournissent tous deux)."""
    def get(name):
        v = headers.get(name)
        if v is None:
            v = headers.get(name.lower())
        return v

    ts = get(HEADER_TS)
    sig = get(HEADER_SIG)
    if not ts or not sig:
        return False, "en-têtes de signature absents"
    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        return False, "timestamp invalide"
    if not secret:
        return False, "appareil inconnu"
    expected = sign(secret, method, path, ts_int, body_bytes)
    if not hmac.compare_digest(expected, str(sig)):
        return False, "signature invalide"
    return True, "ok"


def measurement_key(agent_id, task, at):
    """Clé de déduplication d'une mesure -- une sonde qui renvoie deux
    fois le même lot (coupure entre l'envoi et l'accusé) ne crée jamais
    de doublon, et un rejeu malveillant n'écrit rien de nouveau."""
    return "%s|%s|%s" % (agent_id, task, at)


def validate_measurement(m):
    """Forme minimale d'une mesure ; renvoie (ok, raison). Les données
    utiles (`data`) restent libres : chaque type de tâche a les siennes
    (voir tasks.py), le central les stocke en JSON tel quel."""
    if not isinstance(m, dict):
        return False, "mesure non-objet"
    for k in ("task", "at"):
        if not isinstance(m.get(k), str) or not m[k]:
            return False, "champ '%s' manquant" % k
    if "ok" in m and not isinstance(m["ok"], bool):
        return False, "champ 'ok' non booléen"
    if "data" in m and m["data"] is not None and not isinstance(m["data"], dict):
        return False, "champ 'data' non-objet"
    return True, "ok"
