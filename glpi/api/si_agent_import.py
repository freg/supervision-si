"""
Hôtes des agents si-agent (#421-#436, backlog 63) vers GLPI, et
comparaison de la flotte si-agent avec les agents que GLPI connaît
(GLPI Agent, itemtype `Agent` de GLPI 10) -- livraison #437, backlog 63
(h) « GLPI : lecture de l'inventaire GLPI Agent via glpi-api ».

Deux directions, comme pour l'exploration réseau (#264) :

1. **si-agent → GLPI** (`import_hosts`) : chaque agent de la flotte
   devient un `Computer` GLPI -- nom = hostname, numéro de série DMI
   s'il est connu, `otherserial` = `si-agent:<agent_id>` (clé de
   dédoublonnage, même rôle que la MAC dans `network_agent_import`),
   fabricant / modèle / lieu = listes déroulantes GLPI
   (`Manufacturer`, `ComputerModel`, `Location` = site de l'agent),
   et un commentaire structuré (OS, noyau, CPU, mémoire, disques,
   interfaces, dernière IP, version d'agent). Dédoublonnage par
   `otherserial`, puis numéro de série, puis nom ; `update_existing`
   met à jour (commentaire, listes) au lieu d'ignorer.
2. **GLPI → si-agent** (`compare_fleets`) : les agents GLPI (table
   `glpi_agents` : name, deviceid, version, last_contact, item lié)
   rapprochés des agents si-agent par nom d'hôte (première étiquette,
   sans domaine ni suffixe de date du deviceid) → ce qui est vu des
   deux côtés, seulement par GLPI Agent, seulement par si-agent.

Logique PURE ici (aucun appel réseau vers si-agent-api : app.py lit
`/fleet` et `/agents/<id>/latest` et passe les données) -- seuls les
appels GLPI passent par le client fourni. ⚠️ Comme le reste du module,
jamais exercé contre un vrai GLPI : les noms de champs (`serial`,
`otherserial`, `manufacturers_id`, `computermodels_id`, `locations_id`)
et l'itemtype `Agent` viennent de la documentation / du schéma GLPI 10,
à confirmer au premier import réel (toujours commencer en dry-run).
"""
import re

DEFAULT_GLPI_ITEMTYPE = "Computer"
AGENT_DEDUP_FIELD = "otherserial"
AGENT_KEY_PREFIX = "si-agent:"
DROPDOWNS = (("manufacturers_id", "Manufacturer", "vendor"), ("computermodels_id", "ComputerModel", "product"))
_DEVICEID_DATE = re.compile(r"-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}$")


def _human_bytes(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return None
    for unit in ("o", "Kio", "Mio", "Gio", "Tio"):
        if n < 1024 or unit == "Tio":
            return ("%d %s" % (n, unit)) if unit == "o" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return None


def host_facts(agent, latest):
    """Ce qu'on sait d'un hôte, à plat : {hostname, agent_id, site,
    serial, vendor, product, os, kernel, cpu, cpus, memory, disks,
    nics, ip, agent_version, last_seen_at}. `latest` = réponse de
    `GET /agents/<id>/latest` (`{task: {data, at, ...}}`)."""
    latest = latest or {}
    inv = ((latest.get("inventory") or {}).get("data")) or {}
    hw = inv.get("hardware") or {}
    host = ((latest.get("host") or {}).get("data")) or {}
    system = host.get("system") or {}
    cpu = hw.get("cpu") or {}
    nics = [n for n in (hw.get("nics") or []) if n.get("mac") and not str(n.get("name", "")).startswith(("lo", "docker", "veth", "br-", "ifb"))]
    disks = [d for d in (hw.get("disks") or []) if d.get("size") and d.get("name")]
    return {
        "hostname": agent.get("hostname") or system.get("hostname") or agent.get("agent_id"),
        "agent_id": agent.get("agent_id"),
        "site": agent.get("site"),
        "label": agent.get("label"),
        "serial": (hw.get("serial") or "").strip() or None,
        "vendor": (hw.get("vendor") or "").strip() or None,
        "product": (hw.get("product") or "").strip() or None,
        "os": agent.get("os") or system.get("os"),
        "kernel": system.get("kernel"),
        "cpu": cpu.get("model") or system.get("cpu_model"),
        "cpus": cpu.get("cpus") or system.get("cpus"),
        "memory": _human_bytes(hw.get("memory_total_bytes") or (host.get("memory") or {}).get("total_bytes")),
        "disks": ["%s %s%s" % (d["name"], d["size"], " (%s)" % d["model"] if d.get("model") else "") for d in disks],
        "nics": ["%s %s" % (n.get("name"), n.get("mac")) for n in nics],
        "ip": agent.get("last_ip"),
        "virtualization": hw.get("virtualization") or cpu.get("hypervisor"),
        "agent_version": agent.get("agent_version") or inv.get("agent_version"),
        "last_seen_at": agent.get("last_seen_at"),
    }


def build_comment(facts):
    parts = []
    if facts.get("os"):
        parts.append("OS : %s%s" % (facts["os"], " (noyau %s)" % facts["kernel"] if facts.get("kernel") else ""))
    if facts.get("cpu"):
        parts.append("CPU : %s%s" % (facts["cpu"], " ×%s" % facts["cpus"] if facts.get("cpus") else ""))
    if facts.get("memory"):
        parts.append("Mémoire : %s" % facts["memory"])
    if facts.get("disks"):
        parts.append("Disques : %s" % ", ".join(facts["disks"]))
    if facts.get("nics"):
        parts.append("Interfaces : %s" % ", ".join(facts["nics"]))
    if facts.get("virtualization"):
        parts.append("Virtualisation : %s" % facts["virtualization"])
    if facts.get("ip"):
        parts.append("Dernière IP : %s" % facts["ip"])
    if facts.get("site"):
        parts.append("Site : %s" % facts["site"])
    if facts.get("label"):
        parts.append("Libellé : %s" % facts["label"])
    parts.append("Agent si-agent %s (%s)%s" % (facts.get("agent_id"), facts.get("agent_version") or "?", ", vu le %s" % facts["last_seen_at"] if facts.get("last_seen_at") else ""))
    parts.append("Source : import Agents hôtes (si-agent-api)")
    return " | ".join(parts)


def build_glpi_fields(facts, dropdown_ids=None):
    """Champs `Computer`. `dropdown_ids` : {champ: id} déjà résolus
    par l'appelant (None en dry-run : les noms sont listés à part)."""
    fields = {"name": facts["hostname"], AGENT_DEDUP_FIELD: AGENT_KEY_PREFIX + str(facts["agent_id"]), "comment": build_comment(facts)}
    if facts.get("serial"):
        fields["serial"] = facts["serial"]
    for field, _itemtype, _src in DROPDOWNS:
        if dropdown_ids and dropdown_ids.get(field):
            fields[field] = dropdown_ids[field]
    if dropdown_ids and dropdown_ids.get("locations_id"):
        fields["locations_id"] = dropdown_ids["locations_id"]
    return fields


def dropdown_names(facts):
    """{champ: (itemtype GLPI, nom)} des listes déroulantes à résoudre."""
    out = {}
    for field, itemtype, src in DROPDOWNS:
        if facts.get(src):
            out[field] = (itemtype, facts[src])
    if facts.get("site"):
        out["locations_id"] = ("Location", facts["site"])
    return out


def _first(items):
    return items[0] if isinstance(items, list) and items else None


def find_existing(glpi_client, facts):
    """(item GLPI | None, critère) : `otherserial` si-agent:<id>, puis
    numéro de série, puis nom exact."""
    key = AGENT_KEY_PREFIX + str(facts["agent_id"])
    hit = _first(glpi_client.get_items(DEFAULT_GLPI_ITEMTYPE, search_text={AGENT_DEDUP_FIELD: key}))
    if hit:
        return hit, "agent"
    if facts.get("serial"):
        hit = _first(glpi_client.get_items(DEFAULT_GLPI_ITEMTYPE, search_text={"serial": facts["serial"]}))
        if hit:
            return hit, "serial"
    for it in glpi_client.get_items(DEFAULT_GLPI_ITEMTYPE, search_text={"name": facts["hostname"]}) or []:
        if isinstance(it, dict) and (it.get("name") or "").lower() == str(facts["hostname"]).lower():
            return it, "name"
    return None, None


def import_hosts(glpi_client, agents, latest_by_agent, dry_run=True, only_agents=None, update_existing=False, check_existing=None, include_never_seen=False):
    """`agents` : `GET /fleet` de si-agent-api ; `latest_by_agent` :
    {agent_id: réponse de /agents/<id>/latest['latest']}. Résumé au
    même format que les autres imports (+ `updated`, `dropdowns`).

    `check_existing` : en dry-run, True si le client peut interroger GLPI
    (session ouverte) -- le dédoublonnage est alors joué à blanc ;
    défaut = not dry_run. `include_never_seen` : un agent enrôlé qui n'a
    jamais contacté le central (pas encore installé) n'est pas un actif :
    écarté (`skipped_excluded`) sauf demande."""
    if check_existing is None:
        check_existing = not dry_run
    only = {str(a).strip() for a in only_agents} if only_agents is not None else None
    summary = {"created": [], "updated": [], "skipped_existing": [], "skipped_excluded": [], "skipped_unselected": [], "errors": [], "warnings": [], "dropdowns": []}
    seen_dropdowns = set()
    for agent in agents:
        agent_id = agent.get("agent_id")
        if not agent_id:
            summary["errors"].append("agent sans identifiant -- ignoré")
            continue
        facts = host_facts(agent, (latest_by_agent or {}).get(agent_id))
        name = facts["hostname"]
        if only is not None and str(agent_id) not in only:
            summary["skipped_unselected"].append("%s (%s) -- non sélectionné" % (name, agent_id))
            continue
        if not agent.get("last_seen_at") and not include_never_seen:
            summary["skipped_excluded"].append("%s (%s) -- agent enrôlé mais jamais vu (pas encore installé)" % (name, agent_id))
            continue
        if not (latest_by_agent or {}).get(agent_id, {}).get("inventory"):
            summary["warnings"].append("%s (%s) : pas encore d'inventaire remonté, fiche minimale (nom, OS, IP)" % (name, agent_id))
        wanted = dropdown_names(facts)
        for field, (itemtype, value) in wanted.items():
            if (itemtype, value) not in seen_dropdowns:
                seen_dropdowns.add((itemtype, value))
                summary["dropdowns"].append({"itemtype": itemtype, "name": value})
        existing, how = (None, None)
        if check_existing:
            try:
                existing, how = find_existing(glpi_client, facts)
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append("%s (%s) : recherche dans GLPI échouée : %s" % (name, agent_id, exc))
                continue
        if dry_run:
            fields = build_glpi_fields(facts)
            if existing:
                target = summary["updated"] if update_existing else summary["skipped_existing"]
                target.append({"key": agent_id, "name": name, "itemtype": DEFAULT_GLPI_ITEMTYPE, "glpi_id": existing.get("id"), "matched_by": how,
                               "detail": str(fields), "dropdowns": {f: v for f, (_t, v) in wanted.items()}} if update_existing else "%s (%s) -- déjà présent dans GLPI (id %s, par %s)" % (name, agent_id, existing.get("id"), how))
            else:
                summary["created"].append({"key": agent_id, "name": name, "itemtype": DEFAULT_GLPI_ITEMTYPE, "detail": str(fields),
                                           "dropdowns": {f: v for f, (_t, v) in wanted.items()}})
            continue
        if existing and not update_existing:
            summary["skipped_existing"].append("%s (%s) -- déjà présent dans GLPI (id %s, par %s)" % (name, agent_id, existing.get("id"), how))
            continue
        try:
            ids = {}
            for field, (itemtype, value) in wanted.items():
                ids[field] = glpi_client.get_or_create_dropdown(itemtype, value)
            fields = build_glpi_fields(facts, ids)
            if existing:
                fields.pop("name", None)  # on ne renomme jamais un actif existant
                glpi_client.update_item(DEFAULT_GLPI_ITEMTYPE, existing["id"], fields)
                summary["updated"].append("%s '%s' -- id GLPI %s mis à jour (trouvé par %s)" % (DEFAULT_GLPI_ITEMTYPE, name, existing["id"], how))
            else:
                new_id = glpi_client.add_item(DEFAULT_GLPI_ITEMTYPE, fields)
                summary["created"].append("%s '%s' -- id GLPI %s" % (DEFAULT_GLPI_ITEMTYPE, name, new_id))
        except Exception as exc:  # noqa: BLE001 -- une ligne en échec n'arrête jamais l'import
            summary["errors"].append("%s (%s) : %s" % (name, DEFAULT_GLPI_ITEMTYPE, exc))
    return summary


# ---- Agents GLPI ↔ agents si-agent ---------------------------------------------

def host_key(name):
    """Clé de rapprochement : première étiquette du nom, minuscules,
    sans le suffixe de date d'un deviceid GLPI Agent
    (`pc-01-2024-05-03-10-22-41`)."""
    if not name:
        return None
    s = _DEVICEID_DATE.sub("", str(name).strip().lower())
    return s.split(".")[0] or None


def compare_fleets(glpi_agents, si_agents):
    """[{hostname, status: both|only_si|only_glpi, si, glpi}] + compteurs."""
    by_key = {}
    for a in si_agents or []:
        k = host_key(a.get("hostname")) or host_key(a.get("agent_id"))
        if not k:
            continue
        by_key.setdefault(k, {"hostname": a.get("hostname") or a.get("agent_id"), "si": None, "glpi": None})
        by_key[k]["si"] = {"agent_id": a.get("agent_id"), "site": a.get("site"), "online": a.get("online"), "last_seen_at": a.get("last_seen_at"),
                           "agent_version": a.get("agent_version"), "os": a.get("os")}
    for g in glpi_agents or []:
        if not isinstance(g, dict):
            continue
        k = host_key(g.get("name")) or host_key(g.get("deviceid"))
        if not k:
            continue
        by_key.setdefault(k, {"hostname": g.get("name") or g.get("deviceid"), "si": None, "glpi": None})
        entry = {"id": g.get("id"), "name": g.get("name"), "deviceid": g.get("deviceid"), "version": g.get("version"), "last_contact": g.get("last_contact"),
                 "itemtype": g.get("itemtype"), "items_id": g.get("items_id"), "remote_addr": g.get("remote_addr")}
        if by_key[k]["glpi"] is None:
            by_key[k]["glpi"] = entry
        else:
            by_key[k].setdefault("glpi_others", []).append(entry)
    rows = []
    for k in sorted(by_key):
        r = by_key[k]
        r["status"] = "both" if r["si"] and r["glpi"] else ("only_si" if r["si"] else "only_glpi")
        rows.append(r)
    counts = {"both": sum(1 for r in rows if r["status"] == "both"), "only_si": sum(1 for r in rows if r["status"] == "only_si"),
              "only_glpi": sum(1 for r in rows if r["status"] == "only_glpi")}
    return {"rows": rows, "counts": counts}
