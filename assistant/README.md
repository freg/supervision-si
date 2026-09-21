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

## Premier passage réel (2026-09-21, #534) et ce qui en découle

VM 6 vCPU / 16 Go sur l'hyperviseur, `qwen3:8b`, réflexion active :
classification 9,3/10, résumés 5/5, questions 0/5, 51 à 91 s par cas.
Les questions échouaient parce que l'index ne contenait que `docs/` : les
réponses attendues (règle de commit, sonde path-probe, mise à jour d'agent,
service-watch, coffre) vivent dans les README des modules, le CHANGELOG et
le BACKLOG -- le modèle a correctement répondu « pas dans les extraits »
plutôt que d'inventer. Deux corrections :

- **Documentation du dépôt indexée** : à la construction de l'image, les
  `*/README.md` (renommés `<module>.md`), `README.md`, `CHANGELOG.md` et
  `BACKLOG.md` sont copiés dans `/repo-docs` (source `repo`, identifiants
  `repo:<fichier>`), indexés avec les documents. Rien d'autre du dépôt
  n'entre dans l'image (`.env` exclu).
- **Réflexion coupée par défaut** (`LLM_THINK=false`) : sur un Ollama
  (`LLM_BASE_URL` en `…/v1`), assistant-api appelle l'API native `/api/chat`
  avec `think: false` (et `format: json` pour les usages JSON) ; sur un
  autre serveur compatible OpenAI, l'API `/chat/completions` reste utilisée.
  Le préfixe `/no_think` dans l'invite ne suffit pas avec les versions
  récentes d'Ollama. `LLM_THINK=true` pour comparer la qualité.

## Second passage (2026-09-21, #534 déployé) et réglage du RAG (#535)

Même VM, 65 fichiers du dépôt indexés (86 documents, 3 313 morceaux),
réflexion coupée : classification **10/10** (le cas « contrat » passe),
résumés 4,75/5, questions **2/5**, 47 à 62 s par question. Les trois
questions ratées avaient reçu presque uniquement des morceaux du CHANGELOG
et du BACKLOG (a01 : cinq sur cinq), jamais `shared.md` ni le bon passage
de `si-agent.md` : les journaux sont longs, répètent les mots des
questions (« livraison », « agent », « update ») et occupaient les cinq
extraits. La latence restante est le traitement du prompt sur CPU
(≈ 4 000 jetons d'extraits), pas la génération : c'est ce qu'un GPU
change.

Réglage #535, sans embeddings : les morceaux de `CHANGELOG.md` et
`BACKLOG.md` sont pondérés (`ASSISTANT_JOURNAL_WEIGHT`, défaut 0,4), le
titre du morceau compte triple dans l'index (une question qui nomme le
module remonte son README) et un même document ne fournit qu'au plus deux
des `k` extraits (`max_per_doc`). À mesurer au passage suivant ; si les
questions restent sous 4/5, l'étape d'après est un reclassement par le
modèle ou des embeddings (`nomic-embed-text`), plus coûteux.

## Ce que fait assistant-api

- **Index** (`/assistant/index/rebuild`, au démarrage) : documents locaux
  (`ASSISTANT_DOCS_DIR`, défaut `./docs` du dépôt : .md/.txt/.csv/.json/.html),
  documentation du dépôt copiée dans l'image (`/repo-docs`, #534),
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

Infrastructure (VM, postes détournés, GPU low profile pour châssis 2U,
passthrough) : `docs/assistant-ia-infrastructure.md`.

Tests : `cd assistant && python3 -m unittest discover -s tests`.
