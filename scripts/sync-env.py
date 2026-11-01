#!/usr/bin/env python3
"""Synchronise `.env` avec `.env.example` : ajoute les clés MANQUANTES
avec une valeur par défaut fonctionnelle (livraison #479, demandé
explicitement après un redéploiement où les nouvelles clés PROJEQTOR_*
avaient dû être recopiées à la main).

Règles :

- une clé est « présente » si une ligne `KEY=` existe dans `.env`,
  même vide — jamais d'écrasement d'une clé existante ;
- la valeur par défaut est reprise de `.env.example` (vide reste vide,
  c'est souvent le défaut documenté « fonctionnalité désactivée ») ;
- exception `change-me` : ces placeholders sont TOUS des secrets
  INTERNES (vérifié — les systèmes externes sont laissés vides dans
  `.env.example`, jamais `change-me`), donc une valeur aléatoire est
  générée, comme le fait `scripts/generate-env.sh`. Couplage connu :
  `LDAP_BIND_PASSWORD` / `LDAP_TEST_ADMIN_PASSWORD` partagent la MÊME
  valeur (même compte cn=admin de l'annuaire de test, voir
  `.env.example`) — si `LDAP_BIND_PASSWORD` existe déjà dans `.env`,
  sa valeur est réutilisée TELLE QUELLE (même `change-me`, défaut
  fonctionnel de l'image osixia/openldap), sinon une seule valeur est
  générée pour les deux ;
- les clés ajoutées sont insérées EN FIN de `.env`, chacune précédée
  du bloc de commentaires qui la documente dans `.env.example`, sous
  un en-tête daté (traçabilité) ;
- idempotent : sans clé manquante, `.env` n'est pas modifié.

Appelé automatiquement par `scripts/run.sh` (donc aussi par
`scripts/chantier.sh`, qui lui délègue tout) AVANT `check-env.py`,
pour que le rapport de cohérence reflète l'état APRÈS ajout.

Usage autonome :

    python3 scripts/sync-env.py            # synchronise
    python3 scripts/sync-env.py --check    # liste les clés manquantes sans écrire
"""
import os
import re
import secrets
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXAMPLE = os.path.join(ROOT, ".env.example")
ENV = os.path.join(ROOT, ".env")

KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")

# Couplages de valeurs : la clé reçoit la valeur d'une AUTRE clé si
# celle-ci est déjà connue (existante dans .env ou générée à cette
# exécution), sinon une valeur générée partagée. Voir .env.example.
COUPLED_WITH = {"LDAP_TEST_ADMIN_PASSWORD": "LDAP_BIND_PASSWORD"}


def parse_example(path):
    """Liste ordonnée de (commentaires, clé, valeur) depuis .env.example."""
    entries = []
    comments = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.rstrip("\n")
            match = KEY_RE.match(stripped)
            if match:
                key = match.group(1)
                value = stripped[len(key) + 1:].strip()
                entries.append((comments, key, value))
                comments = []
            elif stripped.startswith("#") or not stripped:
                comments.append(stripped)
            else:
                comments = []  # ligne non commentaire inattendue : ne rien attacher
    return entries


def parse_env_keys(path):
    keys = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            match = KEY_RE.match(line.rstrip("\n"))
            if match:
                key = match.group(1)
                keys[key] = line.strip()[len(key) + 1:]
    return keys


def gen_secret():
    return secrets.token_urlsafe(24)


def main():
    check_only = "--check" in sys.argv
    entries = parse_example(EXAMPLE)
    env_keys = parse_env_keys(ENV)

    missing = [(c, k, v) for (c, k, v) in entries if k not in env_keys]
    if not missing:
        print("✓ .env : toutes les clés de .env.example sont présentes")
        return 0

    if check_only:
        print(f"{len(missing)} clé(s) manquante(s) dans .env :")
        for _, key, _ in missing:
            print(f"  - {key}")
        return 1

    generated = {}  # clé -> valeur générée à CETTE exécution (couplages)

    def value_for(key, default):
        if default != "change-me":
            return default, "défaut .env.example"
        source = COUPLED_WITH.get(key)
        if source:
            # La clé source EXISTE (même vide, même "change-me" --
            # ex. LDAP_BIND_PASSWORD laissé au défaut osixia/openldap :
            # l'annuaire de test utilise alors ce défaut, et la clé
            # couplée doit le suivre pour rester FONCTIONNELLE) :
            # réutiliser sa valeur telle quelle, priorité absolue au
            # couplage fonctionnel.
            if source in env_keys:
                return env_keys[source], f"reprise de {source} (existant)"
            if source in generated:
                return generated[source], f"même valeur que {source}"
            generated[source] = gen_secret()
            return generated[source], f"générée (partagée avec {source})"
        value = gen_secret()
        generated[key] = value
        return value, "générée aléatoirement (secret interne)"

    lines = [
        "",
        f"# --- Clés ajoutées automatiquement par scripts/sync-env.py le {date.today().isoformat()}",
        "# (livraison #479 : nouvelles clés de .env.example absentes de ce .env --",
        "#  valeurs par défaut fonctionnelles, secrets internes générés aléatoirement ;",
        "#  voir ENV_CHANGELOG.md pour le détail de chaque livraison concernée) ---",
    ]
    report = []
    for comments, key, default in missing:
        value, origin = value_for(key, default)
        if comments:
            lines.extend(comments)
        lines.append(f"{key}={value}")
        report.append((key, origin))

    with open(ENV, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"🔧 sync-env : {len(missing)} clé(s) manquante(s) ajoutée(s) à .env :")
    for key, origin in report:
        print(f"   - {key} ({origin})")
    if any("générée" in origin for _, origin in report):
        print("   ⚠️  Des secrets internes ont été générés -- retrouvez-les en fin de .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
