// Logique pure du portail — extraite pour être testable isolément en
// Node (convention du projet). AUCUN Math.min(...spread)/Math.max(...spread)
// ici : plantage connu sur grands tableaux, toujours .reduce().

export const ROLE_LABELS = {
  admin: "Administrateur",
  demandeur: "Demandeur",
  technicien: "Technicien",
  politique: "Politique",
};

export const ROLE_ACCENTS = {
  admin: "#8e44ad",
  demandeur: "#2980b9",
  technicien: "#27ae60",
  politique: "#d35400",
};

// Ordre d'affichage stable du sélecteur de rôle (pas l'ordre
// d'apparition dans le token Keycloak, qui n'est pas garanti).
export const ROLE_ORDER = ["demandeur", "technicien", "politique", "admin"];

// Groupes Keycloak (realm supervision-si) -> rôle applicatif du
// portail. PIVOT fait après un bug Keycloak documenté de longue date
// (KEYCLOAK-3469) : les rôles realm HÉRITÉS d'un groupe ne remontent
// pas toujours de façon fiable dans realm_access.roles du jeton —
// alors que l'appartenance aux groupes elle-même (claim "groups",
// mapper dédié ajouté côté Keycloak) s'est révélée fiable en
// conditions réelles (rôles absents malgré des groupes visiblement
// corrects). Le sélecteur de vues s'appuie donc sur les GROUPES,
// jamais sur les rôles calculés par Keycloak. Mêmes clés que
// hub/src/lib.js (GROUP_TO_ROLE), sans "supervision" ici — ce n'est
// pas une vue du portail, juste un accès à un autre front.
export const GROUP_TO_ROLE = {
  administrateurs: "admin",
  demandeurs: "demandeur",
  techniciens: "technicien",
  direction: "politique",
};

/** Convertit une liste de groupes Keycloak bruts en rôles du portail
 * connus — ignore tout groupe non mappé (ex. "supervision", propre au
 * hub, ou tout autre groupe futur sans équivalence ici). Jamais
 * d'exception sur une entrée absente/malformée. */
export function groupsToPortalRoles(groups) {
  if (!Array.isArray(groups)) return [];
  return groups.map((g) => GROUP_TO_ROLE[g]).filter(Boolean);
}

/** Ensemble des rôles auxquels cette personne a accès dans le portail
 * -- le rôle LOCAL (compte tickets, `users.role`, toujours présent et
 * prioritaire pour l'identité "réelle" de la personne) PLUS tout rôle
 * dérivé des groupes Keycloak dont elle est membre (ex. appartenance à
 * plusieurs groupes, cas d'un compte de test/administration). Toujours
 * au moins 1 élément, jamais de doublon, ordre stable (ROLE_ORDER)
 * plutôt que l'ordre d'arrivée. Le rôle local n'a PAS à être un rôle
 * connu pour ne pas planter (defensive, même si users.role ne devrait
 * en pratique contenir que les 4 valeurs connues). */
export function computeAccessibleRoles(localRole, groups) {
  const groupRoles = groupsToPortalRoles(groups);
  const set = new Set([localRole, ...groupRoles].filter((r) => r in ROLE_LABELS));
  return ROLE_ORDER.filter((r) => set.has(r));
}

export function normalizeText(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

// Bornes temporelles de lignes Gantt [{time_entries:[{start_ts,end_ts}]}]
// -> {min, max} ou null si aucun segment.
export function ganttBounds(rows) {
  const acc = (rows || []).reduce(
    (m, row) =>
      (row.time_entries || []).reduce(
        (m2, e) => ({
          min: Math.min(m2.min, e.start_ts),
          max: Math.max(m2.max, e.end_ts),
        }),
        m
      ),
    { min: Infinity, max: -Infinity }
  );
  if (acc.min === Infinity || acc.max <= acc.min) {
    return acc.min === Infinity ? null : { min: acc.min, max: acc.min + 1 };
  }
  return acc;
}

// Position/largeur en % d'un segment dans les bornes données.
export function segmentGeometry(entry, bounds) {
  const span = bounds.max - bounds.min;
  const left = ((entry.start_ts - bounds.min) / span) * 100;
  const width = Math.max(((entry.end_ts - entry.start_ts) / span) * 100, 0.4);
  return { left, width };
}

// Filtre des lignes Gantt sur le libellé (insensible casse/accents).
export function filterGanttRows(rows, query) {
  const q = normalizeText(query).trim();
  if (!q) return rows;
  return (rows || []).filter((r) => normalizeText(r.subject).includes(q));
}

// Valeur max d'une série de stats [{label, value}] — pour les barres.
export function statsMax(rows) {
  return (rows || []).reduce((m, r) => Math.max(m, r.value || 0), 0);
}

export function fmtDuration(seconds) {
  const s = Math.round(seconds || 0);
  if (s < 60) return `${s} s`;
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, "0")}`;
}

export function fmtTs(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtTsShort(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

// Journal d'état -> étapes lisibles pour la frise "évolution".
export function statusLogSteps(log) {
  const labels = { opened: "Ouvert", closed: "Fermé", reopened: "Rouvert" };
  return (log || []).map((e) => ({
    label: labels[e.event_type] || e.event_type,
    kind: e.event_type,
    ts: e.ts,
  }));
}

// datetime-local -> epoch secondes (null si vide/invalide).
export function datetimeLocalToTs(value) {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isNaN(ms) ? null : Math.round(ms / 1000);
}

// --- Tableau triable (vue Demandeur) ----------------------------------

export const TICKET_SORT_COLUMNS = {
  state: "état (ouvert d'abord)",
  subject: "sujet",
  statut_label: "statut",
  ts_created: "créée le",
  last_change: "dernière activité",
};

/** Comparateur générique une colonne, direction donnée — "state" est
 * une colonne synthétique (pas une vraie colonne API) : ouvert avant
 * fermé, c'est le tri PAR DÉFAUT demandé ("en priorité les tickets
 * ouverts"), pas juste une option parmi d'autres. */
export function sortTickets(tickets, sortKey, sortDir = "asc") {
  const dir = sortDir === "desc" ? -1 : 1;
  const rows = [...(tickets || [])];
  rows.sort((a, b) => {
    let cmp;
    if (sortKey === "state") {
      // ouvert (ts_closed null) = 0, ferme = 1 -> ouvert vient avant
      cmp = (a.ts_closed ? 1 : 0) - (b.ts_closed ? 1 : 0);
    } else if (sortKey === "subject" || sortKey === "statut_label") {
      cmp = normalizeText(a[sortKey] || "").localeCompare(normalizeText(b[sortKey] || ""));
    } else {
      cmp = (a[sortKey] || 0) - (b[sortKey] || 0);
    }
    return cmp * dir;
  });
  return rows;
}

/** Bascule de tri au clic sur un en-tête — même colonne -> inverse la
 * direction ; nouvelle colonne -> ordre par défaut le plus utile pour
 * elle (dates : plus récent d'abord ; état : ouvert d'abord = asc). */
export function nextSortState(current, clickedKey) {
  if (current.key !== clickedKey) {
    const defaultDir = clickedKey === "ts_created" || clickedKey === "last_change" ? "desc" : "asc";
    return { key: clickedKey, dir: defaultDir };
  }
  return { key: clickedKey, dir: current.dir === "asc" ? "desc" : "asc" };
}

// --- Tri par mots-clés (vue Technicien) --------------------------------

/** Tri par score de mots-clés décroissant, PUIS le tri déjà en place
 * côté serveur préservé pour départager (jamais un ré-ordonnancement
 * total qui ferait perdre le tri urgence/attente existant — "en plus",
 * pas "à la place", comme demandé). */
export function sortByKeywordScore(tickets) {
  return [...(tickets || [])].sort((a, b) => (b.keyword_score || 0) - (a.keyword_score || 0));
}

// --- Recopie d'un ticket existant (vue Demandeur) -----------------------

/** Extrait les champs RÉUTILISABLES d'un ticket existant pour
 * préremplir le formulaire de nouvelle demande -- "recopier", demandé
 * explicitement (s'inspirer/repartir d'un ancien ticket ressemblant).
 * Jamais l'id/les dates/le statut -- uniquement ce qui a du sens à
 * reprendre tel quel pour une NOUVELLE demande. Jamais d'exception
 * même sur un ticket incomplet/malformé -- valeurs de repli sûres. */
export function ticketToDraftFields(ticket) {
  if (!ticket) return { subject: "", description: "", typeId: "", siteId: "" };
  return {
    subject: ticket.subject || "",
    description: ticket.description || "",
    typeId: ticket.type_id != null ? String(ticket.type_id) : "",
    // Un ticket similaire concerne souvent le même site -- repris par
    // "recopier" comme le type, jamais imposé (juste une base à
    // ajuster, comme les autres champs de ce brouillon).
    siteId: ticket.site_id != null ? String(ticket.site_id) : "",
  };
}

// --- "Élastique de temps" (vue Technicien, panneau priorités) ----------
//
// Trois perspectives à combiner (précisé explicitement après un
// premier essai insuffisant) :
//   1. temps depuis la demande SANS prise en charge (wait_seconds,
//      déjà disponible -- voir ticketsByLongestWait)
//   2. temps depuis la prise en charge -- PAS ENCORE TRACÉ côté
//      backend (aucun événement "pris en charge" dans
//      ticket_status_log, seulement opened/closed/reopened) --
//      nécessite une clarification avant de construire quoi que ce
//      soit, voir tickets/README.md
//   3. temps restant avant l'échéance -- voir deadlineUrgency

/** Rangs de niveau DISTINCTS, triés décroissant (le plus urgent en
 * premier) -- à partir de la liste COMPLÈTE des niveaux connus
 * (`refs.levels`, jamais seulement ceux présents dans les tickets
 * actuellement filtrés/affichés), pour que la correspondance J+N par
 * POSITION (voir impliedDeadlineTs) reste stable quel que soit le
 * filtre actif à l'écran. */
export function distinctRanksDesc(levels) {
  const ranks = [...new Set((levels || []).map((l) => l.rank))];
  return ranks.sort((a, b) => b - a);
}

/** Correspondance J+N par POSITION de rang (du plus urgent au moins
 * urgent) -- décrite explicitement pour la version BÊTA actuelle :
 * "confondu avec la priorité" (forte=J+0, moyenne=J+1, faible=J+10,
 * notification="à faire un jour", pas encore de délai défini).
 * Jamais basé sur le LIBELLÉ du niveau (fragile si renommé) --
 * uniquement sa POSITION parmi les rangs distincts. Amenée à changer
 * (version intermédiaire : délai modifiable ; version affinée :
 * paramétré par type de tâche -- voir tickets/README.md). */
export const BETA_DEADLINE_OFFSET_DAYS_BY_RANK_POSITION = [0, 1, 10];

/** Échéance IMPLICITE (bêta) déduite du niveau -- épinglée à la
 * CRÉATION du ticket, selon la position de son rang parmi tous les
 * rangs distincts connus. `null` si le rang ne correspond à aucune
 * position couverte (ex. "Notification", 4e position -- pas encore
 * de délai défini, jamais un chiffre inventé) ou si le ticket n'a pas
 * de niveau du tout. */
export function impliedDeadlineTs(ticket, sortedDistinctRanksDesc, offsetsByPosition = BETA_DEADLINE_OFFSET_DAYS_BY_RANK_POSITION) {
  if (!ticket || ticket.level_rank == null || ticket.ts_created == null) return null;
  const position = (sortedDistinctRanksDesc || []).indexOf(ticket.level_rank);
  if (position === -1 || position >= offsetsByPosition.length) return null;
  return ticket.ts_created + offsetsByPosition[position] * 86400;
}

/** Urgence liée à l'échéance d'un ticket -- ratio 0..1 (0 = loin de
 * l'échéance, 1 = échéance dépassée ou toute proche). Utilise
 * `deadline_ts` s'il est EXPLICITEMENT saisi (signal le plus fort,
 * la personne l'a choisi elle-même) ; à défaut, retombe sur
 * l'échéance IMPLICITE déduite du niveau (voir impliedDeadlineTs) --
 * reflète la réalité bêta actuelle où très peu de tickets ont une
 * échéance explicite, l'urgence perçue vient presque toujours du
 * niveau seul. Fenêtre de référence : 48h avant échéance -- au-delà,
 * `null` (rien d'urgent à montrer). */
export function deadlineUrgency(ticket, nowTs, options = {}) {
  const { windowHours = 48, sortedDistinctRanksDesc = [], offsetsByPosition = BETA_DEADLINE_OFFSET_DAYS_BY_RANK_POSITION } = options;
  if (!ticket || ticket.ts_closed) return null;
  const implied = ticket.deadline_ts == null;
  const effectiveDeadline = implied
    ? impliedDeadlineTs(ticket, sortedDistinctRanksDesc, offsetsByPosition)
    : ticket.deadline_ts;
  if (effectiveDeadline == null) return null;
  const hoursRemaining = (effectiveDeadline - nowTs) / 3600;
  if (hoursRemaining > windowHours) return null;
  const ratio = Math.max(0, Math.min(1, 1 - hoursRemaining / windowHours));
  return { hoursRemaining, ratio, overdue: hoursRemaining < 0, implied };
}

/** Liste des tickets ayant une échéance (explicite ou implicite)
 * proche/dépassée, triés du plus urgent au moins urgent -- pour le
 * panneau "priorités et élastiques de temps" (vue Technicien).
 * Jamais les tickets fermés ni sans échéance calculable. */
export function ticketsByDeadlineUrgency(tickets, nowTs, options = {}) {
  return (tickets || [])
    .map((t) => ({ ticket: t, urgency: deadlineUrgency(t, nowTs, options) }))
    .filter((e) => e.urgency !== null)
    .sort((a, b) => a.urgency.hoursRemaining - b.urgency.hoursRemaining);
}

/** Tickets les plus longtemps SANS prise en charge (wait_seconds déjà
 * fourni par /queue) -- perspective 1 des "élastiques de temps",
 * jamais les tickets fermés (déjà pris en charge par construction).
 * Triés du plus longtemps en attente au moins longtemps, limité à
 * `n` pour rester un aperçu, pas une liste exhaustive redondante avec
 * la file elle-même. */
export function ticketsByLongestWait(tickets, n = 5) {
  return [...(tickets || [])]
    .filter((t) => !t.ts_closed)
    .sort((a, b) => (b.wait_seconds || 0) - (a.wait_seconds || 0))
    .slice(0, n);
}

/** Tickets actuellement pris en charge (first_in_progress_ts défini,
 * ticket toujours ouvert) -- perspective 2 des "élastiques de temps",
 * enfin disponible (voir statuts.type, tickets/api/app.py -- premier
 * passage à un statut de type en_cours). Triés du plus longtemps pris
 * en charge au moins longtemps -- le first_in_progress_ts le plus
 * ancien en premier. Jamais les tickets fermés, ni ceux jamais pris
 * en charge (first_in_progress_ts encore null -- couverts par
 * ticketsByLongestWait ci-dessus, perspective 1). */
export function ticketsByLongestInProgress(tickets, n = 5) {
  return [...(tickets || [])]
    .filter((t) => !t.ts_closed && t.first_in_progress_ts != null)
    .sort((a, b) => a.first_in_progress_ts - b.first_in_progress_ts)
    .slice(0, n);
}

/** Regroupe les tickets par niveau (priorité) -- pour le panneau
 * "priorités" (vue Technicien) : combien de tickets à chaque niveau,
 * triés du plus urgent (rank le plus élevé) au moins urgent. Un
 * ticket sans niveau va sous la clé "(sans niveau)", jamais ignoré
 * silencieusement. */
export function groupByLevel(tickets) {
  const groups = new Map();
  for (const t of tickets || []) {
    const key = t.level_label || "(sans niveau)";
    const rank = t.level_rank ?? -1;
    if (!groups.has(key)) groups.set(key, { label: key, rank, count: 0 });
    groups.get(key).count++;
  }
  return [...groups.values()].sort((a, b) => b.rank - a.rank);
}

// --- Import demandeurs (groupe local complémentaire) --------------------

/** Fusionne les résultats de deux imports Keycloak (route
 * /users/import-keycloak-group, appelée une fois par groupe) pour
 * un affichage combiné -- "demandeurs" (LDAP) toujours tenté,
 * `localResult` uniquement si un groupe local est configuré (peut
 * être `null`, jamais une exception). Concatène created/skipped,
 * jamais un doublon d'un même login créé par les deux appels (n'
 * arrive normalement jamais -- un login déjà créé par le premier
 * import ressort "skipped" au second -- mais dédoublonné ici par
 * prudence, pour ne jamais afficher un compte deux fois dans le
 * bilan). */
export function mergeImportResults(mainResult, localResult) {
  const created = [...new Set([...(mainResult?.created || []), ...(localResult?.created || [])])];
  const skipped = [...new Set([...(mainResult?.skipped || []), ...(localResult?.skipped || [])])];
  const totalInGroup = (mainResult?.total_in_group || 0) + (localResult?.total_in_group || 0);
  return { created, skipped, total_in_group: totalInGroup };
}
