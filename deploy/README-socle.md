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

## Miroir froid (#663 — étape 3)

Actif/passif. Le **primaire** envoie ses sauvegardes totales/incrémentales (`scripts/full_backup.py`, chiffrées avec
`SI_BACKUP_PASSPHRASE`, même `.env` des deux côtés) à l'agent de nœud du **miroir** (`deploy/node_agent.py serve`,
VPN + `SI_NODE_TOKEN`), qui les restaure par-dessus son dépôt, services arrêtés. Mise en place :

```
# miroir : socle + agent de nœud, rien de démarré (déjà dans nodes.json avec son adresse VPN)
# primaire :
cp deploy/mirror.example.json deploy/mirror.local.json   # node, host_ip du miroir, role_id (#654) facultatif
python3 deploy/mirror.py sync --full      # première synchronisation (puis `sync` incrémental, à planifier : cron)
python3 deploy/mirror.py status           # âge de la dernière synchro (RPO), archives et services côté miroir
```

Tour de contrôle → Répartition → carte **Miroir froid** : Synchroniser, Basculer (`failover` : le miroir régénère ce qui
est propre à son hôte — HOST_IP, certificat serveur ; CA et sels conservés — démarre tout, puis la tour bascule le rôle),
Revenir (`failback` : sauvegarde du miroir restaurée sur le primaire, miroir en standby, rôle rendu). RPO = intervalle des
`sync` ; RTO = durée du job de bascule. Les données modifiées sur le miroir pendant la bascule reviennent par `failback`
seulement — ne jamais faire tourner les deux en même temps (le rôle désigne « celui qui répond »).
