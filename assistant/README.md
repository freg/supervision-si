# assistant — PoC assistant IA interne, palier 1 (livraison #532, backlog item 81)

Un modèle ouvert servi **sur nos machines** (Ollama, ou tout serveur
compatible OpenAI : llama.cpp, vLLM), un RAG lexical sur les sources du hub,
trois usages ciblés et un jeu d'évaluation reproductible. Objectif du PoC :
**mesurer** (jetons/s, qualité sur 20 cas) avant toute décision GPU.

## Premier test, pas à pas

1. **Machine** : une VM de 24 Go de RAM et 8 vCPU (le Proxmox libre), ou la
   VM super si elle a la marge — le modèle occupe ~5 Go (`qwen3:8b`) à
   ~18 Go (`qwen3:30b-a3b`, MoE : rapide sur CPU). Profil compose
   `assistant` : rien ne démarre sans le demander.
2. **Démarrer** (depuis la racine du projet) :
   ```
   cd ~/SRC/data2/tickets/supervision-si && python3 scripts/sync-env.py && ./scripts/run.sh up -d --build ollama assistant-api tls-proxy hub
   ```
3. **Tirer le modèle** (une fois, plusieurs Go) :
   ```
   cd ~/SRC/data2/tickets/supervision-si && docker compose exec ollama ollama pull qwen3:8b
   ```
   Autres candidats : `qwen3:30b-a3b` (CPU 32 Go, meilleur), `glm5:9b` /
   `glm5:32b` (GPU 24 Go, voir le Modelfile du guide GLM-5 si absent du
   registre Ollama), `gpt-oss:20b`. Changer `LLM_MODEL` dans `.env` puis
   `./scripts/run.sh up -d assistant-api`.
4. **Tuile « Assistant IA (PoC) »** (Documents & ENT) : le bandeau indique
   si le modèle est prêt et ce que contient l'index.
5. **Évaluation** → « Lancer l'évaluation » : 20 cas fictifs (10 documents
   à classer, 5 demandes à résumer, 5 questions sur la documentation du
   dépôt). Rapport : score par famille, jetons/s moyen et minimum, temps
   total ; conservé dans `assistant/data/eval-*.json` pour comparer les
   modèles et les machines.
6. **Cas réels** (hors dépôt) : déposer `assistant/data/cases.json` au même
   format (10 documents GED réels à classer, 5 tickets, 5 questions) ; les
   textes de test se déposent aussi depuis « Classer un document » (source
   `uploads`, indexée à la réindexation).

Serveur de modèle sur une autre machine (GPU) : `LLM_BASE_URL=http://<ip>:11434/v1`
dans `.env`, sans démarrer `ollama` ici.

## Ce que fait assistant-api

- **Index** (`/assistant/index/rebuild`, au démarrage) : documents locaux
  (`ASSISTANT_DOCS_DIR`, défaut `./docs` du dépôt : .md/.txt/.csv/.json/.html),
  dépôts de test, tickets (`tickets-api /queue`), GED (`ged-api /documents`,
  texte des versions textuelles). Découpage en morceaux ~900 caractères,
  BM25 en mémoire (pas d'embeddings au PoC : mesurer d'abord si le modèle
  répond juste avec de bonnes sources ; bge-m3 / Qwen3-Embedding ensuite).
- **Question** (`POST /assistant/ask`) : 5 meilleurs extraits → invite
  « réponds uniquement à partir des extraits, cite [n] » → réponse + sources
  + jetons/s. Mode « sans sources » pour comparer.
- **Classer un document** (`POST /assistant/classify`) : JSON `type, site,
  titre, resume, mots_cles, date, confiance` parmi des types/sites donnés
  (`response_format` JSON + extraction tolérante, balises `<think>` retirées).
- **Résumer une demande** (`POST /assistant/summarize`) : JSON `resume,
  categorie, urgence, actions_suggerees, questions_a_poser`.
- **Évaluation** (`POST /assistant/eval/run`, `GET /assistant/eval/last`,
  `/eval/history/<f>`) : notation par cas — mots-clés attendus, JSON valide
  et champs attendus (valeurs acceptées multiples), source attendue —
  moyenne par famille et globale.
- **Journal** (`/assistant/journal`) : chaque requête (usage, durée,
  jetons/s, sources), sans le texte des documents.

Rien ne sort du SI ; aucun secret dans ce service ; la tuile est réservée
admin/technicien le temps du PoC (le modèle voit les tickets).

## Repères attendus (à confirmer par la mesure)

| Machine | Modèle | jetons/s attendus |
|---|---|---|
| CPU 8 vCPU, 32 Go | qwen3:8b Q4 | 6-12 |
| CPU 8 vCPU, 32 Go | qwen3:30b-a3b Q4 | 8-15 (3 Md actifs) |
| GPU 24 Go | qwen3:30b-a3b / glm5:32b Q4 | 25-100 |

Critère de passage au palier 2 : score ≥ 0,8 sur les classements et résumés
avec ≥ 8 jetons/s en CPU (usage par lots viable) ; le dialogue confortable
(≥ 25 jetons/s) demande le GPU.

Tests : `cd assistant && python3 -m unittest discover -s tests`.
