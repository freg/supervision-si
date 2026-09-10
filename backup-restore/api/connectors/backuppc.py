"""
Connecteur BackupPC (livraison #270, backlog item 27 -- "backup-restore").

BackupPC est un système de sauvegarde réseau haute performance avec
déduplication, support de SMB/NFS/rsync/ftp, et une interface web
d'administration. Ce connecteur permet de :

- Lister les hôtes BackupPC configurés
- Consulter le contenu du hub (pool de fichiers dédupliqués)
- Lister les versions disponibles par hôte
- Visualiser l'historique des sauvegardes

Le connecteur communique avec l'API web de BackupPC (BackupPC_xmpp)
ou directement avec les fichiers de configuration/Pool sur le serveur.

Architecture : le connecteur est conçu pour fonctionner de deux modes :
1. Mode "proxy HTTP" : BackupPC expose une interface CGI/HTTP
2. Mode "direct" : lecture directe des fichiers de configuration
   (si le conteneur a accès au serveur BackupPC)

Pour cette livraison, on implémente le mode "proxy HTTP" via
BACKUPPC_API_URL, avec un mode "simulation" pour les tests.
"""

import logging
import os
import json
import time
from datetime import datetime

_log = logging.getLogger("backuppc_connector")

BACKUPPC_API_URL = os.environ.get("BACKUPPC_API_URL", "").rstrip("/") or None
BACKUPPC_CONFIG_PATH = os.environ.get("BACKUPPC_CONFIG_PATH", "/etc/backuppc")
BACKUPPC_POOL_PATH = os.environ.get("BACKUPPC_POOL_PATH", "/var/lib/backuppc/pc")


class BackupPCConnector:
    """Connecteur vers un serveur BackupPC."""

    def __init__(self, api_url=None, config_path=None, pool_path=None):
        self.api_url = api_url or BACKUPPC_API_URL
        self.config_path = config_path or BACKUPPC_CONFIG_PATH
        self.pool_path = pool_path or BACKUPPC_POOL_PATH
        self._simulation_mode = self.api_url is None

    def is_available(self):
        """Vérifie si le connecteur est configuré et joignable."""
        if self._simulation_mode:
            return False
        try:
            import requests
            resp = requests.get(f"{self.api_url}/status", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def get_hosts(self):
        """Liste les hôtes configurés dans BackupPC.

        Retourne une liste de dicts : [{host, last_backup, last_attempt,
        type, status, ...}] -- best-effort, jamais d'exception bloquante.
        """
        if self._simulation_mode:
            return self._simulate_hosts()

        try:
            import requests
            resp = requests.get(f"{self.api_url}/hosts", timeout=10)
            if resp.status_code != 200:
                _log.warning("BackupPC /hosts a répondu %s", resp.status_code)
                return []
            return resp.json().get("hosts", [])
        except Exception as exc:
            _log.error("Erreur lors de la récupération des hôtes BackupPC: %s", exc)
            return []

    def get_host_versions(self, host):
        """Liste les versions disponibles pour un hôte donné.

        Retourne une liste de dicts : [{num, type, start_time, end_time,
        size, ...}] -- les versions sont triées de la plus récente à la
        plus ancienne.
        """
        if self._simulation_mode:
            return self._simulate_versions(host)

        try:
            import requests
            resp = requests.get(f"{self.api_url}/hosts/{host}/versions", timeout=10)
            if resp.status_code != 200:
                _log.warning("BackupPC /hosts/%s/versions a répondu %s", host, resp.status_code)
                return []
            return resp.json().get("versions", [])
        except Exception as exc:
            _log.error("Erreur lors des versions de %s: %s", host, exc)
            return []

    def get_host_content(self, host, version=None):
        """Liste le contenu (fichiers/répertoires) d'une sauvegarde.

        Si version est None, utilise la dernière version disponible.
        Retourne une arborescence de fichiers.
        """
        if self._simulation_mode:
            return self._simulate_content(host, version)

        try:
            import requests
            params = {}
            if version is not None:
                params["version"] = version
            resp = requests.get(f"{self.api_url}/hosts/{host}/content",
                                params=params, timeout=15)
            if resp.status_code != 200:
                return {"error": f"BackupPC a répondu {resp.status_code}"}
            return resp.json()
        except Exception as exc:
            _log.error("Erreur lors du contenu de %s: %s", host, exc)
            return {"error": str(exc)}

    def get_pool_stats(self):
        """Statistiques du pool de fichiers dédupliqués.

        Retourne des informations sur l'espace utilisé, le nombre de
        fichiers uniques, le taux de déduplication, etc.
        """
        if self._simulation_mode:
            return self._simulate_pool_stats()

        try:
            import requests
            resp = requests.get(f"{self.api_url}/pool/stats", timeout=10)
            if resp.status_code != 200:
                return {}
            return resp.json()
        except Exception as exc:
            _log.error("Erreur lors des stats du pool: %s", exc)
            return {}

    def trigger_backup(self, host):
        """Déclenche une sauvegarde manuelle pour un hôte.

        Retourne {"status": "ok"} ou {"error": "..."}.
        """
        if self._simulation_mode:
            return {"status": "ok", "message": "Simulation: sauvegarde déclenchée"}

        try:
            import requests
            resp = requests.post(f"{self.api_url}/hosts/{host}/backup",
                                 timeout=10)
            if resp.status_code == 200:
                return {"status": "ok"}
            return {"error": f"BackupPC a répondu {resp.status_code}"}
        except Exception as exc:
            return {"error": str(exc)}

    # --- Mode simulation pour les tests et la démonstration ---

    def _simulate_hosts(self):
        """Données simulées pour les tests."""
        now = time.time()
        return [
            {
                "host": "srv-win-01",
                "full_name": "Serveur Windows Principal",
                "last_backup": datetime.fromtimestamp(now - 3600).isoformat(),
                "last_attempt": datetime.fromtimestamp(now - 3600).isoformat(),
                "type": "full",
                "status": "success",
                "size_bytes": 45 * 1024 * 1024 * 1024,
                "versions_count": 7,
            },
            {
                "host": "srv-win-02",
                "full_name": "Serveur Windows Secondaire",
                "last_backup": datetime.fromtimestamp(now - 7200).isoformat(),
                "last_attempt": datetime.fromtimestamp(now - 7200).isoformat(),
                "type": "incr",
                "status": "success",
                "size_bytes": 23 * 1024 * 1024 * 1024,
                "versions_count": 14,
            },
            {
                "host": "pc-bureau-01",
                "full_name": "Poste Bureau Marketing",
                "last_backup": datetime.fromtimestamp(now - 86400 * 3).isoformat(),
                "last_attempt": datetime.fromtimestamp(now - 86400 * 3).isoformat(),
                "type": "full",
                "status": "failed",
                "size_bytes": 12 * 1024 * 1024 * 1024,
                "versions_count": 3,
            },
        ]

    def _simulate_versions(self, host):
        """Versions simulées pour un hôte."""
        now = time.time()
        versions = []
        for i in range(7):
            ts = now - (i * 86400)
            versions.append({
                "num": 6 - i,
                "type": "full" if i == 0 else "incr",
                "start_time": datetime.fromtimestamp(ts - 1800).isoformat(),
                "end_time": datetime.fromtimestamp(ts).isoformat(),
                "size_bytes": (40 - i * 2) * 1024 * 1024 * 1024,
                "duration_seconds": 1800,
                "status": "success",
            })
        return versions

    def _simulate_content(self, host, version=None):
        """Contenu simulé d'une sauvegarde."""
        return {
            "host": host,
            "version": version or 6,
            "tree": [
                {"name": "C:", "type": "dir", "children": [
                    {"name": "Windows", "type": "dir", "size_bytes": 15 * 1024 * 1024 * 1024},
                    {"name": "Users", "type": "dir", "size_bytes": 8 * 1024 * 1024 * 1024},
                    {"name": "Program Files", "type": "dir", "size_bytes": 12 * 1024 * 1024 * 1024},
                    {"name": "ProgramData", "type": "dir", "size_bytes": 2 * 1024 * 1024 * 1024},
                ]},
                {"name": "D:", "type": "dir", "children": [
                    {"name": "Data", "type": "dir", "size_bytes": 50 * 1024 * 1024 * 1024},
                    {"name": "Backups", "type": "dir", "size_bytes": 10 * 1024 * 1024 * 1024},
                ]},
            ],
        }

    def _simulate_pool_stats(self):
        """Statistiques simulées du pool."""
        return {
            "total_files": 1250000,
            "unique_files": 450000,
            "dedup_ratio": 2.78,
            "pool_size_bytes": 120 * 1024 * 1024 * 1024,
            "saved_bytes": 210 * 1024 * 1024 * 1024,
            "last_vacuum": "2026-09-05T03:00:00Z",
        }


# Instance globale du connecteur
_connector = None


def get_connector():
    """Renvoie l'instance globale du connecteur BackupPC."""
    global _connector
    if _connector is None:
        _connector = BackupPCConnector()
    return _connector
