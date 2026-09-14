# -*- coding: utf-8 -*-
"""Constructeur d'après l'adresse MAC (préfixe OUI, 3 premiers octets)
-- livraison #506, facette « équipements réseau » de l'exploration.

Deux sources, dans l'ordre :
  1. le fichier IEEE complet s'il est présent dans le volume de données
     (`/data/oui.csv` -- format « MA-L » de standards-oui.ieee.org, ou
     `oui.txt` historique) : ~35 000 préfixes, la référence ;
  2. sinon une AMORCE embarquée ci-dessous : les constructeurs qui
     comptent pour cette facette (routeurs/switchs), quelques préfixes
     chacun, suffisante pour reconnaître un MikroTik récent ou un
     Cisco/HP/3Com/Nortel de la génération d'origine de la boucle
     locale, PAS exhaustive -- un préfixe absent donne `None`, jamais
     un constructeur inventé.

Chaque entrée porte une CATÉGORIE : « reseau » (constructeur
d'équipements réseau -- indice fort pour la classification),
« virtualisation » (MAC d'hyperviseur : jamais un routeur physique),
« sbc » (Raspberry Pi et cousins), « hote » (constructeur de PC/serveurs)
-- les catégories nourrissent `identify.classify`, pas seulement
l'affichage.
"""
import csv
import os
import re

_HEX = re.compile(r"[^0-9A-Fa-f]")

# (préfixe sans séparateur, majuscules) -> (constructeur, catégorie)
SEED = {}


def _seed(vendor, category, *prefixes):
    for p in prefixes:
        SEED[p.replace(":", "").upper()] = (vendor, category)


# --- Équipements réseau ------------------------------------------------
_seed("MikroTik", "reseau",
      "00:0C:42", "4C:5E:0C", "6C:3B:6B", "B8:69:F4", "CC:2D:E0", "D4:CA:6D", "E4:8D:8C",
      "74:4D:28", "64:D1:54", "DC:2C:6E", "2C:C8:1B", "48:8F:5A", "C4:AD:34", "18:FD:74",
      "08:55:31", "78:9A:18")
_seed("Cisco", "reseau",
      # années 1990-2000 (routeurs 1600/2500/2600/3600, Catalyst 1900/2900/5000)
      "00:00:0C", "00:10:07", "00:10:0B", "00:10:0D", "00:10:11", "00:10:14", "00:10:1F",
      "00:10:29", "00:10:2F", "00:10:54", "00:10:79", "00:10:7B", "00:10:A6", "00:10:F6",
      "00:10:FF", "00:30:19", "00:30:24", "00:30:40", "00:30:71", "00:30:78", "00:30:7B",
      "00:30:80", "00:30:85", "00:30:94", "00:30:96", "00:30:A3", "00:30:B6", "00:30:F2",
      "00:50:0B", "00:50:0F", "00:50:14", "00:50:2A", "00:50:3E", "00:50:50", "00:50:53",
      "00:50:54", "00:50:73", "00:50:80", "00:50:A2", "00:50:A7", "00:50:BD", "00:50:D1",
      "00:50:E2", "00:50:F0", "00:60:09", "00:60:2F", "00:60:3E", "00:60:47", "00:60:5C",
      "00:60:70", "00:60:83", "00:90:0C", "00:90:21", "00:90:2B", "00:90:5F", "00:90:6D",
      "00:90:6F", "00:90:86", "00:90:92", "00:90:A6", "00:90:AB", "00:90:B1", "00:90:BF",
      "00:90:D9", "00:90:F2", "00:B0:4A", "00:B0:64", "00:B0:8E", "00:B0:C2", "00:D0:06",
      "00:D0:58", "00:D0:63", "00:D0:79", "00:D0:90", "00:D0:97", "00:D0:BA", "00:D0:BB",
      "00:D0:BC", "00:D0:C0", "00:D0:D3", "00:D0:E4", "00:D0:FF", "00:E0:14", "00:E0:1E",
      "00:E0:34", "00:E0:4F", "00:E0:8F", "00:E0:A3", "00:E0:B0", "00:E0:F7", "00:E0:F9",
      "00:E0:FE",
      # années 2000-2010
      "00:01:42", "00:01:43", "00:01:96", "00:01:97", "00:02:4A", "00:02:4B", "00:03:6B",
      "00:03:6C", "00:04:27", "00:04:28", "00:05:5E", "00:05:5F", "00:06:28", "00:06:2A",
      "00:07:0D", "00:07:0E", "00:08:20", "00:08:21", "00:09:43", "00:09:44", "00:0A:41",
      "00:0A:42", "00:0B:BE", "00:0B:BF", "00:0C:30", "00:0C:31", "00:0D:28", "00:0D:29",
      "00:0E:38", "00:0E:39", "00:0F:23", "00:0F:24", "00:1A:A1", "00:1B:D4", "00:1C:0E",
      "00:1E:13", "00:21:1B", "00:22:55", "00:23:04", "00:24:13", "00:25:45", "00:26:0A")
_seed("HP ProCurve / HPE", "reseau",
      "08:00:09", "00:80:5F", "00:60:B0", "00:30:6E", "00:30:C1", "00:10:83", "00:0E:7F",
      "00:11:0A", "00:12:79", "00:14:38", "00:14:C2", "00:16:35", "00:17:A4", "00:18:71",
      "00:1B:78", "00:1C:2E", "00:1F:29", "00:21:5A", "00:23:7D", "00:24:81", "00:25:B3",
      "00:26:55", "3C:4A:92", "78:AC:C0", "78:E7:D1", "D4:85:64", "E8:39:35")
_seed("Aruba (HPE)", "reseau",
      "00:0B:86", "00:1A:1E", "00:24:6C", "04:BD:88", "18:64:72", "20:4C:03", "24:DE:C6",
      "40:E3:D6", "6C:F3:7F", "70:3A:0E", "84:D4:7E", "94:B4:0F", "9C:1C:12", "AC:A3:1E", "D8:C7:C8")
_seed("3Com", "reseau",
      "00:01:02", "00:01:03", "00:04:76", "00:0A:04", "00:0A:5E", "00:10:4B", "00:10:5A",
      "00:20:AF", "00:50:04", "00:50:99", "00:50:DA", "00:60:08", "00:60:8C", "00:60:97", "00:A0:24")
_seed("Nortel / Bay Networks", "reseau",
      "00:00:81", "00:04:38", "00:0E:62", "00:11:F9", "00:15:40", "00:16:CA", "00:60:38",
      "00:80:2D", "00:E0:16", "00:E0:7B")
_seed("Netgear", "reseau",
      "00:09:5B", "00:0F:B5", "00:14:6C", "00:18:4D", "00:1B:2F", "00:1E:2A", "00:1F:33",
      "00:22:3F", "00:24:B2", "00:26:F2", "20:4E:7F", "28:C6:8E", "2C:B0:5D", "30:46:9A",
      "44:94:FC", "6C:B0:CE", "84:1B:5E", "A0:21:B7", "A4:2B:8C", "C0:3F:0E", "C4:04:15", "E0:91:F5")
_seed("Linksys (Cisco)", "reseau",
      "00:0C:41", "00:0F:66", "00:12:17", "00:13:10", "00:14:BF", "00:16:B6", "00:18:39",
      "00:18:F8", "00:1A:70", "00:1C:10", "00:1D:7E", "00:1E:E5", "00:21:29", "00:22:6B",
      "00:23:69", "00:25:9C", "48:F8:B3", "58:6D:8F", "C0:C1:C0", "C8:D7:19")
_seed("Juniper", "reseau",
      "00:05:85", "00:10:DB", "00:12:1E", "00:14:F6", "00:17:CB", "00:19:E2", "00:1B:C0",
      "00:1D:B5", "00:1F:12", "00:21:59", "00:22:83", "00:23:9C", "00:24:DC", "00:26:88",
      "2C:21:72", "3C:61:04", "40:B4:F0", "54:E0:32", "5C:5E:AB", "78:19:F7", "80:71:1F",
      "84:B5:9C", "88:E0:F3", "AC:4B:C8", "B0:C6:9A", "CC:E1:7F", "F0:1C:2D", "F4:B5:2F")
_seed("D-Link", "reseau",
      "00:05:5D", "00:0D:88", "00:0F:3D", "00:11:95", "00:13:46", "00:15:E9", "00:17:9A",
      "00:19:5B", "00:1B:11", "00:1C:F0", "00:1E:58", "00:21:91", "00:22:B0", "00:24:01",
      "00:26:5A", "00:50:BA", "00:80:C8", "14:D6:4D", "1C:7E:E5", "1C:AF:F7", "1C:BD:B9",
      "28:10:7B", "34:08:04", "5C:D9:98", "78:54:2E", "84:C9:B2", "90:94:E4", "AC:F1:DF",
      "B8:A3:86", "C8:BE:19", "C8:D3:A3", "CC:B2:55", "F0:7D:68")
_seed("Ubiquiti", "reseau",
      "00:15:6D", "00:27:22", "04:18:D6", "18:E8:29", "24:A4:3C", "44:D9:E7", "60:22:32",
      "68:72:51", "74:83:C2", "78:8A:20", "80:2A:A8", "B4:FB:E4", "DC:9F:DB", "E0:63:DA",
      "F0:9F:C2", "FC:EC:DA")
_seed("Zyxel", "reseau",
      "00:13:49", "00:19:CB", "00:1E:33", "00:23:F8", "00:A0:C5", "28:28:5D", "40:4A:03",
      "50:67:F0", "5C:6A:80", "5C:E2:8C", "90:EF:68", "A0:E4:CB", "B0:B2:DC", "B8:EC:A3",
      "C8:6C:87", "CC:5D:4E", "D8:EC:E5", "E4:18:6B", "EC:43:F6", "F8:62:AA")
_seed("Alcatel-Lucent Enterprise", "reseau", "00:20:DA", "00:D0:95", "00:E0:B1")
_seed("Extreme Networks", "reseau", "00:01:30", "00:04:96", "00:E0:2B")
_seed("Fortinet", "reseau", "00:09:0F", "08:5B:0E", "70:4C:A5", "90:6C:AC", "E8:1C:BA")
_seed("TP-Link", "reseau",
      "00:27:19", "14:CC:20", "18:A6:F7", "30:B5:C2", "50:C7:BF", "54:C8:0F", "60:E3:27",
      "64:70:02", "8C:21:0A", "98:DA:C4", "A4:2B:B0", "B0:4E:26", "C0:4A:00", "E8:DE:27", "EC:08:6B")
# --- Onduleurs / cartes réseau d'onduleur ----------------------------
_seed("APC (Schneider)", "onduleur", "00:C0:B7", "28:29:86")
# --- Virtualisation --------------------------------------------------
_seed("VMware", "virtualisation", "00:50:56", "00:0C:29", "00:05:69", "00:1C:14")
_seed("QEMU/KVM (Proxmox)", "virtualisation", "52:54:00")
_seed("Xen", "virtualisation", "00:16:3E")
_seed("Microsoft Hyper-V", "virtualisation", "00:15:5D")
_seed("Parallels", "virtualisation", "00:1C:42")
_seed("VirtualBox", "virtualisation", "08:00:27")
_seed("Docker", "virtualisation", "02:42")
# --- SBC ------------------------------------------------------------
_seed("Raspberry Pi", "sbc", "B8:27:EB", "DC:A6:32", "E4:5F:01", "28:CD:C1", "D8:3A:DD", "2C:CF:67")
# --- Hôtes (indice « ce n'est pas un routeur ») ----------------------
_seed("Dell", "hote", "00:14:22", "00:1A:A0", "00:21:70", "00:24:E8", "00:C0:4F", "14:FE:B5",
      "18:03:73", "18:DB:F2", "24:B6:FD", "34:17:EB", "54:9F:35", "5C:F9:DD", "74:86:7A",
      "78:2B:CB", "84:2B:2B", "B0:83:FE", "B8:AC:6F", "C8:1F:66", "D4:AE:52", "D4:BE:D9",
      "E4:54:E8", "F0:1F:AF", "F8:B1:56", "F8:BC:12", "F8:DB:88")
_seed("Synology", "stockage", "00:11:32")
_seed("QNAP", "stockage", "24:5E:BE", "00:08:9B")


def normalize_mac(mac):
    """« 4c:5e:0c:aa:bb:cc », « 4C-5E-0C-…», « 4c5e.0caa.bbcc » ->
    « 4C:5E:0C:AA:BB:CC » ; None si ce n'est pas 12 hexadécimaux."""
    if not mac:
        return None
    hexs = _HEX.sub("", str(mac)).upper()
    if len(hexs) != 12:
        return None
    return ":".join(hexs[i:i + 2] for i in range(0, 12, 2))


def is_locally_administered(mac):
    """Bit « localement administré » du premier octet : MAC aléatoire
    (Wi-Fi privé, VM, conteneur) -- l'OUI ne désigne alors PERSONNE."""
    n = normalize_mac(mac)
    if not n:
        return False
    return bool(int(n[:2], 16) & 0x02)


class OuiTable:
    """Table de résolution : amorce embarquée + fichier IEEE optionnel."""

    def __init__(self, path=None):
        self.entries = dict(SEED)
        self.file_entries = 0
        self.path = path
        if path and os.path.exists(path):
            self.file_entries = self.load_file(path)

    def load_file(self, path):
        """Charge `oui.csv` (colonnes Registry,Assignment,Organization
        Name,…) ou `oui.txt` (lignes « 00-00-0C   (hex)   Cisco Systems »).
        Les entrées du fichier COMPLÈTENT l'amorce (le fichier fait foi
        pour le NOM, la catégorie de l'amorce est conservée)."""
        count = 0
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(2048)
            fh.seek(0)
            if "Assignment" in head and "," in head:
                reader = csv.DictReader(fh)
                for row in reader:
                    prefix = (row.get("Assignment") or "").strip().upper()
                    name = (row.get("Organization Name") or "").strip()
                    if len(prefix) == 6 and name:
                        self._put(prefix, name)
                        count += 1
            else:
                rx = re.compile(r"^\s*([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})\s+\(hex\)\s+(.+?)\s*$")
                for line in fh:
                    m = rx.match(line)
                    if m:
                        self._put((m.group(1) + m.group(2) + m.group(3)).upper(), m.group(4))
                        count += 1
        return count

    def _put(self, prefix, name):
        old = self.entries.get(prefix)
        category = old[1] if old else _category_from_name(name)
        self.entries[prefix] = (name, category)

    def lookup(self, mac):
        """-> {vendor, category, prefix, source} ou None."""
        n = normalize_mac(mac)
        if not n:
            return None
        if is_locally_administered(n) and not n.startswith("02:42"):
            return {"vendor": None, "category": "locale", "prefix": n[:8], "source": "bit local"}
        # Docker : 02:42 est un préfixe sur 2 octets (localement administré)
        if n.startswith("02:42:"):
            return {"vendor": "Docker", "category": "virtualisation", "prefix": "02:42", "source": "amorce"}
        key = n.replace(":", "")[:6]
        hit = self.entries.get(key)
        if not hit:
            return None
        return {"vendor": hit[0], "category": hit[1], "prefix": n[:8],
                "source": "fichier IEEE" if self.file_entries and key not in SEED else "amorce"}


_NETWORK_NAME_RE = re.compile(
    r"cisco|mikrotik|hewlett|hp inc|hewlett packard|aruba|juniper|3com|nortel|bay networks|netgear|"
    r"d-link|dlink|ubiquiti|zyxel|alcatel|extreme|fortinet|tp-link|huawei|arista|brocade|foundry|"
    r"allied telesis|edgecore|edge-core|ruckus|meraki|sonicwall|watchguard|palo alto|f5 networks|"
    r"avaya|enterasys|cabletron|adtran|lancom|teltonika|draytek|planet technology|moxa|hirschmann|"
    r"phoenix contact|siemens.*(network|scalance)|\bnetworks?\b",
    re.I)
_VIRT_NAME_RE = re.compile(r"vmware|xensource|red hat|qemu|virtualbox|oracle virtual|parallels", re.I)


def _category_from_name(name):
    if _NETWORK_NAME_RE.search(name or ""):
        return "reseau"
    if _VIRT_NAME_RE.search(name or ""):
        return "virtualisation"
    if re.search(r"raspberry", name or "", re.I):
        return "sbc"
    return "autre"
