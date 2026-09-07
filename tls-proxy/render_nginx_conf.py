#!/usr/bin/env python3
"""
Génère la config nginx du proxy TLS depuis .env — ENTRÉE UNIQUE par
chemin (un seul port public, `GATEWAY_PORT`), pas un port par service.

    python3 tls-proxy/render_nginx_conf.py            # écrit generated/services.conf
    python3 tls-proxy/render_nginx_conf.py --check    # affiche le mapping sans écrire

Décidé avec la personne, en cours de session : réduit la surface
exposée côté Apache (le vrai point d'entrée réseau, sur une machine
séparée à plusieurs pattes) à UN SEUL port au lieu de 15 — un seul
VirtualHost/règle de pare-feu à gérer côté bordure réseau. Remplace le
schéma précédent (un `listen PORT ssl` par service), gardé dans
l'historique git si besoin d'y revenir.

RÉSOLUTION DNS DYNAMIQUE (livraison #134) -- changement DÉLIBÉRÉ,
prérequis à la séparation de Keycloak/tls-proxy dans leur propre
stack Compose (backlog). Un `proxy_pass http://service:port;` LITTÉRAL
(comme avant) force nginx à résoudre le nom UNE SEULE FOIS, au
chargement de la config -- si UN SEUL des 21 noms référencés n'est
pas encore résolvable à cet instant précis (conteneur pas encore créé,
pas juste "pas prêt"), nginx REFUSE DE DÉMARRER ENTIÈREMENT (pas
seulement pour ce service -- pour TOUT, "host not found in upstream").
Rencontré RÉELLEMENT deux fois dans ce projet : l'incident du
2026-08-26 (dépendances manquantes dans `depends_on`), et le bug
`keycloak_admin.py` jamais copié dans l'image `prefs-api` (livraison
#125, voir `keycloak/README.md`). Corrigé en forçant la résolution
DYNAMIQUE, à la CONNEXION (pas au chargement) : `resolver 127.0.0.11`
(résolveur DNS interne de Docker) + une VARIABLE dans `proxy_pass`
(`set $backend ...; proxy_pass http://$backend;`) -- nginx démarre
maintenant TOUJOURS, même si un service référencé n'existe pas encore
(502 le temps qu'il apparaisse, jamais un refus de démarrer).

**Piège nginx à connaître, la vraie raison de ce fichier plutôt qu'un
simple copier-coller** : `proxy_pass` avec une VARIABLE ne fait PLUS
le retrait automatique de préfixe qu'un `proxy_pass .../;` LITTÉRAL
fait (le comportement lié au "/" final ne s'applique qu'en écriture
statique) -- sans compensation, les APIs recevraient le préfixe
`/api/xxx/` en plus de leurs propres routes. D'où le `rewrite
^{path}(.*)$ /$1 break;` explicite ajouté pour les locations "api"
(jamais pour "spa"/"keycloak", qui veulent justement CONSERVER le
préfixe -- comportement inchangé pour elles).

**Second piège, RENCONTRÉ RÉELLEMENT en production (bug PARTIELLEMENT
corrigé, livraison #136 -- voir le TROISIÈME piège ci-dessous pour la
vraie cause complète)** : `proxy_pass http://$backend;` -- une
variable NUE, sans rien après -- laisse une ambiguïté nginx que ce
module ne pouvait pas vérifier faute de binaire nginx installable ici
(dépôts Ubuntu bloqués, voir tls-proxy/README.md) : est-ce que ça
transmet $uri (reflète le `rewrite` ci-dessus) ou $request_uri
(l'original, JAMAIS modifié) ? Corrigé en rendant tout EXPLICITE :
`proxy_pass http://$backend$uri$is_args$args;` -- ce correctif reste
juste et nécessaire, mais s'est avéré INSUFFISANT à lui seul : le 500
a persisté après #136, la vraie cause restant le troisième piège
ci-dessous, non détecté à ce moment faute de preuve directe (logs
nginx réels).

**TROISIÈME piège, LA VRAIE CAUSE COMPLÈTE (bug corrigé, livraison
#146, après DEUX tentatives précédentes infructueuses -- #134 et
#136)** : `rewrite ^{path}(.*)$ /$1 break;` était placé AVANT
`set $backend ...;` dans API_LOCATION_TEMPLATE. Or `break` interrompt
tout le traitement des directives de la phase de réécriture pour
cette requête -- pas seulement les `rewrite` suivants, TOUTES les
directives qui suivraient dans le même bloc, y compris un `set`. Avec
cet ordre, `set $backend` ne s'exécutait donc JAMAIS -- `$backend`
restait perpétuellement non initialisée, `proxy_pass` échouait
systématiquement sur TOUTE route "api" (jamais "spa"/"keycloak", qui
n'ont pas de `rewrite` -- explique pourquoi le hub et l'authentification
Keycloak ont TOUJOURS fonctionné pendant toute cette période, seuls
les appels `/api/*` échouaient, sans exception, du tout premier signalement
jusqu'à cette livraison). Confirmé par les vraies traces nginx
fournies par la personne (`using uninitialized "backend" variable`,
`no host in upstream`) -- SEULE preuve qui a permis de trouver ce
piège, les deux tentatives précédentes (#134, #136) ayant dû deviner
sans pouvoir observer un vrai nginx tourner. Corrigé en inversant
l'ordre : `set` doit TOUJOURS précéder `rewrite ... break;`, jamais le
suivre (SPA_LOCATION_TEMPLATE avait déjà le bon ordre depuis le
début, n'ayant pas de `rewrite` du tout).

TROIS types de service, traités différemment :
- "api" (11 backends Flask) : préfixe RETIRÉ avant transmission --
  DÉSORMAIS via un `rewrite ... break;` explicite (voir ci-dessus,
  plus le simple "/" final d'avant, insuffisant avec une variable) --
  les APIs n'ont aucune notion de préfixe, leurs routes sont écrites
  `/health`, `/subnets`, etc.
- "spa" (frontend/hub/tickets-portal, serveurs de dev Vite) : préfixe
  CONSERVÉ (aucun `rewrite`, la variable dans `proxy_pass` transmet le
  chemin reçu tel quel par défaut) — Vite doit connaître son propre
  préfixe via `base` dans vite.config.js (voir chaque projet) pour
  générer des URLs d'assets cohérentes. PARTIE LA PLUS FRAGILE DE CE
  MODULE — le HMR (rechargement à chaud) de Vite passe par une
  connexion WebSocket qui doit elle aussi survivre au préfixe ET à la
  résolution dynamique, jamais vérifié en conditions réelles ici
  faute de navigateur ET de binaire nginx disponible dans cet
  environnement (voir tls-proxy/README.md).
- "keycloak" : même logique que "spa" (préfixe conservé), mais côté
  Keycloak lui-même il faut EN PLUS `KC_HTTP_RELATIVE_PATH` (déjà
  ajouté dans docker-compose.yml) pour qu'il génère ses propres liens
  avec ce préfixe. Non plus vérifié en conditions réelles.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "generated")
OUT = os.path.join(OUT_DIR, "services.conf")

# (variable .env historique -- gardée seulement pour le message
# d'information, plus utilisée pour publier un port ; nom du service
# docker-compose ; port CONTENEUR interne ; chemin public ; type).
SERVICES = [
    ("SUPERVISION_API_PORT", "api", 5000, "/api/supervision/", "api"),
    ("PIXEL_GRID_API_PORT", "pixel-grid-api", 5000, "/api/pixel-grid/", "api"),
    ("TICKETS_API_PORT", "tickets-api", 5000, "/api/tickets/", "api"),
    ("IPAM_API_PORT", "ipam-api", 5000, "/api/ipam/", "api"),
    ("OPTICK_API_PORT", "optick-api", 5000, "/api/optick/", "api"),
    ("ZENOSS_API_PORT", "zenoss-api", 5000, "/api/zenoss/", "api"),
    ("TTSGU_API_PORT", "tts-gu-api", 5000, "/api/tts-gu/", "api"),
    ("OWNCLOUD_API_PORT", "owncloud-api", 5000, "/api/owncloud/", "api"),
    ("CACTI_API_PORT", "cacti-api", 5000, "/api/cacti/", "api"),
    ("OWNCLOUD_SEARCH_API_PORT", "owncloud-search-api", 5000, "/api/owncloud-search/", "api"),
    ("GEO_IMPORT_API_PORT", "geo-import-api", 5000, "/api/geo-import/", "api"),
    ("DBA_API_PORT", "dba-api", 5000, "/api/dba/", "api"),
    ("SCHEMA_ANALYZER_API_PORT", "schema-analyzer-api", 5000, "/api/schema-analyzer/", "api"),
    ("GED_API_PORT", "ged-api", 5000, "/api/ged/", "api"),
    ("SSH_TUNNELS_API_PORT", "ssh-tunnels-api", 5000, "/api/ssh-tunnels/", "api"),
    # file-manager-api (livraison #396, backlog item 26) -- agrège GED,
    # SSHFS, espace protégé. Routé via la passerelle pour l'interface hub.
    ("FILE_MANAGER_API_PORT", "file-manager-api", 5000, "/api/file-manager/", "api"),
    # snmp-api (livraison #212) -- module SNMP, interface hub #227.
    ("SNMP_API_PORT", "snmp-api", 5000, "/api/snmp/", "api"),
    # netmap-orchestrator-api (livraison #388) -- orchestrateur
    # d'analyse/supervision réseau. Contrairement à docker-monitor-api
    # (#376, jamais routé ici -- accès au socket Docker, équivaut à
    # un accès root sur l'hôte), RIEN ne justifie de garder celui-ci
    # hors passerelle -- lit seulement network-agent-api en HTTP,
    # aucun privilège particulier. Routé ici (#389) pour permettre une
    # future interface hub sans se heurter au blocage "contenu mixte"
    # (page hub en HTTPS, API en HTTP direct) déjà rencontré en
    # tentant d'intégrer docker-monitor-api au hub.
    ("NETMAP_ORCHESTRATOR_API_PORT", "netmap-orchestrator-api", 5000, "/api/netmap-orchestrator/", "api"),
    # network-agent-api (livraison #233) -- agent d'exploration réseau
    # unifié, item 20 du backlog. `service` = "__HOST_IP__" (résolu
    # dynamiquement dans build_config, livraison #239) : ce conteneur
    # tourne en `network_mode: host` (#238, confirmé nécessaire --
    # `ens18` de l'hôte invisible sinon), absent du réseau Docker
    # partagé. `kind` = "api-static" -- mais `host.docker.internal`
    # LUI-MÊME s'est révélé NE PAS FONCTIONNER en déploiement réel
    # ("could not be resolved" -- même un proxy_pass littéral passe
    # par `resolver 127.0.0.11`, qui ne consulte jamais /etc/hosts,
    # voir resolve_host_ip ci-dessus pour le détail complet). Port
    # 15000 (pas 5000, #239) : collision RÉELLE trouvée avec un
    # `docker-registry` déjà présent sur le port 5000 de l'hôte de la
    # personne -- network_mode: host expose directement ce port sur
    # l'hôte, jamais isolé comme les autres services Docker.
    ("NETWORK_AGENT_API_PORT", "__HOST_IP__", 15000, "/api/network-agent/", "api-static"),
    # retro-api (livraison #243) -- tuile "Rétro-ingénierie", item 30
    # du backlog.
    ("RETRO_API_PORT", "retro-api", 5000, "/api/retro/", "api"),
    # backup-restore-api (livraison #249) -- sous-volet "backup-restore",
    # item 27 du backlog, marqué URGENT par la personne.
    ("BACKUP_RESTORE_API_PORT", "backup-restore-api", 5000, "/api/backup-restore/", "api"),
    # architecture-api (livraison #253) -- vue/outil de parcours de
    # l'architecture réseau.
    ("ARCHITECTURE_API_PORT", "architecture-api", 5000, "/api/architecture/", "api"),
    # memory-api (livraison #259) -- tuile "Mémoire", rémanence du
    # tampon de logs Memcached.
    ("MEMORY_API_PORT", "memory-api", 5000, "/api/memory/", "api"),
    # classifier-api (livraison #260) -- classification sémantique
    # des identités découvertes.
    ("CLASSIFIER_API_PORT", "classifier-api", 5000, "/api/classifier/", "api"),
    # vigilance-api (livraison #262) -- automates d'analyse
    # cyber-vigilance/santé du parc.
    ("VIGILANCE_API_PORT", "vigilance-api", 5000, "/api/vigilance/", "api"),
    # tasks-api (livraison #271) -- gestion de tâches Kanban.
    ("TASKS_API_PORT", "tasks-api", 5000, "/api/tasks/", "api"),
    # rights-api (livraison #283) -- service central de droits.
    ("RIGHTS_API_PORT", "rights-api", 5000, "/api/rights/", "api"),
    # netprobe-api (livraisons #295/#297/#301) -- sondage réseau actif.
    # Manque trouvé en finalisant #301 : la tuile hub et son client
    # appelaient déjà /api/netprobe, jamais routé -- 404 systématique
    # sans ce correctif.
    ("NETPROBE_API_PORT", "netprobe-api", 5000, "/api/netprobe/", "api"),
    # ups-monitor-api (livraison #415) -- tuile UPS. Ajouté dès la
    # première livraison (piège #301).
    ("UPS_MONITOR_API_PORT", "ups-monitor-api", 5000, "/api/ups/", "api"),
    # si-agent-api (livraison #421) -- central des agents hôtes ; les
    # agents Linux signent `/api/v1/...` et le préfixe `/api/si-agent`
    # est retiré ici (même mécanique que netprobe). Ajouté dès la
    # première livraison (piège #301).
    ("SI_AGENT_API_PORT", "si-agent-api", 5000, "/api/si-agent/", "api"),
    # relations-api (livraison #335) -- vue relations transversale de
    # la super tuile ENT, backlog item 38 point 2. Piège déjà rencontré
    # pour netprobe-api (#301) -- ajouté ICI dès la première livraison,
    # jamais laissé pour une passe ultérieure.
    ("RELATIONS_API_PORT", "relations-api", 5000, "/api/relations/", "api"),
    ("IMAP_CLIENT_API_PORT", "imap-client-api", 5000, "/api/imap-client/", "api"),
    # glpi-api (livraison #192) -- import Excel pour l'instant, base
    # du futur "tuile+api" GLPI (backlog).
    ("GLPI_API_PORT", "glpi-api", 5000, "/api/glpi/", "api"),
    # nebula-api (livraison #196) -- connexion/consultation Zyxel
    # Nebula, base du futur import vers GLPI (backlog).
    ("NEBULA_API_PORT", "nebula-api", 5000, "/api/nebula/", "api"),
    # rsyslog-listener (livraison #177) -- route HTTP pour /health et
    # /logs UNIQUEMENT (diagnostic) -- le VRAI flux syslog entrant
    # (UDP) ne passe JAMAIS par ici, voir docker-compose.yml
    # (RSYSLOG_LISTENER_PORT, port exposé DIRECTEMENT sur l'hôte).
    ("RSYSLOG_LISTENER_API_PORT", "rsyslog-listener", 5000, "/api/rsyslog-listener/", "api"),
    ("LDAP_ADMIN_API_PORT", "ldap-admin-api", 5000, "/api/ldap-admin/", "api"),
    ("PREFS_API_PORT", "prefs-api", 5000, "/api/prefs/", "api"),
    ("VAULT_API_PORT", "vault-api", 5000, "/api/vault/", "api"),
    ("SUPERVISION_FRONTEND_PORT", "frontend", 5173, "/app/", "spa"),
    ("SUPERVISION_HUB_PORT", "hub", 5173, "/", "spa"),
    ("TICKETS_PORTAL_PORT", "tickets-portal", 5173, "/tickets/", "spa"),
    ("DBA_PORTAL_PORT", "dba-portal", 5173, "/dba/", "spa"),
    ("LDAP_ADMIN_PORTAL_PORT", "ldap-admin-portal", 5173, "/ldap-admin/", "spa"),
    ("VAULT_PORTAL_PORT", "vault-portal", 5173, "/vault/", "spa"),
    ("KEYCLOAK_PORT", "keycloak", 8080, "/auth/", "keycloak"),
]


def parse_env(path):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def resolve_gateway_port(env):
    raw = os.environ.get("GATEWAY_PORT", env.get("GATEWAY_PORT", "")).strip()
    return raw if raw else "6443"


def resolve_host_ip(env):
    """Livraison #239 -- pour les services en `network_mode: host`
    (network-agent-api, #238), AUCUN nom Docker ni `host.docker.internal`
    ne fonctionne comme cible de `proxy_pass` (voir
    API_LOCATION_TEMPLATE_STATIC : même un `proxy_pass` LITTÉRAL passe
    par le résolveur `resolver 127.0.0.11` dès qu'il est déclaré dans
    le bloc englobant -- trouvaille réelle en déploiement, `nginx`
    renvoyait "host.docker.internal could not be resolved" malgré
    `extra_hosts` -- confirmé que CE résolveur ne consulte JAMAIS
    `/etc/hosts`, contrairement à l'hypothèse initiale). Seule
    solution qui fonctionne : l'ADRESSE IP réelle de l'hôte,
    directement joignable depuis N'IMPORTE QUEL réseau du même hôte
    (Docker bridge inclus). Réutilise `HOST_IP` -- DÉJÀ configuré par
    la personne pour les URLs publiques du hub (voir
    ../docker-compose.yml, `VITE_*_API_BASE_URL`) -- jamais une
    deuxième variable à maintenir en double pour la même valeur."""
    raw = os.environ.get("HOST_IP", env.get("HOST_IP", "")).strip()
    return raw if raw else "127.0.0.1"


# APIs : préfixe RETIRÉ via `rewrite ... break;` (modifie $uri) --
# `proxy_pass http://$backend$uri$is_args$args;` transmet ENSUITE ce
# $uri explicitement, ainsi que la chaîne de requête ($is_args = "?"
# ou vide, $args = ce qui suit -- couple standard nginx pour ce cas
# précis). Bug réel rencontré et corrigé (livraison #136) : une
# première version laissait `proxy_pass http://$backend;` SANS rien
# après la variable -- ambiguïté nginx documentée mais jamais
# vérifiable ici faute de nginx installable (voir docstring du
# module) sur ce qu'un `proxy_pass` à variable NUE transmet
# réellement ($uri, reflétant le rewrite, OU $request_uri, l'original
# JAMAIS modifié) -- en pratique, TOUTES les APIs recevaient leur
# propre préfixe (`/api/xxx/...`) en plus de leurs routes internes,
# provoquant un 500 systématique (pas un 404 propre -- une exception
# non gérée quelque part dans le traitement d'une route inconnue).
# $uri EXPLICITE lève toute ambiguïté : sa sémantique ("reflète les
# rewrite") est documentée sans détour, contrairement au comportement
# d'un proxy_pass à variable sans rien après.
#
# Le nom de variable ($backend) est réutilisable à l'identique dans
# CHAQUE location -- une requête ne traverse jamais qu'UN SEUL bloc
# location, aucun risque de collision entre elles malgré le même nom
# partout (comportement nginx standard, pas une portée par bloc comme
# dans un langage généraliste).
#
# PIÈGE RÉEL TROUVÉ ET CORRIGÉ (livraison #146, deux tentatives
# précédentes infructueuses -- #134/#136) : `set $backend` doit
# TOUJOURS précéder `rewrite ... break;`, jamais le suivre. `break`
# interrompt tout le traitement des directives de la phase de
# réécriture pour cette requête -- pas seulement les `rewrite`
# suivants, TOUTES les directives qui suivraient dans le même bloc, y
# compris un `set`. Avec l'ordre inverse (rewrite puis set, la
# version livrée en #134/#136), `$backend` restait perpétuellement
# non initialisée -- confirmé par les vraies traces nginx
# (`using uninitialized "backend" variable`, `no host in upstream`)
# fournies par la personne, seule preuve qui a permis de trouver ce
# piège après deux tentatives à l'aveugle. Explique d'ailleurs
# entièrement pourquoi SEULES les routes "api" (avec rewrite) étaient
# touchées, jamais les routes "spa"/"keycloak" (SPA_LOCATION_TEMPLATE
# ci-dessous, sans rewrite -- son `set` n'a jamais eu ce problème).
API_LOCATION_TEMPLATE = """\
    location {path} {{
        set $backend {service}:{container_port};
        rewrite ^{path}(.*)$ /$1 break;
        proxy_pass http://$backend$uri$is_args$args;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
    }}
"""

# SPA/Keycloak : préfixe CONSERVÉ -- AUCUN `rewrite` (contrairement à
# "api" ci-dessus) : sans rewrite, $uri reste le chemin ORIGINAL reçu
# tel quel, transmis explicitement (voir API_LOCATION_TEMPLATE
# ci-dessus pour le raisonnement complet sur pourquoi EXPLICITE,
# livraison #136). Vite (base dans vite.config.js) et Keycloak
# (KC_HTTP_RELATIVE_PATH) doivent connaître ce même préfixe de leur
# côté. WebSocket inclus (HMR Vite) -- partie non vérifiée en
# conditions réelles, voir docstring du module.
SPA_LOCATION_TEMPLATE = """\
    location {path} {{
        set $backend {service}:{container_port};
        proxy_pass http://$backend$uri$is_args$args;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
    }}
"""

# Résolution STATIQUE (livraison #238) -- réservée aux services en
# `network_mode: host` (network-agent-api, #233/#238 -- `ens18` de
# l'hôte invisible sinon). `proxy_pass` LITTÉRAL (jamais via
# `set $backend` + variable, contrairement aux deux gabarits
# ci-dessus) : **trouvaille réelle, vérifiée avant d'écrire une seule
# ligne de config** -- le résolveur DYNAMIQUE de nginx
# (`resolver 127.0.0.11`, utilisé PAR la variable `$backend`) ne
# consulte JAMAIS `/etc/hosts` (confirmé par la documentation nginx/
# Docker et un incident RÉEL équivalent chez un tiers, nginx-proxy-
# manager#5344) -- `extra_hosts: host.docker.internal` (voir
# gateway/docker-compose.yml) resterait donc SANS EFFET avec le
# gabarit dynamique. Un `proxy_pass` LITTÉRAL, lui, est résolu au
# CHARGEMENT de la config via le résolveur SYSTÈME standard (qui
# consulte bien /etc/hosts) -- fonctionne pour CE cas précis
# uniquement parce que la cible (l'hôte lui-même, via
# host.docker.internal) est TOUJOURS présente dès que Docker tourne,
# contrairement à un conteneur applicatif qui pourrait ne pas encore
# exister au démarrage de nginx (raison D'ÊTRE du gabarit dynamique
# pour tous les AUTRES services, voir docstring du module) -- perdre
# la ré-résolution à chaud est donc un compromis SANS RISQUE ici,
# jamais généralisable aux autres routes.
API_LOCATION_TEMPLATE_STATIC = """\
    location {path} {{
        rewrite ^{path}(.*)$ /$1 break;
        proxy_pass http://{service}:{container_port}$uri$is_args$args;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
    }}
"""

HEADER_TEMPLATE = """\
# Fichier GÉNÉRÉ par tls-proxy/render_nginx_conf.py — NE PAS ÉDITER À LA
# MAIN, les changements seraient perdus au prochain rendu. Modifier la
# liste SERVICES dans le script, ou GATEWAY_PORT dans .env, puis relancer.
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;

server {{
    listen {gateway_port} ssl;
    server_name _;

    # Résolveur DNS interne de Docker (adresse standard, fixe, sur
    # tout réseau défini par l'utilisateur -- voir docstring du
    # module pour le raisonnement complet). "valid=10s" : durée de
    # cache courte -- un conteneur recréé (nouvelle IP) redevient
    # joignable vite, sans attendre une éventuelle valeur TTL DNS plus
    # longue héritée par défaut.
    resolver 127.0.0.11 valid=10s;

    ssl_certificate     /etc/nginx/tls/server.crt;
    ssl_certificate_key /etc/nginx/tls/server.key;

    # Nginx limite par défaut à 1 Mo (client_max_body_size) -- bien en
    # dessous de tout dump de base de données réel. Bug réel rencontré
    # (erreur 413 systématique) : import mysqldump via DBA échouait dès
    # qu'un dump dépassait 1 Mo, alors que Flask (dba/api/app.py,
    # MAX_CONTENT_LENGTH) autorisait déjà 2 Go côté application -- le
    # goulot d'étranglement était ici, à la passerelle, invisible tant
    # qu'on ne teste pas avec un VRAI fichier volumineux. Alignée sur
    # cette même limite de 2 Go pour rester cohérente entre les deux
    # niveaux ; bénéficie aussi aux autres imports volumineux du projet
    # (export/import JSON tickets, restauration coffre-fort...).
    client_max_body_size 2G;

"""

FOOTER = "}\n"


def build_config(env):
    gateway_port = resolve_gateway_port(env)
    host_ip = resolve_host_ip(env)
    locations = []
    summary = [f"  Port unique (GATEWAY_PORT) : {gateway_port}", ""]
    seen_paths = {}
    for var_name, service, container_port, path, kind in SERVICES:
        if service == "__HOST_IP__":
            service = host_ip
        if path in seen_paths:
            raise ValueError(f"conflit de chemin : {path} déjà utilisé par {seen_paths[path]}")
        seen_paths[path] = service

        if kind == "api":
            template = API_LOCATION_TEMPLATE
        elif kind == "api-static":
            template = API_LOCATION_TEMPLATE_STATIC
        else:
            template = SPA_LOCATION_TEMPLATE
        locations.append(template.format(path=path, service=service, container_port=container_port))
        summary.append(f"  {path:<20} -> {service}:{container_port}  ({kind}, {var_name} historique)")

    config = HEADER_TEMPLATE.format(gateway_port=gateway_port) + "\n".join(locations) + FOOTER
    return config, summary


def main():
    check_only = "--check" in sys.argv
    env = parse_env(os.path.join(ROOT, ".env"))

    try:
        config, summary = build_config(env)
    except ValueError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    if check_only:
        print("Rendu vérifié (aucune écriture) :")
        print("\n".join(summary))
        return 0

    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write(config)
    except PermissionError:
        # Piège RÉEL rencontré (livraison #165) : ce fichier est
        # souvent créé une PREMIÈRE fois via `sudo
        # ./gateway/scripts/run.sh ...` (root), puis ce script est
        # ensuite appelé SANS sudo (ex. depuis scripts/chantier.sh,
        # livraison #162, qui régénère automatiquement après un
        # build) -- l'utilisateur normal ne peut alors plus écraser
        # un fichier appartenant à root. Message ACTIONNABLE plutôt
        # qu'une trace Python brute, incompréhensible pour qui ne
        # lit pas le code.
        rel = os.path.relpath(OUT, ROOT)
        print(f"ERREUR : permission refusée en écrivant {rel}", file=sys.stderr)
        print(
            "  Cause probable : ce fichier appartient à un autre utilisateur\n"
            "  (souvent root, si render_nginx_conf.py ou gateway/scripts/run.sh\n"
            "  a déjà tourné via sudo au moins une fois). Corriger avec :\n"
            f"    sudo chown $(id -u):$(id -g) {rel}\n"
            "  puis relancer cette commande.",
            file=sys.stderr,
        )
        return 1
    print(f"Config nginx rendue -> {os.path.relpath(OUT, ROOT)}")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
