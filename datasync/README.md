# Synchronisation centrale (module du hub, livraison #652)

Liaison de synchronisation **unidirectionnelle** depuis les serveurs / applications / bases du parc vers un SGBD
central sur le hub, pour les phases de transition de déploiement et pour l'agrégation (indexation, traitements
transversaux). Demande du 3 oct. 2026, cinq points, tous couverts dans cette première livraison :

1. **Liaison concentrique** : une source → le central = **une API source centrale** (`datasync-api`). Chaque source a un
   jeton (affiché une seule fois) ; un connecteur autonome (`datasync/connector/connector.py`, bibliothèque standard +
   pilote de la base, SELECT seulement) ou n'importe quel programme pousse `/ping`, `/schema`, `/rows` (lots complets —
   le central retire les lignes disparues — ou incrémentaux par colonne croissante, état local du connecteur).
2. **Supervision des remontées** : présence (dernier ping, seuil `DATASYNC_PRESENCE_S`), statistiques par table (lignes,
   lots, lignes et durée du dernier lot, erreurs), journal des lots.
3. **Analyse schéma / étiquette / champ / contenu** (`matching.py`, pur) : profil de chaque colonne (format observé),
   noms normalisés et synonymes (id_contact ~ contactId ~ client, email ~ courriel…), correspondances entre champs de
   tables différentes (nom, format, recouvrement des valeurs), relations déduites par les valeurs (`id_x` résolu dans la
   clé de `x`, y compris entre sources) ; validation manuelle (proposé / confirmé / rejeté) et liens saisis à la main.
4. **Recherche plein texte transversale** : FTS5 (unicode61, sans diacritiques, préfixes, expressions, `champ:valeur`),
   filtre par source/table, extraits surlignés, saut vers les relations.
5. **Recherche relationnelle** : depuis une ligne, les lignes en relation sémantique par les relations confirmées ou
   déduites, dans les deux sens, intra et inter-sources, à 1–3 niveaux ; parcours des tables.

## Décisions

- Stockage central en **lignes génériques** (source, table, clé, JSON, horodatage) + index FTS5 : aucune DDL par
  source, un seul modèle pour les trois outils. SQLite (WAL, un worker) ; PostgreSQL (JSONB + tsvector) = évolution,
  l'accès passe par les seules fonctions d'`app.py`.
- Sens unique strict : le hub ne modifie jamais une ligne ; les connecteurs ne font que lire.
- Jetons : empreinte SHA-256 en base, indice (6 caractères) pour reconnaître ; rotation possible.
- Les données réelles restent dans `datasync/data/` (ignoré par git) ; le connecteur et ses états hors dépôt aussi.

## Vérifié / non vérifié

- `datasync/api/test_datasync.py` : matching pur ; API (deux sources, ping → présence puis absence, schéma avec nom
  invalide refusé, lots complets avec retrait des disparues, incrémental, statistiques, journal, profils, analyse
  inter-sources — relation tickets.id_contact → contacts.id et → clients.num, correspondance email ~ courriel —,
  confirmation conservée à la ré-analyse, lien manuel, plein texte avec accents/préfixe/filtre, relationnel à 2 niveaux
  dans les deux sens, rotation du jeton, suppression) ; **connecteur réel** contre l'API servie dans un thread sur une
  source SQLite (table à watermark : une seule ligne envoyée au second cycle ; table complète : ligne disparue retirée ;
  état local).
- Front : `hub/tests/datasyncLib.test.mjs`, syntaxe `@babel/parser`, pas de couleur en dur.
- Non vérifié : build de l'image, rendu navigateur, pilotes MySQL/PostgreSQL du connecteur (SQLite seul testé).
