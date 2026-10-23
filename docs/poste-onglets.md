# si-onglets : rouvrir les onglets du terminal à l'ouverture de la session (#848)

Fini d'ouvrir un terminal, de le passer en plein écran puis de rouvrir un à un les onglets (et d'en oublier) :
à l'ouverture de la session graphique, `si-onglets` rouvre la fenêtre GNOME Terminal en plein écran avec tous les
onglets enregistrés, chacun dans son dossier et avec sa commande (ex. `ssh super`) ; quand la commande se termine,
l'onglet reste ouvert sur un shell.

Pas de lien : opération manuelle, sur le poste (Linux, GNOME Terminal, sans root).

```
cd ~/Downloads/supervision-si/poste-onglets && sh installer.sh
# ouvrir ses onglets comme d'habitude, puis depuis l'un d'eux :
~/.local/bin/si-onglets --capturer        # relève dossier + commande au premier plan de chaque onglet
~/.local/bin/si-onglets --liste
~/.local/bin/si-onglets --ouvrir --sans-attente   # essai immédiat (ouvre une seconde fenêtre)
```

- Enregistrement : `~/.config/si-onglets/onglets.json` (modifiable à la main ; copie précédente en `.avant`) :
  `plein_ecran` (sinon fenêtre agrandie), `attente_s` (5 s, le temps que le réseau et l'agent ssh soient prêts),
  `onglets` : `[{titre, dossier, commande}]`, dans l'ordre d'ouverture.
- Lancement : `~/.config/autostart/si-onglets.desktop`. Retrait : `sh installer.sh --retirer`.
- Relever à nouveau (`--capturer`) quand la liste des onglets change.
