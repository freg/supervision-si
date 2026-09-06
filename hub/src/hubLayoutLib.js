// Personnalisation de l'accueil, étape 2 (livraison #133) -- modèle
// de données et logique de fusion PURE (jamais d'accès réseau ici,
// voir settingsClient.js pour la lecture/écriture du blob
// /preferences). Stocké dans ce blob déjà existant côté prefs-api,
// nouvelle clé "hubLayout" -- AUCUN changement de schéma nécessaire :
// PUT /preferences fait déjà une fusion superficielle côté serveur
// (voir prefs-api/app.py, put_preferences) qui préserve les autres
// clés (theme, etc.) sans y toucher, exactement pensé pour ce genre
// d'extension future.
//
// Forme de hubLayout :
//   {
//     groups: [{ id, title, order }],
//     tiles: { [frontId]: { groupId, order, hidden } },
//   }
// Une tuile ABSENTE de `tiles` = comportement par défaut, jamais un
// cas à part : groupId null (sans cadre), hidden false, ordre = sa
// position naturelle dans `fronts` -- une personne qui n'a jamais
// touché à la personnalisation voit exactement ce qu'elle voyait
// avant ce chantier.

/** Identifiant de cadre -- suffisamment unique pour un usage
 * PERSONNEL (jamais partagé entre utilisateurs, jamais de risque de
 * collision réelle) : horodatage + compteur, pas de dépendance à une
 * librairie UUID pour un besoin aussi simple. */
let groupIdCounter = 0;
export function generateGroupId() {
  groupIdCounter += 1;
  return `g-${Date.now().toString(36)}-${groupIdCounter}`;
}

/** Regroupe/trie/filtre `fronts` (déjà filtrés par rôle, voir
 * lib.js buildFrontsList) selon `hubLayout`, pour l'AFFICHAGE réel de
 * la grille d'accueil -- DÉFENSIF sur toute forme malformée/absente
 * (hubLayout null/undefined, `groups`/`tiles` absents ou du mauvais
 * type, une tuile pointant vers un `groupId` qui n'existe plus, ex.
 * cadre supprimé entretemps) : retombe TOUJOURS sur un affichage
 * sensé plutôt qu'une exception qui viderait toute la grille.
 *
 * Choix assumé : un cadre sans AUCUNE tuile visible (vide, ou dont
 * toutes les tuiles ont été masquées) n'est PAS renvoyé ici -- pas de
 * cadre vide qui ne ferait que du bruit visuel sur l'écran d'usage
 * quotidien. L'écran "Personnaliser l'accueil" (étape 3, pas encore
 * livrée), lui, devra lire `hubLayout.groups` DIRECTEMENT (pas via
 * cette fonction) pour permettre de gérer un cadre encore vide.
 *
 * Renvoie { ungrouped: [front...], groups: [{ id, title, tiles: [front...] }] }. */
export function applyHubLayout(fronts, hubLayout) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tileStates = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null
    ? hubLayout.tiles
    : {};
  const validGroupIds = new Set(groups.filter((g) => g && typeof g.id === "string").map((g) => g.id));

  const ungrouped = [];
  const byGroupId = new Map(); // groupId -> [{ front, order }]

  (fronts || []).forEach((front, index) => {
    if (!front || !front.id) return; // entrée malformée -- jamais une exception, simplement ignorée
    const state = tileStates[front.id];
    if (state?.hidden === true) return;
    const rawGroupId = state?.groupId;
    const groupId = typeof rawGroupId === "string" && validGroupIds.has(rawGroupId) ? rawGroupId : null;
    const order = typeof state?.order === "number" ? state.order : index;
    if (groupId === null) {
      ungrouped.push({ front, order });
    } else {
      if (!byGroupId.has(groupId)) byGroupId.set(groupId, []);
      byGroupId.get(groupId).push({ front, order });
    }
  });

  ungrouped.sort((a, b) => a.order - b.order);

  const sortedGroups = groups
    .filter((g) => g && typeof g.id === "string" && byGroupId.has(g.id))
    .slice()
    .sort((a, b) => (typeof a.order === "number" ? a.order : 0) - (typeof b.order === "number" ? b.order : 0))
    .map((g) => ({
      id: g.id,
      title: typeof g.title === "string" && g.title.trim() ? g.title : "(sans titre)",
      tiles: byGroupId.get(g.id).slice().sort((a, b) => a.order - b.order).map((x) => x.front),
    }));

  return {
    ungrouped: ungrouped.map((x) => x.front),
    groups: sortedGroups,
  };
}

// ------------------------------------------------------------------
// Mutations PURES pour l'écran "Personnaliser l'accueil" (étape 3,
// livraison #140) -- chacune prend le hubLayout ACTUEL et renvoie un
// NOUVEAU hubLayout, jamais de mutation en place (cohérent avec le
// reste de ce fichier, et avec React -- un nouvel objet déclenche
// correctement un re-rendu). `fronts` (liste actuelle des tuiles,
// même forme que buildFrontsList) est nécessaire à plusieurs de ces
// fonctions pour ne JAMAIS réinitialiser silencieusement la position
// d'une tuile qu'on touche pour la première fois -- voir
// getEffectiveTileState ci-dessous.
// ------------------------------------------------------------------

/** État EFFECTIF d'une tuile -- que sa personnalisation ait déjà été
 * touchée ou non (même repli qu'applyHubLayout : sans cadre, ordre =
 * position naturelle dans `fronts`, visible). Utilisée par les
 * mutations pour préserver la position ACTUELLE d'une tuile qu'on
 * modifie pour la première fois, jamais la remettre à zéro. */
function getEffectiveTileState(hubLayout, frontId, fronts) {
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  const existing = tiles[frontId];
  const naturalIndex = Array.isArray(fronts) ? fronts.findIndex((f) => f && f.id === frontId) : -1;
  return {
    groupId: existing && typeof existing.groupId === "string" ? existing.groupId : null,
    order: existing && typeof existing.order === "number" ? existing.order : (naturalIndex >= 0 ? naturalIndex : 0),
    hidden: existing?.hidden === true,
  };
}

/** Ordre à donner à une tuile placée EN FIN d'un panier (`groupId`
 * donné, ou `null` pour "sans cadre") -- toujours strictement
 * supérieur à tout ordre NATUREL possible (fronts.length) ET à tout
 * ordre déjà présent dans ce panier, pour ne jamais se retrouver
 * mélangée au milieu de tuiles jamais personnalisées (dont l'ordre
 * naturel, l'index dans `fronts`, est toujours < fronts.length). */
function nextOrderInBucket(hubLayout, groupId, fronts) {
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  let max = Array.isArray(fronts) ? fronts.length : 0;
  for (const state of Object.values(tiles)) {
    if (state && (state.groupId ?? null) === groupId && typeof state.order === "number") {
      max = Math.max(max, state.order);
    }
  }
  return max + 1;
}

/** Crée un nouveau cadre, placé en dernier parmi les cadres
 * existants. Titre vide -- retombe sur "Nouveau cadre", jamais un
 * cadre "(sans titre)" créé par erreur silencieuse. */
export function createGroup(hubLayout, title) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  const trimmed = (title || "").trim();
  const maxOrder = groups.reduce((max, g) => Math.max(max, typeof g.order === "number" ? g.order : 0), -1);
  const newGroup = { id: generateGroupId(), title: trimmed || "Nouveau cadre", order: maxOrder + 1 };
  return { groups: [...groups, newGroup], tiles };
}

/** Renomme un cadre. Titre vide -- ignoré (hubLayout renvoyé
 * inchangé), jamais un cadre "(sans titre)" créé par erreur. */
export function renameGroup(hubLayout, groupId, newTitle) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  const trimmed = (newTitle || "").trim();
  if (!trimmed) return { groups, tiles };
  return { groups: groups.map((g) => (g.id === groupId ? { ...g, title: trimmed } : g)), tiles };
}

/** Supprime un cadre -- ses tuiles repassent SANS CADRE (jamais
 * supprimées elles-mêmes), placées en fin de la liste sans cadre
 * pour ne jamais entrer en collision avec l'existant. */
export function deleteGroup(hubLayout, groupId, fronts) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  const remainingGroups = groups.filter((g) => g.id !== groupId);
  let nextOrder = nextOrderInBucket({ groups: remainingGroups, tiles }, null, fronts);
  const newTiles = {};
  for (const [frontId, state] of Object.entries(tiles)) {
    if (state && state.groupId === groupId) {
      newTiles[frontId] = { ...state, groupId: null, order: nextOrder };
      nextOrder += 1;
    } else {
      newTiles[frontId] = state;
    }
  }
  return { groups: remainingGroups, tiles: newTiles };
}

/** Assigne une tuile à un cadre (`groupId`), ou la remet sans cadre
 * (`groupId: null`) -- placée en fin du panier cible. `hidden`
 * PRÉSERVÉ tel quel (voir getEffectiveTileState), jamais réaffiché
 * de force par cette seule action. */
export function setTileGroup(hubLayout, frontId, groupId, fronts) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  const current = getEffectiveTileState(hubLayout, frontId, fronts);
  const order = nextOrderInBucket(hubLayout, groupId, fronts);
  return { groups, tiles: { ...tiles, [frontId]: { groupId, order, hidden: current.hidden } } };
}

/** Masque/affiche une tuile -- cadre et ordre PRÉSERVÉS tels quels
 * (voir getEffectiveTileState), jamais réinitialisés par cette seule
 * action. */
export function setTileHidden(hubLayout, frontId, hidden, fronts) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  const current = getEffectiveTileState(hubLayout, frontId, fronts);
  return { groups, tiles: { ...tiles, [frontId]: { ...current, hidden } } };
}

/** Déplace une tuile d'un cran (`direction`: "up"/"down") DANS SON
 * PANIER ACTUEL (son cadre, ou sans cadre) -- reconstruit le panier
 * ENTIER dans son ordre EFFECTIF (tuiles jamais personnalisées
 * comprises, voir getEffectiveTileState) pour trouver la bonne
 * voisine à échanger, jamais seulement parmi les tuiles déjà
 * explicitement suivies dans `tiles`. Déjà au bord du panier --
 * hubLayout renvoyé inchangé, jamais une exception. */
export function moveTile(hubLayout, frontId, direction, fronts) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  if (!Array.isArray(fronts)) return { groups, tiles };

  const current = getEffectiveTileState(hubLayout, frontId, fronts);
  const bucket = fronts
    .filter((f) => f && f.id)
    .map((f) => ({ id: f.id, ...getEffectiveTileState(hubLayout, f.id, fronts) }))
    .filter((t) => (t.groupId ?? null) === (current.groupId ?? null))
    .sort((a, b) => a.order - b.order);

  const idx = bucket.findIndex((t) => t.id === frontId);
  if (idx === -1) return { groups, tiles };
  const swapIdx = direction === "up" ? idx - 1 : idx + 1;
  if (swapIdx < 0 || swapIdx >= bucket.length) return { groups, tiles };

  const a = bucket[idx], b = bucket[swapIdx];
  const newTiles = { ...tiles };
  newTiles[a.id] = { groupId: a.groupId, order: b.order, hidden: a.hidden };
  newTiles[b.id] = { groupId: b.groupId, order: a.order, hidden: b.hidden };
  return { groups, tiles: newTiles };
}

/** Déplace un cadre d'un cran (`direction`: "up"/"down") parmi les
 * autres cadres -- échange son ordre avec son voisin. Déjà au bord
 * -- hubLayout renvoyé inchangé, jamais une exception. */
export function moveGroup(hubLayout, groupId, direction) {
  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const tiles = hubLayout && typeof hubLayout.tiles === "object" && hubLayout.tiles !== null ? hubLayout.tiles : {};
  const sorted = [...groups].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  const idx = sorted.findIndex((g) => g.id === groupId);
  if (idx === -1) return { groups, tiles };
  const swapIdx = direction === "up" ? idx - 1 : idx + 1;
  if (swapIdx < 0 || swapIdx >= sorted.length) return { groups, tiles };
  const a = sorted[idx], b = sorted[swapIdx];
  const newGroups = groups.map((g) => {
    if (g.id === a.id) return { ...g, order: b.order };
    if (g.id === b.id) return { ...g, order: a.order };
    return g;
  });
  return { groups: newGroups, tiles };
}
