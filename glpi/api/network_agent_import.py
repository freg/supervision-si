"""
Import des appareils découverts par `network-agent` (#250-251) vers
GLPI (livraison #264, demandé explicitement : "je veux exporter vers
glpi tout ce qu'on va découvrir par l'exploration réseau" -- après
avoir confirmé que l'inventaire GLPI actuel est "presque vide", donc
rien d'utile à en IMPORTER pour l'instant -- ce module va dans le
sens INVERSE, peupler GLPI depuis la découverte réseau réelle).

Même esprit que `nebula_import.py` (#208) -- table de mapping
explicite plutôt qu'un type deviné silencieusement, dédoublonnage
par clé naturelle (ici l'adresse MAC, déjà le champ-pivot de
`network-agent` lui-même). Différence de source : ici, PAS de
"type d'appareil" fourni par `network-agent` (contrairement à
Nebula, qui distingue Access point/Switch/Firewall) -- TOUS les
appareils sont mappés vers `NetworkEquipment` (même choix par défaut
que Nebula pour du matériel réseau, le type le plus sûr faute de
mieux), **jamais deviné plus finement à partir du nom d'hôte** dans
cette première tranche -- voir README pour la piste "classification
au moment de l'export" volontairement pas encore suivie.

**Même point vérifié PUIS corrigé que pour Nebula (#208)** : l'adresse
MAC n'est pas une colonne directe de `glpi_networkequipments` en base
GLPI -- stockée dans `otherserial` (champ texte libre générique),
même choix, même réserve (non vérifié contre un vrai GLPI, à
confirmer au premier import réel).
"""

DEFAULT_GLPI_ITEMTYPE = "NetworkEquipment"
MAC_DEDUP_FIELD = "otherserial"


def build_comment(device):
    """Regroupe les colonnes network-agent sans équivalent structurel
    direct dans GLPI -- jamais perdues, juste pas modélisées en
    dropdowns dédiés (même raisonnement que `nebula_import.build_comment`)."""
    parts = []
    if device.get("ip_address"):
        parts.append(f"Dernière IP connue : {device['ip_address']}")
    if device.get("role_hint"):
        parts.append(f"Rôle détecté : {device['role_hint']}")
    if device.get("first_seen"):
        parts.append(f"Vu la 1ère fois : {device['first_seen']}")
    if device.get("last_seen"):
        parts.append(f"Vu la dernière fois : {device['last_seen']}")
    if device.get("bytes_total") is not None:
        parts.append(f"Volume cumulé (octets) : {device['bytes_total']}")
    parts.append("Source : import Exploration réseau (network-agent-api)")
    return " | ".join(parts)


def build_glpi_fields(device):
    """`device` : une ligne de GET /devices côté network-agent-api
    (voir network-agent/api/store.py pour la forme exacte --
    mac_address, ip_address, hostname, first_seen, last_seen,
    packet_count, bytes_total, external_relay_count, role_hint)."""
    fields = {"name": device.get("hostname") or device.get("mac_address")}
    mac = device.get("mac_address")
    if mac:
        fields[MAC_DEDUP_FIELD] = mac
    # Pas de colonne IP dédiée fiable/systématique sur
    # NetworkEquipment selon la version GLPI (même réserve que pour
    # la MAC) -- l'IP est reprise dans le commentaire libre via
    # build_comment si besoin d'y ajouter plus tard, jamais un champ
    # non vérifié utilisé en dur ici.
    fields["comment"] = build_comment(device)
    return fields


def import_devices(glpi_client, network_agent_devices, dry_run=True, exclude_categories=None, classifications=None, only_macs=None):
    """`network_agent_devices` : la liste renvoyée par GET /devices
    (network-agent-api) -- déjà récupérée par l'appelant (voir
    app.py), cette fonction ne fait AUCUN appel réseau vers
    network-agent-api elle-même, seulement vers GLPI. Même structure
    de résumé que `nebula_import.import_devices` pour rester cohérent.

    `classifications` (optionnel) -- {mac: category}, si fourni par
    l'appelant (croisement avec `classifier-api`, voir app.py) --
    `exclude_categories` (optionnel, ex. {"client_dhcp_dynamique"})
    permet d'exclure les catégories jugées TRANSITOIRES (un invité
    WiFi passager n'est pas vraiment un "actif" à suivre dans un
    inventaire) -- SANS classification fournie, TOUT est importé sans
    filtrage, exactement la demande initiale ("tout ce qu'on va
    découvrir").

    `only_macs` (livraison #269, sélection multiple demandée
    explicitement) -- optionnel, un ensemble d'adresses MAC
    (normalisées en minuscules), COMPLÉMENTAIRE à `exclude_categories`
    (les deux filtres s'appliquent ensemble si fournis) : si fourni,
    seuls les appareils dont la MAC y figure sont traités. `None`
    (défaut) -- comportement inchangé."""
    exclude_categories = exclude_categories or set()
    classifications = classifications or {}
    only_macs_normalized = {m.strip().lower() for m in only_macs} if only_macs is not None else None
    summary = {"created": [], "skipped_existing": [], "skipped_excluded": [], "skipped_unselected": [], "errors": [], "warnings": []}

    for device in network_agent_devices:
        mac = (device.get("mac_address") or "").strip()
        if not mac:
            summary["errors"].append("appareil sans adresse MAC -- ignoré")
            continue

        name = device.get("hostname") or mac
        if only_macs_normalized is not None and mac.lower() not in only_macs_normalized:
            summary["skipped_unselected"].append(f"{name} (MAC {mac}) -- non sélectionné")
            continue

        category = classifications.get(mac.lower())
        if category and category in exclude_categories:
            summary["skipped_excluded"].append(f"{name} (MAC {mac}) -- catégorie exclue : {category}")
            continue

        itemtype = DEFAULT_GLPI_ITEMTYPE

        if not dry_run:
            existing = glpi_client.get_items(itemtype, search_text={MAC_DEDUP_FIELD: mac})
            if isinstance(existing, list) and len(existing) > 0:
                summary["skipped_existing"].append(f"{name} (MAC {mac}) -- déjà présent dans GLPI")
                continue

        fields = build_glpi_fields(device)

        if dry_run:
            summary["created"].append({"key": mac, "name": name, "itemtype": itemtype, "detail": str(fields)})
            continue

        try:
            new_id = glpi_client.add_item(itemtype, fields)
            summary["created"].append(f"{itemtype} '{name}' -- id GLPI {new_id}")
        except Exception as exc:  # noqa: BLE001 -- une ligne en échec ne doit jamais arrêter tout l'import
            summary["errors"].append(f"{name} ({itemtype}) : {exc}")

    return summary
