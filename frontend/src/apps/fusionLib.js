// Logique pure de la fusion IP/MAC — corrélation par IP entre les
// entrées renvoyées par ipam-api (/ip_list : ip, mac, hostname,
// subnet, state) et zenoss-api (/ip_list : ip, device, activeCount,
// maxSeverity, severityLabel, historyCount). Aucune dépendance
// React/DOM, testable seule.

export function normalizeText(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

/** Tri numérique par octets (10.0.0.2 avant 10.0.0.10), pas
 * alphabétique. Une IP mal formée (pas 4 octets) est repoussée en
 * fin de liste plutôt que de faire planter le tri. */
export function compareIp(a, b) {
  const pa = String(a).split(".").map(Number);
  const pb = String(b).split(".").map(Number);
  const validA = pa.length === 4 && pa.every((n) => Number.isFinite(n));
  const validB = pb.length === 4 && pb.every((n) => Number.isFinite(n));
  if (validA !== validB) return validA ? -1 : 1;
  if (!validA && !validB) return String(a).localeCompare(String(b));
  for (let i = 0; i < 4; i++) {
    if (pa[i] !== pb[i]) return pa[i] - pb[i];
  }
  return 0;
}

/**
 * Fusionne les entrées de deux (ou plus, via un objet extensible)
 * sources par IP. Chaque IP connue d'au moins une source donne UNE
 * ligne, avec la liste des sources qui la voient, le MAC (seul IPAM
 * en fournit actuellement), les noms d'hôte rencontrés (dédupliqués,
 * peuvent différer d'une source à l'autre — les deux sont gardés) et
 * le détail brut par source pour affichage contextuel.
 */
export function mergeIpSources(ipamEntries, zenossEntries) {
  const byIp = new Map();

  const ensureRow = (ip) => {
    if (!byIp.has(ip)) {
      byIp.set(ip, { ip, mac: null, hostnames: new Set(), sources: new Set(), ipam: null, zenoss: null });
    }
    return byIp.get(ip);
  };

  for (const e of ipamEntries || []) {
    const ip = (e.ip || "").trim();
    if (!ip) continue;
    const row = ensureRow(ip);
    row.sources.add("ipam");
    if (e.mac) row.mac = e.mac;
    if (e.hostname) row.hostnames.add(e.hostname);
    row.ipam = e;
  }

  for (const e of zenossEntries || []) {
    const ip = (e.ip || "").trim();
    if (!ip) continue;
    const row = ensureRow(ip);
    row.sources.add("zenoss");
    if (e.device) row.hostnames.add(e.device);
    row.zenoss = e;
  }

  return Array.from(byIp.values())
    .map((row) => ({
      ...row,
      hostnames: Array.from(row.hostnames),
      sources: Array.from(row.sources).sort(),
    }))
    .sort((a, b) => compareIp(a.ip, b.ip));
}

export function rowMatchesQuery(row, query) {
  const q = normalizeText(query).trim();
  if (!q) return true;
  const haystack = [row.ip, row.mac, ...row.hostnames, row.ipam?.description, row.ipam?.subnet]
    .filter(Boolean)
    .join(" ");
  return normalizeText(haystack).includes(q);
}

/** Filtre dédié à la colonne "Nom(s) d'hôte" — distinct de
 * rowMatchesQuery (recherche globale IP/MAC/hôte/description/subnet) :
 * ne regarde QUE les noms d'hôte, pour permettre d'isoler par exemple
 * un site ou une convention de nommage précise sans bruit des autres
 * champs. */
export function rowMatchesHostname(row, query) {
  const q = normalizeText(query).trim();
  if (!q) return true;
  return normalizeText((row.hostnames || []).join(" ")).includes(q);
}

/** Filtre dédié à la colonne "Alertes actives (Zenoss)" — sur le
 * libellé de sévérité ET le compte, pour retrouver par exemple "critical"
 * ou un nombre précis. Une ligne sans entrée Zenoss ne matche jamais un
 * texte non vide (cohérent : elle n'a rien à filtrer dessus). */
export function rowMatchesAlert(row, query) {
  const q = normalizeText(query).trim();
  if (!q) return true;
  if (!row.zenoss) return false;
  const haystack = `${row.zenoss.severityLabel || ""} ${row.zenoss.activeCount ?? ""}`;
  return normalizeText(haystack).includes(q);
}

export function filterRows(rows, { query = "", correlatedOnly = false, hostnameQuery = "", alertQuery = "" } = {}) {
  return rows.filter((row) => {
    if (correlatedOnly && row.sources.length < 2) return false;
    if (!rowMatchesQuery(row, query)) return false;
    if (!rowMatchesHostname(row, hostnameQuery)) return false;
    if (!rowMatchesAlert(row, alertQuery)) return false;
    return true;
  });
}

// --- Colonnes du tableau : visibilité et largeur réglables ----------
// Un seul endroit qui liste les colonnes (clé, libellé, largeur par
// défaut) — l'en-tête, chaque ligne et le panneau "⚙ Colonnes" en
// dérivent tous, jamais une liste dupliquée qui pourrait diverger.
export const FUSION_COLUMNS = [
  { key: "ip", label: "IP", defaultWidth: 130 },
  { key: "mac", label: "MAC", defaultWidth: 110 },
  { key: "hostnames", label: "Nom(s) d'hôte", defaultWidth: 220 },
  { key: "sources", label: "Sources", defaultWidth: 130 },
  { key: "subnet", label: "Subnet (IPAM)", defaultWidth: 140 },
  { key: "alerts", label: "Alertes actives (Zenoss)", defaultWidth: 180 },
  { key: "position", label: "Position", defaultWidth: 170 },
];

export const MIN_COLUMN_WIDTH = 60;
export const MAX_COLUMN_WIDTH = 600;

export function clampColumnWidth(px) {
  if (typeof px !== "number" || !Number.isFinite(px)) return MIN_COLUMN_WIDTH;
  return Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, Math.round(px)));
}

export function defaultColumnWidths() {
  const widths = {};
  for (const col of FUSION_COLUMNS) widths[col.key] = col.defaultWidth;
  return widths;
}

/** Nouvelle largeur pendant un glisser — pure, testable sans DOM (le
 * geste de souris lui-même reste dans FusionApp.jsx, seul ce calcul
 * l'est ici). `deltaX` : différence en pixels entre la position actuelle
 * du curseur et celle du début du glisser. */
export function computeResizedWidth(startWidth, deltaX) {
  return clampColumnWidth((startWidth ?? 0) + (deltaX ?? 0));
}

export function toggleColumnVisibility(hiddenSet, key) {
  const next = new Set(hiddenSet);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

export function visibleColumns(hiddenSet) {
  return FUSION_COLUMNS.filter((c) => !(hiddenSet || new Set()).has(c.key));
}

const ZENOSS_SEVERITY_CLASS = {
  5: "fusion-sev-critical",
  4: "fusion-sev-error",
  3: "fusion-sev-warning",
  2: "fusion-sev-info",
  1: "fusion-sev-debug",
  0: "fusion-sev-clear",
};

export function severityClass(maxSeverity) {
  return ZENOSS_SEVERITY_CLASS[maxSeverity] || "fusion-sev-unknown";
}

/**
 * Enrichit chaque ligne fusionnée avec sa position connue (si le
 * système de géolocalisation en a une pour cette IP) — jointure pure,
 * aucun appel réseau ici. `geolocations` : liste brute renvoyée par
 * GET /geolocations de pixel-grid-api ({localisation, latitude,
 * longitude, mapped}). Une ligne sans entrée connue reçoit
 * position=null (jamais scannée) plutôt qu'un objet vide trompeur.
 */
export function enrichWithGeolocation(rows, geolocations, matches = null) {
  const byIp = new Map((geolocations || []).map((g) => [g.localisation, g]));
  return rows.map((row) => {
    const geo = byIp.get(row.ip);
    if (geo) {
      return { ...row, position: { latitude: geo.latitude, longitude: geo.longitude, mapped: geo.mapped, source: "ip" } };
    }
    // #426 : position d'après le NOM d'hôte (correspondance appliquée --
    // auto / validée / manuelle -- vers une localisation avec coordonnées),
    // même sujet `ip:<ip>` que la tuile Supervision SI du hub.
    const m = matches && matches[`ip:${row.ip}`];
    if (m && APPLIED_MATCH_STATUSES.has(m.status) && m.latitude != null && m.longitude != null) {
      return { ...row, position: { latitude: m.latitude, longitude: m.longitude, mapped: true, source: "nom", localisation: m.localisation, status: m.status, score: m.score } };
    }
    return { ...row, position: null };
  });
}

export const APPLIED_MATCH_STATUSES = new Set(["auto", "validated", "manual"]);

/** Sujets pour /geolocations/resolve : une ligne sans position, avec au
 * moins un nom d'hôte -> {subject: "ip:<ip>", name: <premier nom>}. Les
 * lignes déjà positionnées ne sont pas renvoyées. */
export function nameResolveSubjects(rows) {
  return (rows || [])
    .filter((r) => !r.position?.mapped && (r.hostnames || []).length)
    .map((r) => ({ subject: `ip:${r.ip}`, name: r.hostnames[0], site: null }));
}

// --- Géocodage par code postal embarqué dans le nom d'hôte -----------
// Convention observée sur les noms réels de ce parc (ex.
// "BIO17-17300-ISLANDE-RB3011", "OFFICEDESFOSSESMOREAU-17000-CARDINAL-
// -R1841") : un code postal français à 5 chiffres apparaît comme
// segment isolé du nom. Extraction par motif, pas par position fixe
// (les noms n'ont pas tous le même nombre de segments) — un simple
// nombre à 5 chiffres délimité par des non-chiffres de part et
// d'autre, jamais un sous-ensemble d'un nombre plus long.
const POSTAL_CODE_RE = /(?<!\d)(\d{5})(?!\d)/;

/** Premier code postal à 5 chiffres trouvé dans le texte, ou null.
 * Ne valide PAS que c'est un vrai code postal existant (departements
 * francais 01-95, 971-976...) -- c'est le role de l'API commune en
 * aval : un faux positif ne renverra simplement aucune commune. */
export function extractPostalCode(text) {
  if (typeof text !== "string") return null;
  const m = text.match(POSTAL_CODE_RE);
  return m ? m[1] : null;
}

/** Premier code postal exploitable parmi les noms d'hôte d'une ligne
 * fusionnée (rows de mergeIpSources) -- null si aucun nom d'hôte n'en
 * contient. */
export function extractPostalCodeFromRow(row) {
  for (const hostname of row?.hostnames || []) {
    const code = extractPostalCode(hostname);
    if (code) return code;
  }
  return null;
}
