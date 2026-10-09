# Tuile « Déploiement d'application » : nouvelle instance par clonage (item 117) — cadrage et tranches

Demandé (9 oct. 2026) : « une tuile de déploiement d'application (GED, tickets…) : clonage configuration ».
Décisions : instance déployée **sur un autre nœud** ; le clonage copie **configuration + référentiels** (types, statuts,
niveaux, sites, règles, modèles, habillage, droits), **jamais** de données métier (tickets, documents), de personnes ni
de secrets.

## Ce qui existe et sera réutilisé
- Répartition par nœud (#509-#517) : `deploy/nodes.json`, `deploy/cohorts.json`, override compose généré par nœud,
  relais DNS vers les services distants, agent de nœud (`deploy/node_agent.py` : apply, export/import de données).
- Tour de contrôle (#586) : jobs détachés, journal ; services-api `/repartition`.
- Exports JSON existants : tickets-api `/export` + `/import?mode=merge`.

## Tranches
1. **Export « configuration » des applications** — FAIT pour le portail tickets (#722) : `GET /export?scope=config`
   (types, niveaux, statuts, sites, règles d'escalade, appariement, exclusions, mots-clés de priorité, filtres d'agenda),
   importable tel quel par `POST /import?mode=merge` de l'instance neuve. À faire : GED (types et plan de classement).
2. **Registre des instances** `deploy/instances.json` : `{nom, application, nœud, suffixe, chemin public, instance
   source}` ; `deploy/cohorts.py override` génère sur le nœud cible les services de l'application **renommés**
   (`tickets-api-<suffixe>`, volume de données propre, ports et relais), et une route `/tickets-<suffixe>/` sur tls-proxy.
3. **Agent de nœud** : job « créer l'instance » = override + `compose up` des services clonés, attente de santé, import
   de la configuration exportée de la source, client Keycloak du front (même realm, redirections de la nouvelle URL).
4. **Tuile** (thématique Données ou Sécurité & accès) : liste des instances (application, nœud, URL, état), formulaire
   « nouvelle instance » (application, source, nœud, nom), avancement par la tour de contrôle, suppression (données
   sauvegardées avant).
5. **Mise à jour** : une instance suit les livraisons comme les autres services (même image, autre nom).
