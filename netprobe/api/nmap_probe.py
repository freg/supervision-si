"""
Sonde nmap à la demande (volet 2 de la demande #295) -- livraison
#302. Même motif que ping_probe.py : appelle le VRAI binaire `nmap`
système via sous-processus, jamais une réimplémentation du scan de
ports soi-même.

**⚠️ NON VÉRIFIÉ contre un vrai `nmap`** -- binaire absent de cet
environnement de développement (`/bin/sh: nmap: not found`), même
limitation déjà documentée pour `ping`/`ssh-keygen`/`sshfs`. Logique
de PARSING testée contre de VRAIES structures XML nmap (format
officiel documenté, `-oX -`), mais jamais confirmée contre le
binaire réel lui-même.

**Sortie XML** (`-oX -`, vers stdout) plutôt que le format humain ou
"grepable" -- structure DOCUMENTÉE et STABLE (schéma XML officiel
nmap), bien plus robuste à parser qu'un format texte dont la mise en
forme peut varier selon la version. `xml.etree.ElementTree`,
bibliothèque STANDARD Python -- aucune dépendance supplémentaire.

**Portée VOLONTAIREMENT à la demande** -- jamais programmé
automatiquement (contrairement à smokeping) : un scan de ports est
BEAUCOUP plus intrusif qu'un ping (peut déclencher des alertes IDS/
IPS côté cible, consomme largement plus de ressources) -- reste un
geste EXPLICITE de la personne, jamais une action de fond silencieuse.
"""
import subprocess
import xml.etree.ElementTree as ET

# Top 1000 ports TCP (comportement par défaut de nmap sans -p) --
# volontairement PAS -p- (tous les 65535 ports, bien plus long et
# intrusif) -- reste le compromis par défaut de nmap lui-même, jamais
# élargi ici sans que la personne le demande explicitement (voir
# `ports` paramètre de `scan_target`, transmis tel quel à -p si fourni).
DEFAULT_TIMEOUT_SECONDS = 120


def scan_target(ip_address, ports=None, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    """Lance `nmap -oX - [-p <ports>] <ip_address>` -- renvoie
    {"success", "open_ports": [{"port", "protocol", "service", "state"}],
    "scan_duration_seconds", "error"}. JAMAIS une exception qui
    remonterait à l'appelant -- une cible injoignable ou un nmap
    absent sont des résultats à ENREGISTRER, pas des pannes de ce
    module (même raisonnement que ping_probe.py)."""
    cmd = ["nmap", "-oX", "-"]
    if ports:
        cmd += ["-p", str(ports)]
    cmd.append(ip_address)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    except FileNotFoundError:
        return {"success": False, "open_ports": [], "scan_duration_seconds": None, "error": "binaire 'nmap' introuvable sur ce système"}
    except subprocess.TimeoutExpired:
        return {"success": False, "open_ports": [], "scan_duration_seconds": timeout_seconds, "error": f"délai dépassé ({timeout_seconds}s)"}
    except Exception as exc:  # noqa: BLE001 -- défensif, jamais remonté brut
        return {"success": False, "open_ports": [], "scan_duration_seconds": None, "error": str(exc)}

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return {"success": False, "open_ports": [], "scan_duration_seconds": None, "error": (detail[-1] if detail else f"nmap a échoué (code {proc.returncode})")}

    return _parse_nmap_xml(proc.stdout)


def _parse_nmap_xml(xml_text):
    """Parse la sortie XML de nmap -- structure documentée :
    <nmaprun><host><ports><port portid=".." protocol=".."><state state=".."/><service name=".."/></port></ports></host><runstats><finished elapsed=".."/></runstats></nmaprun>
    Défensif à chaque étape -- un XML malformé ou incomplet donne un
    résultat vide plutôt qu'une exception, jamais présumé bien formé."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return {"success": False, "open_ports": [], "scan_duration_seconds": None, "error": f"XML nmap illisible : {exc}"}

    open_ports = []
    host = root.find("host")
    if host is not None:
        ports_elem = host.find("ports")
        if ports_elem is not None:
            for port_elem in ports_elem.findall("port"):
                state_elem = port_elem.find("state")
                state = state_elem.get("state") if state_elem is not None else None
                if state != "open":
                    continue  # jamais les ports fermés/filtrés dans le résultat -- seuls les OUVERTS intéressent une supervision
                service_elem = port_elem.find("service")
                open_ports.append({
                    "port": int(port_elem.get("portid", 0)),
                    "protocol": port_elem.get("protocol", "tcp"),
                    "service": service_elem.get("name") if service_elem is not None else None,
                    "state": state,
                })

    duration = None
    runstats = root.find("runstats")
    if runstats is not None:
        finished = runstats.find("finished")
        if finished is not None and finished.get("elapsed"):
            try:
                duration = float(finished.get("elapsed"))
            except ValueError:
                pass

    return {"success": True, "open_ports": open_ports, "scan_duration_seconds": duration, "error": None}
