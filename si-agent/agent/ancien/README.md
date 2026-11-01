# Installeur des hôtes anciens (#867)

Un script pour **toutes les versions de Debian** (4.0 etch, 5.0 lenny… jusqu'aux récentes) : `install-ancien.sh`.

- **Détection** (lecture seule) : version Debian, architecture, glibc, Python 3, OpenSSL, OpenSSH.
- **Hôte récent** (x86_64 + glibc ≥ 2.17, ou Python ≥ 3.7) : renvoie vers l'agent complet (`install.sh`, Python autonome #864).
- **Hôte ancien** (Debian 4 à 7, i686 sans Python récent…) : l'agent ne peut pas tourner (pas de Python 3, TLS < 1.2).
  Le script installe un **compte de relevé** `si-agent` : mot de passe verrouillé, clé limitée à l'IP de l'agent
  relayeur (`from=`), **commande forcée** qui n'exécute que le relevé de la sonde `systemes` (lecture seule ; ni shell,
  ni pty, ni redirection). L'agent relayeur (super) le lit par ssh, sans changement de son côté.
- `--sudo` (option) : une ligne `NOPASSWD` limitée au relevé dans `/etc/sudoers` (vérifiée par `visudo`, copie `.bak`)
  pour avoir les noms des processus à l'écoute.
- Par défaut **`--verifier`** : rien n'est modifié. `--installer` applique, `--retirer` défait tout.

Le relevé embarqué est **généré** depuis `plugins/systemes/systemes.py` : après toute modification du relevé,
`python3 si-agent/agent/ancien/make-installer.py` (le test `test_install_ancien.py` échoue sinon).

Remplace la manipulation manuelle faite sur nms (root) et optick3 (compte personnel) : plus de compte root ni de
compte personnel pour le relevé.
