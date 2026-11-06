# Hub du campus — cadrage (2026-11-06)

**Décisions (freg, 06/11/2026)**
- **Autonome + remontée** : le hub du campus fonctionne seul sur le LAN du campus (ses agents, sa base) et remonte ses
  données au hub principal ; il continue de fonctionner si le lien est coupé.
- **VM dédiée sur prodia** (Proxmox du campus) : isolée de l'IA, sauvegardable, déplaçable.
- **Contenu** : réseau Nebula (synoptique, VLAN, historique des clients, flux éditeurs, équipements du site, plan),
  sondes et Data RF, démonstrations, parc IA du campus (prodia, preprodia).
- **Comptes** : **Keycloak satellite** sur le campus, **réplique filtrée sur le groupe `numeria`** du realm principal
  (comptes, groupes, rôles et mots de passe hachés de ce groupe seulement ; aucun autre compte du realm).

## Ce qui existe et sert de base
- **Socle d'un nœud** (#661, `deploy/socle.py`, `deploy/README-socle.md`) : tls-proxy, Keycloak, services-api (tour de
  contrôle, livraisons, mise à jour git), hub, prefs/rights/accounts/notify ; `socle.py up +<tuile>` ajoute une tuile et
  ses dépendances.
- **Central local / collecteur de site** (`si-agent/local-central`, service `si-collecteur`) : agents enrôlés sur
  place, remontée vers le hub. Précédent : démo Numeria (`docs/demo-numeria-runbook.md`) — **le Proxmox du campus n'a
  pas de route vers super** : toute remontée part DU campus vers l'adresse publique du hub principal.
- **Nebula** : API dans le nuage (aucun accès LAN requis) ; la VM du campus n'a besoin que d'une sortie Internet.
- Démonstrations (#982-#985), Espaces disques (#986), Parc IA, Data RF : tuiles existantes, rien à réécrire.

## Tranches
1. **Profil « campus » du hub** (front, sans infrastructure) : `VITE_HUB_PROFIL=campus` → titre « Hub Campus »,
   seules les tuiles du campus (nebula, equipements-site, flux-editeurs, reperage, audit-securite, datarf, si-agent
   filtré sur le site du campus, demos, iapark, espaces), accueil simplifié. Même profil appliqué dans le hub principal
   aux membres du seul groupe `numeria` (droits existants, rights-api).
2. **Nœud campus** : VM Debian 13 sur prodia, `deploy/socle.py up +nebula-api +si-agent-api` ; `.env` du campus
   (HOST_IP, nom public éventuel, `NEBULA_SITES=<site du campus>` pour ne relever que ce site) ; procédure dans
   `deploy/README-campus.md`.
3. **Keycloak satellite** : le hub principal expose une exportation **filtrée sur le groupe `numeria`**
   (services-api, jeton de nœud `SI_NODE_TOKEN`, export Keycloak partiel : utilisateurs du groupe avec leurs
   identifiants hachés, groupes, rôles du client hub) ; le campus la **tire** toutes les heures (sens campus → principal,
   le seul ouvert) et l'importe dans son realm. Un compte retiré du groupe est désactivé sur le satellite à la synchro
   suivante. Changement de mot de passe : sur le principal (propagé à la synchro).
4. **Remontée vers le principal** : les agents du campus (sondes, prodia, preprodia) s'enrôlent sur le si-agent-api du
   campus, qui relaie mesures et événements vers le principal (mécanisme du collecteur de site) ; file locale tant que
   le lien est coupé. Nebula n'a pas besoin de remontée (le principal relève déjà le nuage).
5. **Démonstrations et parc IA sur place** : services-api du campus (job demo) et vues IA pointées sur prodia.

## À vérifier avant la tranche 2
- Sortie Internet de la VM du campus (Nebula, GitHub pour `git pull`), et accès à l'adresse publique du hub principal
  (`supervision.optline.fr`) depuis le LAN du campus.
- Adresse et nom de la VM ; ressources (4 vCPU, 8 Go, 60 Go suffisent pour le socle + Nebula + agents).
