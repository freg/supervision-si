// Logique PURE de la tuile « Catalogue de positions » (livraison #429,
// backlog 67) -- aucun React, testée sous Node (hub/tests/geoCatalog.test.mjs).

export const STATUS_LABELS = { auto: "automatique", validated: "validée", corrected: "corrigée" };
export const SOURCE_LABELS = { geolocations: "saisie", ban: "BAN / Géoplateforme", commune: "commune", osm: "OpenStreetMap", human: "décision", nominatim: "Nominatim" };

export function confidenceTone(c) {
  if (c == null) return "neutral";
  if (c >= 80) return "good";
  if (c >= 50) return "warn";
  return "bad";
}

// Filtres : todo = automatiques peu sûres ou sans position ; auto ; decided ; all
export function filterPositions(rows, { view = "todo", q = "" } = {}) {
  const t = (q || "").trim().toLowerCase();
  return (rows || []).filter((p) => {
    if (view === "todo" && !(p.status === "auto" && (p.lat == null || (p.confidence ?? 0) < 80))) return false;
    if (view === "auto" && p.status !== "auto") return false;
    if (view === "decided" && p.status === "auto") return false;
    if (view === "unpositioned" && p.lat != null) return false;
    if (t && !`${p.label} ${p.key} ${(p.refs || []).map((r) => r.label).join(" ")} ${(p.links || []).map((l) => l.label).join(" ")}`.toLowerCase().includes(t)) return false;
    return true;
  });
}

// Tri : à traiter d'abord (auto, justesse croissante), puis décidées, puis nom.
export function sortPositions(rows) {
  const st = { auto: 0, validated: 1, corrected: 1 };
  return [...(rows || [])].sort((a, b) => (st[a.status] ?? 0) - (st[b.status] ?? 0) || (a.confidence ?? 0) - (b.confidence ?? 0) || String(a.label).localeCompare(String(b.label)));
}

export function summarize(rows) {
  const out = { total: 0, todo: 0, auto: 0, decided: 0, unpositioned: 0, links: 0 };
  for (const p of rows || []) {
    out.total += 1;
    if (p.status === "auto") out.auto += 1; else out.decided += 1;
    if (p.lat == null) out.unpositioned += 1;
    if (p.status === "auto" && (p.lat == null || (p.confidence ?? 0) < 80)) out.todo += 1;
    out.links += (p.links || []).length;
  }
  return out;
}

// Références affichées : dédoublonnées par source+libellé, la plus précise d'abord.
const PREC = ["manual", "validated", "housenumber", "poi", "osm", "street", "site", "locality", "municipality", "commune", "postcode", "stored", "unknown"];
export function orderedRefs(refs) {
  const seen = new Set();
  return [...(refs || [])].sort((a, b) => (PREC.indexOf(a.precision) === -1 ? 99 : PREC.indexOf(a.precision)) - (PREC.indexOf(b.precision) === -1 ? 99 : PREC.indexOf(b.precision)) || (b.score ?? 0) - (a.score ?? 0))
    .filter((r) => { const k = `${r.source}|${r.label}`; if (seen.has(k)) return false; seen.add(k); return true; });
}

export function fmtCoord(v) { return v == null ? "—" : Number(v).toFixed(5); }

// Emprise pour la carte : position + références (sans les aberrantes à > 200 km)
export function mapPoints(position) {
  const pts = [];
  if (position?.lat != null) pts.push({ lat: position.lat, lon: position.lon, kind: "position", label: position.label });
  for (const r of position?.refs || []) {
    if (r.lat == null) continue;
    if (position?.lat != null && Math.abs(r.lat - position.lat) + Math.abs(r.lon - position.lon) > 2) continue;
    pts.push({ lat: r.lat, lon: r.lon, kind: r.source, label: r.label, precision: r.precision });
  }
  return pts;
}

export function validCoords(lat, lon) {
  const a = Number(lat), b = Number(lon);
  return Number.isFinite(a) && Number.isFinite(b) && a >= -90 && a <= 90 && b >= -180 && b <= 180;
}
