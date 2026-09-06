// Logique pure de gestion des onglets de la coquille du hub --
// demandé explicitement (coquille façon navigateur web, plusieurs
// onglets possibles sur la même application). Séparée de React pour
// rester testable sans monter de composant.

/** Un onglet : {id, appId, url, title}. `id` généré via
 * crypto.randomUUID() (disponible nativement en navigateur moderne
 * et Node 20+, aucune dépendance) -- garantit un identifiant unique
 * même pour deux onglets ouverts sur la MÊME application. */
export function createTab(front) {
  return {
    id: crypto.randomUUID(),
    appId: front.id,
    url: front.url,
    title: front.name,
  };
}

/** Ouvre un nouvel onglet à la fin de la liste -- jamais de mutation
 * du tableau reçu. */
export function openTab(tabs, front) {
  return [...(tabs || []), createTab(front)];
}

/** Ferme l'onglet `tabId` -- renvoie {tabs, activeTabId} (jamais
 * juste `tabs` seul : fermer l'onglet ACTIF change forcément quel
 * onglet devient actif ensuite, l'appelant ne doit jamais avoir à
 * redéduire cette logique lui-même).
 *
 * Onglet fermé NON actif -- activeTabId inchangé, aucune raison de
 * le toucher. Onglet fermé ACTIF -- celui qui glisse à sa place
 * devient actif (même convention que la plupart des navigateurs :
 * l'onglet à droite, ou le dernier restant si on ferme le plus à
 * droite). Aucun onglet restant -- activeTabId devient null,
 * jamais une exception. */
export function closeTab(tabs, tabId, activeTabId) {
  const safeTabs = tabs || [];
  const closedIndex = safeTabs.findIndex((t) => t.id === tabId);
  const remaining = safeTabs.filter((t) => t.id !== tabId);

  if (activeTabId !== tabId) {
    return { tabs: remaining, activeTabId };
  }
  if (remaining.length === 0) {
    return { tabs: remaining, activeTabId: null };
  }
  const newIndex = Math.min(Math.max(closedIndex, 0), remaining.length - 1);
  return { tabs: remaining, activeTabId: remaining[newIndex].id };
}

// --- Protocole postMessage coquille <-> application embarquée ---
// Backlog hub #1. Chaque application embarquée signale son état
// "modification non enregistrée" au hub via postMessage (voir
// shared/useUnsavedChangesWarning.js) -- pour que fermer un ONGLET
// précis avertisse aussi, pas seulement fermer tout le navigateur
// (beforeunload, déjà construit séparément).

/** Type du message échangé -- constante partagée entre l'émetteur
 * (shared/useUnsavedChangesWarning.js, copié par build dans chaque
 * front) et le récepteur (TabShell.jsx) pour ne jamais laisser cette
 * chaîne diverger silencieusement entre les deux bouts. */
export const UNSAVED_CHANGES_MESSAGE_TYPE = "supervision-si:unsaved-changes";

/** Valide la FORME d'un message reçu via `postMessage` avant de lui
 * faire confiance -- ne remplace JAMAIS la vérification d'origine
 * (`event.origin`, faite par l'appelant côté TabShell), mais protège
 * contre un message malformé même venu de la bonne origine (bug côté
 * application embarquée, ou évolution future du protocole) --
 * jamais une exception ici, une forme inattendue est simplement
 * ignorée. */
export function isValidUnsavedChangesMessage(data) {
  return !!data && typeof data === "object" && data.type === UNSAVED_CHANGES_MESSAGE_TYPE && typeof data.value === "boolean";
}

/** Retrouve l'ID d'onglet correspondant à la fenêtre SOURCE d'un
 * message reçu (`event.source`, le `contentWindow` d'une iframe) --
 * pure comparaison de RÉFÉRENCE, jamais un lookup par URL/titre :
 * une même application peut être ouverte dans plusieurs onglets à la
 * fois (voir createTab), seule l'identité de la fenêtre distingue
 * lesquels. `tabWindows` : liste de paires [tabId, window]. undefined
 * si aucune correspondance (onglet déjà fermé entre l'envoi et la
 * réception, ou source inconnue) -- jamais une exception. */
export function findTabIdForWindow(tabWindows, sourceWindow) {
  const entry = (tabWindows || []).find(([, win]) => win === sourceWindow);
  return entry ? entry[0] : undefined;
}

// --- Mémorisation des onglets ouverts (backlog hub, livraison #112) ---
// "à la réouverture" -- survit à un rechargement/une fermeture du
// NAVIGATEUR sur ce même appareil, jamais un réglage de compte à
// synchroniser entre appareils (voir hub/README.md pour ce choix
// assumé) -- même esprit que shared/preferences.js (thème),
// stockage LOCAL fait par le composant (TabShell.jsx), ces deux
// fonctions ne touchent jamais localStorage elles-mêmes : restent
// pures et testables sans navigateur, comme le reste de ce fichier.

/** Réduit la liste d'onglets vivants à sa forme stockable -- jamais
 * les URLs/titres (re-résolus depuis `fronts` à la restauration, plus
 * frais qu'une copie figée si un front a changé depuis) ni les `id`
 * générés (aléatoires, sans valeur d'une session à l'autre) -- juste
 * QUELLE application (`appId`), dans QUEL ordre, et la POSITION de
 * l'onglet actif (jamais son `id`, régénéré à chaque restauration —
 * voir restoreOpenTabs). */
export function serializeOpenTabs(tabs, activeTabId) {
  const safeTabs = tabs || [];
  return {
    appIds: safeTabs.map((t) => t.appId),
    activeIndex: safeTabs.findIndex((t) => t.id === activeTabId),
  };
}

/** Reconstruit une liste d'onglets FRAÎCHE (nouveaux `id`, voir
 * createTab) depuis la forme stockée. `fronts` : liste des
 * applications actuellement disponibles (déjà filtrée par rôle et par
 * `embeddable`, voir TabShell.jsx) -- une application stockée mais
 * introuvable dedans (retirée, renommée, ou permission perdue depuis)
 * est simplement OMISE, jamais une exception ni un onglet cassé.
 * `activeIndex` recalé automatiquement si des applications manquantes
 * précèdent l'onglet initialement actif (le décalage se fait tout
 * seul, `tabs.length` au moment de l'ajout EST déjà le bon index).
 * Jamais d'exception sur une forme stockée corrompue/inattendue --
 * traitée comme "aucun onglet à restaurer". */
export function restoreOpenTabs(stored, fronts) {
  const appIds = Array.isArray(stored?.appIds) ? stored.appIds : [];
  const storedActiveIndex = typeof stored?.activeIndex === "number" ? stored.activeIndex : -1;
  const frontsById = new Map((fronts || []).map((f) => [f.id, f]));
  let newActiveIndex = -1;
  const tabs = [];
  appIds.forEach((appId, originalIndex) => {
    const front = frontsById.get(appId);
    if (!front) return; // application introuvable désormais -- omise, jamais une exception
    if (originalIndex === storedActiveIndex) newActiveIndex = tabs.length;
    tabs.push(createTab(front));
  });
  return { tabs, activeTabId: tabs[newActiveIndex]?.id ?? null };
}
