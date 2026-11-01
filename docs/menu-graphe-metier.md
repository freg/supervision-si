# Menu du hub en graphe métier déployé — analyse (24 sept. 2026)

Demande : « un arbre qui prenne la logique métier et les dépendances ; un
nœud / tuile peut être à plusieurs endroits : c'est un graphe déployé ».
Thèmes proposés : équipements (réseau, hôtes, sondes matérielles, écrans
intelligents…), services, droits, supervision / états, Cortex / IA.

## 1. Ce que le hub sait déjà faire, et ce qui manque

L'arbre de disposition (#516, `hubTree.js`) est déjà un **graphe déployé** au
sens technique : ses nœuds sont des *références* vers un catalogue de
feuilles (vue, front, action) et une même feuille peut être référencée sous
plusieurs groupes. Les thématiques actuelles (#457) sont des groupes de
premier niveau : Supervision, Réseau, Données, Documents, Sécurité,
ProjeQtOr, Paramètres. Ce qui manque n'est pas la structure, c'est la
**sémantique** : les arêtes n'ont pas de type (contenance seulement), le
regroupement est *par outil* (« ce que le hub sait faire ») et non *par
métier* (« ce que la personne cherche à faire »), et rien n'exploite les
dépendances réelles déjà connues du hub : `depends_on` du compose (tour de
contrôle), relations Cortex (entités, incidents, causes), agents ↔ hôtes ↔
sondes, registres d'équipements ↔ accès du coffre ↔ notifications.

## 2. Métiers et compétences (qui vient chercher quoi)

| Métier / rôle | Compétence dominante | Entrées naturelles dans le hub |
|---|---|---|
| Responsable de site client (non initié) | comprendre l'état, savoir qui appeler | Aujourd'hui, état des services, Nebula@site, suivi de demande |
| Technicien réseau | topologie, VLAN, ports, Wi-Fi, routeurs | Nebula, MikroTik, Cisco, exploration, fusion IP/MAC, sondes |
| Administrateur systèmes | hôtes, VM, conteneurs, sauvegardes, mises à jour | Agents hôtes, Proxmox, tour de contrôle, sauvegardes |
| Sécurité / accès | bastion, coffre, droits, comptes, journal | Bastion, accès d'équipements, droits, comptes, notifications |
| Support / SAV | tickets, demandes, contacts, historique | Portail tickets, demandes, GLPI, ENT |
| Données / référentiels | bases, schémas, imports, catalogues | Bases externes, DBA, classification, GED |
| Exploitation / astreinte | alertes, incidents corrélés, actions rapides | Cortex, vigilance, notifications, journal des jobs |
| Direction / AMOA | synthèse, coûts, projets | Infos synthèse SI, ProjeQtOr, rapports |
| IA interne | assistant, extraction, priorisation, apprentissage des règles | Assistant, règles Nebula, Cortex hypothèses |

Un même utilisateur cumule souvent deux ou trois de ces rôles : le menu
doit donc offrir **plusieurs chemins vers la même tuile**, pas un rangement
unique.

## 3. Modèle proposé : un graphe typé, des vues déployées

Nœuds (trois natures) :

- **outils** : les tuiles et actions existantes (catalogue actuel) ;
- **objets métier** : équipement (routeur, switch, borne, hôte, VM,
  conteneur, sonde, onduleur, écran), service (API, front, base, service
  visible d'Internet), site, accès, groupe, personne, ticket ;
- **états** : lampe (vert / orange / rouge), incident, alerte, job en
  cours — issus de la tour, de Cortex, des sondes.

Arêtes typées (le sens compte) :

| type | exemple |
|---|---|
| `dépend-de` | hub → tls-proxy → keycloak ; tuile MikroTik → mikrotik-api → coffre |
| `supervise` | agent i9 → hôte ; sonde wifi-probe → SSID ; service-watch → entrée DNS |
| `configure` | tour → registre Cisco ; Nebula → bornes |
| `sécurise` | bastion → PVE campus ; coffre → routeur ; droits → tuile |
| `alimente` | notifications ← MikroTik / Cisco / tour ; Cortex ← agents / sondes |
| `explique` | incident Cortex → cause racine → équipement |
| `déclenche` | action NAT → notification → groupe → adresses |

Les thèmes demandés deviennent les **cinq racines** du déploiement, chacune
ouvrant le même graphe par une porte différente :

1. **Équipements** — par type (réseau : routeurs, switchs, bornes ; hôtes :
   serveurs, VM, conteneurs, postes ; sondes matérielles : Raspberry,
   onduleurs, écrans intelligents / allée immersive) puis par site ; sous
   chaque équipement : sa tuile de pilotage, ses accès, ses sondes, son
   état, ses tickets, ses notifications.
2. **Services** — les conteneurs du hub (feu tricolore), les entrées
   visibles d'Internet, les services métier des clients (Nebula, GED…) ; sous
   chaque service : dépendances, état, jobs, journal, qui le supervise.
3. **Droits** — personnes et groupes Keycloak, matrice tuiles × groupes,
   accès d'équipements, jetons de consommateurs ; sous chaque groupe : ce
   qu'il voit, ce qu'il reçoit (notifications), ce qu'il peut faire.
4. **Supervision / états** — Aujourd'hui, incidents Cortex, alertes, feu
   tricolore, sondes ; sous chaque état : l'objet concerné (retour vers
   Équipements ou Services), l'action proposée, la notification partie.
5. **Cortex / IA** — assistant, règles apprises, hypothèses, priorisation,
   décisions typées locales ; sous chaque décision : les objets qu'elle
   touche.

Une tuile apparaît donc autant de fois qu'elle a d'arêtes entrantes depuis
les racines : « Routeurs MikroTik » sous Équipements → réseau → routeurs,
sous Sécurité → accès → coffre → routeur-bureau (utilisé par), sous
Supervision → états → routeur-mikrotik rouge, sous Notifications →
mikrotik.nat.add. C'est le graphe déployé demandé, sans dupliquer la tuile.

## 4. Rendu : ce que verrait l'utilisateur

- **Menu arborescent déployé** : les cinq racines en tête ; chaque nœud se
  déplie en ses arêtes sortantes groupées par type (« dépend de », « est
  supervisé par »…), avec la lampe d'état à côté de chaque objet quand elle
  existe. Une feuille déjà ouverte ailleurs est marquée « aussi sous … »
  (fil d'Ariane multiple), cliquable.
- **Filtre début-de-mot** (règle d'ergonomie) sur tout le graphe : « nat »
  fait remonter la règle NAT, l'action mikrotik.nat.add, le routeur.
- **Vue graphe** (existante : arbre radial, Cortex, Nebula topo) pour
  visualiser un voisinage ; le menu en reste la forme linéaire.
- Compatible avec l'arbre personnalisable #516 : le graphe métier est une
  *source* de plus pour l'arbre (racines générées), l'utilisateur garde ses
  regroupements manuels.

## 5. D'où viennent les arêtes (rien à saisir à la main au départ)

| source | arêtes |
|---|---|
| catalogue des tuiles (hubThemes) | outil → thème d'origine |
| docker-compose (`depends_on`, montages) via la tour | service `dépend-de` service |
| registres Cisco / MikroTik / Nebula / Proxmox | équipement `sécurisé-par` accès ; équipement `piloté-par` tuile |
| agents et sondes (si-agent-api, netprobe) | sonde `supervise` hôte / SSID / équipement |
| Cortex (entités, relations, incidents) | incident `explique` équipement ; cause racine |
| notifications (actions, affectations) | action `déclenche` groupe → adresses |
| droits (matrice #559) | groupe `voit` tuile |
| service-watch | entrée `expose` service |

Le graphe est **calculé** à partir de ces sources (une API légère
`graph-api` ou une fonction du hub qui agrège les `/health` et inventaires
existants), mis en cache, et enrichi ensuite à la main (arêtes déclarées,
libellés métier) sans jamais casser le calcul automatique.

## 6. Étapes proposées

État : étape 1 livrée (#599, `hub/src/hubBusiness.js`, menu « Vue métier »).

1. **Catalogue typé** (petite livraison) : donner à chaque tuile un ou
   plusieurs *objets métier* et *types d'arêtes* dans `hubThemes.js` ;
   générer les cinq racines comme thématiques alternatives (« Vue métier »
   dans Univers du hub), sans toucher au menu actuel. Mesure : chaque tuile
   est joignable par au moins deux chemins.
2. **Arêtes calculées** : agrégateur (compose, registres, agents, Cortex,
   notifications, droits) → graphe JSON `{nodes, edges}` ; menu déployé
   avec lampes d'état et « aussi sous … ».
3. **Objets métier navigables** : un nœud équipement / service / groupe a
   sa propre page pivot (état, dépendances, accès, tickets, notifications)
   — c'est ce que le responsable de site non initié attend.
4. **Décisions typées locales** (lien avec l'analyse Jev) : Cortex propose
   la racine d'entrée et la prochaine action, avec confiance et seuil de
   validation humaine.

Risques : profondeur (limiter à trois niveaux dépliés, le reste par filtre
ou page pivot) ; incohérences entre sources (afficher la provenance de
chaque arête) ; performance (cache 30 s, calcul côté API).
