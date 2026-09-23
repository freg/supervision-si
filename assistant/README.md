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

Réglage #535 (journaux pondérés, titre triple, 2 extraits max par
document) : **pire**, questions 0,5/5 -- le plafond par document chassait
les bons passages au profit de README hors sujet. Rejeu hors ligne de la
recherche sur les mêmes 65 fichiers (les cinq questions, en comptant si
les mots attendus sont dans les extraits, sans appeler le modèle) : trois
causes réelles, corrigées en #536.

- **Jetons creux surpondérés** : « quel », « comment », « sert », « porte »,
  « teste-t-elle », « met-il » n'étaient pas des mots vides ; rares dans le
  corpus, ils dominaient le score BM25 (a01 remontait la charte des icônes).
  Mots vides étendus, clitiques interrogatifs ôtés.
- **Titres de section perdus** : le découpage ignorait la structure
  Markdown ; le passage « `shared/DELIVERY_NUMBER` » n'avait pas dans son
  morceau les mots de son titre. `chunk_markdown` préfixe chaque morceau
  du fil des titres (« § si-agent › Auto-mise à jour… »), ce qui sert aussi
  au modèle pour situer l'extrait.
- **Mots composés** : « auto-mise », « path-probe » indexés avec leurs
  parties.
- Cas a03 reformulé : le README ne parle pas de « version minimale ».

Résultat hors ligne : mots attendus présents dans les extraits pour 5/5
questions à k=5 (contre 3,3/5 avec #534 et 1,5/5 avec #535), insensible au
poids des journaux ; plafond par document désactivé par défaut.

Passage réel #536 (2026-09-22, même VM) : **questions 5/5**, classification
10/10, résumés 4,5/5, 38 à 68 s par question. Les quatre passages :

| Livraison | Index | Réflexion | Classification | Résumés | Questions | Par question |
|---|---|---|---|---|---|---|
| #533 | `docs/` seul | oui | 9,3/10 | 5/5 | 0/5 | 51–91 s |
| #534 | + dépôt (65 fichiers) | non | 10/10 | 4,75/5 | 2/5 | 47–62 s |
| #535 | idem, journaux 0,4, 2/doc | non | 10/10 | 4,75/5 | 0,5/5 | 42–65 s |
| #536 | idem, mots vides, titres | non | 10/10 | 4,5/5 | **5/5** | 38–68 s |

Leçon : sur ce corpus, la qualité des questions ne tenait qu'à la
recherche lexicale, pas au modèle -- un 8b sans réflexion répond juste
dès que le bon passage est dans les extraits. Suite : cas réels hors
dépôt (tickets, GED), puis mesure sur GPU (la latence est le traitement
du prompt sur CPU).

## Journal : produit et attendu (#540)

Demandé : « journal : ajouter le résultat produit et l'attendu ». Chaque
ligne du journal porte désormais **Demandé** (question ou début du texte),
**Produit** (le JSON extrait, sinon le texte tronqué à 700 caractères) et,
pour un passage d'évaluation, une ligne par cas (`kind: eval`, colonne
Usage « éval a01 (ask) ») avec **Attendu** (le bloc `expect` du cas :
mots-clés, champs JSON, source) et la **Note** (survol du « ? » : détail
par critère, mots-clés manquants). Les usages interactifs gardent une
ligne par appel ; l'évaluation ne double plus ses lignes.

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

## Extraction de fiches (livraison #571) — `POST /assistant/extract`

`{"text": "...", "schema": "asset" | "service", "fields": [...] (facultatif),
"context": "..."}` → `parsed = {"fiches": [...], "sensible": [champs],
"remarques": [...]}`. Sert au volet Campus de la tuile Nebula (« Extraire
d'un texte (IA interne) ») : on colle un « À propos » Windows, un courriel
de livraison, une liste ; le modèle local (Ollama sur le SI, rien ne sort)
renvoie des fiches structurées, signale les champs sensibles (IP, MAC,
séries, identifiants, comptes ; mots de passe masqués) et les anomalies
(IP incohérente, doublon) ; la personne relit, corrige, importe en fusion.
Journalisé (`extract`) comme les autres usages.
