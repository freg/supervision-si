"""
Import des exports CSV du portail web Nebula (livraison #200, "note et
évolution nebula" -- "import et présentation des csv sur le modèle
ci-joint"). Distinct de nebula_client.py (#196, API OpenAPI, bloquée
tant que Pro Pack + clé support ne sont pas réunis) -- l'export CSV
est accessible DIRECTEMENT depuis le portail web Nebula standard,
SANS aucun des deux prérequis bloquants. Complémentaire, pas un
remplacement : l'API donne un accès programmable temps réel une fois
débloquée, le CSV donne un accès immédiat mais MANUEL (ou via un
agent à concevoir, voir nebula/README.md).

**Format RÉEL** (déterminé en inspectant les 3 fichiers fournis par
la personne, JAMAIS deviné) :
- Sites : Status, Name, Tags, Devices, Usage, Clients, Offline devices,
  % Offline, Template
- Devices : Status, Device type, Model, Site, MAC address, Tags,
  Clients, Usage, Name
- Clients : Status, Name, MAC address, IPv4 address, Connected to,
  Manufacturer, OS, Policy, Band, Rx rate, Tx rate, SSID name,
  Signal strength, Last seen

Détails réels du format, vérifiés sur les fichiers fournis :
- Encodage UTF-8 AVEC BOM (le premier caractère est invisible, ï»¿) --
  toujours lire avec `encoding="utf-8-sig"`, jamais "utf-8" seul (le
  BOM resterait collé au nom de la première colonne, "Status"
  deviendrait invisible à toute recherche exacte de clé).
- Toutes les valeurs entre guillemets, y compris les nombres --
  colonnes comme "Clients" ou "Devices" arrivent donc en TEXTE, à
  convertir explicitement.
- Champs vides possibles : "Tags" (Firewall sans tag dans l'exemple
  fourni), "Template".
- "Usage" au format libre "164.07 MB"/"16.47 GB"/"0 bytes" -- PAS un
  nombre déjà normalisé -- converti en octets ici pour permettre un
  tri/agrégat cohérent, valeur d'origine conservée en parallèle.
"""
import csv
import io
import re

USAGE_UNIT_MULTIPLIERS = {"bytes": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}
_USAGE_RE = re.compile(r"^([\d.]+)\s*([a-zA-Z]+)$")


def parse_usage_to_bytes(usage_str):
    """"164.07 MB" -> 172032614 (int, octets) -- None si le format
    n'est pas reconnu (jamais une exception, une valeur d'usage
    inattendue ne doit pas faire échouer tout l'import)."""
    if not usage_str or not isinstance(usage_str, str):
        return None
    text = usage_str.strip()
    if text.lower() == "0 bytes":
        return 0
    match = _USAGE_RE.match(text)
    if not match:
        return None
    value, unit = match.groups()
    multiplier = USAGE_UNIT_MULTIPLIERS.get(unit.lower())
    if multiplier is None:
        return None
    try:
        return int(float(value) * multiplier)
    except ValueError:
        return None


def _read_csv_rows(file_bytes):
    """Toujours utf-8-sig (voir docstring du module) -- renvoie une
    liste de dict (DictReader), JAMAIS une exception qui remonterait
    pour un encodage inattendu -- décodage en erreurs="replace" en
    dernier recours plutôt qu'un échec total de l'import."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _to_int(value):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def detect_csv_type(file_bytes):
    """Détecte le type d'export Nebula ('sites', 'devices', 'clients')
    à partir des seules colonnes du fichier -- demandé explicitement
    après un import réel où la personne a importé un export Devices
    via l'onglet Sites, sans erreur visible mais avec des données
    fausses insérées (livraison #235). Se base sur des colonnes
    RÉELLEMENT DISTINCTIVES vérifiées contre les 3 fichiers fournis
    par la personne (#200, voir docstring du module) :
    - "Device type" n'existe QUE dans un export Devices.
    - "Connected to" n'existe QUE dans un export Clients.
    - "Offline devices"/"Template" n'existent QUE dans un export
      Sites, ET un export Sites n'a PAS de colonne "MAC address"
      (contrairement à Devices et Clients qui en ont tous deux une).
    Renvoie `None` si aucune colonne distinctive n'est présente
    (fichier qui ne ressemble à AUCUN des trois formats connus --
    jamais un type deviné par défaut dans ce cas)."""
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])

    has_mac = "MAC address" in headers
    if not has_mac and ("Offline devices" in headers or "Template" in headers or "Devices" in headers):
        return "sites"
    if has_mac and "Device type" in headers:
        return "devices"
    if has_mac and "Connected to" in headers:
        return "clients"
    return None


def parse_sites_csv(file_bytes):
    """Renvoie une liste de dict prêts à insérer (voir schéma
    nebula_sites_import, app.py) -- une ligne par site."""
    rows = _read_csv_rows(file_bytes)
    result = []
    for row in rows:
        name = (row.get("Name") or "").strip()
        if not name:
            continue  # ligne sans nom -- inexploitable, jamais insérée
        result.append({
            "status": (row.get("Status") or "").strip() or None,
            "name": name,
            "tags": (row.get("Tags") or "").strip() or None,
            "devices_count": _to_int(row.get("Devices")),
            "usage": (row.get("Usage") or "").strip() or None,
            "usage_bytes": parse_usage_to_bytes(row.get("Usage")),
            "clients_count": _to_int(row.get("Clients")),
            "offline_devices": _to_int(row.get("Offline devices")),
            "percent_offline": (row.get("% Offline") or "").strip() or None,
            "template": (row.get("Template") or "").strip() or None,
        })
    return result


def parse_devices_csv(file_bytes):
    """Une ligne par appareil Nebula (borne Wi-Fi, switch,
    pare-feu...) -- `mac_address` sert de clé naturelle de
    dédoublonnage/rapprochement dans le temps (voir app.py)."""
    rows = _read_csv_rows(file_bytes)
    result = []
    for row in rows:
        mac = (row.get("MAC address") or "").strip()
        if not mac:
            continue  # sans MAC, aucune clé naturelle -- ligne inexploitable
        result.append({
            "status": (row.get("Status") or "").strip() or None,
            "device_type": (row.get("Device type") or "").strip() or None,
            "model": (row.get("Model") or "").strip() or None,
            "site": (row.get("Site") or "").strip() or None,
            "mac_address": mac,
            "tags": (row.get("Tags") or "").strip() or None,
            "clients_count": _to_int(row.get("Clients")),
            "usage": (row.get("Usage") or "").strip() or None,
            "usage_bytes": parse_usage_to_bytes(row.get("Usage")),
            "name": (row.get("Name") or "").strip() or None,
        })
    return result


def parse_clients_csv(file_bytes):
    """Une ligne par client RÉSEAU connecté (PC, téléphone,
    équipement...) -- `mac_address` sert de clé naturelle."""
    rows = _read_csv_rows(file_bytes)
    result = []
    for row in rows:
        mac = (row.get("MAC address") or "").strip()
        if not mac:
            continue
        result.append({
            "status": (row.get("Status") or "").strip() or None,
            "name": (row.get("Name") or "").strip() or None,
            "mac_address": mac,
            "ipv4_address": (row.get("IPv4 address") or "").strip() or None,
            "connected_to": (row.get("Connected to") or "").strip() or None,
            "manufacturer": (row.get("Manufacturer") or "").strip() or None,
            "os": (row.get("OS") or "").strip() or None,
            "policy": (row.get("Policy") or "").strip() or None,
            "band": (row.get("Band") or "").strip() or None,
            "rx_rate": (row.get("Rx rate") or "").strip() or None,
            "tx_rate": (row.get("Tx rate") or "").strip() or None,
            "ssid_name": (row.get("SSID name") or "").strip() or None,
            "signal_strength": (row.get("Signal strength") or "").strip() or None,
            "last_seen": (row.get("Last seen") or "").strip() or None,
        })
    return result
