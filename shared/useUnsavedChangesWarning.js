/**
 * Avertissement natif du navigateur si la personne ferme l'onglet,
 * recharge la page, ou navigue vers une autre URL alors qu'une
 * modification est en cours de saisie -- demandé explicitement,
 * premier morceau (isolé, volontairement) d'une proposition plus
 * large concernant une coquille à onglets pour l'ensemble du hub.
 *
 * Copié (comme shared/preferences.js) dans chaque front au moment du
 * build, pas un paquet npm partagé -- même raisonnement que le reste
 * de shared/.
 *
 * NE COUVRE QUE "fermeture/navigation hors de l'application"
 * (l'évènement natif `beforeunload`) -- jamais la navigation INTERNE
 * entre onglets/écrans d'une même application React (changer de
 * table dans DBA, par exemple), qui reste de la responsabilité de
 * chaque écran individuellement (voir DBA : les sélecteurs sont déjà
 * désactivés pendant une édition, empêchant cette navigation-là
 * plutôt que de simplement avertir dessus).
 *
 * Depuis backlog hub #1 (livraison #111) : signale AUSSI cet état au
 * HUB PARENT via `postMessage`, pour que fermer un ONGLET précis dans
 * la coquille à onglets (hub/src/TabShell.jsx) -- qui ne déclenche
 * JAMAIS `beforeunload` (ce n'est qu'un retrait du DOM/masquage
 * CSS de l'iframe, pas une navigation) -- avertisse aussi. Message
 * envoyé au `targetOrigin` explicite `window.location.origin` (jamais
 * "*") : tout vit sous la même origine derrière tls-proxy (voir
 * tls-proxy/README.md), aucune raison de laisser fuiter cet état vers
 * une autre origine si jamais cette page était un jour chargée
 * ailleurs. Sans effet si l'application n'est PAS embarquée dans une
 * iframe (`window.parent === window`, cas normal -- accès direct hors
 * du hub) : jamais un message envoyé à soi-même.
 */

import { useEffect } from "react";

/**
 * `hasUnsavedChanges` : booléen (ou fonction sans argument renvoyant
 * un booléen, évaluée à chaque tentative de fermeture -- utile si la
 * valeur peut changer sans re-render, rare mais gardé pour rester
 * robuste) indiquant s'il existe une modification non enregistrée en
 * ce moment. `false`/toujours `false` -- aucun avertissement, jamais
 * un correctif à faire dans l'écran appelant pour "désactiver" le
 * hook, il suffit de lui passer `false`.
 *
 * LIMITE CONNUE (mode fonction) : le postMessage vers le hub se
 * déclenche quand la RÉFÉRENCE de `hasUnsavedChanges` change (même
 * dépendance que l'effet beforeunload ci-dessous) -- en mode
 * booléen (cas courant, voir DBA) chaque changement de valeur change
 * la référence, donc chaque changement est bien signalé. En mode
 * fonction avec une référence STABLE mais un résultat qui varie sans
 * re-render, le hub ne recevrait pas la mise à jour tant qu'aucun
 * autre re-render ne survient -- limite assumée, jamais rencontrée en
 * pratique (aucun appelant actuel n'est dans ce cas), documentée
 * plutôt que silencieuse.
 */
export function useUnsavedChangesWarning(hasUnsavedChanges) {
  useEffect(() => {
    const handler = (event) => {
      const active = typeof hasUnsavedChanges === "function" ? hasUnsavedChanges() : hasUnsavedChanges;
      if (!active) return;
      // preventDefault() + returnValue -- les deux sont nécessaires
      // selon le navigateur pour déclencher la boîte de dialogue
      // native (le TEXTE affiché est imposé par le navigateur
      // lui-même pour des raisons de sécurité -- returnValue n'est
      // JAMAIS montré tel quel à la personne dans les navigateurs
      // modernes, mais reste requis pour activer le mécanisme).
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    if (window.parent === window) return; // pas embarqué dans une iframe du hub -- rien à signaler
    const active = typeof hasUnsavedChanges === "function" ? hasUnsavedChanges() : hasUnsavedChanges;
    try {
      window.parent.postMessage(
        { type: "supervision-si:unsaved-changes", value: !!active },
        window.location.origin
      );
    } catch {
      // Jamais bloquant -- un postMessage refusé (ex. iframe
      // sandboxée différemment qu'attendu) ne doit jamais faire
      // planter l'application embarquée elle-même, seulement priver
      // le hub de cet avertissement précis (beforeunload reste actif
      // de toute façon).
    }
  }, [hasUnsavedChanges]);
}
