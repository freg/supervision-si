// Disposition de la tuile Cycle agile -- livraison #411. Logique PURE
// (aucun React), testée sous Node (hub/tests/networkCycleLayout.test.mjs).
//
// Retour de tests : « quand on clique sur l'une des icônes, les
// fonctionnalités se déplient sur la seconde moitié basse de l'écran ; le
// schéma/menu peut être réduit par défaut et autoriser une réduction
// manuelle, voire un masquage en laissant juste une languette pour le
// redéployer ; suggestion : seule la partie menu change entre classique et
// graphique ».
//
// D'où un écran en deux zones : en haut le MENU (soit la barre d'étapes
// « classique », soit le schéma « graphique » -- c'est la seule chose que
// les onglets changent), en bas le DÉTAIL de l'étape courante, toujours
// présent. Le menu a trois états :
//
//   expanded  -- schéma en grand (≈ moitié haute de l'écran)
//   reduced   -- schéma compact (défaut : le détail est ce qu'on lit)
//   hidden    -- menu masqué, il ne reste qu'une languette pour le rouvrir
//
// La barre classique est déjà compacte : reduced et expanded y sont
// équivalents, seul hidden la fait disparaître.

export const MENU_STATES = ["expanded", "reduced", "hidden"];
export const DEFAULT_MENU_STATE = "reduced";
export const VIEW_MODES = ["classique", "graphique"];
export const DEFAULT_VIEW_MODE = "classique";

export function isMenuState(v) {
  return MENU_STATES.includes(v);
}

// Transition d'état du menu selon l'action de la personne :
//   "toggle"  -- bouton ▾/▴ : expanded ⇄ reduced (depuis hidden : reduced)
//   "hide"    -- bouton ✕ : hidden
//   "show"    -- languette : retour à l'état d'AVANT le masquage
//                (`before`), ou reduced si inconnu
export function nextMenuState(current, action, before) {
  switch (action) {
    case "toggle":
      if (current === "expanded") return "reduced";
      return "expanded";
    case "hide":
      return "hidden";
    case "show":
      if (current !== "hidden") return current;
      return isMenuState(before) && before !== "hidden" ? before : DEFAULT_MENU_STATE;
    default:
      return isMenuState(current) ? current : DEFAULT_MENU_STATE;
  }
}

// Hauteur du conteneur du schéma selon l'état, en fraction de la hauteur
// de fenêtre, bornée en pixels : « moitié haute » en grand, un tiers en
// réduit. Le SVG garde son viewBox 800×400 et se met à l'échelle (meet),
// donc réduire la hauteur ne coupe rien, cela rapetisse tout.
export const GRAPH_HEIGHTS = {
  expanded: { vh: 50, min: 300, max: 600 },
  reduced: { vh: 30, min: 170, max: 300 },
};

export function graphHeightPx(menuState, viewportHeight) {
  const spec = GRAPH_HEIGHTS[menuState] || GRAPH_HEIGHTS.reduced;
  const raw = (viewportHeight * spec.vh) / 100;
  return Math.round(Math.min(spec.max, Math.max(spec.min, raw)));
}

// Préférence de disposition, locale au navigateur : { viewMode, menuState }.
// Lecture tolérante (stockage absent, JSON cassé, valeurs inconnues) : on
// retombe toujours sur des valeurs valides, jamais sur une exception au
// montage du composant.
export const LAYOUT_STORAGE_KEY = "hub.cycle.layout";

export function loadLayoutPreference(storage) {
  const fallback = { viewMode: DEFAULT_VIEW_MODE, menuState: DEFAULT_MENU_STATE };
  try {
    const raw = storage?.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return {
      viewMode: VIEW_MODES.includes(parsed?.viewMode) ? parsed.viewMode : fallback.viewMode,
      menuState: isMenuState(parsed?.menuState) ? parsed.menuState : fallback.menuState,
    };
  } catch {
    return fallback;
  }
}

export function saveLayoutPreference(storage, { viewMode, menuState }) {
  if (!VIEW_MODES.includes(viewMode) || !isMenuState(menuState)) return false;
  try {
    storage?.setItem(LAYOUT_STORAGE_KEY, JSON.stringify({ viewMode, menuState }));
    return true;
  } catch {
    return false;
  }
}

// Libellé de la languette quand le menu est masqué.
export function hiddenMenuLabel(viewMode) {
  return viewMode === "graphique" ? "Afficher le schéma du cycle" : "Afficher le menu du cycle";
}
