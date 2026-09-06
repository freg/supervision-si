import { useEffect, useMemo, useState } from "react";
import {
  loadAllDecryptedSecretLabels, decryptSecretValueOnly, fetchAllKeywords, fetchTemplates,
  fetchCollectionsForUser, createCollection, unlockCollectionKey, createSecret, createTemplate,
} from "./vaultOps.js";
import { serializeFields, orderFieldsRequiredFirst } from "./vaultFieldsLib.js";
import {
  buildLocationTree, collectLocationDescendants, filterSecretsByLocationNames,
  filterSecretsByQuery, sortSecrets, usedSecretsByFrequency, filterLocationTree,
  enrichLocationTreeWithUsage, filterTreeToUsedOnly, filterSecretsByTemplate, countSecretsByTemplate,
} from "./vaultSearchLib.js";
import LocationTreeNode from "./LocationTreeNode.jsx";
import FieldsEditor from "./FieldsEditor.jsx";

// Lecture seule des géolocalisations (bâtiments/étages/pièces/points
// d'accès) depuis Supervision SI -- jamais rien de sensible ici, voir
// la décision de sécurité assumée dans vault/README.md (le lien
// secret↔localisation est en clair, jamais le libellé/la valeur).
const PIXEL_GRID_API_BASE_URL = import.meta.env.VITE_PIXEL_GRID_API_BASE_URL || "";

// Préférence personnelle sur les colonnes affichées dans le tableau
// d'usage -- demandé explicitement ("un paramétrage personnel...
// pour l'affichage des codes par fréquence"). Stockage LOCAL simple
// (même principe que createLocalThemeStore, shared/preferences.js) --
// une préférence purement cosmétique, jamais sensible ni utile d'un
// appareil à l'autre, ne justifie pas d'étendre prefs-api pour ça.
const USAGE_COLUMNS_STORAGE_KEY = "supervision-si:vault:usage-columns";
const OPTIONAL_USAGE_COLUMNS = ["collection", "localisation", "lastAccessed"];

function loadUsageColumnPrefs() {
  try {
    const raw = localStorage.getItem(USAGE_COLUMNS_STORAGE_KEY);
    if (!raw) return { collection: true, localisation: true, lastAccessed: true }; // tout visible par défaut
    const parsed = JSON.parse(raw);
    return {
      collection: parsed.collection !== false,
      localisation: parsed.localisation !== false,
      lastAccessed: parsed.lastAccessed !== false,
    };
  } catch {
    return { collection: true, localisation: true, lastAccessed: true };
  }
}

function saveUsageColumnPrefs(prefs) {
  try {
    localStorage.setItem(USAGE_COLUMNS_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // stockage indisponible (navigation privée, quota...) -- la
    // préférence reste appliquée pour cette session, juste pas
    // mémorisée pour la prochaine.
  }
}

export default function VaultSearchScreen({ login, privateKey, publicKeyBase64, isReadOnly, onOpenSecret, onCollectionsChanged }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [failedCollections, setFailedCollections] = useState([]);
  const [allSecrets, setAllSecrets] = useState([]);

  // Ajout de collection/secret DEPUIS cet écran -- backlog coffre-fort
  // #1, demandé explicitement (jusqu'ici possible uniquement depuis
  // l'écran Collections). Réutilise entièrement les mêmes fonctions
  // (createCollection, createSecret, unlockCollectionKey) et le même
  // composant de formulaire (FieldsEditor) que l'écran Collections --
  // aucune logique parallèle. Formulaires repliés par défaut, même
  // motif "+" que partout ailleurs dans le coffre-fort.
  const [showAddCollectionForm, setShowAddCollectionForm] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [creatingCollection, setCreatingCollection] = useState(false);
  const [addCollectionError, setAddCollectionError] = useState(null);

  const [showAddSecretForm, setShowAddSecretForm] = useState(false);
  // Toutes les collections accessibles, PAS seulement celles ayant
  // déjà un secret -- allSecrets (voir loadAllDecryptedSecretLabels)
  // ne liste que des secrets existants, une collection tout juste
  // créée et encore vide en serait absente. Rechargée à chaque
  // ouverture du formulaire pour rester à jour (ex. collection créée
  // juste au-dessus, dans le même écran).
  const [addTargetCollections, setAddTargetCollections] = useState([]);
  const [addTargetCollectionId, setAddTargetCollectionId] = useState("");
  const [addLabel, setAddLabel] = useState("");
  const [addFields, setAddFields] = useState([{ label: "", content: "" }]);
  const [addLocalisation, setAddLocalisation] = useState("");
  const [addKeyword, setAddKeyword] = useState("");
  const [addTemplateId, setAddTemplateId] = useState(null);
  // Modèles pertinents pour la collection CHOISIE dans le menu
  // déroulant ci-dessus -- backlog coffre-fort #2, DISTINCT de
  // allTemplates (onglet "📋 Modèles", volontairement global/toutes
  // collections confondues pour le parcours cross-collection). Ici au
  // contraire il faut rester scopé : un modèle d'une AUTRE collection
  // ne doit jamais apparaître comme applicable. Rechargé à chaque
  // changement de collection choisie (voir effet plus bas).
  const [addFormTemplates, setAddFormTemplates] = useState([]);
  const [addRequiredLabels, setAddRequiredLabels] = useState([]);
  const [addSecretBusy, setAddSecretBusy] = useState(false);
  const [addSecretError, setAddSecretError] = useState(null);

  const [geolocations, setGeolocations] = useState([]);
  const [geoError, setGeoError] = useState(null);
  // "map" volontairement pas encore construit -- voir le bouton
  // désactivé ci-dessous, dit clairement plutôt que caché.
  const [locationLayout, setLocationLayout] = useState("tree"); // "tree" | "map" | "keywords" | "templates"
  const [locationQuery, setLocationQuery] = useState("");
  const [selectedLocation, setSelectedLocation] = useState(null);

  const [allKeywords, setAllKeywords] = useState([]);
  const [keywordQuery, setKeywordQuery] = useState("");

  const [allTemplates, setAllTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);

  const [labelQuery, setLabelQuery] = useState("");
  const [sortMode, setSortMode] = useState("alpha"); // "alpha" (défaut demandé) | "most-used" | "recent"

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadAllDecryptedSecretLabels(login, privateKey).then((res) => {
      if (cancelled) return;
      setLoading(false);
      if (res.ok) {
        setAllSecrets(res.secrets);
        setFailedCollections(res.failedCollections);
      } else {
        setError(res.error);
      }
    });
    return () => { cancelled = true; };
  }, [login, privateKey]);

  /** Recharge la liste après un ajout réussi (collection ou secret) --
   * même appel que l'effet de montage ci-dessus, sans repasser par
   * l'état "loading" plein écran (juste un rafraîchissement discret
   * en arrière-plan). En cas d'échec ici (rare, juste après un ajout
   * qui a lui-même réussi), la liste précédente reste affichée plutôt
   * que de faire disparaître ce qui vient d'être créé derrière une
   * erreur bloquante. */
  async function reloadSecretsAfterChange() {
    const res = await loadAllDecryptedSecretLabels(login, privateKey);
    if (res.ok) {
      setAllSecrets(res.secrets);
      setFailedCollections(res.failedCollections);
    }
  }

  async function toggleAddCollectionForm() {
    setAddCollectionError(null);
    setShowAddCollectionForm((v) => !v);
  }

  async function handleCreateCollectionFromSearch() {
    if (!newCollectionName.trim()) return;
    setCreatingCollection(true);
    setAddCollectionError(null);
    const res = await createCollection(newCollectionName.trim(), login, publicKeyBase64);
    setCreatingCollection(false);
    if (res.ok) {
      setNewCollectionName("");
      setShowAddCollectionForm(false);
      // Une collection neuve est toujours vide -- n'apparaît dans
      // aucune recherche tant qu'aucun secret n'y est ajouté, donc pas
      // besoin de reloadSecretsAfterChange ici. En revanche l'onglet
      // Collections (état séparé, VaultView) doit la voir apparaître
      // sans avoir à changer d'onglet puis revenir.
      onCollectionsChanged?.();
    } else {
      setAddCollectionError(res.error);
    }
  }

  async function toggleAddSecretForm() {
    setAddSecretError(null);
    if (!showAddSecretForm) {
      const cols = await fetchCollectionsForUser(login);
      setAddTargetCollections(cols);
      // Conserve la sélection déjà faite si elle reste valide,
      // sinon retombe sur la première collection disponible.
      setAddTargetCollectionId((prev) =>
        cols.some((c) => String(c.id) === String(prev)) ? prev : (cols[0] ? String(cols[0].id) : "")
      );
    }
    setShowAddSecretForm((v) => !v);
  }

  // Recharge les modèles pertinents (globaux + ceux de LA collection
  // choisie) à chaque changement de sélection dans le formulaire --
  // jamais les modèles d'une autre collection (voir vault-api,
  // GET /templates?collection_id=). Ignoré tant que le formulaire est
  // fermé ou qu'aucune collection n'est encore choisie.
  useEffect(() => {
    if (!showAddSecretForm || !addTargetCollectionId) {
      setAddFormTemplates([]);
      return;
    }
    let cancelled = false;
    fetchTemplates(addTargetCollectionId).then((ts) => { if (!cancelled) setAddFormTemplates(ts); });
    return () => { cancelled = true; };
  }, [showAddSecretForm, addTargetCollectionId]);

  function applyTemplateToAddFields(templateId) {
    const t = addFormTemplates.find((tpl) => tpl.id === templateId);
    if (!t) return;
    const required = t.required_labels || [];
    setAddFields(orderFieldsRequiredFirst(t.field_labels.map((label) => ({ label, content: "" })), required));
    setAddTemplateId(templateId);
    setAddRequiredLabels(required);
  }

  async function handleSaveAsTemplateFromSearch(name, fields, { requiredLabels, scope } = {}) {
    const fieldLabels = fields.map((f) => f.label.trim()).filter(Boolean);
    if (fieldLabels.length === 0 || !addTargetCollectionId) return;
    const res = await createTemplate(name, fieldLabels, login, {
      collectionId: scope === "collection" ? addTargetCollectionId : undefined,
      requiredLabels,
    });
    if (res.ok) setAddFormTemplates(await fetchTemplates(addTargetCollectionId));
  }

  async function handleAddSecretFromSearch() {
    const hasContent = addFields.some((f) => f.content.trim());
    if (!addLabel.trim() || !hasContent || !addTargetCollectionId) return;
    const collection = addTargetCollections.find((c) => String(c.id) === String(addTargetCollectionId));
    if (!collection) {
      setAddSecretError("Collection introuvable -- rouvrez le formulaire.");
      return;
    }
    setAddSecretBusy(true);
    setAddSecretError(null);
    try {
      const collectionKey = await unlockCollectionKey(collection.wrapped_key, privateKey);
      const value = serializeFields(addFields);
      const res = await createSecret(collection.id, addLabel.trim(), value, collectionKey, login, {
        localisation: addLocalisation.trim() || undefined,
        keyword: addKeyword.trim() || undefined,
        templateId: addTemplateId || undefined,
        reason: "création initiale",
      });
      if (res.ok) {
        setAddLabel("");
        setAddFields([{ label: "", content: "" }]);
        setAddLocalisation("");
        setAddKeyword("");
        setAddTemplateId(null);
        setAddRequiredLabels([]);
        setShowAddSecretForm(false);
        reloadSecretsAfterChange();
      } else {
        setAddSecretError(res.error);
      }
    } catch {
      setAddSecretError("Déchiffrement de la collection impossible.");
    }
    setAddSecretBusy(false);
  }

  useEffect(() => {
    if (!PIXEL_GRID_API_BASE_URL) {
      setGeoError("VITE_PIXEL_GRID_API_BASE_URL non configurée -- navigation par arbre indisponible, la recherche par libellé fonctionne quand même.");
      return;
    }
    fetch(`${PIXEL_GRID_API_BASE_URL}/geolocations`)
      .then((r) => r.json())
      .then((body) => setGeolocations(body.geolocations || []))
      .catch(() => setGeoError("Géolocalisations injoignables -- la recherche par libellé fonctionne quand même."));
  }, []);

  // Mots-clés : chargés indépendamment du reste (À TRAVERS toutes les
  // collections, peu importe l'accès -- voir vault-api, GET /keywords)
  // -- but même urgence : savoir où chercher avant même d'avoir accès.
  useEffect(() => {
    fetchAllKeywords().then(setAllKeywords);
  }, []);

  // Mots-clés : chargés indépendamment du reste (À TRAVERS toutes les
  // collections, peu importe l'accès -- voir vault-api, GET /keywords)
  // -- but même urgence : savoir où chercher avant même d'avoir accès.
  useEffect(() => {
    fetchAllKeywords().then(setAllKeywords);
  }, []);

  // Modèles -- globaux comme les mots-clés, mais le COMPTAGE par
  // modèle (voir templateCounts plus bas) ne porte que sur ce qui est
  // déjà accessible/chargé, contrairement aux mots-clés -- choix de
  // portée assumé (voir vault/README.md) : parcourir "par modèle" est
  // un outil d'organisation, pas le même besoin d'urgence cross-accès
  // qui a motivé les mots-clés.
  useEffect(() => {
    fetchTemplates().then(setAllTemplates);
  }, []);

  const templateCounts = useMemo(
    () => countSecretsByTemplate(allSecrets, allTemplates),
    [allSecrets, allTemplates]
  );

  const filteredKeywords = useMemo(() => {
    const q = keywordQuery.trim().toLowerCase();
    if (!q) return allKeywords;
    return allKeywords.filter((k) => k.keyword.toLowerCase().includes(q));
  }, [allKeywords, keywordQuery]);

  const locationTree = useMemo(() => buildLocationTree(geolocations), [geolocations]);
  // Enrichi AVANT le filtre texte -- l'ordre de priorité (codes en
  // tête) doit être posé une fois pour toutes, le filtre ne fait
  // ensuite qu'élaguer sans jamais retrier (voir filterLocationTree).
  const enrichedLocationTree = useMemo(
    () => enrichLocationTreeWithUsage(locationTree, allSecrets),
    [locationTree, allSecrets]
  );
  // Masqué par défaut -- demandé explicitement : la hiérarchie
  // complète des géolocalisations est souvent bien plus vaste que ce
  // qui a réellement des codes, noyait l'essentiel. Bouton pour tout
  // montrer, jamais perdu -- juste pas la vue de départ.
  const [showAllLocations, setShowAllLocations] = useState(false);
  const usageFilteredLocationTree = useMemo(
    () => (showAllLocations ? enrichedLocationTree : filterTreeToUsedOnly(enrichedLocationTree)),
    [enrichedLocationTree, showAllLocations]
  );
  const filteredLocationTree = useMemo(
    () => filterLocationTree(usageFilteredLocationTree, locationQuery),
    [usageFilteredLocationTree, locationQuery]
  );

  const locationFilteredSecrets = useMemo(() => {
    if (!selectedLocation) return allSecrets;
    // enrichedLocationTree, PAS locationTree brut -- ce dernier ne
    // connaît pas les localisations "non répertoriées" (saisies dans
    // un code mais absentes des géolocalisations), qui n'existent que
    // dans la version enrichie. Sans ça, sélectionner l'une d'elles
    // ne retrouverait jamais aucun code.
    const names = collectLocationDescendants(enrichedLocationTree, selectedLocation);
    return filterSecretsByLocationNames(allSecrets, names);
  }, [allSecrets, selectedLocation, enrichedLocationTree]);

  const displayedSecrets = useMemo(() => {
    // Composition des filtres : localisation ET modèle peuvent
    // s'appliquer simultanément (ex. "cartes SIM du Bâtiment A").
    const byTemplate = filterSecretsByTemplate(locationFilteredSecrets, selectedTemplateId);
    const byQuery = filterSecretsByQuery(byTemplate, labelQuery);
    return sortSecrets(byQuery, sortMode);
  }, [locationFilteredSecrets, selectedTemplateId, labelQuery, sortMode]);

  const usageSorted = useMemo(() => usedSecretsByFrequency(allSecrets), [allSecrets]);
  const [usageColumns, setUsageColumns] = useState(loadUsageColumnPrefs);
  const toggleUsageColumn = (col) => {
    setUsageColumns((prev) => {
      const next = { ...prev, [col]: !prev[col] };
      saveUsageColumnPrefs(next);
      return next;
    });
  };

  if (loading) return <p className="vault-muted">Chargement de tous vos codes…</p>;
  if (error) return <p className="vault-error">{error}</p>;

  return (
    <div className="vault-search-screen">
      {failedCollections.length > 0 && (
        <p className="vault-warning">
          ⚠️ {failedCollections.length} collection{failedCollections.length > 1 ? "s n'ont" : " n'a"} pas pu
          être déchiffrée{failedCollections.length > 1 ? "s" : ""} et {failedCollections.length > 1 ? "sont absentes" : "est absente"} de
          cette recherche : {failedCollections.join(", ")}.
        </p>
      )}
      <div className="vault-search-columns">
        <aside className="vault-search-col vault-search-col-left">
          <div className="vault-location-tabs">
            <button
              type="button"
              className={locationLayout === "tree" ? "active" : ""}
              onClick={() => setLocationLayout("tree")}
            >
              🌳 Arbre
            </button>
            <button type="button" disabled title="Pas encore construit — la vue arbre couvre l'usage courant pour l'instant">
              🗺️ Carte (bientôt)
            </button>
            <button
              type="button"
              className={locationLayout === "keywords" ? "active" : ""}
              onClick={() => setLocationLayout("keywords")}
              title="Retrouver un code en urgence par mot-clé, même sans y avoir accès — sait juste où chercher"
            >
              🏷️ Mots-clés
            </button>
            <button
              type="button"
              className={locationLayout === "templates" ? "active" : ""}
              onClick={() => setLocationLayout("templates")}
              title="Parcourir par modèle de fiche (ex. Carte SIM), parmi ce que vous avez déjà chargé"
            >
              📋 Modèles
            </button>
          </div>

          {locationLayout === "keywords" && (
            <>
              <input
                className="vault-location-search"
                placeholder="🔍 Filtrer les mots-clés…"
                value={keywordQuery}
                onChange={(e) => setKeywordQuery(e.target.value)}
              />
              <p className="vault-muted vault-search-geo-note">
                Vue d'urgence — montre où chercher, même dans des collections auxquelles vous n'avez pas encore accès.
              </p>
              <ul className="vault-keyword-list">
                {filteredKeywords.length === 0 && <p className="vault-muted">Aucun mot-clé.</p>}
                {filteredKeywords.map((k, i) => (
                  <li key={i} className="vault-keyword-item">
                    <span className="vault-keyword-text">🏷️ {k.keyword}</span>
                    <span className="vault-keyword-collection">📁 {k.collection_name}</span>
                    {k.localisation && <span className="vault-secret-loc">📍 {k.localisation}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}

          {locationLayout === "templates" && (
            <>
              {selectedTemplateId && (
                <button type="button" className="vault-link-btn" onClick={() => setSelectedTemplateId(null)}>
                  ↺ Tous les modèles
                </button>
              )}
              <ul className="vault-template-list">
                {templateCounts.length === 0 && <p className="vault-muted">Aucun modèle pour l'instant.</p>}
                {templateCounts.map((t) => (
                  <li
                    key={t.id}
                    className={`vault-template-item${selectedTemplateId === t.id ? " vault-template-selected" : ""}${t.count > 0 ? " vault-template-has-codes" : ""}`}
                    onClick={() => setSelectedTemplateId(selectedTemplateId === t.id ? null : t.id)}
                  >
                    <span className="vault-template-name">📋 {t.name}</span>
                    <span className="vault-template-fields">{t.field_labels.join(", ")}</span>
                    {t.count > 0 && <span className="vault-location-count">{t.count}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}

          {(locationLayout === "tree" || locationLayout === "map") && (
            <>
              <input
                className="vault-location-search"
                placeholder="🔍 Filtrer les localisations…"
                value={locationQuery}
                onChange={(e) => setLocationQuery(e.target.value)}
              />
              {geoError && <p className="vault-muted vault-search-geo-note">{geoError}</p>}
              <label className="vault-location-show-all">
                <input
                  type="checkbox"
                  checked={showAllLocations}
                  onChange={(e) => setShowAllLocations(e.target.checked)}
                />
                Montrer aussi les localisations sans code
              </label>
              {selectedLocation && (
                <button type="button" className="vault-link-btn" onClick={() => setSelectedLocation(null)}>
                  ↺ Toutes les localisations
                </button>
              )}
              <div className="vault-location-tree">
                {filteredLocationTree.length === 0 && !geoError && (
                  <p className="vault-muted">Aucune localisation.</p>
                )}
                {filteredLocationTree.map((node) => (
                  <LocationTreeNode key={node.localisation} node={node} selected={selectedLocation} onSelect={setSelectedLocation} />
                ))}
              </div>
            </>
          )}
        </aside>

        <section className="vault-search-col vault-search-col-center">
          <div className="vault-search-center-toolbar">
            <input
              className="vault-search-label-input"
              placeholder="🔍 Filtrer par libellé…"
              value={labelQuery}
              onChange={(e) => setLabelQuery(e.target.value)}
            />
            <select value={sortMode} onChange={(e) => setSortMode(e.target.value)} className="vault-search-sort-select">
              <option value="alpha">Alphabétique</option>
              <option value="most-used">Les plus utilisés</option>
              <option value="recent">Récemment consultés</option>
            </select>
          </div>
          <div className="vault-panel-header-row">
            <p className="vault-muted">{displayedSecrets.length} code{displayedSecrets.length > 1 ? "s" : ""}</p>
            {!isReadOnly && (
              <div className="vault-search-add-buttons">
                <button
                  type="button"
                  className="secondary vault-add-btn"
                  onClick={toggleAddCollectionForm}
                  title={showAddCollectionForm ? "Annuler" : "Nouvelle collection"}
                >
                  {showAddCollectionForm ? "✕" : "📁+"}
                </button>
                <button
                  type="button"
                  className="secondary vault-add-btn"
                  onClick={toggleAddSecretForm}
                  title={showAddSecretForm ? "Annuler" : "Nouveau secret"}
                >
                  {showAddSecretForm ? "✕" : "🔑+"}
                </button>
              </div>
            )}
          </div>

          {showAddCollectionForm && !isReadOnly && (
            <div className="vault-add-secret-form">
              <div className="vault-form-row">
                <input
                  placeholder="nom (ex. Site A - contrôle accès)"
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreateCollectionFromSearch()}
                  autoFocus
                />
                <button
                  className="primary"
                  onClick={handleCreateCollectionFromSearch}
                  disabled={creatingCollection || !newCollectionName.trim()}
                >
                  {creatingCollection ? "Création…" : "➕ Créer"}
                </button>
              </div>
              {addCollectionError && <p className="vault-error">{addCollectionError}</p>}
            </div>
          )}

          {showAddSecretForm && !isReadOnly && (
            <div className="vault-add-secret-form">
              {addTargetCollections.length === 0 ? (
                <p className="vault-muted">Aucune collection accessible -- créez-en une d'abord (bouton 📁+ ci-dessus).</p>
              ) : (
                <>
                  <div className="vault-form-row">
                    <select
                      className="vault-search-sort-select"
                      value={addTargetCollectionId}
                      onChange={(e) => setAddTargetCollectionId(e.target.value)}
                    >
                      {addTargetCollections.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                    <input
                      placeholder="libellé (ex. Portail principal)"
                      value={addLabel}
                      onChange={(e) => setAddLabel(e.target.value)}
                      autoFocus
                    />
                  </div>
                  <FieldsEditor
                    fields={addFields}
                    onChange={setAddFields}
                    templates={addFormTemplates}
                    onUseTemplate={applyTemplateToAddFields}
                    onSaveAsTemplate={(name, opts) => handleSaveAsTemplateFromSearch(name, addFields, opts)}
                    requiredLabels={addRequiredLabels}
                    collectionName={addTargetCollections.find((c) => String(c.id) === String(addTargetCollectionId))?.name}
                  />
                  <div className="vault-form-row">
                    <input
                      placeholder="localisation (optionnel)"
                      value={addLocalisation}
                      onChange={(e) => setAddLocalisation(e.target.value)}
                    />
                    <input
                      placeholder="mot-clé (optionnel)"
                      value={addKeyword}
                      onChange={(e) => setAddKeyword(e.target.value)}
                    />
                  </div>
                  {addSecretError && <p className="vault-error">{addSecretError}</p>}
                  <button
                    className="primary"
                    onClick={handleAddSecretFromSearch}
                    disabled={addSecretBusy || !addLabel.trim() || !addTargetCollectionId}
                  >
                    {addSecretBusy ? "…" : "➕ Créer le secret"}
                  </button>
                </>
              )}
            </div>
          )}

          <ul className="vault-search-secret-list">
            {displayedSecrets.map((s) => (
              <li key={`${s.collectionId}-${s.id}`}>
                <button type="button" className="vault-search-secret-item" onClick={() => onOpenSecret(s)}>
                  <span className="vault-search-secret-label">{s.label}</span>
                  {s.localisation && <span className="vault-search-secret-loc">📍 {s.localisation}</span>}
                  <span className="vault-search-secret-collection">{s.collectionName}</span>
                </button>
              </li>
            ))}
            {displayedSecrets.length === 0 && <p className="vault-muted">Aucun code ne correspond.</p>}
          </ul>
        </section>

        <aside className="vault-search-col vault-search-col-right">
          <div className="vault-panel-header-row">
            <h3>📊 Utilisation des codes</h3>
          </div>
          <div className="vault-usage-columns-toggle">
            {OPTIONAL_USAGE_COLUMNS.map((col) => (
              <label key={col}>
                <input type="checkbox" checked={usageColumns[col]} onChange={() => toggleUsageColumn(col)} />
                {{ collection: "Collection", localisation: "Localisation", lastAccessed: "Dernier accès" }[col]}
              </label>
            ))}
          </div>
          {usageSorted.length === 0 && <p className="vault-muted">Aucun usage enregistré pour l'instant.</p>}
          {usageSorted.length > 0 && (
            <div className="vault-usage-table-scroll">
              <table className="vault-usage-table">
                <thead>
                  <tr>
                    <th>Libellé</th>
                    <th>Utilisations</th>
                    {usageColumns.collection && <th>Collection</th>}
                    {usageColumns.localisation && <th>Localisation</th>}
                    {usageColumns.lastAccessed && <th>Dernier accès</th>}
                  </tr>
                </thead>
                <tbody>
                  {usageSorted.map((s) => (
                    <tr key={`${s.collectionId}-${s.id}`} onClick={() => onOpenSecret(s)}>
                      <td>{s.label}</td>
                      <td className="vault-usage-count">{s.access_count}×</td>
                      {usageColumns.collection && <td>{s.collectionName}</td>}
                      {usageColumns.localisation && <td>{s.localisation || "—"}</td>}
                      {usageColumns.lastAccessed && (
                        <td className="vault-muted">
                          {s.last_accessed_at ? new Date(s.last_accessed_at).toLocaleString("fr-FR") : "—"}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

/** Révèle la valeur d'un secret sélectionné depuis cet écran --
 * réutilise la clé de collection déjà déverrouillée (voir
 * loadAllDecryptedSecretLabels), jamais besoin de rouvrir la
 * collection depuis zéro. Le libellé est déjà connu (secret.label),
 * seule la valeur reste à déchiffrer -- voir decryptSecretValueOnly,
 * bug réel corrigé : decryptSecret exigeait aussi les champs
 * encrypted_label_* pour le libellé, absents des objets transformés
 * par loadAllDecryptedSecretLabels ("Déchiffrement impossible"
 * systématique avant ce correctif). */
export async function revealSecretValue(secret) {
  const value = await decryptSecretValueOnly(secret, secret.collectionKey);
  return { label: secret.label, value };
}
