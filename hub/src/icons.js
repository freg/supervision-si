// Mini charte d'icônes du hub -- livraison #410.
//
// Demandé après un premier usage réel du cycle agile : « le cerveau est un
// peu saignant et la fusée trop Tintin ; si tu peux proposer des jeux
// d'icônes et de symboles, fais-le, qu'on construise une mini charte pour
// le hub ». D'où ce module, PUR (aucun React, aucun DOM) : il décrit les
// jeux d'icônes disponibles et les règles de la charte ; le rendu vit dans
// StepIcon.jsx. Testable sous Node tel quel (hub/tests/icons.test.mjs).
//
// Trois jeux, même vocabulaire (une icône par étape du cycle), pour que
// l'on puisse comparer à l'écran et trancher :
//
//   emoji  -- le langage déjà employé par toutes les tuiles du hub.
//             Choix volontairement sobres : objets, pas de visages ni
//             d'organes (🧠 écarté), pas de véhicules (🚀 écarté).
//   glyph  -- symboles Unicode monochromes : ils prennent la couleur de
//             l'étape et du thème (clair/sombre), plus « charte » que
//             l'emoji dont le dessin dépend du système de la personne.
//   line   -- pictogrammes SVG au trait (24×24, trait 2, bouts ronds),
//             dessinés ici, mêmes règles que les symboles mais rendu
//             identique partout. C'est la voie d'une vraie charte si le
//             hub entier doit un jour abandonner l'emoji.
//
// Règles de la charte (voir docs/charte-icones-hub.md) :
//   1. une idée = une icône, réutilisée partout où l'idée apparaît ;
//   2. la couleur porte l'IDENTITÉ (étape, tuile), jamais l'état ; l'état
//      (ok / attention / critique / inconnu) passe TOUJOURS par la
//      pastille de statut et les variables --ok / --warning / --danger /
//      --muted, pour rester lisible sur les deux thèmes ;
//   3. objets et symboles, pas d'anthropomorphisme ni de « clins d'œil » ;
//   4. emoji fournis en texte, symboles et traits en currentColor : un
//      changement de thème ne doit jamais rendre une icône illisible.

export const CYCLE_STEP_IDS = ["decider", "explorer", "deployer", "mesurer", "apprendre"];

// Tracés SVG au trait (viewBox 0 0 24 24, stroke = currentColor, fill none).
// Dessinés à la main pour ce projet -- géométrie simple, aucune bibliothèque.
const LINE_PATHS = {
  // Boussole : cercle + aiguille en losange, pointe nord marquée.
  decider: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M12 6l2.5 6L12 18l-2.5-6z", "M12 11.5v1"],
  // Exploration : loupe dont le verre contient trois nœuds reliés (un réseau).
  explorer: ["M10.5 4a6.5 6.5 0 1 0 0 13a6.5 6.5 0 1 0 0-13z", "M15.5 15.5L21 21", "M8 12.5l2.5-3.5l2.5 3.5z"],
  // Déploiement : cube en perspective, la boîte que l'on met en place.
  deployer: ["M3 8l9-4l9 4v9l-9 4l-9-4z", "M3 8l9 4l9-4", "M12 12v9"],
  // Mesure : trois barres et une ligne de base.
  mesurer: ["M5 20v-7", "M12 20V5", "M19 20v-11", "M2 20h20"],
  // Apprentissage : livre ouvert.
  apprendre: ["M3 5h6a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H3z", "M21 5h-6a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h7z"],
};

export const ICON_SETS = {
  emoji: {
    id: "emoji",
    label: "Emoji sobres",
    kind: "text",
    description: "Le langage des tuiles du hub, avec des objets plutôt que des personnages.",
    icons: { decider: "🧭", explorer: "🕸️", deployer: "📦", mesurer: "📊", apprendre: "📚" },
  },
  glyph: {
    id: "glyph",
    label: "Symboles monochromes",
    kind: "glyph",
    description: "Symboles Unicode qui prennent la couleur de l'étape et suivent le thème.",
    icons: { decider: "⎈", explorer: "⌕", deployer: "⇪", mesurer: "∿", apprendre: "✎" },
  },
  line: {
    id: "line",
    label: "Pictogrammes au trait",
    kind: "svg",
    description: "Tracés SVG dessinés pour le projet : rendu identique sur toutes les machines.",
    icons: LINE_PATHS,
  },
};

export const DEFAULT_ICON_SET = "emoji";

// Alternatives envisagées par étape (emoji) -- gardées ici pour la
// discussion de charte, pas rendues : ce sont les candidats qu'on peut
// substituer d'un mot dans ICON_SETS.emoji si la personne préfère.
export const EMOJI_ALTERNATIVES = {
  decider: ["🧭", "🎯", "⚖️", "🗺️"],
  explorer: ["🕸️", "🔍", "📡", "🧭"],
  deployer: ["📦", "🛠️", "🧩", "⚙️"],
  mesurer: ["📊", "📈", "📏", "⏱️"],
  apprendre: ["📚", "💡", "🎓", "📝"],
};

// Icônes ÉCARTÉES par la charte, avec la raison -- pour ne pas y revenir.
export const REJECTED_ICONS = {
  "🚀": "véhicule / clin d'œil (« trop Tintin ») -- Déployer",
  "🧠": "organe, connotation viscérale (« saignant ») -- Apprendre",
};

export const ICON_SET_IDS = Object.keys(ICON_SETS);

export function resolveIconSet(id) {
  return ICON_SETS[id] || ICON_SETS[DEFAULT_ICON_SET];
}

// Icône d'une étape dans un jeu donné : { kind, value }. Toujours défini :
// un jeu inconnu retombe sur le jeu par défaut, une étape inconnue sur un
// symbole neutre -- jamais `undefined` rendu à l'écran.
export function getStepIcon(setId, stepId) {
  const set = resolveIconSet(setId);
  const value = set.icons[stepId];
  if (value === undefined) return { kind: "text", value: "•" };
  return { kind: set.kind, value };
}

// Version texte d'une icône (titres, infobulles, journaux) : les emoji et
// symboles tels quels, les tracés SVG remplacés par leur équivalent emoji.
export function getStepIconText(setId, stepId) {
  const icon = getStepIcon(setId, stepId);
  if (icon.kind === "svg") return ICON_SETS.emoji.icons[stepId] || "•";
  return icon.value;
}

export const ICON_SET_STORAGE_KEY = "hub.cycle.iconSet";

// Préférence locale au navigateur (comme la note de pied de page du hub) :
// une préférence de charte n'a pas à traverser les comptes tant que la
// charte n'est pas tranchée. `storage` injectable pour les tests.
export function loadIconSetPreference(storage) {
  try {
    const raw = storage?.getItem(ICON_SET_STORAGE_KEY);
    return ICON_SETS[raw] ? raw : DEFAULT_ICON_SET;
  } catch {
    return DEFAULT_ICON_SET;
  }
}

export function saveIconSetPreference(storage, id) {
  if (!ICON_SETS[id]) return false;
  try {
    storage?.setItem(ICON_SET_STORAGE_KEY, id);
    return true;
  } catch {
    return false;
  }
}
