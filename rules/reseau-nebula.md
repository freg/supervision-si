# Règles réseau — VLAN, liaisons, SSID (source : carte des VLAN Nebula)

Types émis par `nebula/api/vlanmap.py` et champs disponibles pour `Action` :

- `link_missing_vlan` : `vlans`, `missing_on`, `missing_port`, `carried_by`, `carried_port`, `a`, `b`, `a_port`, `b_port`
- `ssid_vlan_not_on_link` : `vlan`, `ssids`, `a`, `b`, `a_port`, `b_port`
- `ssid_vlan_no_port` : `vlan`, `ssids`
- `vlan_no_gateway` : `vlan`, `switches`
- `link_bare` : `a`, `b`, `a_port`, `b_port`
- `ap_port_missing_ssid_vlan` : `vlans`, `ssids`, `ports`, `count` (#701)
- `ap_port_all_vlans` : `ports`, `count` (#701)
- `gateway_ip_not_host` : `vlan`, `interface`, `address`, `suggest` (#701)

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

## R-NET-06 · VLAN d'un SSID absent des ports de bornes
- Quand : ap_port_missing_ssid_vlan
- Gravité : haute
- Action : Ajouter le VLAN {vlans} (SSID {ssids}) aux VLAN autorisés des {count} port(s) de borne concernés. Si ces ports suivent un profil de port commun (ex. « AP »), compléter le PROFIL plutôt que chaque port, sans passer en « All ».
- Applicable : non
- Pourquoi : La borne dépose les clients du SSID dans ce VLAN étiqueté ; si son port ne l'autorise pas, ils restent isolés à la borne : association Wi-Fi réussie, mais ni passerelle ni DHCP.
- Vérifier : Un client du SSID obtient une adresse DHCP du VLAN et joint la passerelle ; l'anomalie disparaît de la carte.
- Exemples : 2026-10 (site-alpha) : nouveau SSID sur un nouveau VLAN, absent du profil de port des bornes ; DHCP rétabli après ajout du VLAN au profil.

## R-NET-07 · Ports de bornes en VLAN « All »
- Quand : ap_port_all_vlans
- Gravité : moyenne
- Action : Remplacer « All » par la liste du VLAN de gestion des bornes et des VLAN de leurs SSID sur {count} port(s) (ou dans leur profil de port).
- Applicable : non
- Pourquoi : Une prise de borne est souvent accessible (plafond, mur) : en « All », un poste qui s'y branche peut étiqueter n'importe quel VLAN du site, serveurs et administration compris.
- Vérifier : Les ports de bornes ne listent que la gestion et les VLAN des SSID ; tous les SSID fonctionnent toujours.

## R-NET-08 · Interface de passerelle à l'adresse du réseau ou de diffusion
- Quand : gateway_ip_not_host
- Gravité : haute
- Action : Corriger l'adresse de l'interface {interface} (VLAN {vlan}) : {address} -> {suggest}, puis vérifier la passerelle annoncée par le DHCP.
- Applicable : non
- Pourquoi : L'adresse du réseau (ou de diffusion) n'est pas une adresse d'hôte : la passerelle n'existe pas pour les postes du VLAN et son serveur DHCP ne répond pas.
- Vérifier : Un poste du VLAN obtient une adresse et joint {suggest} sans le masque.
- Exemples : 2026-10 (site-alpha) : interface d'un nouveau VLAN saisie en x.x.x.0/24.

## R-NET-09 · Port sensible publié sur Internet
- Quand : nat_sensitive_port
- Gravité : haute
- Action : Retirer la publication des port(s) {ports} ({services}) vers {private_ip}, ou la restreindre aux adresses d'origine connues ; pour l'administration, passer par le VPN de la passerelle.
- Applicable : non
- Pourquoi : SSH, bureau à distance, partages Windows, bases de données ou consoles d'administration ouverts à tout Internet sont balayés en permanence : force brute, failles connues, rançongiciels.
- Vérifier : La publication a disparu (ou n'accepte que les origines prévues) ; un balayage depuis l'extérieur (audit extérieur du hub) ne voit plus le port.

## R-NET-10 · Port sensible publié, origine restreinte
- Quand : nat_sensitive_port_restricted
- Gravité : basse
- Action : Vérifier que les origines autorisées ({remote}) sont toujours les bonnes et que le service vers {private_ip} est à jour.
- Applicable : non
- Pourquoi : La restriction d'origine réduit fortement l'exposition, mais une adresse devenue obsolète (ancien prestataire, IP dynamique) rouvre la porte.
- Vérifier : La liste des origines correspond aux accès réellement nécessaires.

## R-NET-11 · Hôte entièrement publié (NAT 1:1 ouvert)
- Quand : nat_whole_host
- Gravité : haute
- Action : Limiter le NAT 1:1 vers {private_ip} aux seuls ports utiles (règles « inbound ») et, si possible, aux origines connues.
- Applicable : non
- Pourquoi : Tous les ports de l'hôte deviennent joignables depuis Internet : chaque service qu'il écoute, même oublié, est exposé.
- Vérifier : Seuls les ports prévus répondent depuis l'extérieur.

## R-NET-12 · Service publié depuis la zone invité
- Quand : nat_to_guest
- Gravité : moyenne
- Action : Déplacer le service {private_ip} hors du VLAN {vlan} (zone invité) ou supprimer la publication.
- Applicable : non
- Pourquoi : Le réseau des invités héberge des appareils non maîtrisés ; y publier un service mélange l'exposition Internet et un réseau sans confiance.
- Vérifier : Plus aucune publication ne vise une adresse du VLAN invité.

## R-NET-13 · Publication vers une adresse inconnue
- Quand : nat_unknown_target
- Gravité : basse
- Action : Vérifier la cible {private_ip} : la mettre à jour ou supprimer la publication si le service n'existe plus.
- Applicable : non
- Pourquoi : Une publication orpheline peut se réactiver le jour où l'adresse est réattribuée à un autre appareil.
- Vérifier : Chaque publication vise un hôte connu d'un VLAN de la passerelle.

## R-NET-14 · SSID invité hors zone invité
- Quand : ssid_guest_not_isolated
- Gravité : moyenne
- Action : Mettre l'interface {interface} (VLAN {vlan}) en zone invité sur la passerelle, ou vérifier dans Nebula que les règles de sécurité interdisent l'accès des invités ({ssids}) aux réseaux internes.
- Applicable : non
- Pourquoi : Les règles de sécurité de la passerelle ne sont pas lisibles par l'API ; seule la zone invité garantit, de façon visible, l'isolation du réseau interne.
- Vérifier : Depuis le SSID invité, les adresses internes sont injoignables (test actif ssid-vlan-check) et l'anomalie disparaît.

## R-NET-15 · SSID non invité en zone invité
- Quand : guest_zone_mixed
- Gravité : basse
- Action : Déplacer le SSID {ssids} vers un VLAN hors zone invité si ses utilisateurs doivent joindre les ressources internes.
- Applicable : non
- Pourquoi : Les clients d'un VLAN en zone invité sont isolés comme des invités : imprimantes, partages et serveurs internes leur sont refusés.
- Vérifier : Les utilisateurs du SSID joignent les ressources attendues.
