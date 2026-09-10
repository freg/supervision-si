// Zoom / déplacement GÉNÉRIQUES pour les graphiques SVG du hub -- livraison
// #413. Logique pure (aucun React), testée sous Node (hub/tests/chartZoom.test.mjs).
//
// Retour de tests : « ajouter des options de zoom / loupe et de modulation
// d'échelle pour tous les graphiques ». Le graphique du cycle agile avait
// déjà son zoom (networkCycleGraph.js, #399) ; ce module en reprend les
// principes -- point sous le curseur immobile, facteur recalculé après
// bornage, échelle commune des deux axes -- en les GÉNÉRALISANT à un
// viewBox quelconque (origine non nulle, comme le radial tree centré en
// 0,0) et aux deux modes de preserveAspectRatio rencontrés dans le hub :
//   "meet" -- une seule échelle, dessin centré (cycle, alluvial, radial) ;
//   "none" -- une échelle par axe, dessin étiré (barres d'historique,
//             courbe de signal des sondes).
// Le composant ZoomableChart.jsx est le seul à appeler ces fonctions ; les
// graphiques eux-mêmes n'ont rien à savoir du zoom.

export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 8;
export const ZOOM_STEP = 1.25;
export const VIEW_INITIAL = { zoom: 1, x: 0, y: 0 };

export function parseViewBox(viewBox) {
  if (typeof viewBox !== "string") return null;
  const parts = viewBox.trim().split(/[\s,]+/).map(Number);
  if (parts.length !== 4 || parts.some((n) => !Number.isFinite(n)) || parts[2] <= 0 || parts[3] <= 0) return null;
  return { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
}

export function clampZoom(z) {
  if (!Number.isFinite(z)) return 1;
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
}

// Même dérivation que networkCycleGraph.zoomAtPoint : le groupe porte
// translate(x y) scale(zoom), un point p s'affiche en x + zoom·p ; imposer
// que l'ancre c reste fixe donne x' = c − (c − x)·(zoom'/zoom).
export function zoomAtPoint(view, factor, anchorX, anchorY) {
  const zoom = clampZoom(view.zoom * factor);
  const applied = zoom / view.zoom;
  return { zoom, x: anchorX - (anchorX - view.x) * applied, y: anchorY - (anchorY - view.y) * applied };
}

// Unités viewBox par pixel, sur chaque axe, selon le mode d'ajustement.
export function unitsPerPixel(rect, vb, preserve = "meet") {
  if (!rect || !(rect.width > 0) || !(rect.height > 0) || !vb) return null;
  if (preserve === "none") return { ux: vb.w / rect.width, uy: vb.h / rect.height, offsetX: 0, offsetY: 0 };
  const u = Math.max(vb.w / rect.width, vb.h / rect.height);
  const drawnW = vb.w / u;
  const drawnH = vb.h / u;
  return { ux: u, uy: u, offsetX: (rect.width - drawnW) / 2, offsetY: (rect.height - drawnH) / 2 };
}

// Déplacement souris (pixels) → unités viewBox.
export function clientDeltaToViewBox(dxPx, dyPx, rect, vb, preserve = "meet") {
  const u = unitsPerPixel(rect, vb, preserve);
  if (!u) return { dx: 0, dy: 0 };
  return { dx: dxPx * u.ux, dy: dyPx * u.uy };
}

// Point écran (pixels, relatif au SVG) → coordonnées viewBox NON
// transformées (avant translate/scale), origine du viewBox comprise.
export function clientPointToViewBox(xPx, yPx, rect, vb, preserve = "meet") {
  const u = unitsPerPixel(rect, vb, preserve);
  if (!u) return { x: vb ? vb.x + vb.w / 2 : 0, y: vb ? vb.y + vb.h / 2 : 0 };
  return { x: vb.x + (xPx - u.offsetX) * u.ux, y: vb.y + (yPx - u.offsetY) * u.uy };
}

// Zoom depuis un bouton : ancré au centre du viewBox.
export function zoomAtCenter(view, factor, vb) {
  return zoomAtPoint(view, factor, vb.x + vb.w / 2, vb.y + vb.h / 2);
}

// Transformation SVG du groupe englobant. Avec un viewBox d'origine non
// nulle, translate/scale s'appliquent autour de (0,0) et non du coin du
// viewBox -- c'est pour cela que zoomAtPoint travaille en coordonnées
// absolues du viewBox : la formule reste juste, quelle que soit l'origine.
export function viewTransform(view) {
  return `translate(${view.x} ${view.y}) scale(${view.zoom})`;
}

export function isInitialView(view) {
  return view.zoom === 1 && view.x === 0 && view.y === 0;
}

export function zoomPercent(view) {
  return Math.round(view.zoom * 100);
}
