#!/usr/bin/env python3
"""
Vérification de migration d'un fichier binaire (clé SSH) --
compagnon de `verify_env_migration.py`, backlog item 22 (livraison
#387). Compare OCTET PAR OCTET le fichier D'ORIGINE avec le résultat
d'un aller-retour chiffrement/déchiffrement -- une clé SSH n'a pas de
structure "clé=valeur" comme un .env, une comparaison binaire directe
est la seule vérification qui ait du sens ici.
"""
import sys


def main():
    if len(sys.argv) != 3:
        print("Usage : verify_file_migration.py <original> <déchiffré>", file=sys.stderr)
        sys.exit(2)

    original_path, decrypted_path = sys.argv[1], sys.argv[2]
    try:
        with open(original_path, "rb") as f:
            original = f.read()
    except OSError as exc:
        print(f"❌ Impossible de lire l'original ({original_path}) : {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(decrypted_path, "rb") as f:
            decrypted = f.read()
    except OSError as exc:
        print(f"❌ Impossible de lire le déchiffré ({decrypted_path}) : {exc}", file=sys.stderr)
        sys.exit(1)

    if original == decrypted:
        print(f"✅ TOUT CORRESPOND -- {len(original)} octet(s), identique bit à bit après l'aller-retour.")
        sys.exit(0)

    print(f"❌ ÉCART DÉTECTÉ -- {len(original)} octet(s) dans l'original, {len(decrypted)} dans le déchiffré -- NE PAS considérer la migration comme fiable.")
    sys.exit(1)


if __name__ == "__main__":
    main()
