#!/usr/bin/env python3
"""
Générateur de données de démonstration pour network-agent -- livraison
#392, backlog item 58. Demandé explicitement : "génère des données
d'exemple en volume suffisant et sur une période de plusieurs mois
afin d'affiner la mise au point de l'interface" (filtres période
temporelle / profondeur de voisinage / volume de trafic / géographie).

Écrit directement en SQL (PAS via les fonctions upsert_* de store.py,
qui codent toutes en dur `now_iso()` -- horodatage RÉEL, jamais
paramétrable) -- nécessaire ici pour contrôler précisément les dates
`first_seen`/`last_seen`/`snapshot_at` et simuler plusieurs mois
d'historique RÉALISTE, pas seulement l'instant présent.

Reproductible -- graine aléatoire FIXE (`RANDOM_SEED`) : deux
exécutions sur une base neuve produisent EXACTEMENT le même jeu de
données, utile pour comparer un changement d'interface sur des
données identiques.

⚠️ Site clairement étiqueté "Démo" (jamais confondu avec un site réel
capturé) -- ce script est idempotent PAR RÉ-EXÉCUTION COMPLÈTE :
relancer supprime D'ABORD toute donnée précédemment générée par CE
script (identifiée par le nom du site), jamais un doublon qui
s'accumulerait à chaque lancement.

Usage :
    python3 network-agent/scripts/seed_demo_data.py [--db-path CHEMIN]
"""
import argparse
import ipaddress
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

RANDOM_SEED = 20260906  # date de cette livraison -- fixe, jamais changée entre deux exécutions
DEMO_SITE_NAME = "Démo — généré automatiquement (#392)"
MONTHS_OF_HISTORY = 6
SNAPSHOT_INTERVAL_DAYS = 7  # hebdomadaire -- ~26 relevés sur 6 mois, dense sans être excessif

# Segments -- chacun représente un niveau de "profondeur de
# voisinage" ET une zone géographique distincte, pour donner aux deux
# filtres (profondeur, géographie) quelque chose de significatif à
# distinguer. Notation profondeur : voir le docstring de
# _ensure_topology_columns (store.py) -- "pN.M", N = routeurs, M =
# commutateurs à ce niveau.
SEGMENTS = [
    {
        "label": "LAN direct — Bâtiment A, RDC",
        "cidr": "10.10.0.0/24",
        "depths": ["p0"] * 6 + ["p0.1"] * 3,  # majoritairement direct, quelques-uns derrière 1 commutateur
        "building": "Bâtiment A", "room_prefix": "RDC-", "zone": "Administration",
        "lat_base": 48.8566, "lon_base": 2.3522, "device_count": 45,
    },
    {
        "label": "LAN direct — Bâtiment A, Étage 1",
        "cidr": "10.10.1.0/24",
        "depths": ["p0.1"] * 5 + ["p0.2"] * 4 + ["p0"] * 2,
        "building": "Bâtiment A", "room_prefix": "E1-", "zone": "Bureaux",
        "lat_base": 48.8567, "lon_base": 2.3523, "device_count": 55,
    },
    {
        "label": "Derrière routeur — Bâtiment B",
        "cidr": "10.20.0.0/24",
        "depths": ["p1"] * 6 + ["p1.1"] * 3,
        "building": "Bâtiment B", "room_prefix": "B-", "zone": "Ateliers",
        "lat_base": 48.8580, "lon_base": 2.3540, "device_count": 40,
    },
    {
        "label": "Site distant — Antenne",
        "cidr": "10.30.0.0/24",
        "depths": ["p1"] * 3 + ["p2"] * 5 + ["p2.1"] * 2,
        "building": "Antenne distante", "room_prefix": "AD-", "zone": "Site secondaire",
        "lat_base": 48.7000, "lon_base": 2.2000, "device_count": 25,
    },
]

SERVICE_CATALOG = [
    ("tcp", 80), ("tcp", 443), ("tcp", 22), ("tcp", 445), ("udp", 53), ("tcp", 3389),
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def random_mac(rng):
    # Bit "localement administré" activé (2e bit de poids faible du
    # premier octet) -- convention standard pour signaler une adresse
    # NON attribuée par un vrai fabricant, jamais confondue avec un
    # VRAI appareil physique si ces données de démo fuitent quelque
    # part par erreur.
    first_octet = rng.choice([0x02, 0x06, 0x0A, 0x0E])
    rest = [rng.randint(0, 255) for _ in range(5)]
    return ":".join(f"{b:02x}" for b in [first_octet] + rest)


def random_hostname(rng, index):
    prefixes = ["pc", "laptop", "srv", "print", "cam", "switch", "ap", "nas"]
    return f"{rng.choice(prefixes)}-{index:03d}"


def generate_devices_for_segment(rng, segment, start_date):
    """Renvoie une liste de dicts {mac, ip, hostname, depth, building,
    room, zone, lat, lon, first_seen}. `first_seen` étalé sur TOUTE la
    période -- certains appareils "existent" depuis le début de
    l'historique simulé, d'autres apparaissent plus récemment (motif
    réaliste, jamais tout le monde présent dès le premier jour)."""
    network = ipaddress.ip_network(segment["cidr"])
    available_hosts = list(network.hosts())[2:]  # évite .1 (passerelle probable) et le tout premier host
    rng.shuffle(available_hosts)

    devices = []
    for i in range(segment["device_count"]):
        depth = rng.choice(segment["depths"])
        has_hostname = rng.random() < 0.65  # ~65% résolus -- jamais 100%, motif réaliste (voir dns_resolver.py)
        # Étalement du first_seen -- biais vers le DÉBUT de la période
        # (la plupart des appareils sont déjà là depuis longtemps),
        # une minorité apparaît plus tard (nouveaux arrivants).
        days_offset = int(rng.betavariate(1.5, 4) * (MONTHS_OF_HISTORY * 30))
        first_seen = start_date + timedelta(days=days_offset)

        has_coords = rng.random() < 0.4  # coordonnées précises pas systématiques -- certains juste "bâtiment/salle"
        devices.append({
            "mac": random_mac(rng),
            "ip": str(available_hosts[i]),
            "hostname": random_hostname(rng, i) if has_hostname else None,
            "depth": depth,
            "building": segment["building"],
            "room": f"{segment['room_prefix']}{rng.randint(1, 20):02d}",
            "zone": segment["zone"],
            "lat": segment["lat_base"] + rng.uniform(-0.001, 0.001) if has_coords else None,
            "lon": segment["lon_base"] + rng.uniform(-0.001, 0.001) if has_coords else None,
            "first_seen": first_seen,
            "is_server_like": rng.random() < 0.12,  # ~12% jouent le rôle de "serveur" (beaucoup de connexions entrantes)
        })
    return devices


def delete_previous_demo_data(conn):
    """Supprime TOUTES les données précédemment générées par CE
    script (identifiées par le nom du site DEMO) -- ré-exécution
    idempotente, jamais une accumulation de doublons à chaque
    lancement. Ne touche JAMAIS un site RÉEL (nom différent)."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM na_sites WHERE name = ?", [DEMO_SITE_NAME])
    row = cur.fetchone()
    if row is None:
        return
    site_id = row[0]
    cur.execute("SELECT id FROM na_network_segments WHERE site_id = ?", [site_id])
    segment_ids = [r[0] for r in cur.fetchall()]
    for seg_id in segment_ids:
        cur.execute("SELECT id FROM na_devices WHERE network_segment_id = ?", [seg_id])
        device_ids = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT id FROM na_history_snapshots WHERE network_segment_id = ?", [seg_id])
        snapshot_ids = [r[0] for r in cur.fetchall()]
        for snap_id in snapshot_ids:
            cur.execute("DELETE FROM na_device_presence_history WHERE snapshot_id = ?", [snap_id])
            cur.execute("DELETE FROM na_link_history WHERE snapshot_id = ?", [snap_id])
        cur.execute("DELETE FROM na_history_snapshots WHERE network_segment_id = ?", [seg_id])
        cur.execute("DELETE FROM na_device_link_services WHERE network_segment_id = ?", [seg_id])
        cur.execute("DELETE FROM na_device_links WHERE network_segment_id = ?", [seg_id])
        for dev_id in device_ids:
            cur.execute("DELETE FROM na_device_services WHERE device_id = ?", [dev_id])
        cur.execute("DELETE FROM na_devices WHERE network_segment_id = ?", [seg_id])
    cur.execute("DELETE FROM na_network_segments WHERE site_id = ?", [site_id])
    cur.execute("DELETE FROM na_sites WHERE id = ?", [site_id])
    conn.commit()


def seed(db_path):
    rng = random.Random(RANDOM_SEED)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        print(f"Suppression des données de démonstration précédentes (site {DEMO_SITE_NAME!r})…")
        delete_previous_demo_data(conn)

        cur = conn.cursor()
        cur.execute("INSERT INTO na_sites (name, created_at) VALUES (?, ?)", [DEMO_SITE_NAME, now_iso()])
        site_id = cur.lastrowid

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=MONTHS_OF_HISTORY * 30)

        all_devices_by_segment = {}  # segment_id -> [device dicts avec "id" ajouté après insertion]

        for segment in SEGMENTS:
            cur.execute(
                "INSERT INTO na_network_segments (site_id, label, cidr, created_at) VALUES (?, ?, ?, ?)",
                [site_id, segment["label"], segment["cidr"], now_iso()],
            )
            segment_id = cur.lastrowid
            print(f"Segment {segment['label']!r} (id={segment_id})…")

            devices = generate_devices_for_segment(rng, segment, start_date)
            for d in devices:
                cur.execute(
                    """INSERT INTO na_devices
                       (network_segment_id, mac_address, ip_address, first_seen, last_seen,
                        packet_count, bytes_total, external_relay_count, hostname,
                        network_depth, building, room, zone, latitude, longitude)
                       VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?)""",
                    [segment_id, d["mac"], d["ip"], to_iso(d["first_seen"]), to_iso(d["first_seen"]),
                     d["hostname"], d["depth"], d["building"], d["room"], d["zone"], d["lat"], d["lon"]],
                )
                d["id"] = cur.lastrowid

                # Services -- appareils "serveur" en ont plusieurs,
                # les autres 0 ou 1 (motif réaliste : la plupart des
                # postes clients n'exposent presque rien).
                n_services = rng.randint(2, 4) if d["is_server_like"] else rng.choice([0, 0, 1])
                d["services"] = rng.sample(SERVICE_CATALOG, k=min(n_services, len(SERVICE_CATALOG)))

            all_devices_by_segment[segment_id] = devices

        conn.commit()

        # --- Simulation de l'historique (relevés hebdomadaires) ---
        total_snapshots = (MONTHS_OF_HISTORY * 30) // SNAPSHOT_INTERVAL_DAYS
        print(f"Simulation de {total_snapshots} relevés hebdomadaires sur {MONTHS_OF_HISTORY} mois…")

        # État cumulatif courant par appareil/lien -- reproduit la
        # sémantique UPSERT réelle (compteurs qui ne font QUE croître).
        device_state = {}  # device_id -> {"packets": int, "bytes": int}
        link_state = {}    # (a_id, b_id, protocol, port) -> {"packets": int, "bytes": int}

        for week in range(total_snapshots):
            snapshot_date = start_date + timedelta(days=(week + 1) * SNAPSHOT_INTERVAL_DAYS)
            if snapshot_date > end_date:
                break

            for segment_id, devices in all_devices_by_segment.items():
                cur.execute(
                    "INSERT INTO na_history_snapshots (network_segment_id, snapshot_at) VALUES (?, ?)",
                    [segment_id, to_iso(snapshot_date)],
                )
                snapshot_id = cur.lastrowid

                active_devices = [d for d in devices if d["first_seen"] <= snapshot_date]

                for d in active_devices:
                    state = device_state.setdefault(d["id"], {"packets": 0, "bytes": 0})
                    # Volume hebdomadaire -- serveurs nettement plus
                    # actifs, plus une variation aléatoire pour éviter
                    # une progression parfaitement linéaire (jamais
                    # réaliste).
                    base = rng.randint(50_000, 400_000) if d["is_server_like"] else rng.randint(500, 15_000)
                    weekly_bytes = int(base * rng.uniform(0.7, 1.4))
                    weekly_packets = max(1, weekly_bytes // rng.randint(200, 800))
                    state["bytes"] += weekly_bytes
                    state["packets"] += weekly_packets

                    cur.execute(
                        "UPDATE na_devices SET packet_count = ?, bytes_total = ?, last_seen = ? WHERE id = ?",
                        [state["packets"], state["bytes"], to_iso(snapshot_date), d["id"]],
                    )
                    cur.execute(
                        """INSERT INTO na_device_presence_history
                           (snapshot_id, device_id, ip_address, packet_count, bytes_total, last_seen)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        [snapshot_id, d["id"], d["ip"], state["packets"], state["bytes"], to_iso(snapshot_date)],
                    )

                # Liens -- appareils "clients" parlent PRINCIPALEMENT
                # aux appareils "serveur" du MÊME segment (motif
                # réaliste), quelques échanges pair-à-pair en plus.
                servers = [d for d in active_devices if d["is_server_like"]]
                clients = [d for d in active_devices if not d["is_server_like"]]
                if not servers or not clients:
                    continue
                for client in clients:
                    if rng.random() > 0.6:  # tous les clients ne parlent pas forcément CETTE semaine
                        continue
                    server = rng.choice(servers)
                    protocol, port = rng.choice(server["services"]) if server["services"] else ("tcp", 443)
                    key = (client["id"], server["id"], protocol, port)
                    lstate = link_state.setdefault(key, {"packets": 0, "bytes": 0})
                    weekly_bytes = int(rng.randint(2_000, 80_000) * rng.uniform(0.7, 1.3))
                    weekly_packets = max(1, weekly_bytes // rng.randint(200, 600))
                    lstate["bytes"] += weekly_bytes
                    lstate["packets"] += weekly_packets

                    cur.execute(
                        """SELECT id FROM na_device_links WHERE network_segment_id = ? AND device_a_id = ? AND device_b_id = ?""",
                        [segment_id, client["id"], server["id"]],
                    )
                    existing = cur.fetchone()
                    if existing is None:
                        cur.execute(
                            """INSERT INTO na_device_links
                               (network_segment_id, device_a_id, device_b_id, packet_count, bytes_total, first_seen, last_seen)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            [segment_id, client["id"], server["id"], lstate["packets"], lstate["bytes"],
                             to_iso(snapshot_date), to_iso(snapshot_date)],
                        )
                    else:
                        cur.execute(
                            "UPDATE na_device_links SET packet_count = ?, bytes_total = ?, last_seen = ? WHERE id = ?",
                            [lstate["packets"], lstate["bytes"], to_iso(snapshot_date), existing["id"]],
                        )
                    cur.execute(
                        """SELECT id FROM na_device_link_services
                           WHERE network_segment_id = ? AND device_a_id = ? AND device_b_id = ? AND protocol = ? AND port = ?""",
                        [segment_id, client["id"], server["id"], protocol, port],
                    )
                    existing_svc = cur.fetchone()
                    if existing_svc is None:
                        cur.execute(
                            """INSERT INTO na_device_link_services
                               (network_segment_id, device_a_id, device_b_id, protocol, port, packet_count, bytes_total, first_seen, last_seen)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            [segment_id, client["id"], server["id"], protocol, port, lstate["packets"], lstate["bytes"],
                             to_iso(snapshot_date), to_iso(snapshot_date)],
                        )
                    else:
                        cur.execute(
                            "UPDATE na_device_link_services SET packet_count = ?, bytes_total = ?, last_seen = ? WHERE id = ?",
                            [lstate["packets"], lstate["bytes"], to_iso(snapshot_date), existing_svc["id"]],
                        )
                    cur.execute(
                        """INSERT INTO na_link_history
                           (snapshot_id, device_a_id, device_b_id, protocol, port, packet_count, bytes_total)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        [snapshot_id, client["id"], server["id"], protocol, port, lstate["packets"], lstate["bytes"]],
                    )
            conn.commit()

        # Services déclarés (na_device_services) -- une fois, à la fin
        # (pas besoin de les faire évoluer semaine par semaine, juste
        # signaler qu'ils existent, comme la vraie capture le ferait
        # dès la première observation).
        for devices in all_devices_by_segment.values():
            for d in devices:
                for protocol, port in d["services"]:
                    cur.execute(
                        """INSERT INTO na_device_services (device_id, protocol, port, first_seen, last_seen, packet_count)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        [d["id"], protocol, port, to_iso(d["first_seen"]), now_iso(), rng.randint(10, 500)],
                    )
        conn.commit()

        total_devices = sum(len(v) for v in all_devices_by_segment.values())
        print(f"\n✅ Terminé -- {len(SEGMENTS)} segment(s), {total_devices} appareil(s), "
              f"{total_snapshots} relevé(s) hebdomadaire(s) sur {MONTHS_OF_HISTORY} mois.")
        print(f"Site : {DEMO_SITE_NAME!r} (id={site_id})")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=None, help="chemin de la base network-agent (défaut : NETWORK_AGENT_DB_PATH ou /data/network-agent.db)")
    args = parser.parse_args()

    import os
    db_path = args.db_path or os.environ.get("NETWORK_AGENT_DB_PATH", "/data/network-agent.db")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
    import store as na_store
    na_store.ensure_schema(db_path)  # garantit les colonnes network_depth/building/... avant d'écrire

    seed(db_path)


if __name__ == "__main__":
    main()
