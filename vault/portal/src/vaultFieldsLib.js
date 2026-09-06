// Gère le contenu "valeur" d'un secret comme une LISTE de champs
// {label, content} plutôt qu'une simple chaîne -- demandé
// explicitement : codes à plusieurs champs (login/mot de passe),
// champs personnalisés ajoutables. Le serveur ne voit jamais rien de
// tout ça : "value" reste un blob chiffré opaque de son point de vue,
// SEUL le contenu qu'on y sérialise avant chiffrement change --
// aucun changement de schéma côté vault-api n'a donc été nécessaire
// pour ce chantier.
//
// RÉTROCOMPATIBILITÉ ASSUMÉE : un ancien secret jamais réédité depuis
// ce chantier a une valeur déchiffrée qui est une simple chaîne, pas
// du JSON -- reste lisible tel quel (voir parseFields), traité comme
// un unique champ implicite SANS libellé affiché, exactement comme
// avant. Aucune migration en masse : impossible de toute façon côté
// serveur (E2E, il ne peut rien déchiffrer pour transformer quoi que
// ce soit) -- chaque secret bascule naturellement au nouveau format
// dès sa prochaine modification.

/** Sérialise une liste de champs vers la forme stockée (chiffrée
 * ensuite par l'appelant, voir vaultOps.js) -- toujours du JSON, même
 * pour un seul champ : un seul chemin de code à la sérialisation,
 * plus simple à maintenir que deux représentations distinctes selon
 * le nombre de champs. */
export function serializeFields(fields) {
  return JSON.stringify((fields || []).map((f) => ({ label: f.label || "", content: f.content || "" })));
}

/** Reconstruit la liste de champs depuis le texte DÉJÀ déchiffré --
 * accepte aussi bien le nouveau format (JSON, liste de {label,
 * content}) que l'ancien (simple chaîne) : dans ce cas, traité comme
 * un unique champ implicite, label vide (voir isSimpleSingleField,
 * l'affichage doit alors ne montrer aucun libellé). Jamais
 * d'exception, quel que soit le contenu reçu -- au pire, un champ
 * "brut" avec le texte tel quel. */
export function parseFields(decryptedText) {
  if (!decryptedText) return [{ label: "", content: "" }];
  try {
    const parsed = JSON.parse(decryptedText);
    if (Array.isArray(parsed) && parsed.length > 0 && parsed.every((f) => f && typeof f === "object" && !Array.isArray(f) && "content" in f)) {
      return parsed.map((f) => ({ label: f.label || "", content: f.content || "" }));
    }
  } catch {
    // Pas du JSON valide -- ancien format simple chaîne, traité ci-dessous.
  }
  return [{ label: "", content: decryptedText }];
}

/** Vrai si la liste ne contient qu'un seul champ SANS libellé -- cas
 * "simple" (comme avant ce chantier, ou un secret jamais réédité) :
 * l'affichage ne doit alors montrer aucun libellé, juste le contenu
 * brut, pour ne rien changer visuellement à l'usage courant. */
export function isSimpleSingleField(fields) {
  return (fields || []).length === 1 && !fields[0].label;
}

/** Préréglage pratique pour le formulaire d'édition -- "🔑
 * Identifiants" ajoute deux champs pré-libellés d'un coup, juste du
 * sucre autour du mécanisme générique de champs personnalisés,
 * aucune logique propre côté stockage. */
export function loginPasswordPreset() {
  return [
    { label: "Login", content: "" },
    { label: "Mot de passe", content: "" },
  ];
}

// Libellés du préréglage ci-dessus -- réutilisés tels quels par
// defaultRequiredLabels (comparaison insensible à la casse/espaces,
// pour couvrir aussi un champ "login" tapé à la main sans passer par
// le préréglage).
const DEFAULT_REQUIRED_LABELS = ["login", "mot de passe"];

/** Détermine quels champs doivent être cochés OBLIGATOIRES par défaut
 * quand on enregistre un nouveau format (modèle) de collection --
 * demandé explicitement ("login/password obligatoires par défaut").
 * Ne préjuge de rien pour les autres champs (jamais obligatoires par
 * défaut, la personne coche elle-même). Comparaison insensible à la
 * casse et aux espaces de bord. */
export function defaultRequiredLabels(fields) {
  return (fields || [])
    .map((f) => (f.label || "").trim())
    .filter((label) => DEFAULT_REQUIRED_LABELS.includes(label.toLowerCase()));
}

/** Réordonne une liste de champs pour présenter les champs
 * OBLIGATOIRES en premier -- demandé explicitement, appliqué quand un
 * format (modèle) de collection est utilisé pour pré-remplir un
 * secret. Obligatoire = INDICATIF seulement (jamais bloquant,
 * décision prise avec la personne) -- ceci n'est qu'un ordre
 * d'affichage. Tri STABLE : l'ordre relatif entre deux champs de même
 * statut (tous deux obligatoires, ou tous deux non) reste inchangé,
 * jamais un réordonnancement surprise au sein d'un même groupe. */
export function orderFieldsRequiredFirst(fields, requiredLabels) {
  const required = new Set((requiredLabels || []).map((l) => (l || "").trim().toLowerCase()));
  return (fields || [])
    .map((f, i) => ({ f, i, required: required.has((f.label || "").trim().toLowerCase()) }))
    .sort((a, b) => (a.required === b.required ? a.i - b.i : a.required ? -1 : 1))
    .map(({ f }) => f);
}

/** Découpe une valeur en mots -- pour la copie partielle mot par mot
 * (demandé explicitement). Espaces multiples/de bord jamais des mots
 * vides. Renvoie un tableau VIDE (pas [valeur]) si un seul "mot" --
 * à l'appelant de décider s'il affiche la liste selon la longueur. */
export function splitIntoWords(value) {
  return (value || "").split(/\s+/).filter(Boolean);
}
