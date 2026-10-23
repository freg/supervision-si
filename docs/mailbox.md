# si-mailbox — agent de messagerie de la session (#840)

Agent **dans la session de l'utilisateur** (pas root), écran web local `127.0.0.1:8095` (jeton), bibliothèque standard
Python seule.

- **Requête** : chercher dans une boîte IMAP (de, sujet, contient, période) et poser une question à l'IA sur les
  messages trouvés (réponse avec références [n]).
- **Automates** : un dossier → filtres → IA de traitement (catégorie, résumé, extraction, consigne libre) → actions
  (déplacer, copier, étiqueter, marquer lu / important, script, notification du bureau), conditionnables à la catégorie
  (« deplacer Factures si à payer »). Mode **essai** d'abord (journal de ce qui serait fait, rien n'est touché), puis
  **actif**. Scripts : seulement `~/.config/si-mailbox/scripts/`, message en JSON sur l'entrée standard, 60 s au plus.
- **Liaison** : **discret** par défaut — aucune liaison avec le hub, aucune connexion hors IMAP et IA configurés.
  **Relié** : résumé SANS contenu (compteurs, automates, dernières actions ; sujets seulement si coché) déposé dans
  `~/.local/share/si-mailbox/publication.json`, remonté par la sonde `mailbox` de l'agent du poste (tuile Boîtes aux lettres).
- **Secrets** : trousseau du système (`security` macOS, `secret-tool` Linux), sinon fichier 600 local.
- **IA** : Ollama local conseillé (le texte des messages ne quitte pas le poste).

## Widget de la barre du haut (#843)

Sous GNOME (45 et plus), une icône et un micro-statut à côté de la date : **non lus au total · non lus du 1er filtre**
(ex. `12 · 3`) ; jaune quand un filtre a des non lus, rouge si aucun compte ne répond, grisé si le relevé date de plus
de 10 min. Le menu détaille chaque filtre et ouvre l'écran. Réglage dans l'onglet **Widget** de l'écran : dossier
(INBOX), cadence (60 s), jusqu'à 5 filtres « de contient » / « sujet contient ». L'agent ne fait que compter
(SEARCH UNSEEN en lecture seule : rien n'est ouvert ni marqué lu) et écrit `~/.local/share/si-mailbox/compteurs.json` (600).
`si-mailbox --compteurs` fait un relevé en ligne de commande. Après l'installation : fermer puis rouvrir la session.

Installation (pas de lien : opération manuelle, sur le poste, sans sudo) :

    cd ~/Downloads/supervision-si/mailbox && sh installer.sh          # Linux (systemd --user) ou macOS (LaunchAgent)
    si-mailbox --ouvrir                                               # adresse de l'écran avec son jeton
    cd ~/Downloads/supervision-si/mailbox && sh installer.sh --retirer
