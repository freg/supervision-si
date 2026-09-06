"""
Export de l'activité des tunnels/montages SSH vers un CSV compatible
avec les loaders pixel-grid (livraison #218, backlog item 10 --
"calendrier partagé... activité tunnels SSH" comme l'une des sources
explicitement nommées). Mêmes colonnes que generate_csv.sh :
ts,valeur,nom,type,data -- sans en-tête.

**Décision de portée prise pour avancer** (l'item d'origine listait
3 aspects "à trancher ensemble" : quelles sources précisément,
comment agréger entre services, réutiliser pixel-grid tel quel ou
construire un outil dédié) :
- Réutilise pixel-grid TEL QUEL (le mécanisme de chargement par
  lot déjà en place, `load_sqlite.sh`/`load_postgres.sh` --
  **découverte en le vérifiant** : pixel-grid n'a PAS d'API
  d'ingestion temps réel, "l'écriture ne passe que par generate.sh"
  -- ce script suit donc EXACTEMENT le même motif que
  `parse_zenoss_emails.py`, un export PAR LOT à rejouer
  périodiquement, jamais un flux continu).
- Cette livraison couvre UNE SEULE des sources nommées (activité
  tunnels SSH) -- la plus simple à connecter, une donnée DÉJÀ bien
  structurée depuis #210 (`ssh_credential_usage_history`). Tickets et
  GED restent pour une prochaine étape, une fois ce premier
  branchement validé.
- **La dimension "utilisateur"** demandée explicitement ("TOUTES les
  données liées à un utilisateur ET une date") reste HORS PORTÉE de
  cette livraison -- vérifié en lisant `pixel-grid/README.md` : la
  table `users` n'y est qu'une ébauche structurelle ("pas
  d'interface associée à ce stade"), aucun filtrage par utilisateur
  n'existe réellement aujourd'hui. `created_by` EST inclus dans le
  sous-arbre `data` de chaque événement (voir plus bas) pour ne pas
  perdre l'information, mais son EXPLOITATION (filtrage réel dans
  l'interface) reste à construire séparément, dans pixel-grid
  lui-même.

**Modélisation retenue** : chaque tentative RÉUSSIE
(`success=1` dans `ssh_credential_usage_history`) devient une PAIRE
`valeur=1` (ouverture, à `started_at`) / `valeur=0` (fermeture, à
`ended_at`, SEULEMENT si renseigné) -- exploite directement
l'appariement automatique déjà en place côté pixel-grid pour les
types `integer_enum` (voir sa docstring : "Un incident sans
résolution trouvée reste marqué EN COURS"). Les tentatives EN ÉCHEC
(`success=0`) sont délibérément EXCLUES de cette paire (jamais de
"valeur=1" fantôme pour une connexion qui n'a en réalité jamais été
établie) -- comptées séparément dans le résumé affiché en sortie,
pour ne pas les perdre silencieusement de vue, mais pas modélisées
comme un incident ouvert/fermé.

Usage :
    python3 pixel-grid/data-generator/export_ssh_tunnel_activity.py \\
        /chemin/vers/ssh-tunnels.db activite_tunnels_ssh.csv
"""
import calendar
import json
import sqlite3
import sys
import time


def _to_epoch(iso_timestamp):
    """'2026-09-02T20:14:34Z' -> epoch UTC (secondes) -- même format
    que now_iso() dans tunnels_store.py, jamais une supposition sur
    un format différent. `calendar.timegm` (pas `time.mktime`) --
    interprète le `struct_time` comme UTC directement, sans jamais
    passer par le fuseau LOCAL de la machine qui exécute ce script
    (mktime + un correctif manuel serait plus fragile, sensible à
    l'heure d'été)."""
    return calendar.timegm(time.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%SZ"))


def export_rows(db_path):
    """Renvoie (rows, stats) -- rows : liste de tuples
    (ts, valeur, nom, type, data_json) prêts à écrire en CSV. stats :
    dict résumant ce qui a été inclus/exclu, pour un message de sortie
    honnête (jamais un simple "terminé" sans détail)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT h.id, h.connection_id, h.action_type, h.auth_method, h.success,
                   h.started_at, h.ended_at, h.created_by, c.label
            FROM ssh_credential_usage_history h
            JOIN ssh_connections c ON c.id = h.connection_id
            ORDER BY h.id
        """)
        entries = cur.fetchall()
    finally:
        conn.close()

    rows = []
    stats = {"total": len(entries), "reussies_ouvertes": 0, "reussies_fermees": 0, "echecs_exclus": 0, "toujours_en_cours": 0}
    for entry in entries:
        if not entry["success"]:
            stats["echecs_exclus"] += 1
            continue
        nom = entry["label"]
        data = {
            "action_type": entry["action_type"],
            "auth_method": entry["auth_method"],
            "created_by": entry["created_by"],
        }
        data_json = json.dumps(data, ensure_ascii=False)
        rows.append((_to_epoch(entry["started_at"]), 1, nom, "activite_tunnel_ssh", data_json))
        stats["reussies_ouvertes"] += 1
        if entry["ended_at"]:
            rows.append((_to_epoch(entry["ended_at"]), 0, nom, "activite_tunnel_ssh", data_json))
            stats["reussies_fermees"] += 1
        else:
            stats["toujours_en_cours"] += 1

    rows.sort(key=lambda r: r[0])
    return rows, stats


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 export_ssh_tunnel_activity.py <ssh-tunnels.db> <sortie.csv>", file=sys.stderr)
        sys.exit(1)
    db_path, output_path = sys.argv[1], sys.argv[2]

    rows, stats = export_rows(db_path)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        import csv
        writer = csv.writer(f, lineterminator="\n")
        for row in rows:
            writer.writerow(row)

    print(f"{len(rows)} ligne(s) écrite(s) dans {output_path}", file=sys.stderr)
    print(f"  {stats['reussies_ouvertes']} connexion(s) réussie(s) ({stats['reussies_fermees']} déjà fermées, "
          f"{stats['toujours_en_cours']} toujours en cours ou jamais fermées proprement)", file=sys.stderr)
    print(f"  {stats['echecs_exclus']} échec(s) exclu(s) (jamais modélisés comme une connexion ouverte)", file=sys.stderr)


if __name__ == "__main__":
    main()
