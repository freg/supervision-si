// Logique pure de la timeline du hub -- backlog, étape 3 (livraison
// #120). Séparée du rendu (HubTimeline.jsx) pour rester testable sans
// monter de composant, même esprit que tabs.js.

/** Métadonnées d'affichage par catégorie -- les 4 valeurs connues
 * côté serveur (VALID_HUB_EVENT_CATEGORIES, prefs-api/app.py). Une
 * catégorie inconnue (ne devrait jamais arriver, l'API rejette tout
 * le reste) affiche un marqueur générique plutôt que de planter. */
export const HUB_EVENT_CATEGORY_META = {
  rappel_sans_reaction: { icon: "⏰", label: "Rappel sans réaction" },
  changement_activite: { icon: "🔄", label: "Changement d'activité" },
  mouvement_onglet: { icon: "🗂️", label: "Mouvement d'onglet" },
  ticket_cree: { icon: "🎫", label: "Ticket créé" },
};

/** Ordre d'affichage du sélecteur -- de la fenêtre la plus courte à
 * la plus longue, "demi-jour" (index 1) est la valeur par défaut
 * demandée explicitement. */
export const TIMELINE_GRANULARITIES = ["heure", "demi-jour", "jour", "semaine", "mois"];

// Fenêtre glissante -- combien de temps EN ARRIÈRE la timeline
// regarde. "mois" approximé à 30 jours (comme le reste du projet,
// jamais un calcul calendaire exact -- voir ticketsByDeadlineUrgency
// et consorts, même philosophie de simplicité assumée).
const WINDOW_SECONDS = {
  heure: 3600,
  "demi-jour": 12 * 3600,
  jour: 24 * 3600,
  semaine: 7 * 24 * 3600,
  mois: 30 * 24 * 3600,
};

// Taille de créneau ("bucket") pour regrouper les événements proches
// -- volontairement plus FIN qu'un simple "fenêtre / N" : l'idée est
// un compteur quand plusieurs événements du MÊME type arrivent
// vraiment au même moment (une rafale de changements d'onglets, par
// exemple), pas d'écraser toute la fenêtre en une poignée de blocs
// grossiers. Grossit avec la fenêtre choisie -- rester lisible même
// sur "mois" sans des centaines de lignes.
const BUCKET_SECONDS = {
  heure: 5 * 60,
  "demi-jour": 30 * 60,
  jour: 60 * 60,
  semaine: 6 * 60 * 60,
  mois: 24 * 60 * 60,
};

const DEFAULT_GRANULARITY = "demi-jour";

/** Fenêtre glissante (secondes) pour une granularité donnée --
 * jamais une exception sur une valeur inconnue, retombe sur le défaut
 * demandé explicitement ("demi-journée par défaut"). */
export function granularityWindowSeconds(granularity) {
  return WINDOW_SECONDS[granularity] ?? WINDOW_SECONDS[DEFAULT_GRANULARITY];
}

/** Taille de créneau (secondes) pour une granularité donnée -- même
 * garde-fou que ci-dessus. */
export function granularityBucketSeconds(granularity) {
  return BUCKET_SECONDS[granularity] ?? BUCKET_SECONDS[DEFAULT_GRANULARITY];
}

/** Regroupe une liste d'événements (chacun avec au moins `ts` et
 * `category`) en créneaux de `bucketSeconds`, puis par catégorie DANS
 * chaque créneau -- un marqueur par catégorie présente, avec un
 * COMPTEUR si plusieurs événements du même type tombent dans le même
 * créneau (demandé explicitement : "un petit chiffre s'il y en a
 * plusieurs dans le même delta temps"). Résultat trié du créneau le
 * plus RÉCENT au plus ancien (même sens que l'API, voir prefs-api/
 * app.py, GET /events). Jamais une exception sur une liste vide/
 * undefined, ou un événement sans `ts`/`category` (silencieusement
 * ignoré -- un événement malformé ne doit jamais casser tout
 * l'affichage). */
export function groupEventsByBucket(events, bucketSeconds) {
  const safeBucketSeconds = bucketSeconds > 0 ? bucketSeconds : BUCKET_SECONDS[DEFAULT_GRANULARITY];
  const buckets = new Map(); // bucketTs -> Map(category -> events[])
  for (const e of events || []) {
    if (!e || typeof e.ts !== "number" || !e.category) continue;
    const bucketTs = Math.floor(e.ts / safeBucketSeconds) * safeBucketSeconds;
    if (!buckets.has(bucketTs)) buckets.set(bucketTs, new Map());
    const byCategory = buckets.get(bucketTs);
    if (!byCategory.has(e.category)) byCategory.set(e.category, []);
    byCategory.get(e.category).push(e);
  }
  return Array.from(buckets.entries())
    .sort((a, b) => b[0] - a[0])
    .map(([bucketTs, byCategory]) => ({
      bucketTs,
      categories: Array.from(byCategory.entries()).map(([category, evts]) => ({
        category,
        count: evts.length,
        events: evts,
      })),
    }));
}
