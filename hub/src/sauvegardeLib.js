// #930 : helpers purs de l'onglet « Sauvegarde » (confs logicielles + montages d'un poste) -- formats et synthèse,
// testés par hub/tests/sauvegardeLib.test.mjs.

/** Octets -> taille lisible (unités décimales, virgule décimale). */
export function octets(o) {
  if (o == null || !isFinite(o)) return "—";
  if (o >= 1e9) return `${(o / 1e9).toFixed(1).replace(".", ",")} Go`;
  if (o >= 1e6) return `${(o / 1e6).toFixed(1).replace(".", ",")} Mo`;
  if (o >= 1e3) return `${Math.round(o / 1e3)} ko`;
  return `${o} o`;
}

/** Une ligne de conf du tableau <-> texte multi-ligne (une clé / un dossier par ligne). */
export const lignes = (arr) => (arr || []).join("\n");
export const depuisLignes = (txt) => String(txt || "").split("\n").map((s) => s.trim()).filter(Boolean);

/** Synthèse d'un résultat de sauvegarde : appli(s), octets confs, octets dossiers, destinations ok/ko, archive. */
export function resume(resultat) {
  const r = resultat || {};
  const confs = r.confs || [];
  const dossiers = r.dossiers || [];
  const dest = r.destinations || [];
  return {
    apps: new Set([...confs.map((c) => c.app), ...dossiers.map((d) => d.app)]).size,
    cles: confs.length,
    octetsConfs: confs.reduce((s, c) => s + (Number(c.octets) || 0), 0),
    octetsDossiers: dossiers.reduce((s, d) => s + (Number(d.octets) || 0), 0),
    destinationsOk: dest.filter((d) => d.ok).length,
    destinationsKo: dest.filter((d) => !d.ok).length,
    archive: r.archive && r.archive.nom ? r.archive : null,
  };
}
