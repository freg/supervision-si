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

#711 : Windows et macOS (syft officiel de la plateforme, exclusions propres au
système, logiciels installés relevés par la sonde software-inventory ajoutés au
SBOM : registre Windows, /Applications) ; images Docker des conteneurs en
service (une par actif « image », `docker:<image>`), commande `{"images": false}`
pour s'en passer."""
import re
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
import urllib.parse
import zipfile

SYFT_VERSION = "1.40.0"
RELEASES = "https://github.com/anchore/syft/releases/download/v%(v)s/"
# zones de données : rien à inventorier, des heures de lecture (relatif à la racine scannée)
EXCLUDES = ["./proc/**", "./sys/**", "./dev/**", "./run/**", "./tmp/**", "./var/tmp/**", "./mnt/**", "./media/**",
            "./var/lib/docker/**", "./var/lib/containerd/**", "./var/lib/lxc/**", "./var/lib/lxcfs/**", "./var/lib/vz/**",
            "./var/lib/libvirt/images/**", "./var/lib/mysql/**", "./var/lib/postgresql/**", "./var/vmail/**", "./var/mail/**",
            "./var/spool/**", "./var/log/**", "./var/cache/**", "./var/backups/**", "./home/*/Maildir/**", "./srv/**",
            "./var/lib/si-agent/**", "./swapfile", "./**/*.raw", "./**/*.qcow2", "./**/*.iso"]


EXCLUDES_WINDOWS = ["./Windows/WinSxS/**", "./Windows/Installer/**", "./Windows/SoftwareDistribution/**", "./Windows/Temp/**",
                    "./$Recycle.Bin/**", "./System Volume Information/**", "./Users/*/AppData/Local/Temp/**",
                    "./Users/*/AppData/Local/Microsoft/Windows/INetCache/**", "./ProgramData/si-agent/**", "./ProgramData/Microsoft/Windows Defender/**",
                    "./pagefile.sys", "./hiberfil.sys", "./swapfile.sys", "./**/*.vhd", "./**/*.vhdx", "./**/*.iso", "./**/*.pst", "./**/*.ost"]
EXCLUDES_DARWIN = ["./System/Volumes/**", "./System/Library/**", "./Volumes/**", "./dev/**", "./private/var/vm/**", "./private/var/folders/**",
                   "./private/var/db/**", "./private/tmp/**", "./Library/Caches/**", "./Users/*/Library/Caches/**", "./Users/*/Library/Mail/**",
                   "./Users/*/Library/Containers/**", "./usr/local/var/lib/si-agent/**", "./**/*.dmg", "./**/*.iso"]


def system_name():
    return "windows" if sys.platform.startswith("win") else "darwin" if sys.platform == "darwin" else "linux"


def default_root(system=None):
    system = system or system_name()
    return (os.environ.get("SystemDrive", "C:") + "\\") if system == "windows" else "/"


def excludes_for(system=None):
    system = system or system_name()
    return EXCLUDES_WINDOWS if system == "windows" else EXCLUDES_DARWIN if system == "darwin" else EXCLUDES


def arch():
    m = platform.machine().lower()
    return {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(m)


def find_syft(tools_dir="/var/lib/si-agent/tools", which=shutil.which, system=None):
    local = os.path.join(tools_dir, "syft.exe" if (system or system_name()) == "windows" else "syft")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return which("syft")


def checksum_for(checksums_text, filename):
    for line in (checksums_text or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == filename:
            return parts[0].lower()
    return None


def install_syft(fetch, tools_dir="/var/lib/si-agent/tools", version=SYFT_VERSION, cpu=None, system=None):
    """Télécharge l'archive officielle de la plateforme + le fichier d'empreintes, vérifie, extrait `syft` seul. -> chemin."""
    system = system or system_name()
    a = cpu or arch()
    if not a:
        raise RuntimeError("architecture %s non prise en charge" % platform.machine())
    base = RELEASES % {"v": version}
    name = "syft_%s_%s_%s.%s" % (version, system, a, "zip" if system == "windows" else "tar.gz")
    binary = "syft.exe" if system == "windows" else "syft"
    sums = fetch(base + "syft_%s_checksums.txt" % version).decode("utf-8", "replace")
    want = checksum_for(sums, name)
    if not want:
        raise RuntimeError("empreinte de %s absente du fichier publié" % name)
    data = fetch(base + name)
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise RuntimeError("empreinte SHA-256 différente pour %s (attendu %s, obtenu %s)" % (name, want[:16], got[:16]))
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            member = next((n for n in z.namelist() if os.path.basename(n) == binary), None)
            if member is None:
                raise RuntimeError("%s absent de l'archive" % binary)
            blob = z.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = next((m for m in tar.getmembers() if m.isfile() and os.path.basename(m.name) == binary), None)
            if member is None:
                raise RuntimeError("syft absent de l'archive")
            blob = tar.extractfile(member).read()
    os.makedirs(tools_dir, exist_ok=True)
    dest = os.path.join(tools_dir, binary)
    with open(dest + ".part", "wb") as fh:
        fh.write(blob)
    os.chmod(dest + ".part", 0o755)
    os.replace(dest + ".part", dest)
    return dest


def scan_argv(syft, root="/", excludes=None, which=shutil.which, source=None):
    """`source` (#711) : cible syft explicite (ex. `docker:nginx:1.25`) ; sinon le système de fichiers `root`."""
    argv = [syft, "scan", source or "dir:%s" % root, "-o", "cyclonedx-json", "-q"]
    for e in ([] if source else (EXCLUDES if excludes is None else excludes)):
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


def add_installed(bom_bytes, installed, source="software-inventory"):
    """#711 : logiciels installés (registre Windows, /Applications…) ajoutés au SBOM quand syft ne les voit pas
    (même nom déjà présent : ignoré). Composants « application » avec éditeur ; pas de purl (aucun écosystème),
    Dependency-Track les rapproche par nom / éditeur / version. -> (octets, nombre ajouté). Pure."""
    bom = json.loads(bom_bytes)
    comps = bom.setdefault("components", [])
    have = {(str(c.get("name") or "").lower(), str(c.get("version") or "")) for c in comps}
    n = 0
    for it in installed or []:
        name, ver = str(it.get("name") or "").strip(), str(it.get("version") or "").strip()
        if not name or (name.lower(), ver) in have:
            continue
        have.add((name.lower(), ver))
        c = {"type": "application", "name": name[:200], "bom-ref": "installed:%d" % n,
             "properties": [{"name": "si:source", "value": it.get("source") or source}]}
        if ver:
            c["version"] = ver[:100]
        if it.get("publisher"):
            c["publisher"] = str(it["publisher"])[:200]
            c["supplier"] = {"name": str(it["publisher"])[:200]}
        comps.append(c)
        n += 1
    return json.dumps(bom).encode(), n


def docker_images(runner=None, which=shutil.which, limit=20):
    """Images des conteneurs en service (dédoublonnées, au plus `limit`) ; [] sans Docker. -> [référence]."""
    if not which("docker"):
        return []
    code, out, _err = (runner or run)(["docker", "ps", "--format", "{{.Image}}"], timeout=60)
    if code != 0:
        return []
    text = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
    refs = []
    for line in text.splitlines():
        ref = line.strip()
        if ref and ref not in refs and re.match(r"^[\w./:@+-]{1,250}$", ref):
            refs.append(ref)
    return refs[:limit]


def _send(upload, out, **kw):
    gz = gzip.compress(out, compresslevel=6)
    status, resp = upload(gz, **kw) if kw else upload(gz)
    ok = 200 <= int(status or 0) < 300
    return ok, len(gz), resp, None if ok else "dépôt refusé par le central (%s) : %s" % (status, (resp or {}).get("error") if isinstance(resp, dict) else resp)


def inventory(upload, fetch=None, runner=run, tools_dir="/var/lib/si-agent/tools", install=False, root=None, which=shutil.which,
              system=None, installed=None, images=False):
    """syft -> SBOM -> gzip -> upload(bytes) -> {"ok", components, by_type, bytes, central, images}. `upload` renvoie
    (statut, réponse) ; pour une image : upload(bytes, kind="image", name=<référence>)."""
    system = system or system_name()
    syft = find_syft(tools_dir, which, system)
    if not syft:
        if not install or fetch is None:
            return {"ok": False, "error": "syft absent sur l'hôte : relancer avec « installer syft » (téléchargement vérifié) ou installer syft"}
        syft = install_syft(fetch, tools_dir, system=system)
    code, out, err = runner(scan_argv(syft, root or default_root(system), excludes_for(system), which=which))
    if code != 0 or not out:
        return {"ok": False, "error": "syft %s : %s" % (code, (err.strip().splitlines() or ["sortie vide"])[-1][:300])}
    added = 0
    if installed:
        out, added = add_installed(out, installed)
    info = summarize(out)
    ok, sent, resp, error = _send(upload, out)
    res = dict(info, ok=ok, bytes=len(out), sent_bytes=sent, central=resp, error=error, installed_added=added, images=[])
    for ref in (docker_images(runner, which) if images else []):
        c, o, e = runner(scan_argv(syft, which=which, source="docker:%s" % ref))
        if c != 0 or not o:
            res["images"].append({"name": ref, "ok": False, "error": "syft %s : %s" % (c, (e.strip().splitlines() or ["sortie vide"])[-1][:200])})
            continue
        i_ok, _sent, i_resp, i_err = _send(upload, o, kind="image", name=ref)
        res["images"].append(dict(summarize(o), name=ref, ok=i_ok, error=i_err,
                                  findings=(i_resp or {}).get("findings") if isinstance(i_resp, dict) else None))
    return res


def due(state, now):
    """Relevé périodique à faire ? (schedule_days > 0 et dernier relevé plus vieux que la période)."""
    days = float(state.get("sbom_schedule_days") or 0)
    if days <= 0:
        return False
    return now - float(state.get("sbom_last_at") or 0) >= days * 86400
