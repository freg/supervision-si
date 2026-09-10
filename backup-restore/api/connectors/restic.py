"""
Connecteur Restic (livraison #270, backlog item 27 -- "backup-restore").

Restic est une solution de sauvegarde open source moderne avec :
- Déduplication par blocs (déduplication cross-snapshot)
- Chiffrement AES-256 côté client
- Compression et vérification d'intégrité
- Multi-backend : local, SFTP, S3, Azure, B2, rclone, etc.
- Restauration incrémentielle

Ce connecteur permet de :
- Lister les snapshots d'un dépôt Restic
- Consulter le contenu d'un snapshot
- Gérer la rétention des snapshots
- Vérifier l'intégrité du dépôt
- Restaurer des fichiers spécifiques

Restic est choisi comme troisième solution car il couvre des cas d'usage
différents de BackupPC (sauvegarde réseau classique) et Clonezilla
(imagerie disque) : sauvegarde cloud-ready, postes nomades, serveurs.
"""

import logging
import os
import time
import json
import subprocess
from datetime import datetime

_log = logging.getLogger("restic_connector")

RESTIC_REPOSITORY = os.environ.get("RESTIC_REPOSITORY", "")
RESTIC_PASSWORD = os.environ.get("RESTIC_PASSWORD", "")
RESTIC_BINARY = os.environ.get("RESTIC_BINARY", "restic")


class ResticConnector:
    """Connecteur vers un dépôt Restic."""

    def __init__(self, repository=None, password=None, binary=None):
        self.repository = repository or RESTIC_REPOSITORY
        self.password = password or RESTIC_PASSWORD
        self.binary = binary or RESTIC_BINARY
        self._simulation_mode = not self.repository

    def is_available(self):
        """Vérifie si Restic est configuré et le dépôt accessible."""
        if self._simulation_mode:
            return False
        try:
            result = self._run(["snapshots", "--json", "--last"], timeout=10)
            return result.returncode == 0
        except Exception:
            return False

    def _run(self, args, timeout=30):
        """Exécute une commande Restic."""
        env = os.environ.copy()
        env["RESTIC_REPOSITORY"] = self.repository
        if self.password:
            env["RESTIC_PASSWORD"] = self.password

        cmd = [self.binary] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, env=env
            )
            return result
        except subprocess.TimeoutExpired:
            _log.error("Timeout lors de l'exécution de restic %s", args)
            return None
        except Exception as exc:
            _log.error("Erreur d'exécution restic: %s", exc)
            return None

    def get_snapshots(self):
        """Liste tous les snapshots du dépôt.

        Retourne [{id, short_id, time, paths, hostname, tags, ...}].
        """
        if self._simulation_mode:
            return self._simulate_snapshots()

        result = self._run(["snapshots", "--json"], timeout=30)
        if result and result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                _log.error("Impossible de parser les snapshots")
                return []
        return []

    def get_snapshot_content(self, snapshot_id, path="/"):
        """Liste le contenu d'un snapshot.

        Retourne l'arborescence de fichiers à partir du chemin donné.
        """
        if self._simulation_mode:
            return self._simulate_snapshot_content(snapshot_id, path)

        result = self._run(["ls", snapshot_id, path, "--json"], timeout=30)
        if result and result.returncode == 0:
            try:
                # Restic ls --json retourne un flux JSON ligne par ligne
                lines = result.stdout.strip().split("\n")
                return [json.loads(line) for line in lines if line.strip()]
            except json.JSONDecodeError:
                return {"error": "Impossible de parser le contenu"}
        return {"error": f"Erreur Restic (code {result.returncode if result else 'N/A'})"}

    def restore(self, snapshot_id, target_path, includes=None, excludes=None):
        """Déclenche une restauration.

        snapshot_id: ID du snapshot à restaurer
        target_path: chemin de destination
        includes: optionnel, liste de chemins à inclure
        excludes: optionnel, liste de chemins à exclure

        Retourne {"status": "ok", "command": "..."} ou {"error": "..."}.
        """
        if self._simulation_mode:
            return {"status": "ok", "command": f"restic restore {snapshot_id} --target {target_path}"}

        args = ["restore", snapshot_id, "--target", target_path]
        if includes:
            for inc in includes:
                args.extend(["--include", inc])
        if excludes:
            for exc in excludes:
                args.extend(["--exclude", exc])

        result = self._run(args, timeout=300)
        if result and result.returncode == 0:
            return {"status": "ok", "command": " ".join(args)}
        return {"error": f"Échec de la restauration: {result.stderr if result else 'N/A'}"}

    def check(self):
        """Vérifie l'intégrité du dépôt.

        Retourne {"ok": True/False, "errors": [...]}.
        """
        if self._simulation_mode:
            return {"ok": True, "errors": []}

        result = self._run(["check"], timeout=300)
        if result and result.returncode == 0:
            return {"ok": True, "errors": []}
        return {"ok": False, "errors": [result.stderr if result else "Erreur inconnue"]}

    def forget(self, retention_policy):
        """Applique la politique de rétention.

        retention_policy: dict avec les clés:
            - keep_last: nombre de snapshots récents à conserver
            - keep_daily: nombre de jours à conserver
            - keep_weekly: nombre de semaines à conserver
            - keep_monthly: nombre de mois à conserver
            - keep_yearly: nombre d'années à conserver

        Retourne {"status": "ok"} ou {"error": "..."}.
        """
        if self._simulation_mode:
            return {"status": "ok", "forgotten": 0, "retained": 12}

        args = ["forget"]
        if retention_policy.get("keep_last"):
            args.extend(["--keep-last", str(retention_policy["keep_last"])])
        if retention_policy.get("keep_daily"):
            args.extend(["--keep-daily", str(retention_policy["keep_daily"])])
        if retention_policy.get("keep_weekly"):
            args.extend(["--keep-weekly", str(retention_policy["keep_weekly"])])
        if retention_policy.get("keep_monthly"):
            args.extend(["--keep-monthly", str(retention_policy["keep_monthly"])])
        if retention_policy.get("keep_yearly"):
            args.extend(["--keep-yearly", str(retention_policy["keep_yearly"])])
        args.append("--prune")

        result = self._run(args, timeout=120)
        if result and result.returncode == 0:
            return {"status": "ok"}
        return {"error": f"Échec de la rétention: {result.stderr if result else 'N/A'}"}

    def get_stats(self):
        """Statistiques du dépôt (taille, déduplication, nombre de blocs)."""
        if self._simulation_mode:
            return self._simulate_stats()

        result = self._run(["stats", "--json"], timeout=60)
        if result and result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {}
        return {}

    def backup(self, paths, tags=None):
        """Déclenche une sauvegarde.

        paths: liste de chemins à sauvegarder
        tags: optionnel, liste de tags à appliquer

        Retourne {"status": "ok", "snapshot_id": "..."} ou {"error": "..."}.
        """
        if self._simulation_mode:
            return {"status": "ok", "snapshot_id": f"sim_{int(time.time())}", "paths": paths}

        args = ["backup"] + paths
        if tags:
            for tag in tags:
                args.extend(["--tag", tag])

        result = self._run(args, timeout=600)
        if result and result.returncode == 0:
            # Extraire l'ID du snapshot de la sortie
            snapshot_id = None
            for line in result.stdout.split("\n"):
                if "snapshot" in line and "saved" in line:
                    # Format: "snapshot abc123 saved"
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p == "snapshot" and i + 1 < len(parts):
                            snapshot_id = parts[i + 1]
                            break
            return {"status": "ok", "snapshot_id": snapshot_id or "unknown"}
        return {"error": f"Échec de la sauvegarde: {result.stderr if result else 'N/A'}"}

    # --- Mode simulation ---

    def _simulate_snapshots(self):
        """Snapshots simulés."""
        now = time.time()
        snapshots = []
        for i in range(12):
            ts = now - (i * 86400)
            snapshots.append({
                "id": f"sim_snap_{i:04d}",
                "short_id": f"sim{i:04d}",
                "time": datetime.fromtimestamp(ts).isoformat() + "Z",
                "paths": ["/home", "/etc", "/var/www"],
                "hostname": "srv-prod-01",
                "tags": ["daily", "auto"],
                "parent": f"sim_snap_{i+1:04d}" if i < 11 else None,
            })
        return snapshots

    def _simulate_snapshot_content(self, snapshot_id, path):
        """Contenu simulé d'un snapshot."""
        return [
            {"name": "home", "type": "dir", "path": "/home", "size_bytes": 1024 * 1024 * 1024},
            {"name": "etc", "type": "dir", "path": "/etc", "size_bytes": 256 * 1024 * 1024},
            {"name": "var", "type": "dir", "path": "/var", "size_bytes": 2 * 1024 * 1024 * 1024},
            {"name": "opt", "type": "dir", "path": "/opt", "size_bytes": 512 * 1024 * 1024},
        ]

    def _simulate_stats(self):
        """Statistiques simulées."""
        return {
            "total_size": 15 * 1024 * 1024 * 1024,
            "total_file_count": 250000,
            "total_blob_count": 125000,
            "dedup_size": 5 * 1024 * 1024 * 1024,
            "dedup_ratio": 3.0,
            "snapshots_count": 12,
        }


# Instance globale
_connector = None


def get_connector():
    """Renvoie l'instance globale du connecteur Restic."""
    global _connector
    if _connector is None:
        _connector = ResticConnector()
    return _connector
