# radicale (livraison #664) -- serveur CalDAV / CardDAV (Python) du groupware : authentification LDAP, droits depuis le
# fichier généré par groupware-api (volume /config), collections dans /data. Servi par tls-proxy sous /dav/.
FROM python:3.12-slim
RUN pip install --no-cache-dir "radicale==3.5.10" "ldap3==2.9.1" "passlib[bcrypt]==1.7.4"
COPY groupware/radicale/entrypoint.sh /usr/local/bin/radicale-entrypoint.sh
RUN chmod +x /usr/local/bin/radicale-entrypoint.sh && mkdir -p /data/collections /config
EXPOSE 5232
CMD ["radicale-entrypoint.sh"]
