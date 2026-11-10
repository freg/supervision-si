# 2026-11-10 — identification des cibles, liste de surveillance (#1001)

**Freg** : un mini-PC de campus déplacé sur une borne murale n'est plus joignable ; doute sur l'appareil vu derrière la
borne (fabricant de l'adaptateur, trafic classé « Google Play »).

**Claude** : le seul client derrière la borne, le volume faible et régulier (profil machine, pas tablette) et l'adresse
annoncée par son cron l'identifient ; le fabricant est celui de l'adaptateur USB. Passage du port LAN de cette seule
borne dans le bon VLAN (réglage propre à la borne, pas celui du site qui aurait basculé toutes les bornes).

**Freg** : une liste de tablettes à ré-enrôler arrive (modèle, n° de série, MAC) ; pas dans le dépôt, mais dans un outil
de recherche automatique du hub utilisant toutes les sources (API Nebula, agents / sondes, imports). Puis : étendre
partout la concordance et l'identification à toutes les données d'une cible, y compris son activité pour ce qu'elle a
de singulier, catégoriser comme on le fait à vue (un Android, un Windows reconnus à leurs connexions).

**Freg** (correction) : une cible s'identifie sur chacun des éléments qui la caractérisent ; les discordances servent à
apprendre à corriger autant qu'à reconnaître une usurpation potentielle.

**Claude** : principe inscrit au backlog ; trois tranches : (1) liste de surveillance + recherche unifiée, (2) relevé de
l'activité par client, (3) catégorisation par l'activité. **Freg** : d'accord, dans cet ordre.

**Claude** (#1001) : onglet Nebula › Surveillance (dépôt par copier-coller, concordance pondérée avec preuves,
discordances, repères « du lot », apprentissage par confirmation), rapprochement à chaque relève horaire avec alerte,
recherche unifiée (historique, listes, identités réseau des agents via `GET /identites`).

**Claude** (#1002) : l'API publique Nebula ne donne pas les applications par client ; l'activité retenue est ce qu'elle
publie (volumes Wi-Fi par relève) et la présence (heures, jours, nuits, week-ends, mobilité) ; profil visible dans
l'historique des clients.

**Claude** (#1003) : catégorie proposée par client (système, nom, fabricant — un adaptateur n'est pas la machine —, MAC
aléatoire, comportement, mobilité, volumes), chaque indice pondéré par sa rareté sur le site, singularités listées ;
la liste de surveillance s'en sert (discordance si une « tablette » se comporte en machine).

**Freg** (essai de #1003) : la recherche générale du hub ne trouve pas l'historique des clients avec « historique » ; la
page est top, mais il faut chercher sur les hypothèses : un menu des catégories présentes et un menu des niveaux de
certitude ; avec une possibilité de confirmation humaine et derrière un apprentissage pour modifier les certitudes.

**Claude** (#1004) : pages profondes dans la recherche générale ; menus catégorie / certitude et colonne Catégorie ;
confirmer / corriger / annuler, chaque décision enseignant ses traits aux clients semblables ; corrections vues à
l'essai (mini-PC classé mobile : seuil de présence continue, mobilité entre deux bornes, cartes Wi-Fi intégrées).
