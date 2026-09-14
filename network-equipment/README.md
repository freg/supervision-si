# Équipements réseau — identification et profils de supervision (livraison #506)

Facette « équipements réseau » de l'exploration : **qui** sont les
routeurs, switchs et autres équipements de niveau 2/3 du LAN
(constructeur, modèle, système, numéro de série, **génération**), d'après
toutes les sources déjà présentes dans le hub, et **quoi** relever dessus
(profils de supervision SNMP génériques par constructeur).

Demande d'origine : « identifier côté LAN la marque et le modèle d'un
routeur sachant que les routeurs récents sont les MikroTik et que les
autres, s'il en reste, datent de l'origine de la boucle locale fibre
(~25 ans) ; à partir de la base Zenoss / SNMP récupérer ces infos et
celles des switchs/équipements niveau 2 ; préparer des interfaces de
supervision génériques Cisco, HP… ».

## Ce que fait le service (`network-equipment-api`, `/api/network-equipment/`)

Une fiche par équipement (SQLite, `/data/network-equipment.db`),
rapprochée entre les sources par **MAC**, puis IP, puis nom. Les champs
identifiés ne sont jamais saisis directement : ils sont **recalculés**
par `identify.merge` à partir des preuves stockées, et un choix manuel
a le dernier mot.

| Source | Ce qu'elle apporte | Comment |
|---|---|---|
| Exploration réseau (`network-agent`) | MAC → constructeur (OUI), dernière IP, nom résolu, rôle observé (passerelle), services en écoute | `POST /import/network-agent` (bouton « Importer l'exploration ») |
| SNMP via `snmp-api` | `sysDescr` / `sysObjectID` / `sysName` (modèle, système, version, genre), **ENTITY-MIB** (modèle exact, numéro de série), voisins **LLDP** et **CDP**, **table des adresses MAC** (BRIDGE-MIB / Q-BRIDGE-MIB), noms de ports | `POST /equipment/<id>/identify`, `POST /identify/batch` |
| Zenoss 2.5 | classe (`/Network/Router/Cisco`…), constructeur/modèle matériel, OS, série, sysDescr/sysObjectID collectés par Zenoss, interfaces (MAC) | `POST /import/zenoss` : JSON du script zendmd **ou** CSV de la liste |
| Manuel | constructeur, modèle, genre, génération, notes | `PUT /equipment/<id>` |

### Génération : « récent » ou « ancien »

C'est le point demandé. `identify.generation_of` date l'équipement
quand une preuve le permet, avec la raison affichée dans la tuile :

- RouterOS (MikroTik), Ubiquiti, IOS ≥ 15, IOS-XE, révision ProCurve /
  Aruba à deux lettres → **récent** ;
- familles Cisco d'avant 2005 (C1600/1700/2500/2600/3600/3700,
  Catalyst 1900/2900XL/3500XL/2950/3550/4000/5000, CatOS), IOS 11.x /
  12.0-12.2 mainline, IOS 12.3/12.4, ProCurve à révision à une lettre
  (`F.05.70`…) ou gammes 1600M/2524/2650/4000M, BayStack / Accelar,
  SuperStack II/3, OmniStack → **ancien** ;
- branche Catalyst 12.2S* (2960/3560/3750 de 2005-2013) → indéterminée
  (la tuile l'écrit) ; tout ce qui n'est pas reconnu reste « — » : rien
  n'est daté au hasard.

### Constructeur d'après la MAC (OUI)

`oui.py` embarque une **amorce** (~400 préfixes : MikroTik, Cisco des
années 1990-2010, HP ProCurve/Aruba, 3Com, Nortel/Bay, Netgear,
Linksys, Juniper, D-Link, Ubiquiti, Zyxel, Alcatel, Extreme, Fortinet,
TP-Link, APC, VMware/QEMU/Xen/Hyper-V/VirtualBox/Docker, Raspberry Pi,
Dell, Synology, QNAP) avec une **catégorie** (réseau, virtualisation,
hôte…) qui nourrit la classification : une MAC VMware n'est jamais un
routeur physique. Pour la couverture complète, charger le registre IEEE
(`oui.csv` « MA-L » de standards-oui.ieee.org, ou `oui.txt`) par le
bouton « Registre OUI… » (`POST /oui/import`) : il est conservé dans le
volume `/data` et rechargé au démarrage.

### Genre (routeur, switch, pare-feu, point d'accès, hôte…)

Déduit de la famille d'image IOS (C2950 = switch, C2600 = routeur…),
des motifs sysDescr, de la classe Zenoss, du rôle observé par
l'exploration (passerelle = routeur), des services (API RouterOS /
Winbox = routeur, RDP/SMB = hôte, 9100 = imprimante), puis de la
catégorie OUI. Un constructeur réseau sans autre indice donne
« équipement réseau ».

## Profils de supervision (`profiles.py`)

Données, pas du code : par constructeur, les OID à relever (GET
scalaires, WALK de colonnes, énumérations décodées, unités en dixièmes
converties) et une **synthèse** (`interpret`) : CPU %, mémoire %,
température, alarmes (ventilateur/alimentation en défaut, composant
down), plus les **interfaces IF-MIB** pour tous.

| Profil | Relevés |
|---|---|
| `cisco-ios` | CPU (CISCO-PROCESS-MIB **et** OLD-CISCO-CPU-MIB pour les IOS 11/12), pools mémoire, température / ventilateurs / alimentations (CISCO-ENVMON-MIB), voisins CDP |
| `cisco-catos` | CDP, envmon si présent (CatOS n'a pas de CPU/mémoire standardisés) |
| `hp-procurve` | CPU (hpSwitchCpuStat), mémoire (hpLocalMem), capteurs (hpicfSensor : ventilateur, alimentation, température) |
| `hp-comware` | CPU / mémoire / température par entité (hh3cEntityExt) |
| `mikrotik` | version, série, firmware, températures et tension (MIKROTIK-MIB), CPU et mémoire HOST-RESOURCES — la tuile « Routeurs MikroTik » (API REST) va plus loin |
| `juniper` | composants jnxOperating* (CPU, température, mémoire, état) |
| `generic-host` | UCD-SNMP (charge, mémoire) + HOST-RESOURCES |
| `generic-bridge` | universel : IF-MIB, ENTITY-MIB, LLDP, table MAC (3Com, Nortel, Netgear, D-Link, Zyxel, Alcatel… en attendant leur MIB propriétaire) |
| `generic-snmp` | system + interfaces |

⚠️ **`verified: False` partout** : aucun de ces OID n'a été relevé sur
un équipement réel dans cet environnement (pas de matériel). La tuile
affiche « non vérifié » ; passer `verified` à `True` dans `profiles.py`
après le premier relevé réel concluant de chaque profil.

## Accès SNMP — jamais de secret ici

Trois façons d'indiquer la communauté, dans le volet de droite :
`credential` = nom d'un accès de genre **snmp** du coffre des accès
d'équipements (#498 ; mot de passe = communauté, révélé par le jeton
interne `CREDENTIALS_INTERNAL_TOKEN`, jamais exposé au navigateur),
`target_id` = cible enregistrée dans snmp-api (communauté chiffrée
là-bas), ou une communauté **ponctuelle** qui part dans la requête et
n'est ni conservée ni journalisée. Seuls le nom de l'accès, l'id de
cible et le port sont mémorisés sur la fiche.

## Zenoss : deux formats (« les deux », décision du 14 sept. 2026)

1. **Script zendmd** `connectors/zenoss_legacy/zendmd_export_devices.py`
   (Python 2.4, lecture seule, communauté omise) : sur le serveur
   Zenoss, `zendmd --script=/chemin/zendmd_export_devices.py` (ou
   `execfile(...)` dans zendmd) → `/tmp/zenoss-devices.json` avec, par
   équipement, classe, constructeur/modèle matériel, OS, série, sysName /
   sysDescr / sysObjectID, lieu, systèmes, groupes, interfaces (MAC,
   IP). C'est le format riche : l'import identifie directement.
2. **CSV** « Export » de la liste des équipements de l'interface Zenoss
   (Device / IP / Device Class / Prod State, séparateur `,` `;` ou
   tabulation, en-têtes tolérants) : la classe sert d'indice de genre et
   de constructeur ; le modèle viendra du relevé SNMP.

L'import passe toujours par une **analyse** (`dry_run`) affichée dans
la tuile (fiches reconnues, classes, identification prévue) avant
confirmation. Rien n'est supprimé : les fiches existantes sont
enrichies (rapprochement MAC → IP → nom).

## Topologie

Les voisins LLDP/CDP sont rapprochés des fiches connues (MAC de châssis,
nom, IP) et la table des adresses MAC d'un switch dit **sur quel port**
chaque équipement connu est appris (`GET /where-is?mac=`, « appris
sur » dans la fiche). `GET /topology` en tire les liens : un par paire
(LLDP prime sur CDP), plus les ports d'accès n'apprenant qu'une ou deux
MAC connues.

## snmp-api : nouvelle route `POST /walk`

Ajoutée pour cette facette : WALK borné d'un sous-arbre numérique
arbitraire (`{host, community | target_id, oid, max_rows?}` →
`{rows: [{oid, value}], truncated}`), GETBULK par 50, arrêt dès que
l'OID sort du préfixe. Au passage, correction d'un vrai bug constaté
contre un simulateur : une cible injoignable faisait remonter une
`TypeError` interne de pysnmp (HTTP 500) au lieu d'un 502 lisible —
les transports sont créés avec `retries=1` et `_run_async` transforme le
cas résiduel en erreur SNMP normale.

## Vérifications

- `python3 -m unittest discover network-equipment/api/tests` : 35 tests
  (OUI, sysDescr de 20 constructeurs/formats, génération, fusion des
  preuves, profils et synthèses, tables ENTITY/LLDP/CDP/FDB, import CSV
  et JSON, API complète avec faux snmp-api / network-agent / coffre :
  imports, identification d'un vieux Catalyst et d'un MikroTik,
  voisins, table MAC, relevé de profil, corrections manuelles, registre
  OUI).
- `snmp/api/test_walk_subtree.py` : 4 tests de la logique du WALK.
- **Bout en bout réel** avec pysnmp 7.1 contre un simulateur SNMP
  (snmpsim, fiche d'un Catalyst 2950 : sysDescr IOS 12.1, ENTITY-MIB,
  CDP, LLDP, BRIDGE-MIB, CPU/mémoire/envmon) : `/walk` de snmp-api,
  identification complète (WS-C2950-24, série, switch, ancien, voisins
  CDP+LLDP rapprochés, table MAC), relevé du profil `cisco-ios` (CPU
  12 %, mémoire 75 %, alarme alimentation), topologie.
- Hub : `hub/tests/networkEquipment.test.mjs` (8 tests), esbuild de la
  vue, aucune couleur en dur, aucun setter sans état.
- Non vérifié : équipements réels (formats sysDescr des constructeurs
  reproduits d'après documentation), rendu navigateur, `/walk-interfaces`
  (IF-MIB compilée) sur le simulateur.

## Variables (`.env`)

`NETWORK_EQUIPMENT_API_PORT` (port hôte optionnel), `NETWORK_EQUIPMENT_DATA_DIR`
(défaut `./network-equipment/data`), `NETWORK_EQUIPMENT_SNMP_TIMEOUT`
(défaut 5 s). Le service lit `CREDENTIALS_INTERNAL_TOKEN` (coffre) et
construit `NETWORK_AGENT_API_URL` depuis `HOST_IP` / `NETWORK_AGENT_HOST_PORT`
comme le hub (network-agent tourne en `network_mode: host`). Hub :
`VITE_NETWORK_EQUIPMENT_API_BASE_URL`, entrée « Équipements réseau » de
la thématique Réseau.

## Suites possibles (BACKLOG 73)

Relevé périodique des profils (automate + historique + alertes), MIB
propriétaires 3Com/Nortel/Netgear/Zyxel, LLDP-MED / téléphones, carte
de topologie graphique (réutiliser le rendu SVG du cycle réseau),
rapprochement avec GLPI, `verified` des profils après premiers relevés
réels.
