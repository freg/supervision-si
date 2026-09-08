# -*- coding: utf-8 -*-
"""Les PARTIS PRIS de Cortex (livraison #462) -- chaque hypothèse produite
par le moteur s'appuie sur un de ces principes, nommé, avec sa confiance de
base et sa justification. Demandé : « totalement transparent en
présentant des évaluations pour chaque hypothèse et parti pris ». Le
retour humain (confirmé / rejeté) est compté par principe : l'évaluation
affichée dans la tuile est donc une mesure, pas une promesse.

Un principe = {id, titre, énoncé, confiance de base (0-1), portée,
limite connue}. Les collecteurs et le corrélateur ne font référence qu'à
ces identifiants ; ajouter un principe ici, c'est l'exposer tel quel.
"""

PRINCIPLES = {
    # -- identité / consolidation --------------------------------------
    "identity-ip": {"title": "Même IP = même entité", "base": 0.9, "scope": "consolidation",
                    "statement": "Deux sources qui parlent de la même adresse IP (hors boucle locale) désignent la même entité.",
                    "limit": "faux si DHCP réattribue l'adresse ou en cas de NAT ; la MAC prime quand elle est connue."},
    "identity-mac": {"title": "Même MAC = même entité", "base": 0.97, "scope": "consolidation",
                     "statement": "Une adresse MAC unicast identifie un équipement, quel que soit le segment où on la voit.",
                     "limit": "MAC aléatoires (WiFi privé) et virtualisation (MAC clonées)."},
    "identity-name": {"title": "Même nom d'hôte = même entité", "base": 0.7, "scope": "consolidation",
                      "statement": "Un nom d'hôte (agent, DNS inverse, cible) commun rapproche deux entités sans IP commune.",
                      "limit": "noms génériques (localhost, pc, serveur) exclus ; homonymes entre sites."},
    # -- relations -------------------------------------------------------
    "gateway-of": {"title": "La passerelle par défaut d'un hôte est en amont de lui", "base": 0.85, "scope": "relation",
                   "statement": "Ce qu'un agent hôte déclare comme passerelle par défaut (ip route) conditionne sa joignabilité.",
                   "limit": "routes multiples ou VPN : seule la route par défaut est prise."},
    "relay-gateway": {"title": "Un appareil qui relaie vers l'extérieur est une passerelle", "base": 0.6, "scope": "rôle",
                      "statement": "network-agent voit un appareil relayer des paquets hors de son sous-réseau : passerelle probable (NAT/routeur).",
                      "limit": "un proxy applicatif ou un serveur très sollicité peut ressembler à un relais."},
    "serves-port": {"title": "Un port servi révèle un rôle", "base": 0.65, "scope": "rôle",
                    "statement": "53 → DNS, 67 → DHCP, 161 → équipement manageable SNMP, 9100/631 → imprimante, 3306/5432 → base de données, 443/80 → serveur web.",
                    "limit": "le port ne dit pas la fonction réelle (443 d'un NAS, 53 d'un routeur domestique)."},
    "same-site": {"title": "Un même site partage une infrastructure", "base": 0.4, "scope": "relation",
                  "statement": "Deux entités du même site déclaré dépendent probablement des mêmes liaisons, alimentation et passerelle.",
                  "limit": "relation faible : ne sert qu'à regrouper, jamais à désigner seule une cause."},
    "ups-powers-site": {"title": "Un onduleur alimente les équipements de son site", "base": 0.5, "scope": "relation",
                        "statement": "Sans câblage déclaré, l'onduleur d'un site est supposé alimenter les hôtes et équipements de ce site.",
                        "limit": "à remplacer par une relation déclarée dès qu'elle existe (baie, prise)."},
    "probe-watches": {"title": "Une sonde observe sa cible", "base": 0.95, "scope": "relation",
                      "statement": "Une cible netprobe (ping, nmap) est reliée à l'équipement qu'elle vise ; sa perte ne concerne que lui.",
                      "limit": "une sonde silencieuse (agent WiFi) peut être elle-même en défaut."},
    "oui-vendor": {"title": "Le constructeur (OUI de la MAC) suggère la famille d'équipement", "base": 0.55, "scope": "rôle",
                   "statement": "Les trois premiers octets d'une MAC désignent un constructeur ; certains ne font que des équipements réseau, des imprimantes ou des VM.",
                   "limit": "table réduite aux constructeurs courants ; un constructeur généraliste (Intel, Dell) ne dit rien."},
    "name-class": {"title": "La classification du nom d'hôte donne un rôle", "base": 0.6, "scope": "rôle",
                   "statement": "classifier-api range un nom d'hôte dans une catégorie (dictionnaires, retour humain) ; une catégorie confirmée vaut plus.",
                   "limit": "dépend de la discipline de nommage ; un nom trompeur trompe."},
    "referential": {"title": "Un référentiel déclaré fait foi", "base": 0.9, "scope": "rôle",
                    "statement": "Nebula (type d'appareil, site, client attaché) et IPAM (nom, description) sont des déclarations d'administrateur, pas des déductions.",
                    "limit": "un import ancien peut être périmé (dernier import daté)."},
    "attached-to": {"title": "Un client WiFi dépend de sa borne", "base": 0.85, "scope": "relation",
                    "statement": "Nebula dit à quelle borne / quel switch un client est attaché : cet équipement est en amont du client.",
                    "limit": "le client peut avoir changé de borne depuis l'import."},
    "route-known": {"title": "Une route déclarée par un hôte est un chemin réel", "base": 0.9, "scope": "relation",
                    "statement": "Les tables de routage relevées par les agents (ip route) décrivent les chemins de sortie effectifs de chaque hôte.",
                    "limit": "VPN et routes par stratégie ne sont pas vus."},
    "change-since": {"title": "Ce qui apparaît ou disparaît entre deux collectes est un changement", "base": 0.8, "scope": "présentation",
                     "statement": "Nouvelle entité, entité plus vue, relation nouvelle ou disparue, rôle qui bascule, passerelle qui change : signalés tels quels.",
                     "limit": "une source injoignable fait « disparaître » ses entités -- ces disparitions sont ignorées quand la source a échoué."},
    # -- positions (étape 3, #464) ----------------------------------------
    "pos-declared": {"title": "Une coordonnée portée par l'appareil fait foi", "base": 0.95, "scope": "position",
                     "statement": "Quand network-agent (ou un référentiel) donne une latitude / longitude à l'appareil, c'est sa position.",
                     "limit": "saisie humaine : une faute de frappe met l'appareil dans l'océan (0,0 rejeté, pas le reste)."},
    "pos-validated": {"title": "Une correspondance validée par une personne fait foi", "base": 0.9, "scope": "position",
                      "statement": "Une correspondance nom → localisation validée ou saisie à la main (pixel-grid, geo-catalog) l'emporte sur toute déduction.",
                      "limit": "validée un jour, pas forcément encore vraie (déménagement)."},
    "pos-place": {"title": "Une entité est où est son lieu déclaré", "base": 0.85, "scope": "position",
                  "statement": "Le lieu déclaré le plus précis (salle > bâtiment > site) donne la position de l'entité ; un site textuel suffit s'il est positionné.",
                  "limit": "précision du lieu : un site de 3 ha positionne à 100 m près."},
    "place-hierarchy": {"title": "Un lieu sans coordonnées hérite de son parent", "base": 0.9, "scope": "position",
                        "statement": "Une salle sans coordonnées est au bâtiment ; un bâtiment sans coordonnées est au site.",
                        "limit": "perd la précision fine ; signalé (« hérité de »)."},
    "pos-geolocation": {"title": "La table des géolocalisations positionne par nom ou par IP", "base": 0.8, "scope": "position",
                        "statement": "Une entrée de la table des géolocalisations dont le nom est celui de l'entité ou son IP la positionne.",
                        "limit": "homonymes ; une IP DHCP peut changer d'hôte."},
    "pos-resolved-name": {"title": "Une correspondance automatique de nom est une bonne piste", "base": 0.6, "scope": "position",
                          "statement": "La résolution nom → localisation de pixel-grid (alias, équivalences, similarité ≥ 0,75) positionne, en attente de validation.",
                          "limit": "faux amis (Annexe-Nord ≠ Annexe Nord-Ouest) ; à valider dans la file."},
    "pos-propagated": {"title": "Une entité est où est ce dont elle dépend", "base": 0.7, "scope": "position",
                       "statement": "Un client WiFi est à sa borne ; un hôte sans position est à sa passerelle si elle est du même site ; un onduleur est avec ce qu'il alimente.",
                       "limit": "un hôte distant (VPN) passe par une passerelle qui n'est pas près de lui : d'où la condition « même site »."},
    "pos-neighbor": {"title": "Sans mieux, une entité est près de ses voisins", "base": 0.5, "scope": "position",
                     "statement": "Moyenne pondérée (par le poids des liens) des voisins positionnés, profondeur ≤ 3, chaîne conservée ; la confiance baisse avec la profondeur.",
                     "limit": "un voisin de flux peut être à l'autre bout du pays (serveur central) ; ne sert qu'à afficher, jamais à intervenir."},
    "pos-fallback": {"title": "La position de repli n'est pas une position", "base": 0.1, "scope": "position",
                     "statement": "Une entité qu'aucun barreau n'a positionnée prend la position de repli (__default__) pour rester visible, et entre dans la file de travail.",
                     "limit": "—"},
    "unsupervised": {"title": "Vue par la découverte seule = non supervisée", "base": 0.8, "scope": "présentation",
                     "statement": "Une entité que seules la découverte réseau, Nebula, IPAM ou la classification connaissent n'a ni agent, ni sonde, ni relevé : elle est signalée comme non supervisée.",
                     "limit": "un équipement passif (switch non manageable) n'a rien à superviser ; à exclure à la main."},
    # -- apprentissage / anticipation / signaux faibles (étape 4, #465) ----
    "sequence-learned": {"title": "Une séquence fréquente est une règle proposée", "base": 0.6, "scope": "causalité",
                         "statement": "Quand B suit A dans la fenêtre bien plus souvent que le hasard (support ≥ 3, confiance ≥ 0,5, ≥ 2 × l'attendu), « A précède B » est proposé comme règle, à confirmer.",
                         "limit": "corrélation, pas causalité : une cause commune non vue produit la même séquence ; d'où l'état « proposée »."},
    "sequence-confirmed": {"title": "Une règle confirmée par une personne fait foi", "base": 0.9, "scope": "causalité",
                           "statement": "Une règle A → B confirmée sert à regrouper, à désigner la cause et à annoncer ; rejetée, elle est ignorée.",
                           "limit": "confirmée un jour ; ses annonces jugées (juste / fausse) la remesurent."},
    "anticipation": {"title": "Quand A survient, annoncer B", "base": 0.7, "scope": "causalité",
                     "statement": "Si A est ouvert et qu'une règle A → B existe, Cortex annonce « B suit habituellement dans n min (x fois sur n) » tant que B n'est pas là ; l'annonce est ensuite jugée.",
                     "limit": "une annonce n'est pas un événement : rien n'est ouvert à sa place, elle est affichée avec sa confiance."},
    "drift-zscore": {"title": "Un écart de plusieurs sigmas à la dernière heure est un signal faible", "base": 0.6, "scope": "signal faible",
                     "statement": "Sur une mesure (CPU, mémoire, disque, latence, charge, tension…), la moyenne de la dernière heure comparée aux 24 h précédentes ; ≥ 3 σ = avertissement, ≥ 5 σ = critique.",
                     "limit": "une série plate a un σ minuscule : tout écart devient « énorme » (σ plancher 2 %) ; un redémarrage crée un faux écart."},
    "drift-trend": {"title": "Une tendance vers un seuil se signale avant le seuil", "base": 0.65, "scope": "signal faible",
                    "statement": "Régression linéaire sur 24 h ; si la droite atteint le seuil (disque 90 %, batterie 30 %…) dans moins de 7 jours, l'échéance est annoncée.",
                    "limit": "linéaire : un remplissage par paliers ou une purge programmée ne sont pas vus."},
    "seasonality": {"title": "Inhabituel pour l'heure = à surveiller", "base": 0.5, "scope": "signal faible",
                    "statement": "La dernière heure comparée au même créneau (±1 h) des jours précédents ; signale ce qui sort de l'habitude horaire sans dépasser un seuil.",
                    "limit": "il faut plusieurs jours d'historique ; week-end et jours fériés ne sont pas distingués."},
    # -- causalité -------------------------------------------------------
    "upstream-first": {"title": "La cause est l'entité la plus en amont", "base": 0.75, "scope": "causalité",
                       "statement": "Dans un groupe d'événements liés, l'entité dont dépendent les autres (passerelle, onduleur, liaison) est proposée comme cause racine.",
                       "limit": "ne voit pas une cause hors du graphe connu (panne électrique générale, opérateur)."},
    "window-cluster": {"title": "Des événements proches et reliés forment un incident", "base": 0.7, "scope": "causalité",
                       "statement": "Des événements ouverts dans une même fenêtre (5 min par défaut) et reliés par au moins une relation sont un seul incident.",
                       "limit": "une fenêtre trop large fusionne des pannes indépendantes ; trop courte les sépare."},
    "site-cluster": {"title": "Sans relation connue, la simultanéité sur un site suffit à regrouper", "base": 0.35, "scope": "causalité",
                     "statement": "Des événements simultanés d'un même site sans relation explicite sont regroupés, avec une confiance faible.",
                     "limit": "coïncidence possible ; l'incident est marqué « regroupement faible »."},
    "severity-max": {"title": "Un incident a la sévérité de son pire événement", "base": 1.0, "scope": "présentation",
                     "statement": "La sévérité d'un incident est le maximum de celles de ses événements ; l'accusé ne la change pas.",
                     "limit": "—"},
    "single-event": {"title": "Un événement isolé est un incident à lui seul", "base": 0.9, "scope": "causalité",
                     "statement": "Un événement ouvert sans voisin dans la fenêtre devient un incident d'une seule entité, cause = l'entité elle-même.",
                     "limit": "—"},
}


def describe(pid):
    p = PRINCIPLES.get(pid)
    return {"id": pid, **p} if p else {"id": pid, "title": pid, "base": 0.5, "scope": "?", "statement": "", "limit": ""}


def evaluate(pid, feedback_counts):
    """Évaluation mesurée d'un principe : confiance de base ajustée par le
    retour humain (confirmés / rejetés). -> {base, confirmed, rejected,
    applied, measured} ; measured = None tant qu'il n'y a pas de retour."""
    p = describe(pid)
    fc = feedback_counts.get(pid, {}) if feedback_counts else {}
    confirmed, rejected, applied = fc.get("confirmed", 0), fc.get("rejected", 0), fc.get("applied", 0)
    measured = None
    if confirmed + rejected > 0:
        # lissage bayésien simple : la base compte pour 4 retours
        measured = round((p["base"] * 4 + confirmed) / (4 + confirmed + rejected), 3)
    return {**p, "confirmed": confirmed, "rejected": rejected, "applied": applied, "measured": measured,
            "effective": measured if measured is not None else p["base"]}
