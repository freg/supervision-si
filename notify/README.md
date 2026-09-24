# Notifications et gestionnaire d'envoi — notify-api (#590, backlog item 92)

Tuile **Sécurité & accès → 📣 Notifications** (`?view=notifications`,
`&tab=assign|groups|queue|consumers|settings`), groupe `administrateurs`.

## Modèle

- **Actions** : catalogue `module.action` (ex. `mikrotik.nat.add`,
  `cisco.restore`, `tower.heal.gave-up`), gravité `info | warning |
  critical`. Déclarées par les modules au démarrage
  (`POST /actions/register`) ou créées à la première notification reçue.
- **Groupes** (adresses) et **méta-groupes** (union de groupes, récursive,
  cycles tolérés). Chaque module a son **groupe par défaut généré**
  `auto:<module>` : renseigner ses adresses suffit pour recevoir tout le
  module.
- **Affectation** action → groupes : par action, ou `module.*` pour tout le
  module ; sans affectation → groupe par défaut.
- **Liste noire** : adresse, action (ou `module.*`), consommateur.
- **Consommateurs** : les modules du hub avec le jeton interne
  (`NOTIFY_INTERNAL_TOKEN`, en-tête `X-Notify-Token`, `X-Notify-Consumer`
  = nom du module) ; les services **externes** (GED…) reçoivent chacun un
  jeton émis dans la tuile (montré une fois, haché en base).

## Gestionnaire d'envoi (détaché)

`POST /notify` met en file et répond **202** immédiatement (jamais
bloquant). Un fil d'envoi (5 s) traite la file : **regroupement** des
messages identiques (action + sujet + destinataires) dans la fenêtre,
**retenue des rafales** (au-delà du seuil par action et fenêtre : les
suivants sont `held`, un résumé unique part), **débit maximal** par minute,
**backoff** (1, 2, 4… min) et **disjoncteur** SMTP (N échecs consécutifs →
pause), **abandon** après N tentatives (`failed`, renvoyable). États :
`queued`, `sent`, `held`, `failed`, `no-recipients`, `dropped` — tout reste
consultable dans la file avec sa raison. Réglages dans la tuile ; `enabled`
à faux retient tout sans rien perdre.

## Producteurs branchés (#590)

`shared/notify_client.py` : `notify(action, subject, body, context)`
(fire-and-forget, 2 s, jamais d'exception) et `register_actions([...])`.
Branchés : **MikroTik** (NAT ajout / modification / suppression, interface,
redémarrage), **Cisco** (sauvegarde, restauration, interface, write,
reload), **tour de contrôle** (livraison appliquée, job terminé / en échec,
auto-réparation : relance et abandon, redémarrage manuel, registre
modifié). Variables du producteur : `NOTIFY_API_URL`,
`NOTIFY_INTERNAL_TOKEN`, `NOTIFY_CONSUMER`.

## API (jeton Keycloak sauf producteurs)

`POST /notify`, `POST /actions/register` (jeton consommateur) ;
`GET /actions`, `PUT /actions/<action>/groups`, `GET/POST /groups`,
`PUT/DELETE /groups/<id>`, `GET/POST /blacklist`, `DELETE
/blacklist/<kind>/<value>`, `GET/POST /consumers`, `DELETE
/consumers/<name>`, `GET /queue[?status=]`, `GET /queue/<id>`, `POST
/queue/<id>/retry|drop`, `POST /queue/release`, `GET/PUT /settings`,
`GET /events`, `POST /test {to}`, `GET /health`.

## Configuration

```
NOTIFY_INTERNAL_TOKEN=<openssl rand -hex 24>   # obligatoire pour les producteurs
NOTIFY_SMTP_HOST= NOTIFY_SMTP_PORT=587 NOTIFY_SMTP_USER= NOTIFY_SMTP_PASSWORD= NOTIFY_SMTP_FROM= NOTIFY_SMTP_USE_TLS=true
NOTIFY_ADMIN_GROUPS=administrateurs   NOTIFY_SUBJECT_PREFIX=[Hub SI]   NOTIFY_DATA_DIR=./notify/data
```

Sans `NOTIFY_SMTP_*`, les `SECRETS_ALERT_SMTP_*` du PRA sont repris.
Base SQLite dans `notify/data/` (à sauvegarder). Tests : `notify/api/test_core.py`
(résolution, liste noire, backoff, rafale, disjoncteur), `test_app.py`
(producteurs, catalogue, groupes / méta, file, envoi simulé), hub
`tests/notifyLib.test.mjs`.

Suites (item 92) : canaux SMS (TRB140) et webhook, gabarits par action,
digest quotidien, rattachement des circuits épars (`SECRETS_ALERT_*`,
`SI_AGENT_NOTIFY_*`, service-watch, Cortex) au gestionnaire.
