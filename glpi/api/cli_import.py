#!/usr/bin/env python3
"""
Import direct en ligne de commande (livraison #192) -- alternative à
la route `POST /import/excel` du service `glpi-api`, pour tester SANS
déployer tout le stack Docker (utile si la machine qui exécute ce
script a un accès réseau à GLPI que le stack supervision-si n'aurait
pas forcément).

Usage :
    python3 cli_import.py FICHIER.xlsx --base-url https://glpi.exemple.fr/apirest.php --user-token XXXX [--live] [--sheet Devices]

Par défaut : DRY-RUN (aucune écriture vers GLPI). Passer `--live` pour
écrire réellement -- TOUJOURS lancer sans `--live` d'abord et relire
le résumé affiché avant de passer en écriture réelle.
"""
import argparse
import sys

import glpi_client as glpi
import excel_import


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fichier", help="Chemin vers le fichier Excel à importer")
    parser.add_argument("--base-url", required=True, help="ex. https://glpi.exemple.fr/apirest.php")
    parser.add_argument("--app-token", default=None)
    parser.add_argument("--user-token", default=None)
    parser.add_argument("--login", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--sheet", default="Devices")
    parser.add_argument("--live", action="store_true", help="ÉCRIT réellement dans GLPI -- sans cette option, dry-run seulement")
    args = parser.parse_args()

    dry_run = not args.live
    client = glpi.GlpiClient(args.base_url, app_token=args.app_token)

    if not dry_run:
        if not args.user_token and not (args.login and args.password):
            print("Erreur : --user-token, ou --login + --password, requis pour un import réel (--live).", file=sys.stderr)
            sys.exit(1)
        try:
            client.init_session(args.login, args.password, user_token=args.user_token)
        except glpi.GlpiError as exc:
            print(f"Connexion à GLPI échouée : {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Connecté à {args.base_url} -- import RÉEL en cours (peut prendre plusieurs minutes)...")
    else:
        print("Mode DRY-RUN -- aucune écriture vers GLPI. Relancer avec --live une fois ce résumé vérifié.")

    try:
        summary = excel_import.import_excel(client, args.fichier, sheet_name=args.sheet, dry_run=dry_run)
    finally:
        if not dry_run:
            client.kill_session()

    print()
    print(f"=== Résumé ({'dry-run' if dry_run else 'RÉEL'}) ===")
    print(f"Créés : {len(summary['created'])}")
    print(f"Déjà présents (ignorés) : {len(summary['skipped_existing'])}")
    print(f"Erreurs : {len(summary['errors'])}")
    print(f"Avertissements à vérifier : {len(summary['warnings'])}")

    if summary["warnings"]:
        print("\n--- Avertissements ---")
        for w in summary["warnings"]:
            print(f"  - {w}")
    if summary["errors"]:
        print("\n--- Erreurs ---")
        for e in summary["errors"]:
            print(f"  - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
