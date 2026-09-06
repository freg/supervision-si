# Module SNMP (livraison #212)

Backlog item 13 -- "Nouveau module/tuile SNMP -- découverte et
déploiement automatisé". Demande explicite, trois volets sur une
cible IPv4/MAC :
1. Découverte de ce qui est ouvert sur la cible (scan de
   ports/services).
2. Gestion des paramètres d'accès sécurisés (communautés SNMP ou
   identifiants SNMPv3).
3. Analyse des informations disponibles sur la cible (SNMP
   walk/MIB).

## Portée de cette livraison -- décisions prises pour avancer

La demande d'origine listait explicitement 3 aspects "à trancher
ensemble le moment venu" (portée du "déploiement automatisé", quelles
informations analyser, niveau de scan). Plutôt que d'attendre,
décisions prises pour construire un premier socle utile -- **à
corriger si elles ne conviennent pas** :

1. **SNMPv1/v2c (communauté) SEULEMENT.** SNMPv3 (identifiants
   chiffrés, USM) ajoute une complexité d'authentification
   significative -- reporté à une étape suivante.
2. **Informations analysées** : groupe "System" (SNMPv2-MIB --
   sysDescr, sysName, sysUpTime, sysContact, sysLocation) et table
   des interfaces (IF-MIB -- ifDescr, ifOperStatus, ifSpeed) -- les
   deux MIB les plus universellement supportées.
3. **PAS de scan de ports/services** (volet 1 de la demande) --
   seulement l'accès SNMP lui-même, une fois qu'on sait DÉJÀ qu'une
   cible y répond. La découverte de ce qui est ouvert sur une cible
   est un chantier à part, plus proche d'un scanner réseau général.
4. **PAS de "déploiement automatisé"** -- terme resté ambigu
   (déployer QUOI ? sur la cible elle-même, ou une configuration
   locale ?) -- rien construit sur ce point, explicitement laissé de
   côté plutôt que deviné.

## Bibliothèque retenue

`pysnmp`, fork `lextudio/pysnmp` -- vérifié ACTIF avant de le
choisir : l'original `etingof/pysnmp` est à l'abandon depuis 2022
(décès du mainteneur). Version `7.1.21` confirmée réellement publiée
par deux sources indépendantes (Cloudsmith, Tessl) avant d'être
fixée dans `requirements.txt`.

## API

- `POST /query` -- `{"host", "community", "port"?, "timeout"?}` OU
  `{"target_id", "port"?, "timeout"?}` (cible enregistrée, #213) ->
  informations "System" (SNMPv2-MIB).
- `POST /walk-interfaces` -- même corps -> table des interfaces
  (IF-MIB), `ifOperStatus` déjà traduit en texte (RFC 2863 : up,
  down, testing, unknown, dormant, notPresent, lowerLayerDown).
- `POST /traffic-rate` -- même corps + `sample_interval`? (secondes
  entre deux relevés, 1-60, défaut 5) -- débit RÉEL par interface
  (octets/s entrant et sortant), livraison #384, backlog item 49
  reformulé ("il s'agit d'analyser le trafic"). Calculé par
  DIFFÉRENCE entre deux relevés des compteurs 64 bits IF-MIB
  (`ifHCInOctets`/`ifHCOutOctets`, RFC 2863/3273 -- préférés aux
  compteurs 32 bits historiques pour éviter un rebouclage sur un
  lien gigabit+) espacés de `sample_interval` secondes -- cette
  route reste BLOQUANTE pendant toute la durée du prélèvement,
  nettement plus lente que `/query`/`/walk-interfaces` par
  conception (deux relevés espacés, pas un seul GET). Rebouclage de
  compteur détecté (delta négatif) -- interface OMISE plutôt qu'un
  débit négatif absurde, jamais rencontré en pratique sur un
  compteur 64 bits à l'échelle d'un seul `sample_interval`, vérifié
  quand même par prudence. Interface apparue/disparue entre les deux
  relevés -- également omise (liste d'interfaces supposée STABLE sur
  quelques secondes, jamais garantie).

## Interface hub (livraison #227)

Onglet "SNMP" dans le hub (`hub/src/SnmpView.jsx` +
`snmpClient.js`) -- gestion des cibles enregistrées (créer/
supprimer), interrogation (informations système ou table des
interfaces) sur une cible enregistrée OU un host+communauté saisi
directement. Câblé dans la passerelle (`tls-proxy/render_nginx_conf.py`,
route `/api/snmp/`) et `docker-compose.yml`
(`VITE_SNMP_API_BASE_URL`).

**Vérifié réellement** : structure JSX revérifiée, logique de
construction des paramètres de requête et de validation du
formulaire testée en isolation, non-régression du générateur de
configuration nginx confirmée après ajout de la route. **Non
vérifié** : rendu visuel réel dans un navigateur (aucun ici) --
hérite par ailleurs de la réserve déjà connue du backend (#212) :
jamais testé contre un vrai équipement SNMP.

## Cibles SNMP enregistrées (livraison #213)

Volet 2 de la demande d'origine ("gestion des paramètres d'accès
sécurisés"). Une cible = hôte+port+communauté NOMMÉ et réutilisable,
sans ressaisir la communauté à chaque interrogation -- `/query`/
`/walk-interfaces` acceptent toujours `host`+`community` en direct
pour un usage ponctuel (comportement de #212 inchangé).

- **Stockage** : `credential_crypto.py`, même motif que
  `ssh-tunnels/api/credential_crypto.py` (#210) -- enveloppe
  `shared/secret_crypto.py` (#202-206), communauté JAMAIS stockée en
  clair. `SNMP_CRED_PASSPHRASE`/`SNMP_CRED_SALT` fournis EN CONTINU à
  ce conteneur (pas une ressaisie ponctuelle au déploiement) -- une
  cible peut être interrogée bien après le lancement.
- **API** : `GET /targets`, `POST /targets`
  (`{"label", "host", "port"?, "community"}`), `DELETE
  /targets/<id>`. `community_encrypted` JAMAIS exposé via l'API
  (même défense en profondeur que `password_encrypted` côté
  ssh-tunnels-api).

**Vérifié réellement** : CRUD testé (création, liste, lecture,
suppression, suppression d'une cible déjà supprimée -> `False`
propre). Bout en bout via l'app réelle : `/query` avec `target_id`
fonctionne, et surtout -- vérifié explicitement que la VRAIE
communauté déchiffrée (pas un jeton, pas une valeur factice) atteint
bien l'appel `pysnmp` sous-jacent. Non-régression du mode direct
(`host`+`community`) reconfirmée après ces changements.

## ⚠️ Jamais testé contre un vrai équipement SNMP

`pysnmp` n'est pas installable dans cet environnement de
développement (réseau restreint, comme `sshpass`/certains autres
paquets déjà rencontrés dans ce projet). Tout le code (`snmp_client.py`)
est écrit à partir de la documentation OFFICIELLE
(docs.lextudio.com/pysnmp/v7.1) -- exemples vérifiés un par un avant
d'écrire ce module, jamais improvisés ni copiés d'une version
obsolète de la bibliothèque.

**Vérifié réellement** : la logique d'ENVELOPPE (formatage des
résultats, traduction des erreurs, traduction des codes de statut
d'interface) testée contre une SIMULATION FIDÈLE de l'API réelle de
`pysnmp` (reconstruite d'après les exemples exacts de la
documentation officielle -- mêmes noms de fonctions, mêmes formes de
retour `(errorIndication, errorStatus, errorIndex, varBinds)`) --
succès, erreur réseau (errorIndication), erreur SNMP (errorStatus),
walk multi-lignes avec détection de fin de MIB, traduction
ifOperStatus. Route Flask testée de bout en bout contre cette même
simulation. **PAS vérifié** : l'appel réseau réel lui-même, ni la
compatibilité avec un équipement SNMP réel précis -- à confirmer en
priorité au premier usage réel, en commençant par `POST /query` sur
un équipement déjà connu pour répondre au SNMP (jamais un nouvel
équipement non testé en premier).

**`/traffic-rate` (livraison #384)** : le calcul de débit lui-même
(appariement par interface, delta, détection de rebouclage, valeur
non numérique) testé en isolation avec 4 scénarios -- correspond
ligne à ligne au code réel, jamais une copie approximative. Un VRAI
bug trouvé et corrigé en testant la route : `sample_interval=0`
était interprété comme "non fourni" à cause de l'évaluation Python
`0 or 5` (0 est faux), retombant silencieusement sur la valeur par
défaut au lieu d'être rejeté par la vérification de bornes -- corrigé
en distinguant explicitement l'absence de la valeur (`None`) de zéro.
Route testée avec `snmp_client.get_interface_traffic_rate` mocké
(bornes 1-60 respectées, valeur par défaut, transmission correcte).
**PAS vérifié**, comme le reste de ce module : le prélèvement réel
des compteurs 64 bits contre un vrai équipement.

## Pas encore fait

- SNMPv3 (identifiants chiffrés).
- Scan de ports/services (volet 1 de la demande d'origine).
- "Déploiement automatisé" (portée jamais clarifiée).

## Import vers GLPI (livraison #232)

Backlog -- "remplir GLPI plus ou moins automatiquement... nos futurs
outils d'exploration et les extractions de Nebula". Complète le pont
Nebula→GLPI (#208) avec un pont SNMP→GLPI équivalent.

Nouveau `glpi/api/snmp_import.py` (même motif que
`nebula_import.py`) -- interroge chaque cible SNMP enregistrée
(`GET /targets` + `POST /query` par cible, appels
CONTENEUR-À-CONTENEUR vers `snmp-api`) et crée/complète une entrée
GLPI `NetworkEquipment` par cible joignable. `sysName` -> nom (repli
sur le label de la cible si vide), `sysLocation` -> Location GLPI
(dropdown, comme le `site` Nebula), hôte (IP) -> `otherserial` (MÊME
champ que Nebula pour la même raison de dédoublonnage -- MAC non
disponible depuis le groupe System interrogé ici). Route
`POST /import/snmp-targets` (`dry_run` par défaut, comme tous les
imports GLPI de ce projet). Bouton "Import vers GLPI" ajouté dans
`SnmpView.jsx`.

**Vérifié réellement** : logique testée en isolation (dry-run sans
appel GLPI, dédoublonnage par hôte, résolution de Location). **Un
vrai bug trouvé et corrigé en testant** : un retour inattendu (`None`)
de la fonction d'interrogation SNMP faisait planter TOUT l'import --
corrigé pour traiter ce cas comme une simple erreur sur CETTE cible,
jamais bloquant pour les autres. Route testée de bout en bout
(dry-run, confirmation réelle, échec de `snmp-api` propagé
proprement en 502).

**⚠️ Mêmes réserves que les deux ponts existants** : MAC non
disponible depuis le groupe System (walk des interfaces non exploité
ici, resterait à faire pour un mapping plus riche), champ
`otherserial` pour l'hôte pas vérifié contre un vrai GLPI (même
réserve que Nebula), et bien sûr jamais testé contre un vrai
équipement SNMP ni un vrai GLPI.

## Correctif : premier déploiement réel, deux vrais bugs (livraison #252)

La personne a partagé de vrais logs `gunicorn` de quatre services
crashés au démarrage. Pour `snmp-api` :
`ImportError: cannot import name 'ContextData' from
'pysnmp.hlapi.v1arch.asyncio'`.

Confirmé par recherche : `ContextData` n'existe QUE dans `v3arch`
(SNMPv3, système de contextes/moteurs) -- absent de `v1arch`
(SNMPv1/v2c, ce module), qui n'en avait d'ailleurs jamais eu besoin
dans les appels réels `get_cmd`/`bulk_cmd` de `snmp_client.py`
(jamais passé en argument). Un import résiduel, jamais utilisé,
faisait planter tout le module au chargement -- corrigé en le
retirant, aucune autre modification nécessaire (le code appelant
était déjà correct).

Corrige aussi l'affirmation trop optimiste du module ("exemples
vérifiés un par un") -- cet import précis avait échappé à cette
vérification, corrigé honnêtement dans la docstring plutôt que
laissé tel quel.

## Branchement rights-api (livraison #313)

Suite de l'item 38 du backlog. SCOPE VOLONTAIREMENT ÉTROIT : gardé
UNIQUEMENT sur `create_target`/`delete_target` (gestion des cibles
enregistrées) -- jamais sur `/query` ni `/walk-interfaces`.

Raison de cette limite, assumée explicitement : ces deux routes
acceptent SOIT une communauté fournie à la volée par l'appelant
(self-service, aucun gain à gater -- il fournit son propre
identifiant), SOIT un `target_id` enregistré dont la communauté
CHIFFRÉE est utilisée côté serveur sans jamais être révélée à
l'appelant -- ce second cas mériterait une garde CONDITIONNELLE
(seulement si `target_id` est utilisé), plus fine qu'un simple gate
en tête de route. Pas construite ici, faute de temps pour la bâtir
ET la tester correctement dans cette même session -- noté
explicitement comme limite connue, à reprendre séparément plutôt
que bâclée.

OPT-IN via `SNMP_RIGHTS_API_URL`, vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
`/query`/`/walk-interfaces` confirmés TOUJOURS libres même avec
`rights-api` actif et refusant, FAIL CLOSED sur les deux routes
gardées si `rights-api` injoignable, 403 confirmé pour un groupe non
autorisé. Testé avec des stubs minimaux pour `pysnmp`/
`credential_crypto` (non installables dans cet environnement de
développement, même limite déjà documentée) -- confirme la logique
de la garde, jamais l'appel SNMP réel lui-même.
