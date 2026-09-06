// Logique PURE des historiques de l'agent réseau (présence d'un appareil,
// volume échangé entre deux appareils) : agrégation par relevé, calcul des
// deltas, disposition des barres. Aucun import React -- testable sous Node
// (voir tests/networkAgentHistory.test.mjs), même motif que ldapTree.js et
// networkCycleGraph.js.
//
// Contexte : l'API stocke des relevés CUMULATIFS (voir store.take_snapshot,
// "jamais un delta stocké") -- "calculer un delta entre deux points est la
// responsabilité de la lecture (hub)". C'est ici que cette responsabilité
// est tenue.

export function formatBytes(bytes) {
  if (typeof bytes !== "number" || !Number.isFinite(bytes)) return "?";
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} Go`;
}

// Regroupe les lignes brutes par relevé (`snapshot_at`) en sommant les
// volumes. Nécessaire pour `/links/history`, qui renvoie UNE ligne par
// (relevé, protocole, port) ; inoffensif pour `/presence-history` (une ligne
// par relevé, ou plusieurs si l'appareil a changé d'IP dans l'intervalle).
// Trié par date croissante quelle que soit l'ordre d'entrée.
export function aggregateBySnapshot(rows) {
  const byAt = new Map();
  for (const r of rows || []) {
    if (!r || !r.snapshot_at) continue;
    const cur = byAt.get(r.snapshot_at) || { at: r.snapshot_at, bytes: 0, packets: 0 };
    cur.bytes += Number(r.bytes_total) || 0;
    cur.packets += Number(r.packet_count) || 0;
    byAt.set(r.snapshot_at, cur);
  }
  return [...byAt.values()].sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0));
}

// Transforme des relevés cumulatifs en série de deltas.
// - Premier relevé : delta `null` (aucune base de comparaison), jamais 0 --
//   un 0 se lirait comme "rien n'a été échangé", ce qui est faux.
// - Delta négatif : le compteur a reculé (redémarrage de la capture, purge).
//   Le cumul courant est alors la meilleure estimation du volume échangé
//   depuis, et le point est marqué `reset: true` pour être affiché
//   différemment plutôt que silencieusement lissé.
export function computeDeltaSeries(rows) {
  const points = aggregateBySnapshot(rows);
  return points.map((p, i) => {
    if (i === 0) return { at: p.at, cumulative: p.bytes, packets: p.packets, delta: null, reset: false };
    const prev = points[i - 1];
    const raw = p.bytes - prev.bytes;
    if (raw < 0) return { at: p.at, cumulative: p.bytes, packets: p.packets, delta: p.bytes, reset: true };
    return { at: p.at, cumulative: p.bytes, packets: p.packets, delta: raw, reset: false };
  });
}

// Disposition des barres dans un cadre width x height. Les points sans delta
// (le premier) occupent leur place mais ne produisent pas de barre -- l'axe
// du temps reste régulier. Hauteur minimale de 1 pour un delta non nul mais
// trop petit pour être visible, 0 strict pour un delta nul.
export function buildBarLayout(series, width, height, gap = 2) {
  const n = series.length;
  if (n === 0 || width <= 0 || height <= 0) return { bars: [], max: 0 };
  const max = series.reduce((m, p) => (p.delta != null && p.delta > m ? p.delta : m), 0);
  const slot = width / n;
  const barW = Math.max(1, slot - gap);
  const bars = [];
  series.forEach((p, i) => {
    if (p.delta == null) return;
    let h = max > 0 ? (p.delta / max) * height : 0;
    if (p.delta > 0 && h < 1) h = 1;
    bars.push({
      x: i * slot + gap / 2,
      y: height - h,
      w: barW,
      h,
      index: i,
      at: p.at,
      delta: p.delta,
      cumulative: p.cumulative,
      reset: p.reset,
    });
  });
  return { bars, max };
}

// Total échangé sur la série (somme des deltas connus) -- ce que la personne
// veut lire en un coup d'oeil sous le graphique.
export function sumDeltas(series) {
  return series.reduce((a, p) => a + (p.delta || 0), 0);
}
