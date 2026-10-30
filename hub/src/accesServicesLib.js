// #928 : helpers purs de l'onglet « Accès services » (temps d'accès aux services d'un poste) -- formats et synthèse,
// testés par hub/tests/accesServicesLib.test.mjs.

/** Millisecondes -> secondes en français (virgule décimale) ; « — » si inconnu. */
export const secondes = (ms) => (ms == null ? "—" : `${(ms / 1000).toFixed(2).replace(".", ",")} s`);

/** Ton d'un code HTTP : vert < 300, orange 3xx, rouge >= 400. */
export const codeTon = (c) => (c == null ? "" : c >= 400 ? "bad" : c >= 300 ? "warn" : "good");

/** Synthèse d'un résultat : nb de sites, injoignables, identifiants refusés, lents (brut ou auth). */
export function resume(resultat) {
  const sites = (resultat && resultat.sites) || [];
  const r = { sites: sites.length, injoignables: 0, refuses: 0, lents: 0, authentifies: 0 };
  for (const s of sites) {
    const b = s.brut || {}, a = s.authentifie;
    if (b.erreur) r.injoignables += 1;
    if (a) {
      r.authentifies += 1;
      if (a.connecte === false) r.refuses += 1;
    }
    const lentBrut = !b.erreur && typeof b.total_ms === "number" && b.total_ms >= 2000;
    const lentAuth = a && !a.erreur && typeof a.total_ms === "number" && a.total_ms >= 5000;
    if (lentBrut || lentAuth) r.lents += 1;
  }
  return r;
}
