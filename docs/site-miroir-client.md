# Site miroir pour un client (Numeria) — analyse et plan (25 sept. 2026)

Demande : « pour les clients (Numeria pour le moment) il faut un site
miroir, soit en interne et potentiellement autonome, soit projeté par
supervision.optline.fr ».

## 1. Deux formes, complémentaires

| | A. Projeté (supervision.optline.fr) | B. Miroir interne autonome |
|---|---|---|
| Où tourne le hub | sur super, un seul déploiement | sur une VM du client (son Proxmox, déjà joint par le bastion #583) |
| Ce que voit le client | `numeria.supervision.optline.fr` : le hub, restreint à **son site** et à **ses tuiles** | le même hub, chez lui, sur son LAN |
| Si Internet ou super tombe | plus rien | continue : les agents du site parlent au miroir |
| Données | celles du hub central, filtrées | celles du site, **remontées** au central quand le lien est là |
| Coût de mise en place | faible : frontal (#471) + groupe + matrice des droits + filtre de site | moyen : cohorte « site » du compose + fédération miroir → central |
| Risque | un filtre oublié = données d'un autre client visibles | deux annuaires, deux séries de mises à jour |

Les deux se complètent : A tout de suite pour la démo et le suivi
quotidien ; B pour un client qui veut l'autonomie (Numeria : campus, Wi-Fi,
robots — la supervision doit vivre sans Internet).

## 2. Ce qui existe déjà et sert tel quel

- Frontal public Apache + certbot (#471, mode réécriture) : un **vhost par
  client** (`numeria.supervision.optline.fr`) vers la même passerelle.
- Matrice des droits tuiles × groupes (#559) : un groupe Keycloak
  `site-numeria` ne voit que Aujourd'hui, Supervision SI, Nebula, Sondes,
  Agents hôtes, Redirections NAT, Demandes… — jamais coffres, comptes, tour.
- Filtre `?site=` sur la plupart des API (agents, netprobe, licences,
  MikroTik, Cisco, Nebula) et sélecteur de site dans les tuiles.
- Comptes de démonstration (#608) : les personnes du client peuvent être
  des comptes Keycloak locaux, sans toucher au LDAP.
- Cohortes de déploiement (`deploy/cohorts.json`, #529) : core /
  supervision / tickets — la base d'une cohorte « site ».
- si-agent : un agent parle à **un** central ; l'URL du central est dans sa
  configuration (`--central`), donc un agent de site peut viser le miroir.

## 3. Ce qui manque

### A — projeté

1. **Périmètre de site imposé par le groupe** (nouveau, petit) : dans les
   app-settings du hub, une table `groupe Keycloak → site(s)` ; à la
   connexion, si la personne n'est que dans des groupes « à périmètre », le
   hub verrouille le sélecteur de site et ajoute `?site=` à tous les appels
   (`siteScope` dans les clients d'API). Les API vérifient aussi côté
   serveur : le jeton porte `groups`, `si-proxy/admin/auth.py` sait déjà le
   lire → une garde commune `site_scope(groups)` refuse un `?site=` hors
   périmètre. C'est le point de sécurité : jamais un filtre seulement
   côté navigateur.
2. **Habillage par client** (facultatif) : nom, logo, couleur d'accent lus
   dans l'app-setting du site (`branding`) selon le vhost d'entrée
   (`X-Forwarded-Host`).
3. **Vhost** : une ligne dans `scripts/front-reverse-proxy.sh`
   (`--client numeria`), certificat inclus.

### B — miroir autonome

1. **Cohorte « site »** : hub + tls-proxy + keycloak (comptes locaux ou
   fédération vers le LDAP central par le bastion) + si-agent-api +
   netprobe + nebula + notify + licences (le client en a besoin) ; sans
   tour de contrôle des livraisons du central, sans coffres partagés.
2. **Fédération miroir → central** (nouveau module `federation`) : le
   miroir pousse périodiquement vers super, par HTTPS et jeton de
   consommateur (mécanisme des consommateurs externes de notify #590) :
   flotte et mesures résumées des agents, événements, état Nebula,
   redirections NAT, journal. Le central affiche le site comme
   « distant » (origine, dernière synchronisation, retard). Rien ne
   transite en direct hors 178.217.95.134 : le miroir sort par le routeur
   du client vers l'entrée HTTPS du hub, comme un agent.
3. **Sens central → miroir** : livraisons (zip signé) et configurations
   par la tour de contrôle, via le shim host du site (#575) — le miroir est
   une cible de déploiement comme les autres.
4. **Identité** : mode 1 (simple) comptes Keycloak locaux du miroir (les
   personnes du client) ; mode 2 fédération LDAP du miroir vers l'annuaire
   central par le bastion, avec cache de session pour tenir sans lien.

### Constat du 25 sept. (avant A1) — prérequis A0

Vérifié dans le code : seules licenses-api, notify-api et services-api
vérifient le jeton Keycloak, et uniquement sur les écritures. **Toutes les
lectures de toutes les API passent sans jeton** derrière la passerelle
(modèle « LAN de confiance »). Depuis l'exposition publique du hub
(supervision.optline.fr, 25 sept.), c'est une faiblesse en soi, et un
périmètre de site imposé côté navigateur seul serait contournable en
appelant l'API directement. D'où :

- **A0 — lectures authentifiées** (prérequis) : garde commune
  `shared/api_guard.py` (dérivée de `si-proxy/admin/auth.py`) en
  `before_request` sur chaque API : jeton exigé sur tout sauf `/health`,
  `/version` et les routes des agents / sondes (secret propre) ; `g.user`
  avec `groups`. Côté hub : envoyer `Authorization: Bearer` dans tous les
  clients JS (trois le font déjà). Non-régression : agents, sondes,
  keycloak-backup, licenses → si-agent, scripts hôte.
- **Mesure conservatoire** sur le frontal public, sans toucher aux API :
  refuser `/api/` aux requêtes sans en-tête `Authorization: Bearer`
  (`RewriteCond %{HTTP:Authorization} !^Bearer`), ce qui ferme les lectures
  anonymes depuis Internet ; les vues dont le client n'envoie pas encore le
  jeton cessent de fonctionner depuis l'extérieur jusqu'à A0 (liste = ce
  qu'A0 doit traiter).
- **Fait en #615, à la frontière** : mod_auth_openidc sur le frontal (voir
  docs/acces-public-frontal.md § 2 bis) + intercepteur hub. La garde
  par API (`g.user`, périmètre de site A1) reste à faire pour le LAN et
  pour A1.
- A1 s'appuie ensuite sur la même garde (`site_scope(groups)`).

## 4. Ordre proposé

0. **A0** (lectures authentifiées) — voir constat ci-dessus.
1. **A1 + A3** (une livraison) : périmètre de site par groupe (hub + garde
   d'API), vhost `numeria.supervision.optline.fr`, groupe `site-numeria`,
   matrice des droits réglée, comptes de démo → démo Numeria possible.
2. **A2** (petite) : habillage par client.
3. **B1 + B2** (chantier) : cohorte « site » et fédération ; premier miroir
   sur le Proxmox Numeria (VM déjà joignable par le bastion), agents du
   campus repointés vers le miroir, central alimenté par fédération.
4. **B3 / B4** ensuite.

Mesure de succès : depuis Internet, un compte `site-numeria` ne peut lire
que Numeria (vérifié par les tests de garde) ; le miroir coupé d'Internet
continue d'alerter sur le LAN du campus.
