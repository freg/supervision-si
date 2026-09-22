# Règles lisibles — base de connaissance de l'IA intégrée et des modules

Dossier de **règles humainement compréhensibles et modifiables** (livraison
#556). Chaque règle dit, en français, ce qu'on constate, ce que ça signifie,
ce qu'on propose de faire et si le hub peut le faire lui-même. Les mêmes
fichiers servent à trois usages :

1. **Les modules** (carte des VLAN Nebula aujourd'hui, Cortex et
   service-watch ensuite) : quand un module détecte une anomalie d'un type
   donné (`Quand`), il lit ici la gravité et l'action proposée, et l'affiche
   dans son tableau d'anomalies. Changer une phrase ici change ce que le
   hub propose, sans toucher au code.
2. **L'assistant IA** (`assistant/`) : ces fichiers sont indexés comme
   documents (`ASSISTANT_RULES_DIR`, monté en `/rules`) — l'IA répond à
   « que faire si un VLAN manque sur un lien ? » avec la règle, pas avec une
   invention. C'est l'ensemble d'apprentissage : des cas, leur explication,
   la bonne réponse.
3. **Vox-cortex** (BACKLOG item 83) : l'IA propose, le hub journalise, une
   personne confirme — une règle marquée `Applicable : oui` est la seule
   qu'une validation peut exécuter automatiquement.

## Format d'une règle

Un fichier Markdown par domaine (`reseau-nebula.md`, `services.md`…). Une
règle = un titre de niveau 2 commençant par son identifiant, puis des lignes
« - Clé : valeur ». Les clés reconnues :

```
## R-NET-01 · VLAN manquant d'un côté d'une liaison
- Quand : link_missing_vlan
- Gravité : haute
- Action : Ajouter le VLAN {vlans} en étiqueté sur le port {missing_port} de {missing_on}.
- Applicable : oui
- Pourquoi : (explication libre, plusieurs phrases possibles)
- Vérifier : (comment s'assurer que c'est réglé)
- Exemples : (cas réels anonymisés, ce qui s'est passé)
```

- `Quand` : le type technique d'anomalie émis par le module (un mot, sans
  espace). Un type inconnu des règles s'affiche quand même, avec l'action
  « à qualifier ».
- `Gravité` : `haute`, `moyenne`, `basse` ou `info`.
- `Action` : phrase avec des `{champs}` remplacés par les détails de
  l'anomalie (les champs disponibles sont listés par règle ci-dessous). Un
  champ absent reste tel quel entre accolades, jamais une erreur.
- `Applicable` : `oui` seulement si le module sait exécuter l'action par
  une API (et que l'écriture est autorisée dans le `.env`) ; sinon `non`.
- Tout le reste est du texte pour les humains et pour l'IA.

Les règles sont relues à chaque appel (pas de redémarrage). Un fichier qui
ne parse pas est ignoré avec un message dans `errors`, jamais un plantage.
