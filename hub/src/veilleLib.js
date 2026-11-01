// Tuile « Veille cyber » (livraison #814) : fonctions pures (tests : tests/veilleLib.test.mjs).

/** Règle de filtre -> paramètres d'URL de /veille/articles et /veille/extraction (vides omis). */
export function paramsRegle(r = {}) {
  const p = new URLSearchParams();
  for (const k of ["categories", "niveaux", "prefiltres", "publics", "statuts", "sources"]) if (r[k]?.length) p.set(k, r[k].join(","));
  if (r.texte?.trim()) p.set("texte", r.texte.trim());
  p.set("jours", String(r.jours || 30));
  for (const k of ["cve", "nos_modeles", "non_lus", "suivis", "impacts"]) if (r[k]) p.set(k, "1");
  if (r.rejetes === "avec" || r.rejetes === "seuls") p.set("rejetes", r.rejetes);
  return p.toString();
}

const MOTS_VIDES = new Set(["dans", "pour", "avec", "sans", "sous", "entre", "after", "with", "from", "this", "that", "your", "their", "about", "les", "des", "une", "aux"]);
/** #820 rejet par mots-clés : mots saillants d'un titre (3 plus longs, hors mots vides), proposés à l'utilisateur. */
export function motsCles(titre = "", n = 3) {
  const vus = new Set();
  return (titre.match(/[\p{L}][\p{L}\p{N}._-]{3,}/gu) || [])
    .filter((m) => { const k = m.toLowerCase(); if (MOTS_VIDES.has(k) || vus.has(k)) return false; vus.add(k); return true; })
    .sort((x, y) => y.length - x.length).slice(0, n).join(" ");
}

/** Bascule d'une valeur dans une liste (puces). */
export function basculer(liste = [], v) {
  return liste.includes(v) ? liste.filter((x) => x !== v) : [...liste, v];
}

/** « a, b ; c » -> ["a", "b", "c"] sans doublons ni vides. */
export function termes(texte) {
  return [...new Set(String(texte || "").split(/[,;\n]/).map((x) => x.trim()).filter(Boolean))];
}

/** Date courte : « 21/10 14:05 » cette année, « 21/10/2025 » sinon. */
export function dateCourte(ts, maintenant = new Date()) {
  if (!ts) return "—";
  const d = new Date(ts * 1000), p = (x) => String(x).padStart(2, "0");
  return d.getFullYear() === maintenant.getFullYear() ? `${p(d.getDate())}/${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}` : `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/** Ton (np-tone) d'un article : rouge s'il touche notre SI en P1 ou cite nos modèles en alerte, orange s'il touche le SI. */
export function ton(a = {}) {
  const imp = a.impacts || {};
  if ((imp.actifs?.length && (imp.priorite === "P1" || a.niveau === "exploitee" || a.niveau === "alerte")) || (a.nos_modeles?.length && a.niveau)) return "bad";
  if (imp.actifs?.length || a.nos_modeles?.length) return "warn";
  return "neutral";
}

/** « Chez nous » : texte court des actifs touchés (« srv-a, srv-b +3 (P1) ») ou chaîne vide. */
export function chezNous(imp = {}, max = 2) {
  const a = imp.actifs || [];
  if (!a.length) return "";
  return `${a.slice(0, max).join(", ")}${a.length > max ? ` +${a.length - max}` : ""}${imp.priorite ? ` (${imp.priorite})` : ""}`;
}

/** EPSS en pourcentage lisible (0.9731 -> « 97 % »), « — » sinon. */
export function fmtEpss(v) {
  if (v == null || Number.isNaN(Number(v))) return "—";
  const p = Number(v) * 100;
  return `${p >= 10 ? Math.round(p) : p.toFixed(1).replace(".", ",")} %`;
}
