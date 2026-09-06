"""
Gestion des PROCESSUS `ssh -L` (tunnels de redirection de port,
livraison #159) -- lance/arrête/vérifie de VRAIS processus `ssh` en
sous-processus. Le PID est stocké en BASE par l'appelant HTTP (voir
tunnels_store.py), jamais seulement en mémoire de CE module -- 2
workers Gunicorn ne partagent pas leur mémoire, un PID connu d'un
seul worker serait invisible à l'autre (même problème que les logs
avant #145, pas résoluble de la même façon pour un VRAI processus OS
-- voir ssh-tunnels/README.md pour le choix assumé : un seul worker
pour ce service précis, la base SQLite reste la source de vérité du
PID quel que soit le worker qui répond à une requête donnée).

Construction de la commande TOUJOURS par LISTE d'arguments (jamais
`shell=True`, jamais de concaténation de chaîne) -- élimine toute
injection shell par construction, quelle que soit la provenance des
valeurs (host/user/ports viennent de la base après validation à la
création, jamais directement d'une entrée libre au moment de
l'exécution).
"""
import logging
import os
import signal
import subprocess
import time

# Traces DEBUG à chaque étape sensible (livraison #215, demandé
# explicitement -- "rien ne doit être silencieux... identifier vite
# les points de blocage"). Lancement/arrêt de VRAIS processus OS
# externes -- exactement le genre d'étape qui peut échouer
# silencieusement sans ces traces (processus qui ne démarre jamais,
# qui meurt immédiatement sans message clair, qui refuse de
# s'arrêter). RÈGLE ABSOLUE : le mot de passe (mode `auth_method=
# "password"`, #210) n'apparaît JAMAIS dans un message de log, à
# aucun niveau -- seule sa PRÉSENCE (booléen) est tracée, jamais sa
# valeur.
_log = logging.getLogger("tunnel_process")


def install_reaper():
    """Installe un gestionnaire SIGCHLD qui "récolte" (waitpid) tout
    enfant terminé -- SANS ÇA, un enfant ssh arrêté (SIGTERM envoyé
    par stop_tunnel_process, ou mort de lui-même -- réseau coupé,
    hôte distant redémarré...) reste un PROCESSUS ZOMBIE tant que ce
    processus Python ne l'a jamais "récolté" via waitpid -- un
    zombie répond TOUJOURS `os.kill(pid, 0)` avec succès (le PID
    existe encore dans la table des processus), is_process_alive le
    verrait donc à tort comme "vivant" indéfiniment. Bug RÉEL trouvé
    en testant (processus affiché `[bash] <defunct>` après un arrêt
    pourtant correctement envoyé).

    À appeler UNE SEULE FOIS au démarrage de l'application (voir
    app.py) -- ce module tourne avec un SEUL worker Gunicorn
    (décision assumée, voir ssh-tunnels/README.md), donc un seul
    appel suffit pour tout le processus."""
    def _reap(signum, frame):
        while True:
            try:
                pid, _status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break
    signal.signal(signal.SIGCHLD, _reap)


def build_ssh_command(ssh_host, ssh_port, ssh_user, key_path, local_port, remote_host, remote_port,
                       strict_host_key_checking="accept-new", auth_method="key"):
    """`-N` : pas de shell distant, uniquement la redirection.
    `BatchMode=yes` : jamais un prompt interactif (mot de passe,
    confirmation) qui bloquerait le processus indéfiniment --
    échoue proprement à la place si une interaction serait
    nécessaire. `StrictHostKeyChecking=accept-new` (repli, PAS "no")
    : accepte une clé d'hôte JAMAIS VUE, mais échoue si une clé
    CONNUE a changé -- protection MITM conservée sur les connexions
    suivantes, tout en restant utilisable sans pré-remplir
    manuellement un known_hosts avant le premier usage.

    **Correctif #184 -- BUG RÉEL rencontré par la personne**
    (connexion refusée depuis dba-api à travers un tunnel) :
    `-L {local_port}:...` SANS adresse de liaison explicite lie le
    port par défaut à `127.0.0.1` -- LOOPBACK DU CONTENEUR
    `ssh-tunnels-api` LUI-MÊME, invisible depuis n'importe quel autre
    conteneur (dba-api compris), MÊME sur le réseau Docker partagé.
    Casse directement le "mode proxy" promis en #159 ("le tunnel
    ouvre son port local sur le conteneur, les autres API s'y
    connectent directement par son nom Docker") -- jamais vérifié
    contre un vrai second conteneur consommateur avant ce rapport
    réel. Corrigé : liaison EXPLICITE `0.0.0.0:` -- toutes les
    interfaces du conteneur, donc atteignable via le réseau Docker
    interne par son nom de service. Le conteneur n'exposant AUCUN
    port vers l'hôte (voir docker-compose.yml, pas de `ports:` sur
    ce service), ce changement n'élargit PAS l'exposition au-delà du
    réseau Docker déjà partagé entre tous les conteneurs du projet --
    seule la portée VOULUE depuis #159 devient enfin RÉELLEMENT
    atteignable.

    **`auth_method="password"` (livraison #210, backlog item 12)** --
    contexte donné par la personne : certains vieux systèmes refusent
    la connexion par clé. `BatchMode=yes` et `-i {key_path}` sont
    alors OMIS (une interaction serait nécessaire pour le mot de
    passe) -- la commande est enveloppée dans `sshpass -e ssh ...`,
    qui répond au prompt de mot de passe de façon non interactive en
    lisant la variable d'environnement `SSHPASS` -- JAMAIS le mot de
    passe en argument de ligne de commande (visible dans `ps`/les
    journaux système) -- voir start_tunnel_process, qui positionne
    cette variable UNIQUEMENT dans l'environnement du sous-processus,
    jamais dans la commande elle-même. Comportement en mode "key"
    (par défaut) rigoureusement INCHANGÉ -- aucune régression sur les
    tunnels existants."""
    base_options = [
        "-N",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", f"StrictHostKeyChecking={strict_host_key_checking}",
    ]
    if auth_method == "password":
        auth_options = ["-o", "PubkeyAuthentication=no", "-o", "PreferredAuthentications=password"]
        prefix = ["sshpass", "-e"]
    else:
        auth_options = ["-o", "BatchMode=yes", "-i", key_path]
        prefix = []
    return prefix + [
        "ssh",
        *base_options,
        *auth_options,
        "-p", str(ssh_port),
        "-L", f"0.0.0.0:{local_port}:{remote_host}:{remote_port}",
        f"{ssh_user}@{ssh_host}",
    ]


def is_process_alive(pid):
    """`os.kill(pid, 0)` n'envoie AUCUN signal réel -- teste juste
    l'existence/l'autorisation. `PermissionError` compte comme VIVANT
    (le processus existe, juste possédé par un autre utilisateur --
    ne devrait normalement pas arriver ici, ce module tourne dans un
    conteneur dédié, mais ne JAMAIS le confondre avec "processus
    mort")."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def start_tunnel_process(ssh_host, ssh_port, ssh_user, key_path, local_port, remote_host, remote_port,
                          auth_method="key", password=None):
    """Lance le sous-processus `ssh -L` en arrière-plan
    (`start_new_session=True` -- survit indépendamment du processus
    Python appelant, jamais tué par accident si CE worker Gunicorn
    redémarre). Renvoie (pid, error) -- error non-None si le
    lancement échoue immédiatement (ex. clé introuvable) OU si le
    processus meurt dans la courte fenêtre qui suit (échec RAPIDE de
    connexion -- mauvais hôte/port/clé refusée), stderr capturé pour
    un message utile, jamais juste "a échoué".

    `auth_method="password"` (livraison #210) : `password` est
    positionné dans l'environnement du SOUS-PROCESSUS UNIQUEMENT
    (variable `SSHPASS`, lue par `sshpass -e`, voir
    build_ssh_command) -- jamais dans la commande elle-même (qui
    resterait visible via `ps`/les journaux). L'environnement du
    sous-processus part d'une COPIE de celui du processus appelant
    (`os.environ.copy()`) -- jamais un environnement vide qui
    romprait `ssh`/`sshpass` (résolution de `PATH`, `HOME` pour
    `known_hosts`, etc.)."""
    if auth_method == "password":
        if not password:
            _log.debug("start_tunnel_process : refusé -- auth_method=password mais aucun mot de passe fourni")
            return None, "mot de passe requis pour l'authentification par mot de passe"
    elif not os.path.isfile(key_path):
        _log.debug("start_tunnel_process : refusé -- fichier de clé introuvable (%s)", key_path)
        return None, f"fichier de clé introuvable : {key_path}"

    _log.debug("start_tunnel_process : préparation -- hôte=%s port=%s user=%s auth_method=%s local_port=%s remote=%s:%s",
               ssh_host, ssh_port, ssh_user, auth_method, local_port, remote_host, remote_port)
    cmd = build_ssh_command(ssh_host, ssh_port, ssh_user, key_path, local_port, remote_host, remote_port,
                             auth_method=auth_method)
    subprocess_env = None
    if auth_method == "password":
        subprocess_env = os.environ.copy()
        subprocess_env["SSHPASS"] = password
        _log.debug("start_tunnel_process : SSHPASS positionné dans l'environnement du sous-processus (jamais loggé lui-même)")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, env=subprocess_env,
        )
    except OSError as exc:
        _log.debug("start_tunnel_process : ÉCHEC du lancement du sous-processus -- %s", exc)
        return None, f"lancement du processus ssh échoué : {exc}"
    _log.debug("start_tunnel_process : sous-processus lancé (pid=%s), fenêtre d'observation de 0.5s démarrée", proc.pid)

    # Courte fenêtre pour détecter un échec RAPIDE (ssh échoue
    # généralement en moins d'une seconde sur un hôte/clé/port
    # refusé) -- un tunnel qui échoue PLUS TARD (timeout réseau) sera
    # détecté via check_tunnel_process, jamais bloqué ici.
    time.sleep(0.5)
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode("utf-8", errors="replace").strip()
        _log.debug("start_tunnel_process : le processus (pid=%s) s'est arrêté pendant la fenêtre d'observation (code=%s)",
                   proc.pid, proc.returncode)
        return None, stderr or f"le processus ssh s'est arrêté immédiatement (code {proc.returncode})"
    _log.debug("start_tunnel_process : succès -- processus toujours vivant après la fenêtre d'observation (pid=%s)", proc.pid)
    return proc.pid, None


def stop_tunnel_process(pid, timeout=5):
    """Arrêt PROPRE (`SIGTERM`, puis `SIGKILL` après `timeout`s si
    toujours vivant) -- jamais un `SIGKILL` direct, laisse à `ssh`
    une chance de fermer la connexion proprement d'abord. `True` si
    le processus est bien arrêté à la fin (ou n'existait déjà plus)."""
    _log.debug("stop_tunnel_process : démarré (pid=%s, timeout=%ss)", pid, timeout)
    if not is_process_alive(pid):
        _log.debug("stop_tunnel_process : pid=%s déjà arrêté (rien à faire)", pid)
        return True
    try:
        os.kill(pid, signal.SIGTERM)
        _log.debug("stop_tunnel_process : SIGTERM envoyé (pid=%s)", pid)
    except OSError as exc:
        _log.debug("stop_tunnel_process : SIGTERM a échoué, processus probablement déjà mort (pid=%s) -- %s", pid, exc)
        return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_process_alive(pid):
            _log.debug("stop_tunnel_process : pid=%s arrêté proprement après SIGTERM", pid)
            return True
        time.sleep(0.2)
    _log.debug("stop_tunnel_process : pid=%s toujours vivant après %ss -- passage en SIGKILL", pid, timeout)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    time.sleep(0.2)
    still_alive = is_process_alive(pid)
    _log.debug("stop_tunnel_process : issue finale pour pid=%s -- %s", pid, "toujours vivant (ANORMAL)" if still_alive else "arrêté")
    return not still_alive
