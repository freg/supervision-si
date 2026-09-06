"""
Export des liens de documents GED (`document_links`) vers un CSV
compatible avec les loaders pixel-grid (livraison #219, backlog item
10 -- 3e et dernière des sources nommées, "documents ged"). Mêmes
colonnes que generate_csv.sh : ts,valeur,nom,type,data -- sans
en-tête.

**Choix de la table source** : `document_links` (métadonnées LOCALES
de `ged-api`) plutôt que les documents Mayan eux-mêmes -- vérifié en
lisant `ged/api/documents_store.py`/`mayan_client.py` avant d'écrire
quoi que ce soit : les documents VIVENT dans Mayan (système externe,
#157-168), `ged-api` n'a AUCUNE table locale de documents, seulement
les LIENS (document ↔ ticket/autre entité). `mayan_client.py` n'a
d'ailleurs aucune fonction de LISTE de documents (seulement
`get_document(id)`, un document précis à la fois) -- lister tous les
documents demanderait une nouvelle capacité côté Mayan, jamais
construite ici. `document_links` a en revanche déjà `linked_by`
(qui) et `linked_at` (quand) -- exactement la combinaison
utilisateur+temps recherchée, sans le moindre appel réseau à Mayan.

**Différence de modélisation avec SSH (#218) et tickets (#219)** : un
lien est un ÉVÉNEMENT PONCTUEL (pas de "début"/"fin" -- créer un lien
n'est pas une action qui "se termine" plus tard), contrairement à une
connexion SSH ou un segment de temps. Représenté ici par une SEULE
ligne `valeur=1` par lien, JAMAIS de `valeur=0` correspondant --
pixel-grid affichera ces entrées comme "EN COURS" (son comportement
par défaut pour un `valeur=1` sans résolution trouvée, voir sa
docstring) -- imprécis sémantiquement pour un événement ponctuel,
mais reste visuellement exploitable (répéré dans le temps) sans
inventer un faux "événement de fermeture". À revoir si ça s'avère
gênant en usage réel (passe d'optimisation à venir).

**`nom` = `linked_by`** (ou "non_attribue" si NULL) -- même
raisonnement que pour les tickets : permet de cliquer un utilisateur
pour voir SES liaisons de documents dans le temps.

Usage :
    python3 pixel-grid/data-generator/export_document_links.py \\
        /chemin/vers/ged.db activite_ged.csv
"""
import csv
import json
import sqlite3
import sys
import time


def _to_epoch(iso_timestamp):
    """Même format que linked_at (voir documents_store.py,
    now_iso()-style) -- 'YYYY-MM-DDTHH:MM:SSZ' -> epoch UTC."""
    import calendar
    return calendar.timegm(time.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%SZ"))


def export_rows(db_path):
    """Renvoie (rows, stats) -- même contrat que les deux autres
    exports de ce dossier (SSH, tickets)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, document_id, linked_type, linked_id, linked_by, linked_at FROM document_links ORDER BY id")
        entries = cur.fetchall()
    finally:
        conn.close()

    rows = []
    stats = {"total": len(entries), "attribues": 0, "non_attribues": 0}
    for entry in entries:
        nom = entry["linked_by"] or "non_attribue"
        if entry["linked_by"]:
            stats["attribues"] += 1
        else:
            stats["non_attribues"] += 1
        data = {
            "document_id": entry["document_id"],
            "linked_type": entry["linked_type"],
            "linked_id": entry["linked_id"],
        }
        data_json = json.dumps(data, ensure_ascii=False)
        rows.append((_to_epoch(entry["linked_at"]), 1, nom, "activite_document_ged", data_json))

    rows.sort(key=lambda r: r[0])
    return rows, stats


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 export_document_links.py <ged.db> <sortie.csv>", file=sys.stderr)
        sys.exit(1)
    db_path, output_path = sys.argv[1], sys.argv[2]

    rows, stats = export_rows(db_path)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        for row in rows:
            writer.writerow(row)

    print(f"{len(rows)} ligne(s) écrite(s) dans {output_path} ({stats['total']} lien(s) de document)", file=sys.stderr)
    print(f"  {stats['attribues']} lien(s) attribué(s) à un utilisateur, "
          f"{stats['non_attribues']} non attribué(s) (regroupés sous 'non_attribue')", file=sys.stderr)


if __name__ == "__main__":
    main()
