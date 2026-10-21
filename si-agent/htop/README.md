# si-htop (#800) — supervision « htop » en direct par UDP

Trois morceaux, bibliothèque standard Python seule :

| fichier | où | rôle |
|---|---|---|
| `emetteur.py` | chaque VM, CT et Proxmox (Python 3.5+, donc PVE 5.4) | relevé toutes les 2 s : CPU global et par cœur, iowait, steal, charge, mémoire (ARC ZFS à part), swap, processus les plus gourmands, partitions, pools ZFS ; sur un Proxmox, CPU et mémoire de chaque CT / VM lus dans les cgroups v1 / v2 avec leur nom |
| `relais.py` | pile supervision (service `htop-relais`) | reçoit les relevés signés, garde 10 min à pleine résolution et 24 h par minute (moyenne et pic, pics par invité), calcule les constats soutenus, les sert au central (tuile hub « htop », notifications) et les diffuse aux clients abonnés |
| `client.py` | poste d'exploitation | écran façon htop dans un terminal : liste des hôtes (invités rangés sous leur Proxmox), constats, détail d'un hôte (cœurs, processus, invités) ; signal sonore sur constat critique (`--son`, touche `s`) |

## Protocole

Paquet UDP = magie (4 octets) + HMAC-SHA256 tronqué à 16 octets + JSON compressé (zlib).
`SH1E` émetteur → relais (clé `HTOP_CLE_EMETTEURS`), `SH1S` abonnement client → relais et `SH1R` relais → client
(clé `HTOP_CLE_CLIENTS`). Le relais refuse un paquet mal signé, une horloge décalée de plus de 5 min, un numéro de
séquence rejoué. Le client renouvelle son abonnement toutes les 5 s et le relais répond à l'adresse source : aucun
port à ouvrir côté poste, NAT compris. 8 clients au plus.

## Constats (soutenus 60 s, hystérésis 5 points)

CPU ≥ 90 % (critique 98), iowait ≥ 30 % (50), steal ≥ 20 % (40), mémoire hors ARC ≥ 92 % (97), swap ≥ 60 % (90),
charge par cœur ≥ 2 (4), partition ≥ 90 % (97), pool ZFS ≥ 85 % (95) ou non ONLINE, CT / VM à ≥ 95 % de sa limite
mémoire hors cache (99), hôte muet depuis 30 s. Message : les trois plus gros consommateurs (invités d'un Proxmox,
sinon processus). Seuils réglables : `HTOP_SEUILS='{"cpu": 85, "duree_s": 120}'`. Le central (si-agent-api) lit les
constats toutes les 30 s et les verse au journal : `htop-alert` (gravité du constat), `htop-recovered` (fin).

## Mise en service

1. Central : dans `.env`, `HTOP_CLE_EMETTEURS`, `HTOP_CLE_CLIENTS`, `HTOP_JETON_INTERNE` (chacun : `openssl rand -hex 24`),
   puis `docker compose up -d --build htop-relais si-agent-api`. Port UDP publié : `HTOP_UDP_PORT` (8399) — l'ouvrir
   au pare-feu pour les adresses des émetteurs et du poste.
2. Chaque hôte surveillé (root) : copier `emetteur.py`, `si-htop-emetteur.service`, `installer-emetteur.sh` puis
   `sh installer-emetteur.sh --relais <relais>:8399` (clé demandée au clavier, rangée dans `/etc/si-htop/cle`).
3. Poste : clé client dans `~/.si-htop-cle` (chmod 600), puis `python3 client.py --relais <relais>:8399 --son`.
   Windows : `pip install windows-curses` ou `--texte`.

Contrôle sur un hôte : `python3 /usr/local/lib/si-htop/emetteur.py --afficher` (un relevé, rien n'est envoyé).
Tests : `python3 -m pytest si-agent/htop/test_htop.py`.
