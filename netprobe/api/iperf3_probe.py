"""
Sonde débit réel (volet "couche expérience client", backlog item 47
reformulé le 2026-09-05 -- "voyons ce qu'on peut déjà faire sans RF
simplement avec un client wifi et la couche IP et le snmp"). Livraison
#385.

Appelle le VRAI binaire `iperf3` système via sous-processus, même
motif déjà établi ailleurs dans ce projet (`ping`, `tcpdump`,
`nmap`...) plutôt que de réimplémenter le protocole de mesure de
débit soi-même. Format JSON de sortie (`-J`) utilisé plutôt que le
texte humain -- schéma STABLE et documenté, contrairement au format
texte qui varie selon la largeur du terminal -- confirmé par
recherche (plusieurs sources indépendantes) avant d'écrire ce module,
jamais deviné.

**⚠️ NON VÉRIFIÉ contre un vrai `iperf3`** -- binaire absent de cet
environnement de développement, même limitation déjà documentée pour
`ping` (`ping_probe.py`) et `ssh`/`sshfs` ailleurs dans ce projet.
Logique de PARSING testée contre des sorties JSON RECONSTRUITES
d'après le schéma confirmé par recherche, jamais capturées d'un
VRAI serveur de référence.

**⚠️ Limite architecturale IMPORTANTE, découverte en construisant ce
module -- PAS résolue ici** : ce conteneur (`netprobe-api`) n'a PAS
`network_mode: host` -- le débit mesuré par `iperf3` depuis
L'INTÉRIEUR de ce conteneur reflète donc le chemin RÉEL (traverse la
VRAIE interface réseau de l'hôte, Docker ne fait qu'ajouter un saut
NAT/bridge supplémentaire), MAIS ce module ne peut PAS voir le BSSID/
l'itinérance WiFi de l'hôte (propriété du pilote WiFi de l'hôte,
invisible depuis un namespace réseau Docker isolé) -- cette partie du
volet "expérience client" (suivi de roaming) reste HORS de portée
tant que l'architecture d'agents multi-hôtes (items 45/48 du backlog,
volontairement non tranchée) n'est pas décidée avec la personne.

**Seul TCP couvert ici** -- UDP (`-u`) a un schéma JSON DIFFÉRENT
(un seul bloc "sum", pas "sum_sent"/"sum_received", confirmé par
recherche) -- pas ajouté, hors du besoin exprimé ("débit réel").
"""
import json
import subprocess


def iperf3_throughput(server_host, port=5201, duration_seconds=5, timeout_seconds=15):
    """Lance `iperf3 -c <server_host> -p <port> -t <duration_seconds> -J`
    -- renvoie {"success", "sent_mbps", "received_mbps", "retransmits",
    "error"}. JAMAIS une exception qui remonterait à l'appelant -- un
    serveur de référence injoignable est un résultat NORMAL à
    enregistrer (comme ping_probe.py), pas une panne de ce module.
    `timeout_seconds` du sous-processus volontairement PLUS LARGE que
    `duration_seconds` (marge pour la connexion + le rapport final,
    jamais coupé en plein test)."""
    try:
        proc = subprocess.run(
            ["iperf3", "-c", server_host, "-p", str(port), "-t", str(duration_seconds), "-J"],
            capture_output=True, text=True, timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return {"success": False, "sent_mbps": None, "received_mbps": None, "retransmits": None,
                "error": "binaire 'iperf3' introuvable sur ce système"}
    except subprocess.TimeoutExpired:
        return {"success": False, "sent_mbps": None, "received_mbps": None, "retransmits": None,
                "error": "délai dépassé"}
    except Exception as exc:  # noqa: BLE001 -- défensif, jamais remonté brut
        return {"success": False, "sent_mbps": None, "received_mbps": None, "retransmits": None, "error": str(exc)}

    # iperf3 renvoie un JSON valide MÊME en cas d'échec de connexion
    # (bloc "error" au niveau racine, pas de bloc "end") -- vérifié
    # par recherche, pas une supposition.
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"success": False, "sent_mbps": None, "received_mbps": None, "retransmits": None,
                "error": (proc.stderr.strip() or "sortie JSON invalide")[:300]}

    if "error" in data:
        return {"success": False, "sent_mbps": None, "received_mbps": None, "retransmits": None, "error": str(data["error"])[:300]}

    end = data.get("end") or {}
    sum_sent = end.get("sum_sent") or {}
    sum_received = end.get("sum_received") or {}
    sent_bps = sum_sent.get("bits_per_second")
    received_bps = sum_received.get("bits_per_second")

    if sent_bps is None or received_bps is None:
        return {"success": False, "sent_mbps": None, "received_mbps": None, "retransmits": None,
                "error": "réponse iperf3 incomplète (sum_sent/sum_received absents)"}

    return {
        "success": True,
        "sent_mbps": round(sent_bps / 1_000_000, 2),
        "received_mbps": round(received_bps / 1_000_000, 2),
        "retransmits": sum_sent.get("retransmits"),
        "error": None,
    }
