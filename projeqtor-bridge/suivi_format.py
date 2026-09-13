"""Format « suivi des demandes » — « Tableau des suivis des demandes » imposé par la
société (livraison #484). SOURCE UNIQUE du format, utilisée par
l'import (parse_workbook) ET l'export (build_workbook) : les deux ne
peuvent jamais dériver l'un de l'autre.

Format analysé sur le fichier réel « Tableau des suivis des
demandes.xlsx » :

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
from datetime import datetime, timedelta

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


# --- Import tolérant (livraison #497) ---------------------------------
# Constat de la personne : « l'import ne fonctionne pas » sur un fichier
# réel. Causes possibles couvertes ici, sans rien deviner en silence :
#   - fichier .xls (BIFF, Excel 97-2003) ou .csv et non .xlsx ;
#   - en-têtes ailleurs qu'en ligne 8, colonnes dans un autre ordre ou
#     nommées autrement (Objet / Demande / Priorité / Type / Description…) ;
#   - dates, durées et accomplissements saisis en TEXTE (« 12/09/2026 »,
#     « 3 j », « 50 % ») ou en numéro de série Excel.
# Une feuille sans en-têtes reconnaissables retombe sur le format imposé
# (ligne 8, colonnes A..O) — le comportement d'origine. Chaque
# décision (en-têtes trouvés en ligne N, colonne X ignorée) est
# renvoyée dans `erreurs`/`notes`, jamais silencieuse.

HEADER_SYNONYMS = {
    COL_ID: ["id", "n°", "no", "numero", "num", "ref", "reference"],
    COL_DATE: ["date de demande", "date demande", "date", "cree le", "creation", "date de creation"],
    COL_REQUESTER: ["demandeur", "demandeuse", "demande par", "utilisateur", "client", "contact", "nom"],
    COL_SUBJECT: ["sujet", "objet", "demande", "titre", "intitule", "probleme", "resume"],
    COL_PRIORITY: ["niveau de priorite", "priorite", "niveau", "urgence", "criticite"],
    COL_CATEGORY: ["categorie", "type", "domaine", "famille", "nature"],
    COL_DURATION: ["duree (j)", "duree", "duree j", "jours", "charge", "charge (j)", "estimation"],
    COL_COMMENT: ["commentaire", "commentaires", "description", "detail", "details", "observation", "observations"],
    COL_PROGRESS: ["accomplissement", "avancement", "progression", "realise", "% realise", "pourcentage"],
    COL_CLOSED: ["date de cloture", "date cloture", "cloture", "clôture", "date de fermeture", "fermeture", "termine le", "resolu le"],
}
DEFAULT_LETTERS = COL_TO_LETTER  # format imposé (ligne 8)
_EXCEL_EPOCH = datetime(1899, 12, 30)


def _cell_text(value):
    return normalize_key(value) if value is not None else ""


def _find_header(rows, max_scan=40):
    """(index de ligne, {clé: index de colonne}) ou (None, {}) — la ligne
    d'en-têtes est celle qui contient « sujet » (ou synonyme) ET
    « demandeur » ou « date de demande » (ou synonymes)."""
    for r, row in enumerate(rows[:max_scan]):
        cells = [_cell_text(v) for v in row]
        mapping = {}
        for key, names in HEADER_SYNONYMS.items():
            for c, text in enumerate(cells):
                if text and text in names and c not in mapping.values():
                    mapping[key] = c
                    break
        if COL_SUBJECT in mapping and (COL_REQUESTER in mapping or COL_DATE in mapping):
            return r, mapping
    return None, {}


def _to_datetime(value, errors, row, label):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20000 < float(value) < 80000:  # numéro de série Excel (1954..2119)
            return _EXCEL_EPOCH + timedelta(days=float(value))
        errors.append(f"ligne {row} : {label} invalide ({value!r}), laissée vide")
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    errors.append(f"ligne {row} : {label} invalide ({value!r}), laissée vide")
    return None


def _to_number(value, errors, row, label, percent=False):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    else:
        text = str(value).strip().lower().replace(",", ".").replace("%", "").replace("jours", "").replace("j", "").strip()
        try:
            num = float(text)
        except ValueError:
            errors.append(f"ligne {row} : {label} non numérique ({value!r}), laissé vide")
            return None
        if percent and isinstance(value, str) and "%" in value:
            num = num / 100.0
    if percent and num > 1.0:
        num = num / 100.0  # « 50 » saisi pour 50 %
    return int(num) if num == int(num) and not percent else num


def _rows_from_xlsx(content):
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    ws = wb[SHEET_NAME] if SHEET_NAME in wb.sheetnames else wb.worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)], ws.title


def _rows_from_xls(content):
    import xlrd  # .xls (BIFF) seulement — openpyxl ne les lit pas
    book = xlrd.open_workbook(file_contents=content)
    sheet = book.sheet_by_name(SHEET_NAME) if SHEET_NAME in book.sheet_names() else book.sheet_by_index(0)
    rows = []
    for r in range(sheet.nrows):
        row = []
        for c in range(sheet.ncols):
            cell = sheet.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_DATE:
                row.append(datetime(*xlrd.xldate_as_tuple(cell.value, book.datemode)))
            elif cell.ctype == xlrd.XL_CELL_EMPTY:
                row.append(None)
            elif cell.ctype == xlrd.XL_CELL_NUMBER:
                row.append(cell.value)
            else:
                row.append(cell.value)
        rows.append(row)
    return rows, sheet.name


def _rows_from_csv(content):
    import csv
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("encodage du CSV non reconnu")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = [[(c if c != "" else None) for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    return rows, "csv"


def load_rows(content, filename=None):
    """Bytes -> (lignes brutes, nom de feuille, format). Le format est
    reconnu à la SIGNATURE du fichier, jamais à l'extension seule."""
    if content[:4] == b"PK\x03\x04":
        rows, name = _rows_from_xlsx(content)
        return rows, name, "xlsx"
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        rows, name = _rows_from_xls(content)
        return rows, name, "xls"
    if filename and filename.lower().endswith((".xlsx", ".xls")):
        raise ValueError("le fichier n'est ni un xlsx ni un xls valide (signature inconnue)")
    rows, name = _rows_from_csv(content)
    return rows, name, "csv"


def parse_workbook(content, filename=None):
    """Bytes (xlsx, xls ou csv) -> (demandes, erreurs). Tolérant : une
    ligne incomplète ou invalide n'arrête jamais l'import, elle part
    dans `erreurs` avec son numéro de ligne (format imposé => saisi à
    la main par des humains, les lignes bancales EXISTENT). Les
    en-têtes sont cherchés par NOM (synonymes) ; à défaut, format
    imposé (ligne 8, colonnes A..O)."""
    demands, errors = [], []
    try:
        rows, sheet_name, fmt = load_rows(content, filename)
    except Exception as exc:  # noqa: BLE001 — fichier pas tableur du tout
        return [], [f"fichier illisible ({exc})"]

    header_idx, mapping = _find_header(rows)
    if header_idx is None:
        # format imposé : lettres fixes, en-têtes ligne 8
        col = lambda letter: ord(letter) - ord("A")  # noqa: E731
        mapping = {key: col(letter) for key, letter in DEFAULT_LETTERS.items()}
        first = FIRST_DATA_ROW - 1
        errors.append(f"en-têtes non reconnus (feuille « {sheet_name} », {fmt}) : format imposé supposé (ligne {HEADER_ROW}, colonnes A..O)")
    else:
        first = header_idx + 1
        missing = [k for k in (COL_DATE, COL_REQUESTER, COL_PRIORITY, COL_CATEGORY, COL_DURATION, COL_COMMENT, COL_PROGRESS, COL_CLOSED) if k not in mapping]
        if missing:
            errors.append(f"en-têtes ligne {header_idx + 1} (feuille « {sheet_name} », {fmt}) ; colonnes absentes, laissées vides : {', '.join(missing)}")

    def get(row, key):
        idx = mapping.get(key)
        if idx is None or idx >= len(row):
            return None
        value = row[idx]
        return value.strip() if isinstance(value, str) else value

    for i in range(first, len(rows)):
        row = rows[i]
        rownum = i + 1
        subject = get(row, COL_SUBJECT)
        date = get(row, COL_DATE)
        requester = get(row, COL_REQUESTER)
        if (subject in (None, "")) and (date in (None, "")) and (requester in (None, "")):
            continue  # ligne vide du tableau (le format en réserve ~100)
        if subject in (None, ""):
            errors.append(f"ligne {rownum} : sujet vide, ligne ignorée")
            continue
        ident = get(row, COL_ID)
        if isinstance(ident, float) and ident == int(ident):
            ident = int(ident)  # xls / xlsx rendent 7.0 pour 7
        demands.append({
            COL_ID: ident,
            COL_DATE: _to_datetime(date, errors, rownum, "date de demande"),
            COL_REQUESTER: (str(requester).strip() if requester not in (None, "") else ""),
            COL_SUBJECT: str(subject).strip(),
            COL_PRIORITY: str(get(row, COL_PRIORITY) or "").strip(),
            COL_CATEGORY: str(get(row, COL_CATEGORY) or "").strip(),
            COL_DURATION: _to_number(get(row, COL_DURATION), errors, rownum, "durée"),
            COL_COMMENT: str(get(row, COL_COMMENT) or "").strip(),
            COL_PROGRESS: _to_number(get(row, COL_PROGRESS), errors, rownum, "accomplissement", percent=True),
            COL_CLOSED: _to_datetime(get(row, COL_CLOSED), errors, rownum, "date de clôture"),
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
