# -*- coding: utf-8 -*-
"""#931 : poussée d'une archive de sauvegarde de poste vers Proxmox Backup Server (pbs10), exécutée par l'agent DU
serveur PBS (le client proxmox-backup-client y est déjà installé -- cf. sonde `pbs`). L'archive, écrite sur un
partage de pbs10 par la sauvegarde (#930), est poussée dans le datastore en un snapshot « host » par poste, espace
de noms « postes » : confs + AppData + montages regroupés (combinés) et dédupliqués par PBS.

Sécurité : le secret du JETON d'API (PBS_PASSWORD) passe par l'environnement du processus -- jamais en argument de
ligne de commande (visible en `ps`) ni en trace. Le dépôt (`repository`) contient le NOM du jeton, pas son secret.
Module pur/testable : construction des commandes, environnement, interprétation du résultat.
"""
import re

NOM_PXAR = "poste"   # nom de l'archive pxar dans le snapshot (host/<id>/<time> -> poste.pxar)


def argv_preflight(repository, namespace=None):
    """Commande LECTURE SEULE : liste les snapshots du dépôt (vérifie client + authentification + accès au ns)."""
    a = ["proxmox-backup-client", "snapshot", "list", "--repository", repository, "--output-format", "json"]
    if namespace:
        a += ["--ns", namespace]
    return a


def argv_push(dossier, repository, backup_id, namespace=None):
    """Commande d'écriture : sauvegarde `dossier` (contenu extrait de l'archive) en pxar, snapshot host/<backup_id>."""
    if not backup_id or not re.match(r"^[A-Za-z0-9._-]+$", backup_id):
        raise ValueError("backup-id invalide : %r" % backup_id)
    a = ["proxmox-backup-client", "backup", "%s.pxar:%s" % (NOM_PXAR, dossier),
         "--repository", repository, "--backup-type", "host", "--backup-id", backup_id]
    if namespace:
        a += ["--ns", namespace]
    return a


def env_push(token_secret=None, fingerprint=None):
    """Variables d'environnement pour proxmox-backup-client : secret du jeton et empreinte du certificat. Jamais
    d'argument de ligne de commande (le secret n'apparaît ni en `ps` ni en trace)."""
    env = {}
    if token_secret:
        env["PBS_PASSWORD"] = str(token_secret)
    if fingerprint:
        env["PBS_FINGERPRINT"] = str(fingerprint)
    return env


_SNAP = re.compile(r"\b(host/[A-Za-z0-9._-]+/[0-9TZ:\-]+)\b")


def interpreter(returncode, stdout, stderr, action="push"):
    """Résultat d'un appel proxmox-backup-client -> {ok, action, snapshot?, erreur?, resume}. Sans secret."""
    txt = ((stdout or "") + "\n" + (stderr or "")).strip()
    ok = returncode == 0
    r = {"ok": ok, "action": action}
    if action == "preflight":
        r["resume"] = "accès PBS vérifié" if ok else "préflight en échec"
    m = _SNAP.search(txt)
    if m:
        r["snapshot"] = m.group(1)
    if not ok:
        # dernière ligne utile de l'erreur (jamais de secret dans la sortie du client)
        lignes = [l for l in txt.splitlines() if l.strip()]
        r["erreur"] = (lignes[-1] if lignes else "code %s" % returncode)[:300]
    return r
