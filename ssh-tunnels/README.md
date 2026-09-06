# ssh-tunnels — supervision de tunnels SSH et partages SSHFS

Livraison #159, backlog `BACKLOG.md` #2. Demandé explicitement :
superviser les tunnels SSH et partages SSHFS présents, gérer les
clés (activer/désactiver/informer), une interface de montage/
démontage -- objectif : accès à des ressources privées distantes
(service redistribué en mode proxy type rinetd/proxy-delegated, ou
système de fichiers distant).

## Trois points tranchés avec la personne AVANT de coder

- **Clés SSH** : "un chemin protégé paramétré" -- ce module ne
  génère ni ne stocke JAMAIS de clé lui-même. Un simple REGISTRE
  (métadonnées : label, activée/désactivée) par-dessus des fichiers
  déjà présents sur un volume monté en **lecture seule**
  (`SSH_KEYS_DIR`) -- voir `key_scanner.py`.
- **SSHFS** : "on verra plus tard mais c'est bien de préparer
  l'interface" -- table `ssh_mounts` et routes CRUD présentes dans
  cette livraison, mais les actions `mount`/`unmount` renvoient
  explicitement `501 pas encore implémenté`. **Aucun montage FUSE
  réel** -- privilèges élevés requis (`SYS_ADMIN`, `/dev/fuse`),
  décision explicitement reportée.
- **Mode proxy CONFIRMÉ** ("rinetd"/"proxy delegated") : un tunnel
  ouvre son port LOCAL sur CE conteneur (réseau Docker partagé), les
  autres API s'y connectent DIRECTEMENT par le nom du conteneur
  (`ssh-tunnels-api:<local_port>`) -- jamais un relais applicatif à
  construire en plus.

## Architecture

- `tunnels_store.py` -- persistance SQLite (clés, connexions,
  tunnels, montages).
- `key_scanner.py` -- découverte des fichiers dans `SSH_KEYS_DIR`
  (jamais récursif, `.pub`/fichiers cachés exclus) + empreinte via
  `ssh-keygen -lf` en sous-processus -- **jamais le contenu de la
  clé lui-même**.
- `tunnel_process.py` -- lance/arrête de VRAIS processus `ssh -L`
  (`subprocess.Popen`, commande TOUJOURS construite par LISTE
  d'arguments, jamais `shell=True`). `StrictHostKeyChecking=accept-new`
  (repli) -- accepte une clé d'hôte jamais vue, mais échoue si une
  clé CONNUE a changé (protection MITM conservée sans pré-remplir un
  `known_hosts` à la main).

## Un seul worker Gunicorn -- pourquoi

Décision assumée (voir `Dockerfile`) : gérer de VRAIS processus OS
(PID stocké en base, récolté via `SIGCHLD` -- voir
`tunnel_process.py`/`mount_process.py`) ne se prête PAS au même
partage multi-worker que les tampons de logs des autres services de
ce projet (Memcached, livraison #145) -- 2 workers Gunicorn ne
partagent pas leur mémoire, un PID connu d'un seul worker serait
invisible à l'autre. Plus simple et plus sûr de garder un seul
processus Python responsable de tous les sous-processus `ssh`/
`sshfs` qu'il lance, la base SQLite restant la source de vérité du
PID quel que soit le worker (unique) qui répond à une requête
donnée.

## Correctif #184 : mode proxy réellement inatteignable (bug réel)

La personne a rapporté un "connection refused" depuis l'onglet DBA
en tentant de se connecter à un tunnel MySQL fraîchement créé (port
distant 3306, port local 5306) -- le test de connexion bloquait.

Cause RÉELLE : `build_ssh_command` construisait `-L
{local_port}:{remote_host}:{remote_port}` SANS adresse de liaison
explicite -- `ssh` lie alors le port forwardé par défaut à
`127.0.0.1`, le LOOPBACK DU CONTENEUR `ssh-tunnels-api` LUI-MÊME,
invisible depuis N'IMPORTE QUEL autre conteneur (`dba-api` compris),
même sur le réseau Docker interne partagé. Casse directement le
"mode proxy" promis dès #159 ("le tunnel ouvre son port local sur le
conteneur, les autres API s'y connectent directement par son nom
Docker") -- jamais vérifié contre un vrai SECOND conteneur
consommateur avant ce rapport réel (seul `ssh-tunnels-api`
lui-même avait été testé, contre son propre processus).

Corrigé : liaison EXPLICITE `0.0.0.0:{local_port}:...` -- toutes les
interfaces du conteneur, donc atteignable via le réseau Docker par
son nom de service (`ssh-tunnels-api:5306` par exemple). Le
conteneur n'exposant AUCUN port vers l'HÔTE (pas de `ports:` dans
`docker-compose.yml`), ce changement élargit seulement l'accès au
réseau Docker INTERNE déjà partagé entre tous les conteneurs du
projet -- jamais vers l'extérieur.

**Vérifié réellement** : commande générée confirmée
(`0.0.0.0:5306:127.0.0.1:3306`), principe de liaison `0.0.0.0`
vérifié avec un VRAI socket TCP (accepte une connexion là où
`127.0.0.1` seul l'aurait refusée depuis un autre processus/
conteneur). Non-régression complète retestée (création/démarrage/
arrêt de tunnel, paramètres transmis correctement).

**Pour vérifier vous-même une fois redéployé** :
```bash
docker compose exec ssh-tunnels-api sh -c "ss -tlnp 2>/dev/null || netstat -tlnp"
```
Doit maintenant montrer `0.0.0.0:5306` (ou `:::5306`) au lieu de
`127.0.0.1:5306`. Et côté DBA, la connexion doit cibler l'hôte
`ssh-tunnels-api` (le nom du service Docker), PAS `localhost` ni
`127.0.0.1` -- ce dernier resterait toujours refusé, quel que soit
ce correctif (`localhost` depuis le conteneur `dba-api` désigne
`dba-api` lui-même, jamais `ssh-tunnels-api`).


Gérer de VRAIS processus OS pose le même problème que les logs avant
Memcached (#145) -- 2 workers Gunicorn ne partagent pas leur
mémoire -- mais en PIRE : un PID connu d'un seul worker serait
invisible à l'autre, et il n'existe pas d'équivalent "Memcached" pour
un descripteur de processus en cours d'exécution. Deux solutions
possibles : partager l'information via la base (le PID EST stocké en
base, n'importe quel worker peut le lire/signaler) -- fait ici -- OU
réduire à un seul worker pour éviter la question entièrement. Choix
assumé : **un seul worker**, la base restant la source de vérité du
PID par prudence supplémentaire (permet de reconsidérer ce choix
plus tard sans tout récrire).

## Piège réel trouvé en testant : processus zombies

Un enfant `ssh` arrêté (`SIGTERM` envoyé, ou mort de lui-même --
réseau coupé, hôte distant redémarré) reste un **processus ZOMBIE**
tant qu'il n'est jamais "récolté" (`waitpid`) par ce processus
Python. Un zombie répond **TOUJOURS** `os.kill(pid, 0)` avec succès
(le PID existe encore dans la table des processus) -- `is_process_alive`
le verrait donc À TORT comme "vivant" indéfiniment. Corrigé par un
gestionnaire `SIGCHLD` (`tunnel_process.install_reaper()`, installé
une fois au démarrage) qui récolte tout enfant terminé,
systématiquement.

## Vérifié réellement

`tunnels_store.py` testé directement (23 cas -- clés, upsert
idempotent, contraintes FOREIGN KEY et UNIQUE, cycle complet
connexions/tunnels/montages). `key_scanner.py` testé directement
(découverte de fichiers, exclusions, 4 défenses anti-traversée de
chemin) -- l'extraction d'empreinte testée avec un `ssh-keygen`
SIMULÉ (non disponible dans cet environnement, réseau restreint --
format de sortie documenté/stable, mais jamais vérifié contre le
VRAI binaire ici). `tunnel_process.py` testé avec un `ssh` SIMULÉ
(démarrage réussi, arrêt propre, échec rapide de connexion avec
message d'erreur réel capturé, **zombie détecté et corrigé** --
confirmé qu'aucun zombie ne s'accumule sur 5 cycles répétés).
Application complète (`app.py`) testée de bout en bout (25 cas) --
cycle complet clés→connexion→tunnel→démarrage/arrêt réels→échec de
démarrage réel→montages (interface, 501 explicite)→contraintes de
suppression.

**Non vérifié dans cet environnement** : contre un VRAI serveur SSH
distant (`ssh`/`ssh-keygen` simulés ici, réseau restreint empêchant
l'installation d'`openssh-client`) -- à tester en PRIORITÉ une fois
déployé, avec de vraies clés et un vrai hôte distant.

## Onglet hub (livraison #175)

`SshTunnelsView.jsx` (menu "Tunnels SSH") -- quatre sections dans
l'ordre logique d'usage : **Clés** (consultation/activation
seulement, jamais générées ni stockées ici) → **Connexions**
(host/user/clé) → **Tunnels** (démarrage/arrêt de vrais processus
ssh, statut avec dernière erreur visible) → **Montages SSHFS**
(interface complète, mais boutons monter/démonter affichent le 501
de l'API TEL QUEL -- action réelle toujours pas implémentée, voir
plus haut). Nouveau `hub/src/sshTunnelsClient.js`, même motif que
`gedClient.js`/`schemaAnalyzerClient.js`.

**Vérifié réellement** : `sshTunnelsClient.js` testé avec un `fetch`
simulé en Node (20 cas -- bonnes URLs/méthodes/corps pour chaque
fonction des 4 sections, y compris la préservation du message 501
tel quel pour montage/démontage, et le repli sur liste vide en cas
d'erreur réseau). Structure JSX de `SshTunnelsView.jsx` et de
`App.jsx` vérifiée par un contrôle d'équilibre accolades/
parenthèses/balises.

**Non vérifié dans cet environnement** : compilation Vite réelle ni
rendu visuel dans un vrai navigateur -- et, comme pour `ged`, ce
sera aussi le premier test de bout en bout réel du backend #159
(processus ssh, récolte des zombies, etc.), pas seulement de cette
interface.

## Montage SSHFS réel (livraison #180)

Demandé explicitement par la personne ("j'en ai besoin pour
concevoir la suite") -- volet explicitement reporté en #159
("privilèges élevés requis"), construit maintenant.

**Architecture** : nouveau `mount_process.py`, même motif que
`tunnel_process.py` -- `sshfs -f` (premier plan, condition pour que
le PID du sous-processus Python SOIT le montage lui-même,
contrairement à `sshfs` par défaut qui se détache en démon).
Démontage via `fusermount -u` (idempotent -- un point déjà démonté
ou un chemin absent du disque sont tous deux traités comme un
succès). Réutilise `is_process_alive`/le récolteur de zombies déjà
en place (`tunnel_process.install_reaper`, un seul suffit pour tous
les sous-processus de ce service, ssh ET sshfs).

**Sécurité du chemin** : `local_mount_path` est désormais un NOM
RELATIF (jamais un chemin absolu ni de traversée `..`) -- résolu et
restreint à `SSH_MOUNTS_BASE_DIR` (`/mounts` dans le conteneur),
même motif exact que `prefs-api/file_source_poller._resolve_safe_path`
(#176), dupliqué ici plutôt qu'importé (chaque service reste
autonome). Validé DÈS LA CRÉATION du montage, pas seulement au
premier `/mount`.

**Docker** : privilèges FUSE ajoutés au service (`cap_add:
SYS_ADMIN`, `devices: /dev/fuse`, `security_opt:
apparmor:unconfined` -- ce dernier nécessaire en pratique sur un
hôte Ubuntu/Debian avec AppArmor actif par défaut, même avec
SYS_ADMIN). Paquet `sshfs` ajouté au `Dockerfile`.

**⚠️ CORRIGÉ (livraison #355) -- `bind: propagation: rshared` cassait
le démarrage sur macOS.** Ce réglage (présent jusqu'à cette livraison
sur `SSH_TUNNELS_MOUNTS_DIR`, pensé pour qu'un montage FUSE fait À
L'INTÉRIEUR du conteneur devienne visible sur l'hôte) a été signalé
en conditions réelles par la personne : `docker compose up` échouait
avec "path .../ssh-tunnels/mounts is mounted on /host_mnt/Users but
it is not a shared mount". Confirmé par recherche -- limitation
CONNUE et ANCIENNE de Docker Desktop (`moby/moby#39093`, 2019,
toujours d'actualité) : contrairement à Linux natif, où la correction
habituelle (`mount --make-rshared` côté hôte) résout le problème,
plusieurs retours concordants confirment qu'elle NE FONCTIONNE PAS
de façon fiable sur Docker Desktop pour Mac/Windows -- pas un réglage
à ajuster, une limitation de fond de sa virtualisation.

**Compromis assumé** : propagation RETIRÉE par défaut dans
`docker-compose.yml` -- le conteneur démarre désormais partout
(macOS/Windows/Linux), mais un montage SSHFS fait DANS le conteneur
n'est PLUS visible depuis l'explorateur de fichiers de l'hôte
(Finder/Explorateur) -- reste consultable uniquement depuis
l'intérieur du conteneur. La gestion des tunnels/montages via l'API
elle-même n'est PAS affectée par ce compromis. Sur un hôte Linux
NATIF (pas Docker Desktop), voir le commentaire dans
`docker-compose.yml` pour retrouver la propagation `rshared` --
fonctionne normalement dans ce cas précis.

**Reste à tester contre un VRAI `sshfs`** -- réseau restreint dans
cet environnement, le binaire n'est pas installable (même limitation
déjà documentée pour `ssh`/`ssh-keygen`) :
- Le montage lui-même (nécessite le binaire, jamais testé ici).
- Les privilèges Docker (`cap_add`/`devices`/`security_opt`) --
  déduits de la documentation FUSE-in-Docker, jamais confirmés
  contre un vrai `docker compose up` sur la machine cible.

**Vérifié réellement** (ce qui l'est, malgré l'absence de `sshfs`
lui-même) : `fusermount` et `/dev/fuse` sont RÉELLEMENT présents
dans cet environnement -- `unmount_path` testée contre le VRAI
binaire (a corrigé une hypothèse initialement fausse sur le
vocabulaire d'erreur : "Invalid argument", pas "not mounted").
`stop_mount_process` testée avec un vrai processus qui ignore
SIGTERM (filet de sécurité SIGKILL confirmé). Migration de schéma
(colonnes `pid`/`last_error` ajoutées à `ssh_mounts`, ancien statut
`not_implemented` reclassé `unmounted`) testée contre une vraie base
SQLite simulant l'ancien schéma (#159), idempotente sur double
application. Orchestration complète `app.py` testée de bout en bout
(création avec validation de chemin, montage, remontage idempotent,
démontage, réconciliation d'un processus mort détecté à la lecture)
avec `start_mount_process`/`stop_mount_process` simulés (seule la
partie nécessitant le binaire `sshfs` lui-même). Non-régression
confirmée sur tunnels/connexions/clés (fonctionnalités existantes,
pas touchées mais le module partage des imports communs).

## Supervision des montages (livraison #182)

Demandé explicitement, en réponse à un résumé informationnel des
possibilités ("transforme ça en vraie fonctionnalité de
supervision") : `GET /mounts/<id>/stats` sur un montage ACTIF --

- **Espace et inodes distants** (`get_disk_inode_stats`) --
  `os.statvfs` À TRAVERS le montage, aucun coût réseau
  supplémentaire (SSHFS relaie l'appel au serveur distant via SFTP).
  ⚠️ `inodes.total`/`inodes.free` dépendent ENTIÈREMENT du système
  de fichiers DISTANT -- pertinents sur ext2/3/4, souvent 0 ou non
  significatifs sur XFS/Btrfs/ZFS côté serveur, rien à voir avec
  SSHFS lui-même.
- **Confirmation de montage actif** (`is_mount_point`,
  `os.path.ismount()`) -- signal COMPLÉMENTAIRE à `pid_alive`
  (processus vivant), jamais substituable : les deux peuvent
  diverger (démonté de l'extérieur sans que le processus ait encore
  été récolté, par exemple).
- **Latence** (`measure_latency`) -- un `os.stat()` chronométré,
  dans un thread séparé avec délai d'attente (`?latency=false` pour
  l'ignorer et répondre plus vite).

Réponse `409` si le montage n'est pas actuellement actif -- jamais
un `statvfs` sur un point non monté, qui renverrait SILENCIEUSEMENT
les stats du CONTENEUR lui-même plutôt que du serveur distant.

**Piège réel trouvé en testant** : `with ThreadPoolExecutor()`
bloque à la SORTIE du bloc jusqu'à ce que le thread sous-jacent
termine RÉELLEMENT (`shutdown(wait=True)` implicite) -- annulait
tout l'intérêt du timeout de `measure_latency` (mesuré : 2s
d'attente malgré un timeout de 0.3s demandé). Corrigé :
`shutdown(wait=False)` explicite, jamais via `with`.

**Autre piège trouvé** : `mount --bind` ne change JAMAIS `st_dev`
(donc invisible pour `os.path.ismount()`) -- pas représentatif d'un
montage FUSE/SSHFS, qui EST un système de fichiers séparé. Validé à
la place contre un VRAI montage `tmpfs` (même propriété qu'un
montage FUSE de ce point de vue).

**Vérifié réellement** : les trois fonctions testées contre de
VRAIES ressources -- `statvfs` sur un vrai répertoire, `ismount()`
contre un vrai montage `tmpfs` monté puis démonté, `measure_latency`
avec un VRAI `os.stat` chronométré ET avec un blocage simulé pour
confirmer le timeout réellement respecté (0.302s mesuré pour un
timeout de 0.3s, après correctif). Route `/mounts/<id>/stats` testée
de bout en bout contre un vrai montage `tmpfs` monté dans le
processus de test (409 sur montage inactif, structure complète de la
réponse, `?latency=false` respecté). Hub (`SshTunnelsView.jsx`) :
bouton "Stats" par montage actif, résultat affiché formaté
(`formatBytes`, testé en isolation, 9 cas). Corrigé au passage :
`handleMountAction`/`handleUnmountAction` n'actualisaient jamais la
liste après action (contrairement aux autres handlers) -- le statut
naissant serait resté invisible en pratique.

**Non vérifié dans cet environnement** : contre un vrai montage
SSHFS (le binaire n'est pas installable ici) -- les valeurs
d'inodes en particulier, dont la pertinence dépend du système de
fichiers distant réel visé.

## Indicateur visuel "action en cours" (livraison #197)

Demandé explicitement, item 18 du backlog : "ajouter une prise en
compte visuel des tentatives de lancement (diode orange ?)", "idem
partout où un délai est normal". Premier terrain d'application (le
cas explicitement nommé) -- démarrage/arrêt de tunnel, montage/
démontage SSHFS (`SshTunnelsView.jsx`).

**Principe** : `busy` (existant) est un booléen GLOBAL, désactive
tous les boutons pendant N'IMPORTE QUELLE action -- insuffisant pour
distinguer VISUELLEMENT laquelle ligne est concernée. Deux `Set()`
séparés par type d'action (`startingTunnelIds`/`stoppingTunnelIds`,
`mountingIds`/`unmountingIds`) -- l'id y est ajouté au clic, retiré
une fois la réponse HTTP reçue (succès OU échec) -- affiché
PRIORITAIREMENT au statut réel tant qu'il y est présent (le statut
serveur resterait sinon "arrêté"/"démonté" pendant toute la durée de
l'appel, laissant croire à tort que rien ne se passe).

**Pas encore fait** : les autres écrans du hub où un délai est
également normal (application de règles IMAP, interprétation de
message, import GLPI/Nebula -- ces derniers backend seul, pas encore
de tuile hub) -- le principe est posé et fonctionne ici, son
extension aux autres écrans reste à faire au cas par cas.

**Extension livrée en #209** : `GedView.jsx` (envoi de document,
envoi de nouvelle version -- par document, même motif de `Set`/état
dédié que `SshTunnelsView.jsx`) et `SchemaAnalyzerView.jsx` (import
des propositions détectées, préfixe 🟠 aligné sur l'analyse de schéma
qui avait déjà son propre indicateur textuel depuis avant #197, sans
le préfixe -- harmonisé ici).

**Vérifié réellement** : logique de calcul de l'état affiché testée
en isolation (priorité de l'état "en cours" sur le statut réel,
AUCUNE fuite d'état entre deux lignes -- un tunnel en démarrage
n'affecte jamais l'affichage d'un autre tunnel ; même vérification
faite pour l'upload de nouvelle version par document dans GedView).
Structure JSX revérifiée après chaque modification (retour implicite
converti en corps de bloc pour permettre le calcul intermédiaire,
là où nécessaire).

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici).

## Authentification par mot de passe (livraison #210)

Backlog item 12. Contexte donné par la personne : certains vieux
systèmes refusent la connexion par clé SSH. Demande explicite :
gestion SÉCURISÉE de couples utilisateur/mot de passe (jamais en
clair), avec un historique d'usage (quand, via quelle connexion,
durée).

### Architecture retenue

- **Stockage** : `shared/secret_crypto.py` (#202-206), via une
  enveloppe dédiée `credential_crypto.py` -- PAS le coffre-fort
  (même raisonnement que le PRA des secrets de démarrage, #203 :
  indépendance de Keycloak).
- **Différence assumée avec les secrets de démarrage** : un mot de
  passe SSH stocké doit pouvoir être déchiffré BIEN APRÈS le
  déploiement (au moment où quelqu'un démarre effectivement un
  tunnel/montage) -- ce service reçoit donc `SSH_TUNNELS_CRED_PASSPHRASE`
  et `SSH_TUNNELS_CRED_SALT` en variables d'environnement CONTINUES
  (pas une ressaisie ponctuelle à chaque déploiement comme pour
  `.env.encrypted`). Choix cohérent avec le reste du projet : d'autres
  secrets (mots de passe de base de données...) persistent déjà dans
  l'environnement d'un conteneur pour toute sa durée de vie.
- **Connexion SSH réelle** : `sshpass -e ssh/sshfs ...` --
  `BatchMode=yes` (interdit tout prompt interactif) est désactivé
  SEULEMENT en mode mot de passe, jamais en mode clé. Le mot de passe
  transite UNIQUEMENT par la variable d'environnement `SSHPASS` du
  SOUS-PROCESSUS -- jamais sur la ligne de commande (invisible via `ps`).

### Migration de schéma

`ssh_key_id` (NOT NULL à l'origine) rendu NULLABLE -- SQLite ne
permet pas de modifier une contrainte NOT NULL directement,
reconstruction de la table dans une TRANSACTION EXPLICITE (motif
standard, ROLLBACK automatique si une étape échoue). **Testée contre
une base SIMULANT EXACTEMENT l'état réel déjà en production**
(connexions et tunnels existants) -- confirmé : rien perdu, rien
dupliqué, `auth_method` rétro-rempli à `'key'` pour toutes les
connexions existantes (leur comportement réel actuel, jamais supposé
différent).

### Historique d'usage

Nouvelle table `ssh_credential_usage_history` -- une ligne PAR
TENTATIVE (tunnel ou montage), succès ET échecs. `ended_at` rempli à
l'arrêt (calcul de durée a posteriori) via une heuristique simple
(ferme la plus récente entrée ouverte pour cette connexion/type
d'action -- pas de référence directe stockée entre démarrage et
arrêt, suffisant tant qu'une même connexion n'a pas plusieurs
tunnels/montages démarrés/arrêtés en parallèle de façon chevauchée).

### Sécurité

`password_encrypted` (le jeton chiffré) n'est JAMAIS exposé via
l'API, même chiffré -- filtré à la sortie de `GET /connections` et
`POST /connections` (défense en profondeur, repéré et corrigé avant
même de tester).

### Vérifié réellement

Non-régression RIGOUREUSEMENT vérifiée sur le mode par clé (déjà en
production, plusieurs bugs réels déjà corrigés dessus -- #184, #185,
#188) : commande SSH/SSHFS identique à avant, migration testée
contre une base réelle simulée, démarrage/arrêt par clé testés de
bout en bout via l'app réelle (dont le cas "clé désactivée -> 409").
Mode mot de passe testé de bout en bout : création de connexion,
rédaction de `password_encrypted` confirmée à la liste ET à la
création, démarrage avec le VRAI mot de passe déchiffré transmis au
bon endroit, échec correctement historisé (jamais un faux succès),
fermeture d'historique à l'arrêt (durée calculable).

### Interface hub (livraison #211)

`SshTunnelsView.jsx` : sélecteur de mode d'authentification dans le
formulaire de création (clé/mot de passe), champs conditionnels sans
redondance (⚠️ correctif appliqué avant même de construire l'écran :
la route exigeait initialement `ssh_user` ET `password_username`
séparément en mode mot de passe pour la même information -- simplifié,
`password_username` porte seul ce rôle en mode mot de passe).
Indicateur 🔑/🔒 par connexion. Historique d'usage consultable par
connexion (chargé à la demande), avec durée calculée.

**Vérifié réellement** : logique de calcul de durée et de bascule
d'affichage testée en isolation. Structure JSX revérifiée après
chaque édition.

## Génération et suppression réelle de clés (livraison #277)

Deux notes explicites de la personne, restées en attente depuis
#210 : "permettre la suppression des clés ssh sans aucune
sauvegarde surtout" et "permettre de générer des clés sans
passphrase ou avec".

**Point capital trouvé en creusant AVANT de coder** : les deux
contredisaient une décision explicite prise avec la personne en
#159 -- `SSH_KEYS_DIR` monté en LECTURE SEULE, "ce service ne
génère ni ne stocke jamais de clé lui-même". Plutôt que d'inverser
silencieusement ce choix, la contradiction a été signalée
explicitement -- **la personne a confirmé** l'inversion
(montage passé en lecture-écriture), un vrai changement de posture
sécurité assumé pour ce service précis, pas un détail
d'implémentation.

### Suppression réelle -- `DELETE /keys/<id>`

Fichier ET registre supprimés, AUCUNE copie conservée nulle part --
exactement l'inverse du reste de ce projet (versionnement LDIF,
coffre-fort, GED...), la personne voulant explicitement cette
absence de filet pour du matériel de clé SSH.

**Garde-fou ajouté malgré tout** -- refuse (409) si la clé est
encore RÉFÉRENCÉE par une connexion active : la demande portait sur
l'absence de COPIE conservée, jamais sur l'absence de vérification
de sécurité élémentaire -- supprimer le fichier d'une clé en usage
casserait cette connexion sans prévenir. Ordre délibéré : fichier
supprimé D'ABORD, registre ENSUITE -- un échec de suppression du
fichier laisse la clé encore visible plutôt qu'un registre
incohérent avec un fichier orphelin.

### Génération -- `POST /keys/generate`

`ssh-keygen -t <type> -N <passphrase>` (`key_scanner.generate_key`)
-- `passphrase=""` (défaut) pour un usage automatisé non interactif,
ou une phrase non vide pour une clé protégée.

**Limite ASSUMÉE et documentée plutôt que cachée** : `ssh-keygen`
n'offre AUCUN mécanisme par variable d'environnement pour la
passphrase (contrairement à `sshpass -e`, déjà utilisé ailleurs dans
ce module pour l'authentification par mot de passe, #210) -- vérifié
auprès de la documentation officielle avant d'écrire cette fonction,
`-N` reste la SEULE voie non interactive. Expose donc BRIÈVEMENT la
passphrase dans la liste des processus de CE conteneur pendant
l'exécution -- jamais journalisée, jamais persistée nulle part,
fenêtre d'exposition locale et transitoire, pas une fuite durable,
mais réelle.

N'écrit PAS directement dans le registre `ssh_keys` -- le prochain
appel à `GET /keys` (déjà un rescan systématique à chaque appel)
détecte et enregistre automatiquement le nouveau fichier, aucune
logique d'enregistrement dupliquée.

### Vérifié réellement

`ssh-keygen` non installable dans cet environnement de développement
(réseau restreint, tentative d'installation confirmée échouée) --
`generate_key` testée avec un sous-processus SIMULÉ : validation
défensive du nom de fichier (`/`, `..`, vide), type de clé invalide,
refus d'écraser un fichier existant, construction EXACTE de la
commande (liste, jamais `shell=True`), passphrase vide ET non vide
correctement transmises via `-N`. **Vérification spécifique et
critique** : la passphrase n'apparaît JAMAIS dans le message
d'erreur renvoyé en cas d'échec de `ssh-keygen`, quel que soit le
contenu de `stderr`.

Suppression testée de bout en bout avec un VRAI fichier sur disque
(pas seulement simulée) : fichier ET registre confirmés supprimés
en l'absence d'usage ; refus confirmé (409) avec fichier ET registre
INTACTS quand une connexion référence encore la clé ; clé
introuvable gérée proprement (404). Non-régression complète du
reste du module reconfirmée. Structure JSX revérifiée après
l'ajout du formulaire de génération et du bouton de suppression.

**Non vérifié** : `ssh-keygen` réel (voir ci-dessus), et l'interface
hub en conditions réelles (aucun navigateur disponible ici).

## Premier branchement réel de rights-api (livraison #289)

Suite au backlog item 38 ("brancher rights-api sur les ~40 autres
API du projet... probablement commencer par les services les plus
sensibles") -- `ssh-tunnels-api` choisi comme prévu (clés SSH,
génération/suppression réelle depuis #277). `vault-api` délibérément
ÉCARTÉ comme premier candidat malgré sa sensibilité évidente : il a
déjà son propre modèle d'accès CRYPTOGRAPHIQUE par utilisateur
(chiffrement de bout en bout, voir `vault/README.md`) -- y brancher
le système de droits par GROUPES aurait fait doublon avec un
mécanisme déjà pensé pour cet usage précis, jamais présumé que les
deux se combinent proprement sans en discuter d'abord.

**Gating au niveau du SERVICE ENTIER** (`resource_type:
"ssh-tunnels-api"`, action `"manage"`) -- pas par clé/connexion
individuelle. Choix délibéré pour ce premier branchement : plus
simple à construire et à vérifier, tout en apportant une vraie
valeur (restreindre QUI peut générer/supprimer des clés, créer des
connexions, démarrer/arrêter des tunnels, monter/démonter du SSHFS).
Un affinage par ressource individuelle resterait possible plus tard
si le besoin se précise.

**12 routes protégées** : `DELETE /keys/<id>`, `POST /keys/generate`,
`POST/DELETE /connections`, `POST/DELETE /tunnels`,
`POST /tunnels/<id>/start`, `POST /tunnels/<id>/stop`,
`POST/DELETE /mounts`, `POST /mounts/<id>/mount`,
`POST /mounts/<id>/unmount`. Les routes de simple CONSULTATION
(`GET /keys`, `/connections`, `/tunnels`, `/mounts`) restent
OUVERTES -- seules les actions qui MODIFIENT un état sont gatées.

**FAIL CLOSED, jamais fail-open** : si `rights-api` est injoignable,
répond une erreur HTTP inattendue, ou une réponse illisible --
l'action est REFUSÉE, même pour un appelant qui aurait normalement
tous les droits (`admin_hub`). Un service qui gère des clés SSH
réelles ne doit jamais se rabattre sur "autorisé par défaut" en cas
de doute.

**OPT-IN, jamais actif par défaut** (`RIGHTS_API_URL`/
`SSH_TUNNELS_RIGHTS_API_URL` vide = gating désactivé, comportement
identique à avant #289) -- activer le gating sans que la personne
ait déjà un groupe `admin_hub` assigné dans Keycloak bloquerait ses
propres actions sans prévenir, en pleine session de test. À activer
explicitement dans `.env` une fois prêt.

**Vérifié réellement** : `_check_manage_right` testé en isolation
(gating désactivé, autorisé, refusé, ET les trois scénarios de
panne -- rights-api injoignable, HTTP non-200, réponse illisible --
confirmant le FAIL CLOSED dans les trois cas, y compris pour
`admin_hub`). Câblage réel testé sur `delete_key`/`create_connection`
-- confirmé qu'un refus n'exécute JAMAIS l'action (le fichier de clé
reste intact), et que la MÊME action réussit une fois le droit
accordé. Non-régression complète du reste du module reconfirmée
(gating désactivé = comportement identique à #277).

## Migration guidée vers des clés chiffrées (livraison #387)

Backlog item 22, suite de `migrate-env-to-encrypted.sh` (#386) --
même séquence de sécurité, adaptée aux fichiers binaires :

```bash
./scripts/migrate-ssh-keys-to-encrypted.sh
```

Découvre TOUTES les clés de `ssh-tunnels/keys/` (même convention que
ce module lui-même -- un fichier = une clé, `README.md`/`*.pub`
exclus), et pour CHACUNE : sauvegarde horodatée, chiffrement
(`secrets_tool.py encrypt-file`), puis déchiffrement de vérification
immédiat + comparaison OCTET PAR OCTET avec l'original
(`scripts/verify_file_migration.py`, nouveau -- une clé SSH n'a pas
de structure clé=valeur comme un `.env`, seule une comparaison
binaire directe a du sens). Phrase de passe redemandée SÉPARÉMENT
pour chaque clé, jamais stockée ni réutilisée automatiquement.

**Bug réel trouvé et corrigé en écrivant ce script** : les arguments
CLI de `encrypt-file`/`decrypt-file` (`path`) sont POSITIONNELS, pas
`--path` -- confondu une première fois avec la convention `--input`/
`--output` de `encrypt-env`/`decrypt-env` (ceux-là SONT nommés). Testé
avec de VRAIS outils de chiffrement (échoue en pratique à cause
d'une limite du harnais de test lui-même -- saisie de phrase de
passe à travers plusieurs invocations Python enchaînées sur un seul
pipe, voir `docs/chiffrement-secrets.md`), puis avec des remplaçants
factices pour isoler la logique d'orchestration : succès, écart
détecté (clé d'origine confirmée INTACTE), aucune clé présente dans
le dossier -- les trois cas se comportent comme prévu.

**La clé d'origine et sa sauvegarde ne sont JAMAIS touchées par ce
script.** Comme pour `.env` : ce script prépare et vérifie des
fichiers `.enc`, il ne bascule jamais ce module vers leur utilisation
effective -- `ssh-tunnels-api` continue de lire les clés en clair, ce
câblage reste un sujet séparé, non traité ici.
