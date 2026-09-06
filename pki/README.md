# Autorité de certification interne (`pki/`)

Certificats TLS pour `tls-proxy` (voir `tls-proxy/README.md`), sans
dépendance à Let's Encrypt ni à internet — environnement autonome.

## Ce qui se passe, en deux temps

1. **`generate-ca.sh`** — génère une fois pour toutes un certificat
   racine auto-signé (`pki/ca/ca.crt` + `pki/ca/ca.key`, 10 ans de
   validité par défaut). **Jamais régénéré s'il existe déjà** — le
   régénérer casserait la confiance de tous les postes qui auraient
   déjà installé l'ancien (voir plus bas). Supprimer `pki/ca/` à la
   main est le seul moyen d'en forcer un nouveau.
2. **`generate-server-cert.sh`** — génère le certificat *feuille*
   utilisé par nginx, signé par cette CA, avec `HOST_IP` (`.env`) en
   Subject Alternative Name. **Régénéré à chaque lancement** (via
   `scripts/run.sh`, automatique) : aucun risque, la CA ne change pas,
   donc aucun nouvel avertissement navigateur — seul le certificat
   feuille est renouvelé, ce qui le garde toujours aligné sur l'IP
   réelle de la machine (utile si elle change, ex. bail DHCP).

Un seul certificat serveur suffit pour **tous** les ports de
`tls-proxy` — un certificat valide un **hôte** (via ses SAN), pas un
port. Pas besoin d'un certificat par service.

## Lancement

Automatique via `./scripts/run.sh up -d --build` (CA + certificat +
config nginx régénérés avant chaque `docker compose`). À la main :

```bash
pki/scripts/generate-ca.sh
pki/scripts/generate-server-cert.sh
```

## Distribuer la CA aux postes clients — l'étape qui compte vraiment

Sans ça, chaque navigateur affichera un avertissement de sécurité à
chaque nouveau service tant que le certificat n'est pas accepté à la
main — exactement ce que la CA interne est censée éviter. **Une seule
fois par poste**, installer `pki/ca/ca.crt` (pas `server.crt`, jamais
`.key`) dans le magasin de certificats de confiance :

**Windows** : double-clic sur `ca.crt` → *Installer le certificat* →
*Ordinateur local* → *Placer tous les certificats dans le magasin
suivant* → **Autorités de certification racines de confiance**.
Ou en ligne de commande (élevé) :
```
certutil -addstore -f "ROOT" ca.crt
```

**macOS** : double-clic sur `ca.crt` (ouvre Trousseau d'accès) → onglet
*Certificats* → double-clic sur le certificat importé → *Approbation*
→ *Toujours faire confiance*. Ou en ligne de commande :
```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ca.crt
```

**Linux (Debian/Ubuntu)** :
```bash
sudo cp ca.crt /usr/local/share/ca-certificates/supervision-si-ca.crt
sudo update-ca-certificates
```
**Firefox a son propre magasin, indépendant de l'OS** (contrairement à
Chrome/Edge/Safari qui utilisent celui du système) : *Paramètres* →
*Vie privée et sécurité* → *Certificats* → *Afficher les certificats*
→ onglet *Autorités* → *Importer* → cocher *Faire confiance à cette
AC pour identifier des sites web*.

## Sécurité

`pki/ca/ca.key` est la pièce la plus sensible de tout ce mécanisme —
quiconque la possède peut émettre un certificat que **tous les postes
ayant installé la CA** accepteront pour n'importe quel nom. Jamais
versionnée (`pki/ca/` et `pki/server/` sont dans `.gitignore`, comme
`keycloak/import/`), permissions restreintes (`chmod 600`) posées par
`generate-ca.sh` lui-même. `pki/server/server.key` est sensible aussi
mais son impact est borné aux SAN de ce seul certificat (l'IP de cette
machine), pas "n'importe quel nom" comme la clé de la CA.

## Dossier configurable (`PKI_DIR`)

Vide par défaut = comportement historique (`pki/ca/`, `pki/server/`
dans l'arborescence du projet). Même mécanisme que
`KEYCLOAK_IMPORT_DIR`/`KEYCLOAK_BACKUP_DIR`/`TICKETS_DATA_DIR`, même
garde-fou anti-`~`.

**Pourquoi ça compte particulièrement ici** — bug réel rencontré :
`SEC_ERROR_REUSED_ISSUER_AND_SERIAL` côté navigateur. Un déploiement
qui supprime puis réextrait le projet à chaque nouvelle livraison
régénère une CA neuve à chaque fois — toujours le même nom
d'émetteur (`O=Supervision SI, CN=Supervision SI Internal CA`,
codé en dur), et comme le fichier `.srl` de suivi des numéros de
série ne survit pas non plus, le premier certificat signé par
CHAQUE nouvelle CA repart du même numéro de série de départ. Si une
CA plus ancienne traîne encore dans le magasin de confiance du
navigateur (jamais retirée avant d'en réimporter une nouvelle),
Firefox voit deux certificats différents partageant émetteur ET
numéro de série — refuse, à raison, d'y faire confiance.

```bash
# .env
PKI_DIR=/home/<utilisateur>/supervision-si-pki
```

**Si l'erreur apparaît malgré tout** : le magasin de certificats du
navigateur contient probablement plusieurs entrées "Supervision SI
Internal CA" (impossible à distinguer visuellement, même nom
affiché) — les retirer **toutes**, puis réimporter uniquement le
`ca.crt` actuellement sur disque.

## Bugs réels rencontrés en test réel (personne, machine physique)

**`/bin/sh: Syntax error: "(" unexpected` dans `generate-server-cert.sh`.**
Le script utilisait une substitution de processus `<(...)` — syntaxe
propre à bash, absente de `sh`/`dash` (l'implémentation par défaut de
`/bin/sh` sur Debian/Ubuntu). Selon comment ce script finit par être
invoqué dans une chaîne d'appel, il peut se retrouver interprété par
`sh` malgré son `#!/usr/bin/env bash`, et échouer avec cette erreur
obscure. Corrigé : fichier temporaire classique (`mktemp`) à la place
— fonctionne à l'identique sous n'importe quel shell.

**`bad ip address ... value=localhost`.** `HOST_IP=localhost` — la
valeur recommandée dans ce README pour tester via tunnel SSH — faisait
planter la génération du certificat serveur : le script traitait
`HOST_IP` comme une adresse IP littérale sans le vérifier, produisant
un SAN invalide `IP:localhost` ("localhost" est un nom, pas une
adresse — openssl a raison de le refuser). Corrigé : distinction
explicite entre une IPv4 littérale (`IP:...`) et un nom (`DNS:...`),
plus de suppression aveugle de la sortie openssl (`>/dev/null 2>&1`
retiré des deux commandes) — un échec futur affichera son vrai message
d'erreur au lieu de se limiter à un `❌ ARRÊT` générique côté
`scripts/run.sh`.

**`scripts/run.sh` n'affichait pas clairement pourquoi il s'arrêtait**
si une étape de préparation (rendu Keycloak, CA/certificat, config
nginx) échouait — `set -e` arrêtait le script, mais sans message
explicite reliant "une commande a échoué plus haut" à "la stack Docker
n'a donc pas démarré". Ajout d'un message `❌ ARRÊT` impossible à
manquer après chaque étape critique.

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : génération réelle de la CA et du certificat serveur
(`openssl` disponible ici), **chaîne de confiance vérifiée
cryptographiquement** (`openssl verify -CAfile ca.crt server.crt` →
`OK`), SAN corrects avec un `HOST_IP` réaliste et `TLS_EXTRA_SAN`,
idempotence de `generate-ca.sh` (relancé deux fois, rien refait la
seconde). Bug réel trouvé et corrigé en testant l'enchaînement complet
depuis `scripts/run.sh` : `generate-server-cert.sh` ne lisait `HOST_IP`
que depuis `.env`, jamais depuis la variable d'environnement déjà
exportée par `run.sh` après détection automatique (`hostname -I`) —
le SAN se retrouvait donc sans l'IP réelle malgré une détection
correcte en amont. Corrigé (priorité variable d'environnement > `.env`
> défaut, comme partout ailleurs dans ce projet).

**Non vérifié** : aucun navigateur réel ici pour confirmer l'absence
d'avertissement une fois la CA installée, ni les procédures
d'installation par OS ci-dessus (rédigées depuis la documentation
officielle de chaque plateforme, jamais exécutées en conditions
réelles depuis cet environnement).
