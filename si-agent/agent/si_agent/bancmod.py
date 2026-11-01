# -*- coding: utf-8 -*-
"""Modèles de VM du banc d'installation (livraison #826, BACKLOG 133) -- commande `banc_modele` du central.

Sur un nœud Proxmox (agent en root), fabrique un modèle (« template ») Linux à partir de l'image cloud officielle de la
distribution : téléchargement, empreinte vérifiée contre le fichier de sommes de l'éditeur, VM créée avec l'agent invité
QEMU activé, disque importé (import-from, PVE ≥ 7.2), cloud-init (DHCP, utilisateur « banc », paquet qemu-guest-agent
installé au premier démarrage par un « vendor snippet »), disque agrandi, puis `qm template`. Les modèles Windows
restent à préparer à la main (ISO, VirtIO, agent invité) : voir docs/banc-installation.md.
Pur et testé : valider, script."""
import re

RECETTES = {
    "debian13": {"os": "linux", "titre": "Debian 13 (trixie)",
                 "url": "https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2",
                 "sommes": "https://cloud.debian.org/images/cloud/trixie/latest/SHA512SUMS", "algo": "sha512"},
    "debian12": {"os": "linux", "titre": "Debian 12 (bookworm)",
                 "url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2",
                 "sommes": "https://cloud.debian.org/images/cloud/bookworm/latest/SHA512SUMS", "algo": "sha512"},
    "ubuntu2404": {"os": "linux", "titre": "Ubuntu 24.04 LTS (noble)",
                   "url": "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
                   "sommes": "https://cloud-images.ubuntu.com/noble/current/SHA256SUMS", "algo": "sha256"},
    "rocky9": {"os": "linux", "titre": "Rocky Linux 9",
               "url": "https://dl.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2",
               "sommes": "https://dl.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud-Base.latest.x86_64.qcow2.CHECKSUM", "algo": "sha256"},
}
STORAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,62}$")
BRIDGE_RE = re.compile(r"^vmbr\d{1,4}(\.\d{1,4})?$")
DOSSIER = "/var/lib/vz/template/banc"
SNIPPET = "banc-vendor.yaml"
VENDOR = """#cloud-config
package_update: true
packages:
  - qemu-guest-agent
runcmd:
  - [systemctl, enable, --now, qemu-guest-agent]
"""


def valider(params):
    p = params or {}
    r = str(p.get("recette") or "")
    if r not in RECETTES:
        return None, "recette inconnue (%s)" % ", ".join(sorted(RECETTES))
    try:
        vmid = int(p.get("vmid"))
    except (TypeError, ValueError):
        return None, "vmid entier requis"
    if not 100 <= vmid <= 999999999:
        return None, "vmid invalide"
    st = str(p.get("stockage") or "local-lvm")
    pont = str(p.get("pont") or "vmbr0")
    if not STORAGE_RE.match(st):
        return None, "stockage invalide"
    if not BRIDGE_RE.match(pont):
        return None, "pont réseau invalide (vmbrN)"
    try:
        disque = max(4, min(200, int(p.get("disque_go") or 12)))
    except (TypeError, ValueError):
        return None, "disque_go entier"
    return {"recette": r, "vmid": vmid, "stockage": st, "pont": pont, "disque_go": disque,
            "autoriser_snippets": bool(p.get("autoriser_snippets"))}, None


def script(v):
    """Script bash (root, nœud Proxmox) qui fabrique le modèle ; s'arrête à la première erreur avec un message clair."""
    r = RECETTES[v["recette"]]
    fichier = r["url"].rsplit("/", 1)[1]
    nom = "banc-modele-%s" % v["recette"]
    return """set -eu
D=%(d)s; F=%(f)s; V=%(vmid)d
fail() { echo "ERREUR : $*" >&2; exit 1; }
command -v qm >/dev/null || fail "qm absent : ce n'est pas un nœud Proxmox"
qm status $V >/dev/null 2>&1 && fail "le vmid $V existe déjà"
mkdir -p "$D" /var/lib/vz/snippets
cd "$D"
curl -fsSL --retry 3 -o sommes.part '%(sommes)s' || fail "fichier de sommes injoignable : %(sommes)s"
ATT=$(grep -E "(^|[ *(])$F([) ]|$)" sommes.part | grep -oE '[0-9a-f]{64,128}' | head -n 1)
[ -n "$ATT" ] || fail "empreinte de $F absente du fichier de sommes"
if [ -f "$F" ] && [ "$(%(algo)ssum "$F" | cut -d' ' -f1)" = "$ATT" ]; then echo "image déjà présente et vérifiée"; else
  curl -fSL --retry 3 -o "$F.part" '%(url)s' || fail "téléchargement impossible : %(url)s"
  [ "$(%(algo)ssum "$F.part" | cut -d' ' -f1)" = "$ATT" ] || { rm -f "$F.part"; fail "empreinte %(algo)s différente : image refusée"; }
  mv "$F.part" "$F"
fi
if ! pvesm status --content snippets 2>/dev/null | awk 'NR>1{print $1}' | grep -qx local; then
  if [ "%(snip)s" = "1" ]; then
    C=$(pvesh get /storage/local --output-format json | python3 -c 'import json,sys; print(json.load(sys.stdin).get("content",""))')
    pvesm set local --content "$C,snippets" || fail "impossible d'activer les snippets sur le stockage local"
    echo "contenu « snippets » activé sur le stockage local"
  else
    fail "le stockage « local » n'accepte pas les snippets (cloud-init de l'agent invité) : relancer avec autoriser_snippets, ou pvesm set local --content <actuel>,snippets"
  fi
fi
cat > /var/lib/vz/snippets/%(snippet)s <<'EOS'
%(vendor)sEOS
qm create $V --name %(nom)s --memory 2048 --cores 2 --net0 virtio,bridge=%(pont)s --scsihw virtio-scsi-pci --agent enabled=1 \\
  --ostype l26 --serial0 socket --vga serial0 --description "banc d'installation si-agent : %(titre)s (#826)"
qm set $V --scsi0 %(st)s:0,import-from="$D/$F" || { qm destroy $V --purge 1 >/dev/null 2>&1; fail "import du disque impossible (PVE >= 7.2 requis, stockage %(st)s)"; }
qm resize $V scsi0 %(disque)dG
qm set $V --ide2 %(st)s:cloudinit --boot order=scsi0 --ipconfig0 ip=dhcp --ciuser banc --cicustom vendor=local:snippets/%(snippet)s
qm template $V
echo "modèle $V (%(nom)s) prêt"
""" % {"d": DOSSIER, "f": fichier, "vmid": v["vmid"], "sommes": r["sommes"], "url": r["url"], "algo": r["algo"], "snip": "1" if v["autoriser_snippets"] else "0",
       "snippet": SNIPPET, "vendor": VENDOR, "nom": nom, "pont": v["pont"], "titre": r["titre"], "st": v["stockage"], "disque": v["disque_go"]}


def run(cmd, params):
    v, err = valider(params)
    if err:
        return {"ok": False, "error": err}
    r = cmd(["bash", "-c", script(v)], timeout=3600)
    rc = getattr(r, "returncode", -1)
    out = (getattr(r, "stdout", "") or "")[-2000:]
    errt = (getattr(r, "stderr", "") or "")[-2000:]
    if rc != 0:
        msg = next((l for l in errt.splitlines()[::-1] if l.startswith("ERREUR")), None) or errt.strip()[-400:] or "code %s" % rc
        return {"ok": False, "error": msg, "result": {"stdout": out, "stderr": errt, "returncode": rc}}
    return {"ok": True, "error": None, "result": {"vmid": v["vmid"], "recette": v["recette"], "os": RECETTES[v["recette"]]["os"], "stdout": out}}
