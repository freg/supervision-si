# Couple de proxys d'entrée interchangeables (#776)

Deux VM chez l'hébergeur, **sur deux nœuds Proxmox différents**, portent chacune un HAProxy identique. Elles reçoivent
les noms publics (HTTPS par SNI, et HTTP sur 80 pour les renouvellements Let's Encrypt) ou des ports publics, et les
renvoient vers des **serveurs internes** joints par le tunnel WireGuard. Les certificats restent sur les serveurs
internes (passage direct du TLS) : rien à renouveler sur les proxys.

```
 client ──DNS──> proxy-a (nœud A) ─┐
                 proxy-b (nœud B) ─┴─ wg0 ──> serveur interne actif (ou un candidat, au choix du hub)
```

- **Interchangeables** : même routes, même configuration (empreinte comparée dans la tuile). DNS en mode « les deux »
  (le nom pointe vers les deux IP : répartition, et le client essaie l'autre si l'une ne répond pas) ou « proxy actif »
  (une seule IP ; « Rendre actif » sur l'autre proxy, puis l'alerte DNS dit quoi changer).
- **Redirection dynamique** : chaque route liste des serveurs internes candidats ; choisir un autre candidat réapplique
  aussitôt sur les deux proxys.
- **Contrôle DNS automatique** (toutes les 10 min) : les serveurs **faisant autorité** de la zone (ce qui est publié) et
  des résolveurs publics (ce que voient les clients). Écart publié → événement « DNS à configurer » avec le **serveur
  DNS à modifier** (fournisseur et serveurs de la zone), l'enregistrement exact à poser et la valeur actuelle ; écart
  chez les résolveurs seulement → « propagation en cours ».
- Sécurité : l'agent fabrique lui-même la configuration HAProxy à partir de champs validés (aucun texte de
  configuration venu du réseau) ; `haproxy -c` avant tout remplacement ; l'ancienne configuration est remise si le
  rechargement échoue ; la configuration d'origine est gardée dans `haproxy.cfg.avant-si`.

## Mise en place
1. Deux VM Debian 13 (1 vCPU, 1 Go suffisent), une sur chaque nœud, chacune avec son IP publique.
2. Sur chaque VM, en root : `./install-edge.sh` (HAProxy, WireGuard, réglages), puis l'agent du hub
   (Agents hôtes › Déploiement, ligne Linux).
3. Tunnel vers le LAN : ajouter les deux VM à `deploy/nodes.json`, `deploy/wg-mesh.sh`, copier `wg0.conf`,
   `systemctl enable --now wg-quick@wg0` ; vérifier `./install-edge.sh --check`.
4. Hub › Réseau › **Proxys d'entrée** : déclarer les deux proxys (agent, IP publique, nœud), ajouter les routes
   (nom public → serveur interne : port, candidats), « Appliquer aux deux proxys ».
5. DNS : poser les enregistrements que la tuile indique (TTL court conseillé, 300 s), attendre « DNS conforme ».

Adresse réelle des clients : option PROXY par route (le serveur interne doit l'accepter, Apache :
`RemoteIPProxyProtocol On`), sinon les journaux internes voient l'adresse du proxy.
