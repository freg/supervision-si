// #913 : logique pure du suivi direct des tests de charge (poste-charge). Transforme les échantillons NDJSON
// poussés par l'agent (mesure « poste-charge-live ») en séries pour le graphe de tension et en état courant.
// Testé sous Node (hub/tests/chargeLive.test.mjs) ; aucun calcul enfoui dans le composant.

/** Échantillons bruts depuis live.data (objet {echantillons:[…]} ou liste directe). */
export function echantillons(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return Array.isArray(data.echantillons) ? data.echantillons : [];
}

/** Série de débit disque (Mo/s) dans le temps : l'effondrement du débit = disque qui cale. */
export function serieDisque(ech) {
  const pts = (ech || []).filter((e) => e && e.phase === "disque" && typeof e.mo_s === "number");
  if (!pts.length) return { points: [], moSMax: 0, tMax: 0 };
  const t0 = pts[0].t || 0;
  const points = pts.map((e) => ({ t: Math.max(0, (e.t || 0) - t0), mo_s: e.mo_s, sous: e.sous }));
  const moSMax = points.reduce((m, p) => (p.mo_s > m ? p.mo_s : m), 0);   // .reduce (pas Math.max(...) : grand volume)
  const tMax = points.reduce((m, p) => (p.t > m ? p.t : m), 0);
  return { points, moSMax, tMax };
}

/** Dernier échantillon « utile » (hors marqueurs début/fini) : phase, sous-phase, %, métrique, secondes. */
export function dernierEtat(ech) {
  const utiles = (ech || []).filter((e) => e && e.phase && e.phase !== "début" && e.phase !== "fini");
  return utiles.length ? utiles[utiles.length - 1] : null;
}

/** true si le flux contient le marqueur de fin (le test est terminé). */
export function estFini(ech) {
  return (ech || []).some((e) => e && e.phase === "fini");
}
