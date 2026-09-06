"""
Import des appareils Nebula (déjà importés côté `nebula-api`, #200)
vers GLPI (livraison #208, backlog item 16 -- "endpoint API déjà
repéré : sites/devices"). Complète l'import Excel (#192) : même
esprit (dédoublonnage par clé naturelle, approximation documentée du
mapping de type), source de données différente -- ici les appareils
RÉSEAU de Nebula (bornes Wi-Fi, switchs, pare-feu), préalablement
importés dans `nebula-api` via `GET /imported/devices` (CSV du
portail web, #200, OU l'API officielle une fois débloquée, #196 --
source indifférente ici, cette fonction ne voit que la forme déjà
normalisée par `nebula-api`).

**Types RÉELS rencontrés** dans les fichiers fournis par la personne
(#200) : "Access point", "Switch", "Firewall" -- uniquement ces trois,
jamais un jeu de types exhaustif deviné à l'avance. Tous mappés vers
`NetworkEquipment` (le type GLPI dédié au matériel réseau) -- un type
Nebula NON reconnu retombe aussi sur `NetworkEquipment` (le choix par
défaut le plus sûr pour du matériel réseau), mais SIGNALÉ comme tel
dans le résumé d'import, jamais silencieux.

**⚠️ Point vérifié PUIS corrigé avant même de tester** : l'adresse MAC
n'est PAS une colonne directe de `glpi_networkequipments` en base
GLPI -- confirmé en recherchant (une requête SQL réelle vue dans un
rapport de bug GLPI référence `port.mac` depuis `glpi_networkports`,
un sous-objet séparé). Créer proprement ce sous-objet par appareil
serait la solution la plus correcte, mais ajoute un appel API
supplémentaire par appareil -- complexité VOLONTAIREMENT reportée,
même raisonnement que les adresses MAC multiples déjà différées dans
l'import Excel (#192). À la place : la MAC est stockée dans
`otherserial` (champ texte libre générique, disponible sur la
quasi-totalité des types d'actifs GLPI dont NetworkEquipment) --
choix plus prudent qu'un champ `mac` direct qui n'existe probablement
pas, mais LUI-MÊME PAS VÉRIFIÉ CONTRE UN VRAI GLPI -- à confirmer en
priorité au premier import réel (voir glpi/README.md).
"""

NEBULA_DEVICE_TYPE_MAPPING = {
    "access point": "NetworkEquipment",
    "switch": "NetworkEquipment",
    "firewall": "NetworkEquipment",
}
DEFAULT_GLPI_ITEMTYPE = "NetworkEquipment"
MAC_DEDUP_FIELD = "otherserial"


def build_comment(device):
    """Regroupe les colonnes Nebula sans équivalent structurel direct
    dans GLPI -- jamais perdues, juste pas modélisées en dropdowns
    dédiés (même raisonnement que build_comment dans excel_import.py,
    #192)."""
    parts = []
    for key, label in [("device_type", "Type Nebula"), ("clients_count", "Clients connectés"),
                        ("usage", "Usage"), ("tags", "Tags Nebula")]:
        value = device.get(key)
        if value not in (None, "", 0) or (key == "clients_count" and value == 0):
            parts.append(f"{label} : {value}")
    parts.append("Source : import Nebula (nebula-api)")
    return " | ".join(parts)


def resolve_glpi_itemtype(device):
    """Renvoie (itemtype, avertissement_ou_None) -- jamais un type
    deviné silencieusement si le type Nebula n'est pas dans la liste
    connue (voir docstring du module)."""
    raw_type = (device.get("device_type") or "").strip()
    key = raw_type.lower()
    itemtype = NEBULA_DEVICE_TYPE_MAPPING.get(key)
    if itemtype is None:
        return DEFAULT_GLPI_ITEMTYPE, f"type Nebula '{raw_type}' inconnu -- classé {DEFAULT_GLPI_ITEMTYPE} par défaut -- À VÉRIFIER"
    return itemtype, None


def build_glpi_fields(device, model_id, location_id):
    """`device` : une ligne de GET /imported/devices côté nebula-api
    (voir nebula/api/csv_import.py pour la forme exacte -- mac_address,
    model, device_type, name, site, clients_count, usage, tags)."""
    fields = {"name": device.get("name") or device.get("mac_address")}
    if model_id is not None:
        fields["networkequipmentmodels_id"] = model_id
    if location_id is not None:
        fields["locations_id"] = location_id
    mac = device.get("mac_address")
    if mac:
        fields[MAC_DEDUP_FIELD] = mac
    fields["comment"] = build_comment(device)
    return fields


def import_devices(glpi_client, nebula_devices, dry_run=True, only_macs=None):
    """`nebula_devices` : la liste renvoyée par GET /imported/devices
    (nebula-api) -- déjà récupérée par l'appelant (voir app.py),
    cette fonction ne fait AUCUN appel réseau vers nebula-api elle-
    même, seulement vers GLPI. Même structure de résumé que
    excel_import.import_excel (#192) pour rester cohérent.

    `only_macs` (livraison #269, sélection multiple demandée
    explicitement) -- optionnel, un ensemble d'adresses MAC
    (normalisées en minuscules) : si fourni, seuls les appareils dont
    la MAC y figure sont traités. `None` (défaut) -- comportement
    inchangé, tout est traité."""
    only_macs_normalized = {m.strip().lower() for m in only_macs} if only_macs is not None else None
    summary = {"created": [], "skipped_existing": [], "skipped_unselected": [], "errors": [], "warnings": []}
    model_cache = {}
    location_cache = {}

    for device in nebula_devices:
        mac = (device.get("mac_address") or "").strip()
        if not mac:
            summary["errors"].append("appareil sans adresse MAC -- ignoré")
            continue

        name = device.get("name") or mac
        if only_macs_normalized is not None and mac.lower() not in only_macs_normalized:
            summary["skipped_unselected"].append(f"{name} (MAC {mac}) -- non sélectionné")
            continue

        itemtype, warning = resolve_glpi_itemtype(device)
        if warning:
            summary["warnings"].append(f"{name} : {warning}")

        if not dry_run:
            existing = glpi_client.get_items(itemtype, search_text={MAC_DEDUP_FIELD: mac})
            if isinstance(existing, list) and len(existing) > 0:
                summary["skipped_existing"].append(f"{name} (MAC {mac}) -- déjà présent dans GLPI")
                continue

        model_name = (device.get("model") or "").strip()
        model_id = None
        if model_name:
            cache_key = (itemtype, model_name)
            if cache_key not in model_cache:
                model_cache[cache_key] = None if dry_run else glpi_client.get_or_create_dropdown("NetworkEquipmentModel", model_name)
            model_id = model_cache[cache_key]

        site_name = (device.get("site") or "").strip()
        location_id = None
        if site_name:
            if site_name not in location_cache:
                location_cache[site_name] = None if dry_run else glpi_client.get_or_create_dropdown("Location", site_name)
            location_id = location_cache[site_name]

        fields = build_glpi_fields(device, model_id, location_id)

        if dry_run:
            summary["created"].append({"key": mac, "name": name, "itemtype": itemtype, "detail": str(fields)})
            continue

        try:
            new_id = glpi_client.add_item(itemtype, fields)
            summary["created"].append(f"{itemtype} '{name}' -- id GLPI {new_id}")
        except Exception as exc:  # noqa: BLE001 -- une ligne en échec ne doit jamais arrêter tout l'import
            summary["errors"].append(f"{name} ({itemtype}) : {exc}")

    return summary
