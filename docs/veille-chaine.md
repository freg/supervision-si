# si-veille : veilleur local de la chaîne du hub (#841)

Un petit programme qui tourne **dans votre session** (Mac ou Linux, sans root) et qui teste toute la chaîne d'accès
au hub à intervalle régulier, **sans passer par le hub** : il doit justement voir le moment où le hub tombe.

- **Silencieux** tant que tout va bien : il écrit seulement dans son journal.
- **En cas de panne** : une notification graphique **qui revient** toutes les `rappel_min` minutes tant que la panne
  dure, et **un seul courriel** au début de l'incident. Si l'envoi échoue (réseau coupé côté poste), il est retenté au
  tour suivant. À la fin de la panne : notification « rétablie », plus un courriel seulement si `mail_retabli` vaut true.
- **Maillons chaînés** (`depend_de`) : quand un maillon tombe, ceux qui en dépendent ne sont pas testés, et l'alerte
  nomme la **cause probable** (le premier maillon en échec). `seuil_echecs` (2 par défaut) évite les fausses alertes.

Pas d'onglet dans le hub (c'est voulu). Pas de lien : opération manuelle.

## Types de maillons

| type | champs | réussite |
|---|---|---|
| `dns` | `nom_hote`, `attendu` (optionnel) | le nom résout (vers l'adresse attendue) |
| `tcp` | `hote`, `port` | le port s'ouvre |
| `tls` | `hote`, `port`, `nom_attendu`, `ca`, `jours_min` | certificat valide pour ce nom, pas d'expiration avant `jours_min` jours |
| `http` | `url`, `codes`, `contient`, `ca` | code attendu (200/30x/401 par défaut), texte présent |
| `commande` | `commande` | code de sortie 0 (par exemple `ssh hote "docker ps …"`) |

Champs communs : `id`, `nom`, `depend_de`, `delai_s` (10 s par défaut), `seuil_echecs`.

## Installation

```
cd ~/Downloads/supervision-si/veille-chaine && sh installer.sh ~/chemin/vers/ma-config.json
si-veille --tester-notif
```

- Mac : agent de connexion `~/Library/LaunchAgents/fr.exemple.si-veille.plist`. La première notification peut
  demander l'autorisation dans Réglages Système → Notifications (Éditeur de script).
- Linux : service utilisateur `systemctl --user status si-veille` (l'installeur lui passe l'affichage, le bus de
  session et l'agent ssh de la session ; à relancer après un changement de session graphique si les notifications
  n'apparaissent plus).
- Retrait : `sh installer.sh --retirer` (la configuration est gardée).

Les vraies adresses restent **hors dépôt** : `~/.config/si-veille/config.json` (le modèle `config.exemple.json` est
fictif).

## Icône de la barre du haut (#845)

Sous GNOME (45 et plus), `installer.sh` ajoute une icône au centre de la barre du haut, après la date : bouclier vert
quand tout va bien (rien d'autre affiché), orange sur un échec isolé, triangle rouge avec le nom du maillon en panne,
grisée si si-veille ne passe plus. Le menu donne l'état, la **dernière alerte**, les **maillons** (✓ ✗ ? —), les
**alertes récentes** (50 gardées), **Ouvrir le journal** et **Vérifier maintenant**. Le service démarre et s'arrête avec
la session graphique. Après l'installation : fermer puis rouvrir la session.

## Mot de passe SMTP

Jamais dans la configuration :

- Mac : `security add-generic-password -s si-veille -a smtp -w` (le mot de passe est demandé)
- Linux : `secret-tool store --label si-veille service si-veille compte smtp`
- à défaut : `~/.config/si-veille/secrets.json` = `{"smtp": "…"}`, en mode 600.

## Consulter

```
si-veille --une-fois > /tmp/veille.txt; less /tmp/veille.txt      # un passage complet, maillon par maillon
si-veille --etat                                                   # résultat du dernier passage
less ~/.local/state/si-veille/journal.log
```

Les commandes `ssh` doivent marcher sans mot de passe (`BatchMode=yes`). Côté hôte, `journalctl -u si-proxy-host`
demande que le compte soit dans le groupe `systemd-journal` ou `adm` : sinon le motif « canal de contrôle perdu »
n'est jamais vu.
