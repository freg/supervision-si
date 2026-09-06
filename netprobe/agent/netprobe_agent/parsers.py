"""Analyse des sorties d'outils système -- logique PURE, sans aucun
sous-processus ici (voir tasks.py pour l'exécution). Chaque fonction
prend du TEXTE et renvoie un dict ; testée sur des sorties réelles
capturées (tests/test_parsers.py), jamais sur un format supposé.

Outils lus :
- `iw dev <if> link`  -- état du lien WiFi du CLIENT (BSSID, SSID,
  fréquence, signal, débits négociés). C'est ce que #385 déclarait
  "hors de portée" depuis un conteneur : natif sur le Pi, c'est lisible.
- `iw dev <if> scan`  -- bornes VISIBLES depuis ce point, avec canal et
  signal -- occupation des canaux vue d'un client, sans mode moniteur
  (le Pi Zero W n'en est pas capable, et ce n'est pas nécessaire ici).
- `ping`              -- même format que ping_probe.py de netprobe-api.
- `iperf3 -J`         -- même schéma JSON que iperf3_probe.py.
- `/proc` et sysfs    -- santé du Pi (charge, température, uptime).
"""
import json
import re

_LINK_CONNECTED_RE = re.compile(r"^Connected to ([0-9a-fA-F:]{17})", re.M)
# `[ \t]*` et non `\s*` après "SSID:" -- `\s` avale le saut de ligne, et un
# SSID VIDE (borne masquée, "SSID: " suivi de rien) ferait capturer la
# ligne SUIVANTE comme nom de réseau. Trouvé par le test de borne masquée.
_SSID_RE = re.compile(r"^[ \t]*SSID:[ \t]*(.*)$", re.M)
# iw affiche les octets non imprimables échappés (`\x00\x00...`) : un SSID
# fait uniquement de ces octets est une borne masquée, pas un nom.
_HIDDEN_SSID_RE = re.compile(r"^(\\x00)*$")
_FREQ_RE = re.compile(r"^\s*freq:\s*(\d+)", re.M)
_SIGNAL_RE = re.compile(r"^\s*signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", re.M)
_RX_BR_RE = re.compile(r"^\s*rx bitrate:\s*([\d.]+)\s*MBit/s(.*)$", re.M)
_TX_BR_RE = re.compile(r"^\s*tx bitrate:\s*([\d.]+)\s*MBit/s(.*)$", re.M)
_MCS_RE = re.compile(r"MCS\s+(\d+)")
_NSS_RE = re.compile(r"(?:VHT-NSS|HE-NSS|NSS)\s+(\d+)")
_WIDTH_RE = re.compile(r"(\d+)MHz")


def freq_to_channel(freq_mhz):
    """Correspondance fréquence -> canal (2,4 GHz, 5 GHz, 6 GHz). Renvoie
    None hors des plages connues plutôt qu'un canal inventé."""
    try:
        f = int(freq_mhz)
    except (TypeError, ValueError):
        return None
    if f == 2484:
        return 14
    if 2412 <= f <= 2472 and (f - 2407) % 5 == 0:
        return (f - 2407) // 5
    if 5000 < f < 5900 and (f - 5000) % 5 == 0:
        return (f - 5000) // 5
    if 5955 <= f <= 7115 and (f - 5950) % 5 == 0:
        return (f - 5950) // 5
    return None


def band_of(freq_mhz):
    try:
        f = int(freq_mhz)
    except (TypeError, ValueError):
        return None
    if 2400 <= f < 2500:
        return "2.4"
    if 5000 <= f < 5900:
        return "5"
    if 5900 <= f <= 7200:
        return "6"
    return None


def _bitrate(match):
    if not match:
        return None, {}
    mbps = float(match.group(1))
    tail = match.group(2) or ""
    extra = {}
    m = _MCS_RE.search(tail)
    if m:
        extra["mcs"] = int(m.group(1))
    m = _NSS_RE.search(tail)
    if m:
        extra["nss"] = int(m.group(1))
    m = _WIDTH_RE.search(tail)
    if m:
        extra["width_mhz"] = int(m.group(1))
    if "short GI" in tail:
        extra["short_gi"] = True
    return mbps, extra


def parse_iw_link(text):
    """`iw dev wlan0 link`. Non connecté -> {"connected": False}. Les
    champs absents restent None (un pilote qui n'expose pas le débit rx
    n'est pas une erreur)."""
    text = text or ""
    m = _LINK_CONNECTED_RE.search(text)
    if not m:
        return {"connected": False}
    out = {"connected": True, "bssid": m.group(1).lower()}
    s = _SSID_RE.search(text)
    out["ssid"] = (s.group(1).strip() or None) if s else None
    f = _FREQ_RE.search(text)
    out["freq_mhz"] = int(f.group(1)) if f else None
    out["channel"] = freq_to_channel(out["freq_mhz"])
    out["band"] = band_of(out["freq_mhz"])
    sig = _SIGNAL_RE.search(text)
    out["signal_dbm"] = float(sig.group(1)) if sig else None
    rx, rx_extra = _bitrate(_RX_BR_RE.search(text))
    tx, tx_extra = _bitrate(_TX_BR_RE.search(text))
    out["rx_bitrate_mbps"] = rx
    out["tx_bitrate_mbps"] = tx
    if rx_extra:
        out["rx_extra"] = rx_extra
    if tx_extra:
        out["tx_extra"] = tx_extra
    return out


_BSS_RE = re.compile(r"^BSS ([0-9a-fA-F:]{17})", re.M)
_DS_CHANNEL_RE = re.compile(r"^\s*DS Parameter set:\s*channel\s*(\d+)", re.M)
_PRIMARY_RE = re.compile(r"^\s*\*\s*primary channel:\s*(\d+)", re.M)
_VHT_WIDTH_RE = re.compile(r"^\s*\*\s*channel width:\s*\d+\s*\((\d+)\s*MHz\)", re.M)
_HT_SEC_RE = re.compile(r"^\s*\*\s*secondary channel offset:\s*(\S+)", re.M)
_LAST_SEEN_RE = re.compile(r"^\s*last seen:\s*(\d+)\s*ms ago", re.M)
_SCAN_SIGNAL_RE = re.compile(r"^\s*signal:\s*(-?\d+(?:\.\d+)?)\s*dBm", re.M)


def _split_bss_blocks(text):
    positions = [m.start() for m in _BSS_RE.finditer(text)]
    blocks = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        blocks.append(text[start:end])
    return blocks


def parse_iw_scan(text, own_bssid=None):
    """`iw dev wlan0 scan` -> liste de bornes visibles + synthèse par
    canal. `own_bssid` (celui du lien courant) est marqué `is_ours`
    pour distinguer notre infrastructure des voisins/parasites."""
    networks = []
    for block in _split_bss_blocks(text or ""):
        bssid = _BSS_RE.match(block).group(1).lower()
        ssid_m = _SSID_RE.search(block)
        freq_m = _FREQ_RE.search(block)
        sig_m = _SCAN_SIGNAL_RE.search(block)
        freq = int(freq_m.group(1)) if freq_m else None
        channel = None
        ds = _DS_CHANNEL_RE.search(block)
        prim = _PRIMARY_RE.search(block)
        if ds:
            channel = int(ds.group(1))
        elif prim:
            channel = int(prim.group(1))
        else:
            channel = freq_to_channel(freq)
        width = 20
        vht = _VHT_WIDTH_RE.search(block)
        sec = _HT_SEC_RE.search(block)
        if vht:
            width = int(vht.group(1))
        elif sec and sec.group(1) not in ("no", "no secondary"):
            width = 40
        ssid = ssid_m.group(1).strip() if ssid_m else ""
        if _HIDDEN_SSID_RE.match(ssid):
            ssid = ""
        net = {
            "bssid": bssid,
            "ssid": ssid or None,
            "hidden": not ssid,
            "freq_mhz": freq,
            "band": band_of(freq),
            "channel": channel,
            "width_mhz": width,
            "signal_dbm": float(sig_m.group(1)) if sig_m else None,
            "security": "WPA2" if "\n\tRSN:" in block or "RSN:" in block else ("WPA" if "WPA:" in block else ("open" if "Privacy" not in block else "WEP?")),
        }
        ls = _LAST_SEEN_RE.search(block)
        if ls:
            net["last_seen_ms"] = int(ls.group(1))
        if own_bssid and bssid == own_bssid.lower():
            net["is_ours"] = True
        networks.append(net)
    networks.sort(key=lambda n: (n["signal_dbm"] is None, -(n["signal_dbm"] or -999)))
    return {"networks": networks, "summary": summarize_scan(networks, own_bssid)}


def summarize_scan(networks, own_bssid=None):
    """Synthèse compacte -- c'est ELLE que le central garde en priorité
    pour les graphiques (la liste complète est volumineuse) : nombre de
    bornes par bande et par canal, plus fort voisin co-canal de NOTRE
    borne (= candidat interférence WiFi sur le même canal)."""
    by_band = {}
    by_channel = {}
    ours = None
    for n in networks:
        if n.get("band"):
            by_band[n["band"]] = by_band.get(n["band"], 0) + 1
        if n.get("channel") is not None:
            key = "%s/%s" % (n.get("band") or "?", n["channel"])
            by_channel[key] = by_channel.get(key, 0) + 1
        if own_bssid and n["bssid"] == own_bssid.lower():
            ours = n
    summary = {
        "total": len(networks),
        "hidden": sum(1 for n in networks if n.get("hidden")),
        "by_band": by_band,
        "by_channel": by_channel,
    }
    if ours and ours.get("channel") is not None:
        co = [n for n in networks
              if n is not ours and n.get("band") == ours.get("band") and n.get("channel") == ours.get("channel")
              and n.get("signal_dbm") is not None]
        summary["our_channel"] = "%s/%s" % (ours.get("band"), ours["channel"])
        summary["co_channel_count"] = len(co)
        if co:
            strongest = max(co, key=lambda n: n["signal_dbm"])
            summary["strongest_co_channel"] = {
                "bssid": strongest["bssid"], "ssid": strongest.get("ssid"), "signal_dbm": strongest["signal_dbm"],
            }
    return summary


_PING_TX_RE = re.compile(r"(\d+) packets transmitted, (\d+) (?:packets )?received")
_PING_LOSS_RE = re.compile(r"([\d.]+)% packet loss")
_PING_RTT_RE = re.compile(r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms")


def parse_ping(text):
    """Sortie de `ping -c N`. Même expressions que ping_probe.py, plus le
    détail min/max/mdev utile pour la gigue côté WiFi."""
    text = text or ""
    out = {"sent": None, "received": None, "loss_pct": None,
           "rtt_min_ms": None, "rtt_avg_ms": None, "rtt_max_ms": None, "rtt_mdev_ms": None}
    m = _PING_TX_RE.search(text)
    if m:
        out["sent"] = int(m.group(1))
        out["received"] = int(m.group(2))
    m = _PING_LOSS_RE.search(text)
    if m:
        out["loss_pct"] = float(m.group(1))
    m = _PING_RTT_RE.search(text)
    if m:
        out["rtt_min_ms"], out["rtt_avg_ms"], out["rtt_max_ms"], out["rtt_mdev_ms"] = (float(m.group(i)) for i in range(1, 5))
    out["ok"] = bool(out["received"])
    return out


def parse_iperf3_json(text):
    """Sortie `iperf3 -c ... -J`. Même schéma que iperf3_probe.py."""
    try:
        data = json.loads(text or "")
    except ValueError:
        return {"ok": False, "error": "JSON iperf3 invalide"}
    if not isinstance(data, dict):
        return {"ok": False, "error": "JSON iperf3 inattendu"}
    if data.get("error"):
        return {"ok": False, "error": str(data["error"])[:300]}
    end = data.get("end") or {}
    sent = end.get("sum_sent") or {}
    recv = end.get("sum_received") or {}
    if sent.get("bits_per_second") is None and recv.get("bits_per_second") is None:
        return {"ok": False, "error": "résultat iperf3 incomplet"}
    return {
        "ok": True,
        "sent_mbps": round(sent["bits_per_second"] / 1e6, 2) if sent.get("bits_per_second") is not None else None,
        "received_mbps": round(recv["bits_per_second"] / 1e6, 2) if recv.get("bits_per_second") is not None else None,
        "retransmits": sent.get("retransmits"),
    }


def parse_loadavg(text):
    """/proc/loadavg : "0.12 0.08 0.02 1/123 4567"."""
    try:
        parts = (text or "").split()
        return {"load1": float(parts[0]), "load5": float(parts[1]), "load15": float(parts[2])}
    except (IndexError, ValueError):
        return {}


def parse_uptime(text):
    try:
        return {"uptime_s": int(float((text or "").split()[0]))}
    except (IndexError, ValueError):
        return {}


def parse_thermal(text):
    """sysfs thermal_zone0/temp : millidegrés."""
    try:
        return {"cpu_temp_c": round(int((text or "").strip()) / 1000.0, 1)}
    except ValueError:
        return {}


def parse_meminfo(text):
    out = {}
    for line in (text or "").splitlines():
        if line.startswith("MemTotal:") or line.startswith("MemAvailable:"):
            key = "mem_total_kb" if line.startswith("MemTotal") else "mem_available_kb"
            try:
                out[key] = int(line.split()[1])
            except (IndexError, ValueError):
                pass
    return out
