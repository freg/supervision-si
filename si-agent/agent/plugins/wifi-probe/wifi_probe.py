#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde Wi-Fi « expérience client » (livraison #525, famille « explorer »).

Le poste porte l'agent est associé, comme un utilisateur, au SSID à observer
(interface Wi-Fi sans route par défaut : l'Ethernet reste le chemin vers le
central). La sonde mesure ce qu'un flux vidéo / cast subirait :

- lien (iw link / station dump) : borne (BSSID), fréquence, RSSI, débits
  négociés tx/rx, retransmissions et échecs d'émission (le vrai symptôme d'un
  canal encombré), pertes de balises ;
- canal (iw survey dump) : temps actif / occupé / émission / réception -- le
  taux d'occupation vu par la puce, y compris le trafic des autres ;
  compteurs cumulés sur beaucoup de pilotes -> delta avec le passage précédent ;
- voisinage (iw scan) : bornes visibles par canal, co-canal, et l'élément
  « BSS Load » des balises (nombre de stations, utilisation du canal vue par
  la borne elle-même) ;
- chemin (ping vers la passerelle du Wi-Fi) : latence, gigue (mdev), pertes ;
- optionnel (iperf3 -u vers un serveur du LAN) : gigue et pertes d'un flux
  UDP de type cast.

Alertes (jamais d'action) : non associé, RSSI faible, retransmissions,
occupation du canal, débit négocié bas, gigue / pertes, borne chargée.
Stdlib seulement ; `iw`, `ping`, `ip` requis ; `iperf3` facultatif.

Usage : wifi_probe.py [--iface auto|wlan0] [--target auto|IP] [--iperf HOST]
                      [--no-scan] [--state FICHIER]
"""
import json
import os
import re
import subprocess
import sys
import time

VERSION = "1"
STATE_DEFAULT = "/var/lib/si-agent/wifi-probe.state.json"
THRESHOLDS = {"rssi_warn": -70, "rssi_crit": -80, "retry_pct_warn": 15.0, "retry_pct_crit": 30.0,
              "busy_pct_warn": 60.0, "busy_pct_crit": 80.0, "tx_mbit_warn": 24.0, "jitter_ms_warn": 30.0,
              "loss_pct_warn": 1.0, "loss_pct_crit": 5.0, "latency_ms_warn": 50.0,
              "bss_util_pct_warn": 60.0, "bss_stations_warn": 40, "beacon_loss_warn": 5}


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


# --- analyseurs (purs, testés) -------------------------------------------

def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_link(text):
    """`iw dev X link` -> {connected, bssid, ssid, freq, signal_dbm, tx_mbit, rx_mbit, tx_mcs, rx_mcs}."""
    out = {"connected": False}
    if not text or text.strip().startswith("Not connected"):
        return out
    m = re.search(r"Connected to ([0-9a-f:]{17})", text, re.I)
    if not m:
        return out
    out["connected"] = True
    out["bssid"] = m.group(1).lower()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("SSID:"):
            out["ssid"] = line[5:].strip()
        elif line.startswith("freq:"):
            out["freq"] = int(_num(line.split(":", 1)[1].strip().split()[0]) or 0)
        elif line.startswith("signal:"):
            out["signal_dbm"] = _num(line.split(":", 1)[1].strip().split()[0])
        elif line.startswith("tx bitrate:") or line.startswith("rx bitrate:"):
            key = "tx" if line.startswith("tx") else "rx"
            rest = line.split(":", 1)[1].strip()
            out[key + "_mbit"] = _num(rest.split()[0])
            out[key + "_mcs"] = " ".join(rest.split()[2:])[:60]
    if out.get("freq"):
        out["band"] = "2.4 GHz" if out["freq"] < 3000 else ("6 GHz" if out["freq"] >= 5925 else "5 GHz")
        out["channel"] = freq_to_channel(out["freq"])
    return out


def freq_to_channel(freq):
    if not freq:
        return None
    if freq == 2484:
        return 14
    if freq < 2484:
        return int((freq - 2407) / 5)
    if freq >= 5925:
        return int((freq - 5950) / 5)
    return int((freq - 5000) / 5)


def parse_station(text):
    """`iw dev X station dump` (une station : la borne) -> compteurs et taux."""
    out = {}
    if not text:
        return out
    keys = {"tx packets": "tx_packets", "tx retries": "tx_retries", "tx failed": "tx_failed", "rx packets": "rx_packets",
            "rx drop misc": "rx_drop", "beacon loss": "beacon_loss", "connected time": "connected_s",
            "inactive time": "inactive_ms"}
    for line in text.splitlines():
        line = line.strip()
        for k, name in keys.items():
            if line.startswith(k + ":"):
                out[name] = int(_num(line.split(":", 1)[1].strip().split()[0]) or 0)
        if line.startswith("signal avg:"):
            out["signal_avg_dbm"] = _num(line.split(":", 1)[1].strip().split()[0])
        elif line.startswith("expected throughput:"):
            out["expected_mbit"] = _num(re.sub(r"[^0-9.]", "", line.split(":", 1)[1].strip().split("Mbps")[0]))
    return out


def rates(cur, prev):
    """Taux de retransmission / échec sur le DELTA (compteurs cumulés) ou en
    absolu si pas de passage précédent comparable."""
    out = {}
    tx = cur.get("tx_packets")
    if tx is None:
        return out
    d = {}
    for k in ("tx_packets", "tx_retries", "tx_failed"):
        c, p = cur.get(k), (prev or {}).get(k)
        d[k] = (c - p) if (p is not None and c is not None and c >= p) else c
    base = d.get("tx_packets") or 0
    if base > 0:
        out["retry_pct"] = round(100.0 * (d.get("tx_retries") or 0) / base, 1)
        out["failed_pct"] = round(100.0 * (d.get("tx_failed") or 0) / base, 2)
        out["window_packets"] = base
    out["delta"] = prev is not None and (prev or {}).get("tx_packets") is not None and (cur.get("tx_packets") or 0) >= (prev or {}).get("tx_packets", 0)
    return out


def parse_survey(text):
    """`iw dev X survey dump` -> liste [{freq, in_use, noise, active_ms, busy_ms, rx_ms, tx_ms}]."""
    out, cur = [], None
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("Survey data from"):
            cur = {}
            out.append(cur)
        elif cur is None:
            continue
        elif s.startswith("frequency:"):
            cur["freq"] = int(_num(s.split(":", 1)[1].strip().split()[0]) or 0)
            cur["in_use"] = "[in use]" in s
        elif s.startswith("noise:"):
            cur["noise"] = _num(s.split(":", 1)[1].strip().split()[0])
        elif s.startswith("channel active time:"):
            cur["active_ms"] = int(_num(s.split(":", 1)[1].strip().split()[0]) or 0)
        elif s.startswith("channel busy time:"):
            cur["busy_ms"] = int(_num(s.split(":", 1)[1].strip().split()[0]) or 0)
        elif s.startswith("channel receive time:"):
            cur["rx_ms"] = int(_num(s.split(":", 1)[1].strip().split()[0]) or 0)
        elif s.startswith("channel transmit time:"):
            cur["tx_ms"] = int(_num(s.split(":", 1)[1].strip().split()[0]) or 0)
    return [c for c in out if c.get("freq")]


def channel_usage(survey, prev_survey=None):
    """Occupation du canal en usage, sur le delta si les compteurs sont cumulés
    (croissants) sinon en absolu ; None si rien d'exploitable."""
    cur = next((s for s in survey if s.get("in_use")), None)
    if not cur or not cur.get("active_ms"):
        return None
    prev = next((s for s in (prev_survey or []) if s.get("freq") == cur.get("freq")), None)
    a, b, tx, rx = cur.get("active_ms", 0), cur.get("busy_ms", 0), cur.get("tx_ms", 0), cur.get("rx_ms", 0)
    delta = False
    if prev and prev.get("active_ms") is not None and a > prev["active_ms"] and b >= prev.get("busy_ms", 0):
        a, b = a - prev["active_ms"], b - prev.get("busy_ms", 0)
        tx, rx = max(0, tx - prev.get("tx_ms", 0)), max(0, rx - prev.get("rx_ms", 0))
        delta = True
    if a <= 0:
        return None
    return {"freq": cur["freq"], "noise_dbm": cur.get("noise"), "busy_pct": round(100.0 * b / a, 1),
            "tx_pct": round(100.0 * tx / a, 1), "rx_pct": round(100.0 * rx / a, 1),
            "other_pct": round(max(0.0, 100.0 * (b - tx - rx) / a), 1), "window_ms": a, "delta": delta}


def parse_scan(text):
    """`iw dev X scan` -> [{bssid, ssid, freq, channel, signal_dbm, associated, stations, utilisation_pct}]."""
    out, cur = [], None
    for line in (text or "").splitlines():
        s = line.strip()
        m = re.match(r"BSS ([0-9a-f:]{17})", s, re.I)
        if m and not line.startswith("\t"):
            cur = {"bssid": m.group(1).lower(), "associated": "associated" in s}
            out.append(cur)
        elif cur is None:
            continue
        elif s.startswith("freq:"):
            cur["freq"] = int(_num(s.split(":", 1)[1].strip().split()[0]) or 0)
            cur["channel"] = freq_to_channel(cur["freq"])
        elif s.startswith("signal:"):
            cur["signal_dbm"] = _num(s.split(":", 1)[1].strip().split()[0])
        elif s.startswith("SSID:"):
            cur["ssid"] = s[5:].strip()
        elif s.startswith("* station count:"):
            cur["stations"] = int(_num(s.split(":", 1)[1].strip()) or 0)
        elif s.startswith("* channel utilisation:"):
            v = s.split(":", 1)[1].strip()
            m2 = re.match(r"(\d+)/(\d+)", v)
            if m2 and int(m2.group(2)):
                cur["utilisation_pct"] = round(100.0 * int(m2.group(1)) / int(m2.group(2)), 1)
        elif s.startswith("* primary channel:"):
            cur["channel"] = int(_num(s.split(":", 1)[1].strip()) or 0) or cur.get("channel")
    return [b for b in out if b.get("freq")]


def neighbourhood(scan, link):
    """Synthèse du voisinage : bornes par canal, co-canal de la nôtre, autres
    bornes du même SSID (candidates au roaming) et charge de notre borne."""
    per_channel = {}
    for b in scan:
        per_channel.setdefault(b.get("channel"), []).append(b)
    ours = next((b for b in scan if link.get("bssid") and b["bssid"] == link["bssid"]), None)
    same_ssid = sorted([b for b in scan if link.get("ssid") and b.get("ssid") == link["ssid"] and b["bssid"] != link.get("bssid")],
                       key=lambda b: -(b.get("signal_dbm") or -100))
    co = [b for b in per_channel.get(link.get("channel"), []) if b["bssid"] != link.get("bssid")] if link.get("channel") else []
    return {"bss_count": len(scan),
            "channels": {str(k): len(v) for k, v in sorted(per_channel.items(), key=lambda kv: (kv[0] is None, kv[0]))},
            "co_channel": [{"bssid": b["bssid"], "ssid": b.get("ssid"), "signal_dbm": b.get("signal_dbm")} for b in co][:10],
            "same_ssid": [{"bssid": b["bssid"], "channel": b.get("channel"), "signal_dbm": b.get("signal_dbm"),
                           "stations": b.get("stations"), "utilisation_pct": b.get("utilisation_pct")} for b in same_ssid][:10],
            "our_bss": {"stations": ours.get("stations"), "utilisation_pct": ours.get("utilisation_pct")} if ours else None}


def parse_ping(text):
    """Sortie de ping -> {sent, received, loss_pct, min_ms, avg_ms, max_ms, jitter_ms}."""
    out = {}
    m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received.*?([\d.]+)% packet loss", text or "")
    if m:
        out.update({"sent": int(m.group(1)), "received": int(m.group(2)), "loss_pct": float(m.group(3))})
    m = re.search(r"(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", text or "")
    if m:
        out.update({"min_ms": float(m.group(1)), "avg_ms": float(m.group(2)), "max_ms": float(m.group(3)), "jitter_ms": float(m.group(4))})
    return out


def parse_iperf(text):
    """iperf3 -J (UDP) -> {mbit, jitter_ms, loss_pct, lost, packets}."""
    try:
        d = json.loads(text or "")
        s = d["end"]["sum"]
        return {"mbit": round(s.get("bits_per_second", 0) / 1e6, 1), "jitter_ms": round(s.get("jitter_ms", 0), 2),
                "loss_pct": round(s.get("lost_percent", 0), 2), "lost": s.get("lost_packets"), "packets": s.get("packets")}
    except (ValueError, KeyError, TypeError):
        return {"error": "sortie iperf3 illisible"}


def evaluate(link, station_rates, usage, neigh, ping, iperf, t=None):
    """Constats (jamais d'action). severity: critical / warning / info."""
    t = dict(THRESHOLDS, **(t or {}))
    al = []

    def add(sev, code, msg):
        al.append({"severity": sev, "code": code, "message": msg})
    if not link.get("connected"):
        add("critical", "not-associated", "interface Wi-Fi non associée : aucune mesure d'expérience possible")
        return al
    s = link.get("signal_dbm")
    if s is not None:
        if s <= t["rssi_crit"]:
            add("critical", "rssi", "signal très faible (%s dBm) sur %s" % (s, link.get("bssid")))
        elif s <= t["rssi_warn"]:
            add("warning", "rssi", "signal faible (%s dBm) : débit et fiabilité dégradés" % s)
    rp = station_rates.get("retry_pct")
    if rp is not None:
        if rp >= t["retry_pct_crit"]:
            add("critical", "retries", "%s %% de retransmissions : canal saturé ou interférences" % rp)
        elif rp >= t["retry_pct_warn"]:
            add("warning", "retries", "%s %% de retransmissions (seuil %s %%)" % (rp, t["retry_pct_warn"]))
    if (station_rates.get("failed_pct") or 0) >= 1.0:
        add("warning", "tx-failed", "%s %% de trames non délivrées" % station_rates["failed_pct"])
    if usage and usage.get("busy_pct") is not None:
        b = usage["busy_pct"]
        if b >= t["busy_pct_crit"]:
            add("critical", "busy", "canal occupé à %s %% (dont %s %% par d'autres) : plus de place pour un flux vidéo" % (b, usage.get("other_pct")))
        elif b >= t["busy_pct_warn"]:
            add("warning", "busy", "canal occupé à %s %% (dont %s %% par d'autres)" % (b, usage.get("other_pct")))
    tx = link.get("tx_mbit")
    if tx is not None and tx < t["tx_mbit_warn"]:
        add("warning", "low-rate", "débit négocié bas (%s Mbit/s) : borne lointaine ou client rétrogradé" % tx)
    if link.get("band") == "2.4 GHz":
        add("info", "band-2g4", "associé en 2,4 GHz : bande encombrée, préférer le 5 GHz pour le cast")
    if ping:
        if (ping.get("loss_pct") or 0) >= t["loss_pct_crit"]:
            add("critical", "loss", "%s %% de pertes vers la passerelle" % ping["loss_pct"])
        elif (ping.get("loss_pct") or 0) >= t["loss_pct_warn"]:
            add("warning", "loss", "%s %% de pertes vers la passerelle" % ping["loss_pct"])
        if (ping.get("jitter_ms") or 0) >= t["jitter_ms_warn"]:
            add("warning", "jitter", "gigue %s ms vers la passerelle : flux vidéo saccadé probable" % ping["jitter_ms"])
        if (ping.get("avg_ms") or 0) >= t["latency_ms_warn"]:
            add("warning", "latency", "latence moyenne %s ms vers la passerelle" % ping["avg_ms"])
    if iperf and not iperf.get("error"):
        if (iperf.get("loss_pct") or 0) >= t["loss_pct_warn"]:
            add("warning", "iperf-loss", "flux UDP type cast : %s %% de pertes" % iperf["loss_pct"])
        if (iperf.get("jitter_ms") or 0) >= t["jitter_ms_warn"]:
            add("warning", "iperf-jitter", "flux UDP type cast : gigue %s ms" % iperf["jitter_ms"])
    ob = (neigh or {}).get("our_bss") or {}
    if (ob.get("utilisation_pct") or 0) >= t["bss_util_pct_warn"]:
        add("warning", "bss-load", "la borne annonce %s %% d'utilisation de son canal (%s stations)" % (ob["utilisation_pct"], ob.get("stations")))
    elif (ob.get("stations") or 0) >= t["bss_stations_warn"]:
        add("info", "bss-stations", "%s stations sur la borne" % ob["stations"])
    co = (neigh or {}).get("co_channel") or []
    if len(co) >= 3:
        add("info", "co-channel", "%d autres bornes sur le même canal" % len(co))
    return al


def summarize(alerts):
    counts = {"critical": 0, "warning": 0, "info": 0}
    for a in alerts:
        counts[a["severity"]] = counts.get(a["severity"], 0) + 1
    return {"state": "critical" if counts["critical"] else ("warning" if counts["warning"] else "ok"), "counts": counts}


# --- collecte -------------------------------------------------------------

def detect_iface():
    code, out, _ = run(["iw", "dev"], 10)
    ifaces = re.findall(r"^\s*Interface (\S+)", out, re.M)
    managed = []
    for name in ifaces:
        blk = out.split("Interface " + name, 1)[1]
        if "type managed" in blk.split("Interface", 1)[0]:
            managed.append(name)
    return (managed or ifaces or [None])[0]


def detect_target(iface):
    """Passerelle du Wi-Fi : route par défaut de l'interface, sinon passerelle
    DHCP vue par NetworkManager, sinon .1 du sous-réseau."""
    code, out, _ = run(["ip", "-4", "route", "show", "dev", iface], 10)
    m = re.search(r"default via (\S+)", out)
    if m:
        return m.group(1)
    code, out, _ = run(["nmcli", "-g", "IP4.GATEWAY", "device", "show", iface], 10)
    if code == 0 and out.strip():
        return out.strip().splitlines()[0]
    code, out, _ = run(["ip", "-4", "-o", "addr", "show", "dev", iface], 10)
    m = re.search(r"inet (\d+\.\d+\.\d+)\.\d+/", out)
    return (m.group(1) + ".1") if m else None


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def collect(iface=None, target=None, iperf_host=None, do_scan=True, state_path=STATE_DEFAULT):
    iface = iface if iface and iface != "auto" else detect_iface()
    result = {"plugin": "wifi-probe", "version": VERSION, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "iface": iface}
    if not iface:
        result["error"] = "aucune interface Wi-Fi (iw dev)"
        result["alerts"] = [{"severity": "critical", "code": "no-iface", "message": result["error"]}]
        result["summary"] = summarize(result["alerts"])
        return result
    prev = load_state(state_path)
    code, out, err = run(["iw", "dev", iface, "link"], 15)
    link = parse_link(out) if code == 0 else {"connected": False, "error": (err or out)[:200]}
    station, usage, neigh, ping, iperf = {}, None, None, None, None
    if link.get("connected"):
        code, out, _ = run(["iw", "dev", iface, "station", "dump"], 15)
        station = parse_station(out) if code == 0 else {}
        code, out, _ = run(["iw", "dev", iface, "survey", "dump"], 15)
        survey = parse_survey(out) if code == 0 else []
        usage = channel_usage(survey, prev.get("survey"))
        if do_scan:
            code, out, err = run(["iw", "dev", iface, "scan"], 60)
            if code == 0:
                neigh = neighbourhood(parse_scan(out), link)
            else:
                neigh = {"error": (err or out)[:200].strip() or "scan refusé"}
        target = target if target and target != "auto" else detect_target(iface)
        if target:
            code, out, _ = run(["ping", "-I", iface, "-n", "-q", "-c", "20", "-i", "0.2", "-W", "1", target], 40)
            ping = parse_ping(out)
            ping["target"] = target
        if iperf_host:
            code, out, _ = run(["ip", "-4", "-o", "addr", "show", "dev", iface], 10)
            m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/", out)
            cmd = ["iperf3", "-c", iperf_host, "-u", "-b", "20M", "-t", "10", "-J"] + (["-B", m.group(1)] if m else [])
            code, out, err = run(cmd, 40)
            iperf = parse_iperf(out) if code == 0 else {"error": (err or out)[:200].strip() or "iperf3 en échec"}
            iperf["server"] = iperf_host
    else:
        survey = []
    sr = rates(station, prev.get("station")) if station else {}
    alerts = evaluate(link, sr, usage, neigh, ping, iperf)
    save_state(state_path, {"at": result["at"], "station": station, "survey": survey})
    result.update({"link": link, "station": station, "rates": sr, "channel": usage, "neighbourhood": neigh,
                   "ping": ping, "iperf": iperf, "alerts": alerts, "summary": summarize(alerts)})
    return result


def main(argv):
    iface, target, iperf_host, do_scan, state = "auto", "auto", None, True, STATE_DEFAULT
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--iface" and i + 1 < len(argv):
            iface = argv[i + 1]; i += 2; continue
        if a == "--target" and i + 1 < len(argv):
            target = argv[i + 1]; i += 2; continue
        if a == "--iperf" and i + 1 < len(argv):
            iperf_host = argv[i + 1]; i += 2; continue
        if a == "--state" and i + 1 < len(argv):
            state = argv[i + 1]; i += 2; continue
        if a == "--no-scan":
            do_scan = False
        i += 1
    try:
        print(json.dumps(collect(iface, target, iperf_host, do_scan, state)))
    except Exception as exc:  # noqa: BLE001 -- une sonde ne doit jamais planter l'agent
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
