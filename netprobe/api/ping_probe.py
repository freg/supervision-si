"""
Sonde smokeping (volet 1 de la demande #295) -- livraison #297.
Appelle le VRAI binaire `ping` système via sous-processus, même motif
déjà établi ailleurs dans ce projet (`ssh-keygen`, `ldapsearch`,
`mysqldump`...) plutôt que de réimplémenter le protocole ICMP
soi-même (nécessiterait des sockets raw, privilèges root, et une
réimplémentation fragile d'un protocole déjà bien géré par un
binaire mature).

**⚠️ NON VÉRIFIÉ contre un vrai `ping`** -- binaire absent de cet
environnement de développement (`/bin/sh: ping: not found`), même
limitation déjà documentée pour `ssh`/`ssh-keygen`/`sshfs` ailleurs
dans ce projet. Logique de PARSING testée contre de VRAIES sorties
`ping` (Linux `iputils-ping`, format le plus répandu) capturées de
mémoire/documentation, mais jamais confirmée contre le binaire réel
lui-même.

**UN SEUL ping par échantillon par défaut** (`count=1`), pas les 20
envois traditionnels de smokeping -- décision de charge, cohérente
avec la préoccupation exprimée par la personne à l'origine du choix
"module séparé" (#295) : "potentiellement tous les IP relevés" peut
représenter beaucoup de cibles, un ping unique reste représentatif
pour une supervision de tendance (pas une étude statistique fine de
gigue), configurable si besoin plus tard.
"""
import re
import subprocess

# Motif Linux (iputils-ping) -- "1 packets transmitted, 1 received,
# 0% packet loss, time 0ms" -- capture le pourcentage de perte,
# format le plus répandu en conteneur Docker (Debian/Ubuntu base).
_LOSS_RE = re.compile(r"(\d+)% packet loss")
# "rtt min/avg/max/mdev = 12.345/12.345/12.345/0.000 ms" -- capture
# la moyenne (2e valeur) en millisecondes.
_RTT_RE = re.compile(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms")
# Repli si rtt indisponible (un seul paquet reçu, section rtt absente
# sur CERTAINES variantes de ping) -- "time=12.3 ms" ligne par ligne.
_TIME_RE = re.compile(r"time=([\d.]+) ?ms")


def ping_once(ip_address, count=1, timeout_seconds=2):
    """Lance `ping -c <count> -W <timeout_seconds> <ip_address>` --
    renvoie {"success", "latency_ms", "packet_loss_percent", "error"}.
    JAMAIS une exception qui remonterait à l'appelant -- une cible
    injoignable est un résultat NORMAL à enregistrer, pas une panne
    de ce module (voir même raisonnement que
    ssh-tunnels/key_scanner.py pour les erreurs best-effort)."""
    try:
        proc = subprocess.run(
            ["ping", "-c", str(count), "-W", str(timeout_seconds), ip_address],
            capture_output=True, text=True, timeout=timeout_seconds * count + 5,
        )
    except FileNotFoundError:
        return {"success": False, "latency_ms": None, "packet_loss_percent": None, "error": "binaire 'ping' introuvable sur ce système"}
    except subprocess.TimeoutExpired:
        return {"success": False, "latency_ms": None, "packet_loss_percent": 100, "error": "délai dépassé"}
    except Exception as exc:  # noqa: BLE001 -- défensif, jamais remonté brut
        return {"success": False, "latency_ms": None, "packet_loss_percent": None, "error": str(exc)}

    output = proc.stdout or ""
    loss_match = _LOSS_RE.search(output)
    packet_loss_percent = int(loss_match.group(1)) if loss_match else (100 if proc.returncode != 0 else None)

    rtt_match = _RTT_RE.search(output)
    if rtt_match:
        latency_ms = float(rtt_match.group(1))
    else:
        time_match = _TIME_RE.search(output)
        latency_ms = float(time_match.group(1)) if time_match else None

    success = proc.returncode == 0 and latency_ms is not None
    return {
        "success": success,
        "latency_ms": latency_ms,
        "packet_loss_percent": packet_loss_percent if packet_loss_percent is not None else (0 if success else 100),
        "error": None if success else ((output.strip().splitlines() or ["échec sans détail"])[-1]),
    }
