# -*- coding: utf-8 -*-
"""Inventaire logiciel de l'hôte pour l'audit de vulnérabilités (livraison
#699, tranche 2 de #688). Commande du central `sbom` :

  {"now": true}            inventaire tout de suite (en arrière-plan)
  {"schedule_days": 7}     relevé périodique (0 = arrêt), mémorisé par l'agent
  {"install": true}        installe syft s'il manque (sinon : refus explicite)

syft (Anchore) produit un SBOM CycloneDX du système de fichiers (paquets
dpkg / rpm / apk, Python, Node, Java, Go, binaires...), en priorité basse
(nice / ionice), sans les zones de données (boîtes aux lettres, disques de
VM / CT, journaux, caches) ; le SBOM part compressé, SIGNÉ, au central
(`POST /api/v1/agents/<id>/sbom`), qui le transmet à vuln-api : correspondance
OSV, priorité EPSS / KEV, tuile « Vulnérabilités ».

syft absent : installé à la demande dans /var/lib/si-agent/tools depuis les
publications officielles, archive vérifiée par son empreinte SHA-256 publiée.
Linux seulement dans cette tranche."""
import gzip
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile

SYFT_VERSION = "1.40.0"
RELEASES = "https://github.com/anchore/syft/releases/download/v%(v)s/"
# zones de données : rien à inventorier, des heures de lecture (relatif à la racine scannée)
EXCLUDES = ["./proc/**", "./sys/**", "./dev/**", "./run/**", "./tmp/**", "./var/tmp/**", "./mnt/**", "./media/**",
            "./var/lib/docker/**", "./var/lib/containerd/**", "./var/lib/lxc/**", "./var/lib/lxcfs/**", "./var/lib/vz/**",
            "./var/lib/libvirt/images/**", "./var/lib/mysql/**", "./var/lib/postgresql/**", "./var/vmail/**", "./var/mail/**",
            "./var/spool/**", "./var/log/**", "./var/cache/**", "./var/backups/**", "./home/*/Maildir/**", "./srv/**",
            "./var/lib/si-agent/**", "./swapfile", "./**/*.raw", "./**/*.qcow2", "./**/*.iso"]


def arch():
    m = platform.machine().lower()
    return {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(m)


def find_syft(tools_dir="/var/lib/si-agent/tools", which=shutil.which):
    local = os.path.join(tools_dir, "syft")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return which("syft")


def checksum_for(checksums_text, filename):
    for line in (checksums_text or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename:
            return parts[0].lower()
    return None


def install_syft(fetch, tools_dir="/var/lib/si-agent/tools", version=SYFT_VERSION, cpu=None):
    """Télécharge l'archive officielle + le fichier d'empreintes, vérifie, extrait `syft` seul. -> chemin."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError("installation de syft prise en charge sous Linux seulement (cette tranche)")
    a = cpu or arch()
    if not a:
        raise RuntimeError("architecture %s non prise en charge" % platform.machine())
    base = RELEASES % {"v": version}
    name = "syft_%s_linux_%s.tar.gz" % (version, a)
    sums = fetch(base + "syft_%s_checksums.txt" % version).decode("utf-8", "replace")
    want = checksum_for(sums, name)
    if not want:
        raise RuntimeError("empreinte de %s absente du fichier publié" % name)
    data = fetch(base + name)
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise RuntimeError("empreinte SHA-256 différente pour %s (attendu %s, obtenu %s)" % (name, want[:16], got[:16]))
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.isfile() and os.path.basename(m.name) == "syft"), None)
        if member is None:
            raise RuntimeError("syft absent de l'archive")
        blob = tar.extractfile(member).read()
    os.makedirs(tools_dir, exist_ok=True)
    dest = os.path.join(tools_dir, "syft")
    with open(dest + ".part", "wb") as fh:
        fh.write(blob)
    os.chmod(dest + ".part", 0o755)
    os.replace(dest + ".part", dest)
    return dest


def scan_argv(syft, root="/", excludes=None, which=shutil.which):
    argv = [syft, "scan", "dir:%s" % root, "-o", "cyclonedx-json", "-q"]
    for e in (EXCLUDES if excludes is None else excludes):
        argv += ["--exclude", e]
    prefix = []
    if which("nice"):
        prefix += ["nice", "-n", "19"]
    if which("ionice"):
        prefix += ["ionice", "-c", "3"]
    return prefix + argv


def run(argv, timeout=3600):
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                       env=dict(os.environ, SYFT_CHECK_FOR_APP_UPDATE="false"))
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")


def summarize(bom_bytes):
    """Nombre de composants et types (pour le compte rendu), sans garder le SBOM en mémoire plus que nécessaire."""
    bom = json.loads(bom_bytes)
    if str(bom.get("bomFormat", "")).lower() != "cyclonedx":
        raise ValueError("sortie de syft inattendue (CycloneDX JSON attendu)")
    types = {}
    for c in bom.get("components") or []:
        purl = c.get("purl") or ""
        kind = purl[4:].split("/", 1)[0] if purl.startswith("pkg:") else (c.get("type") or "?")
        types[kind] = types.get(kind, 0) + 1
    return {"components": len(bom.get("components") or []), "by_type": dict(sorted(types.items(), key=lambda kv: -kv[1])[:12])}


def inventory(upload, fetch=None, runner=run, tools_dir="/var/lib/si-agent/tools", install=False, root="/", which=shutil.which):
    """syft -> SBOM -> gzip -> upload(bytes) -> {"ok", components, by_type, bytes, central}. `upload` renvoie (statut, réponse)."""
    syft = find_syft(tools_dir, which)
    if not syft:
        if not install or fetch is None:
            return {"ok": False, "error": "syft absent sur l'hôte : relancer avec « installer syft » (téléchargement vérifié) ou installer syft"}
        syft = install_syft(fetch, tools_dir)
    code, out, err = runner(scan_argv(syft, root, which=which))
    if code != 0 or not out:
        return {"ok": False, "error": "syft %s : %s" % (code, (err.strip().splitlines() or ["sortie vide"])[-1][:300])}
    info = summarize(out)
    gz = gzip.compress(out, compresslevel=6)
    status, resp = upload(gz)
    ok = 200 <= int(status or 0) < 300
    return dict(info, ok=ok, bytes=len(out), sent_bytes=len(gz), central=resp,
                error=None if ok else "dépôt refusé par le central (%s) : %s" % (status, (resp or {}).get("error") if isinstance(resp, dict) else resp))


def due(state, now):
    """Relevé périodique à faire ? (schedule_days > 0 et dernier relevé plus vieux que la période)."""
    days = float(state.get("sbom_schedule_days") or 0)
    if days <= 0:
        return False
    return now - float(state.get("sbom_last_at") or 0) >= days * 86400
