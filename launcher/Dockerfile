FROM python:3.12-slim

# CLI docker -- PAS du docker-in-docker (ce conteneur ne fait tourner
# aucun démon Docker à lui), juste le CLIENT parlant au démon de
# L'HÔTE via le socket monté (voir docker-compose.yml, service
# "launcher", volumes). C'est ce socket, pas ce paquet, qui donne le
# contrôle réel -- à traiter avec la même prudence qu'un accès root à
# l'hôte, puisque c'en est un en pratique.
RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# www/ copié EN PREMIER, launcher_core.py ajouté APRÈS dans cgi-bin/ --
# ordre important : launcher_core.py ne fait PAS partie de l'arbre
# source www/ (il vit à la racine de launcher/), l'inverser
# l'écraserait silencieusement s'il y avait jamais un fichier de même
# nom dans www/.
COPY launcher/www /app/www
COPY launcher/launcher_core.py /app/www/cgi-bin/launcher_core.py
RUN chmod +x /app/www/cgi-bin/launcher.cgi

WORKDIR /app/www
EXPOSE 8000

# Serveur CGI de la bibliothèque standard -- volontairement PAS Flask
# ici (contrairement à tous les autres services de ce projet) :
# demandé explicitement comme un "cgi", et http.server --cgi
# l'exécute au sens propre du terme (processus séparé par requête,
# variables d'environnement CGI), sans dépendance supplémentaire.
CMD ["python3", "-m", "http.server", "--cgi", "8000"]
