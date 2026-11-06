# -*- coding: utf-8 -*-
"""#996 : nœud IA -- Hermes, atelier de codage et apprentissage (hermes-web) installés et mis à jour DEPUIS LE HUB.

Commande `noeud_ia` (Linux), actions :
  etat      -- état du dernier déploiement et santé de hermes-web (lecture) ;
  deployer  -- INTERVENTION : télécharge l'archive déposée dans le hub (requête signée), vérifie son empreinte, reçoit
               le jeton du nœud (requête signée, jamais dans les paramètres ni les traces), installe sous /opt/hermes-ia
               (ancienne version gardée en hermes-web.old) et lance hermes-web/deploy/noeud/compose.yml.
Le déploiement dure (construction de l'image Hermes) : fil détaché, étapes relevées, événement à la fin.
Logique testable ici (fonctions pures + Deploiement aux dépendances injectées)."""
import hashlib
import json
import os
import re
import shutil
import tarfile
import time

RACINE = "/opt/hermes-ia"
UID_HERMES = 10000                 # utilisateur de l'image Hermes (exige /opt/data à lui)
NOM_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
MODELE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,80}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ETAPES = ("téléchargement", "vérification", "jeton", "extraction", "dossiers", "construction et démarrage", "santé")


def valider(params):
    """-> message d'erreur ou None."""
    p = params or {}
    if p.get("action", "etat") not in ("etat", "deployer"):
        return "action : etat ou deployer"
    if p.get("action") == "deployer":
        if not NOM_RE.match(str(p.get("nom") or "")):
            return "nom du nœud : minuscules, chiffres, tirets"
        if not SHA_RE.match(str(p.get("sha256") or "")):
            return "empreinte sha256 de l'archive requise"
        try:
            port = int(p.get("port") or 8092)
        except (TypeError, ValueError):
            return "port numérique"
        if not 1024 <= port <= 65535:
            return "port entre 1024 et 65535"
        if p.get("modele") and not MODELE_RE.match(str(p["modele"])):
            return "modèle invalide"
    return None


def contenu_env(jeton, port=8092, modele="qwen3:4b", racine=RACINE):
    if not re.match(r"^[A-Za-z0-9_-]{16,128}$", str(jeton or "")):
        raise ValueError("jeton reçu invalide")
    return "HERMES_WEB_JETON=%s\nHERMES_WEB_PORT=%d\nHERMES_MODELE=%s\nDONNEES=%s\n" % (jeton, int(port), modele or "qwen3:4b", racine)


def argv_compose(racine=RACINE, docker_compose_v2=True):
    base = ["docker", "compose"] if docker_compose_v2 else ["docker-compose"]
    return base + ["-p", "hermes-ia", "--env-file", os.path.join(racine, "env"),
                   "-f", os.path.join(racine, "hermes-web", "deploy", "noeud", "compose.yml"), "up", "-d", "--build"]


def membres_surs(tar, dest):
    """Membres de l'archive à extraire, premier dossier retiré (git archive --prefix=hermes-web/) ; refuse chemins absolus,
    remontées et liens sortant de la destination."""
    out = []
    dest = os.path.realpath(dest)
    for m in tar.getmembers():
        parts = m.name.split("/", 1)
        if len(parts) < 2 or not parts[1]:
            continue
        rel = parts[1]
        if rel.startswith("/") or ".." in rel.split("/"):
            raise ValueError("archive refusée : chemin %s" % m.name)
        if m.issym() or m.islnk():
            cible = os.path.realpath(os.path.join(dest, os.path.dirname(rel), m.linkname))
            if not (cible == dest or cible.startswith(dest + os.sep)):
                raise ValueError("archive refusée : lien %s" % m.name)
        if not (m.isfile() or m.isdir() or m.issym() or m.islnk()):
            continue
        m.name = rel
        out.append(m)
    return out


def version_kit(dossier):
    try:
        with open(os.path.join(dossier, "hermes_web", "__init__.py"), encoding="utf-8") as fh:
            m = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read())
            return m.group(1) if m else None
    except OSError:
        return None


def sha256_fichier(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as fh:
        for bloc in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


class Deploiement(object):
    """Un déploiement. Dépendances injectées : telecharger(dest), jeton() -> str, commande(argv, timeout) -> (rc, sortie),
    sante(port, jeton) -> (ok, texte), chown(chemin, uid)."""

    def __init__(self, params, telecharger, jeton, commande, sante, chown=None, racine=RACINE, horloge=time.time):
        self.p, self.racine, self.horloge = params, racine, horloge
        self.telecharger, self.jeton, self.commande, self.sante = telecharger, jeton, commande, sante
        self.chown = chown or (lambda chemin, uid: os.chown(chemin, uid, uid))
        self.etat = {"nom": params.get("nom"), "en_cours": True, "debut": horloge(), "etape": None, "etapes": [], "ok": None}

    def _etape(self, nom):
        self.etat["etape"] = nom
        self.etat["etapes"].append({"etape": nom, "debut": self.horloge()})

    def executer(self):
        r = self.racine
        try:
            os.makedirs(r, exist_ok=True)
            os.chmod(r, 0o755)
            kit = os.path.join(r, "kit.tar.gz")
            self._etape("téléchargement")
            self.telecharger(kit)
            self._etape("vérification")
            if sha256_fichier(kit) != self.p["sha256"]:
                raise ValueError("empreinte de l'archive différente de celle annoncée par le hub")
            self._etape("jeton")
            env = contenu_env(self.jeton(), self.p.get("port") or 8092, self.p.get("modele") or "qwen3:4b", r)
            fd = os.open(os.path.join(r, "env"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(env)
            self._etape("extraction")
            neuf, actuel, ancien = (os.path.join(r, x) for x in ("hermes-web.new", "hermes-web", "hermes-web.old"))
            shutil.rmtree(neuf, ignore_errors=True)
            os.makedirs(neuf)
            with tarfile.open(kit, "r:gz") as tar:
                tar.extractall(neuf, members=membres_surs(tar, neuf))
            self.etat["version"] = version_kit(neuf)
            if not os.path.isfile(os.path.join(neuf, "deploy", "noeud", "compose.yml")):
                raise ValueError("archive sans deploy/noeud/compose.yml (hermes-web 0.29 ou plus récent requis)")
            shutil.rmtree(ancien, ignore_errors=True)
            if os.path.isdir(actuel):
                os.rename(actuel, ancien)
            os.rename(neuf, actuel)
            self._etape("dossiers")
            for d in ("data", "opt-data", "ateliers"):
                os.makedirs(os.path.join(r, d), exist_ok=True)
            conf = os.path.join(r, "opt-data", "config.yaml")
            if not os.path.exists(conf):
                shutil.copyfile(os.path.join(actuel, "deploy", "noeud", "hermes-config.yaml"), conf)
            for d in ("data", "opt-data", "ateliers"):
                for base, dirs, fichiers in os.walk(os.path.join(r, d)):
                    for x in [base] + [os.path.join(base, f) for f in dirs + fichiers]:
                        self.chown(x, UID_HERMES)
                        try:
                            os.chmod(x, os.stat(x).st_mode & ~0o022)
                        except OSError:
                            pass
            self._etape("construction et démarrage")
            rc, sortie = self.commande(argv_compose(r), 3600)
            self.etat["sortie"] = (sortie or "")[-4000:]
            if rc != 0:
                raise RuntimeError("docker compose : code %s" % rc)
            self._etape("santé")
            ok, txt = False, ""
            for _ in range(30):
                ok, txt = self.sante(int(self.p.get("port") or 8092))
                if ok:
                    break
                time.sleep(2)
            if not ok:
                raise RuntimeError("hermes-web ne répond pas : %s" % txt)
            self.etat.update({"ok": True, "sante": txt})
        except Exception as exc:  # noqa: BLE001
            self.etat.update({"ok": False, "erreur": str(exc)[:500]})
        finally:
            self.etat.update({"en_cours": False, "fin": self.horloge()})
            try:
                os.remove(os.path.join(r, "kit.tar.gz"))
            except OSError:
                pass
            try:
                with open(os.path.join(r, "etat.json"), "w", encoding="utf-8") as fh:
                    json.dump({k: v for k, v in self.etat.items() if k != "sortie"}, fh, ensure_ascii=False)
            except OSError:
                pass
        return self.etat


def etat_disque(racine=RACINE):
    try:
        with open(os.path.join(racine, "etat.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def lire_jeton(racine=RACINE):
    try:
        with open(os.path.join(racine, "env"), encoding="utf-8") as fh:
            for l in fh:
                if l.startswith("HERMES_WEB_JETON="):
                    return l.strip().split("=", 1)[1]
    except OSError:
        pass
    return None
