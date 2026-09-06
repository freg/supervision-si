"""
Gestion des PROCESSUS `sshfs` (montage SSHFS réel, livraison #180 --
volet "montage/démontage SSHFS réel", explicitement reporté en #159,
demandé maintenant explicitement par la personne : "j'en ai besoin
pour concevoir la suite"). MÊME motif que tunnel_process.py (#159) :
lance/arrête un vrai sous-processus, PID stocké en BASE (jamais
seulement en mémoire -- même raisonnement multi-worker que les
tunnels), commande TOUJOURS par LISTE d'arguments (jamais
`shell=True`).

**Différence structurelle avec un tunnel `ssh -L`** : `sshfs` SE
DÉTACHE en arrière-plan par défaut une fois le montage FUSE établi
(il devient un DÉMON), contrairement à `ssh -N -L` qui reste au
premier plan tant qu'il tourne. Lancé ici avec `-f` (foreground) --
comme pour les tunnels, le sous-processus Python lui-même reste le
processus qui tourne tant que le montage est actif, un `is_process_alive`
partagé avec tunnel_process.py suffit alors à vérifier l'état, SANS
dupliquer cette logique.

**Démontage** : `fusermount -u <point_de_montage>` (paquet
`fuse3`/`libfuse3`, présent par défaut sur la plupart des
distributions Linux modernes, contrairement à `umount` qui demande
souvent des privilèges root supplémentaires pour un montage FUSE
utilisateur) -- ferme proprement le montage, ce qui fait
NATURELLEMENT sortir le processus `sshfs -f` en foreground (plus
besoin de lui envoyer SIGTERM en temps normal, mais un filet de
sécurité `stop_mount_process` l'envoie quand même si le processus
n'a pas terminé après le démontage, ex. démontage FUSE qui échoue
silencieusement).

**⚠️ Non vérifié dans cet environnement contre un VRAI `sshfs`** :
réseau restreint ici, le paquet n'est pas installable (même
limitation déjà documentée pour `ssh`/`ssh-keygen`, voir
ssh-tunnels/README.md) -- `fusermount`/`/dev/fuse` sont en revanche
bien présents, la commande de démontage EST DIRECTEMENT testable
(voir tests), seul le montage lui-même (nécessite le binaire
`sshfs`) ne l'est pas.

**Supervision (livraison #182)** : `get_disk_inode_stats` (espace +
inodes, via `os.statvfs` -- fonctionne À TRAVERS un montage SSHFS
sans coût réseau supplémentaire, SSHFS relaie l'appel au serveur
distant via SFTP), `is_mount_point` (confirmation qu'un chemin EST
réellement un point de montage actif, `os.path.ismount()` -- testé
contre un VRAI montage `tmpfs` ici, `mount --bind` NE convient PAS
pour ce test : un bind mount ne change jamais `st_dev`, contrairement
à un montage FUSE qui EST un système de fichiers séparé, exactement
comme `tmpfs`), `measure_latency` (temps d'un `os.stat()` sur la
racine du montage, borné par un timeout via thread séparé -- Python
n'offre aucun timeout natif sur un appel système bloquant).
"""
import concurrent.futures
import logging
import os
import signal
import subprocess
import time

# Traces DEBUG à chaque étape sensible (livraison #215). Même
# raisonnement et même RÈGLE ABSOLUE que tunnel_process.py : le mot
# de passe (mode `auth_method="password"`, #210) n'apparaît JAMAIS
# dans un message de log.
_log = logging.getLogger("mount_process")

from tunnel_process import is_process_alive  # réutilisé tel quel, jamais dupliqué


def build_sshfs_command(ssh_host, ssh_port, ssh_user, key_path, remote_path, local_mount_path,
                         strict_host_key_checking="accept-new", auth_method="key"):
    """`-f` : premier plan -- voir docstring du module, condition pour
    que le PID du sous-processus Python SOIT le montage lui-même.
    `reconnect` : reconnexion automatique sur coupure réseau
    passagère, plutôt qu'un montage mort au moindre accroc -- cohérent
    avec `ServerAliveInterval`/`ServerAliveCountMax` déjà en place
    pour les tunnels (tunnel_process.build_ssh_command). `allow_other`
    volontairement PAS ajouté -- seul l'utilisateur du conteneur a
    besoin d'y accéder, jamais présumé plus large sans demande
    explicite (option qui, de plus, exige `user_allow_other` dans
    `/etc/fuse.conf`, une configuration côté image à part entière).

    `auth_method="password"` (livraison #210, backlog item 12) --
    même motif que tunnel_process.build_ssh_command : `BatchMode=yes`
    et `IdentityFile={key_path}` omis, commande enveloppée dans
    `sshpass -e sshfs ...` -- voir cette fonction pour le
    raisonnement complet (jamais le mot de passe en argument de ligne
    de commande). Comportement en mode "key" (par défaut)
    rigoureusement INCHANGÉ."""
    base_options = [
        "-o", "reconnect",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", f"StrictHostKeyChecking={strict_host_key_checking}",
    ]
    if auth_method == "password":
        auth_options = ["-o", "PubkeyAuthentication=no", "-o", "PreferredAuthentications=password"]
        prefix = ["sshpass", "-e"]
    else:
        auth_options = ["-o", "BatchMode=yes", "-o", f"IdentityFile={key_path}"]
        prefix = []
    return prefix + [
        "sshfs",
        "-f",
        *base_options,
        *auth_options,
        "-p", str(ssh_port),
        f"{ssh_user}@{ssh_host}:{remote_path}",
        local_mount_path,
    ]


def start_mount_process(ssh_host, ssh_port, ssh_user, key_path, remote_path, local_mount_path,
                         auth_method="key", password=None):
    """Même structure que tunnel_process.start_tunnel_process --
    fenêtre courte pour détecter un échec RAPIDE (clé refusée, hôte
    injoignable, chemin distant inexistant -- sshfs échoue
    généralement en moins d'une seconde dans ces cas), stderr capturé
    pour un message utile. Le POINT DE MONTAGE doit déjà EXISTER
    (créé par l'appelant, voir app.py) -- sshfs ne le crée jamais
    lui-même, contrairement à certains outils.

    `auth_method="password"` (livraison #210) : même motif que
    tunnel_process.start_tunnel_process -- `password` transmis
    UNIQUEMENT via l'environnement du sous-processus (`SSHPASS`),
    jamais dans la commande."""
    if auth_method == "password":
        if not password:
            _log.debug("start_mount_process : refusé -- auth_method=password mais aucun mot de passe fourni")
            return None, "mot de passe requis pour l'authentification par mot de passe"
    elif not os.path.isfile(key_path):
        _log.debug("start_mount_process : refusé -- fichier de clé introuvable (%s)", key_path)
        return None, f"fichier de clé introuvable : {key_path}"
    if not os.path.isdir(local_mount_path):
        _log.debug("start_mount_process : refusé -- point de montage introuvable (%s)", local_mount_path)
        return None, f"point de montage introuvable : {local_mount_path}"

    _log.debug("start_mount_process : préparation -- hôte=%s port=%s user=%s auth_method=%s remote_path=%s local_mount_path=%s",
               ssh_host, ssh_port, ssh_user, auth_method, remote_path, local_mount_path)
    cmd = build_sshfs_command(ssh_host, ssh_port, ssh_user, key_path, remote_path, local_mount_path,
                               auth_method=auth_method)
    subprocess_env = None
    if auth_method == "password":
        subprocess_env = os.environ.copy()
        subprocess_env["SSHPASS"] = password
        _log.debug("start_mount_process : SSHPASS positionné dans l'environnement du sous-processus (jamais loggé lui-même)")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, env=subprocess_env,
        )
    except OSError as exc:
        _log.debug("start_mount_process : ÉCHEC du lancement du sous-processus -- %s", exc)
        return None, f"lancement du processus sshfs échoué : {exc}"
    _log.debug("start_mount_process : sous-processus lancé (pid=%s), fenêtre d'observation de 0.5s démarrée", proc.pid)

    time.sleep(0.5)
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode("utf-8", errors="replace").strip()
        _log.debug("start_mount_process : le processus (pid=%s) s'est arrêté pendant la fenêtre d'observation (code=%s)",
                   proc.pid, proc.returncode)
        return None, stderr or f"le processus sshfs s'est arrêté immédiatement (code {proc.returncode})"
    _log.debug("start_mount_process : succès -- processus toujours vivant après la fenêtre d'observation (pid=%s)", proc.pid)
    return proc.pid, None


def unmount_path(local_mount_path, timeout=5):
    """`fusermount -u` -- renvoie (ok, error). Un point NON monté est
    traité comme un SUCCÈS silencieux (idempotent, même raisonnement
    que delete_document sur un 404 dans ged/api/mayan_client.py,
    #163) : démonter un point déjà démonté ne devrait jamais être une
    erreur bloquante côté appelant.

    Vocabulaire RÉEL confirmé contre le VRAI binaire `fusermount`
    (`fuse3` 3.14, présent dans cet environnement -- contrairement à
    `sshfs` lui-même, non installable, réseau restreint) -- PAS
    deviné : "failed to unmount ... Invalid argument" pour un
    répertoire qui existe mais n'est PAS un point de montage FUSE
    actif, "bad mount point ... No such file or directory" pour un
    répertoire absent du disque -- les DEUX traités comme
    "rien à démonter", jamais une erreur."""
    _log.debug("unmount_path : démarré (local_mount_path=%s, timeout=%ss)", local_mount_path, timeout)
    try:
        result = subprocess.run(
            ["fusermount", "-u", local_mount_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _log.debug("unmount_path : ÉCHEC -- délai dépassé (%ss)", timeout)
        return False, f"démontage de '{local_mount_path}' expiré après {timeout}s"
    except OSError as exc:
        _log.debug("unmount_path : ÉCHEC -- lancement de fusermount impossible : %s", exc)
        return False, f"impossible de lancer fusermount : {exc}"
    if result.returncode == 0:
        _log.debug("unmount_path : succès (code retour 0)")
        return True, None
    stderr = result.stderr.decode("utf-8", errors="replace").strip().lower()
    idempotent_markers = ("invalid argument", "no such file or directory", "not mounted", "n'est pas monté")
    if any(marker in stderr for marker in idempotent_markers):
        _log.debug("unmount_path : rien à démonter (idempotent -- code retour %s, marqueur reconnu)", result.returncode)
        return True, None  # idempotent -- voir docstring
    _log.debug("unmount_path : ÉCHEC réel (code retour %s)", result.returncode)
    return False, result.stderr.decode("utf-8", errors="replace").strip() or f"fusermount a échoué (code {result.returncode})"


def stop_mount_process(pid, local_mount_path, timeout=5):
    """Démonte D'ABORD (fait normalement sortir `sshfs -f`
    naturellement), puis filet de sécurité : SIGTERM/SIGKILL sur le
    PID s'il tourne toujours après (démontage FUSE qui aurait échoué
    silencieusement, scénario rare mais jamais un processus orphelin
    laissé derrière). Renvoie (ok, error) -- error non-None seulement
    si NI le démontage NI l'arrêt du processus n'ont abouti."""
    unmounted, unmount_error = unmount_path(local_mount_path, timeout=timeout)

    if is_process_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        deadline = time.time() + timeout
        while time.time() < deadline and is_process_alive(pid):
            time.sleep(0.2)
        if is_process_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            time.sleep(0.2)

    process_gone = not is_process_alive(pid)
    if unmounted or process_gone:
        return True, None
    return False, unmount_error or "démontage et arrêt du processus sshfs tous deux échoués"


# ------------------------------------------------------------------
# Supervision (livraison #182, demandé explicitement -- "transforme
# ça en vraie fonctionnalité de supervision"). Voir docstring du
# module pour le raisonnement complet.
# ------------------------------------------------------------------

def get_disk_inode_stats(path):
    """Renvoie {disk: {total_bytes, free_bytes, available_bytes},
    inodes: {total, free}} -- `os.statvfs` À TRAVERS le montage,
    aucun coût réseau supplémentaire par rapport à ce que SSHFS fait
    déjà en interne (relaie l'appel au SERVEUR DISTANT via SFTP).

    `inodes.total`/`inodes.free` peuvent être 0 ou non significatifs
    -- dépend ENTIÈREMENT du système de fichiers DISTANT (ext2/3/4 a
    un nombre d'inodes fixe et pertinent ; XFS/Btrfs/ZFS répondent
    souvent 0, rien à voir avec SSHFS lui-même) -- jamais une
    garantie universelle, à interpréter en connaissance du serveur
    visé.

    Lève OSError si `path` n'est PAS un point de montage valide
    (chemin inexistant, ou statvfs échoue pour une autre raison) --
    l'appelant DOIT vérifier `is_mount_point` avant, sans quoi ces
    stats seraient celles du système de fichiers PARENT (le
    conteneur lui-même), pas du montage distant -- silencieusement
    trompeur, jamais souhaité ici."""
    st = os.statvfs(path)
    return {
        "disk": {
            "total_bytes": st.f_frsize * st.f_blocks,
            "free_bytes": st.f_frsize * st.f_bfree,
            "available_bytes": st.f_frsize * st.f_bavail,
        },
        "inodes": {
            "total": st.f_files,
            "free": st.f_ffree,
        },
    }


def is_mount_point(path):
    """`os.path.ismount()` -- compare le `st_dev` de `path` à celui
    de son parent, True si différents (un montage FUSE/SSHFS EST un
    système de fichiers séparé, donc un `st_dev` distinct -- vérifié
    ici contre un VRAI montage `tmpfs`, voir tests). Renvoie False
    (jamais une exception) si `path` n'existe même pas -- même
    comportement que la fonction standard sur laquelle elle s'appuie.

    ⚠️ NE PAS confondre avec is_process_alive : un montage peut
    apparaître "démonté" ici (chemin absent, ou démonté de
    l'extérieur) alors que le PROCESSUS sshfs tourne encore un court
    instant -- les deux signaux sont complémentaires, jamais
    substituables l'un à l'autre (voir app.py, qui les combine)."""
    try:
        return os.path.ismount(path)
    except OSError:
        return False


def measure_latency(path, timeout=3):
    """Chronomètre un `os.stat()` sur `path` (millisecondes),
    dans un THREAD SÉPARÉ avec délai d'attente -- Python n'offre
    AUCUN timeout natif sur un appel système bloquant (contrairement
    à `requests`/`socket`), un montage devenu inerte (réseau coupé,
    pas encore détecté par `ServerAliveInterval`) pourrait sinon
    bloquer l'appelant indéfiniment. Renvoie None si le délai est
    dépassé -- le thread sous-jacent reste bloqué en arrière-plan
    (Python ne peut PAS tuer un thread de force), mais l'appelant
    n'attend jamais plus que `timeout`s, ce qui est le seul objectif
    ici : ne jamais faire pendre une requête HTTP de supervision à
    cause d'un montage malade.

    **Piège réel trouvé en testant** : `with ThreadPoolExecutor()`
    appelle `shutdown(wait=True)` à la SORTIE du bloc -- ça bloque
    jusqu'à ce que le thread sous-jacent se termine RÉELLEMENT, même
    après avoir déjà obtenu un timeout sur `future.result()` --
    annule tout l'intérêt du timeout (mesuré : 2s d'attente malgré un
    timeout de 0.3s demandé). Corrigé : `executor` créé et fermé
    EXPLICITEMENT avec `shutdown(wait=False)`, jamais via `with`."""
    def _stat():
        start = time.monotonic()
        os.stat(path)
        return (time.monotonic() - start) * 1000

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_stat)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        return None
    except OSError:
        return None
    finally:
        executor.shutdown(wait=False)
