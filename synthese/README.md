# Infos synthèse SI (livraison #523)

Demande : « présenter la synthèse DNS / IP OVH / IPAM dans une page “infos
synthèse SI” de la tuile documentation, la rendre interactive pour accéder
aux équipements, outils et autres ; maintien automatique ; liens vers ipam,
la gestion des IP OVH, les zones DNS, Online ».

## Principe

`synthese/generate.py` lit les **exports** déposés dans `synthese/data/`
(**hors dépôt** : ce sont des données réelles -- noms de domaine, adresses
publiques, équipements) et écrit `synthese/generated/synthese.json` (hors
dépôt aussi). `prefs-api` le sert tel quel (`GET /synthese`) et la vue du hub
« Infos synthèse SI » (Documents & ENT) le rend interactif : recherche
transversale, recoupement par adresse (« à quoi sert cette IP ? » : noms DNS,
bloc OVH, service, hôte IPAM, équipement), liens vers IPAM, la gestion des IP
et des zones OVH, la console Online, les outils du hub (équipements réseau,
exploration), échéances des services OVH (alerte à 60 jours).

Les sources sont reconnues par leur **contenu**, jamais par le nom de la
feuille -- un classeur `.xlsx` (une feuille par source), des `.csv`, des
dumps de zone `.txt` :

| source | reconnue par |
|---|---|
| dump de zone BIND (OVH, Online) | `$ORIGIN <zone>.` puis `nom ttl IN TYPE valeur [note]` |
| blocs d'IP OVH | en-tête « Bloc d'IP / Correspondances DNS / Version / Type / Pays / Service attaché » |
| services OVH (renouvellements) | en-tête « Service / Type / Statut / Renouvellement / Date d'effet » |
| sous-réseau IPAM (phpipam, export) | titre, CIDR, « vlan: … », en-tête « ip address / hostname / … » |
| équipements IPAM | lignes « nom ; IP ; … ; N Objects ; type ; constructeur ; modèle » |

`synthese/data/links.json` (facultatif) : `{"ipam_url": "https://…/"}` pour
les liens vers votre phpipam ; les gabarits OVH / Online ont des valeurs par
défaut (`DEFAULT_LINKS` dans generate.py) et peuvent y être redéfinis.
`synthese/data.example/` est un jeu **fictif** (RFC 5737) pour les tests.

## Mise en place

```
mkdir -p synthese/data && cp ~/exports/affectations.xlsx synthese/data/
echo '{"ipam_url": "https://ipam.exemple.fr/"}' > synthese/data/links.json
pip install openpyxl            # lecture des .xlsx (les .csv/.txt n'en ont pas besoin)
scripts/synthese-si.sh          # -> synthese/generated/synthese.json
```

Maintien automatique : `crontab -e` → `15 6 * * * /chemin/supervision-si/scripts/synthese-si.sh`
après avoir mis en place l'export régulier des sources (zone dumps par l'API
OVH / Online, export IPAM) dans `synthese/data/` -- ou en déposant
simplement un nouveau classeur. Le hub relit le fichier à chaque ouverture de
la page : rien à redémarrer.

## Suites (backlog)

Tirer directement les sources sans passer par des exports : zones et IP par
les API OVH et Online (jetons dans le coffre des accès), sous-réseaux et
équipements par `ipam-api` ; comparer deux générations (IP apparues /
disparues) ; ouvrir la fiche d'un équipement depuis la synthèse (paramètre
`ip` sur la vue Équipements réseau).
