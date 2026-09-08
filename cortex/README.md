# Cortex (livraison #462) — décloisonne, corrèle, relie, consolide

Première étape du découpage de `docs/analyse-supervision-unifiee.md`
(#461) : un modèle commun et une file d'incidents corrélés, **totalement
transparents** — chaque hypothèse porte sa confiance, ses preuves et le
principe (parti pris) qu'elle applique, et chaque principe est évalué par
les retours humains.

## Modèle commun (`cortex-api`, SQLite)

- **entités** consolidées : clé stable `mac:` > `ip:` > `name:` ; les clés
  secondaires sont absorbées (`alias_map`, principes `identity-*`) ; type,
  nom, IP, MAC, site, origines (quelle source, quel identifiant), indices
  de rôle ;
- **relations** : `gateway_of` (route par défaut vue par un agent),
  `powers_site` (onduleur d'un site), `neighbor`, `talks_to`, `flow`
  (network-agent), `watches` (sonde) — chacune avec poids, principe,
  preuve et source ;
- **événements normalisés** : `{empreinte, source, type, sévérité, entité,
  site, message, référence brute, état open/acked/closed, premier/dernier,
  compteur}` — un événement répété est rafraîchi, jamais dupliqué ; une
  source lue avec succès qui ne le remonte plus le ferme ;
- **incidents** : regroupement par fenêtre glissante (`CORTEX_WINDOW_SECONDS`,
  300) + relation partagée, ou même entité, ou (faiblement) même site ;
  cause racine = entité la plus en **amont** (passerelle, onduleur) ;
  hypothèses, sévérité = pire événement, état (ouvert / acquitté / clos)
  conservé d'une collecte à l'autre ;
- **retours** (`feedback`) par principe et **journal des collectes**
  (`runs`) : quelle source a répondu, en combien de temps, ce qui en est
  sorti.

Sources lues (API internes, rien de modifié chez elles) : si-agent
(flotte, netviews, événements récents, état de la flotte), vigilance,
UPS, orchestrateur, netprobe, network-agent, sauvegardes du hub.
Collecte toutes les `CORTEX_INTERVAL_SECONDS` (300) et à la demande
(`POST /collect`, droit `manage` si `CORTEX_RIGHTS_API_URL`).

## Principes (partis pris) — `cortex/api/principles.py`

Quatorze principes nommés, chacun avec sa confiance de base, son énoncé et
sa limite connue : identité (IP, MAC, nom), relations (passerelle, relais,
port servi → rôle, même site, onduleur du site, sonde), causalité (amont
d'abord, fenêtre + relation, regroupement par site, événement isolé),
présentation (sévérité max). La confiance **mesurée** d'un principe
intègre les retours « juste / fausse » donnés sur les hypothèses qui s'en
réclament (lissage : la base vaut quatre retours). La confiance d'un
incident est celle de son hypothèse causale — jamais un maximum flatteur.

## Routes

`/status`, `POST /collect`, `/principles`, `/runs`, `/stats?days=`,
`/entities?q=`, `/entities/<clé>` (rôles pondérés, relations, événements),
`/relations?entity=`, `/events?state&severity&since&entity`,
`POST /events/<empreinte>/ack|close`, `/incidents?state=`,
`/incidents/<clé>` (détail : hypothèses, entités, relations, événements),
`POST /incidents/<clé>/ack|close`, `POST /incidents/<clé>/feedback
{principle, verdict}`.

## Tuile

Thématique Supervision, premier onglet : incidents (cause proposée,
confiance en mots et en %, détail avec hypothèses votables, entités,
relations utilisées, événements), entités (rôles pondérés, origines),
événements ouverts, principes & évaluations, statistiques (par source,
sévérité, jour, entités bruyantes, principes appliqués), collecte.

## Vérifié

10 tests purs (principes, normalisation de chaque source, alias et fusion,
rôles pondérés, cause racine passerelle et onduleur, fenêtre, regroupement
faible, retour humain qui baisse la confiance, statistiques) ; API réelle
contre le central si-agent de l'environnement + UPS et vigilance simulés :
un onduleur sur batterie et un agent du même site hors ligne forment **un**
incident dont la cause proposée est l'onduleur (confiance annoncée faible,
22 %, parce que le lien onduleur → site n'est qu'une supposition) ; un
signal vigilance et un agent portant la même IP sont consolidés en une
entité (3 alias) ; acquittement, clôture, retour humain (la confiance
mesurée baisse), 6 onglets rendus sous Chromium ; 166 tests Node.
**Non vérifié** : la collecte contre les vraies API sur « super »
(network-agent en réseau hôte, netprobe, orchestrateur).

## Suite (découpage #461)

2. rôles pondérés enrichis (OUI, IPAM/Nebula, classification), table de
routes, graphe d'architecture persistant, « ce qui a changé » ; 3. lieux
et positions avec provenance, fiche d'intervention, couches carto ;
4. séquences apprises et anticipation, dérives ; 5. MTTA/MTTR, politiques
d'alerte, notifications par incident.
