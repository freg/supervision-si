# ups-monitor — tuile « Onduleurs (UPS) »

Livraison #415, demandée en urgence : « gestion des UPS : un automate /
cron ; une liste d'onduleurs / site / IP / user / password ; en version 0
une requête HTTP du genre `http://user:password@ip/index.htm` qui retourne
la page ; d'où on extrait une fiche d'état avec tous les champs présentés
et qu'on propose en tableau ; les données sont archivées et présentées à
la demande en timeline ; fréquence initiale (paramétrable) 1 heure ».

## Ce que fait la version 0

- **Liste** des onduleurs : nom, site, IP ou nom, schéma (http/https),
  page (`/index.htm` par défaut), utilisateur, mot de passe, fréquence
  propre (vide = fréquence globale), activé/désactivé, notes.
- **Automate** (`poller.py`) : thread de fond dans `ups-monitor-api`, un
  passage par minute ; chaque onduleur activé est relevé quand son
  intervalle est écoulé depuis `last_polled_at` (en base, donc résistant
  au redémarrage). Fréquence globale `UPS_POLL_INTERVAL_SECONDS` (3600 par
  défaut), 30 s minimum par onduleur (la page se rafraîchit elle-même
  toutes les 30 s).
- **Requête** : GET sur `scheme://host/path` avec authentification HTTP
  Basic construite depuis utilisateur / mot de passe — c'est ce que le
  navigateur fait de `user:password@` dans l'URL. `urllib` de la
  bibliothèque standard, délai 10 s, 512 Ko maximum, sans suivi vers un
  autre hôte.
- **Fiche d'état** (`ups_parser.py`) : sections = cellules `class="title"`,
  champs = cellule « Libellé: » suivie de sa valeur, sur la page
  « UPS Management Web » (Socomec NETYS RT) copiée par la personne
  (`samples/netys_rt_index.htm`) — 4 sections, 14 champs, heure système,
  classe CSS de chaque valeur. Générique sur cette forme : un libellé
  inconnu est conservé avec une clé dérivée, jamais perdu. Les valeurs
  numériques (« 236.0 V », « 8 % », « 27,4 V ») sont extraites avec leur
  unité. État global `ok` / `alarm` / `unknown` d'après Communication,
  Output Source, Battery.
- **Archive** (`ups_readings`) : un relevé par requête, réussie OU NON
  (« injoignable depuis 3 h » est une information), fiche complète en
  JSON + colonnes extraites (tension entrée/sortie, charge, batterie).
  Conservation `UPS_HISTORY_RETENTION_DAYS` (365, 0 = illimitée).
- **Tuile hub** (`hub/src/UpsView.jsx`) : liste avec état, âge du dernier
  relevé, résumé, fréquence, actions ⟳ relever / ✎ modifier / 🗑 ;
  formulaire avec « Tester la requête » (essai sans enregistrer) ; fiche
  d'état en tableau (section, champ en français, valeur colorée pour les
  champs d'état) ; **timeline** : fenêtre 24 h / 7 j / 30 j / tout, courbe
  d'un champ numérique au choix (zoom #413), tableau des relevés avec
  les valeurs qui ont changé mises en évidence et les échecs datés.

## API (`/api/ups` via tls-proxy, port direct `UPS_MONITOR_API_PORT` = 6128)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/status` | compteurs, réglages effectifs, `secrets_encrypted` |
| GET / POST | `/ups` | liste (sans mot de passe) / création |
| GET / PUT / DELETE | `/ups/<id>` | fiche (onduleur + dernier relevé + dernière fiche complète) / modification (mot de passe vide = inchangé, `clear_password` pour l'effacer) / suppression avec archive |
| POST | `/ups/<id>/poll` | relever maintenant |
| POST | `/ups/test` | essayer une saisie sans rien enregistrer |
| GET | `/ups/<id>/readings?start&end&limit&fields=1` | timeline (du plus ancien au plus récent) |
| GET | `/ups/<id>/series?key=input_voltage&start&end` | série d'un champ (relevés réussis) |

Le mot de passe n'est **jamais** renvoyé (`has_password`,
`password_encrypted`).

## Mots de passe stockés

Même motif que `snmp-api` (#213) : `credential_crypto.py` enveloppe
`shared/secret_crypto.py`, phrase de passe `UPS_CRED_PASSPHRASE` et sel
`UPS_CRED_SALT` (base64, généré UNE fois :
`python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(16)).decode())"`,
jamais régénéré) fournis en continu au conteneur. **Différence assumée
avec snmp** (urgence) : sans ces variables, les mots de passe sont
stockés **en clair** dans le volume `/data` et la tuile l'affiche en
avertissement. Une fois les variables posées, chaque modification
d'onduleur rechiffre son mot de passe ; pour tout rechiffrer d'un coup,
ouvrir et enregistrer chaque onduleur (ou `PUT /ups/<id>` avec `{}`).
Si la phrase de passe disparaît ou change, le relevé échoue avec un
message explicite et le jeton est conservé tel quel.

## Variables (`.env`)

`UPS_MONITOR_API_PORT` (6128), `UPS_MONITOR_DATA_DIR`,
`UPS_POLL_INTERVAL_SECONDS` (3600), `UPS_HTTP_TIMEOUT_SECONDS` (10),
`UPS_HISTORY_RETENTION_DAYS` (365), `UPS_CRED_PASSPHRASE`, `UPS_CRED_SALT`.
Côté conteneur seulement : `UPS_POLL_ENABLED=false` (tests),
`UPS_POLL_TICK_SECONDS` (60).

## Tests

```bash
cd ups-monitor/api && UPS_POLL_ENABLED=false python3 -m unittest test_ups_monitor.py   # 14 tests
node --test hub/tests/upsMonitor.test.mjs                                               # 7 tests
```

Parseur sur la page réelle ; store, automate (intervalles, activation,
forçage), timeline, purge, cascade ; routes via `test_client` ; un vrai
serveur HTTP local avec Basic (401 sans identifiants) interrogé par le
vrai `urllib` ; chiffrement optionnel (clair → chiffré à la modification,
phrase absente → échec explicite, jeton conservé).

## Vérifié / non vérifié

**Vérifié** : les 21 tests ci-dessus ; build Vite réel du hub ; **chaîne
complète réelle** dans l'environnement de développement : `ups-monitor-api`
lancé (Flask) + faux onduleur HTTP servant la page copiée derrière Basic +
tuile rendue dans Chromium (Playwright) — création, test de requête,
relevés, fiche, timeline avec courbe, onduleur injoignable en erreur
datée, aucune erreur console.

**Non vérifié** : un onduleur RÉEL (la page copiée est celle d'un NETYS RT ;
une autre carte Socomec ou un autre constructeur peut présenter la page
autrement — le parseur signale alors « aucun champ reconnu », voir
ci-dessous) ; le build Docker (`docker compose build ups-monitor-api`) et
la route tls-proxy en conditions réelles ; le comportement d'une carte
qui répondrait par un formulaire de connexion plutôt qu'en Basic.

## Ce que cette version ne fait pas (backlog 62)

- D'autres pages de la carte (`info_battery.htm`, `info_io.htm`,
  `hist_log1.htm`) : le parseur les lirait déjà, il manque la notion de
  « plusieurs pages par onduleur ».
- SNMP (RFC 1628 UPS-MIB), plus fiable que l'HTML : la tuile est prête
  à recevoir une seconde méthode de relevé.
- Alertes (passage en alarme, injoignable depuis N relevés) vers
  vigilance / SMS (`shared/secrets_alert.py`).
- Seuils personnalisés (tension, charge, batterie) et détection de
  dérive.
