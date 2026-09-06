/**
 * Gestion partagée du thème (clair/foncé) — copié (comme
 * shared/theme.css) dans chacun des 4 fronts au moment du build, pas
 * un paquet npm partagé.
 *
 * SYNCHRONISATION CROISÉE ENTRE LES 4 FRONTS — demandée explicitement
 * par la personne après la première version de ce module (qui traitait
 * "compte" et "local" comme deux mécanismes cloisonnés, ne se
 * parlant jamais). Rendue possible par un fait déjà vrai de
 * l'architecture : les 4 fronts vivent sous la MÊME origine (entrée
 * unique par chemin) -- localStorage y est donc déjà partagé de fait.
 * Il ne manquait que l'écoute des changements en temps réel (l'
 * évènement navigateur "storage") et un pont vers le mécanisme lié au
 * compte.
 *
 * Principe retenu : localStorage devient le bus de synchronisation
 * UNIQUE et immédiat entre les 4 fronts, quel que soit celui où le
 * choix a été fait. `prefs-api` (compte Keycloak, hub + portail
 * tickets uniquement, seuls fronts avec une identité aujourd'hui)
 * reste une couche de DURABILITÉ par-dessus -- elle amorce un
 * navigateur qui n'a encore RIEN de local (première visite), mais ne
 * l'écrase JAMAIS si un choix plus frais existe déjà localement
 * (potentiellement posé il y a un instant depuis un autre front).
 *
 * Les deux modes exposent la MÊME interface :
 * { get(), set(theme), onChange(cb) } — le bouton de bascule (dupliqué
 * par front, volontairement simple) n'a jamais besoin de savoir lequel
 * des deux est actif.
 */

const STORAGE_KEY = "supervision-si:theme";
const VALID_THEMES = ["light", "dark"];

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
}

/**
 * DBA, Supervision SI (aucune authentification aujourd'hui) — ET
 * mécanisme interne de createAccountThemeStore() (hub, portail
 * tickets), qui s'appuie dessus plutôt que de dupliquer la logique de
 * synchronisation croisée.
 */
export function createLocalThemeStore() {
  let current = localStorage.getItem(STORAGE_KEY);
  if (!VALID_THEMES.includes(current)) current = null; // valeur corrompue/absente -> pas de préférence explicite, le CSS de base du front s'applique
  if (current) applyTheme(current);

  const listeners = new Set();

  // Écoute les changements faits par un AUTRE onglet/front de même
  // origine — "storage" ne se déclenche JAMAIS dans l'onglet qui a
  // fait le changement lui-même, seulement les autres : exactement le
  // comportement voulu pour propager sans boucle infinie (le front
  // À L'ORIGINE du changement l'a déjà appliqué directement dans
  // set(), pas besoin qu'il se re-déclenche lui-même via cet
  // évènement).
  if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    window.addEventListener("storage", (e) => {
      if (e.key !== STORAGE_KEY) return;
      if (!VALID_THEMES.includes(e.newValue)) return;
      current = e.newValue;
      applyTheme(current);
      listeners.forEach((cb) => cb(current));
    });
  }

  return {
    get: () => current,
    set(theme) {
      if (!VALID_THEMES.includes(theme)) return;
      current = theme;
      localStorage.setItem(STORAGE_KEY, theme);
      applyTheme(theme);
      listeners.forEach((cb) => cb(theme));
    },
    onChange(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
  };
}

/**
 * Hub, portail tickets — identité connue via Keycloak. `username` est
 * un paramètre explicite de `load()`/`set()` plutôt que figé au
 * constructeur : l'identité n'est connue qu'APRÈS authentification,
 * cette API doit rester utilisable avant.
 *
 * S'appuie sur createLocalThemeStore() en interne pour l'application
 * immédiate ET la synchronisation croisée avec les 3 autres fronts —
 * prefs-api n'intervient qu'en complément (amorçage + durabilité),
 * jamais comme mécanisme concurrent.
 */
export function createAccountThemeStore({ apiBase }) {
  const local = createLocalThemeStore();
  const listeners = new Set();
  local.onChange((theme) => listeners.forEach((cb) => cb(theme)));

  async function load(username) {
    // Un choix DÉJÀ présent localement (potentiellement posé il y a
    // un instant depuis un autre front) prime toujours sur ce que
    // connaît le compte -- prefs-api ne sert qu'à amorcer un
    // navigateur qui n'a ENCORE RIEN de local (première visite,
    // jamais aucun front n'a encore posé de préférence ici).
    if (local.get() !== null) return;
    if (!username) return;
    try {
      const res = await fetch(`${apiBase}/preferences?user=${encodeURIComponent(username)}`);
      if (!res.ok) return;
      const data = await res.json();
      if (VALID_THEMES.includes(data.theme)) {
        local.set(data.theme); // applique + propage aux 3 autres fronts au passage
      }
    } catch {
      // API injoignable -- le front garde son thème par défaut/local
      // plutôt que de planter ; pas une erreur bloquante.
    }
  }

  async function set(theme, username) {
    local.set(theme); // applique immédiatement + propage aux 3 autres fronts
    if (!username) return;
    try {
      await fetch(`${apiBase}/preferences?user=${encodeURIComponent(username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme }),
      });
    } catch {
      // Persistance côté compte échouée -- le thème reste appliqué
      // localement (et propagé aux autres fronts) pour cette session,
      // juste pas mémorisé pour la prochaine sur un autre appareil.
    }
  }

  return {
    get: local.get,
    set,
    load,
    onChange(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
  };
}
