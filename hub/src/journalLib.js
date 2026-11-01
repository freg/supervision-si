// Tuile « Journal des chantiers » (livraison #795) -- logique PURE, testée sous Node (hub/tests/journalLib.test.mjs).
// Données : si-agent-api /journal (entrées, chantiers, indicateurs), /journal/suggestions (événements du central).

export const NATURES = ["Acte", "Surveillance", "Relance", "Intervention"];
export const STATUTS = ["Fait", "En cours", "Planifié", "À faire"];
export const STATUT_TONE = { "Fait": "ok", "En cours": "info", "Planifié": "warning", "À faire": "critical" };
const JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
const BUREAU = [[8 * 60 + 30, 12 * 60 + 15], [14 * 60, 18 * 60]];

/** « 2026-10-20 » -> « 20/10/2026 ». */
export const fmtDay = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : "");

export function weekday(d) {
  if (!d) return "";
  const [y, m, j] = d.split("-").map(Number);
  return JOURS[new Date(Date.UTC(y, m - 1, j)).getUTCDay()];
}

const minutes = (hm) => (hm ? Number(hm.slice(0, 2)) * 60 + Number(hm.slice(3, 5)) : null);

/** Durée en minutes (fin après minuit acceptée), null si une heure manque. */
export function durationMin(e) {
  const a = minutes(e?.start), b = minutes(e?.end);
  if (a == null || b == null) return null;
  return b >= a ? b - a : b + 24 * 60 - a;
}

export const fmtDuration = (m) => (m == null ? "" : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`);

export const isWeekend = (d) => ["samedi", "dimanche"].includes(weekday(d));

/** Heure hors bureau (8 h 30 - 12 h 15, 14 h - 18 h) ou week-end. */
export function offHour(day, hm) {
  if (!day || !hm) return false;
  if (isWeekend(day)) return true;
  const m = minutes(hm);
  return !BUREAU.some(([a, b]) => a <= m && m <= b);
}

export const emptyEntry = (chantier = "") => ({ chantier, day: new Date().toISOString().slice(0, 10), start: "", end: "", nature: "Acte", acte: "", description: "", resultat: "", statut: "Fait", source: "" });

export const entryToForm = (e) => ({ ...emptyEntry(), ...Object.fromEntries(Object.entries(e || {}).map(([k, v]) => [k, v == null ? "" : v])) });

/** Filtre texte (début de mot prioritaire) + nature + statut. */
export function filterEntries(entries, { q = "", nature = "", statut = "" } = {}) {
  const t = q.trim().toLowerCase();
  return (entries || []).filter((e) => (!nature || e.nature === nature) && (!statut || e.statut === statut)
    && (!t || [e.acte, e.description, e.resultat, e.source, e.chantier].some((x) => (x || "").toLowerCase().includes(t))));
}

/** Contenu d'un fichier importé -> charge utile de POST /journal/import (JSON : liste ou {entries} ; sinon CSV). */
export function importPayload(text, fileName = "", chantier = "") {
  const s = (text || "").replace(/^﻿/, "").trim();
  if (fileName.toLowerCase().endsWith(".json") || s.startsWith("[") || s.startsWith("{")) {
    let data;
    try { data = JSON.parse(s); } catch { return { error: "JSON illisible" }; }
    const rows = Array.isArray(data) ? data : Array.isArray(data?.entries) ? data.entries : null;
    if (!rows) return { error: "JSON attendu : une liste d'entrées, ou {\"entries\": [...]}" };
    return { rows: rows.map((r) => ({ ...r, chantier: r.chantier || chantier })) };
  }
  if (!s) return { error: "fichier vide" };
  return { csv: s, chantier };
}

/** Totaux toutes chantiers confondus à partir de stats[] du serveur. */
export function totals(stats) {
  return (stats || []).reduce((t, s) => ({ lignes: t.lignes + s.lignes, fait: t.fait + s.fait, a_faire: t.a_faire + s.a_faire,
    weekend: t.weekend + s.weekend, hors_heures: t.hors_heures + s.hors_heures, minutes: t.minutes + s.minutes }),
  { lignes: 0, fait: 0, a_faire: 0, weekend: 0, hors_heures: 0, minutes: 0 });
}
