# Skills et apprentissage des IA du hub (#827, #828 — BACKLOG 132 T4-T5)

## Skills (Parc IA > Skills)

- Consignes versionnées des IA : chaque enregistrement crée une version, l'historique se consulte et se restaure.
- Branchés sur le code : `priorites-preparation`, `priorites-decideur` (instructions / critères des questions ; les
  clés et le format de réponse restent imposés), `priorites-explication`. Non personnalisé ou désactivé : le texte du
  code s'applique.
- Skills personnels : bibliothèque (assistant, veille, harnais…), avec « Essayer » sur un texte.

## Apprentissage (Parc IA > Apprentissage)

1. **Décider** dans la veille cyber : statuts posés par une personne, rejets. Ce sont les étiquettes.
2. **Jeu** : aperçu, statistiques, export JSONL (`train` / `test`, découpage stable par article).
3. **Entraîner** sur un hôte GPU NVIDIA avec `si-agent/tools/apprentissage/lora_unsloth.py` (pas de lien : opération
   manuelle) puis `ollama create decideur-lora:1 -f <sortie>/Modelfile`.
4. **Évaluer** : renseigner le modèle produit dans l'entraînement, « Évaluer » (part test) ; comparer à une évaluation
   du modèle de production (même bouton avec son nom).
5. **Mettre en service** seulement s'il fait mieux : Parc IA > Veille des modèles > Usages, case « décideur » sur
   l'hôte des priorités.

Garde-fous : petits modèles (≤ 8 B), LoRA seulement, données jamais hors de nos machines, aucune mise en service
automatique.
