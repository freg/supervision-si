# Accès public au hub par un frontal Apache (livraison #471)

Cas : la VM du hub (« super ») est sur le LAN ; une autre VM du LAN reçoit
le 443 public. Le frontal termine le TLS public avec un certificat Let's
Encrypt (certbot, renouvellement automatique) et fait proxy inverse vers la
passerelle nginx du hub. Script : `scripts/front-reverse-proxy.sh`
(Debian / Ubuntu, root, idempotent).

Deux modes. **Réécriture (recommandé, #473)** : le hub reste construit
pour son origine LAN, le frontal réécrit cette origine en nom public dans
tout ce qu'il renvoie ; LAN et extérieur coexistent, aucun rebuild.
**Reconstruction** : le hub est construit pour le nom public (section 1),
et le LAN doit résoudre ce nom.

## 0. Mode réécriture — côté hub : deux lignes

```bash
# .env de super
VITE_ALLOWED_HOSTS=super,hub.mondomaine.fr            # #472 : le serveur Vite accepte ces noms
KEYCLOAK_EXTRA_ORIGINS=https://hub.mondomaine.fr      # #473 : redirections OIDC / origines web des clients
python3 keycloak/render.py && ./scripts/run.sh up -d   # run.sh propose la ré-importation du realm
```

Puis, sur le frontal, `INTERNAL_ORIGIN=https://<HOST_IP>:<GATEWAY_PORT>`
(l'origine telle que le hub a été construit, ex. `https://192.0.2.10:6443`)
en plus des variables de la section 2. Apache décompresse les réponses,
remplace `https://192.0.2.10:6443` (et `wss://…`, `//…/`) par le nom
public dans HTML, JS, CSS, JSON et texte, réécrit les en-têtes `Location`
et le domaine des cookies (`mod_substitute`, `mod_deflate`,
`ProxyPassReverse`). Keycloak garde `KC_HOSTNAME` interne : ses URL sont
réécrites au passage, l'émetteur des jetons reste le même pour les API.
Limites : ce qui est construit côté client à partir de `window.location`
n'est pas concerné (déjà public) ; un texte qui citerait l'origine
interne dans un contenu métier (ticket, document) serait réécrit aussi
à l'affichage — jamais en base.

## 1. Mode reconstruction — côté hub : construire pour le nom public

Les URL du hub (Keycloak, fronts, API) sont fabriquées **au build** à
partir de `HOST_IP:GATEWAY_PORT`. Derrière un frontal, le navigateur doit
recevoir des URL en `https://<nom public>/…`, donc :

```bash
# .env
HOST_IP=hub.mondomaine.fr
GATEWAY_PORT=443            # la passerelle écoute et publie 443 sur super
./pki/scripts/generate-server-cert.sh          # certificat de la passerelle : SAN = hub.mondomaine.fr
python3 keycloak/render.py                     # URL de redirection OIDC des clients du realm
./scripts/run.sh up -d --build                 # rebuild des fronts ; run.sh propose la ré-importation du realm
```

Sur le LAN, `hub.mondomaine.fr` doit résoudre vers le frontal (DNS interne
ou `/etc/hosts`) — ou directement vers super si tu préfères éviter le
détour — sauf si la box fait du « hairpin NAT ». Rien d'autre à ouvrir :
seul le frontal est publié.

## 2. Côté frontal — Apache + certbot

```bash
scp freg@super:SRC/data2/tickets/supervision-si/si-proxy/certs/ca.crt /root/hub-ca.crt   # CA de la PKI (public)
PUBLIC_HOST=hub.mondomaine.fr LE_EMAIL=moi@mondomaine.fr HUB_UPSTREAM=https://super:6443 \
INTERNAL_ORIGIN=https://192.0.2.10:6443 HUB_CA=/root/hub-ca.crt sudo -E ./front-reverse-proxy.sh
#   (mode reconstruction : HUB_UPSTREAM=https://super:443, sans INTERNAL_ORIGIN)
```

Le script installe apache2 + certbot, active ssl / proxy / proxy_http /
proxy_wstunnel / headers / rewrite, écrit le site `hub-<nom>` (port 80 :
défi ACME + redirection ; port 443 : proxy, WebSocket, X-Forwarded-*,
HSTS, pas de plafond d'envoi), obtient le certificat par `--webroot`,
installe un hook de renouvellement qui recharge Apache (`certbot.timer`,
deux essais par jour). `STAGING=1` pour un premier essai sans consommer le
quota Let's Encrypt. Relançable : la configuration est régénérée.

Avec `HUB_CA`, Apache **vérifie** le certificat de la passerelle (nom +
chaîne) ; sans, il chiffre sans vérifier — acceptable sur un LAN maîtrisé,
pas au-delà.

## 3. Vérifier

```bash
curl -sI https://hub.mondomaine.fr/ | head -3            # 200/302 depuis l'extérieur
certbot renew --dry-run                                  # renouvellement simulé
tail -f /var/log/apache2/hub-hub.mondomaine.fr-error.log
```

Puis connexion au hub : Keycloak doit rediriger vers `https://hub.mondomaine.fr/…`
(si la page de connexion renvoie vers une IP LAN, `HOST_IP` n'a pas été
reconstruit ou le realm n'a pas été ré-importé).

## 4. Ce que le frontal ne couvre pas

- Le **bastion si-proxy** (6450) n'est pas de l'HTTP : il passe par le saut
  SSH (`si-proxy/README.md`) ou par un `--san` + port publié, pas par Apache.
- Les ports directs non passerellés (`shared/EXPOSURE.json`) restent LAN.
- Le 443 public est désormais la porte d'entrée : garder le frontal à jour,
  et envisager `mod_evasive` / fail2ban sur ses journaux.
