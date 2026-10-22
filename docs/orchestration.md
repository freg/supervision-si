# Orchestration : VM et conteneurs (#832)

Tuile **Équipements > Orchestration**. Conteneurs : commande `orchestration` de l'agent de l'hôte
(`si-agent/agent/si_agent/orchctl.py`) ; état : sonde `plugin:orchestration` (60 s). VM : vues de l'infrastructure
Proxmox (sonde proxmox), création depuis les modèles du **Banc**.

| | k3s | Nomad |
|---|---|---|
| Installer | `get.k3s.io`, serveur, `--disable traefik --disable servicelb` | dépôt apt HashiCorp, serveur + client, pilote Docker |
| Rejoindre | `K3S_URL` + jeton (lu à la main sur le serveur) | `servers = ["<serveur>:4647"]` |
| Charge | Deployment + Service NodePort | job `service`, port dynamique |
| Quotas | ResourceQuota par espace | Enterprise uniquement |
| TTL | annotation `si-orchestration/expire` | meta `si_expire` |
| Accès API | kubeconfig root (`/etc/rancher/k3s/k3s.yaml`, 600) | `127.0.0.1:4646`, sans ACL |

## Mise en route d'un hôte

1. Pas de lien : opération manuelle -- agent installé (root) sur l'hôte ; Docker requis pour Nomad.
2. Agents hôtes > l'agent > Sondes : activer **orchestration**.
3. Orchestration > Clusters : « Installer » k3s et / ou Nomad.
4. Ajouter un nœud k3s : sur le serveur `sudo cat /var/lib/rancher/k3s/server/node-token`, puis sur le nouvel hôte
   « Rejoindre un serveur… » (URL `https://<serveur>:6443` + jeton ; masqué ensuite).

Interface web Nomad : `ssh -L 4646:127.0.0.1:4646 <hôte>` puis http://127.0.0.1:4646.
