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
