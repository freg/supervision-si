# Publication du projet — GitHub & Framagit

Le dépôt git est **déjà initialisé** (branche `main`, commit initial,
`.gitignore` en place). Un seul historique, poussé vers **deux
remotes** — c'est volontaire : deux imports séparés donneraient deux
dépôts qui divergent dès le premier commit.

## 1. Identité des commits (une fois)

Le commit initial porte une identité de substitution. Mets la tienne :

```bash
git config user.name  "Ton Nom"
git config user.email "ton@email"
git commit --amend --reset-author --no-edit
```

## 2. Créer les dépôts distants (vides)

- **GitHub** : *New repository* → nom `supervision-si` → **ne rien
  cocher** (ni README, ni .gitignore, ni licence — le dépôt doit être
  vide pour accepter le push tel quel).
- **Framagit** (GitLab) : *New project* → *Create blank project* →
  décocher *Initialize repository with a README*.

## 3. Pousser vers les deux

```bash
GITHUB_REMOTE=git@github.com:<compte>/supervision-si.git \
FRAMAGIT_REMOTE=git@framagit.org:<compte>/supervision-si.git \
./scripts/publish_remotes.sh
```

(URLs HTTPS acceptées aussi ; le script est relançable, il met juste à
jour les remotes.) Ensuite, au quotidien :

```bash
git push github main && git push framagit main
```

## Ce qui ne part PAS dans git (voulu)

- `.env` — configuration locale et **secrets** (mot de passe de bind
  LDAP, admin Keycloak). Versionné à la place : `.env.example`, à
  copier en `.env` sur chaque machine (`cp .env.example .env`).
- `keycloak/import/` — realm **rendu** contenant le mot de passe LDAP
  en clair (le gabarit sans secret, lui, est versionné).
- `*.db`, `node_modules/`, `__pycache__/`, `*.zip`.

## Licence — à choisir avant de rendre public

Aucune licence n'est imposée ici : **sans fichier LICENSE, un dépôt
public reste "tous droits réservés"** (lisible mais légalement non
réutilisable). Si tu veux du libre : AGPL-3.0 (copyleft fort, esprit
Framagit), GPL-3.0, ou MIT/Apache-2.0 (permissives). Ajouter le
fichier `LICENSE` correspondant puis commit.
