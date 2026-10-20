# Navigateur de l'hôte (livraison #798)

Un Chromium **visible** qui tourne sur l'hôte d'un agent Linux -- en priorité une VM OVH, pour voir **nos services
depuis l'extérieur** -- et non dans le navigateur qui consulte le hub. Pour le débogage et la QA :

- **Écran web** (noVNC) : on voit et on utilise ce navigateur depuis la tuile « Navigateur des hôtes » du hub ;
- **Automate** (Playwright branché en CDP sur ce même navigateur) : ouvrir une adresse, capturer, jouer un parcours au
  format QA (`goto`, `click`, `fill`, `select`, `check`, `press`, `wait`, `expect_*`, `screenshot`), avec arrêt avant
  les étapes marquées `"ecrit": true`. On voit l'automate travailler dans l'écran et on peut reprendre la main.

```
hub (https) ──/navigateur/<nom>/──▶ tls-proxy ──▶ si-proxy:<port publié> ══ bastion ══▶ shim de l'hôte ──▶ 127.0.0.1:6080 (noVNC)
hub ──commande « navigateur »──▶ central ◀── agent de l'hôte (relève) ──▶ 127.0.0.1:8094 (automate, jeton) ──CDP──▶ Chromium
```

Rien n'écoute sur une interface publique de l'hôte : écran, VNC, CDP et automate sont sur 127.0.0.1 (réseau de l'hôte).

## Installation sur l'hôte (root, Docker requis, agent si-agent déjà installé)

```
cd /opt && git clone <dépôt> supervision-si      # ou copie du dossier navigateur/ seul
cd /opt/supervision-si/navigateur && sudo sh installer.sh
```

Le script crée `.env` (jeton de l'automate, mot de passe de l'écran -- 8 caractères, limite VNC), dépose le jeton pour
l'agent (`/etc/si-agent/navigateur/jeton`, `port`), construit et démarre le conteneur, et affiche le mot de passe de
l'écran. Relancé, il garde les secrets.

## Publication de l'écran (une fois par hôte)

1. **Shim du bastion sur l'hôte** (si absent) : `si-proxy/install-host.sh`, nom du shim = par ex. `ovh1`
   (voir `docs/canal-web-site-distant.md`, étape 1).
2. **Publication sur le relais** (`.env` du hub) : `SI_PROXY_PUBLISH=…,6490=ovh1:127.0.0.1:6080`. Si
   `SI_PROXY_PUBLISH_ALLOW` est renseigné, y ajouter le réseau Docker du hub (tls-proxy s'y connecte), ex. `172.16.0.0/12`.
3. **Chemin sous le hub** (`.env` du hub) : `NAVIGATEURS=ovh1=6490`, puis
   `cd ~/SRC/data2/tickets/supervision-si && ./scripts/run.sh up -d --build si-proxy tls-proxy si-agent-api hub`.
4. **Déclaration** dans la tuile : « + Déclarer un navigateur » (nom `ovh1`, agent de l'hôte, libellé).

L'écran est alors sous `https://<hub>/navigateur/ovh1/` (même origine que le hub, mot de passe de l'écran demandé).

## Réactivité

L'automate passe par la relève des commandes de l'agent (60 s par défaut). Pour un hôte de QA, la réduire à 5 s :
réglage `commands_poll_seconds` de l'agent. L'écran, lui, est en direct.

## Fichiers

`Dockerfile` (image Playwright + Xvfb, fluxbox, x11vnc, noVNC), `entrypoint.sh` (écran, Chromium relancé s'il est
fermé, profil persistant), `automate.py` (API locale ; tests `test_automate.py` sans navigateur), `docker-compose.yml`,
`installer.sh`. Côté agent : `si-agent/agent/si_agent/navctl.py`. Côté central : `si-agent/api/navigateurs.py`
(registre), commande `navigateur`. tls-proxy : `NAVIGATEURS`. Hub : `NavigateurView.jsx`, `navigateurLib.js`.
