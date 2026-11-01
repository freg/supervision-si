// #874 : contexte de navigation du hub -- un rechargement (F5, rechargement « sans cache » d'une nouvelle livraison,
// retour de Keycloak, PWA relancée) revient sur la page consultée, dans le même onglet interne, à la même position.
// Tout est gardé PAR ONGLET DU NAVIGATEUR (sessionStorage) : deux onglets du hub restent indépendants.
// - vue : `?view=` dans l'URL (lien profond, #559) sinon la dernière vue de cet onglet, sinon l'accueil ;
// - onglets internes des pages : useNavState(scope, clé, défaut) (remplace useState) ;
// - position : défilement de la page et des cadres déroulants (en-têtes fixes, tbody qui défilent) par vue.
import { useCallback, useEffect, useState } from "react";

const KEY = "hub.nav";

function lire() {
  try { return JSON.parse(sessionStorage.getItem(KEY) || "{}") || {}; } catch { return {}; }
}
function ecrire(nav) {
  try { sessionStorage.setItem(KEY, JSON.stringify(nav)); } catch { /* stockage indisponible : on perd seulement le confort */ }
}

const VUE_OK = /^[a-z0-9:-]+$/;

/** Vue à ouvrir au chargement : lien profond, sinon la dernière vue de cet onglet, sinon l'accueil. */
export function vueInitiale(defaut = "grid") {
  try {
    const v = new URLSearchParams(window.location.search).get("view");
    if (v && VUE_OK.test(v)) return v;
  } catch { /* rien */ }
  const n = lire();
  return n.view && VUE_OK.test(n.view) ? n.view : defaut;
}

/** Vue courante : mémorisée et posée dans l'URL (`?view=`), les autres paramètres de l'URL étant gardés tels quels
 *  tant que la vue ne change pas (ils appartiennent à la vue : agent sélectionné, onglet d'un lien…). */
export function memoriserVue(view) {
  const n = lire();
  const change = n.view !== view;
  n.view = view;
  ecrire(n);
  try {
    const u = new URL(window.location.href);
    const avant = u.searchParams.get("view");
    if (avant === view || (!avant && view === "grid")) return;
    if (change && avant) {   // changement de vue : les paramètres de l'ancienne vue ne la suivent pas
      for (const k of [...u.searchParams.keys()]) if (k !== "v") u.searchParams.delete(k);
    }
    if (view === "grid") u.searchParams.delete("view"); else u.searchParams.set("view", view);
    window.history.replaceState(window.history.state, "", u.pathname + (u.searchParams.toString() ? "?" + u.searchParams : "") + u.hash);
  } catch { /* rien */ }
}

/** URL à retrouver après le retour de Keycloak (qui revient sur « / ») : la vue de cet onglet. */
export function urlApresConnexion() {
  const v = lire().view;
  return window.location.pathname + (v && v !== "grid" && VUE_OK.test(v) ? "?view=" + encodeURIComponent(v) : "");
}

/** useState mémorisé pour la vue courante de cet onglet du navigateur (onglet interne d'une page, section ouverte…).
 *  `scope` : nom du composant (évite les collisions entre une page et les composants qu'elle contient). */
export function useNavState(scope, cle, defaut) {
  const k = `${lire().view || "grid"}|${scope}.${cle}`;
  const [v, setV] = useState(() => {
    const s = (lire().etats || {})[k];
    return s === undefined ? defaut : s;
  });
  const set = useCallback((x) => {
    setV((ancien) => {
      const nv = typeof x === "function" ? x(ancien) : x;
      const n = lire();
      n.etats = { ...(n.etats || {}), [k]: nv };
      ecrire(n);
      return nv;
    });
  }, [k]);
  return [v, set];
}

// -- position dans la page --------------------------------------------------------------------------------------------
function chemin(el) {
  const racine = document.getElementById("root") || document.body;
  const p = [];
  for (let e = el; e && e !== racine; e = e.parentElement) {
    const parent = e.parentElement;
    if (!parent) return null;
    p.unshift(`${Array.prototype.indexOf.call(parent.children, e)}${e.tagName[0]}`);
  }
  return p.join("/");
}
function trouver(c) {
  let e = document.getElementById("root") || document.body;
  for (const pas of c.split("/")) {
    const i = parseInt(pas, 10);
    e = e && e.children[i];
    if (!e || e.tagName[0] !== pas.slice(-1)) return null;
  }
  return e;
}

/** Mémorise en continu la position de défilement de la vue (fenêtre + cadres déroulants), et la restaure UNE fois après
 *  un rechargement, en réessayant le temps que les données arrivent (4 s au plus). */
export function usePositionMemorisee(view) {
  useEffect(() => {
    let t = null;
    const noter = () => {
      clearTimeout(t);
      t = setTimeout(() => {
        const pos = [];
        if (window.scrollY > 0) pos.push({ c: "window", y: window.scrollY });
        document.querySelectorAll("#root div, #root main, #root section, #root tbody, #root ul").forEach((el) => {
          if (el.scrollTop > 0 || el.scrollLeft > 0) {
            const c = chemin(el);
            if (c) pos.push({ c, y: el.scrollTop, x: el.scrollLeft });
          }
        });
        const n = lire();
        n.positions = { ...(n.positions || {}), [view]: pos };
        ecrire(n);
      }, 300);
    };
    window.addEventListener("scroll", noter, true);
    window.addEventListener("pagehide", noter);
    return () => { window.removeEventListener("scroll", noter, true); window.removeEventListener("pagehide", noter); clearTimeout(t); };
  }, [view]);
}

let restaure = false;
export function restaurerPosition(view) {
  if (restaure) return;     // une seule fois, au chargement : naviguer vers une autre vue repart du haut
  restaure = true;
  const pos = (lire().positions || {})[view] || [];
  if (!pos.length) return;
  const reste = new Set(pos.map((_, i) => i));
  const debut = Date.now();
  const essai = () => {
    for (const i of [...reste]) {
      const p = pos[i];
      if (p.c === "window") {
        if (document.documentElement.scrollHeight - window.innerHeight >= p.y - 2) { window.scrollTo(0, p.y); reste.delete(i); }
        continue;
      }
      const el = trouver(p.c);
      if (el && el.scrollHeight - el.clientHeight >= p.y - 2) { el.scrollTop = p.y; el.scrollLeft = p.x || 0; reste.delete(i); }
    }
    if (reste.size && Date.now() - debut < 4000) setTimeout(essai, 150);
  };
  setTimeout(essai, 100);
}

/** Pour les pages dont l'onglet vient déjà d'un lien (`?tab=`…) : valeur mémorisée de cet onglet du navigateur, à
 *  utiliser APRÈS le paramètre du lien et AVANT la valeur par défaut ; memoriserEtat() à chaque changement. */
export function etatMemorise(scope, cle) {
  return (lire().etats || {})[`${lire().view || "grid"}|${scope}.${cle}`];
}
export function memoriserEtat(scope, cle, valeur) {
  const n = lire();
  n.etats = { ...(n.etats || {}), [`${n.view || "grid"}|${scope}.${cle}`]: valeur };
  ecrire(n);
}
