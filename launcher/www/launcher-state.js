// Logique PURE de gestion d'état des feux -- testable sans DOM ni
// réseau (voir launcher.js pour le rendu réel/les appels fetch).

// Au-delà de ce délai sans confirmation, on abandonne l'attente et on
// affiche la réalité telle que reçue -- jamais bloqué en orange
// indéfiniment si une action a échoué silencieusement côté serveur
// (ex. `docker compose start` qui échoue sans que le service ne
// démarre jamais).
export const MAX_PENDING_MS = 15000;

export function initialState() {
  return { status: "unknown", pending: null, pendingSince: null };
}

/** Appelé au clic sur un feu -- ne fait rien si une action est déjà en
 * cours (orange), ou si le statut est encore inconnu (gris, on ne
 * sait pas quelle action aurait un sens). Renvoie le nouvel état ET
 * l'action à déclencher réellement ("start"|"stop"|null) -- décision
 * INVERSÉE par rapport à la couleur cliquée : rouge (arrêté) → clic →
 * démarre ; vert (actif) → clic → arrête. */
export function onClick(state, now) {
  if (state.pending) return { state, action: null };
  if (state.status === "up") {
    return { state: { ...state, pending: "stopping", pendingSince: now }, action: "stop" };
  }
  if (state.status === "down") {
    return { state: { ...state, pending: "starting", pendingSince: now }, action: "start" };
  }
  return { state, action: null };
}

/** Appelé à chaque réception d'un nouveau statut confirmé (sondage
 * périodique). Efface "pending" si le nouveau statut correspond à ce
 * qui était attendu, OU si l'attente a dépassé MAX_PENDING_MS. */
export function onStatusUpdate(state, newStatus, now) {
  let pending = state.pending;
  if (pending === "starting" && newStatus === "up") pending = null;
  if (pending === "stopping" && newStatus === "down") pending = null;
  if (pending && state.pendingSince !== null && now - state.pendingSince > MAX_PENDING_MS) {
    pending = null;
  }
  return { ...state, status: newStatus, pending, pendingSince: pending ? state.pendingSince : null };
}

/** Couleur à afficher pour un état donné -- pure fonction de
 * présentation, testable indépendamment du DOM. */
export function colorFor(state) {
  if (state.pending) return "orange";
  if (state.status === "up") return "green";
  if (state.status === "down") return "red";
  return "gray";
}
