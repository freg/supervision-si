# ProjeQtOr (fork supervision-si) — gestion de projets intégrée au hub.
# Livraison #476. Voir projeqtor/README.md pour le raisonnement complet.
#
# Base php:8.3-apache (et pas 8.4) : l'extension `imap` (requise par
# ProjeQtOr pour récupérer les réponses par mail, voir src/readme.txt)
# est débarquée du noyau PHP en 8.4 — rester sur 8.3 tant que le fork
# n'a pas remplacé cet usage.
FROM php:8.3-apache

# Extensions requises par ProjeQtOr (src/readme.txt) : gd (graphiques
# des rapports), imap (mails), mbstring (UTF-8), mysqli + pdo_mysql
# (base), xml ; plus ldap (authentification sur l'annuaire du hub,
# livraison #476) et zip/curl (plugins, appels sortants).
# default-mysql-client : uniquement pour `mysqladmin ping` dans
# l'entrypoint (attente bornée de la base au premier démarrage).
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpng-dev libjpeg62-turbo-dev libfreetype6-dev \
      libldap2-dev \
      libc-client-dev libkrb5-dev \
      libonig-dev \
      libzip-dev libcurl4-openssl-dev libxml2-dev \
      default-mysql-client \
    && docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-configure imap --with-kerberos --with-imap-ssl \
    && docker-php-ext-install -j"$(nproc)" \
       gd imap ldap mbstring mysqli pdo_mysql xml zip curl \
    && rm -rf /var/lib/apt/lists/*

# Réglages PHP conseillés par ProjeQtOr (src/readme.txt) :
# max_input_vars > 2000 pour l'écran d'imputation réelle, 512M pour la
# génération PDF.
COPY projeqtor.ini /usr/local/etc/php/conf.d/projeqtor.ini

# Sources du fork — V13.1.0 vendorées TELLES QUELLES. Garder src/
# identique à l'archive upstream tant qu'aucune retouche d'ergonomie
# n'est livrée : un `diff -r` contre l'archive officielle montre alors
# exactement nos seules modifications (voir README.md, section Fork).
COPY src/ /var/www/html/projeqtor/

# Localisation du fichier de paramètres HORS de la portée web (conseil
# de sécurité explicite de src/readme.txt et tool/projeqtor.php).
# Écrit au BUILD (contenu constant), jamais dans src/ (voir ci-dessus).
# Le fichier de paramètres lui-même est généré au DÉMARRAGE par
# l'entrypoint, depuis les variables d'environnement, et jamais
# régénéré ensuite (les retouches faites via l'écran de configuration
# de ProjeQtOr sont préservées).
RUN echo '<?php $parametersLocation="/data/config/parameters.php";' \
      > /var/www/html/projeqtor/tool/parametersLocation.php \
    && mkdir -p /data \
    && chown -R www-data:www-data /var/www/html/projeqtor/cache \
                                  /var/www/html/projeqtor/files \
                                  /data

COPY docker-entrypoint.sh /usr/local/bin/projeqtor-entrypoint.sh
RUN chmod +x /usr/local/bin/projeqtor-entrypoint.sh

# Apache écoute sur 80 (port CONTENEUR, jamais publié sur l'hôte —
# tout passe par tls-proxy, chemin /projeqtor/, voir
# tls-proxy/render_nginx_conf.py).
ENTRYPOINT ["projeqtor-entrypoint.sh"]
CMD ["apache2-foreground"]
