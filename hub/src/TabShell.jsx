import { useEffect, useRef, useState } from "react";
import {
  openTab, closeTab, isValidUnsavedChangesMessage, findTabIdForWindow,
  serializeOpenTabs, restoreOpenTabs,
} from "./tabs.js";
import { postHubEvent } from "./hubEvents.js";
import HubTimeline from "./HubTimeline.jsx";

// Mémorisation des onglets ouverts -- backlog hub, livraison #112.
// "à la réouverture" : survit à un rechargement/une fermeture du
// NAVIGATEUR sur ce même appareil (localStorage, même principe que
// shared/preferences.js pour le thème) -- pas un réglage de compte à
// synchroniser entre appareils (prefs-api), choix assumé documenté
// dans hub/README.md.
const OPEN_TABS_STORAGE_KEY = "supervision-si:hub:open-tabs";

function loadStoredOpenTabs(fronts) {
  try {
    const raw = localStorage.getItem(OPEN_TABS_STORAGE_KEY);
    if (!raw) return { tabs: [], activeTabId: null };
    return restoreOpenTabs(JSON.parse(raw), fronts);
  } catch {
    // Stockage indisponible (navigation privée, quota) ou JSON
    // corrompu -- retombe sur "aucun onglet", comportement identique
    // à avant ce chantier, jamais une exception qui casserait tout
    // le hub au démarrage.
    return { tabs: [], activeTabId: null };
  }
}

// Visibilité de la timeline -- demandé explicitement ("pouvoir la
// masquer"). Même principe/même appareil que OPEN_TABS_STORAGE_KEY
// juste au-dessus -- pas un réglage de compte à synchroniser entre
// appareils. Visible PAR DÉFAUT (true) si jamais rien n'est encore
// stocké -- comportement identique à avant ce chantier tant que la
// personne n'a jamais touché au nouveau bouton.
const TIMELINE_VISIBLE_STORAGE_KEY = "supervision-si:hub:timeline-visible";

function loadStoredTimelineVisible() {
  try {
    const raw = localStorage.getItem(TIMELINE_VISIBLE_STORAGE_KEY);
    if (raw === null) return true;
    return JSON.parse(raw) === true;
  } catch {
    return true;
  }
}

/**
 * Coquille à onglets -- demandé explicitement ("façon navigateur
 * web"), premier étage d'une proposition plus large (le contexte par
 * onglet et l'historique versionné restent des chantiers séparés,
 * discutés et volontairement mis de côté pour l'instant).
 *
 * Chaque onglet est une <iframe> pointant vers une application du
 * hub -- possible car toutes vivent sous la MÊME origine (une seule
 * entrée par chemin via tls-proxy, voir tls-proxy/README.md), aucun
 * souci cross-origin réel à gérer. Seules les applications
 * `embeddable: true` (voir lib.js) sont proposées ici -- Keycloak
 * (X-Frame-Options natif) et l'administration du coffre-fort (port
 * LAN direct, origine différente) restent des liens classiques,
 * jamais un onglet.
 *
 * TOUTES les iframes ouvertes restent montées en permanence, quel
 * que soit l'onglet affiché -- seule leur visibilité CSS change
 * (`display: none`/`block`). Les démonter à chaque bascule perdrait
 * le travail en cours dans les onglets inactifs, contraire à
 * l'objectif même de cette coquille.
 *
 * Compromis assumé et à connaître : la barre d'adresse du navigateur
 * reste sur l'URL du hub, quel que soit l'onglet actif à
 * l'intérieur -- normal pour ce type de coquille (comme VS Code web,
 * par exemple).
 *
 * Depuis backlog hub #1 (livraison #111) : écoute le protocole
 * postMessage (voir tabs.js, shared/useUnsavedChangesWarning.js) pour
 * savoir quels onglets ont des modifications non enregistrées --
 * fermer un onglet PRÉCIS (contrairement à `beforeunload`, qui ne
 * couvre que fermer/recharger TOUT le navigateur) demande alors
 * confirmation. Dégrade proprement pour toute application qui
 * n'appelle pas encore ce hook (aucun message reçu -> jamais
 * d'avertissement, comportement identique à avant ce chantier).
 *
 * Depuis backlog hub #2 (livraison #112) : les onglets ouverts (et
 * lequel est actif) sont mémorisés dans localStorage -- restaurés
 * automatiquement à la prochaine ouverture du hub sur ce même
 * appareil (voir loadStoredOpenTabs/tabs.js, restoreOpenTabs).
 *
 * Depuis la timeline du hub (livraison #119) : chaque bascule
 * d'onglet actif (clic sur un onglet existant, ou ouverture d'une
 * nouvelle application qui devient l'onglet actif) émet un événement
 * "mouvement_onglet" (voir shared/hubEvents.js) -- jamais pour un
 * clic sur l'onglet DÉJÀ actif (aucun changement réel).
 *
 * Timeline du hub, étape 3 (livraison #120) : `HubTimeline` rendue en
 * colonne DROITE fixe (voir `.hub-tabshell-body`), à côté de
 * `.hub-tab-content` plutôt que par-dessus -- "à droite en bordure
 * d'écran" demandé explicitement.
 *
 * Timeline masquable (livraison #130, demandé explicitement) :
 * bouton dédié dans la barre d'onglets, état mémorisé par appareil
 * (même principe que la mémorisation des onglets ouverts ci-dessus),
 * visible par défaut.
 */
export default function TabShell({ fronts, onBack, login, prefsApiBase }) {
  const embeddableFronts = fronts.filter((f) => f.embeddable);

  // Calculé UNE SEULE FOIS (pas un par useState -- loadStoredOpenTabs
  // génère de nouveaux id à chaque appel via createTab, deux appels
  // indépendants produiraient un activeTabId qui ne correspond à
  // AUCUN id de tabs). Motif "ref mémoïsée pendant le rendu" --
  // jamais recalculé aux rendus suivants (le stockage n'a de sens
  // qu'AU DÉMARRAGE, pas à chaque re-render).
  const initialOpenTabsRef = useRef(null);
  if (initialOpenTabsRef.current === null) {
    initialOpenTabsRef.current = loadStoredOpenTabs(embeddableFronts);
  }
  const [tabs, setTabs] = useState(() => initialOpenTabsRef.current.tabs);
  const [activeTabId, setActiveTabId] = useState(() => initialOpenTabsRef.current.activeTabId);
  const [showPicker, setShowPicker] = useState(false);
  // tabId -> booléen "modification non enregistrée en cours",
  // alimenté par postMessage. État PAR ONGLET (pas juste un booléen
  // global) -- plusieurs onglets peuvent être dans des états
  // différents en même temps.
  const [unsavedTabIds, setUnsavedTabIds] = useState({});
  // tabId -> élément <iframe> DOM -- registre de correspondance pour
  // retrouver quel onglet a envoyé un message donné (comparaison de
  // référence sur .contentWindow, voir findTabIdForWindow). Une ref,
  // jamais un state : ne doit provoquer aucun re-render à lui seul.
  const iframeRefs = useRef(new Map());

  // Visibilité de la timeline -- demandé explicitement, voir
  // TIMELINE_VISIBLE_STORAGE_KEY plus haut pour le raisonnement.
  const [showTimeline, setShowTimeline] = useState(() => loadStoredTimelineVisible());

  useEffect(() => {
    try {
      localStorage.setItem(TIMELINE_VISIBLE_STORAGE_KEY, JSON.stringify(showTimeline));
    } catch {
      // Stockage indisponible -- la bascule marche quand même pour
      // cette session, seule la mémorisation pour la PROCHAINE visite
      // est perdue silencieusement, jamais bloquant ici.
    }
  }, [showTimeline]);

  // Sauvegarde à CHAQUE changement (ouverture, fermeture, bascule
  // d'onglet actif) -- jamais bloquant, voir loadStoredOpenTabs pour
  // le raisonnement symétrique côté lecture.
  useEffect(() => {
    try {
      localStorage.setItem(OPEN_TABS_STORAGE_KEY, JSON.stringify(serializeOpenTabs(tabs, activeTabId)));
    } catch {
      // Stockage indisponible -- la personne garde son travail en
      // cours dans le hub, seule la mémorisation pour la PROCHAINE
      // visite est perdue silencieusement, jamais bloquant ici.
    }
  }, [tabs, activeTabId]);

  useEffect(() => {
    function handleMessage(event) {
      // Vérification d'origine D'ABORD, avant même de regarder la
      // forme du message -- tout vit sous la même origine derrière
      // tls-proxy, un message d'ailleurs n'a jamais à être considéré.
      if (event.origin !== window.location.origin) return;
      if (!isValidUnsavedChangesMessage(event.data)) return;
      const tabWindows = Array.from(iframeRefs.current.entries()).map(([id, el]) => [id, el?.contentWindow]);
      const tabId = findTabIdForWindow(tabWindows, event.source);
      if (!tabId) return; // onglet déjà fermé entre l'envoi et la réception, ou source inconnue -- jamais une exception
      setUnsavedTabIds((prev) => (prev[tabId] === event.data.value ? prev : { ...prev, [tabId]: event.data.value }));
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const handleOpenTab = (front) => {
    const newTabs = openTab(tabs, front);
    const newTab = newTabs[newTabs.length - 1];
    setTabs(newTabs);
    setActiveTabId(newTab.id);
    setShowPicker(false);
    postHubEvent(prefsApiBase, { login, category: "mouvement_onglet", label: newTab.title });
  };

  // Émet "mouvement_onglet" jamais pour un clic sur l'onglet DÉJÀ
  // actif -- aucun changement réel, pas un mouvement.
  const handleSelectTab = (tabId) => {
    if (tabId === activeTabId) return;
    const tab = tabs.find((t) => t.id === tabId);
    setActiveTabId(tabId);
    postHubEvent(prefsApiBase, { login, category: "mouvement_onglet", label: tab?.title || null });
  };

  const handleCloseTab = (tabId) => {
    if (unsavedTabIds[tabId]) {
      const confirmed = window.confirm(
        "Cet onglet a des modifications non enregistrées. Le fermer quand même ?"
      );
      if (!confirmed) return;
    }
    const result = closeTab(tabs, tabId, activeTabId);
    setTabs(result.tabs);
    setActiveTabId(result.activeTabId);
    iframeRefs.current.delete(tabId);
    setUnsavedTabIds((prev) => {
      if (!(tabId in prev)) return prev;
      const next = { ...prev };
      delete next[tabId];
      return next;
    });
  };

  return (
    <div className="hub-tabshell">
      <div className="hub-tabshell-topbar">
        <button className="secondary" onClick={onBack} title="Retour à l'accueil du hub">◀ Accueil</button>
      </div>
      <div className="hub-tabbar">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className={`hub-tab${tab.id === activeTabId ? " active" : ""}`}
            onClick={() => handleSelectTab(tab.id)}
          >
            <span className="hub-tab-title">
              {tab.title}
              {unsavedTabIds[tab.id] && (
                <span className="hub-tab-unsaved-dot" title="Modifications non enregistrées dans cet onglet">●</span>
              )}
            </span>
            <button
              className="hub-tab-close"
              onClick={(e) => { e.stopPropagation(); handleCloseTab(tab.id); }}
              title="Fermer cet onglet"
            >
              ✕
            </button>
          </div>
        ))}
        <button className="hub-tab-add" onClick={() => setShowPicker((v) => !v)} title="Ouvrir une application">
          +
        </button>
        <button
          className="hub-timeline-toggle"
          onClick={() => setShowTimeline((v) => !v)}
          title={showTimeline ? "Masquer la timeline" : "Afficher la timeline"}
        >
          🕒
        </button>
      </div>

      {/* Bug réel signalé (le "+" ne faisait rien, visuellement) --
          rendu ICI, en dehors de .hub-tabbar : ce conteneur a
          overflow-x: auto pour le défilement horizontal des onglets,
          ce qui recadre implicitement aussi tout débordement
          vertical de ses enfants (overflow-y devient "auto" dès que
          overflow-x est fixé, même sans le déclarer explicitement) --
          le menu se rendait bel et bien, juste invisible, coupé par
          ce recadrage du parent. */}
      {showPicker && (
        <div className="hub-tab-picker">
          {embeddableFronts.length === 0 && <p className="muted">Aucune application disponible.</p>}
          {embeddableFronts.map((f) => (
            <button key={f.id} className="hub-tab-picker-item" onClick={() => handleOpenTab(f)}>
              {f.name}
            </button>
          ))}
        </div>
      )}

      <div className="hub-tabshell-body">
        <div className="hub-tab-content">
          {tabs.length === 0 && (
            <p className="muted hub-tab-empty">Aucun onglet ouvert — cliquez "+" pour en ouvrir un.</p>
          )}
          {tabs.map((tab) => (
            <iframe
              key={tab.id}
              ref={(el) => {
                if (el) iframeRefs.current.set(tab.id, el);
                else iframeRefs.current.delete(tab.id);
              }}
              src={tab.url}
              title={tab.title}
              className="hub-tab-iframe"
              style={{ display: tab.id === activeTabId ? "block" : "none" }}
            />
          ))}
        </div>
        {showTimeline && <HubTimeline login={login} prefsApiBase={prefsApiBase} />}
      </div>
    </div>
  );
}
