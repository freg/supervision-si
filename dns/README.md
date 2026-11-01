# DNS éditable (module du hub, livraison #656)

Choix de la personne (3 oct. 2026) : fournisseurs **Internet** OVH et Online/Scaleway avec **cache**, **intranet** (BIND, mises
à jour dynamiques RFC 2136 avec clé TSIG) en **fallback** ; Nebula hors contexte pour l'instant (à prévoir côté relais du
hub local au campus).

- Une zone = un nom + une liste ordonnée de fournisseurs (`ovh`, `scaleway`, `bind`). Une modification est appliquée à
  tous dans l'ordre ; un fournisseur Internet injoignable ne bloque pas l'intranet (état « dégradé », modification
  « partielle » rejouable : `POST /zones/<z>/replay`). Le cache (`records`) est la dernière lecture de chaque fournisseur,
  consultable sans réseau, rafraîchi à la demande (`GET /zones/<z>/records?refresh=1`), avec divergences signalées.
- Journal (`changes`) avant/après, auteur, résultat par fournisseur ; retour en arrière `POST /changes/<id>/revert`.
- Secrets : coffre des accès (`credentials-api`, jeton interne). Conventions : OVH = identifiant « app_key/consumer_key »,
  mot de passe = app secret ; Scaleway = mot de passe = secret key ; intranet = identifiant = nom de la clé TSIG, mot de
  passe = secret (serveur et algorithme dans la zone).
- Bascule de rôle « DNS » (si-agent-api, `DNS_API_URL`) : change l'enregistrement du rôle vers le candidat choisi ; le DNS
  intranet suit même quand Internet manque (c'est le « DNS secondaire en fallback » demandé). Bascule « keepalived » :
  commande `vrrp_set` aux agents des candidats (priorité haute sur l'élu, basse sur les autres, `keepalived -t` puis
  reload, sauvegarde de la configuration).

Vérifié : `dns/api/test_dns.py` (zones, cache et divergences, modification sur tous, fallback → partiel → rejeu, retour en
arrière, suppression ; signature OVH et flux, corps Scaleway, scripts nsupdate/dig avec HTTP et commandes simulés) ;
`si-agent/api/test_z_pra.py` (mécanismes dns et keepalived) ; `si-agent/agent/tests/test_vrrpctl.py`.
Non vérifié : API OVH/Scaleway réelles, BIND réel, keepalived réel, rendu navigateur, build de l'image.
