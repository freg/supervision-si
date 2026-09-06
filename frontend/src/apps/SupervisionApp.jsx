import { useEffect, useState } from "react";
import { fetchSourceData, fetchSources, registerSource, ingestSource, fetchMatchingSources, deleteSource, restoreSource, fetchDeletedSources, createSourceFromSelection } from "../api.js";
import { isPathSelected, computeReinclusion } from "../components/JsonTree.jsx";
import SourcesPanel from "../components/SourcesPanel.jsx";
import MapPanel from "../components/MapPanel.jsx";
import SynthesisPanel from "../components/SynthesisPanel.jsx";
import SelectionBasket from "../components/SelectionBasket.jsx";
import RadialTree from "../components/RadialTree.jsx";
import IpamOverviewPanel from "../components/IpamOverviewPanel.jsx";

const POLL_INTERVAL_MS = 10000;

export default function SupervisionApp({ onNavigate, mapFocusRequest, onMapFocusConsumed, mapMarkers }) {
  const [discoveredSources, setDiscoveredSources] = useState([]);
  const [payloads, setPayloads] = useState({}); // { [sourceName]: apiResponse }
  const [selectedSource, setSelectedSource] = useState(null);
  const [deletedSources, setDeletedSources] = useState([]);
  const [showDeletedSources, setShowDeletedSources] = useState(false);
  const [selectedFeature, setSelectedFeature] = useState(null);

  // Calendrier — overlay au-dessus de la carte
  const [showCalendar, setShowCalendar] = useState(false);
  const [radialTreeExpanded, setRadialTreeExpanded] = useState(false);
  // Réduction manuelle de la carte -- demandée explicitement (bouton,
  // pas automatique) après retour réel : la carte, "bien qu'importante,
  // n'a pas à être omniprésente". Jamais liée à l'état de la
  // sélection -- volontairement laissée au choix de la personne.
  const [mapCollapsed, setMapCollapsed] = useState(false);
  const [selectedDates, setSelectedDates] = useState(new Set());
  const [keywordExpr, setKeywordExpr] = useState(""); // ex: "incident OR panne AND regions"

  // Deux voies d'entrée dans la corbeille, fusionnées :
  // - dateMatchedNames : calculé automatiquement depuis la sélection calendrier
  // - manualNames : coché directement dans la liste des sources (colonne gauche)
  const [dateMatchedNames, setDateMatchedNames] = useState(new Set());
  const [manualNames, setManualNames] = useState(new Set());

  // Corbeille — { [sourceName]: { deselectedPaths: Set<string> } }
  const [basketEntries, setBasketEntries] = useState({});

  useEffect(() => {
    let cancelled = false;

    async function pollAll() {
      const sources = await fetchSources();
      if (cancelled) return;
      setDiscoveredSources(sources);

      const registeredNames = sources.filter((s) => s.registered).map((s) => s.source);
      const results = await Promise.all(
        registeredNames.map(async (name) => [name, await fetchSourceData(name)])
      );
      if (!cancelled) {
        setPayloads(Object.fromEntries(results));
      }
    }

    pollAll();
    const interval = setInterval(pollAll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  // Résout la sélection temporelle en sources concernées.
  useEffect(() => {
    let cancelled = false;

    async function resolveDateMatches() {
      if (selectedDates.size === 0) {
        if (!cancelled) setDateMatchedNames(new Set());
        return;
      }
      const matches = await fetchMatchingSources(Array.from(selectedDates), keywordExpr);
      if (!cancelled) setDateMatchedNames(new Set(matches.map((m) => m.source)));
    }

    resolveDateMatches();
    return () => {
      cancelled = true;
    };
  }, [selectedDates, keywordExpr]);

  // Fusionne les deux voies (dates + sélection manuelle) dans la corbeille,
  // en préservant l'état de sélection fine des sources qui restent présentes.
  useEffect(() => {
    const unionNames = new Set([...dateMatchedNames, ...manualNames]);
    setBasketEntries((prev) => {
      const next = {};
      for (const name of unionNames) {
        next[name] = prev[name] || { deselectedPaths: new Set() };
      }
      return next;
    });
  }, [dateMatchedNames, manualNames]);

  function handleSelectSource(name) {
    setSelectedSource(name);
    setSelectedFeature(null);
  }

  function handleFeatureSelect(feature) {
    setSelectedFeature(feature);
  }

  async function handleRegisterSource(name) {
    const ok = await registerSource(name);
    if (ok) {
      const sources = await fetchSources();
      setDiscoveredSources(sources);
      const payload = await fetchSourceData(name);
      setPayloads((prev) => ({ ...prev, [name]: payload }));
    }
  }

  async function handleDeleteSource(name) {
    const ok = await deleteSource(name);
    if (ok) {
      const sources = await fetchSources();
      setDiscoveredSources(sources);
      setPayloads((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
      if (selectedSource === name) setSelectedSource(null);
      const deleted = await fetchDeletedSources();
      setDeletedSources(deleted);
    }
  }

  async function handleRestoreSource(name) {
    const ok = await restoreSource(name);
    if (ok) {
      const sources = await fetchSources();
      setDiscoveredSources(sources);
      const payload = await fetchSourceData(name);
      setPayloads((prev) => ({ ...prev, [name]: payload }));
      const deleted = await fetchDeletedSources();
      setDeletedSources(deleted);
    }
  }

  async function handleToggleDeletedPanel() {
    if (!showDeletedSources) {
      const deleted = await fetchDeletedSources();
      setDeletedSources(deleted);
    }
    setShowDeletedSources((v) => !v);
  }

  // Rafraîchit la liste + le payload d'UNE source après qu'elle a été
  // enregistrée côté serveur (par n'importe quel chemin : injection
  // manuelle, "Figer cette vue" depuis un onglet base, ou "Charger
  // comme source" depuis la carte externe) — évite d'attendre le
  // prochain sondage (jusqu'à 10s) pour la voir apparaître.
  async function refreshAfterRegistration(name) {
    const sources = await fetchSources();
    setDiscoveredSources(sources);
    const payload = await fetchSourceData(name);
    setPayloads((prev) => ({ ...prev, [name]: payload }));
  }

  async function handleInject(name, data) {
    const result = await ingestSource(name, data);
    if (result.ok) {
      await refreshAfterRegistration(name);
    }
    return result;
  }

  function handleToggleDate(dateStr) {
    setSelectedDates((prev) => {
      const next = new Set(prev);
      if (next.has(dateStr)) {
        next.delete(dateStr);
      } else {
        next.add(dateStr);
      }
      return next;
    });
  }

  function handleClearDates() {
    setSelectedDates(new Set());
  }

  function handleToggleManualSelection(name) {
    setManualNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  // Case à cocher unifiée de la colonne des sources : si la source est déjà
  // dans la corbeille (peu importe la voie), la retirer entièrement ;
  // sinon l'ajouter manuellement. Homogénéise l'action avec l'état affiché
  // (coché/indéterminé) plutôt que de ne piloter que la voie manuelle.
  function handleToggleSourceInBasket(name) {
    if (basketEntries[name]) {
      handleRemoveFromBasket(name);
    } else {
      handleToggleManualSelection(name);
    }
  }

  function handleToggleBasketNode(source, path) {
    setBasketEntries((prev) => {
      const entry = prev[source];
      if (!entry) return prev;

      const nextDeselected = new Set(entry.deselectedPaths);
      const currentlySelected = isPathSelected(path, nextDeselected);
      if (currentlySelected) {
        nextDeselected.add(path);
      } else {
        nextDeselected.delete(path);
      }

      return { ...prev, [source]: { deselectedPaths: nextDeselected } };
    });
  }

  function handleRemoveFromBasket(source) {
    // Retrait explicite : coupe les deux voies d'entrée pour cette source,
    // sinon elle réapparaîtrait immédiatement via la fusion automatique.
    setManualNames((prev) => {
      const next = new Set(prev);
      next.delete(source);
      return next;
    });
    setBasketEntries((prev) => {
      const next = { ...prev };
      delete next[source];
      return next;
    });
  }

  // "Verser vers la bannette" : prend l'état ACTUEL de la corbeille
  // (éphémère, en mémoire, perdu au rechargement) et le persiste comme
  // nouvelle source côté API — repris dans la colonne des sources,
  // section "Bannette d'interaction", disponible pour d'autres modules
  // ou une prochaine session.
  //
  // SIMPLIFICATION ASSUMÉE pour cette première version : envoie les
  // données BRUTES (non filtrées) de chaque source de la corbeille,
  // pas encore le filtrage fin par nœud désélectionné (deselectedPaths).
  // Reproduire cette logique récursive correctement sans jamais pouvoir
  // la vérifier visuellement était un risque jugé trop réel pour cette
  // livraison — le filtrage fin reste à faire dans un second temps,
  // une fois cette première brique en place et testée en conditions
  // réelles.
  const [pourToTray, setPourToTray] = useState({ status: "idle" }); // idle | busy | { ok, error? }

  async function handlePourToTray() {
    const names = Object.keys(basketEntries);
    if (names.length === 0) return;
    setPourToTray({ status: "busy" });
    const combined = Object.fromEntries(names.map((name) => [name, basketSourceData[name] ?? null]));
    const label = names.length === 1 ? names[0] : `${names.length}-sources-${Date.now()}`;
    const res = await createSourceFromSelection(label, combined);
    if (res.ok) {
      setPourToTray({ status: "ok" });
      const sources = await fetchSources();
      setDiscoveredSources(sources);
    } else {
      setPourToTray({ status: "error", error: res.error });
    }
  }

  // Bascule "intelligente" utilisée par le second clic de l'arbre radial
  // en mode aperçu couvrant : retrait simple si le nœud est déjà
  // sélectionné, réintégration précise (préserve les branches voisines)
  // sinon — contrairement à handleToggleBasketNode qui suppose toujours
  // qu'on part d'un état sélectionné (cas de l'arbre JSON de la corbeille,
  // qui ne montre jamais de nœud non sélectionné).
  function handleSmartToggle(source, path) {
    const entry = basketEntries[source];
    if (!entry) return;

    const rawData = basketSourceData[source];
    const globallySelected = isPathSelected(path, entry.deselectedPaths);

    setBasketEntries((prev) => {
      const current = prev[source];
      if (!current) return prev;

      const nextDeselected = globallySelected
        ? new Set([...current.deselectedPaths, path])
        : computeReinclusion(current.deselectedPaths, rawData, path);

      return { ...prev, [source]: { deselectedPaths: nextDeselected } };
    });
  }

  const registeredSources = discoveredSources.filter((s) => s.registered);
  // Bannette d'interaction : origine "selection" (versée depuis la
  // corbeille), jamais auto-enregistrée -- distincte des "Propositions"
  // classiques (dépôt externe détecté au scan). Un même filtre
  // (!registered || modified) EXCLUT désormais explicitement l'origine
  // "selection" pour ne pas la compter deux fois dans les deux listes.
  const traySources = discoveredSources.filter((s) => !s.registered && s.origin === "selection");
  const proposedSources = discoveredSources.filter(
    (s) => (!s.registered || s.status === "modified") && s.origin !== "selection"
  );

  const sourcePayload = selectedSource ? payloads[selectedSource] : null;
  const rawGeojsonData = sourcePayload?.status === "ok" ? sourcePayload.data : null;

  // Si la source affichée est aussi dans la corbeille, la carte ne montre
  // que les features encore cochées — la corbeille et la carte doivent
  // rester cohérentes plutôt que de vivre indépendamment.
  let geojsonData = rawGeojsonData;
  const basketEntryForSelected = selectedSource ? basketEntries[selectedSource] : null;
  if (rawGeojsonData && basketEntryForSelected && Array.isArray(rawGeojsonData.features)) {
    const filteredFeatures = rawGeojsonData.features.filter((_, index) =>
      isPathSelected(`$.features[${index}]`, basketEntryForSelected.deselectedPaths)
    );
    geojsonData = { ...rawGeojsonData, features: filteredFeatures };
  }

  const selectedLatLng =
    selectedFeature?.geometry?.type === "Point"
      ? [selectedFeature.geometry.coordinates[1], selectedFeature.geometry.coordinates[0]]
      : null;

  const basketSourceData = Object.fromEntries(
    Object.keys(basketEntries).map((name) => [name, payloads[name]?.data])
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="status-dot ok pulse" />
        <strong>Supervision SI</strong>
        <span>— vue centralisée</span>
      </header>

      <SourcesPanel
        registeredSources={registeredSources.map((s) => ({ name: s.source, payload: payloads[s.source] }))}
        proposedSources={proposedSources}
        traySources={traySources}
        selectedSource={selectedSource}
        onSelectSource={handleSelectSource}
        onRegisterSource={handleRegisterSource}
        basketEntries={basketEntries}
        manualSelection={manualNames}
        onToggleSourceInBasket={handleToggleSourceInBasket}
        onInject={handleInject}
        onDeleteSource={handleDeleteSource}
        deletedSources={deletedSources}
        showDeletedSources={showDeletedSources}
        onToggleDeletedPanel={handleToggleDeletedPanel}
        onRestoreSource={handleRestoreSource}
        onNavigate={onNavigate}
        onSourceRegistered={refreshAfterRegistration}
        onPourSelectionToTray={handlePourToTray}
      />

      <MapPanel
        geojsonData={geojsonData}
        onFeatureSelect={handleFeatureSelect}
        selectedLatLng={selectedLatLng}
        showCalendar={showCalendar}
        onOpenCalendar={() => setShowCalendar(true)}
        onCloseCalendar={() => setShowCalendar(false)}
        calendarProps={{
          selectedDates,
          onToggleDate: handleToggleDate,
          onClearDates: handleClearDates,
          keywordExpr,
          onChangeKeywords: setKeywordExpr,
        }}
        radialTreeExpanded={radialTreeExpanded}
        onCloseRadialTree={() => setRadialTreeExpanded(false)}
        radialTreeProps={{
          basketEntries,
          sourceData: basketSourceData,
          onToggleSelection: handleSmartToggle,
        }}
        focusRequest={mapFocusRequest}
        onFocusConsumed={onMapFocusConsumed}
        markers={mapMarkers}
        collapsed={mapCollapsed}
        onToggleCollapsed={() => setMapCollapsed((v) => !v)}
      />

      <div className="col-synthesis">
        <div className="synthesis-section">
          <div className="synthesis-section-title">IPAM</div>
          <IpamOverviewPanel />
        </div>
        <div className="synthesis-section">
          <div className="synthesis-section-title">Synthèse</div>
          <SynthesisPanel
            selectedSource={selectedSource}
            sourcePayload={sourcePayload}
            selectedFeature={selectedFeature}
          />
        </div>
        <div className="synthesis-section synthesis-section-grow">
          <div className="synthesis-section-title">
            Sélection {Object.keys(basketEntries).length > 0 && `(${Object.keys(basketEntries).length})`}
            {Object.keys(basketEntries).length > 0 && (
              <button
                className="basket-pour-btn"
                onClick={handlePourToTray}
                disabled={pourToTray.status === "busy"}
                title="Verser la corbeille actuelle dans la bannette d'interaction (nouvelle source, données non filtrées pour l'instant)"
              >
                {pourToTray.status === "busy" ? "…" : "📥 Verser vers la bannette"}
              </button>
            )}
            {pourToTray.status === "ok" && <span className="basket-pour-ok">✓ versé</span>}
            {pourToTray.status === "error" && <span className="basket-pour-error">✗ {pourToTray.error}</span>}
          </div>
          <SelectionBasket
            basketEntries={basketEntries}
            sourceData={basketSourceData}
            onToggleNode={handleToggleBasketNode}
            onRemove={handleRemoveFromBasket}
          />
          <div className="radial-tree-container">
            <div className="radial-tree-container-header">
              <span className="synthesis-section-title" style={{ margin: 0 }}>
                Arbre radial
              </span>
              {!radialTreeExpanded && Object.keys(basketEntries).length > 0 && (
                <button className="radial-tree-expand-btn" onClick={() => setRadialTreeExpanded(true)}>
                  ⤢ Agrandir sur la carte
                </button>
              )}
            </div>
            {radialTreeExpanded ? (
              <p className="synthesis-empty">
                Agrandi sur la carte —{" "}
                <button className="radial-tree-expand-btn" onClick={() => setRadialTreeExpanded(false)}>
                  réduire
                </button>{" "}
                pour l'afficher ici.
              </p>
            ) : (
              <RadialTree
                basketEntries={basketEntries}
                sourceData={basketSourceData}
                onToggleSelection={handleSmartToggle}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
