# docker-monitor/analysis/

Dossier où `docker-monitor-api` écrit son fichier d'analyse EXTERNE
(`docker-monitor-analysis.log` par défaut, voir `DOCKER_MONITOR_ANALYSIS_LOG`
dans `../README.md`) — monté en volume depuis `docker-compose.yml`,
survit à un redémarrage/une reconstruction du conteneur.

Contenu volontairement PAS versionné (voir `.gitignore` -- seul ce
`README.md` l'est) : c'est un journal généré à l'exécution, qui
grossit avec le temps, propre à chaque déploiement -- jamais un
contenu à committer.
