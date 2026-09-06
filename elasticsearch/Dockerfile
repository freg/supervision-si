# Elasticsearch 5.6.16 -- version EXACTE requise par l'app ownCloud
# "search_elastic" (6.x non supporte par cette app, confirme via sa
# documentation). Image officielle du registre Elastic, jamais un
# mirroir tiers -- voir owncloud/search-api/README.md pour le detail
# de ce choix.
FROM docker.elastic.co/elasticsearch/elasticsearch:5.6.16

# ingest-attachment : SEUL pre-requis documente par search_elastic
# (extraction de texte via Apache Tika pour PDF/DOCX/XLSX/PPTX/ODT/ODS).
# --batch : installation non interactive (accepte automatiquement les
# permissions supplementaires que le plugin demande a l'installation).
RUN bin/elasticsearch-plugin install --batch ingest-attachment
