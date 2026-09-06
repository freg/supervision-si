"""
Import des CLIENTS Nebula (livraison #269) vers GLPI -- DISTINCT de
`nebula_import.py` (#208), qui importe les ÉQUIPEMENTS d'infra
Nebula (bornes Wi-Fi, switchs, pare-feu). Ici : les appareils qui SE
CONNECTENT à travers cette infrastructure (téléphones, portables,
tablettes...) -- demandé explicitement : "à partir des logs de
nebula je peux exporter les clients connectés ou récemment
connectés... pourra t'on les injecter dans glpi".

Source de données : `GET /imported/clients` côté `nebula-api`
(import CSV du portail web, #200, table `nebula_clients_import`,
CLIENTS_COLUMNS = ["status", "name", "mac_address", "ipv4_address",
"connected_to", "manufacturer", "os", "policy", "band", "rx_rate",
"tx_rate", "ssid_name", "signal_strength", "last_seen"]).

**Type GLPI : `Computer`, PAS `NetworkEquipment`** -- choix
délibéré, à la différence de `nebula_import.py` (infrastructure
réseau). Ces lignes décrivent des appareils UTILISATEURS finaux
(présence de `manufacturer`/`os`, absents des équipements
d'infrastructure) -- `Computer` est le type GLPI le plus proche
sémantiquement, même s'il ne couvre pas parfaitement les téléphones/
tablettes (GLPI a d'autres types dédiés -- `Phone` -- mais rien dans
les données Nebula ne permet de distinguer fiablement un ordinateur
portable d'un téléphone connecté au même SSID -- `Computer` reste le
choix par défaut le plus sûr, JAMAIS présenté comme définitivement
exact, à ajuster si la personne constate le contraire en conditions
réelles).

**Même réserve MAC/`otherserial`** que `nebula_import.py` (#208) --
non vérifiée contre un vrai GLPI.
"""

DEFAULT_GLPI_ITEMTYPE = "Computer"
MAC_DEDUP_FIELD = "otherserial"


def build_comment(client):
    """Regroupe les colonnes Nebula sans équivalent structurel direct
    dans GLPI -- même raisonnement que `nebula_import.build_comment`."""
    parts = []
    for key, label in [
        ("ipv4_address", "IP"), ("manufacturer", "Fabricant"), ("os", "OS"),
        ("connected_to", "Connecté à"), ("ssid_name", "SSID"), ("signal_strength", "Signal"),
        ("last_seen", "Vu la dernière fois"),
    ]:
        value = client.get(key)
        if value not in (None, ""):
            parts.append(f"{label} : {value}")
    parts.append("Source : import Nebula -- client connecté (nebula-api)")
    return " | ".join(parts)


def build_glpi_fields(client):
    """`client` : une ligne de GET /imported/clients côté nebula-api
    (voir CLIENTS_COLUMNS dans nebula/api/app.py pour la forme exacte)."""
    fields = {"name": client.get("name") or client.get("mac_address")}
    mac = client.get("mac_address")
    if mac:
        fields[MAC_DEDUP_FIELD] = mac
    fields["comment"] = build_comment(client)
    return fields


def import_clients(glpi_client, nebula_clients, dry_run=True, only_macs=None):
    """`nebula_clients` : la liste renvoyée par GET /imported/clients
    côté nebula-api -- déjà récupérée par l'appelant (voir app.py).
    Même structure de résumé que `nebula_import.import_devices` pour
    rester cohérent.

    `only_macs` (livraison #269, demandé explicitement -- "une
    interface de sélection multiple") -- optionnel, un ensemble
    d'adresses MAC (normalisées en minuscules) : si fourni, SEULES
    les lignes dont la MAC y figure sont traitées, permettant à la
    personne de choisir précisément lesquels des clients détectés
    importer plutôt que "tout ou rien". `None` (défaut) -- comportement
    inchangé, tout est traité."""
    only_macs_normalized = {m.strip().lower() for m in only_macs} if only_macs is not None else None
    summary = {"created": [], "skipped_existing": [], "skipped_unselected": [], "errors": [], "warnings": []}

    for client_row in nebula_clients:
        mac = (client_row.get("mac_address") or "").strip()
        if not mac:
            summary["errors"].append("client sans adresse MAC -- ignoré")
            continue

        name = client_row.get("name") or mac
        if only_macs_normalized is not None and mac.lower() not in only_macs_normalized:
            summary["skipped_unselected"].append(f"{name} (MAC {mac}) -- non sélectionné")
            continue

        itemtype = DEFAULT_GLPI_ITEMTYPE

        if not dry_run:
            existing = glpi_client.get_items(itemtype, search_text={MAC_DEDUP_FIELD: mac})
            if isinstance(existing, list) and len(existing) > 0:
                summary["skipped_existing"].append(f"{name} (MAC {mac}) -- déjà présent dans GLPI")
                continue

        fields = build_glpi_fields(client_row)

        if dry_run:
            # Structuré (livraison #269, pas une simple chaîne) --
            # `key` = la MAC, exploitable directement par le hub pour
            # construire une case à cocher par candidat ("interface de
            # sélection multiple" demandée explicitement).
            summary["created"].append({"key": mac, "name": name, "itemtype": itemtype, "detail": str(fields)})
            continue

        try:
            new_id = glpi_client.add_item(itemtype, fields)
            summary["created"].append(f"{itemtype} '{name}' -- id GLPI {new_id}")
        except Exception as exc:  # noqa: BLE001 -- une ligne en échec ne doit jamais arrêter tout l'import
            summary["errors"].append(f"{name} ({itemtype}) : {exc}")

    return summary
