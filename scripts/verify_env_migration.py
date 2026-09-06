#!/usr/bin/env python3
"""
Vérification de migration .env -> .env.encrypted (backlog item 22,
livraison #386). Compare le .env D'ORIGINE avec la sortie de
`secrets_tool.py decrypt-env` (lignes `export CLE='valeur'`, lues sur
stdin) -- clé par clé, valeur par valeur. Réutilise `parse_env_file`
de `check-env.py` plutôt que d'écrire un second analyseur .env.

Sortie : "TOUT CORRESPOND" et code 0 si chaque clé du .env d'origine
a EXACTEMENT la même valeur après le aller-retour chiffrement/
déchiffrement -- sinon, liste précise des clés en écart et code 1.
Jamais un message vague ("échec") sans dire QUELLE clé pose problème.
"""
import shlex
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# "check-env" contient un tiret -- pas un nom de module Python valide
# pour un import direct -- chargé explicitement par chemin de fichier
# ci-dessous plutôt que par nom.
import importlib.util
spec = importlib.util.spec_from_file_location("check_env", os.path.join(HERE, "check-env.py"))
check_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_env)


def parse_decrypted_exports(text):
    """Parse les lignes 'export CLE=valeur' (valeur shell-quotée par
    shlex.quote côté decrypt-env) -- utilise shlex pour un dé-quotage
    SÛR, jamais un simple split/strip qui casserait sur une valeur
    contenant des espaces ou des guillemets."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("export "):
            continue
        rest = line[len("export "):]
        key, _, quoted_value = rest.partition("=")
        key = key.strip()
        if not key:
            continue
        try:
            parts = shlex.split(quoted_value)
            value = parts[0] if parts else ""
        except ValueError:
            value = quoted_value  # dé-quotage impossible -- valeur brute conservée telle quelle, jamais une exception ici
        values[key] = value
    return values


def main():
    if len(sys.argv) != 2:
        print("Usage : verify_env_migration.py <chemin .env d'origine>  (lignes déchiffrées attendues sur stdin)", file=sys.stderr)
        sys.exit(2)

    original_path = sys.argv[1]
    original = check_env.parse_env_file(original_path)
    decrypted = parse_decrypted_exports(sys.stdin.read())

    missing_in_decrypted = sorted(set(original) - set(decrypted))
    extra_in_decrypted = sorted(set(decrypted) - set(original))
    mismatched = sorted(k for k in (set(original) & set(decrypted)) if original[k] != decrypted[k])

    if not missing_in_decrypted and not extra_in_decrypted and not mismatched:
        print(f"✅ TOUT CORRESPOND -- {len(original)} clé(s) vérifiée(s), aller-retour chiffrement/déchiffrement fidèle à 100%.")
        sys.exit(0)

    print("❌ ÉCART(S) DÉTECTÉ(S) -- NE PAS considérer la migration comme fiable :")
    if missing_in_decrypted:
        print(f"  - Absente(s) après déchiffrement : {', '.join(missing_in_decrypted)}")
    if extra_in_decrypted:
        print(f"  - En trop après déchiffrement (jamais dans l'original) : {', '.join(extra_in_decrypted)}")
    if mismatched:
        print(f"  - Valeur DIFFÉRENTE après aller-retour : {', '.join(mismatched)}")
    sys.exit(1)


if __name__ == "__main__":
    main()
