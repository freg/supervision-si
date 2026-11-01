# Canal vers l'interface web d'un site distant (via relais si-proxy)

**But :** atteindre depuis le hub une interface web (ex. Proxmox `:8006`) d'un
site **injoignable de l'extérieur** (pare-feu, aucun entrant), en utilisant un
poste du site **qui a une route sortante** comme relais. Cas concret : PVE du
campus Numeria (pas de route entrante) atteint via le **minipc pc-numeria**.

**Aucun code nouveau** — on réutilise le bastion si-proxy : shim nommé sur un
poste de site (#575) + publication de port sur le relais (#583) + lien
« interface web ↗ » de la tuile Proxmox (`VITE_PROXMOX_WEB_URLS`).

```
navigateur ──▶ relais (conteneur hub, écoute :6488) ◀── shim « campus » (minipc, SORTANT)
   (hub)          publie 6488 → via campus → cible          │
                                                            └──▶ TCP  pve-campus:8006  (LAN campus)
```

Le shim **compose vers le relais** (rien d'entrant sur le campus). Le relais
apparie et pompe les octets. Le minipc est le seul à ouvrir une socket vers le
PVE campus.

## Prérequis

- Relais si-proxy du hub joignable depuis le minipc (voir « Transport » plus bas).
- Un **jeton de shim host** (`SI_PROXY_HOST_TOKEN`) et la **CA du projet**
  (`si-proxy/certs/ca.crt`) — mêmes éléments que le shim du hub.
- L'IP LAN du PVE campus (ex. `pve-campus` ou `172.16.x.y`) et son port web (`8006`).
- Le minipc est récent (Python 3.7+ / asyncio) — OK pour le shim.

## Étape 1 — Shim « campus » sur le minipc

Depuis la racine du dépôt sur le minipc, selon le **transport** disponible :

**A. Le minipc joint directement le port du relais** (ex. `supervision.optline.fr:6450`) :

```
sudo ./si-proxy/install-host.sh \
  --name campus \
  --relay supervision.optline.fr:6450 \
  --ca si-proxy/certs/ca.crt \
  --token "$SI_PROXY_HOST_TOKEN" \
  --shell-user root \
  --deny 0.0.0.0/0            # (optionnel) voir Sécurité : restreindre à la seule cible
```

**B. Le minipc ne sort que par SSH** (le relais est joint par un tunnel SSH local, #575) :

```
sudo ./si-proxy/install-host.sh \
  --name campus \
  --relay supervision.optline.fr:6450 \
  --ca si-proxy/certs/ca.crt \
  --token "$SI_PROXY_HOST_TOKEN" \
  --ssh-jump user@supervision.optline.fr:22 \
  --ssh-key /etc/si-proxy/jump.key
```

Vérifie l'enregistrement : `journalctl -u si-proxy-host -f` doit montrer
« shim host « campus » enregistré ».

## Étape 2 — Publication du port sur le relais (côté hub)

Sur le hub, ajoute une publication au service `si-proxy` — via l'option
`--publish` du relais, ou l'env `SI_PROXY_PUBLISH` (séparés par des virgules) :

```
SI_PROXY_PUBLISH=6488=campus:pve-campus:8006
SI_PROXY_PUBLISH_ALLOW=<IP du Mac / du réseau autorisé>      # restreint qui peut ouvrir 6488
```

Le relais écoute alors `:6488` et pousse chaque connexion vers `pve-campus:8006`
**via le shim « campus »**, sans client siproxy. Expose `6488` sur le service
`si-proxy` (bloc `ports:`) comme le port du relais, puis redéploie `si-proxy`.

## Étape 3 — Lien « interface web ↗ » dans la tuile Proxmox

Dans le `.env` du hub :

```
VITE_PROXMOX_WEB_URLS=pve-campus=https://supervision.optline.fr:6488
```

(`pve-campus` = l'`agent_id` de l'agent Proxmox campus dans la flotte.) Rebuild
du front `hub`. Le lien « interface web ↗ » de la fiche du nœud ouvre alors
l'interface Proxmox du campus, tunnelée par le minipc.

## Sécurité

- **TLS/PKI du projet** de bout en bout (cert du relais, CA vérifiée par le shim).
- **`--publish-allow`** limite les IP autorisées à ouvrir le port publié.
- **`--deny`** sur le shim restreint ce que le minipc accepte d'ouvrir : pour
  n'autoriser QUE le PVE campus, denie large et laisse la publication cibler la
  seule IP:port voulue (le shim n'ouvre que ce que le relais lui demande, et le
  relais n'ouvre que la publication déclarée — donc la cible est déjà bornée).
- **Audit** : chaque session est journalisée (métadonnées, jamais la charge) —
  `siproxy.audit`, visible dans l'interface de contrôle du bastion.
- Le minipc porte aussi le si-agent : deux canaux sortants indépendants, sans
  interférence.

## Kill switch

- Couper le canal : `systemctl stop si-proxy-host` sur le minipc (et le tunnel
  `si-proxy-jump` si variante B). La publication du relais retombe « down ».
- Retirer la publication côté hub : enlever l'entrée de `SI_PROXY_PUBLISH` et
  redéployer `si-proxy`.

## Réutilisable

Ce schéma vaut pour tout site sans entrant : un shim nommé par site + une
publication `PORT=SHIM:CIBLE` par service web à exposer (Proxmox, une appli
interne, un équipement). C'est aussi la brique de base de l'« agent miroir
portail » (backlog item 110).
