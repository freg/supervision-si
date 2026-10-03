# Socle commun d'un nœud (#661 — étape 1 des items 108-110)

Le **socle** = ce qu'il faut sur n'importe quel hôte pour recevoir et appliquer des déploiements et servir l'interface
complète, sans les tuiles métier : `tls-proxy`, `keycloak` (passerelle), `services-api` (tour de contrôle : livraisons
zip, mise à jour git #659, plan, rebuild), `hub`, `memcached`, `prefs-api`, `rights-api`, `accounts-api`, `notify-api`.
Démarré avec `--no-deps` : les API des tuiles absentes ne sont pas lancées (le front les affiche indisponibles ; en
étape 2 la passerelle les routera vers le nœud qui les porte).

## Reprise sur un nouvel hôte

```
git clone https://github.com/<compte>/supervision-si.git && cd supervision-si
# depuis l'hôte d'origine, HORS dépôt : .env (secrets communs) et pki/ca/ (CA interne du hub, déjà connue des postes)
scp origine:~/SRC/data2/tickets/supervision-si/.env .
scp -r origine:~/SRC/data2/tickets/supervision-si/pki/ca pki/
python3 scripts/sync-env.py          # clés nouvelles de .env.example, jamais d'écrasement
python3 deploy/socle.py check        # .env, ca.crt, ca.key présents ?
sudo python3 deploy/socle.py up --build
python3 deploy/socle.py status
```

À adapter dans le `.env` recopié : `HOST_IP` (adresse de CE nœud), `VITE_ALLOWED_HOSTS`, et les URL publiques si le
nœud a son propre nom. La CA du bastion si-proxy (`si-proxy/.../ca.key`, `relay.key`) ne se copie **jamais** : elle
n'est pas dans le socle.

## Ajouter une tuile au socle

`python3 deploy/socle.py up +si-agent-api +qa-api` : la tuile et sa fermeture de dépendances compose rejoignent la
liste (hors `network_mode: host`, à lancer à part). `deploy/socle.py list +…` montre le découpage sans rien lancer.

## Suite

Étape 2 (paquets cohérents, placement multi-hôtes, conf passerelle) et étape 3 (miroir : réplication + bascule) :
`docs/architecture-clonage-distribution-hub.md`. Le déploiement réparti par cohortes (#513, `deploy/node_agent.py`,
`nodes.json`) reste la voie quand plusieurs nœuds sont déjà affectés.
