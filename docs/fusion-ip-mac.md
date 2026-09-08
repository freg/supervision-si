# Tuile « Fusion IP/MAC » (livraison #431, backlog 64 point 4, suite)

L'onglet Fusion IP/MAC de l'ancienne maquette (`frontend/`) promu dans le
hub : `hub/src/FusionView.jsx`, logique pure `hub/src/fusionLib.js`
(reprise de `frontend/src/apps/fusionLib.js` + `lib/ipClassify.js`, 4
tests), client `hub/src/fusionClient.js`.

- **Corrélation par IP** entre `ipam-api /ip_list` (ip, mac, hostname,
  subnet, state) et `zenoss-api /ip_list` (ip, device, activeCount,
  maxSeverity, severityLabel), calculée dans le navigateur ; tri numérique
  des IP, noms d'hôte dédupliqués, sources par ligne, alertes Zenoss
  colorées.
- **Positions** : table `geolocations` de pixel-grid par IP, sinon
  correspondance par nom d'hôte (#426, sujets `ip:<ip>` — les mêmes que
  Supervision SI), sinon « en attente » / IP privée / IP publique.
- **Trois compléments** (boutons, droit *manage* sur pixel-grid via
  `groups`) : 🌍 GeoIP (`/geolocations/register_ips`, IP publiques
  résolues, privées en attente), 🏘 code postal du nom d'hôte
  (`/commune_centroid` → `geolocations`), 🏷 nom d'hôte
  (`/geolocations/resolve`, correspondances conservées, à valider /
  rejeter / corriger dans Supervision SI → cadre « Localisations »).
- Filtres (global, nom d'hôte, alerte, corrélées seulement), colonnes
  masquables (préférence `hub.fusion.hiddenColumns`), fiche par IP (détail
  IPAM et Zenoss, position, liens vers Supervision SI et le catalogue de
  positions).

Tuile et entrée du menu Réseau visibles dès que `VITE_IPAM_API_BASE_URL`
ou `VITE_ZENOSS_API_BASE_URL` est définie (déjà ajoutées au service `hub`
en #425). L'ancienne maquette garde son onglet tant que le front n'est
pas retiré.

Vérifié : tests Node, build Vite, rendu Chromium sur faux IPAM/Zenoss avec
le vrai pixel-grid (bouton « nom d'hôte » → correspondances réelles).
Non vérifié : ipam-api / zenoss-api réels, GeoIP réel.

Reste (backlog 64) : géomatique (GeoImportApp), puis retrait de l'ancien front.
