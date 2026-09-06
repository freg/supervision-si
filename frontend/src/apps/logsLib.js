// Logique pure du module Logs — fusion multi-services, tri, priorisation
// pour le bandeau replié. Aucune dépendance à import.meta.env ici, pour
// rester testable via un simple script Node (même convention que
// zenossLib.js/geolocationLib.js).

const LEVEL_RANK = { CRITICAL: 5, ERROR: 4, WARNING: 3, INFO: 2, DEBUG: 1 };

export function levelRank(level) {
  return LEVEL_RANK[level] ?? 0;
}

/** Fusionne les résultats par service ({service, entries, error}) en
 * une seule liste triée par timestamp décroissant (plus récent
 * d'abord). Une entrée de niveau inconnu est conservée (rang 0),
 * jamais filtrée silencieusement — mieux vaut un log mal classé que
 * perdu. */
export function mergeLogEntries(perServiceResults) {
  const merged = [];
  for (const result of perServiceResults || []) {
    for (const entry of result?.entries || []) {
      merged.push(entry);
    }
  }
  merged.sort((a, b) => (b?.timestamp ?? 0) - (a?.timestamp ?? 0));
  return merged;
}

/** Sélectionne `count` entrées à afficher en priorité pour le bandeau
 * replié : les ERROR/CRITICAL d'abord, puis complète avec le reste —
 * dans les deux groupes, l'ordre déjà trié par timestamp décroissant
 * de `entries` est préservé (pas re-trié ici : fonction pure simple,
 * ne dépend que de l'ordre déjà établi par mergeLogEntries). */
export function pickPriorityEntries(entries, count) {
  const errors = (entries || []).filter((e) => levelRank(e.level) >= LEVEL_RANK.ERROR);
  const rest = (entries || []).filter((e) => levelRank(e.level) < LEVEL_RANK.ERROR);
  return [...errors, ...rest].slice(0, count);
}

export function countByLevel(entries) {
  const counts = { CRITICAL: 0, ERROR: 0, WARNING: 0, INFO: 0, DEBUG: 0 };
  for (const e of entries || []) {
    if (e?.level in counts) counts[e.level] += 1;
  }
  return counts;
}

export function fmtLogTimestamp(ts) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  return new Date(ts * 1000).toLocaleTimeString("fr-FR", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}
