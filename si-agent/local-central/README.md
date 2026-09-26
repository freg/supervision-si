# Central local de test (`local_central.py`, livraison #624)

Remplace le hub sur un poste de travail (Mac, Linux) pour piloter un ou
quelques agents **sans Docker, sans Keycloak, sans réseau d'entreprise** :
Python 3.8+ stdlib, `openssl`, `bash` et `tar` (présents sur macOS).
Fait pour : essayer l'agent Windows chez soi (image P2V à chaud,
redémarrage, lanceurs, chien de garde, banc de charge, réveil réseau),
démonstration hors ligne, dépannage d'un agent.

## Lancer

    cd si-agent/local-central
    python3 local_central.py                 # https://<IP du poste>:6444  (interface : la même URL)
    python3 local_central.py --plugins web-audit,windows-probe --plugin-arg web-audit="--urls https://exemple.test"
    python3 local_central.py --http --port 8080          # HTTP clair, test seulement
    python3 local_central.py --listen 127.0.0.1          # interface et face agents sur le seul poste

Au premier démarrage : PKI auto-signée dans `data/pki` (servie sur `/ca`,
**épinglée** par l'installeur via `-CaFingerprint`, aucune confiance
système à ajouter sur le poste), archive de l'agent construite par
`si-agent/make-archive.sh` dans `data/`, jeton d'enrôlement. Le terminal
et l'interface affichent la ligne à coller :

- Windows, PowerShell **administrateur** : une ligne `powershell -NoProfile … iex …/deploy/windows?token=…`
  (délégué C# pour accepter le certificat auto-signé pendant l'amorçage,
  comme `install.ps1` sur PowerShell 5.1 ; l'installeur vérifie ensuite
  l'empreinte de la CA) ;
- Linux / macOS : `curl -fsSL -k '…/deploy/linux?token=…' | sudo sh`.

Le pare-feu du poste doit laisser entrer le port 6444 (macOS demande
l'autorisation pour `python3` au premier lancement).

## Interface (`/`)

Agents (dernier contact, IP, hôte), événements, et par agent : **poste**
(collecte, redémarrage/arrêt/annulation, réveil d'un autre poste par paquet
magique, banc de charge), **image** (Disk2vhd à chaud : cible, lecteurs,
outil, suivi `image-*`, aide-mémoire d'import Proxmox), **lanceurs**
(activer / désactiver), **watchdog** (une application par ligne),
**sondes** (mesures brutes), **commandes** (commande brute JSON, historique
et résultats). Aucune authentification : n'exposer que sur un réseau de
confiance.

## Face agents

Même contrat que si-agent-api, avec `si_agent/protocol.py` et
`si_agent/control.py` importés (jamais réimplémentés) : `POST /api/v1/enroll`
(jeton), `GET …/config` et `GET …/commands` **signés** avec le secret de
l'agent (plugins signés de même), `POST …/measurements`, `POST …/commands/<id>/ack`,
`GET /ca`, `GET /package`, `GET /package/info`, `GET /deploy/<windows|linux>?token=`.
Les plugins servis sont ceux de `si-agent/agent/plugins/<id>` (`--plugins`).

## Données

`data/state.json` : jeton, agents **avec leur secret**, commandes, dernière
mesure par tâche, 500 derniers événements — ne pas partager ce dossier, il
est hors dépôt (`data/` ignoré). « Oublier » un agent dans l'interface
oblige à le réenrôler ; le poste garde son `agent.json` : relancer
l'amorçage ou l'installeur avec `-Upgrade` n'y touche pas, utiliser
`uninstall.ps1` puis réenrôler.

## Tests

    cd si-agent/local-central && python3 -m unittest test_local_central
