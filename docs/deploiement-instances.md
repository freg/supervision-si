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
2. **Registre des instances** — FAIT (#731) : `deploy/instances.py` + `deploy/instances.json` (modèle
   `instances.example.json`). Voir « Mode d'emploi » ci-dessous. Détail initial : `deploy/instances.json` : `{nom, application, nœud, suffixe, chemin public, instance
   source}` ; `deploy/cohorts.py override` génère sur le nœud cible les services de l'application **renommés**
   (`tickets-api-<suffixe>`, volume de données propre, ports et relais), et une route `/tickets-<suffixe>/` sur tls-proxy.
3. **Agent de nœud** — FAIT (#732) : `node_agent.py instance-deploy <nom>` (voir Mode d'emploi). Détail initial : job « créer l'instance » = override + `compose up` des services clonés, attente de santé, import
   de la configuration exportée de la source, client Keycloak du front (même realm, redirections de la nouvelle URL).
4. **Tuile** (thématique Données ou Sécurité & accès) : liste des instances (application, nœud, URL, état), formulaire
   « nouvelle instance » (application, source, nœud, nom), avancement par la tour de contrôle, suppression (données
   sauvegardées avant).
5. **Mise à jour** : une instance suit les livraisons comme les autres services (même image, autre nom).

## Mode d'emploi (#731)

```
cd ~/SRC/data2/tickets/supervision-si && cp deploy/instances.example.json deploy/instances.json   # puis éditer name / node
cd ~/SRC/data2/tickets/supervision-si && python3 deploy/instances.py check && python3 deploy/instances.py plan formation
cd ~/SRC/data2/tickets/supervision-si && python3 deploy/cohorts.py check && python3 deploy/cohorts.py override <nœud-cible>
cd ~/SRC/data2/tickets/supervision-si && ./scripts/run.sh up -d --build tickets-api-formation tickets-portal-formation   # sur le nœud cible
cd ~/SRC/data2/tickets/supervision-si && python3 tls-proxy/render_nginx_conf.py && ./scripts/run.sh restart tls-proxy        # passerelle : routes /tickets-formation/
```
- Services clonés `<service>-<nom>` : même construction, données dans `./instances/<nom>/<service>` (ignoré par git),
  adresses internes et chemins publics renommés (`/api/tickets-<nom>`, `VITE_BASE=/tickets-<nom>/`), base **SQLite
  forcée** (jamais la base PostgreSQL de l'instance d'origine), étiquettes `si.instance`.
- `deploy/cohorts.py` intègre le registre : cohorte `inst-<nom>` sur le nœud choisi, définition complète des services
  dans l'override de ce nœud, relais vers eux sur les autres (bordure : routes tls-proxy).

### Création en une commande (#732, sur le manager)
```
cd ~/SRC/data2/tickets/supervision-si && python3 deploy/node_agent.py instance-deploy formation
```
1. nœud cible (`POST /instance`, registre transmis) : apply → services clonés + relais vers la source
   (`SI_INSTANCE_SOURCE_URL`) ; puis, DANS le conteneur `tickets-api-<nom>` : attente de `/health`,
   `GET <source>/export?scope=config`, `POST /import?mode=merge` (référentiels seulement) ;
2. chaque passerelle (bordure / core, `POST /instance/gateway`) : relais vers l'instance, `render_nginx_conf.py` +
   rechargement de tls-proxy, `keycloak/render.py` + `sync_clients.py` (redirections `/tickets-<nom>/*` du client
   `tickets-portal`).
- Arrêt : `node_agent.py instance-stop <nom>` sur le nœud cible (conteneurs retirés, données conservées).
- Reste (tranche 4) : la tuile (liste, formulaire, suivi par la tour de contrôle).
