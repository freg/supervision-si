"""
Import de l'inventaire Excel fourni vers GLPI (livraison #192,
besoin immédiat explicite). Lit la feuille "Devices" (220 lignes
au moment de cette livraison), mappe chaque ligne vers un itemtype
GLPI (Computer/Peripheral/Monitor/Printer), et crée les actifs via
`glpi_client.GlpiClient`.

**⚠️ Jamais exécuté contre un vrai GLPI** -- voir glpi_client.py.
Toujours lancer d'abord en `dry_run=True` (par défaut) : affiche ce
qui SERAIT créé, sans rien envoyer à GLPI -- le seul moyen de
vérifier le mapping avant d'écrire quoi que ce soit sur un GLPI de
production.

**Problèmes de qualité de données RÉELLEMENT trouvés dans le fichier
fourni** (voir `_KNOWN_TYPE_TYPOS`/`_KNOWN_LAB_TYPOS` ci-dessous,
et le résumé affiché en fin d'import) :
- 12 lignes "Borne-001" à "Borne-012" : la colonne "Nom" est VIDE,
  l'identifiant a été saisi dans la colonne "Type" à la place --
  utilisé ici comme nom, type par défaut "Peripheral", SIGNALÉ dans
  le résumé pour vérification humaine (jamais un choix silencieux).
- "Bras Niryo" / "Bras NIryo" (casse différente) : même situation
  (Nom vide, valeur dans Type) -- traité pareil, regroupé comme UN
  seul type normalisé.
- "Amphi Immersif" / "Amphi immersif" (casse), "Mediateurs" /
  "Médiateurs" (accent) dans la colonne "Lab" -- normalisés vers
  UNE seule forme (celle la plus fréquente) avant de créer/chercher
  la localisation GLPI, pour ne jamais créer deux entrées différentes
  pour le même lieu.
"""
import re

import pandas as pd


# Type Excel -> itemtype GLPI. Approximation DOCUMENTÉE (mode
# "approximer et documenter", cohérent avec le reste du projet) --
# GLPI n'a pas de type "Tablette"/"Casque VR" dédié dans son schéma
# CLASSIQUE (Computer/Peripheral/Monitor/Printer/NetworkEquipment/
# Phone) -- Peripheral sert de catégorie générique pour tout ce qui
# n'est ni un ordinateur, ni un écran, ni une imprimante. À ajuster
# facilement ici si la réalité GLPI de la personne diffère (ex. un
# plugin "Tablet" dédié déjà en place).
TYPE_MAPPING = {
    "ordinateur portable": "Computer",
    "ordi portable": "Computer",
    "ordi fixe": "Computer",
    "tablette": "Peripheral",
    "casque vr": "Peripheral",
    "smarttv": "Monitor",
    "ecran interactif 86'": "Monitor",
    "ecran interactif 55'": "Monitor",
    "ecran de circulation": "Monitor",
    "ecran de contrôle": "Monitor",
    "vidéoprojecteur": "Peripheral",
    "caméra 360": "Peripheral",
    "photocopieur": "Printer",
    "cave": "Peripheral",
    "table interactive": "Peripheral",
    "rapidmooc": "Peripheral",
    "imprimante 3d": "Printer",
    "bras niryo": "Peripheral",
    "régie": "Peripheral",
}

# Corrige les fautes de frappe RÉELLEMENT trouvées dans ce fichier
# AVANT la recherche dans TYPE_MAPPING -- jamais un rapprochement
# "flou" général (risque de mal regrouper deux types réellement
# différents), seulement les cas CONCRETS déjà repérés.
_KNOWN_TYPE_TYPOS = {
    "ecran interactiif 55'": "ecran interactif 55'",
    "bras niryo": "bras niryo",  # déjà normalisé par le .lower(), gardé explicite pour lisibilité
    "bras niryo ": "bras niryo",
}

_KNOWN_LAB_TYPOS = {
    "amphi immersif": "Amphi Immersif",
    "mediateurs": "Médiateurs",
    "médiateurs": "Médiateurs",
}

_BORNE_TYPE_RE = re.compile(r"^borne-\d+$", re.IGNORECASE)


def normalize_lab(lab):
    if pd.isna(lab):
        return None
    key = str(lab).strip().lower()
    return _KNOWN_LAB_TYPOS.get(key, str(lab).strip())


def resolve_itemtype_and_name(row):
    """Renvoie (itemtype, nom, avertissement_ou_None). Gère le cas
    RÉEL trouvé dans ce fichier -- Nom vide + un identifiant dans
    Type (Borne-XXX, Bras Niryo/NIryo) -- voir docstring du module."""
    raw_type = row.get("Type")
    raw_name = row.get("Nom")
    type_str = "" if pd.isna(raw_type) else str(raw_type).strip()
    name_str = None if pd.isna(raw_name) else str(raw_name).strip()

    if not name_str and (_BORNE_TYPE_RE.match(type_str) or type_str.lower().startswith("bras ")):
        warning = (
            f"colonne 'Nom' vide, identifiant '{type_str}' trouvé dans 'Type' à la place -- "
            f"utilisé comme nom, type GLPI par défaut 'Peripheral' -- À VÉRIFIER"
        )
        return "Peripheral", type_str, warning

    key = _KNOWN_TYPE_TYPOS.get(type_str.lower(), type_str.lower())
    itemtype = TYPE_MAPPING.get(key)
    if itemtype is None:
        return "Peripheral", name_str or type_str, f"type '{type_str}' inconnu -- classé 'Peripheral' par défaut -- À VÉRIFIER"
    return itemtype, name_str or type_str, None


def build_comment(row):
    """Regroupe les colonnes SANS équivalent structurel direct dans
    GLPI (Classe/Sous-classe/Profil/Localisation/Stockage/Compte/
    Commentaire d'origine) -- jamais perdues, juste pas modélisées
    en dropdowns dédiés pour cette première version."""
    parts = []
    mapping = [
        ("Compte", "Compte"), ("Classe", "Classe"), ("Sous-classe", "Sous-classe"),
        ("Localisation", "Localisation"), ("Stockage", "Stockage"), ("Profil", "Profil"),
        ("Commentaire", "Commentaire d'origine"),
    ]
    for col, label in mapping:
        value = row.get(col)
        if not pd.isna(value) and str(value).strip():
            parts.append(f"{label} : {str(value).strip()}")
    return " | ".join(parts) if parts else None


def build_fields(row, itemtype, name, model_id, location_id):
    fields = {"name": name}
    if model_id is not None:
        model_field = {"Computer": "computermodels_id", "Peripheral": "peripheralmodels_id",
                        "Monitor": "monitormodels_id", "Printer": "printermodels_id"}.get(itemtype)
        if model_field:
            fields[model_field] = model_id
    if location_id is not None:
        fields["locations_id"] = location_id
    serial = row.get("Numero de série")
    if not pd.isna(serial) and str(serial).strip():
        fields["serial"] = str(serial).strip()
    comment = build_comment(row)
    if comment:
        fields["comment"] = comment
    return fields


def read_devices(filepath, sheet_name="Devices"):
    return pd.read_excel(filepath, sheet_name=sheet_name)


def import_excel(client, filepath, sheet_name="Devices", dry_run=True):
    """Renvoie un résumé {created, skipped_existing, errors, warnings}.
    `skipped_existing` : dédoublonnage par NUMÉRO DE SÉRIE (`search_items`
    avant chaque création) -- un ré-import du même fichier ne crée
    jamais de doublon, condition nécessaire pour pouvoir relancer cet
    import sans risque si le fichier est mis à jour plus tard."""
    df = read_devices(filepath, sheet_name)
    summary = {"created": [], "skipped_existing": [], "errors": [], "warnings": []}
    model_cache = {}
    location_cache = {}

    for _, row in df.iterrows():
        itemtype, name, warning = resolve_itemtype_and_name(row)
        if warning:
            summary["warnings"].append(f"{name or '(sans nom)'} : {warning}")
        if not name:
            summary["errors"].append("ligne sans nom ni type exploitable -- ignorée")
            continue

        serial = row.get("Numero de série")
        serial = str(serial).strip() if not pd.isna(serial) and str(serial).strip() else None

        if serial and not dry_run:
            # `searchText` filtre par NOM DE CHAMP réel ("serial"),
            # jamais par un id de "searchoption" numérique -- celui-ci
            # varie selon l'itemtype et je n'ai aucun moyen de le
            # confirmer sans un vrai GLPI sous la main (voir
            # glpi_client.py) -- searchText est documenté comme
            # acceptant directement le nom de colonne, plus sûr ici
            # que de deviner un numéro.
            existing = client.get_items(itemtype, search_text={"serial": serial})
            if isinstance(existing, list) and len(existing) > 0:
                summary["skipped_existing"].append(f"{name} (série {serial}) -- déjà présent dans GLPI")
                continue

        model_name = row.get("Modèle")
        model_id = None
        if not pd.isna(model_name) and str(model_name).strip():
            cache_key = (itemtype, str(model_name).strip())
            if cache_key not in model_cache:
                if dry_run:
                    model_cache[cache_key] = None
                else:
                    model_field = {"Computer": "ComputerModel", "Peripheral": "PeripheralModel",
                                    "Monitor": "MonitorModel", "Printer": "PrinterModel"}.get(itemtype)
                    model_cache[cache_key] = client.get_or_create_dropdown(model_field, str(model_name).strip()) if model_field else None
            model_id = model_cache[cache_key]

        lab = normalize_lab(row.get("Lab"))
        location_id = None
        if lab:
            if lab not in location_cache:
                location_cache[lab] = None if dry_run else client.get_or_create_dropdown("Location", lab)
            location_id = location_cache[lab]

        fields = build_fields(row, itemtype, name, model_id, location_id)

        if dry_run:
            summary["created"].append(f"[SIMULATION] {itemtype} '{name}' -- {fields}")
            continue

        try:
            new_id = client.add_item(itemtype, fields)
            summary["created"].append(f"{itemtype} '{name}' -- id GLPI {new_id}")
        except Exception as exc:  # noqa: BLE001 -- une ligne en échec ne doit jamais arrêter tout l'import
            summary["errors"].append(f"{name} ({itemtype}) : {exc}")

    return summary
