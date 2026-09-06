// Timeline du hub -- backlog, livraison #118 (backend) / #119 (ce
// fichier). Émission des événements connus vers prefs-api (voir
// prefs-api/app.py, POST /events) -- copié (comme
// shared/preferences.js) dans chaque front qui en a besoin au moment
// du build, pas un paquet npm partagé.
//
// JAMAIS bloquant : un échec ici (réseau, prefs-api indisponible...)
// ne doit jamais empêcher l'action réelle qui déclenche l'événement
// (fermer un rappel, changer d'onglet, créer un ticket) -- ce n'est
// qu'un journal d'activité, pas un mécanisme dont dépend une
// fonctionnalité.

/** Dépose un événement dans la timeline personnelle du hub.
 * `login` : fortement recommandé (la timeline est personnelle, voir
 * hub/README.md) mais pas strictement requis côté serveur.
 * `category` : une des 4 valeurs connues côté serveur
 * (VALID_HUB_EVENT_CATEGORIES, prefs-api/app.py) -- une valeur hors
 * de cette liste est rejetée par l'API (400), jamais silencieusement
 * acceptée ; ce module ne revalide pas la liste lui-même pour ne
 * jamais la laisser diverger de la source de vérité côté serveur. */
export async function postHubEvent(prefsApiBase, { login, category, label, data } = {}) {
  try {
    await fetch(`${prefsApiBase}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, category, label, data }),
    });
  } catch {
    // Volontairement silencieux -- voir commentaire d'en-tête.
  }
}
