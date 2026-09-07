"""
Parseur de la page d'état d'un onduleur (livraison #415, tuile « UPS »).

Version 0, demandée explicitement : « une requête HTTP du genre
http://user:password@ip/index.htm qui retourne la page en copie, d'où on
extrait une fiche d'état avec tous les champs présentés ». La page de
référence est celle d'une carte réseau Socomec (« UPS Management Web »,
NETYS RT) : un tableau HTML 4 où chaque section est un `<td CLASS="title">`
et chaque champ une paire de cellules `<td ALIGN="right">Libellé:</td>
<td CLASS="normal|bold">Valeur</td>`.

Le parseur est VOLONTAIREMENT générique sur cette forme (sections =
cellules de classe `title`, champs = cellule se terminant par « : » suivie
de la cellule non vide suivante) plutôt qu'une liste de libellés en dur :
une autre carte du même constructeur, ou une autre page du même firmware
(info_battery.htm, info_io.htm), donnera des libellés différents que l'on
veut voir apparaître SANS retoucher ce fichier. Les libellés connus reçoivent
en plus une clé normalisée stable (`input_voltage`, `battery_capacity`…)
pour la timeline ; les autres reçoivent une clé dérivée du libellé.

Pur : stdlib (`html.parser`), aucun réseau, testable avec la page copiée
(test_ups_parser.py).
"""
import re
import unicodedata
from html.parser import HTMLParser

# Libellés connus → clé stable. Tout libellé absent d'ici reçoit une clé
# dérivée (slug) -- jamais perdu, seulement moins joli.
KNOWN_KEYS = {
    "model": "model",
    "communication": "communication",
    "output source": "output_source",
    "battery": "battery",
    "input voltage": "input_voltage",
    "output voltage": "output_voltage",
    "input frequency": "input_frequency",
    "output frequency": "output_frequency",
    "output loading": "output_load",
    "battery capacity": "battery_capacity",
    "next power off time": "next_power_off",
    "next power on time": "next_power_on",
    "next test time": "next_test",
    "time to power off": "time_to_power_off",
}

# Champs d'ÉTAT (texte) dont une valeur autre que la valeur normale
# signale un problème -- base de l'indicateur global (`derive_state`).
STATE_FIELDS = {
    "communication": ("ok",),
    "output_source": ("normal",),
    "battery": ("normal",),
}

_NUMBER_RE = re.compile(r"^\s*([-+]?\d+(?:[.,]\d+)?)\s*([A-Za-z%°/]+)?\s*$")


def slugify(label):
    """« Output Loading » → `output_loading` ; accents retirés, tout ce qui
    n'est pas alphanumérique devient `_`."""
    text = unicodedata.normalize("NFKD", label or "").encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return text or "champ"


def field_key(label):
    clean = re.sub(r"\s+", " ", (label or "").strip().rstrip(":").strip()).lower()
    return KNOWN_KEYS.get(clean) or slugify(clean)


def parse_number(value):
    """« 236.0 V » → (236.0, "V") ; « 8 % » → (8.0, "%") ; texte → (None, None).
    La virgule décimale est acceptée (firmware localisé)."""
    if value is None:
        return None, None
    m = _NUMBER_RE.match(str(value))
    if not m:
        return None, None
    try:
        return float(m.group(1).replace(",", ".")), (m.group(2) or None)
    except ValueError:
        return None, None


class _CellCollector(HTMLParser):
    """Collecte les lignes de tableau sous forme de listes de cellules
    (attributs + texte aplati). Les balises imbriquées (b, a, img…) sont
    ignorées : seul le texte compte. Le `<title>` est gardé à part."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []          # [[{"attrs": {...}, "text": "..."}, ...], ...]
        self.title = ""
        self._row = None
        self._cell = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            if self._row is None:
                self._row = []
            self._cell = {"attrs": {k.lower(): (v or "") for k, v in attrs}, "text": ""}

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag in ("td", "th"):
            if self._cell is not None and self._row is not None:
                self._cell["text"] = re.sub(r"\s+", " ", self._cell["text"]).strip()
                self._row.append(self._cell)
            self._cell = None
        elif tag == "tr":
            if self._row is not None:
                # Une cellule ouverte sans fermeture (HTML 4 tolérant) est
                # rattachée à sa ligne plutôt que perdue.
                if self._cell is not None:
                    self._cell["text"] = re.sub(r"\s+", " ", self._cell["text"]).strip()
                    self._row.append(self._cell)
                    self._cell = None
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._cell is not None:
            self._cell["text"] += data


_SYSTEM_TIME_RE = re.compile(r"System Time:\s*(.+)$", re.IGNORECASE)


def parse_ups_page(html):
    """Fiche d'état.

    Renvoie :
      {
        "title": "UPS Management Web",
        "system_time": "09/07/2026 Monday 09:00:58" | None,
        "sections": [{"title": "UPS Status", "fields": [ {label, key, value, number, unit, css}, ... ]}, ...],
        "fields": {key: {label, value, number, unit, css, section}},
        "field_count": N,
      }
    Une page qui n'a pas cette forme renvoie sections/fields vides, jamais
    une exception -- c'est à l'appelant de décider que « 0 champ » est une
    erreur (voir poller).
    """
    parser = _CellCollector()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:  # noqa: BLE001 -- html.parser est tolérant, ceinture et bretelles
        pass

    sections = []
    fields = {}
    system_time = None
    current = None

    for row in parser.rows:
        texts = [c["text"] for c in row]
        # Heure système : cellule isolée « System Time: … »
        for t in texts:
            m = _SYSTEM_TIME_RE.search(t)
            if m and system_time is None:
                system_time = m.group(1).strip()
        title_cell = next((c for c in row if "title" in c["attrs"].get("class", "").lower().split()), None)
        if title_cell and title_cell["text"]:
            current = {"title": title_cell["text"], "fields": []}
            sections.append(current)
            continue
        # Champ : première cellule dont le texte finit par « : », valeur =
        # cellule suivante (même vide -- « Next Power Off Time: » sans
        # valeur est une information : rien de programmé).
        for i, cell in enumerate(row):
            text = cell["text"]
            if not text.endswith(":"):
                continue
            label = text.rstrip(":").strip()
            if not label or " " in label and len(label) > 40:
                continue
            value_cell = row[i + 1] if i + 1 < len(row) else {"attrs": {}, "text": ""}
            value = value_cell["text"]
            number, unit = parse_number(value)
            key = field_key(label)
            entry = {
                "label": label,
                "key": key,
                "value": value,
                "number": number,
                "unit": unit,
                "css": value_cell["attrs"].get("class", "").strip().lower() or None,
            }
            if current is None:
                current = {"title": "", "fields": []}
                sections.append(current)
            current["fields"].append(entry)
            if key not in fields:
                fields[key] = dict(entry, section=current["title"])
            break

    return {
        "title": re.sub(r"\s+", " ", parser.title).strip(),
        "system_time": system_time,
        "sections": sections,
        "fields": fields,
        "field_count": sum(len(s["fields"]) for s in sections),
    }


def derive_state(fields):
    """Indicateur global à partir des champs d'état connus :
      "ok"      -- tous les champs d'état connus ont leur valeur normale ;
      "alarm"   -- au moins un champ d'état connu a une autre valeur ;
      "unknown" -- aucun champ d'état connu dans la page.
    Renvoie (state, [raisons])."""
    reasons = []
    seen = 0
    for key, normal_values in STATE_FIELDS.items():
        entry = fields.get(key)
        if not entry:
            continue
        seen += 1
        value = (entry.get("value") or "").strip().lower()
        if value not in normal_values:
            reasons.append(f"{entry.get('label', key)} : {entry.get('value') or '(vide)'}")
    if seen == 0:
        return "unknown", reasons
    return ("alarm" if reasons else "ok"), reasons
