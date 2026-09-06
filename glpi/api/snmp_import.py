"""
Import des cibles SNMP (déjà enregistrées côté `snmp-api`, #213) vers
GLPI (livraison #232, demandé explicitement : "remplir GLPI plus ou
moins automatiquement... à la fois nos futurs outils d'exploration et
les extractions de Nebula"). Complète l'import Nebula (#208) : même
esprit (dédoublonnage par clé stable, dry_run systématique, jamais
bloquant sur un échec isolé), source de données différente -- ici les
informations SNMP (groupe System) d'une cible déjà enregistrée dans
`snmp-api`, interrogée EN DIRECT à chaque import (pas de cache --
`snmp-api` lui-même n'en garde pas non plus, voir snmp/README.md).

**Choix de dédoublonnage** : contrairement à Nebula (adresse MAC déjà
disponible dans les données importées), une interrogation SNMP ne
fournit PAS nativement de MAC exploitable ici (elle vivrait dans la
table des interfaces, pas le groupe System utilisé pour ce premier
import -- voir "Reste à faire" plus bas). À la place : l'HÔTE
(adresse IP ou nom, tel qu'enregistré dans la cible SNMP) stocké dans
`otherserial` -- MÊME CHAMP que `nebula_import.py` (jamais deux
conventions différentes pour le même besoin dans ce projet), MÊME
réserve assumée : pas vérifié contre un vrai GLPI que ce champ est le
bon choix, à confirmer au premier import réel.

**sysLocation -> Location GLPI** -- mappé via `get_or_create_dropdown`,
même mécanisme que `site` côté Nebula -- SEULEMENT si la cible SNMP
répond une valeur non vide (beaucoup d'équipements laissent ce champ
à sa valeur par défaut, souvent vide ou générique -- jamais créé une
Location "vide" ou un texte par défaut sans valeur informative).
"""

DEFAULT_GLPI_ITEMTYPE = "NetworkEquipment"
HOST_DEDUP_FIELD = "otherserial"


def build_comment(target, system_info):
    """Regroupe les informations SNMP sans équivalent structurel
    direct dans GLPI -- même raisonnement que build_comment dans
    nebula_import.py/excel_import.py."""
    parts = []
    descr = (system_info.get("sysDescr") or "").strip()
    if descr:
        parts.append(f"Description SNMP : {descr}")
    contact = (system_info.get("sysContact") or "").strip()
    if contact:
        parts.append(f"Contact SNMP : {contact}")
    uptime = (system_info.get("sysUpTime") or "").strip()
    if uptime:
        parts.append(f"Uptime SNMP (centièmes de seconde) : {uptime}")
    parts.append(f"Cible SNMP enregistrée : '{target.get('label')}'")
    parts.append("Source : import SNMP (snmp-api)")
    return " | ".join(parts)


def build_glpi_fields(target, system_info, location_id):
    """`target` : une entrée de GET /targets côté snmp-api (id, label,
    host, port). `system_info` : le sous-objet "system" de la réponse
    POST /query pour cette cible (sysDescr, sysName, sysContact,
    sysLocation, sysUpTime)."""
    sys_name = (system_info.get("sysName") or "").strip()
    fields = {"name": sys_name or target.get("label") or target.get("host")}
    if location_id is not None:
        fields["locations_id"] = location_id
    host = target.get("host")
    if host:
        fields[HOST_DEDUP_FIELD] = host
    fields["comment"] = build_comment(target, system_info)
    return fields


def import_targets(glpi_client, snmp_query_fn, targets, dry_run=True, only_ids=None):
    """`targets` : la liste renvoyée par GET /targets (snmp-api) --
    déjà récupérée par l'appelant (voir app.py), cette fonction ne
    fait AUCUN appel réseau vers snmp-api elle-même pour LISTER les
    cibles, mais appelle `snmp_query_fn(target_id)` pour EN
    INTERROGER chacune (injecté -- jamais un vrai appel réseau dans
    un test unitaire). Une cible injoignable ou dont la communauté
    est refusée n'arrête JAMAIS l'import des autres -- même
    philosophie que tout ce projet (#215-225 notamment). Même
    structure de résumé que nebula_import.import_devices pour rester
    cohérent.

    `only_ids` (livraison #269, sélection multiple demandée
    explicitement) -- optionnel, un ensemble d'`id` de cibles SNMP
    (pas d'adresse MAC ici -- une cible SNMP est identifiée par son
    id/hôte, jamais par MAC dans ce module). `None` (défaut) --
    comportement inchangé, toutes les cibles sont traitées."""
    summary = {"created": [], "skipped_existing": [], "skipped_unselected": [], "errors": [], "warnings": []}
    location_cache = {}

    for target in targets:
        name_for_log = target.get("label") or target.get("host") or f"cible #{target.get('id')}"

        if only_ids is not None and target.get("id") not in only_ids:
            summary["skipped_unselected"].append(f"{name_for_log} -- non sélectionné")
            continue

        query_result = snmp_query_fn(target["id"])
        if not query_result or query_result.get("error"):
            error_detail = (query_result or {}).get("error") or "réponse inattendue (vide) de snmp-api"
            summary["errors"].append(f"{name_for_log} : interrogation SNMP échouée -- {error_detail}")
            continue
        system_info = query_result.get("system") or {}

        itemtype = DEFAULT_GLPI_ITEMTYPE
        host = target.get("host")

        if not dry_run and host:
            existing = glpi_client.get_items(itemtype, search_text={HOST_DEDUP_FIELD: host})
            if isinstance(existing, list) and len(existing) > 0:
                summary["skipped_existing"].append(f"{name_for_log} (hôte {host}) -- déjà présent dans GLPI")
                continue

        location_name = (system_info.get("sysLocation") or "").strip()
        location_id = None
        if location_name:
            if location_name not in location_cache:
                location_cache[location_name] = None if dry_run else glpi_client.get_or_create_dropdown("Location", location_name)
            location_id = location_cache[location_name]

        fields = build_glpi_fields(target, system_info, location_id)
        display_name = fields["name"]

        if dry_run:
            summary["created"].append({"key": target["id"], "name": display_name, "itemtype": itemtype, "detail": str(fields)})
            continue

        try:
            new_id = glpi_client.add_item(itemtype, fields)
            summary["created"].append(f"{itemtype} '{display_name}' -- id GLPI {new_id}")
        except Exception as exc:  # noqa: BLE001 -- une cible en échec ne doit jamais arrêter tout l'import
            summary["errors"].append(f"{display_name} ({itemtype}) : {exc}")

    return summary
