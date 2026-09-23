# -*- coding: utf-8 -*-
"""Fiches du campus (livraison #566) -- logique PURE, testée (tests/test_campus.py).

Deux collections importées depuis les tableurs du client (xlsx / ods / csv),
jamais dans le dépôt (données du site, volume /data) :
- `assets`   : matériels (inventaire : nom, type, modèle, série, MAC, compte,
               lab, classe, localisation, stockage, profil, mise en service…)
- `services` : services / logiciels / ateliers (expériences : parcours, lab,
               atelier, matériel, Wi-Fi/LAN/Internet, site, plateformes…)

Le tableur est lu tel quel (première ligne = en-têtes) ; les colonnes
connues sont normalisées dans des champs stables (`name`, `kind`, `lab`,
`location`, `mac`, `serial`), le reste est conservé dans `fields` pour la
fiche. Les lignes de tableur « en creux » (parcours / lab vides sous une
ligne renseignée) héritent de la ligne précédente (fusion visuelle du
tableur)."""
import csv
import io
import re
import zipfile
from xml.etree import ElementTree as ET

ASSET_KEYS = {"name": ("nom", "name"), "kind": ("type",), "designation": ("désignation", "designation"), "model": ("modèle", "modele", "model"),
              "serial": ("numero de série", "numéro de série", "serial", "n° de série"), "mac": ("adresse mac", "mac"), "account": ("compte", "account"),
              "lab": ("lab",), "klass": ("classe",), "subclass": ("sous-classe",), "location": ("localisation",), "storage": ("stockage",),
              "profile": ("profil",), "commissioned": ("date de mise en service",), "comment": ("commentaire", "comment")}
SERVICE_KEYS = {"course": ("parcours",), "lab": ("lab",), "name": ("nom de l’atelier", "nom de l'atelier", "atelier", "nom"), "apk": ("date de livraison de l’apk", "date de livraison de l'apk", "apk"),
                "hardware": ("matériel", "materiel"), "wifi": ("wifi", "wi-fi"), "lan": ("lan",), "internet": ("internet",), "site": ("site",)}
INHERIT = {"assets": (), "services": ("course", "lab")}


def _norm_header(h):
    return re.sub(r"\s+", " ", str(h or "")).strip().lower()


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v != v:
        return ""
    s = str(v).strip()
    if s.endswith(" 00:00:00"):
        s = s[:-9]
    return s


# ---------------------------------------------------------------- lecture
def read_table(data, filename):
    """[[cellules]] de la première feuille utile (xlsx / ods / csv)."""
    name = (filename or "").lower()
    if name.endswith(".csv") or name.endswith(".txt"):
        text = data.decode("utf-8-sig", errors="replace")
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=";,\t") if text.strip() else csv.excel
        return [row for row in csv.reader(io.StringIO(text), dialect)]
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        return _read_xlsx(data)
    if name.endswith(".ods"):
        return _read_ods(data)
    raise ValueError("format non reconnu (xlsx, ods ou csv attendu)")


def _read_xlsx(data):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    best = []
    for ws in wb.worksheets:
        rows = [[_cell(c) for c in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        if len(rows) > len(best):
            best = rows
    return best


def _read_ods(data):
    ns = {"table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0", "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
          "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0"}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("content.xml"))
    best = []
    for table in root.iter("{%s}table" % ns["table"]):
        rows = []
        for tr in table.iter("{%s}table-row" % ns["table"]):
            cells = []
            for tc in tr:
                if tc.tag not in ("{%s}table-cell" % ns["table"], "{%s}covered-table-cell" % ns["table"]):
                    continue
                rep = int(tc.get("{%s}number-columns-repeated" % ns["table"], "1"))
                txt = " ".join("".join(p.itertext()) for p in tc.iter("{%s}p" % ns["text"])).strip()
                if rep > 50:  # remplissage de fin de ligne
                    rep = 1 if txt else 0
                cells.extend([txt] * rep)
            while cells and not cells[-1]:
                cells.pop()
            if any(cells):
                rows.append(cells)
        if len(rows) > len(best):
            best = rows
    return best


# ---------------------------------------------------------------- fiches
def parse_records(rows, collection):
    """[[cellules]] -> [{champs normalisés + fields}] pour `assets` ou `services`."""
    keys = ASSET_KEYS if collection == "assets" else SERVICE_KEYS
    if not rows:
        return []
    headers = [_norm_header(h) for h in rows[0]]
    col = {}
    for field, names in keys.items():
        for i, h in enumerate(headers):
            if h in names and field not in col:
                col[field] = i
    out = []
    prev = {}
    for idx, r in enumerate(rows[1:], start=2):
        r = list(r) + [""] * (len(headers) - len(r))
        rec = {}
        for field, i in col.items():
            rec[field] = _cell(r[i])
        for f in INHERIT[collection]:
            if not rec.get(f) and prev.get(f):
                rec[f] = prev[f]
        fields = {rows[0][i]: _cell(r[i]) for i in range(len(headers)) if i < len(r) and _cell(r[i]) and i not in col.values()}
        rec["fields"] = fields
        if collection == "assets":
            rec["macs"] = [m for m in re.split(r"[,\s;]+", rec.get("mac", "")) if re.match(r"^[0-9a-fA-F]{2}([:-][0-9a-fA-F]{2}){5}$", m)]
            rec["macs"] = [m.lower().replace("-", ":") for m in rec["macs"]]
            if not (rec.get("name") or rec.get("serial") or rec.get("kind")):
                continue
            # clé stable ; une ligne sans nom ni série (matériel non identifié) garde son rang de ligne pour ne pas écraser ses voisines
            rec["key"] = (rec.get("name") or "") + "|" + (rec.get("serial") or "") + "|" + (rec.get("kind") or "") + "|" + (rec.get("lab") or "") + ("" if (rec.get("name") or rec.get("serial")) else "|l%d" % idx)
        else:
            if not (rec.get("name") or rec.get("course") or rec.get("hardware")):
                continue
            for f in ("wifi", "lan", "internet"):
                rec[f] = rec.get(f, "").strip().lower() in ("x", "oui", "yes", "1", "true")
            rec["key"] = (rec.get("course") or "") + "|" + (rec.get("lab") or "") + "|" + (rec.get("name") or "")
        prev = rec
        out.append(rec)
    return out


def match_assets(assets, clients):
    """Rapproche les fiches matériel des clients Nebula (par MAC, sinon par
    nom) : ajoute `nebula` = {name, ip, status, connected_to, vlan, last_seen}."""
    by_mac = {}
    by_name = {}
    for c in clients or []:
        m = (c.get("mac") or "").lower().replace("-", ":")
        if m:
            by_mac[m] = c
        n = (c.get("name") or "").strip().lower()
        if n:
            by_name[n] = c
    for a in assets:
        hit = None
        for m in a.get("macs") or []:
            if m in by_mac:
                hit = by_mac[m]
                break
        if not hit and a.get("name"):
            hit = by_name.get(a["name"].strip().lower())
        a["nebula"] = {k: hit.get(k) for k in ("name", "ip", "status", "connected_to", "parent_name", "vlan", "last_seen", "wired")} if hit else None
    return assets
