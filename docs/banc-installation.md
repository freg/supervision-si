# Banc d'installation des agents (#825, #826 — BACKLOG 133)

Tuile **Banc d'installation** : un pool de VM de test sur un nœud Proxmox (son agent, sondes proxmox active),
des modèles de VM, et des passages automatiques par modèle :
cloner → démarrer → attendre l'agent invité → installer → vérifier → désinstaller → arrêter → détruire.
Un échec saute au nettoyage : aucune VM de banc ne reste. L'agent du nœud refuse toute exécution dans une VM qui ne
s'appelle pas `banc-…`.

## 1. Pool

Onglet « Pool et passages » › « Configurer le pool » : agent du nœud, plage de vmid réservée aux clones (500 au plus),
stockage des clones, modèles (nom, os, vmid), commandes par OS. Réseau : un pont isolé (sans route vers la production)
qui joint seulement le central de test.

## 2. Modèles Linux (automatique)

Onglet « Modèles de VM » › « Fabriquer » : Debian 13 / 12, Ubuntu 24.04, Rocky 9. L'agent du nœud télécharge l'image
cloud officielle, vérifie son empreinte contre le fichier de sommes de l'éditeur, crée la VM (agent invité QEMU activé,
cloud-init DHCP, utilisateur `banc`, paquet `qemu-guest-agent` installé au premier démarrage par un snippet
`local:snippets/banc-vendor.yaml`), agrandit le disque et la transforme en modèle (`banc-modele-<recette>`).
Prérequis : PVE ≥ 7.2 (`import-from`), stockage `local` acceptant les snippets (case « activer les snippets »).

## 3. Modèles Windows (manuel)

1. ISO Windows + ISO VirtIO (virtio-win) sur le stockage ISO du nœud.
2. VM : q35, OVMF + TPM (Windows 11), VirtIO SCSI, réseau VirtIO, **agent invité QEMU activé**, nom `banc-modele-w11`.
3. Installation (pilote de disque depuis l'ISO VirtIO), puis `virtio-win-gt-x64.msi` et `guest-agent\qemu-ga-x86_64.msi`.
4. Mises à jour, puis Sysprep avec un fichier de réponse qui passe l'OOBE (compte local administrateur, pas de compte
   Microsoft) : `C:\Windows\System32\Sysprep\sysprep.exe /generalize /oobe /shutdown /unattend:C:\banc\unattend.xml`.
5. Sur le nœud : `qm template <vmid>` ; dans le hub : « Ajouter au pool ».
6. Commande d'installation Windows : ligne PowerShell du central ou MSI (`msiexec /i C:\banc\si-agent.msi /qn
   CENTRAL=… TOKEN=… CAFINGERPRINT=…`, MSI déposé dans le modèle avant le Sysprep — voir
   `si-agent/agent/windows/msi/README.md`).

## 4. Commandes par défaut

- Vérifier : Linux `systemctl is-active si-agent` (ou conteneur Docker) ; Windows : tâche planifiée `si-agent` en cours.
- Désinstaller : Windows `uninstall.ps1` ; Linux : aucune par défaut (le clone est détruit de toute façon).
- Les jetons d'enrôlement sont masqués partout (pool affiché, commandes relues, événements de l'agent).
