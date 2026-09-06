# Clés SSH -- dossier à peupler manuellement

Déposez ici les clés PRIVÉES déjà autorisées côté machines
distantes (celles que `ssh-tunnels-api` doit pouvoir utiliser pour
ouvrir des tunnels). Ce module ne génère, ne modifie, ni ne stocke
jamais de clé lui-même -- voir `ssh-tunnels/README.md`.

- Un fichier = une clé (jamais de sous-dossier, jamais scanné
  récursivement).
- Les fichiers `.pub` sont ignorés lors de la découverte (inutile de
  les retirer, ils ne sont juste jamais listés comme des clés à part
  entière).
- Permissions habituelles d'une clé privée (`chmod 600`) recommandées
  sur l'hôte, même si ce dossier est monté en LECTURE SEULE dans le
  conteneur.
- Ce dossier est explicitement exclu de Git (`.gitignore`, racine du
  projet) -- ne JAMAIS committer de vraie clé privée.

Une fois un fichier déposé ici, il apparaît automatiquement dans
`GET /api/ssh-tunnels/keys` (scan à chaque appel, rien à redémarrer).
