#!/usr/bin/env python3
"""Tests des connecteurs backup-restore (livraison #270, backlog item 27).

Vérifie le bon fonctionnement des nouveaux endpoints et du modèle de données
étendu pour les connecteurs BackupPC, Clonezilla et Restic.
"""
import json
import os
import sys
import tempfile
import unittest

# Ajouter le répertoire api au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import store


class TestConnectorSchema(unittest.TestCase):
    """Vérifie la création du schéma des connecteurs."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        store.ensure_schema(self.db_path)
        store.ensure_connector_schema(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_connector_configs_table_exists(self):
        """La table connector_configs doit exister."""
        configs = store.list_connector_configs(self.db_path)
        self.assertEqual(configs, [])

    def test_backup_jobs_table_exists(self):
        """La table backup_jobs doit exister."""
        jobs = store.list_jobs(self.db_path)
        self.assertEqual(jobs, [])

    def test_backup_schedules_table_exists(self):
        """La table backup_schedules doit exister."""
        schedules = store.list_schedules(self.db_path)
        self.assertEqual(schedules, [])

    def test_file_versions_table_exists(self):
        """La table file_versions doit exister."""
        hosts = store.get_hosts_with_versions(self.db_path)
        self.assertEqual(hosts, [])


class TestConnectorConfigs(unittest.TestCase):
    """Vérifie la gestion des configurations de connecteurs."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        store.ensure_schema(self.db_path)
        store.ensure_connector_schema(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_backuppc_config(self):
        """Création d'une configuration BackupPC."""
        cid = store.create_connector_config(
            self.db_path,
            connector_type="backuppc",
            name="Serveur BackupPC Principal",
            url="http://backuppc.local:8080",
        )
        self.assertIsNotNone(cid)
        self.assertGreater(cid, 0)

    def test_create_clonezilla_config(self):
        """Création d'une configuration Clonezilla."""
        cid = store.create_connector_config(
            self.db_path,
            connector_type="clonezilla",
            name="Serveur DRBL",
            url="http://drbl.local:9999",
        )
        self.assertIsNotNone(cid)

    def test_create_restic_config(self):
        """Création d'une configuration Restic."""
        cid = store.create_connector_config(
            self.db_path,
            connector_type="restic",
            name="Dépôt S3",
            url="s3:s3.amazonaws.com/my-bucket",
        )
        self.assertIsNotNone(cid)

    def test_list_connector_configs(self):
        """Liste des configurations."""
        store.create_connector_config(self.db_path, "backuppc", "PC1")
        store.create_connector_config(self.db_path, "clonezilla", "CZ1")
        store.create_connector_config(self.db_path, "restic", "R1")

        configs = store.list_connector_configs(self.db_path)
        self.assertEqual(len(configs), 3)

    def test_list_connector_configs_filter_by_type(self):
        """Filtrage par type de connecteur."""
        store.create_connector_config(self.db_path, "backuppc", "PC1")
        store.create_connector_config(self.db_path, "backuppc", "PC2")
        store.create_connector_config(self.db_path, "restic", "R1")

        configs = store.list_connector_configs(self.db_path, connector_type="backuppc")
        self.assertEqual(len(configs), 2)

    def test_delete_connector_config(self):
        """Suppression d'une configuration."""
        cid = store.create_connector_config(self.db_path, "backuppc", "PC1")
        deleted = store.delete_connector_config(self.db_path, cid)
        self.assertTrue(deleted)

        configs = store.list_connector_configs(self.db_path)
        self.assertEqual(len(configs), 0)

    def test_delete_nonexistent_config(self):
        """Suppression d'une configuration inexistante."""
        deleted = store.delete_connector_config(self.db_path, 9999)
        self.assertFalse(deleted)


class TestBackupJobs(unittest.TestCase):
    """Vérifie la gestion des jobs de sauvegarde."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        store.ensure_schema(self.db_path)
        store.ensure_connector_schema(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_job(self):
        """Création d'un job."""
        jid = store.create_job(
            self.db_path,
            connector_type="clonezilla",
            job_type="save",
            device="/dev/sda",
            image_name="pc-test-01",
        )
        self.assertIsNotNone(jid)
        self.assertGreater(jid, 0)

    def test_create_job_default_status_pending(self):
        """Le statut par défaut d'un nouveau job est 'pending'."""
        jid = store.create_job(
            self.db_path,
            connector_type="restic",
            job_type="backup",
        )
        job = store.get_job(self.db_path, jid)
        self.assertEqual(job["status"], "pending")

    def test_update_job_status(self):
        """Mise à jour du statut d'un job."""
        jid = store.create_job(
            self.db_path,
            connector_type="backuppc",
            job_type="save",
        )
        updated = store.update_job_status(self.db_path, jid, "running")
        self.assertTrue(updated)

        job = store.get_job(self.db_path, jid)
        self.assertEqual(job["status"], "running")
        self.assertIsNotNone(job["started_at"])

    def test_update_job_progress(self):
        """Mise à jour de la progression d'un job."""
        jid = store.create_job(
            self.db_path,
            connector_type="clonezilla",
            job_type="restore",
        )
        store.update_job_status(self.db_path, jid, "running", progress_percent=45)

        job = store.get_job(self.db_path, jid)
        self.assertEqual(job["progress_percent"], 45)

    def test_update_job_completed(self):
        """Marquage d'un job comme terminé."""
        jid = store.create_job(
            self.db_path,
            connector_type="restic",
            job_type="backup",
        )
        store.update_job_status(self.db_path, jid, "completed")

        job = store.get_job(self.db_path, jid)
        self.assertEqual(job["status"], "completed")
        self.assertIsNotNone(job["finished_at"])

    def test_update_job_failed(self):
        """Marquage d'un job comme échoué."""
        jid = store.create_job(
            self.db_path,
            connector_type="backuppc",
            job_type="save",
        )
        store.update_job_status(
            self.db_path, jid, "failed",
            error_message="Connexion refusée"
        )

        job = store.get_job(self.db_path, jid)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_message"], "Connexion refusée")

    def test_list_jobs_filter_by_status(self):
        """Filtrage des jobs par statut."""
        jid1 = store.create_job(self.db_path, "backuppc", "save")
        jid2 = store.create_job(self.db_path, "backuppc", "save")
        store.update_job_status(self.db_path, jid1, "completed")

        pending = store.list_jobs(self.db_path, status="pending")
        self.assertEqual(len(pending), 1)

        completed = store.list_jobs(self.db_path, status="completed")
        self.assertEqual(len(completed), 1)

    def test_list_jobs_filter_by_connector(self):
        """Filtrage des jobs par connecteur."""
        store.create_job(self.db_path, "backuppc", "save")
        store.create_job(self.db_path, "clonezilla", "save")
        store.create_job(self.db_path, "restic", "backup")

        backuppc_jobs = store.list_jobs(self.db_path, connector_type="backuppc")
        self.assertEqual(len(backuppc_jobs), 1)

    def test_get_nonexistent_job(self):
        """Récupération d'un job inexistant."""
        job = store.get_job(self.db_path, 9999)
        self.assertIsNone(job)


class TestBackupSchedules(unittest.TestCase):
    """Vérifie la gestion des planifications."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        store.ensure_schema(self.db_path)
        store.ensure_connector_schema(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_schedule(self):
        """Création d'une planification."""
        sid = store.create_schedule(
            self.db_path,
            connector_type="restic",
            name="Sauvegarde quotidienne",
            cron_expression="0 2 * * *",
        )
        self.assertIsNotNone(sid)

    def test_list_schedules(self):
        """Liste des planifications."""
        store.create_schedule(self.db_path, "restic", "Daily", "0 2 * * *")
        store.create_schedule(self.db_path, "backuppc", "Weekly", "0 0 * * 0")

        schedules = store.list_schedules(self.db_path)
        self.assertEqual(len(schedules), 2)

    def test_delete_schedule(self):
        """Suppression d'une planification."""
        sid = store.create_schedule(self.db_path, "restic", "Test", "0 0 * * *")
        deleted = store.delete_schedule(self.db_path, sid)
        self.assertTrue(deleted)

        schedules = store.list_schedules(self.db_path)
        self.assertEqual(len(schedules), 0)


class TestFileVersions(unittest.TestCase):
    """Vérifie la gestion des versions de fichiers."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        store.ensure_schema(self.db_path)
        store.ensure_connector_schema(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_add_file_version(self):
        """Ajout d'une version de fichier."""
        vid = store.add_file_version(
            self.db_path,
            connector_type="backuppc",
            host="srv-win-01",
            file_path="C:/Users/admin/doc.docx",
            version_number=1,
            size_bytes=1024000,
        )
        self.assertIsNotNone(vid)

    def test_list_file_versions(self):
        """Liste les versions d'un fichier."""
        store.add_file_version(self.db_path, "backuppc", "srv-win-01", "/etc/config", 1)
        store.add_file_version(self.db_path, "backuppc", "srv-win-01", "/etc/config", 2)
        store.add_file_version(self.db_path, "backuppc", "srv-win-01", "/etc/config", 3)

        versions = store.list_file_versions(self.db_path, "srv-win-01", "/etc/config")
        self.assertEqual(len(versions), 3)
        # Trié du plus récent au plus ancien
        self.assertEqual(versions[0]["version_number"], 3)

    def test_get_hosts_with_versions(self):
        """Liste les hôtes avec des versions."""
        store.add_file_version(self.db_path, "backuppc", "host1", "/f1", 1)
        store.add_file_version(self.db_path, "restic", "host2", "/f2", 1)

        hosts = store.get_hosts_with_versions(self.db_path)
        self.assertIn("host1", hosts)
        self.assertIn("host2", hosts)

    def test_get_hosts_with_versions_filter(self):
        """Filtrage des hôtes par connecteur."""
        store.add_file_version(self.db_path, "backuppc", "host1", "/f1", 1)
        store.add_file_version(self.db_path, "restic", "host2", "/f2", 1)

        backuppc_hosts = store.get_hosts_with_versions(self.db_path, connector_type="backuppc")
        self.assertEqual(backuppc_hosts, ["host1"])


class TestConnectorModules(unittest.TestCase):
    """Vérifie l'importation et le mode simulation des connecteurs."""

    def test_backuppc_connector_import(self):
        """Le connecteur BackupPC peut être importé."""
        from connectors.backuppc import BackupPCConnector
        c = BackupPCConnector()
        self.assertTrue(c._simulation_mode)

    def test_backuppc_simulation_hosts(self):
        """Le connecteur BackupPC retourne des hôtes simulés."""
        from connectors.backuppc import BackupPCConnector
        c = BackupPCConnector()
        hosts = c.get_hosts()
        self.assertIsInstance(hosts, list)
        self.assertGreater(len(hosts), 0)
        self.assertIn("host", hosts[0])

    def test_backuppc_simulation_versions(self):
        """Le connecteur BackupPC retourne des versions simulées."""
        from connectors.backuppc import BackupPCConnector
        c = BackupPCConnector()
        versions = c.get_host_versions("test-host")
        self.assertIsInstance(versions, list)
        self.assertGreater(len(versions), 0)

    def test_backuppc_simulation_pool_stats(self):
        """Le connecteur BackupPC retourne des stats simulées."""
        from connectors.backuppc import BackupPCConnector
        c = BackupPCConnector()
        stats = c.get_pool_stats()
        self.assertIn("dedup_ratio", stats)

    def test_clonezilla_connector_import(self):
        """Le connecteur Clonezilla peut être importé."""
        from connectors.clonezilla import ClonezillaConnector
        c = ClonezillaConnector()
        self.assertTrue(c._simulation_mode)

    def test_clonezilla_simulation_images(self):
        """Le connecteur Clonezilla retourne des images simulées."""
        from connectors.clonezilla import ClonezillaConnector
        c = ClonezillaConnector()
        images = c.get_images()
        self.assertIsInstance(images, list)
        self.assertGreater(len(images), 0)

    def test_clonezilla_simulation_jobs(self):
        """Le connecteur Clonezilla retourne des jobs simulés."""
        from connectors.clonezilla import ClonezillaConnector
        c = ClonezillaConnector()
        jobs = c.get_jobs()
        self.assertIsInstance(jobs, list)

    def test_clonezilla_simulation_pxe_config(self):
        """Le connecteur Clonezilla retourne une config PXE simulée."""
        from connectors.clonezilla import ClonezillaConnector
        c = ClonezillaConnector()
        config = c.get_pxe_config()
        self.assertIn("pxe_server", config)

    def test_restic_connector_import(self):
        """Le connecteur Restic peut être importé."""
        from connectors.restic import ResticConnector
        c = ResticConnector()
        self.assertTrue(c._simulation_mode)

    def test_restic_simulation_snapshots(self):
        """Le connecteur Restic retourne des snapshots simulés."""
        from connectors.restic import ResticConnector
        c = ResticConnector()
        snapshots = c.get_snapshots()
        self.assertIsInstance(snapshots, list)
        self.assertGreater(len(snapshots), 0)

    def test_restic_simulation_stats(self):
        """Le connecteur Restic retourne des stats simulées."""
        from connectors.restic import ResticConnector
        c = ResticConnector()
        stats = c.get_stats()
        self.assertIn("dedup_ratio", stats)

    def test_restic_simulation_check(self):
        """Le connecteur Restic retourne un check simulé."""
        from connectors.restic import ResticConnector
        c = ResticConnector()
        result = c.check()
        self.assertTrue(result["ok"])


class TestOriginalFeatures(unittest.TestCase):
    """Vérifie que les fonctionnalités originales (#249) fonctionnent toujours."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        store.ensure_schema(self.db_path)
        store.ensure_connector_schema(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_image_still_works(self):
        """La création d'image fonctionne toujours."""
        iid = store.create_image(
            self.db_path,
            device_mac="00:11:22:33:44:55",
            device_label="test-pc",
            tool="clonezilla",
            taken_at="2026-09-01T10:00:00Z",
        )
        self.assertIsNotNone(iid)

    def test_list_images_still_works(self):
        """La liste des images fonctionne toujours."""
        store.create_image(
            self.db_path,
            device_mac=None,
            device_label="test-pc",
            tool="backuppc",
            taken_at="2026-09-01T10:00:00Z",
        )
        images = store.list_images(self.db_path)
        self.assertEqual(len(images), 1)

    def test_delete_image_still_works(self):
        """La suppression d'image fonctionne toujours."""
        iid = store.create_image(
            self.db_path,
            device_mac=None,
            device_label="test-pc",
            tool="other",
            taken_at="2026-09-01T10:00:00Z",
        )
        deleted = store.delete_image(self.db_path, iid)
        self.assertEqual(deleted, 1)


if __name__ == "__main__":
    unittest.main()
