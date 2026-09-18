# Assistant IA interne — infrastructure d'inférence (étude, item 81, sept. 2026)

Complément de l'étude du backlog (item 81) et du PoC `assistant/` (#532) :
sur quoi faire tourner le modèle, sans achat d'abord, puis avec le GPU le
moins cher qui tienne dans le matériel existant. Chiffres attendus, à
remplacer par les mesures de l'évaluation (`assistant/data/eval-*.json`).
Aucune valeur d'exploitation (adresses, noms de machines réels) ici.

## Ce qui fixe la vitesse

En inférence locale, les jetons/s dépendent d'abord de la **bande passante
mémoire** (le modèle entier est relu à chaque jeton), ensuite des jeux
d'instructions (AVX2 / AVX-512 / AMX sur CPU), très peu du nombre de cœurs.
Ordres de grandeur pour un modèle 8B quantifié 4 bits (~5,5 Go) :

| Support | Bande passante | 8B Q4 | 30B-A3B Q4 (MoE, 3 Md actifs, 18 Go) |
|---|---|---|---|
| CPU DDR4/DDR5 double canal | 50-90 Go/s | 6-12 jetons/s | 8-15 (s'il tient en RAM) |
| GPU low profile 16 Go (224 Go/s) | 224 Go/s | 25-30 | partiel (déborde) |
| GPU 16 Go grand public (448 Go/s) | 448 Go/s | ~40 | partiel |
| GPU 24 Go (936 Go/s) | 936 Go/s | ~50 | 12-25 entier |

Lecture : le CPU suffit aux usages **par lots** (classement GED, résumés de
demandes, réponses avec sources en 20-40 s) ; le dialogue confortable
(≥ 25 jetons/s) demande un GPU.

## Palier 1 — sans achat : hyperviseur existant et postes détournés

Inventaire type d'un hôte Proxmox de bureau (Core Ultra 5 225, 10 cœurs,
AVX2, 40 Go DDR5-4800 double canal, charge nulle, ~28 Go disponibles) :
sous la règle « ne pas dépasser 2/3 des ressources », une VM **6 vCPU
(type `host`) / 16 Go, sans ballooning** tient sans toucher aux autres VM.
Elle sert le 8B en permanence ; le 30B-A3B (18 Go) n'y tient pas.

Un poste i9 de 12e génération (6 P + 8 E cœurs, 32 Go, AVX2) fait un
meilleur serveur d'inférence de nuit : il porte le 30B-A3B et sert de banc
de comparaison. `OLLAMA_NUM_THREADS` = nombre de P-cores (mélanger les
E-cores ralentit).

Commandes utiles (Proxmox, à adapter : stockage, ISO, identifiant) :

```
qm create 210 --name ia1 --cores 6 --sockets 1 --cpu host --memory 16384 --balloon 0 --numa 0 \
  --machine q35 --bios ovmf --efidisk0 <stockage>:1 --scsihw virtio-scsi-single \
  --scsi0 <stockage>:60,discard=on,ssd=1 --net0 virtio,bridge=vmbr0 --ostype l26 --agent 1 --onboot 1 \
  --cdrom local:iso/debian-12-netinst.iso
```

Dans la VM : `curl -fsSL https://ollama.com/install.sh | sh`, puis dans
`systemctl edit ollama` : `OLLAMA_HOST=0.0.0.0`, `OLLAMA_NUM_THREADS=6`,
`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `ollama pull qwen3:8b`.
Côté hub : `LLM_BASE_URL=http://<ip-vm>:11434/v1` (port 11434 sans
authentification : à filtrer sur le LAN/VPN).

Inventaire d'un hôte en une commande (root) : `lscpu`, `free -g`,
`dmidecode -t memory`, `lspci -nn | grep -iE "vga|3d"`, `lsblk -d`,
`zpool list`, `/proc/pressure/{cpu,memory}`, `qm list` + `qm config` des VM,
ARC ZFS (`/proc/spl/kstat/zfs/arcstats`).

## Palier 2 — un GPU dans le matériel existant

### Contrainte de format : lire le boîtier avant la carte

Un serveur **rack 2U** (ex. gamme « serveur 2U » de revendeur : 7 slots
**demi-hauteur**, alimentation 600 W 80+ Gold, carte mère Z890 avec deux
slots PCIe x16 pleine longueur libres, le premier relié au CPU en PCIe 5.0)
n'accepte que des cartes **low profile, deux slots au plus, idéalement
≤ 75 W** (alimentées par le slot : aucun câble à tirer dans un châssis peu
accessible). Les cartes grand public pleine hauteur (RTX 5060 Ti, 3090…)
sont exclues d'office, quel que soit le budget.

### Candidates low profile 16 Go (prix constatés sept. 2026)

| Carte | VRAM / bande passante | Conso | Prix | Verdict |
|---|---|---|---|---|
| **NVIDIA RTX 2000 Ada** (LP, 2 slots) | 16 Go GDDR6, 224 Go/s | 70 W, slot seul | ≈ 650-750 € | Choix sûr : CUDA, Ollama/llama.cpp sans surprise, passthrough Proxmox éprouvé. 8B Q4 ≈ 25-30 jetons/s, 14B Q4 ≈ 15 |
| **Intel Arc Pro B50** (LP, 2 slots, PCIe 5.0 x8) | 16 Go GDDR6, 224 Go/s | 70 W, slot seul | ≈ 350-400 € | Moitié prix, même VRAM ; pilote Linux `xe` + llama.cpp SYCL/Vulkan ou Ollama-IPEX, plus jeune ; SR-IOV promis, absent. À valider sur une VM de test avant achat |
| RTX A2000 12 Go (LP, occasion) | 12 Go, 288 Go/s | 70 W | ≈ 350-450 € | 12 Go limitent au 8B ; seulement si nettement moins chère |
| RTX 4000 SFF Ada 20 Go (LP) | 20 Go, 280 Go/s | 70 W | ≈ 1 200-1 400 € | Hors budget démonstration |

Pour un boîtier **tour** (pleine hauteur, alimentation avec câble PCIe) :
RTX 5060 Ti 16 Go neuve (≈ 450 €, 150 W, 448 Go/s, ~40 jetons/s en 8B)
comme premier GPU ; RTX 3090 24 Go d'occasion (≈ 650-900 €, 350 W,
alimentation 750 W) seulement si les mesures montrent que le 30B entier
change la qualité.

Recommandation pour le dossier « démonstration d'utilité » : **RTX 2000
Ada 16 Go** en référence principale (aucun risque d'intégration), **Arc
Pro B50** en variante économique sous réserve d'un test du pilote.

### Passthrough dans la VM `ia1` (à préparer avant l'achat)

1. BIOS : VT-d, Above 4G Decoding, Resizable BAR activés (redémarrage
   planifié de l'hôte).
2. Hôte : `intel_iommu=on iommu=pt` dans `/etc/kernel/cmdline` (boot ZFS :
   `proxmox-boot-tool refresh`), `vfio-pci` sur l'identifiant de la carte
   (`lspci -nn`), pilotes `nvidia`/`nouveau` (ou `xe`/`i915` pour Intel)
   blacklistés sur l'hôte ; l'affichage de l'hôte reste sur l'iGPU.
3. VM : créée en `q35` + OVMF (voir ci-dessus), puis
   `qm set 210 --hostpci0 <bus>:00,pcie=1`.
4. Dans la VM : pilote (NVIDIA : `nvidia-driver` Debian + CUDA ; Intel :
   noyau récent + `intel-compute-runtime`), Ollama détecte le GPU
   (`ollama ps` montre `100% GPU`).

## Critères de décision (à alimenter par l'évaluation)

- Palier 1 suffisant si : score ≥ 0,8 sur classements et résumés, ≥ 8
  jetons/s en CPU → usages par lots viables, pas d'achat.
- Passage au palier 2 si : la démonstration exige le dialogue (≥ 25
  jetons/s) ou des modèles 14B ; budget 400-750 € selon la carte.
- 24 Go (30B entier) impossible en 2U demi-hauteur : changer de châssis ou
  déporter sur une tour (poste détourné + carte pleine hauteur).

Sources de prix et de tests : Compute Market (RTX 3090 vs 5060 Ti, 2026),
ServeTheHome (Arc Pro B50), TechPowerUp / Tom's Hardware (lancement Arc Pro
B50/B60), n3rdware (cartes low profile 2026), fiche du serveur 2U chez le
revendeur.
