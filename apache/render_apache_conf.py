#!/usr/bin/env python3
"""
Génère la config Apache (UN SEUL VirtualHost, entrée unique par
chemin) depuis .env.

    python3 apache/render_apache_conf.py            # écrit generated/supervision-si.conf
    python3 apache/render_apache_conf.py --check    # affiche le mapping sans écrire

Devenu trivial depuis le passage à une entrée unique côté tls-proxy
(décidé en cours de session — voir tls-proxy/README.md) : Apache n'a
plus qu'UN port à relayer, pas 15. Le fichier généré reste néanmoins
généré plutôt qu'écrit à la main, pour ne jamais désynchroniser
GATEWAY_PORT entre .env et cette config.

ARCHITECTURE (décidée avec la personne) : Apache termine le TLS
lui-même et relaie EN HTTPS vers tls-proxy — Apache est sur une
machine séparée, à plusieurs pattes réseau, jamais de HTTP en clair
qui traverserait un vrai lien réseau. Apache doit donc faire confiance
à la même CA interne pour valider le certificat de tls-proxy côté
sortant (SSLProxyCACertificateFile).

TLS_PROXY_UPSTREAM_HOST (.env) : IP/nom que CETTE machine Apache doit
utiliser pour joindre tls-proxy — délibérément DISTINCT de HOST_IP
(qui sert au navigateur, potentiellement une IP différente si la
machine Docker est elle-même multi-pattes). Défaut : HOST_IP.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(HERE, "generated")
OUT = os.path.join(OUT_DIR, "supervision-si.conf")


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


VHOST_TEMPLATE = """\
# Fichier GÉNÉRÉ par apache/render_apache_conf.py — NE PAS ÉDITER À LA
# MAIN, les changements seraient perdus au prochain rendu. Modifier
# GATEWAY_PORT/TLS_PROXY_UPSTREAM_HOST dans .env puis relancer.
#
# Modules requis (Debian : `a2enmod <nom>` puis recharger Apache) :
#   ssl proxy proxy_http proxy_wstunnel rewrite
#
# Topologie : Apache sur une machine séparée (plusieurs pattes réseau),
# relais vers tls-proxy EN HTTPS (pas en clair) — voir apache/README.md.
# Entrée unique par chemin : un seul VirtualHost pour toute la
# plateforme, tls-proxy fait le routage interne par chemin.

Listen {port}

<VirtualHost *:{port}>
    ServerName {server_name}

    SSLEngine on
    SSLCertificateFile      {tls_dir}/server.crt
    SSLCertificateKeyFile   {tls_dir}/server.key
    SSLProtocol             -all +TLSv1.2
    SSLCipherSuite          HIGH:!aNULL:!MD5:!3DES
    SSLHonorCipherOrder     on

    # Connexion SORTANTE (Apache -> tls-proxy) en HTTPS elle aussi --
    # machine séparée, plusieurs pattes réseau, jamais de HTTP en
    # clair traversant un vrai lien réseau. Apache doit faire
    # confiance à la même CA interne que celle qui a signé le
    # certificat de tls-proxy (voir pki/README.md).
    SSLProxyEngine          on
    SSLProxyCACertificateFile {tls_dir}/ca.crt
    SSLProxyCheckPeerCN     on
    SSLProxyCheckPeerName   on

    ProxyPreserveHost On
    ProxyRequests     Off

    # WebSocket (HMR des serveurs de dev Vite : /app/, /, /tickets/)
    # -- inoffensif pour les APIs qui n'en ont pas besoin.
    RewriteEngine On
    RewriteCond %{{HTTP:Upgrade}} =websocket [NC]
    RewriteRule ^/?(.*) wss://{upstream_host}:{port}/$1 [P,L]

    ProxyPass        / https://{upstream_host}:{port}/
    ProxyPassReverse / https://{upstream_host}:{port}/

    ErrorLog  ${{APACHE_LOG_DIR}}/supervision-si-error.log
    CustomLog ${{APACHE_LOG_DIR}}/supervision-si-access.log combined
</VirtualHost>
"""


def main():
    check_only = "--check" in sys.argv
    env = parse_env(os.path.join(ROOT, ".env"))
    server_name = os.environ.get("APACHE_SERVER_NAME", env.get("APACHE_SERVER_NAME", "")).strip() or "supervision-si"
    tls_dir = os.environ.get("APACHE_TLS_DIR", env.get("APACHE_TLS_DIR", "")).strip() or "/etc/apache2/tls"
    port = os.environ.get("GATEWAY_PORT", env.get("GATEWAY_PORT", "")).strip() or "6443"
    upstream_host = os.environ.get("TLS_PROXY_UPSTREAM_HOST", env.get("TLS_PROXY_UPSTREAM_HOST", "")).strip()
    if not upstream_host:
        upstream_host = os.environ.get("HOST_IP", env.get("HOST_IP", "")).strip() or "localhost"

    config = VHOST_TEMPLATE.format(port=port, server_name=server_name, tls_dir=tls_dir, upstream_host=upstream_host)
    summary = [
        f"  Port unique      : {port}",
        f"  ServerName       : {server_name}",
        f"  Certificats dans : {tls_dir} (server.crt, server.key, ca.crt)",
        f"  tls-proxy joint via : https://{upstream_host}:{port}",
    ]

    if check_only:
        print("Rendu vérifié (aucune écriture) :")
        print("\n".join(summary))
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(config)
    print(f"Config Apache rendue -> {os.path.relpath(OUT, ROOT)}")
    print("\n".join(summary))
    print()
    print("Copier ce fichier sur la machine Apache, puis voir apache/README.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
