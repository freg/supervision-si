# glpi

Intégration GLPI (livraison #192, backlog : "évolution d'intégration
GLPI, une tuile et une api pour utiliser l'api glpi et ses données
dans les autres tuiles du hub" -- demande explicite).

## Portée de cette livraison

Le **besoin immédiat** explicite couvrait deux imports (inventaire
Excel + un site Zyxel Nebula). **Seul l'import Excel est construit
ici** -- l'import Nebula nécessite sa propre recherche d'API,
traité comme un chantier séparé (voir BACKLOG.md).

La vision plus large ("une tuile et une api... dans les autres
tuiles du hub") n'est **pas commencée** -- ce module en est le tout
début : la connexion GLPI elle-même et l'import, rien de plus.
L'exposition des données GLPI aux autres tuiles viendra dans une
étape suivante, une fois cet import validé en conditions réelles.

## ⚠️ Jamais testé contre un vrai GLPI

Aucun accès réseau externe dans cet environnement de développement.
Toute la logique HTTP (`glpi_client.py`) est construite à partir de
la documentation OFFICIELLE de l'API historique GLPI (`apirest.php`,
https://help.glpi-project.org/documentation/modules/configuration/
general/api/api, consultée le jour de cette livraison) -- mais reste
**à confirmer contre le GLPI réel de la personne**. Commencer
TOUJOURS par `GET /test-connection`, puis un import en **dry-run**
(`dry_run=true`, valeur par défaut), avant tout import réel.

## Deux API GLPI, un choix délibéré

GLPI 11 propose deux API : l'**historique** (`apirest.php`, éprouvée,
bien documentée) et une **nouvelle API v2**, encore "work in
progress" pour les types d'objets qui nous intéressent ici (actifs)
au moment de cette livraison (confirmé via la doc officielle : "many
of the itemtypes have schemas/endpoints now as of 11.0.5 and many
more get added each version" -- pas encore TOUS). Choix : l'API
historique, plus fiable pour un import maintenant -- à reconsidérer
si la v2 mûrit.

## Architecture

- `glpi_client.py` -- client bas niveau (session, recherche, CRUD,
  résolution de dropdown). Authentification par SESSION
  (`initSession`/`Session-Token`), `session_write=true` demandé dès
  l'ouverture (un import a besoin d'écriture, jamais découvert en
  échec plus tard). Traitement d'erreur DÉFENSIF
  (`_raise_with_detail`) -- le format exact des réponses d'erreur de
  GLPI n'est pas garanti à 100% sans un essai réel, accepte plusieurs
  formes plausibles et inclut TOUJOURS le corps brut en repli.
- `excel_import.py` -- mapping Excel -> GLPI et logique d'import.
- `app.py` -- service Flask (`GET /test-connection`, `POST
  /import/excel`, `GET /logs`, `GET /health`).
- `cli_import.py` -- alternative en ligne de commande, sans passer
  par le stack Docker (utile si la machine qui l'exécute a un accès
  réseau à GLPI que le stack supervision-si n'aurait pas forcément).

## Mapping Excel -> GLPI (import inventaire)

Le fichier fourni (`Inventaire.xlsx`, feuille "Devices", 220 lignes
au moment de cette livraison) a des colonnes qui ne correspondent
pas toutes à des champs GLPI standards -- choix faits, à ajuster
si besoin :

| Colonne Excel | Destination GLPI |
|---|---|
| `Type` | itemtype (Computer/Peripheral/Monitor/Printer) -- voir `TYPE_MAPPING` dans `excel_import.py`, GLPI n'a pas de type "Tablette"/"Casque VR" dédié dans son schéma classique, `Peripheral` sert de catégorie générique |
| `Nom` | `name` |
| `Numero de série` | `serial` (aussi utilisé pour le DÉDOUBLONNAGE -- voir plus bas) |
| `Modèle` | dropdown modèle (`ComputerModel`/`PeripheralModel`/`MonitorModel`/`PrinterModel` selon l'itemtype), créé s'il n'existe pas encore |
| `Lab` | dropdown `Location`, créé s'il n'existe pas encore (normalisé d'abord -- voir plus bas) |
| `Compte`, `Classe`, `Sous-classe`, `Localisation`, `Stockage`, `Profil`, `Commentaire` | regroupés dans `comment` (pas d'équivalent structurel direct dans GLPI pour ces colonnes) |
| `Adresse MAC`, `Profil ServeurCampusAlpha`, `Date de mise en service` | **PAS ENCORE importés** -- voir "Pas encore fait" plus bas |

## Dédoublonnage

Avant chaque création (import réel seulement, jamais en dry-run),
recherche par `serial` via `GET /:itemtype/?searchText[serial]=...`
-- si un actif avec ce numéro de série existe déjà, la ligne est
SAUTÉE (`skipped_existing`), jamais un doublon. Un ré-import du même
fichier plus tard ne recrée donc rien -- condition nécessaire pour
pouvoir relancer cet import sans risque si le fichier est mis à
jour.

**Choix délibéré** : recherche par NOM DE CHAMP réel (`searchText`),
jamais par un id de "searchoption" numérique (`criteria[0][field]`)
-- ce dernier varie selon l'itemtype et je n'ai aucun moyen de le
confirmer sans un vrai GLPI sous la main. Même raisonnement pour
`get_or_create_dropdown`.

## Problèmes de qualité de données RÉELLEMENT trouvés dans le fichier fourni

- **12 lignes "Borne-001" à "Borne-012"** : la colonne "Nom" est
  VIDE, l'identifiant a été saisi dans la colonne "Type" à la place
  (confirmé en inspectant le fichier). Traité : utilisé comme nom,
  type GLPI par défaut `Peripheral`, SIGNALÉ dans le résumé d'import
  pour vérification humaine.
- **"Bras Niryo" / "Bras NIryo"** (casse différente) : même
  situation (Nom vide, valeur dans Type).
- **"Amphi Immersif" / "Amphi immersif"** (casse), **"Mediateurs" /
  "Médiateurs"** (accent) dans la colonne "Lab" : normalisés vers
  UNE seule forme avant de créer/chercher la localisation GLPI, pour
  ne jamais créer deux entrées différentes pour le même lieu.

Le résumé d'import (`warnings`) liste chaque cas rencontré -- jamais
un traitement silencieux.

## Pas encore fait (pistes pour une prochaine étape)

- **Adresses MAC multiples** (48 lignes du fichier fourni en ont
  plusieurs, séparées par virgule) -- GLPI modélise ça via des
  sous-objets `NetworkPort`, un appel API supplémentaire PAR adresse
  MAC PAR actif -- complexité volontairement reportée pour garder
  cette première livraison ciblée sur l'essentiel.
- **Date de mise en service** -- GLPI la stocke via un sous-objet
  `Infocom` (infos financières/administratives), une création
  séparée après l'actif -- pas encore fait, même raison.
- **"Tuile + API"** (vision plus large du backlog) -- exposer les
  données GLPI aux autres tuiles du hub -- pas commencé.

## Import Nebula -> GLPI (livraison #208)

Backlog item 16 -- nouveau module `nebula_import.py` : importe les
appareils Nebula DÉJÀ importés côté `nebula-api` (#200, via
`GET /imported/devices` -- indifférent qu'ils viennent du CSV du
portail web ou de l'API officielle) vers GLPI. Route
`POST /import/nebula-devices` (`dry_run` par défaut) -- appel
CONTENEUR-À-CONTENEUR vers `nebula-api` (`NEBULA_API_INTERNAL_URL`,
défaut `http://nebula-api:5000`), jamais vers l'API Nebula publique
directement.

**Types RÉELS rencontrés** dans les fichiers fournis par la personne
(#200) : "Access point", "Switch", "Firewall" -- tous mappés vers
`NetworkEquipment`, le type GLPI dédié au matériel réseau.

**⚠️ Point vérifié PUIS corrigé avant même de tester** : l'adresse
MAC n'est PAS une colonne directe de `glpi_networkequipments` --
confirmé en recherchant (elle vit normalement dans le sous-objet
`NetworkPort`, jamais créé ici par choix -- même raisonnement que les
adresses MAC multiples ci-dessus). Utilisée à la place : `otherserial`
(champ texte libre générique GLPI) pour le dédoublonnage -- plus sûr
qu'un champ `mac` direct qui n'existe probablement pas, mais LUI-MÊME
PAS VÉRIFIÉ CONTRE UN VRAI GLPI -- **à confirmer en priorité au
premier import réel**.

**Vérifié réellement** : mapping testé (3 vrais types Nebula, type
inconnu correctement signalé jamais silencieux), MAC dans
`otherserial` confirmé, cache de dropdown Location efficace,
dédoublonnage et dry-run testés. Route testée de bout en bout avec
`nebula-api` simulé -- succès, `nebula-api` injoignable (502, message
clair), erreur HTTP de `nebula-api` propagée proprement.

## Utilisation

**1. Configurer** (`.env`, voir `.env.example`) : `GLPI_BASE_URL`
(vers `apirest.php`, PAS `/api/` sauf réécriture d'URL confirmée
côté serveur GLPI), `GLPI_APP_TOKEN` (optionnel), et UN SEUL des
deux modes d'authentification : `GLPI_USER_TOKEN` (recommandé) OU
`GLPI_LOGIN`+`GLPI_PASSWORD`.

**2. Tester la connexion** : `GET /api/glpi/test-connection` (via le
hub/tls-proxy une fois déployé) -- doit répondre `200`.

**3. Dry-run** : envoyer le fichier Excel en `multipart/form-data`
(champ `file`) à `POST /api/glpi/import/excel` (dry-run par défaut)
-- ou en ligne de commande :
```bash
python3 cli_import.py Inventaire.xlsx --base-url https://glpi.exemple.fr/apirest.php --user-token XXXX
```
**Relire le résumé** (créations prévues, avertissements) avant de
passer à l'étape suivante.

**4. Import réel** : `POST /api/glpi/import/excel?dry_run=false`, ou
`cli_import.py ... --live`.

## Vérifié réellement

`glpi_client.py` testé via mock des réponses HTTP -- **reconstituées
fidèlement d'après les exemples de la documentation officielle**
(format exact de `initSession`, `add_item` (`{"id": 15}`),
`add_items` en lot avec échec partiel (`id: False` sur échec
individuel, conforme à la doc), `search_items`, `get_or_create_dropdown`
existant/absent). Bug réel trouvé et corrigé en testant :
`kill_session` ne rattrapait que `requests.RequestException`, pas une
erreur générique, contrairement à l'intention documentée ("jamais
bloquant, peu importe la cause").

`excel_import.py` : logique de normalisation/résolution de type
testée unitairement, PUIS un dry-run RÉEL contre le VRAI fichier
fourni (220 lignes, 0 erreur, 14 avertissements -- exactement les 14
cas de qualité de données identifiés en inspectant le fichier).
Orchestration complète testée avec un client GLPI entièrement simulé
sur un extrait du vrai fichier -- cache de dropdown confirmé efficace
(un seul appel pour plusieurs lignes partageant le même modèle).

`app.py` testé de bout en bout via de VRAIES requêtes HTTP
multipart, y compris l'upload du VRAI fichier fourni (confirmé :
220 créations simulées, 14 avertissements, cohérent avec les tests
plus bas niveau).

**Non vérifié dans cet environnement** : tout ce qui nécessite un
VRAI GLPI (connexion, création réelle, résolution de dropdown
réelle, format exact des réponses d'erreur du serveur) -- à tester
en PRIORITÉ, en dry-run d'abord, une fois déployé.

## Résumé d'inventaire en lecture seule (livraison #231)

Backlog item 21 -- interface pour ce qui est RAISONNABLEMENT
construisible sans présumer de faits réels sur l'infrastructure de la
personne (combien de segments réseau, lesquels sont isolés -- voir
`docs/preparation-glpi-inventory.docx`, #222, pour ces questions
toujours ouvertes).

**Décision de portée** : nouvelle route `GET /inventory-summary`
(lecture seule -- `Computer` + `NetworkEquipment` déjà connus de
GLPI, comptage + échantillon de 20) et `hub/src/GlpiInventoryView.jsx`
correspondante. **PAS** un formulaire de configuration de tâche de
découverte/inventaire -- l'itemtype exact de l'API REST GLPI pour
l'inventaire natif (GLPI 10+ a remplacé l'ancien mécanisme
FusionInventory) n'a jamais été vérifié dans ce projet ; plutôt que
présenter un formulaire non vérifié qui pourrait sembler fonctionnel
sans l'être dans une démonstration, cette vue reste strictement dans
les limites de ce qui est réellement construit et testé.

**Vérifié réellement** : route testée avec des données simulées
(comptage exact, échantillon limité à 20, cas plafonné à 999+ items
-- `capped: true`, honnête plutôt qu'un faux total approximé), échec
de connexion propagé proprement (502). Structure JSX revérifiée.

**Non vérifié** : contre un vrai GLPI (même réserve que le reste de
ce module, réseau restreint dans cet environnement de développement).

## Correctif : fichier manquant au déploiement (livraison #252)

`snmp_import.py` (le pont SNMP→GLPI, #232) était importé par
`app.py` mais jamais copié par le `Dockerfile` -- oubli non détecté
jusqu'ici faute de redéploiement récent de ce service précis (trouvé
par une vérification systématique de tous les `Dockerfile` du
projet, après trois cas similaires signalés par la personne sur
d'autres services). Corrigé. `cli_import.py` (script CLI autonome,
jamais importé par `app.py`) reste volontairement absent -- ce n'est
pas un oubli, il n'est pas nécessaire au service web.

## Export vers GLPI des appareils découverts par network-agent (livraison #264)

Demandé explicitement, dans le sens INVERSE de l'import GLPI→ce
projet envisagé un temps : "je veux exporter vers glpi tout ce qu'on
va découvrir par l'exploration réseau" -- confirmé pertinent après
que la personne ait précisé que l'inventaire GLPI actuel est "presque
vide", donc rien d'utile à en importer pour l'instant.

**Contexte donné explicitement, déterminant pour la conception** :
"L'important pour mon client c'est [Alpha] (nebula) mais nebula ne
connait pas directement les 200 clients plus ou moins mobiles actifs
dans son réseau, à nous de les identifier et de les traiter dans
glpi". Puis précision cruciale après un premier test : "attention ce
que le dns te donne qui match le motif dhcp123 ce sont les clients
wifi du lan de ma structure pas le lan de alpha, tu identifiera
alpha avec des adresses 172...".

**Deux réseaux DISTINCTS peuvent être surveillés par `network-agent`**
(un seul agent, plusieurs segments possibles, voir #233) -- celui de
la structure de la personne (192.168.x.x, avec ses propres clients
WiFi `dhcpNNN`) et celui d'un client comme Alpha (172.x.x.x). D'où
`segment_id` en paramètre OPTIONNEL MAIS FORTEMENT RECOMMANDÉ de la
nouvelle route -- cible UN SEUL segment, jamais un mélange des deux
réseaux par défaut.

Nouveau module `network_agent_import.py`, même esprit que
`nebula_import.py` (#208) -- dédoublonnage par adresse MAC
(`otherserial`, même réserve sur ce champ que pour Nebula, non
vérifié contre un vrai GLPI), tous les appareils mappés vers
`NetworkEquipment` (pas de type plus fin déduit du nom d'hôte dans
cette première tranche). Nouvelle route
`POST /import/network-agent-devices` -- `dry_run` (défaut `true`,
même garde que les autres imports), `segment_id` (voir ci-dessus),
`exclude_dynamic` (défaut `false` -- **volontairement**, côté
Alpha les clients DHCP dynamiques sont justement les 200 clients
mobiles que Nebula ne voit pas lui-même, la donnée la plus utile à
remonter, jamais du bruit à filtrer par défaut ; l'option existe pour
qui voudrait explicitement les exclure ailleurs, croisée avec
`classifier-api` en best-effort si activée).

**Vérifié réellement** : testé avec un scénario reproduisant
EXACTEMENT la clarification reçue -- deux segments simulés (un
192.168.x.x avec un client `dhcp139`, un 172.x.x.x avec deux
"clients mobiles Alpha") -- confirmé que `segment_id=<segment
Alpha>` exporte SEULEMENT ses 2 appareils, jamais celui de la
structure de la personne ; et inversement pour l'autre segment.
Dédoublonnage par MAC testé (réimport identique -> sauté proprement).
Exclusion optionnelle par classification testée. Cas d'échec testés
(`network-agent` injoignable, URL non configurée) -- toujours un 502
propre, jamais un crash. Dockerfile vérifié avec le script de
contrôle systématique développé en #252 -- un fichier RÉELLEMENT
manquant trouvé et corrigé immédiatement (`network_agent_import.py`
lui-même, oublié une première fois avant la vérification).
Non-régression complète de `glpi-api` reconfirmée.

**Non vérifié** : contre un vrai GLPI (même réserve que tout le
reste de ce module), et contre un vrai déploiement `network-agent`
sur le réseau 172.x.x.x de Alpha (jamais testé dans cet
environnement, aucun accès à ce réseau).

## Audit et corrections majeures : sélection multiple, clients Nebula, annuler/supprimer (livraison #269)

Suite à quatre questions explicites de la personne, posées comme un
audit ("questions à traiter si la réponse est non ou pas
complètement") :

1. **"memory a t'il une interface de consultation ?"** -- Oui, déjà
   complète (`MemoryView.jsx`, #259). Rien à faire.
2. **"les données explorateur réseau et import nebula sont t'elles
   prêtes à être exportées vers glpi ?"** -- Le BACKEND l'était
   (#208, #264), mais AUCUNE interface hub ne permettait de les
   déclencher -- seulement des appels API bruts. Corrigé ici.
3. **"à partir des logs de nebula je peux exporter les clients
   connectés... pourra t'on les injecter dans glpi avec une
   interface de sélection multiple ?"** -- Vraie trouvaille en
   creusant : `nebula-api` suit DÉJÀ les clients connectés
   séparément des équipements d'infrastructure (`GET
   /imported/clients`, table `nebula_clients_import`, #200), mais
   RIEN ne les exportait vers GLPI. Nouveau module
   `nebula_clients_import.py` -- type GLPI `Computer` (pas
   `NetworkEquipment`, ces lignes décrivant des appareils
   UTILISATEURS finaux -- présence de `manufacturer`/`os`).
4. **"partout dans les imports/exports y a t'il la possibilité
   d'annuler ou de supprimer en sélectionnant individuellement ?"**
   -- Non, le client GLPI n'avait même pas de méthode de suppression.

### Suppression individuelle -- corbeille GLPI native

`delete_item` ajouté à `glpi_client.py`, **comportement vérifié
contre la documentation officielle GLPI** (plusieurs sources
concordantes, dont le dépôt officiel `glpi-project/glpi`) : SANS
`force_purge` (le défaut), GLPI déplace l'objet dans SA PROPRE
corbeille -- récupérable nativement depuis l'interface GLPI
elle-même, l'équivalent exact d'un "annuler" SANS avoir à construire
un mécanisme de undo maison. Avec `force_purge=true`, suppression
définitive -- jamais le défaut, un choix explicite de l'appelant.

Nouvelles routes `GET /items/<itemtype>` (listing pour parcourir/
sélectionner) et `DELETE /items/<itemtype>/<id>` -- scopées à
`MANAGED_ITEMTYPES` (`Computer`, `NetworkEquipment`), les seuls
types réellement produits par les imports de ce module.

### Sélection multiple -- tous les imports existants étendus

Les quatre modules d'import (`nebula_import`, `nebula_clients_import`,
`network_agent_import`, `snmp_import`) acceptent désormais un filtre
optionnel (`only_macs` pour les trois premiers, `only_ids` pour SNMP
qui identifie ses cibles autrement) -- `None` par défaut, comportement
INCHANGÉ (tout est traité), non-régression vérifiée explicitement.

**Un vrai problème de conception trouvé en construisant l'interface** :
les aperçus (`dry_run=true`) renvoyaient jusqu'ici des CHAÎNES DE
TEXTE formatées (`"[SIMULATION] Computer 'X' -- {...}"`) --
inexploitables pour construire des cases à cocher côté hub. Corrigé
dans les quatre modules : en mode aperçu, `created` contient
désormais des objets structurés (`{key, name, itemtype, detail}`) --
`key` étant la clé naturelle de sélection (MAC ou id de cible SNMP).
**L'import RÉEL (`dry_run=false`) reste inchangé** (chaîne
informative avec l'id GLPI attribué) -- seule la PRÉVISUALISATION a
changé de forme, non-régression vérifiée explicitement sur ce point
précis.

### Interface hub -- reconstruite entièrement

`GlpiInventoryView.jsx` était jusqu'ici un résumé EN LECTURE SEULE
(#231) -- aucun déclenchement d'import, aucune gestion possible.
Reconstruite avec : sélecteur de source (les quatre imports),
prévisualisation avec case à cocher PAR CANDIDAT (tout coché par
défaut), import de la sélection, et une section "Actifs déjà créés"
listant/supprimant individuellement (bouton "🗑 Annuler" par ligne,
confirmation avant action).

**Vérifié réellement** : `delete_item` testé contre les réponses
RÉELLES documentées par GLPI (`[{"16":true,"message":""}]`, item
introuvable, 204 sans corps, erreur HTTP réelle jamais masquée).
Routes `/items/*` testées de bout en bout. Sélection multiple testée
sur les quatre modules, y compris COMBINÉE avec le filtrage par
catégorie déjà existant côté `network_agent_import` (les deux
s'appliquent ensemble). Structuration des aperçus vérifiée sans
casser l'import réel. `glpiClient.js` testé de bout en bout avec un
`fetch` simulé, y compris la distinction `only_macs`/`only_ids`
selon la source. Structure JSX complète revérifiée.

## Correctif : sélection de segment pour l'import network-agent (livraison #270)

Manque trouvé en relisant l'interface tout juste construite en
#269 : le sélecteur de source "Exploration réseau — appareils
découverts" ne permettait pas de choisir un SEGMENT réseau précis --
sans ce choix, l'aperçu/import aurait mélangé TOUS les segments
connus par `network-agent`, y compris potentiellement le réseau de
la structure de la personne ET celui d'un client comme Alpha
(172.x.x.x) -- exactement la confusion déjà signalée et corrigée
côté `architecture-api`/`vigilance-api` (#264, #268).

Corrigé -- `previewImport`/`commitImport` (côté hub) acceptent
désormais un `segment_id` optionnel, transmis à la route déjà
capable de le recevoir (#264). Sélecteur de segment affiché
UNIQUEMENT pour la source "Exploration réseau" (les autres sources
n'ont pas cette notion), peuplé depuis `network-agent-api`
(`GET /sites`, déjà utilisé ailleurs dans le hub). Avertissement
explicite affiché si aucun segment n'est choisi ("tous les segments
seront mélangés").

**Vérifié réellement** : logique de transmission de `segment_id`
testée en isolation (présent dans l'URL quand fourni, absent sinon,
jamais transmis aux sources qui n'en ont pas la notion comme
Nebula). Logique de construction de la liste de segments à plat
testée (site sans segments géré sans exception). Structure JSX
complète revérifiée.

## Branchement rights-api (livraison #294)

Suite au backlog item 38, cinquième service branché après
ssh-tunnels-api (#289), ldap-admin-api (#290), vault-admin-api
(#291), dba-api (#292). Aucune décision explicite préexistante
trouvée dans ce module contraire à ce branchement -- procédé
directement.

**6 routes protégées** : `DELETE /items/<itemtype>/<id>`,
`POST /import/excel`, `POST /import/nebula-devices`,
`POST /import/nebula-clients`, `POST /import/network-agent-devices`,
`POST /import/snmp-targets` -- y compris en mode `dry_run` (gating
au niveau de la ROUTE, pas de l'effet réel, même cohérence que les
services précédents). Les routes de consultation (`GET /items`,
`/inventory-summary`, `/test-connection`) restent ouvertes.

**Cas particulier** : `/import/excel` reçoit un envoi MULTIPART
(fichier), jamais de corps JSON -- `groups` extrait d'un champ de
formulaire ordinaire, même motif que `dba-api/import_mysql_dump`
(#292).

Même motif que les quatre services précédents pour le reste : gating
au niveau du SERVICE ENTIER, FAIL CLOSED, OPT-IN via
`GLPI_RIGHTS_API_URL`.

**Vérifié réellement** : câblage testé sur les 6 routes (refusé) et
sur `delete_item_route` (autorisé -- confirmé que le blocage par les
droits n'intervient plus, la requête atteint bien la logique GLPI
réelle ensuite). Non-régression reconfirmée.

**Incident évité en cours de route** : une édition mal formée a
d'abord tronqué la docstring d'`import_nebula_devices_route` (une
partie du texte perdue) -- repéré en relisant le résultat
immédiatement après chaque édition (jamais supposé correct sans
vérifier), corrigé avant de continuer.
