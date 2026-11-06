# -*- coding: utf-8 -*-
"""#996 : nœuds IA déployés depuis le hub -- archive de hermes-web déposée (kit), jeton de chaque nœud, suivi.

Jeton d'un nœud = HMAC-SHA256(IA_NOEUDS_SECRET, « hermes-web:<nom> ») tronqué : recalculé à la demande par si-agent-api
(remis à l'agent du nœud par requête signée) et par la passerelle (rendu nginx) -- jamais stocké, jamais dans une
commande, un résultat ou une trace. Logique pure, testée dans test_noeudia.py."""
import hashlib
import hmac
import io
import re
import tarfile

NOM_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
TAILLE_MAX = 200 * 1024 * 1024
VERSION_MIN = (0, 29)


def jeton(secret, nom):
    if not secret or not NOM_RE.match(str(nom or "")):
        return None
    return hmac.new(str(secret).encode("utf-8"), ("hermes-web:%s" % nom).encode("utf-8"), hashlib.sha256).hexdigest()[:48]


def _version(txt):
    m = re.search(r'__version__\s*=\s*"([^"]+)"', txt or "")
    return m.group(1) if m else None


def _tuple(v):
    try:
        return tuple(int(x) for x in str(v).split(".")[:2])
    except ValueError:
        return (0, 0)


def analyser_kit(data):
    """Octets d'une archive .tar.gz de hermes-web (git archive --prefix=hermes-web/) -> (meta, erreur).
    meta = {version, sha256, taille, fichiers}."""
    if not data:
        return None, "archive vide"
    if len(data) > TAILLE_MAX:
        return None, "archive trop grosse (%d Mo au plus)" % (TAILLE_MAX // 2**20)
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
            noms = t.getnames()
            init = next((n for n in noms if re.match(r"^[^/]+/hermes_web/__init__\.py$", n)), None)
            compose = any(re.match(r"^[^/]+/deploy/noeud/compose\.yml$", n) for n in noms)
            if not init:
                return None, "ce n'est pas une archive de hermes-web (hermes_web/__init__.py absent sous un dossier racine)"
            version = _version(t.extractfile(init).read(4096).decode("utf-8", "replace"))
    except (tarfile.TarError, OSError, EOFError) as exc:
        return None, "archive illisible (.tar.gz attendu) : %s" % exc
    if not compose or _tuple(version) < VERSION_MIN:
        return None, "hermes-web %s trop ancien : 0.29 ou plus récent requis (deploy/noeud/compose.yml)" % (version or "?")
    return {"version": version, "sha256": hashlib.sha256(data).hexdigest(), "taille": len(data), "fichiers": len(noms)}, None


def valider_demande(b):
    """Corps de POST /agents/<id>/noeud-ia -> (params de commande, erreur)."""
    b = b or {}
    action = str(b.get("action") or "etat")
    if action not in ("etat", "deployer"):
        return None, "action : etat ou deployer"
    p = {"action": action}
    try:
        p["port"] = int(b.get("port") or 8092)
    except (TypeError, ValueError):
        return None, "port numérique"
    if not 1024 <= p["port"] <= 65535:
        return None, "port entre 1024 et 65535"
    if action == "deployer":
        nom = str(b.get("nom") or "").strip()
        if not NOM_RE.match(nom):
            return None, "nom du nœud : minuscules, chiffres, tirets (ex. prodia)"
        p["nom"] = nom
        modele = str(b.get("modele") or "qwen3:4b").strip()
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,80}$", modele):
            return None, "modèle invalide"
        p["modele"] = modele
    return p, None
