// Journalisation des erreurs de liaison DU HUB LUI-MÊME (indicateurs
// de présence, accès aux logs applicatifs) -- demandé explicitement
// après un test où tout apparaissait injoignable sans la moindre
// trace du pourquoi ni du depuis-quand (livraison #141). Réutilise
// le MÊME tampon que les autres logs de prefs-api (voir
// prefs-api/app.py, /hub-log) -- pas un 16e service séparé.
//
// Émission PAR TRANSITION uniquement (jamais à chaque sondage) :
// sans ça, un vrai incident prolongé (tous les services injoignables
// pendant 10 minutes, sondage toutes les 15-30s) remplirait le
// tampon de 200 entrées de messages IDENTIQUES et redondants en
// quelques minutes, chassant tout le reste -- y compris, ironie du
// sort, les vraies erreurs applicatives qu'on cherche justement à
// voir. Une ligne au moment où ça CASSE, une ligne au moment où ça
// REVIENT -- jamais entre les deux.

/** Envoie UNE ligne de journal. Échec de l'envoi lui-même --
 * silencieux, jamais une exception qui remonterait plus haut (si
 * /hub-log est injoignable, il n'y a de toute façon aucun moyen de
 * journaliser CET échec-là -- pas la peine d'insister). */
async function reportHubLog(prefsApiBase, level, message) {
  try {
    await fetch(`${prefsApiBase}/hub-log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ level, message }),
    });
  } catch {
    // volontairement silencieux, voir commentaire ci-dessus
  }
}

/** Compare l'état de présence PRÉCÉDENT au NOUVEAU (objets
 * id -> bool joignable) et journalise UNE ligne par id dont l'état a
 * RÉELLEMENT changé -- jamais pour ceux qui restent identiques d'un
 * sondage à l'autre. `previous` absent (premier sondage) -- rien à
 * comparer, rien journalisé (un premier état "injoignable" au tout
 * premier chargement de la page n'est pas une TRANSITION, juste
 * l'état de départ). `labels` : id -> nom lisible, pour un message
 * utile sans deviner depuis le seul id technique. */
export function logPresenceTransitions(prefsApiBase, previous, current, labels) {
  if (!previous || !current) return;
  for (const id of Object.keys(current)) {
    const wasUp = previous[id];
    const isUp = current[id];
    if (wasUp === undefined) continue; // absent du sondage précédent -- pas une transition constatable
    if (wasUp === isUp) continue; // pas de changement -- rien à journaliser
    const label = labels?.[id] || id;
    reportHubLog(
      prefsApiBase,
      "WARNING",
      isUp ? `${label} : de nouveau joignable` : `${label} : devenu injoignable`
    );
  }
}
