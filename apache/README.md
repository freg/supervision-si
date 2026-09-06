# Point d'entrée Apache 2.4.25-3

Devenu trivial depuis le passage à une **entrée unique par chemin**
côté `tls-proxy` (voir `tls-proxy/README.md`) : **un seul
`VirtualHost`** à générer, plus 15. Toujours généré depuis `.env`
plutôt qu'écrit à la main — `GATEWAY_PORT` ne doit jamais diverger
entre les deux côtés.

## Décisions actées avec la personne

- **Apache termine le TLS lui-même** — pas de double chiffrement côté client.
- **Apache est sur une machine séparée, à plusieurs pattes réseau** —
  le relais vers `tls-proxy` se fait donc **en HTTPS**, jamais en
  clair. Apache doit faire confiance à la même CA interne pour
  valider le certificat présenté par `tls-proxy` côté sortant.
- **Entrée unique par chemin** (suggestion de la personne, actée en
  cours de session) — un seul port à relayer des deux côtés.

## `TLS_PROXY_UPSTREAM_HOST` — quelle IP Apache utilise pour joindre `tls-proxy`

**Distincte de `HOST_IP`** (celle-ci sert au *navigateur* pour
joindre la plateforme, auto-détectée côté machine Docker via
`hostname -I` — pas forcément la bonne patte réseau si cette machine
est elle-même multi-pattes). Dans `.env` :
```bash
TLS_PROXY_UPSTREAM_HOST=<IP par laquelle Apache atteint la machine Docker>
```
Vide = retombe sur `HOST_IP`.

**Important** : cette IP doit figurer dans le certificat que
`tls-proxy` présente (`pki/server/server.crt`) — si elle diffère de
`HOST_IP`, l'ajouter à `TLS_EXTRA_SAN` (`.env`) avant de régénérer
(`pki/scripts/generate-server-cert.sh`), sinon Apache
(`SSLProxyCheckPeerName on`) rejettera la connexion.

## Checklist de mise en place

**1. Modules Apache requis** :
```bash
sudo a2enmod ssl proxy proxy_http proxy_wstunnel rewrite
sudo systemctl restart apache2
```

**2. Certificats** — trois fichiers : le certificat propre d'Apache
pour le TLS côté client, **plus** la CA interne pour valider
`tls-proxy` côté sortant (voir `pki/README.md`) :
```bash
sudo mkdir -p /etc/apache2/tls
sudo cp pki/server/server.crt pki/server/server.key pki/ca/ca.crt /etc/apache2/tls/
sudo chmod 600 /etc/apache2/tls/server.key
```
(chemin personnalisable via `APACHE_TLS_DIR` dans `.env`.)

**3. Générer et copier la config** :
```bash
python3 apache/render_apache_conf.py
scp apache/generated/supervision-si.conf <apache-host>:/etc/apache2/sites-available/
```

**4. Activer et tester AVANT de recharger** :
```bash
sudo a2ensite supervision-si
sudo apache2ctl configtest
sudo systemctl reload apache2
```

**5. Vérifier** :
```bash
curl -kv https://<apache-host>:6443/auth/realms/supervision-si
```
Si ça échoue précisément côté connexion sortante d'Apache (pas côté
client), regarder `SSLProxyCheckPeerName`/le SAN du certificat de
`tls-proxy` en premier.

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : `render_apache_conf.py --check` et génération réelle
(1 `VirtualHost` confirmé), résolution de `TLS_PROXY_UPSTREAM_HOST`
(testée avec et sans surcharge), syntaxe relue (directives stables
depuis bien avant Apache 2.4.25).

**Non vérifié** : aucun Apache réel disponible dans cet environnement
— ni `apache2ctl configtest`, ni un chargement réel de cette config,
ni le relais effectif vers `tls-proxy` à travers un vrai réseau à
deux machines. `apache2ctl configtest` (étape 4) est le geste le plus
important à faire en premier sur la vraie machine, avant `reload`.
