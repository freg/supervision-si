# si-agent (agent)


## Python requis et hôtes anciens (livraison #646)

L'agent requiert **Python >= 3.7**. `install.sh` le **vérifie avant tout
enrôlement** (interpréteur d'exécution = `--python`, défaut le `python3`
système) et **refuse proprement** sur un hôte trop ancien (Debian 9 / PVE 5 =
Python 3.5) au lieu d'installer un service qui boucle en crash. Sur ces hôtes :
installer un **Python autonome** (aucun changement système, l'agent est stdlib
pur) et lancer `install.sh --python <chemin>` -- procédure : `docs/agent-python-autonome.md`.
Le service systemd est écrit avec cet interpréteur (ExecStart). Les scripts
d'amorçage (enrôlement, vérif CA) restent sous le `python3` système, compatibles 3.5.
