// Filtre texte commun (livraison #562) -- note design : « filtre texte
// priorisant le début de mot, exemple n doit présenter nebula en premier ».
// Sans accents ni casse ; rang 0 = un mot commence par la saisie, 1 = la
// saisie est contenue ailleurs ; à rang égal, l'ordre initial (ou le
// comparateur fourni) est conservé.

export const fold = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Rang d'un texte pour une saisie déjà repliée : 0 (début de mot), 1 (contenu), -1 (absent). */
export function matchRank(text, q) {
  const t = fold(text);
  if (!q) return 0;
  const i = t.indexOf(q);
  if (i < 0) return -1;
  if (i === 0 || /[\s\-_/.:()·,]/.test(t[i - 1])) return 0;
  // un autre mot commence par q plus loin ?
  const re = new RegExp("(^|[\\s\\-_/.:()·,])" + q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return re.test(t) ? 0 : 1;
}

/** Filtre + tri : items correspondants, débuts de mot d'abord. `text(item)` donne le texte cherché ;
 *  `cmp` (facultatif) départage à rang égal. */
export function rankFilter(items, query, text, cmp) {
  const q = fold(query).trim();
  const ranked = [];
  items.forEach((it, i) => { const r = matchRank(text(it), q); if (r >= 0) ranked.push({ it, r, i }); });
  ranked.sort((a, b) => a.r - b.r || (cmp ? cmp(a.it, b.it) : a.i - b.i));
  return ranked.map((x) => x.it);
}
