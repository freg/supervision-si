// Logique pure de l'onglet "Dépôt shapefiles" — testable via Node.

export const GEOMETRY_TYPE_LABELS = {
  POINT: "Point",
  MULTIPOINT: "Multi-point",
  LINESTRING: "Ligne",
  MULTILINESTRING: "Multi-ligne",
  POLYGON: "Polygone",
  MULTIPOLYGON: "Multi-polygone",
  GEOMETRY: "Géométrie (mixte)",
  GEOMETRYCOLLECTION: "Collection géométrique",
};

export function geometryTypeLabel(rawType) {
  if (!rawType) return "—";
  const key = String(rawType).toUpperCase();
  return GEOMETRY_TYPE_LABELS[key] || rawType;
}

export function isValidFusionSelection(selectedLayers) {
  return Array.isArray(selectedLayers) && selectedLayers.length >= 2;
}

/** Nom de couche fusionnée suggéré par défaut, à partir des couches
 * sélectionnées — simple concaténation bornée, jamais imposé (toujours
 * éditable par la personne avant de lancer la fusion). */
export function suggestFusionLayerName(selectedLayers) {
  if (!Array.isArray(selectedLayers) || selectedLayers.length === 0) return "";
  const joined = selectedLayers.slice(0, 3).join("_");
  const suffix = selectedLayers.length > 3 ? `_et_${selectedLayers.length - 3}_autres` : "";
  return `fusion_${joined}${suffix}`.slice(0, 63);
}

/** true si le nom de fichier ressemble à une archive .zip exploitable
 * (vérification cliente légère, avant envoi — la vraie validation du
 * contenu se fait côté serveur, celle-ci n'est qu'un premier filtre). */
export function looksLikeZipFile(filename) {
  return typeof filename === "string" && filename.toLowerCase().endsWith(".zip");
}

// --- Outil de corrélation --------------------------------------------

export const CORRELATION_STRATEGIES = [
  { key: "semantic", label: "Sémantique (libellés)", needsColumns: true },
  { key: "geographic", label: "Géographique (proximité)", needsColumns: false },
  { key: "temporal", label: "Temporelle (dates)", needsColumns: true },
];

export function strategyLabel(key) {
  return CORRELATION_STRATEGIES.find((s) => s.key === key)?.label || key;
}

export function strategyNeedsColumns(key) {
  return CORRELATION_STRATEGIES.find((s) => s.key === key)?.needsColumns ?? false;
}

/** Formate un score selon le sens attendu par la stratégie (renvoyé
 * par le backend via scoreDirection) -- "higher_better" (sémantique,
 * 0-1) affiché en pourcentage ; "lower_better" (géo en mètres, temporel
 * en jours) affiché avec son unité. Ne suppose jamais l'unité sans que
 * l'appelant la précise (une distance et un écart de jours n'ont pas
 * le même sens). */
export function formatCorrelationScore(score, scoreDirection, unit) {
  if (typeof score !== "number") return "—";
  if (scoreDirection === "higher_better") return `${Math.round(score * 100)}%`;
  if (unit === "m") {
    return score >= 1000 ? `${(score / 1000).toFixed(2)} km` : `${Math.round(score)} m`;
  }
  if (unit === "j") return `${score.toFixed(1)} j`;
  return String(score);
}

/** Valide les options d'une stratégie avant d'appeler l'API -- évite
 * un aller-retour serveur pour une erreur détectable côté client
 * (colonne non choisie). Ne remplace pas la validation serveur
 * (couches/colonnes réellement existantes), juste un filtre rapide. */
export function validateCorrelationOptions(strategy, layerA, layerB, options) {
  if (!layerA || !layerB) return "Choisissez les deux couches à corréler.";
  if (layerA === layerB) return "Les deux couches doivent être différentes.";
  if (strategyNeedsColumns(strategy)) {
    if (!options?.column_a || !options?.column_b) return "Choisissez une colonne pour chaque couche.";
  }
  return null;
}
