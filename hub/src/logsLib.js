// Gestionnaire de logs (hub), livraison #139 -- demandé explicitement
// ("un excellent moyen pour optimiser en déploiement et en
// fonctionnement"), avec les 3 présentations validées par la
// personne, dans l'ordre : par service, vue combinée, tableau de
// bord. Logique PURE ici (jamais d'accès réseau -- voir
// logsClient.js) : liste des services, fusion multi-services triée
// par horodatage, résumé par service pour le tableau de bord.
//
// Chemins RELATIFS (/api/<segment>/logs), jamais une URL absolue par
// service -- le hub tourne déjà sur la MÊME origine que les 15 APIs
// (même tls-proxy), inutile de dupliquer 15 variables d'environnement
// VITE_*_API_BASE_URL alors que le navigateur résout déjà
// correctement un chemin relatif contre l'origine courante -- exactement
// ce qu'il ferait de toute façon pour charger le hub lui-même.
//
// Liste et segments EXACTEMENT ceux de tls-proxy/render_nginx_conf.py
// (SERVICES, type "api") -- toute divergence romprait silencieusement
// le lien entre cette liste et le vrai routage. FIXE (les 15
// services internes) -- distincte des sources EXTERNES poussées
// (livraison #142, voir logsClient.js fetchPushedSources), qui
// n'existent qu'une fois découvertes à l'exécution, jamais une
// liste statique possible pour elles.
// Ordonnée par ordre ALPHABÉTIQUE de libellé (note pratique de la
// personne, livraison #199 -- "par défaut ordonner les listes par
// ordre alphabétique, à commencer par Logs/services") -- convention
// par défaut pour les listes de ce projet désormais, sauf ordre plus
// pertinent déjà en place ailleurs (ex. PROBABILITY_LEVELS/
// IMPACT_LEVELS dans CyberView.jsx restent ordonnées par sévérité,
// STATUS_ORDER par étape de traitement -- jamais alphabétisées à
// l'aveugle). `glpi`/`nebula` ajoutés au passage (livraisons #192,
// #196) -- manquaient de cette liste jusqu'ici. 12 SERVICES
// SUPPLÉMENTAIRES ajoutés en #351 (architecture/classifier/memory/
// netprobe/network-agent/relations/retro/rights/snmp/tasks/
// vault(vigilance)/backup-restore) -- trouvé en recoupant
// systématiquement cette liste contre docker-compose.yml, DÉRIVE
// RÉELLE constatée : ces services étaient invisibles dans le
// gestionnaire de logs du hub depuis leur création respective,
// jamais ajoutés ici au moment de leur livraison. `pixel-grid-bridge`
// (script en arrière-plan, aucune route HTTP /logs) et
// `vault-admin-api` (jamais routé par la passerelle publique,
// volontairement isolé) restent EXCLUS de cette liste précise --
// aucun chemin HTTP atteignable pour eux depuis le navigateur, voir
// prefs-api/log_archiver.py (KNOWN_LOG_SERVICES) pour leur couverture
// côté archivage persistant, qui lit Memcached directement plutôt
// que via HTTP.
export const LOG_SERVICES = [
  { id: "schema-analyzer", label: "Analyse de schémas", path: "/api/schema-analyzer/logs" },
  { id: "architecture", label: "Architecture réseau", path: "/api/architecture/logs" },
  { id: "cacti", label: "Cacti", path: "/api/cacti/logs" },
  { id: "classifier", label: "Classification", path: "/api/classifier/logs" },
  { id: "imap-client", label: "Client IMAP", path: "/api/imap-client/logs" },
  { id: "vault", label: "Coffre-fort", path: "/api/vault/logs" },
  { id: "dba", label: "DBA", path: "/api/dba/logs" },
  { id: "rights", label: "Droits", path: "/api/rights/logs" },
  { id: "rsyslog-listener", label: "Écoute syslog (UDP)", path: "/api/rsyslog-listener/logs" },
  { id: "network-agent", label: "Exploration réseau", path: "/api/network-agent/logs" },
  { id: "ged", label: "GED (documents)", path: "/api/ged/logs" },
  { id: "geo-import", label: "Geo-Import", path: "/api/geo-import/logs" },
  { id: "glpi", label: "GLPI", path: "/api/glpi/logs" },
  { id: "ipam", label: "IPAM", path: "/api/ipam/logs" },
  { id: "ldap-admin", label: "LDAP Admin", path: "/api/ldap-admin/logs" },
  { id: "memory", label: "Mémoire", path: "/api/memory/logs" },
  { id: "nebula", label: "Nebula", path: "/api/nebula/logs" },
  { id: "optick", label: "Optick", path: "/api/optick/logs" },
  { id: "owncloud", label: "Owncloud", path: "/api/owncloud/logs" },
  { id: "owncloud-search", label: "Owncloud Search", path: "/api/owncloud-search/logs" },
  { id: "pixel-grid", label: "Pixel Grid", path: "/api/pixel-grid/logs" },
  { id: "prefs", label: "Préférences (prefs-api)", path: "/api/prefs/logs" },
  { id: "relations", label: "Relations", path: "/api/relations/logs" },
  { id: "retro", label: "Rétro-ingénierie", path: "/api/retro/logs" },
  { id: "backup-restore", label: "Sauvegardes", path: "/api/backup-restore/logs" },
  { id: "snmp", label: "SNMP", path: "/api/snmp/logs" },
  { id: "netprobe", label: "Sondes réseau", path: "/api/netprobe/logs" },
  { id: "supervision", label: "Supervision", path: "/api/supervision/logs" },
  { id: "tasks", label: "Tâches", path: "/api/tasks/logs" },
  { id: "tickets", label: "Tickets", path: "/api/tickets/logs" },
  { id: "tts-gu", label: "TTS-GU", path: "/api/tts-gu/logs" },
  { id: "ssh-tunnels", label: "Tunnels SSH", path: "/api/ssh-tunnels/logs" },
  { id: "vigilance", label: "Vigilance", path: "/api/vigilance/logs" },
  { id: "zenoss", label: "Zenoss", path: "/api/zenoss/logs" },
];

/** Fusionne les résultats de plusieurs services (voir logsClient.js,
 * fetchAllServiceLogs) en une seule liste triée par horodatage
 * DÉCROISSANT (le plus récent en premier) -- pour la vue combinée.
 * DÉFENSIF : un service en échec (undefined/null/pas un tableau) est
 * simplement ignoré, jamais une exception qui viderait la vue entière
 * à cause d'UN SEUL service en panne -- particulièrement important
 * ici, l'outil doit justement rester utilisable QUAND des services
 * sont en panne (voir contexte : ce chantier a démarré en pleine
 * panne réelle du 01/09).
 *
 * `services` (livraison #142) : la liste à considérer, PARAMÈTRE
 * OBLIGATOIRE plutôt qu'un repli implicite sur LOG_SERVICES -- pour
 * les sources externes poussées, l'appelant doit explicitement
 * fournir la liste combinée (15 fixes + sources découvertes),
 * jamais un oubli silencieux qui ferait disparaître les sources
 * externes de la fusion.
 * `resultsByService` : { [serviceId]: entries[] | undefined }. Chaque
 * entrée de sortie porte `serviceId`/`serviceLabel` (résolus depuis
 * `services`) en plus des champs déjà présents (timestamp, level,
 * logger, message). */
export function mergeLogEntries(resultsByService, services) {
  const list = Array.isArray(services) ? services : [];
  const merged = [];
  for (const svc of list) {
    if (!svc || typeof svc.id !== "string") continue;
    const entries = resultsByService?.[svc.id];
    if (!Array.isArray(entries)) continue;
    for (const e of entries) {
      if (!e || typeof e.timestamp !== "number") continue;
      merged.push({ ...e, serviceId: svc.id, serviceLabel: svc.label });
    }
  }
  merged.sort((a, b) => b.timestamp - a.timestamp);
  return merged;
}

/** Résumé par service pour le tableau de bord -- nombre d'entrées par
 * niveau (WARNING/ERROR/CRITICAL...) et statut de la sonde elle-même
 * (le service a-t-il seulement répondu ?). DÉFENSIF, même principe
 * que mergeLogEntries : un service absent de `resultsByService` (ou
 * en erreur, `null`) est signalé `reachable: false`, jamais une
 * exception. Renvoie un tableau dans le MÊME ordre que `services`
 * (ordre d'affichage stable, jamais réordonné par le nombre
 * d'erreurs -- un service qui redevient sain ne doit pas sauter de
 * position, source de confusion pour un usage répété). `services` :
 * même raisonnement que mergeLogEntries ci-dessus (paramètre
 * obligatoire, jamais un repli implicite). */
export function summarizeLogEntries(resultsByService, services) {
  const list = Array.isArray(services) ? services : [];
  return list.map((svc) => {
    const entries = resultsByService?.[svc.id];
    if (!Array.isArray(entries)) {
      return { id: svc.id, label: svc.label, reachable: false, counts: {}, total: 0, mostRecent: null };
    }
    const counts = {};
    let mostRecent = null;
    for (const e of entries) {
      if (!e || typeof e.level !== "string") continue;
      counts[e.level] = (counts[e.level] || 0) + 1;
      if (typeof e.timestamp === "number" && (mostRecent === null || e.timestamp > mostRecent)) {
        mostRecent = e.timestamp;
      }
    }
    return { id: svc.id, label: svc.label, reachable: true, counts, total: entries.length, mostRecent };
  });
}
