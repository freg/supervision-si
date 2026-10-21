# Veille cyber, impacts et couverture du SI — cadrage (BACKLOG 130)

But : savoir **vite** ce qui se passe (alertes, vulnérabilités, nouvelles normes), **ce que ça touche chez nous**, et
**ce que nous ne voyons pas** de notre propre SI. Trois publics, une même source de vérité : RSSI (risque, décisions),
développeurs (dépendances, pratiques), administrateurs systèmes et réseau (correctifs, configuration).

## Ce qui existe déjà et sera réutilisé

| Brique | Apport |
|---|---|
| `vuln/` (#688) | SBOM (syft), OSV, EPSS, KEV, Dependency-Track, priorités P1-P4 par actif — le moteur des impacts logiciels |
| agents + `software-inventory` | inventaire logiciel des hôtes et postes |
| `network-equipment/`, Cisco, MikroTik, Nebula | modèles et micrologiciels des équipements |
| fusion IP/MAC, exploration réseau, netprobe, sondes radio | ce qui est **vu** sur le réseau (IP, MAC, ports, protocoles) |
| `service-watch/`, Infos synthèse SI, DNS | les services exposés et ce que nous **déclarons** |
| `rsyslog-listener`, `app-logwatch`, `mail-server` | les journaux réellement collectés |
| `notify-api` (#590) | groupes et méta-groupes de destinataires, envoi détaché, push (#796) |
| assistant IA local (Ollama) | résumés et explications en français, sans envoyer nos données dehors |

## Sources (ouvertes, sans abonnement payant)

- **Alertes et avis** : CERT-FR (alertes, avis, actualités — RSS), CISA KEV (déjà chargé), CERT-EU, ANSSI (publications).
- **Vulnérabilités** : NVD CVE API 2.0 (nouveautés et modifications), OSV et EPSS (déjà), avis GitHub (via OSV).
- **Systèmes du parc** : Debian DSA/DLA, Ubuntu USN, Proxmox, Microsoft MSRC (API CVRF).
- **Constructeurs du parc** : Cisco PSIRT, MikroTik, Zyxel, Teltonika — limités aux modèles que nous possédons.
- **Normes** : RFC Editor (nouvelles RFC, errata), groupes IETF suivis (TLS, DNSOP, OPSEC, OAUTH…), avis de dépréciation.
- **« Ce que je ne connais pas »** : chaque élément reçoit une fiche d'explication (de quoi s'agit-il, pourquoi c'est
  important, pour qui) générée par l'IA locale, relue au besoin, et un glossaire qui grandit avec la veille.

## Chaîne

1. **Collecte** (module `veille/`, service `veille-api`) : un collecteur par source (RSS/Atom/JSON/API), relève
   planifiée, normalisation `{id, source, date, titre, résumé, CVE, produits (CPE / noms), gravité, liens}`,
   dédoublonnage par CVE et par lien.
2. **Enrichissement** : CVSS, EPSS, KEV (moteur `vuln`), catégorie (vulnérabilité, campagne, norme, bonne pratique),
   public(s) concernés, fiche d'explication en français.
3. **Rapprochement avec notre SI** : produits et versions de l'inventaire (SBOM, logiciels des agents, micrologiciels
   des équipements, systèmes des VM / CT, services exposés) → « impacte : 3 hôtes, 1 routeur, le service X ».
4. **Diffusion** par public via notify-api : alerte immédiate si exploitée activement **et** présente chez nous ;
   synthèse quotidienne (admins), hebdomadaire (RSSI, développeurs) ; lien vers la fiche dans le hub ; lu / à traiter
   / traité / non applicable, avec qui et quand (traçabilité pour le RSSI).

## Les trois pages

1. **Veille cyber — dernières infos** : fil filtrable (public, source, gravité, « nous concerne »), fiche de chaque
   élément (résumé, explication, liens, impacts), statut de traitement, recherche plein texte, glossaire.
2. **Impacts sur notre SI** : par actif (hôte, VM, équipement, service, application) les vulnérabilités ouvertes et
   avis applicables, triés par priorité (P1-P4 de `vuln`), avec l'action attendue (mise à jour, contournement,
   surveillance) et son responsable ; vue inverse « cette alerte touche… ».
3. **Couverture du SI** : tous les actifs connus, fusionnés — vus sur le réseau (IP, MAC, constructeur, ports et
   protocoles), déclarés (services, DNS, IPAM), inventoriés — croisés avec les couches de surveillance (agent, SBOM,
   sondes de service, journaux collectés, sauvegarde, inventaire constructeur). Matrice actifs × couches, score de
   couverture, et surtout la liste des **trous** : « vu sur le réseau, sans agent ni journal », « service exposé sans
   sonde », « équipement sans inventaire de micrologiciel ».

## Tranches proposées

| Tranche | Contenu |
|---|---|
| T1 | `veille-api` + sources CERT-FR, KEV, NVD, RFC Editor ; tuile « Veille cyber » (fil, fiche, statuts) ; synthèse quotidienne par notify-api |
| T2 | Rapprochement avec l'inventaire (vuln, logiciels des agents, équipements) ; page « Impacts » ; alerte immédiate KEV + présent |
| T3 | Page « Couverture » : fusion des découvertes réseau et des actifs connus, matrice des couches, trous |
| T4 | Fiches d'explication et glossaire par l'IA locale, résumés par public |
| T5 | Sources constructeurs et systèmes du parc (Cisco, MikroTik, Zyxel, Proxmox, Debian, Microsoft) |

## Choix à valider

- Destinataires de chaque public (groupes notify-api) et rythme des synthèses.
- Sources prioritaires au-delà de T1 ; groupes IETF à suivre.
- Durée de conservation du fil (proposé : 2 ans, fiches traitées gardées pour l'historique RSSI).

## Livré (#814, T1 et T2)

Dans **vuln-api** (pas de nouveau service) : `vuln/veillelib.py` (pur), `vuln/veille.py` (routes `/veille`, relève en
tâche de fond), tuile « Veille cyber » (`hub/src/VeilleView.jsx`).

- Relève des 18 sources ouvertes (dont KEV) ; tables alertes / IA cyber / générales / France-Europe / règlements.
- Impacts : CVE des articles × constats de vuln-api (actifs, priorité P1-P4, EPSS, KEV) ; onglet « Impacts SI » et
  vue par actif. Le rapprochement par **nom de produit et version** (composants des SBOM, sans CVE) reste à faire.
- Publics RSSI / administrateurs / développeurs (règles dans `veillelib.publics`) ; suivi de traitement et journal.
- Diffusion notify-api : `veille.alerte-si` (immédiate, une fois par article), `veille.quotidienne-<public>` à
  `VEILLE_SYNTHESE_HEURE`. Les groupes destinataires se règlent dans la tuile Notifications.
- Préfiltres (python, php, linux, bsd, mikrotik + nos modèles, gardés en base), filtres enregistrés, extraction
  CSV / Markdown / JSON / Atom, IA locale (explication, synthèse).
- Même logique que la tuile « Cyber news » du hub maison (dépôt séparé), où elle sert aussi de banc d'essai des modèles.

Restent : T3 (Couverture), T4 (fiches et glossaire), T5 (sources constructeurs et systèmes du parc).
