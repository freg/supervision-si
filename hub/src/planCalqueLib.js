// #973 : calque du plan d'un site -- logique pure (testée sous Node). Coordonnées en fractions 0..1 de l'image du plan.
// formes : polygones fermés {id, type: espace|zone, nom, points: [[x, y], …]} ; etiquettes : {id, type, texte, x, y}.
// Même règle côté serveur (nebula/api/calque.py) : sert à nommer la pièce d'une borne.

export const TYPES_FORME = [["espace", "Espace (pièce)"], ["zone", "Zone"]];
export const TYPES_ETIQUETTE = [["espace", "Nom d'espace"], ["spot", "Spot (borne)"], ["zone", "Zone"], ["note", "Note"]];
export const CALQUE_VIDE = { formes: [], etiquettes: [] };
export const TOLERANCE_FERMETURE = 0.015;   // clic à moins de 1,5 % du premier point : polygone fermé

export function normaliserCalque(c) {
  return { formes: Array.isArray(c?.formes) ? c.formes : [], etiquettes: Array.isArray(c?.etiquettes) ? c.etiquettes : [] };
}

export function nouvelId(prefixe, calque) {
  const pris = new Set([...(calque?.formes || []), ...(calque?.etiquettes || [])].map((x) => x.id));
  let i = 1;
  while (pris.has(`${prefixe}${i}`)) i += 1;
  return `${prefixe}${i}`;
}

const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** Clic pendant le tracé : ajoute le point, ou ferme si on revient au premier point (3 points au moins).
 *  -> {points, ferme} */
export function cliquerTrace(points, p, tol = TOLERANCE_FERMETURE) {
  const pts = points || [];
  if (pts.length >= 3 && dist(pts[0], p) <= tol) return { points: pts, ferme: true };
  return { points: [...pts, p], ferme: false };
}

export function ajouterForme(calque, { type = "espace", nom, points }) {
  const c = normaliserCalque(calque);
  if (!points || points.length < 3) return c;
  return { ...c, formes: [...c.formes, { id: nouvelId("f", c), type, nom: (nom || "").trim() || null, points }] };
}

export function ajouterEtiquette(calque, { type = "note", texte, x, y }) {
  const c = normaliserCalque(calque);
  if (!String(texte || "").trim() || x == null || y == null) return c;
  return { ...c, etiquettes: [...c.etiquettes, { id: nouvelId("e", c), type, texte: String(texte).trim(), x, y }] };
}

export function retirer(calque, id) {
  const c = normaliserCalque(calque);
  return { formes: c.formes.filter((f) => f.id !== id), etiquettes: c.etiquettes.filter((e) => e.id !== id) };
}

export function renommer(calque, id, nom) {
  const c = normaliserCalque(calque);
  return { formes: c.formes.map((f) => (f.id === id ? { ...f, nom: nom || null } : f)), etiquettes: c.etiquettes.map((e) => (e.id === id ? { ...e, texte: nom || e.texte } : e)) };
}

export function dansPolygone(x, y, pts) {
  let dedans = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-12) + xi) dedans = !dedans;
  }
  return dedans;
}

function aire(pts) {
  let s = 0;
  for (let i = 0; i < pts.length; i++) { const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % pts.length]; s += x1 * y2 - x2 * y1; }
  return Math.abs(s) / 2;
}

/** Centre de gravité d'un polygone (pour y écrire son nom). */
export function centroide(pts) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % pts.length];
    const f = x1 * y2 - x2 * y1; a += f; cx += (x1 + x2) * f; cy += (y1 + y2) * f;
  }
  if (Math.abs(a) < 1e-12) return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
  return [cx / (3 * a), cy / (3 * a)];
}

/** Nom de l'espace (sinon de la zone) qui contient le point ; le plus petit s'ils s'emboîtent. */
export function espaceDe(calque, x, y) {
  if (x == null || y == null) return null;
  const c = normaliserCalque(calque).formes.filter((f) => f.nom && dansPolygone(x, y, f.points))
    .map((f) => [f.type === "espace" ? 0 : 1, aire(f.points), f.nom]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return c.length ? c[0][2] : null;
}
