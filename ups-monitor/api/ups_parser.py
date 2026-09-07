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
    # Net Vision v6 (#417) -- libellés français de la « Synthèse ASI »
    "état de l'asi": "ups_state",
    "etat de l'asi": "ups_state",
    "taux de charge utilisation": "output_load",
    "tension de sortie": "output_voltage",
    "capacité batterie": "battery_capacity",
    "capacite batterie": "battery_capacity",
    "autonomie batterie": "battery_runtime",
    "tension batterie": "battery_voltage",
    "tension d'entrée redresseur": "input_voltage",
    "tension d'entree redresseur": "input_voltage",
    "tension d'entrée": "input_voltage",
    "température": "temperature",
    "temperature": "temperature",
    "date net vision": "device_date",
    "heure net vision": "device_time",
    "modèle": "model",
    "numéro de série": "serial_number",
}

# Champs d'ÉTAT (texte) dont une valeur autre que la valeur normale
# signale un problème -- base de l'indicateur global (`derive_state`).
STATE_FIELDS = {
    "communication": ("ok",),
    "output_source": ("normal",),
    "battery": ("normal",),
    # Net Vision v6 : « Utilisation sur Onduleur » = fonctionnement normal
    # d'un onduleur on-line (double conversion) ; « sur Batterie »,
    # « sur Bypass », « Défaut »… = alarme.
    "ups_state": ("utilisation sur onduleur", "normal", "fonctionnement normal", "on line", "online", "on inverter"),
}

# Unités reconnues dans un libellé « Libellé (unité) » (Net Vision v6) ;
# tout autre contenu entre parenthèses (« dd/mm/yyyy ») est un format,
# retiré du libellé mais jamais pris pour une unité.
_LABEL_UNITS = {"%", "v", "a", "w", "va", "kva", "kw", "kvar", "hz", "min", "minutes", "s", "sec", "°c", "oc", "c", "ah", "wh", "kwh", "h"}


def split_label_unit(label):
    """« Taux de charge Utilisation (%) » → (« Taux de charge Utilisation », « % ») ;
    « Température (oC) » → unité « °C » ; « Date (dd/mm/yyyy) » → (« Date », None)."""
    text = re.sub(r"\s+", " ", (label or "")).strip()
    m = re.search(r"\(([^()]*)\)\s*$", text)
    if not m:
        return text, None
    inner = m.group(1).strip()
    base = text[: m.start()].strip()
    low = inner.lower().replace(" ", "")   # « <SUP>o</SUP>C » aplati en « o C »
    if low in _LABEL_UNITS:
        return base, "°C" if low in ("oc", "c") else inner
    return base, None


def _strip_tags(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


# Appels JavaScript qui écrivent les lignes de la « Synthèse ASI » de Net
# Vision v6 : CheckParameter("valeur", drapeau, ">Libellé<i> (unité)</i>").
_CHECK_PARAMETER_RE = re.compile(r"""CheckParameter\s*\(\s*"([^"]*)"\s*,\s*(\d+)\s*,\s*"([^"]*)"\s*\)""")
_NV_MODEL_RE = re.compile(r'tmpP1\s*=\s*"([^"]*)"')
_NV_SERIAL_RE = re.compile(r'tmpP2\s*=\s*"([^"]*)"')
_NV_SUBTITLE_RE = re.compile(r'SetSubTitle\s*\(\s*"([^"]*)"')


def parse_check_parameters(script):
    """Champs écrits par CheckParameter dans un script, dans l'ordre."""
    out = []
    for value, flag, label_html in _CHECK_PARAMETER_RE.findall(script or ""):
        label = _strip_tags(label_html).lstrip(">").strip()
        value = "" if value.strip().lower() in ("<br>", "inconnu", "unknown") else _strip_tags(value)
        out.append({"label": label, "value": value, "flag": flag})
    return out

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
        # `items` : ("row", [cellules]) et ("script", texte) dans l'ordre du
        # document -- Net Vision v6 (#417) écrit une partie des lignes du
        # tableau en JavaScript, entre deux lignes HTML.
        self.items = []
        self.title = ""
        self._row = None
        self._cell = None
        self._in_title = False
        self._in_script = False
        self._script = ""

    @property
    def rows(self):
        return [it[1] for it in self.items if it[0] == "row"]

    def _flush_cell(self):
        if self._cell is not None and self._row is not None:
            self._cell["text"] = re.sub(r"\s+", " ", self._cell["text"]).strip()
            self._row.append(self._cell)
        self._cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "script":
            self._in_script = True
            self._script = ""
        elif tag == "tr":
            self._flush_cell()
            if self._row is not None:
                self.items.append(("row", self._row))
            self._row = []
        elif tag in ("td", "th"):
            if self._row is None:
                self._row = []
            # Cellule imbriquée (table dans une cellule, Net Vision v6) : la
            # cellule englobante est close ici, son texte propre n'est que
            # de la mise en page.
            self._flush_cell()
            self._cell = {"attrs": {k.lower(): (v or "") for k, v in attrs}, "text": "", "tag": tag}

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_script = False
            self.items.append(("script", self._script))
        elif tag in ("td", "th"):
            self._flush_cell()
        elif tag == "tr":
            if self._row is not None:
                # Une cellule ouverte sans fermeture (HTML 4 tolérant) est
                # rattachée à sa ligne plutôt que perdue.
                self._flush_cell()
                self.items.append(("row", self._row))
            self._row = None

    def close(self):
        super().close()
        self._flush_cell()
        if self._row:
            self.items.append(("row", self._row))
            self._row = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_script:
            self._script += data
        elif self._cell is not None:
            self._cell["text"] += data


_SYSTEM_TIME_RE = re.compile(r"System Time:\s*(.+)$", re.IGNORECASE)


class _FrameCollector(HTMLParser):
    """Sources des <frame>, <iframe> et redirections <meta refresh> d'une
    page -- pour suivre une page « conteneur » jusqu'à la page d'état."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sources = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in ("frame", "iframe"):
            src = a.get("src", "").strip()
            if src:
                self.sources.append(src)
        elif tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            m = re.search(r"url\s*=\s*['\"]?([^'\";]+)", a.get("content", ""), re.IGNORECASE)
            if m:
                self.sources.append(m.group(1).strip())


def extract_frame_sources(html):
    """Livraison #416 : « une partie des onduleurs répond avec une frame ».
    Certaines cartes (frameset HTML 4) servent en /index.htm un simple
    conteneur : <frameset><frame src="menu.htm"><frame src="status.htm">.
    Renvoie les sources dans l'ordre du document, sans doublon, en ignorant
    les pseudo-URL (javascript:, about:, données)."""
    p = _FrameCollector()
    try:
        p.feed(html or "")
        p.close()
    except Exception:  # noqa: BLE001
        pass
    out = []
    for src in p.sources:
        low = src.lower()
        if low.startswith(("javascript:", "about:", "data:", "#")):
            continue
        if src not in out:
            out.append(src)
    return out


def parse_ups_page(html):
    """Fiche d'état.

    Renvoie :
      {
        "title": "UPS Management Web",
        "system_time": "09/07/2026 Monday 09:00:58" | None,
        "sections": [{"title": "UPS Status", "fields": [ {label, key, value, number, unit, css}, ... ]}, ...],
        "fields": {key: {label, value, number, unit, css, section}},
        "field_count": N,
        "flavor": "ups-management-web" | "netvision-v6" | "generic" | None,
      }
    Deux formes reconnues, dans l'ordre du document :
      - « UPS Management Web » (NETYS RT) : sections `class="title"`, champs
        « Libellé: » + valeur ;
      - « Net Vision v6 » (#417, ITYS) : lignes `<TD ID=TH1>Libellé (unité)</TD>`
        + valeur dans une table imbriquée, ET lignes écrites en JavaScript
        par CheckParameter("valeur", drapeau, "Libellé (unité)") ; modèle et
        numéro de série dans le script d'en-tête, sous-titre SetSubTitle.
    Une page qui n'a aucune de ces formes renvoie sections/fields vides,
    jamais une exception -- c'est à l'appelant de décider que « 0 champ »
    est une erreur (voir poller).
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
    flavors = set()
    nv_subtitle = None

    def add_field(label, value, css=None, unit_hint=None, flag=None):
        nonlocal current
        base, label_unit = split_label_unit(label)
        number, unit = parse_number(value)
        if unit is None:
            unit = unit_hint or label_unit
        key = field_key(base)
        entry = {"label": base, "key": key, "value": value, "number": number, "unit": unit, "css": css}
        if flag is not None:
            entry["flag"] = flag
        if current is None:
            current = {"title": nv_subtitle or "", "fields": []}
            sections.append(current)
        current["fields"].append(entry)
        if key not in fields:
            fields[key] = dict(entry, section=current["title"])

    for kind, item in parser.items:
        if kind == "script":
            # Net Vision v6 : identité et sous-titre dans le script d'en-tête,
            # lignes de mesure dans les scripts du tableau.
            m_sub = _NV_SUBTITLE_RE.search(item)
            if m_sub and nv_subtitle is None:
                nv_subtitle = m_sub.group(1).strip()
                if current is not None and not current["title"]:
                    current["title"] = nv_subtitle
            m_model = _NV_MODEL_RE.search(item)
            m_serial = _NV_SERIAL_RE.search(item)
            if m_model or m_serial:
                flavors.add("netvision-v6")
                ident = {"title": "Identification", "fields": []}
                sections.insert(0, ident)
                saved, current = current, ident
                if m_model and m_model.group(1).strip() not in ("", "<BR>"):
                    add_field("Modèle", m_model.group(1).strip())
                if m_serial and m_serial.group(1).strip() not in ("", "<BR>"):
                    add_field("Numéro de série", m_serial.group(1).strip())
                current = saved
            params = parse_check_parameters(item)
            if params:
                flavors.add("netvision-v6")
                for pm in params:
                    add_field(pm["label"], pm["value"], css=None, flag=pm["flag"])
            continue

        row = item
        texts = [c["text"] for c in row]
        # Heure système : cellule isolée « System Time: … » (UPS Management Web)
        for t in texts:
            m = _SYSTEM_TIME_RE.search(t)
            if m and system_time is None:
                system_time = m.group(1).strip()
        title_cell = next((c for c in row if "title" in c["attrs"].get("class", "").lower().split()), None)
        if title_cell and title_cell["text"]:
            current = {"title": title_cell["text"], "fields": []}
            sections.append(current)
            flavors.add("ups-management-web")
            continue
        # Forme 1 : « Libellé: » puis valeur (même vide : rien de programmé).
        matched = False
        for i, cell in enumerate(row):
            text = cell["text"]
            if not text.endswith(":"):
                continue
            label = text.rstrip(":").strip()
            if not label or " " in label and len(label) > 40:
                continue
            value_cell = row[i + 1] if i + 1 < len(row) else {"attrs": {}, "text": ""}
            add_field(label, value_cell["text"], css=value_cell["attrs"].get("class", "").strip().lower() or None)
            flavors.add("ups-management-web")
            matched = True
            break
        if matched:
            continue
        # Forme 2 (Net Vision v6) : cellule d'en-tête (id TH*, ou <th>) puis
        # première cellule non vide qui suit.
        for i, cell in enumerate(row):
            attrs = cell["attrs"]
            is_header = cell.get("tag") == "th" or attrs.get("id", "").lower().startswith("th")
            if not is_header or not cell["text"]:
                continue
            value_cell = next((c for c in row[i + 1:] if c["text"]), None)
            if value_cell is None:
                break
            add_field(cell["text"], value_cell["text"], css=(value_cell["attrs"].get("id") or value_cell["attrs"].get("class") or "").strip().lower() or None)
            flavors.add("netvision-v6")
            break

    # Sections nommées d'après le sous-titre Net Vision quand rien d'autre
    # ne les nomme.
    if nv_subtitle:
        for sec in sections:
            if not sec["title"]:
                sec["title"] = nv_subtitle
        for f in fields.values():
            if not f.get("section"):
                f["section"] = nv_subtitle

    # Heure de l'appareil Net Vision : date + heure sur deux lignes.
    if system_time is None and fields.get("device_date", {}).get("value"):
        system_time = (fields["device_date"]["value"] + " " + fields.get("device_time", {}).get("value", "")).strip()

    flavor = None
    if flavors:
        flavor = "netvision-v6" if "netvision-v6" in flavors else next(iter(flavors))

    return {
        "title": re.sub(r"\s+", " ", parser.title).strip(),
        "system_time": system_time,
        "sections": sections,
        "fields": fields,
        "field_count": sum(len(s["fields"]) for s in sections),
        "flavor": flavor,
    }


def display_value(entry):
    """Valeur lisible : l'unité est ajoutée quand la page ne l'écrit pas
    dans la valeur (Net Vision : « 230.0 » + unité « V » → « 230.0 V »)."""
    value = (entry or {}).get("value") or ""
    unit = (entry or {}).get("unit")
    if value and unit and unit.lower() not in value.lower():
        return f"{value} {unit}"
    return value


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
