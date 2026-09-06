# Sauvegardes -- suivi/couverture (livraison #249)

Backlog item 27 -- "backup-restore", sous-volet marqué **URGENT**
par la personne : "Clonezilla (ou équivalent) pour produire une IMAGE
SYSTÈME complète -- objectif immédiat = future VIRTUALISATION de
postes Windows existants".

## Portée VOLONTAIREMENT LIMITÉE

Ce module répond d'abord à l'exigence explicite du backlog : "toute
machine [détectée sur le LAN] doit avoir une image prête à la
restauration" -- un registre des images connues, croisé avec les
appareils DÉJÀ découverts par `network-agent` (#233/#240), pour
répondre à la question "quelles machines n'ont PAS d'image récente ?".

**PAS construit ici** : l'automatisation réelle de Clonezilla (PXE
boot, DRBL, déclenchement à distance d'une capture) -- exactement le
même raisonnement que pour l'agent réseau (#233) : ce genre
d'infrastructure nécessite du matériel/réseau réel (serveur PXE/TFTP,
postes Windows accessibles) qu'aucun test dans cet environnement ne
peut valider. Les images sont enregistrées MANUELLEMENT pour
l'instant -- une fois que la personne aura défini comment elle pilote
réellement Clonezilla (script, DRBL, autre), une ingestion automatique
pourra remplacer cette saisie manuelle.

Les AUTRES volets du backlog (connecteur BackupPC, comparatif d'une
solution de backup alternative, statistiques/versions de fichiers,
agent courrier) restent également PAS COMMENCÉS -- seul le sous-volet
signalé urgent est traité ici.

## Modèle de données

Un enregistrement = UNE image de sauvegarde connue. `device_mac`
optionnel -- une image peut être enregistrée avant que la machine
correspondante soit rapprochée d'un appareil découvert par
`network-agent` (ou si cette machine n'est pas/plus sur le réseau
surveillé). `tool` reste un champ libre extensible
(clonezilla/backuppc/other) -- ne ferme jamais la porte aux autres
volets du backlog.

## Couverture -- le cœur de la demande

`GET /coverage` croise les appareils DÉCOUVERTS par `network-agent`
avec le registre local des images connues (par adresse MAC,
comparaison insensible à la casse). Renvoie, PAR APPAREIL, s'il a une
image, sa date, et depuis combien de jours -- calculé côté serveur
(une seule source de vérité pour "aujourd'hui"). Les machines SANS
image apparaissent EN TÊTE du tri, jamais une liste neutre à retrier.

**⚠️ Couverture nécessairement PARTIELLE et honnêtement signalée
comme telle** : une machine sans trafic réseau récent (éteinte,
débranchée du LAN surveillé) n'apparaît pas dans `network-agent`, donc
pas ici non plus -- ce n'est PAS un inventaire exhaustif du parc,
seulement des machines ACTIVEMENT vues sur le réseau surveillé.

## Point d'architecture important -- `network_mode: host`

`network-agent-api` tourne en `network_mode: host` (#238-239, confirmé
nécessaire en déploiement réel) -- il n'est PLUS sur le réseau Docker
partagé. `backup-restore-api` le joint via `NETWORK_AGENT_API_URL`,
construite avec `HOST_IP` (voir `docker-compose.yml`) -- **jamais le
nom de service Docker habituel**, qui ne résoudrait pas depuis un
conteneur normal comme celui-ci. Même piège déjà rencontré et corrigé
pour la passerelle nginx (#239), reproduit ici en connaissance de
cause dès la conception plutôt que découvert après un premier
déploiement raté.

## API

- `GET /images` (`?device_mac=X` optionnel) -- liste des images
  enregistrées.
- `POST /images` -- enregistre une nouvelle image (`device_label`,
  `tool`, `taken_at` requis).
- `DELETE /images/<id>` -- supprime un enregistrement.
- `GET /coverage` -- la vue croisée décrite ci-dessus. Best-effort
  explicite si `network-agent-api` est injoignable -- erreur claire
  (502), jamais un plantage silencieux.

## Vérifié réellement

Testé en profondeur : normalisation de casse des adresses MAC
(création ET filtrage), regroupement "la plus récente par machine"
confirmé correct (pas la première créée), image sans MAC gérée sans
exception et exclue proprement du regroupement par MAC, suppression
d'un id inexistant sans exception. Route `/coverage` testée de bout
en bout avec de vrais appareils simulés (cross-référencement correct,
tri machines-sans-image en tête, calcul des jours écoulés côté
serveur), et avec `network-agent-api` injoignable (502 propre, jamais
un 500 nu). Validation des champs requis et de la valeur `tool`
testée. Structure JSX de `BackupRestoreView.jsx` et `App.jsx`
revérifiée après câblage.

## Branchement rights-api (livraison #309)

Suite de l'item 38 du backlog -- service de SUIVI de couverture
uniquement (jamais l'automatisation réelle de Clonezilla), mais
falsifier ou supprimer un enregistrement pourrait masquer un vrai
trou de couverture. Gardé sur les deux routes d'ÉCRITURE
(`create_image`, `delete_image`) uniquement -- `/coverage` et
`/logs` restent en lecture libre, même motif que partout ailleurs
dans ce projet. OPT-IN via `BACKUP_RESTORE_RIGHTS_API_URL`, vide par
défaut, comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 sur les deux routes
gardées avec un groupe non autorisé, `/coverage` confirmée NON
affectée (même code de statut avant/après activation de
`rights-api`). Non-régression complète reconfirmée.

## Reste à faire

- Automatisation réelle de Clonezilla (PXE/DRBL) -- nécessite de
  cadrer l'infrastructure réelle avec la personne avant tout code,
  hors de portée de cette livraison d'urgence.
- Ingestion automatique des images (au lieu de la saisie manuelle
  actuelle) -- dépend de la façon dont Clonezilla sera concrètement
  piloté.
- Rapprochement automatique `device_label` <-> appareil réseau quand
  `device_mac` n'a pas été renseigné à la création.
- Les autres volets du backlog (BackupPC, solution alternative,
  statistiques de versions de fichiers, agent courrier) -- non
  traités ici, à cadrer séparément.
