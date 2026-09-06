"""
Sauvegardes versionnées de l'annuaire LDAP -- même philosophie que
tickets/api/backup_manager.py, adaptée au LDIF. Dump horodaté,
rétention, lecture sécurisée.

Différence assumée avec backup_manager.py : là où les sauvegardes de
tickets sont un dump SQL complet réinjectable tel quel, restaurer un
LDIF ici revient à appliquer des changements via `ldapmodify` --
demandé explicitement -- jamais un "vider puis recharger" (LDAP n'a
pas d'équivalent simple à "DROP puis CREATE" une base entière depuis
un client réseau standard).
"""

import os
import time


def _timestamp():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def backup_filename(trigger, timestamp=None):
    """Même raisonnement que backup_manager.backup_filename (tickets)
    -- trigger tracé dans le nom pour comprendre l'historique sans
    ouvrir chaque fichier."""
    ts = timestamp or _timestamp()
    safe_trigger = "".join(c if c.isalnum() or c == "-" else "-" for c in trigger)
    return f"ldap-{ts}-{safe_trigger}.ldif"


def list_backup_files(backup_dir):
    if not os.path.isdir(backup_dir):
        return []
    return sorted(
        (f for f in os.listdir(backup_dir) if f.startswith("ldap-") and f.endswith(".ldif")),
        reverse=True,
    )


def files_to_prune(all_files, retention_count):
    if retention_count <= 0:
        return list(all_files)
    return list(all_files[retention_count:])


def is_safe_backup_filename(filename):
    if not filename or not isinstance(filename, str):
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return filename.startswith("ldap-") and filename.endswith(".ldif")


def create_backup(backup_dir, trigger, config, export_fn, retention_count=30):
    """Point d'entrée unique -- `export_fn` injecté (typiquement
    ldap_client.export_ldif) plutôt qu'un appel direct, pour rester
    testable sans vrai serveur LDAP. Lève une exception si l'export
    échoue -- jamais un fichier de sauvegarde vide/partiel écrit sur
    disque en cas d'échec."""
    result = export_fn(config)
    if not result["ok"]:
        raise RuntimeError(f"export LDAP échoué : {result['stderr']}")

    os.makedirs(backup_dir, exist_ok=True)
    filename = backup_filename(trigger)
    filepath = os.path.join(backup_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(result["stdout"])

    all_files = list_backup_files(backup_dir)
    for old_file in files_to_prune(all_files, retention_count):
        try:
            os.remove(os.path.join(backup_dir, old_file))
        except OSError:
            pass

    return filename


def read_backup(backup_dir, filename):
    """Lit le contenu d'une sauvegarde -- vérifie la sécurité du nom
    de fichier AVANT tout accès disque, même garde-fou que
    backup_manager.restore_backup (tickets)."""
    if not is_safe_backup_filename(filename):
        raise ValueError("nom de fichier de sauvegarde invalide")
    filepath = os.path.join(backup_dir, filename)
    if not os.path.isfile(filepath):
        raise ValueError("sauvegarde introuvable")
    with open(filepath, encoding="utf-8") as f:
        return f.read()
