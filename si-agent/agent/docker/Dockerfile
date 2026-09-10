# si-agent en conteneur (livraison #430) -- image construite SUR L'HÔTE par
# deploy-docker.sh (rien à télécharger d'autre que l'image de base).
# Le conteneur tourne en --network host --pid host, avec le système de
# fichiers de l'hôte monté en lecture seule sous /host (SI_AGENT_HOST_ROOT) :
# l'agent lit le VRAI /etc, /var (journaux, reboot-required), les VRAIS
# disques, processus, ports et voisins ARP -- pas ceux du conteneur.
FROM python:3.12-slim

# iproute2 : ip / ss (vue réseau passive) ; procps : ps ; util-linux : lscpu,
# lsblk, last ; systemd : le binaire journalctl (lecture du journal de l'hôte
# par -D /host/var/log/journal, sans systemd qui tourne) ; login : who.
RUN apt-get update && apt-get install -y --no-install-recommends \
      iproute2 procps util-linux systemd login ca-certificates tcpdump \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/si-agent
COPY si_agent /opt/si-agent/si_agent
COPY plugins /opt/si-agent/plugins-bundled

ENV PYTHONPATH=/opt/si-agent \
    PYTHONUNBUFFERED=1 \
    SI_AGENT_HOST_ROOT=/host \
    SI_AGENT_CONFIG=/etc/si-agent/agent.json

# Plugins livrés copiés dans le volume au premier démarrage (désactivés), puis l'agent.
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "si_agent.agent", "--config", "/etc/si-agent/agent.json"]
