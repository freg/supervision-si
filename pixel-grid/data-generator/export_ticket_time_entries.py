"""
Export des segments de temps sur tickets (`ticket_time_entries`) vers
un CSV compatible avec les loaders pixel-grid (livraison #219,
backlog item 10 -- 2e des sources nommées, "tickets"). Mêmes colonnes
que generate_csv.sh : ts,valeur,nom,type,data -- sans en-tête.

**Choix de la table source** : `ticket_time_entries` plutôt que
`tickets` directement -- vérifié en lisant tickets/api/app.py avant
d'écrire quoi que ce soit : cette table associe DÉJÀ un `start_ts`/
`end_ts` PRÉCIS (une vraie plage horaire, pas juste "créé le...") ET
un `technician_login` (livraison #115) -- exactement la combinaison
"utilisateur + plage horaire" demandée explicitement pour ce
calendrier partagé, contrairement à `tickets` seule qui n'a qu'un
horodatage de création et le DEMANDEUR (pas le technicien qui a
travaillé dessus).

**Différence avec l'export SSH (#218)** : ici, `start_ts` ET `end_ts`
sont TOUJOURS renseignés (colonnes NOT NULL) -- jamais de cas "encore
en cours" à gérer, chaque segment devient directement une paire
ouverture(1)/fermeture(0) complète.

**`nom` = le login du technicien** (ou "non_attribue" si NULL --
segments importés depuis un calendrier générique, ou créés avant la
livraison #115, jamais une valeur inventée) -- permet de cliquer un
technicien dans pixel-grid pour voir SA timeline complète (voir
"Vue timeline équipement" dans pixel-grid/README.md, qui fonctionne
par `nom` quel que soit ce que ce champ représente réellement).

Usage :
    python3 pixel-grid/data-generator/export_ticket_time_entries.py \\
        /chemin/vers/tickets.db activite_tickets.csv
"""
import csv
import json
import sqlite3
import sys


def export_rows(db_path):
    """Renvoie (rows, stats) -- même contrat que
    export_ssh_tunnel_activity.export_rows."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id, e.ticket_id, e.start_ts, e.end_ts, e.weight, e.technician_login,
                   t.subject
            FROM ticket_time_entries e
            JOIN tickets t ON t.id = e.ticket_id
            ORDER BY e.id
        """)
        entries = cur.fetchall()
    finally:
        conn.close()

    rows = []
    stats = {"total": len(entries), "attribues": 0, "non_attribues": 0}
    for entry in entries:
        nom = entry["technician_login"] or "non_attribue"
        if entry["technician_login"]:
            stats["attribues"] += 1
        else:
            stats["non_attribues"] += 1
        data = {
            "ticket_id": entry["ticket_id"],
            "subject": entry["subject"],
            "weight": entry["weight"],
        }
        data_json = json.dumps(data, ensure_ascii=False)
        rows.append((entry["start_ts"], 1, nom, "activite_ticket_temps", data_json))
        rows.append((entry["end_ts"], 0, nom, "activite_ticket_temps", data_json))

    rows.sort(key=lambda r: r[0])
    return rows, stats


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 export_ticket_time_entries.py <tickets.db> <sortie.csv>", file=sys.stderr)
        sys.exit(1)
    db_path, output_path = sys.argv[1], sys.argv[2]

    rows, stats = export_rows(db_path)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        for row in rows:
            writer.writerow(row)

    print(f"{len(rows)} ligne(s) écrite(s) dans {output_path} ({stats['total']} segment(s) de temps)", file=sys.stderr)
    print(f"  {stats['attribues']} segment(s) attribué(s) à un technicien, "
          f"{stats['non_attribues']} non attribué(s) (regroupés sous 'non_attribue')", file=sys.stderr)


if __name__ == "__main__":
    main()
