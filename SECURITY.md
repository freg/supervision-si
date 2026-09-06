# Risques cyber — état des lieux (2026-09-02, livraison #185)

Passe **préliminaire**, volontairement concise (demandé explicitement
-- "pas besoin de trop de détails explicatifs, on refera l'analyse
en fin de conception"). Fondé sur l'architecture réelle du projet à
ce stade, pas un audit générique -- à reprendre et approfondir une
fois la conception stabilisée.

## 1. Risques identifiés

| # | Risque | Où |
|---|--------|-----|
| R1 | Secrets en clair dans `.env` (mots de passe SGBD, IMAP, Mayan) et clés SSH sur disque, jamais chiffrées | `.env`, `ssh-tunnels/keys/` |
| R2 | `rsyslog-listener` : port UDP exposé directement sur l'hôte, sans authentification ni chiffrement (syslog nature du protocole) | `rsyslog-listener/` |
| R3 | `ssh-tunnels-api` tourne avec `SYS_ADMIN` + AppArmor désactivé (nécessaire pour FUSE/SSHFS) | `ssh-tunnels/`, #180 |
| R4 | Échappement SQL manuel (pas de requête paramétrée) sur l'endpoint `/sql` de `dba-api`, utilisé par le "aller à la ligne liée" | `schema-analyzer`, #178 |
| R5 | Logs SANS rémanence -- tampon Memcached uniquement, perdu à chaque redémarrage (item 8 du backlog, pas encore traité) | `shared/log_buffer.py`, #145 |
| R6 | CORS permissif (`CORS(app)` sans restriction d'origine) sur la plupart des API internes | quasi tous les `app.py` |
| R7 | Mode proxy `ssh-tunnels` : aucun contrôle d'accès par consommateur -- tout conteneur du réseau Docker peut utiliser n'importe quel tunnel actif | `ssh-tunnels/`, #159/#184 |
| R8 | Composants tiers à surface de patching externe (Mayan/Django, Elasticsearch, Postgres/Redis/RabbitMQ...) | `mayan/`, `pixel-grid/`, etc. |
| R9 | Cibles distantes elles-mêmes anciennes/mal maintenues (vieux MySQL, SSH refusant les clés) -- souvent le maillon le plus faible, hors du périmètre de ce code | systèmes distants |
| R10 | Pas de piste d'audit détaillée des actions sensibles (qui a créé/démarré un tunnel, monté un partage, consulté un secret) au-delà d'un simple `created_by` | plusieurs modules |

## 2. Matrice de risque (probabilité × impact)

| Impact →<br>Probabilité ↓ | Faible | Moyen | Élevé | Critique |
|---|---|---|---|---|
| **Élevée** | | R6 | R9 | R1, R5 |
| **Moyenne** | | | R2, R4, R7, R8 | |
| **Faible** | | | | R3 |

**Priorités qui ressortent** : R1 (secrets en clair) et R5 (pas de
rémanence des logs) cumulent probabilité élevée ET impact fort --
premiers candidats naturels. R3 (privilèges `ssh-tunnels-api`) a un
impact critique mais une probabilité faible en l'état (suppose une
compromission préalable du conteneur) -- à garder sous surveillance
plutôt qu'à traiter en urgence.

## 3. Proposition de tableau de bord de surveillance

Un point par risque, en s'appuyant sur ce qui existe déjà quand
possible plutôt que de tout réinventer :

| Risque | Indicateur proposé | Source possible |
|---|---|---|
| R1 | Alerte si une clé `ssh-tunnels/keys/` ou une valeur `.env` change de permissions/apparaît en dehors des canaux attendus | à construire -- surveillance de fichiers (inotify ou sondage périodique) |
| R2 | Volume de paquets UDP reçus par `rsyslog-listener`, taux de paquets "hors format" (RFC non reconnu) | déjà loggé partiellement (#177) -- à exposer en compteur |
| R3 | Alerte si le processus `ssh-tunnels-api` tente une syscall inhabituelle (hors `mount`/`ssh`/`sshfs` attendus) | hors du périmètre applicatif -- outil hôte (auditd/Falco) plutôt qu'un développement interne |
| R4 | Journal de CHAQUE requête `/sql` avec la requête littérale exécutée, consultable a posteriori | à construire -- log dédié, distinct du tampon diagnostic actuel |
| R5 | Ancienneté de la plus vieille entrée encore en tampon vs événements réellement survenus (détecte une perte silencieuse) | dépend de l'item 8 (archivage persistant, pas encore traité) |
| R6 | Liste des origines CORS réellement utilisées en pratique (log des en-têtes `Origin` reçus), pour resserrer une fois connues | à construire -- middleware de journalisation |
| R7 | Table de correspondance "quel conteneur a utilisé quel tunnel, quand" -- absente aujourd'hui | à construire -- nécessiterait un log applicatif côté tunnel |
| R8 | Version/CVE connus des images tierces utilisées, comparés à un flux de vulnérabilités publiques | outil externe (Trivy, Grype...) plutôt qu'un développement interne |
| R9 | Déjà partiellement couvert : `GET /mounts/<id>/stats` (#182) et les statuts de connexion `ssh-tunnels`/`dba-api` donnent un signal de santé des cibles distantes | existant, réutilisable tel quel |
| R10 | Étendre les `created_by`/`actor` déjà présents en un vrai journal d'audit consultable (qui, quoi, quand) par module | à construire -- généraliser un motif déjà partiellement en place |

**Non traité ici, à creuser en fin de conception** : quantification
plus fine (échelle numérique plutôt que Faible/Moyen/Élevé),
priorisation chiffrée, plan de remédiation détaillé par risque,
répartition des responsabilités.
