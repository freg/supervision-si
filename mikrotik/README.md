# mikrotik — supervision et commande des routeurs MikroTik

Livraison #485. Demandé explicitement : « intégrer les fonctionnalités
de base de supervision et de commande/paramétrage dans une interface
du hub ». Tuile « Routeurs MikroTik » de la thématique **Réseau**,
servie sous `/mikrotik/` par tls-proxy.

⚠️ **Jamais testé contre un vrai routeur** à la livraison — tout est
testé contre un faux RouterOS en mémoire (`tests/smoke_test.py`). Le
premier contact réel peut révéler des écarts de champs (les noms de
compteurs varient selon les versions de RouterOS).

## Transport SSH (#587) — « le hub doit être transparent »

`"transport": "ssh"` dans le registre (port 22 par défaut) : la tuile parle
au routeur par la CLI RouterOS **en SSH**, l'accès que l'administrateur a déjà
ouvert — rien à activer ni changer sur le routeur (pas de www-ssl, pas d'API),
RouterOS v6 et v7. Même accès du coffre (utilisateur + mot de passe ; le hub
se connecte en `user+ct`, sans couleurs ni pagination). Les objets sont lus
par le langage de script (`:put [/ip firewall nat get $i]`) et parsés ; les
gestes sont des commandes CLI dont chaque valeur est validée et citée
(`mikrotik/ssh_client.py`, `natrules.py`). Même surface que le REST : résumé,
interfaces, ping, redémarrage, **et** :

- **Règles NAT** (`GET/POST /mikrotik/routers/<n>/nat`, `PATCH/DELETE
  …/nat/<*id>`) : traduction ip:port → ip:port (dst-nat / redirect), src-nat /
  masquerade ; champs bornés (chaîne, action, protocole, adresses, ports,
  interfaces, commentaire, activée) ; suppression confirmée
  (`{"confirm": "REMOVE"}`) ; chaque geste journalisé. Disponible aussi en
  REST (PUT / PATCH / DELETE `ip/firewall/nat`).
- **Relevés** (`POST …/command`, SSH seulement) : commandes en lecture seule
  — `print`, `export`, `get`, `monitor-traffic` — tout verbe modifiant
  (`set`, `add`, `remove`, `reboot`, `$`, `;`…) est refusé avant d'atteindre
  le routeur ; liste de relevés proposés (`GET /mikrotik/commands`).
- Empreinte SSH non épinglée (patte interne, comme le module Cisco) ;
  `MIKROTIK_SSH_TIMEOUT` (12 s). Tests : `tests/test_ssh_nat.py` (parseurs,
  session simulée, règles), `tests/test_api_ssh.py` (routes).

## Transport : API REST RouterOS v7

HTTPS + authentification Basic sur le service `www-ssl` du routeur
(activé par défaut sur v7). **RouterOS v6 non couvert** (pas d'API
REST, seulement l'API binaire :8728) — un routeur v6 apparaît
« injoignable », jamais comme une donnée fausse. TLS non vérifié par
défaut (certificats auto-signés quasi systématiques, posture LAN) ;
`MIKROTIK_TLS_VERIFY=1` réactive la vérification.

## Registre et identifiants

- **Registre** : `mikrotik/routers.json` (versionné) — nom, hôte,
  port, et la clé `credential` optionnelle. Éditable sans rebuild
  (bind mount en lecture seule, rechargé à chaque requête).
- **Identifiants** (depuis #498) : le **coffre des accès
  d'équipements** du hub (`credentials/`, tuile « Accès d'équipements »
  de la thématique Sécurité & accès), plus rien dans `.env`. La clé
  `"credential"` du registre est le nom de l'accès dans le coffre ;
  `"default"` (ou absente) = l'accès nommé **`mikrotik`**. Révélation
  par jeton interne (`CREDENTIALS_INTERNAL_TOKEN`, jamais exposé au
  navigateur), cache mémoire 60 s (`CREDENTIALS_CACHE_SECONDS`)
  invalidé sur refus d'authentification : un accès corrigé dans la
  tuile prend effet à la sonde suivante. Un accès absent est signalé
  dans la liste avec un lien vers la tuile.

## Fonctionnalités

- **Supervision** : identité, version RouterOS, uptime, CPU, mémoire,
  disque, température/tension quand le modèle les expose ; interfaces
  avec état et compteurs de trafic.
- **Commande** (corps JSON explicite, jamais déclenchable par un
  simple GET) : activer/désactiver une interface, ping depuis le
  routeur (borné à 20 paquets), redémarrage (double confirmation +
  `{"confirm": "REBOOT"` côté API).

⚠️ Couper l'interface par laquelle on **joint** le routeur coupe la
commande au milieu — le PATCH part, la réponse peut ne pas revenir.
Inhérent au geste, signalé dans l'interface.

## Routes API

```
GET  /mikrotik/routers                        registre + joignabilité
GET  /mikrotik/routers/<n>/summary            identité/ressources/santé
GET  /mikrotik/routers/<n>/interfaces         interfaces + compteurs
POST /mikrotik/routers/<n>/interfaces/toggle  {"id":"*3","enable":false}
POST /mikrotik/routers/<n>/ping               {"address":"…","count":4}
POST /mikrotik/routers/<n>/reboot             {"confirm":"REBOOT"}
GET  /mikrotik/health | /mikrotik/version
```

## Intégration transversale (livraison #486)

Chaque routeur du registre a une **IP** — c'est la clé de croisement
avec le reste du hub. Mis en œuvre :

- **Supervision SI** (carte + table) : type d'équipement « Routeur
  MikroTik » (origine mikrotik), fusionné par IP avec ce que les
  sondes et l'exploration réseau voient déjà — un seul équipement,
  plusieurs origines. L'état vient de la joignabilité mesurée par
  mikrotik-api ; la position sur la carte suit le mécanisme commun
  (nom, site, liens déduits).
- **Liens profonds** : le bouton d'origine « Routeur MikroTik » (table
  Supervision SI) ouvre la tuile sur `/mikrotik/#router=<nom>` —
  ancre comprise par l'interface (sélection initiale + hashchange).
- **Tickets** : bouton « Créer un ticket » dans la fiche équipement
  (cadre Liens) — `source_type="mikrotik"`, `source_nom=<nom>` quand
  l'équipement est un routeur déclaré ; le portail tickets affiche
  alors un lien « ouvrir le routeur » vers la même ancre.

## Carte des redirections NAT (livraison #606)

`GET /mikrotik/nat-map[?site=]` (`natmap.py`, pur, testé) : les règles NAT
de tous les routeurs du registre, normalisées en flux « entrée → routeur →
cible » (`kind` inbound / outbound), regroupées par cible, avec les
**conflits** (deux règles actives sur le même port d'entrée d'un routeur :
la seconde n'est jamais atteinte), les désactivées et les routeurs
injoignables (jamais une 500). Tuile hub **Redirections NAT** (Réseau ;
vue métier : Équipements › Réseau › Routeurs et Services › Entrées
d'Internet) : schéma SVG à trois colonnes (Internet / entrée, routeur,
cible LAN nommée par les agents hôtes quand l'adresse est connue), flux
verts / rouges (conflit) / gris pointillés (désactivé), filtre début de mot,
tableau avec activer / désactiver sur place, lien vers la tuile MikroTik
pour ajouter ou modifier.
