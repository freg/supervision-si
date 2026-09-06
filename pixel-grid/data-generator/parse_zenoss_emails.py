"""
Parseur d'e-mails d'alerte Zenoss (backlog ou export Thunderbird) vers
un CSV compatible avec les loaders pixel-grid (mêmes colonnes que
generate_csv.sh : ts,valeur,nom,type,data — sans en-tête).

Format d'entrée attendu : le template de notification standard Zenoss,
tel qu'exporté en texte depuis Thunderbird (sélection des messages +
copier-coller). Deux formes reconnues :

  [Site A] <équipement> <message> exploitation@exemple.fr

  Alert generated at YYYY/MM/DD HH:MM:SS.000 Equipement : <équipement>
  Message : <message> Localisation : <loc> Composants : <comp>
  Severite : <sévérité>

  [Site A] clear: <équipement> <message de résolution> exploitation@exemple.fr

  Event Cleared At: YYYY/MM/DD HH:MM:SS.000 Alert generated at
  YYYY/MM/DD HH:MM:SS.000 Clear Message : <msg> Message : <msg original>
  Localisation : <loc> Composants : <comp> Severite : <sévérité>

Règle de conversion (type "alerte_zenoss_email", kind=integer_enum,
donc directement compatible avec la logique de coloration existante) :
  - Un mail d'alerte active (pas "clear:")  -> valeur=1 (erreur),
    horodaté à "Alert generated at".
  - Un mail "clear:" (résolution)           -> valeur=0 (normal),
    horodaté à "Event Cleared At" (le moment où CE mail est parti).

Les horodatages du texte n'indiquent pas de fuseau — traités tels
quels comme UTC (hypothèse à corriger si tes mails sont en heure
locale et que ça compte pour ton usage).

Usage :
    python3 parse_zenoss_emails.py export.txt alertes.csv
"""
import csv
import json
import re
import sys
from datetime import datetime, timezone

ENTRY_RE = re.compile(
    r"\[Site A\]\s*(?P<clear_prefix>clear:\s*)?.+?\s+exploitation@exemple\.fr"
    r"\s*\n\s*\n\s*(?P<body>.+?)(?=\n\s*\[Site A\]|\Z)",
    re.DOTALL,
)

CLEARED_BODY_RE = re.compile(
    r"Event Cleared At:\s*(?P<cleared_at>[\d/:. ]+?)\s+"
    r"Alert generated at\s*(?P<alert_at>[\d/:. ]+?)\s+"
    r"Clear Message\s*:\s*(?P<clear_msg>.+?)\s+"
    r"Message\s*:\s*(?P<msg>.+?)\s+"
    r"Localisation\s*:\s*(?P<loc>.*?)\s+"
    r"Composants\s*:\s*(?P<comp>.*?)"
    r"(?:\s*Severite\s*:\s*(?P<sev>\S+))?\s*$",
    re.DOTALL,
)

ACTIVE_BODY_RE = re.compile(
    r"Alert generated at\s*(?P<alert_at>[\d/:. ]+?)\s+"
    r"Equipement\s*:\s*(?P<equip>.+?)\s+"
    r"Message\s*:\s*(?P<msg>.+?)\s+"
    r"Localisation\s*:\s*(?P<loc>.*?)\s+"
    r"Composants\s*:\s*(?P<comp>.*?)"
    r"(?:\s*Severite\s*:\s*(?P<sev>\S+))?\s*$",
    re.DOTALL,
)

SUBJECT_RE = re.compile(r"\[Site A\]\s*(?:clear:\s*)?(?P<device>\S+)")


def parse_timestamp(raw):
    """'2026/08/11 10:30:12.000' -> epoch UTC (secondes)."""
    dt = datetime.strptime(raw.strip(), "%Y/%m/%d %H:%M:%S.%f")
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def parse_entries(text):
    rows = []
    skipped = 0

    for match in ENTRY_RE.finditer(text):
        is_clear = bool(match.group("clear_prefix"))
        body = match.group("body")
        subject_match = SUBJECT_RE.search(match.group(0))
        device_from_subject = subject_match.group("device") if subject_match else None

        if is_clear:
            m = CLEARED_BODY_RE.search(body)
            if not m:
                skipped += 1
                continue
            ts = parse_timestamp(m.group("cleared_at"))
            valeur = 0
            equip = device_from_subject or "inconnu"
            data = {
                "message": m.group("msg").strip(),
                "clear_message": m.group("clear_msg").strip(),
                "localisation": m.group("loc").strip(),
                "composants": m.group("comp").strip(),
                "severite": (m.group("sev") or "Inconnue").strip(),
                "alert_generated_at": m.group("alert_at").strip(),
                "resolu": True,
            }
        else:
            m = ACTIVE_BODY_RE.search(body)
            if not m:
                skipped += 1
                continue
            ts = parse_timestamp(m.group("alert_at"))
            valeur = 1
            equip = m.group("equip").strip() or device_from_subject or "inconnu"
            data = {
                "message": m.group("msg").strip(),
                "localisation": m.group("loc").strip(),
                "composants": m.group("comp").strip(),
                "severite": (m.group("sev") or "Inconnue").strip(),
                "resolu": False,
            }

        rows.append((ts, valeur, equip, "alerte_zenoss_email", json.dumps(data, ensure_ascii=False)))

    return rows, skipped


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 parse_zenoss_emails.py <export.txt> <sortie.csv>", file=sys.stderr)
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]
    text = open(input_path, "r", encoding="utf-8", errors="replace").read()

    rows, skipped = parse_entries(text)
    rows.sort(key=lambda r: r[0])

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        for row in rows:
            writer.writerow(row)

    print(f"{len(rows)} entrées écrites dans {output_path}", file=sys.stderr)
    if skipped:
        print(f"{skipped} bloc(s) non reconnus (format inattendu), ignorés", file=sys.stderr)
    if rows:
        valeur1 = sum(1 for r in rows if r[1] == 1)
        print(f"  dont {valeur1} alerte(s) active(s) et {len(rows) - valeur1} résolution(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
