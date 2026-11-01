# service-watch — entrées de services vues d'Internet (livraison #531, backlog item 80)

Ce qu'un utilisateur d'Internet voit de nos services, mesuré depuis le
central, et ce qui traverse réellement (canaris). Page servie sous
`/service-watch/` (tls-proxy), tuile « Entrées de services » de la
thématique Supervision.

## Ce que fait un passage (toutes les `SERVICE_WATCH_INTERVAL_MINUTES`, 10 par défaut)

Pour chaque entrée active :

1. **DNS** : résolution du nom (non résolu = trou DNS ou zone modifiée) ;
2. **ports** : TCP 80/443/25/465/587/993/22 + ceux déclarés ; ports attendus fermés = critique ;
3. **TLS** (443) : émetteur, SAN, jours restants (avertissement ≤ 21 j, expiré ou nom absent = critique) ;
4. **HTTP** : statut, URL finale (redirection hors du nom attendu), titre, serveur, délai, **page d'hébergeur** (parking, page par défaut, en construction, suspendu) ;
5. **scénario** (optionnel) : pas HTTP déclaratifs, connexion avec un **compte de test du coffre** (`credentials-api`, genre `http`, désigné par son nom — jamais un mot de passe dans le registre ni dans les résultats) ;
6. **contenu** : texte visible normalisé (dates, heures, nombres, hachages et motifs `masks` remplacés) → empreinte ; première mesure = référence ; changement ≥ `diff_threshold_pct` (30 %) = « contenu modifié » avec la différence mot à mot ; bouton **Valider comme référence** (déploiement légitime, journalisé) ;
7. **classement** : web / mail / ged / ssh / autre / silencieux ; changement de classe signalé.

Constats → événements → notifications (`SECRETS_ALERT_*` : courriel dès `warning`, SMS si `critical`) **au changement seulement** (nouveaux constats, retour à la normale).

## Inventaire

- **Import d'une zone DNS** (export BIND OVH/Online) ou d'une liste de noms : A/AAAA/CNAME/MX (cible)/SRV (cible) deviennent des entrées source `dns` ; SOA/NS/TXT/jokers ignorés. Option « marquer disparues » : les entrées absentes du nouvel import sont datées (`gone_at`), jamais supprimées, événement `entry-gone`.
- **Registre versionné** `service-watch/entries.json` (sans secret, exemple fictif) : entrées avec ports, URL, `expect_url`, `max_ms`, `masks`, scénario ; chargé au démarrage (source `registry`).
- **Ajout manuel** depuis la page.

Scénario : `[{name, path|url, method, form, json, login:{credential, user_field, password_field}, expect:{status, text, not_text, url, headers, max_ms}, follow}]`.

## Canaris mail

Un message porteur d'un jeton unique (`X-SI-Canary`) part d'un compte **externe** (SMTP, identifiants dans le coffre) vers une boîte **interne** ; la boîte est lue par IMAP jusqu'à `wait_s` : délai, sauts `Received`, `Authentication-Results` (SPF/DKIM/DMARC), intégrité du corps ; message supprimé ensuite. Constats : non arrivé, en retard (`max_delay_s`), authentification en échec, altéré, envoi impossible. Toutes les `SERVICE_WATCH_CANARY_INTERVAL_MINUTES` (60).

## API

| Route | Rôle |
|---|---|
| `GET /status`, `/entries`, `/entries/<n>/runs`, `/canaries`, `/canaries/<n>/runs`, `/events` | lecture |
| `POST /entries` (`{name, ports, url, expect_url, max_ms, diff_threshold_pct, masks, scenario}`), `DELETE /entries/<n>` | entrées |
| `POST /entries/<n>/check`, `POST /entries/<n>/reference` | passage immédiat, validation de la référence de contenu |
| `POST /import` (`{text, origin, replace}`) | zone DNS / liste de noms |
| `POST /canaries`, `DELETE /canaries/<n>`, `POST /canaries/<n>/run` | canaris |
| `POST /cycle` (`{what: entries|canaries|all}`) | passage global en arrière-plan |

## Limites et suites (item 80)

Pas encore : point d'exécution **hors du SI** (nœud OVH / agent externe) pour distinguer « service mort » de « chemin cassé » ; captures d'écran et différence d'image (Playwright) — la différence de texte couvre déjà défiguration, page d'erreur et parking ; canari GED (dépôt + audit) ; alimentation automatique depuis la synthèse SI (#523) ; règles Cortex.

Trafic identifié par le User-Agent `si-service-watch/1`. Tests : `cd service-watch && python3 -m unittest discover -s tests`.
