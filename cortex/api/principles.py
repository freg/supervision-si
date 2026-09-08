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
