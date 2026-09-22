# Règles réseau — VLAN, liaisons, SSID (source : carte des VLAN Nebula)

Types émis par `nebula/api/vlanmap.py` et champs disponibles pour `Action` :

- `link_missing_vlan` : `vlans`, `missing_on`, `missing_port`, `carried_by`, `carried_port`, `a`, `b`, `a_port`, `b_port`
- `ssid_vlan_not_on_link` : `vlan`, `ssids`, `a`, `b`, `a_port`, `b_port`
- `ssid_vlan_no_port` : `vlan`, `ssids`
- `vlan_no_gateway` : `vlan`, `switches`
- `link_bare` : `a`, `b`, `a_port`, `b_port`

## R-NET-01 · VLAN porté d'un seul côté d'une liaison entre commutateurs
- Quand : link_missing_vlan
- Gravité : haute
- Action : Ajouter le VLAN {vlans} en étiqueté sur le port {missing_port} de {missing_on} (le port {carried_port} de {carried_by} le porte déjà).
- Applicable : oui
- Pourquoi : Un VLAN déclaré sur un seul des deux ports d'un lien est coupé à cet endroit : tout ce qui vit dans ce VLAN de l'autre côté (un SSID, des postes) n'a plus ni passerelle ni DHCP. C'est la cause de l'incident Wi-Fi de septembre : les VLAN Wi-Fi manquaient sur les liaisons montantes des commutateurs d'accès vers le cœur.
- Vérifier : Relire la carte des VLAN ; la liaison ne doit plus être rouge et les deux côtés doivent lister les mêmes VLAN. Sur un poste du VLAN concerné, obtenir une adresse DHCP et joindre la passerelle.
- Exemples : 2026-09 (campus) : VLAN 30 et 40 absents des ports 49 des GS2220 vers le XS3800 ; ajout en étiqueté, retour immédiat du Wi-Fi.

## R-NET-02 · VLAN d'un SSID absent d'une liaison
- Quand : ssid_vlan_not_on_link
- Gravité : moyenne
- Action : Si des bornes diffusant {ssids} sont derrière cette liaison, ajouter le VLAN {vlan} en étiqueté sur {a} port {a_port} et {b} port {b_port} ; sinon, rien à faire (liaison hors du chemin de ce SSID).
- Applicable : non
- Pourquoi : Un SSID rattaché à un VLAN a besoin que ce VLAN traverse chaque liaison entre la borne et la passerelle. L'absence n'est une panne que si une borne de ce SSID est derrière le lien — d'où une gravité moyenne et une action à confirmer par une personne.
- Vérifier : Dans le synoptique, suivre le chemin des bornes concernées jusqu'à la passerelle : chaque liaison doit porter le VLAN.

## R-NET-03 · VLAN d'un SSID sur aucun port de commutateur
- Quand : ssid_vlan_no_port
- Gravité : haute
- Action : Créer le VLAN {vlan} sur les commutateurs et l'étiqueter sur les ports des bornes et des liaisons montantes, ou corriger le VLAN du SSID {ssids} si le numéro est une faute de frappe.
- Applicable : non
- Pourquoi : Le SSID envoie ses clients dans un VLAN que le réseau filaire ne connaît pas : ils sont isolés dès la borne.
- Vérifier : Le VLAN apparaît dans la carte avec des ports étiquetés sur chaque commutateur du chemin.

## R-NET-04 · VLAN présent sur les commutateurs sans interface de passerelle
- Quand : vlan_no_gateway
- Gravité : basse
- Action : Confirmer l'usage du VLAN {vlan} (présent sur {switches}) : routé ailleurs, VLAN de couche 2 seule (stockage, caméras, gestion) ou reliquat à supprimer. Si c'est un reliquat, le retirer des ports.
- Applicable : non
- Pourquoi : Un VLAN sans passerelle n'est pas forcément une erreur (réseau fermé volontaire), mais un VLAN oublié élargit la surface d'attaque et embrouille les diagnostics.
- Vérifier : La personne responsable du site nomme l'usage ; la note est reportée dans le référentiel des services.
- Exemples : 2026-09 (campus) : VLAN 10, 195, 250 et 666 sans interface sur la passerelle, usage à confirmer.

## R-NET-05 · Liaison sans aucun VLAN déclaré
- Quand : link_bare
- Gravité : info
- Action : Confirmer que la liaison {a} port {a_port} ↔ {b} port {b_port} est membre d'un agrégat (LACP) dont les VLAN sont portés par l'agrégat ; sinon, désactiver le port ou le configurer.
- Applicable : non
- Pourquoi : Deux liens entre les mêmes commutateurs, l'un plein et l'autre nu, est la signature d'un agrégat. Un lien nu isolé est plutôt un port oublié.
- Vérifier : Le réglage d'agrégation du commutateur liste les deux ports.
