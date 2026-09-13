# mikrotik — supervision et commande des routeurs MikroTik

Livraison #485. Demandé explicitement : « intégrer les fonctionnalités
de base de supervision et de commande/paramétrage dans une interface
du hub ». Tuile « Routeurs MikroTik » de la thématique **Réseau**,
servie sous `/mikrotik/` par tls-proxy.

⚠️ **Jamais testé contre un vrai routeur** à la livraison — tout est
testé contre un faux RouterOS en mémoire (`tests/smoke_test.py`). Le
premier contact réel peut révéler des écarts de champs (les noms de
compteurs varient selon les versions de RouterOS).

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
- **Identifiants** : `.env` (SECRET, jamais versionné) —
  `MIKROTIK_USER` / `MIKROTIK_PASSWORD` partagés, ou par routeur via
  `"credential": "agence"` → `MIKROTIK_AGENCE_USER` /
  `MIKROTIK_AGENCE_PASSWORD` (nom en majuscules, tirets → `_`).

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

