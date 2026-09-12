"""Format OPTLINE — « Tableau des suivis des demandes » imposé par la
société (livraison #484). SOURCE UNIQUE du format, utilisée par
l'import (parse_workbook) ET l'export (build_workbook) : les deux ne
peuvent jamais dériver l'un de l'autre.

Format analysé sur le fichier réel « Copie de Tableau des suivis des
demandes_Support OPTLINE.xlsx » :

- titre « Synthèse des demandes » en B7, fusionné B7:L7 ;
- en-têtes ligne 8 (fond rouge, gras) : A=Id, B=Date de demande,
  C=Demandeur, D=Sujet, E=Niveau de priorité, F=Catégorie,
  G=Durée (j), H=Commentaire, I=Accomplissement, J=FR, K=Reste,
  L=Reste, M=Jours restants, (N=vide), O=Date de cloture ;
- données à partir de la ligne 9, dans un tableau Excel « Tableau1 » ;
- colonnes calculées (formules) : J=I, K=durée*(1-avancement),
  L=SUM(I:J)/2, M=(100%-L)*durée ;
- listes de référence HORS du tableau, colonnes N/P/Q :
  N9:N13 priorités, P7:P13 catégories, Q7+ demandeurs — ciblées par
  des validations de données (listes déroulantes) sur E, F, C.

Une « demande » manipulée ici est un dict plat (clés = constantes
COL_* ci-dessous) — jamais d'objet métier pour si peu, le module
entier est un pont de traduction.
"""
import io
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

# --- Structure du tableau ------------------------------------------------

SHEET_NAME = "Feuil1"
TITLE_CELL = "B7"
TITLE_TEXT = "Synthèse des demandes"
TITLE_MERGE = "B7:L7"
HEADER_ROW = 8
FIRST_DATA_ROW = 9

# (colonne, en-tête). L'ordre EST le format — ne jamais réordonner.
COLUMNS = [
    ("A", "Id"),
    ("B", "Date de demande"),
    ("C", "Demandeur"),
    ("D", "Sujet"),
    ("E", "Niveau de priorité"),
    ("F", "Catégorie"),
    ("G", "Durée (j)"),
    ("H", "Commentaire"),
    ("I", "Accomplissement"),
    ("O", "Date de cloture"),
]
# Colonnes calculées du fichier d'origine (J/K/L/M) — régénérées en
# formules A1 classiques (fonctionnellement identiques aux références
# structurées Tableau1 de l'original, sans le risque de corruption
# openpyxl qu'elles posent à l'écriture). Leurs EN-TÊTES font partie
# du format (une table Excel exige une chaîne par colonne, sinon le
# fichier est « illisible » à l'ouverture) — écrites comme les autres.
FORMULA_HEADERS = [("J", "FR"), ("K", "Reste"), ("L", "Reste"), ("M", "Jours restants")]
FORMULAS = {
    "J": "=I{r}",
    "K": "=G{r}*(1-I{r})",
    "L": "=SUM(I{r}:J{r})/2",
    "M": "=(100%-L{r})*G{r}",
}

# Colonnes des listes de référence (hors tableau) et leurs valeurs
# PAR DÉFAUT — reprises EXACTEMENT du fichier imposé, y compris
# l'espace terminal de « accessoire » (fait partie des données
# d'origine ; la correspondance ignore casse/accents/espaces, voir
# normalize_key).
REF_PRIORITY_COL = "N"
REF_CATEGORY_COL = "P"
REF_REQUESTER_COL = "Q"
REF_FIRST_ROW = 7  # N et P commencent ligne 7, Q aussi (fichier réel)
DEFAULT_PRIORITIES = ["Urgent", "J+1", "J+2", "J+5", "Pas urgent"]
DEFAULT_CATEGORIES = ["bureautique", "poste de travail", "réseau", "logiciel", "mail", "service en ligne", "accessoire "]
DEFAULT_REQUESTERS = []  # propre à chaque organisation — jamais codé en dur

# Validations de données du fichier d'origine (plages identiques).
DV_PRIORITY_RANGE = "$N$9:$N$13"
DV_CATEGORY_RANGE = "$P:$P"
DV_REQUESTER_RANGE = "$Q:$Q"

HEADER_FILL = PatternFill("solid", fgColor="FFFF0000")
HEADER_FONT = Font(bold=True)

# Clés du dict « demande » (identiques aux en-têtes, en snake_case).
COL_ID = "id"
COL_DATE = "date_demande"       # datetime
COL_REQUESTER = "demandeur"     # texte
COL_SUBJECT = "sujet"           # texte
COL_PRIORITY = "priorite"       # texte
COL_CATEGORY = "categorie"      # texte
COL_DURATION = "duree_j"        # nombre
COL_COMMENT = "commentaire"     # texte
COL_PROGRESS = "accomplissement"  # fraction 0..1 (convention du fichier)
COL_CLOSED = "date_cloture"     # datetime ou None

COL_TO_LETTER = {
    COL_ID: "A", COL_DATE: "B", COL_REQUESTER: "C", COL_SUBJECT: "D",
    COL_PRIORITY: "E", COL_CATEGORY: "F", COL_DURATION: "G",
    COL_COMMENT: "H", COL_PROGRESS: "I", COL_CLOSED: "O",
}


def normalize_key(value):
    """Clé de correspondance pour les référentiels : casse, espaces
    (y compris terminaux, cf. « accessoire ») et accents ignorés —
    jamais de doublon « Réseau » / « réseau » à l'import."""
    if value is None:
        return ""
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(c for c in text if not unicodedata.combining(c)).strip().lower()


def parse_workbook(content):
    """Bytes xlsx -> (demandes, erreurs). Tolérant : une ligne
    incomplète ou invalide n'arrête jamais l'import, elle part dans
    `erreurs` avec son numéro de ligne (format imposé => saisi à la
    main par des humains, les lignes bancales EXISTENT)."""
    demands, errors = [], []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    except Exception as exc:  # noqa: BLE001 — fichier pas xlsx du tout
        return [], [f"fichier illisible ({exc})"]
    ws = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else wb.worksheets[0]

    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        subject = ws[f"D{row}"].value
        date = ws[f"B{row}"].value
        requester = ws[f"C{row}"].value
        if subject is None and date is None and requester is None:
            continue  # ligne vide du tableau (le format en réserve ~100)
        if subject is None or str(subject).strip() == "":
            errors.append(f"ligne {row} : sujet vide, ligne ignorée")
            continue
        if date is not None and not isinstance(date, datetime):
            errors.append(f"ligne {row} : date de demande invalide ({date!r}), laissée vide")
            date = None
        closed = ws[f"O{row}"].value
        if closed is not None and not isinstance(closed, datetime):
            errors.append(f"ligne {row} : date de clôture invalide ({closed!r}), ignorée")
            closed = None
        duration = ws[f"G{row}"].value
        if duration is not None and not isinstance(duration, (int, float)):
            errors.append(f"ligne {row} : durée non numérique ({duration!r}), laissée vide")
            duration = None
        progress = ws[f"I{row}"].value
        if progress is not None and not isinstance(progress, (int, float)):
            progress = None
        demands.append({
            COL_ID: ws[f"A{row}"].value,
            COL_DATE: date,
            COL_REQUESTER: (str(requester).strip() if requester else ""),
            COL_SUBJECT: str(subject).strip(),
            COL_PRIORITY: (str(ws[f"E{row}"].value or "").strip()),
            COL_CATEGORY: (str(ws[f"F{row}"].value or "").strip()),
            COL_DURATION: duration,
            COL_COMMENT: (str(ws[f"H{row}"].value or "").strip()),
            COL_PROGRESS: progress,
            COL_CLOSED: closed,
        })
    return demands, errors


def build_workbook(demands, priorities=None, categories=None, requesters=None):
    """(demandes, référentiels) -> bytes xlsx au format imposé.

    Les listes de référence sont celles VIVANTES du système (passées
    par l'appelant — lues de ProjeQtOr), jamais les défauts codés ici ;
    les défauts ne servent qu'au tout premier export sans référentiel.
    """
    priorities = priorities or DEFAULT_PRIORITIES
    categories = categories or DEFAULT_CATEGORIES
    requesters = requesters if requesters is not None else DEFAULT_REQUESTERS

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    ws[TITLE_CELL] = TITLE_TEXT
    ws[TITLE_CELL].font = Font(bold=True, size=14)
    ws.merge_cells(TITLE_MERGE)

    for letter, header in COLUMNS + FORMULA_HEADERS:
        cell = ws[f"{letter}{HEADER_ROW}"]
        cell.value = header
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT

    # Listes de référence (hors tableau) — mêmes colonnes que l'original.
    for i, value in enumerate(priorities):
        ws[f"{REF_PRIORITY_COL}{REF_FIRST_ROW + 2 + i}"] = value  # N9+
    for i, value in enumerate(categories):
        ws[f"{REF_CATEGORY_COL}{REF_FIRST_ROW + i}"] = value      # P7+
    for i, value in enumerate(requesters):
        ws[f"{REF_REQUESTER_COL}{REF_FIRST_ROW + i}"] = value     # Q7+

    dv_priority = DataValidation(type="list", formula1=DV_PRIORITY_RANGE, allow_blank=True)
    dv_priority.add(f"E{FIRST_DATA_ROW}:E1048576")
    ws.add_data_validation(dv_priority)
    dv_category = DataValidation(type="list", formula1=DV_CATEGORY_RANGE, allow_blank=True)
    dv_category.add(f"F{FIRST_DATA_ROW}:F1048576")
    ws.add_data_validation(dv_category)
    dv_requester = DataValidation(type="list", formula1=DV_REQUESTER_RANGE, allow_blank=True)
    dv_requester.add(f"C{FIRST_DATA_ROW}:C{FIRST_DATA_ROW + 95}")
    ws.add_data_validation(dv_requester)

    last_row = FIRST_DATA_ROW - 1
    for i, demand in enumerate(demands):
        row = FIRST_DATA_ROW + i
        last_row = row
        for key, letter in COL_TO_LETTER.items():
            value = demand.get(key)
            if value is not None and value != "":
                ws[f"{letter}{row}"] = value
        for letter, template in FORMULAS.items():
            ws[f"{letter}{row}"] = template.format(r=row)
        if demand.get(COL_DATE):
            ws[f"B{row}"].number_format = "DD/MM/YYYY"
        if demand.get(COL_CLOSED):
            ws[f"O{row}"].number_format = "DD/MM/YYYY"

    # Tableau « Tableau1 » : A8:K104 dans le fichier d'origine (les
    # colonnes L à O restent HORS du tableau — vérifié dans son XML).
    # Même amplitude de lignes réservées, même hors-données ; jamais
    # réduite aux seules lignes exportées (la personne complète le
    # fichier à la main ensuite, c'est le but du format imposé).
    table_last = max(last_row, FIRST_DATA_ROW + 95)
    table = Table(displayName="Tableau1", ref=f"A{HEADER_ROW}:K{table_last}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
