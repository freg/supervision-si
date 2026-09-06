import { useEffect, useRef, useState } from "react";
import { fetchSourceData } from "../api.js";
import useIpamStats from "../hooks/useIpamStats.js";
import { loadIpamAsSource } from "../apps/ipamSourceLoader.js";

function relativeTime(isoString) {
  if (!isoString) return "—";
  const deltaSeconds = Math.round((Date.now() - new Date(isoString).getTime()) / 1000);
  if (deltaSeconds < 5) return "à l'instant";
  if (deltaSeconds < 60) return `il y a ${deltaSeconds}s`;
  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (deltaMinutes < 60) return `il y a ${deltaMinutes}min`;
  const deltaHours = Math.round(deltaMinutes / 60);
  return `il y a ${deltaHours}h`;
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Case à cocher tri-état : reflète l'état réel dans la corbeille plutôt
 * que la seule sélection manuelle — cochée (source entièrement
 * sélectionnée), indéterminée (partiellement sélectionnée via l'arbre
 * JSON), ou vide (absente de la corbeille). L'attribut `indeterminate`
 * n'existe pas en JSX, d'où le ref + effet.
 */
function TriStateCheckbox({ checked, indeterminate, onChange, title }) {
  const ref = useRef(null);

  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return <input type="checkbox" ref={ref} checked={checked} onChange={onChange} title={title} />;
}

function InjectForm({ onInject, onCancel }) {
  const [sourceName, setSourceName] = useState("");
  const [fileContent, setFileContent] = useState(null);
  const [fileLabel, setFileLabel] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileLabel(file.name);
    if (!sourceName) {
      setSourceName(file.name.replace(/\.json$|\.geojson$/i, ""));
    }

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(reader.result);
        setFileContent(parsed);
        setError(null);
      } catch (err) {
        setFileContent(null);
        setError("Le fichier n'est pas un JSON valide.");
      }
    };
    reader.readAsText(file);
  }

  async function handleSubmit() {
    if (!sourceName.trim()) {
      setError("Le nom de la source est requis.");
      return;
    }
    if (!fileContent) {
      setError("Choisis d'abord un fichier JSON valide.");
      return;
    }

    setSubmitting(true);
    setError(null);
    const result = await onInject(sourceName.trim(), fileContent);
    setSubmitting(false);

    if (!result.ok) {
      setError(result.error || "Échec de l'injection.");
      return;
    }
    onCancel(); // ferme le formulaire après succès
  }

  return (
    <div className="inject-form">
      <div className="inject-form-title">Injecter un fichier JSON</div>

      <input
        type="text"
        className="calendar-keywords-input"
        placeholder="nom de la source (ex: mon_fichier)"
        value={sourceName}
        onChange={(e) => setSourceName(e.target.value)}
      />

      <label className="inject-file-label">
        {fileLabel || "Choisir un fichier .json / .geojson"}
        <input type="file" accept=".json,.geojson,application/json" onChange={handleFileChange} hidden />
      </label>

      {error && <div className="inject-form-error">{error}</div>}

      <div className="inject-form-actions">
        <button className="calendar-nav-btn" onClick={onCancel} disabled={submitting}>
          Annuler
        </button>
        <button className="calendar-nav-btn inject-submit-btn" onClick={handleSubmit} disabled={submitting}>
          {submitting ? "Envoi…" : "Injecter"}
        </button>
      </div>
    </div>
  );
}

/**
 * Carte d'une source "externe" — base en lecture seule d'un autre
 * onglet (IPAM pour l'instant), PAS un fichier JSON importé : symbole
 * dédié (📡 plutôt que le point de statut coloré des sources
 * fichiers), pas de case à cocher/téléchargement/suppression (rien de
 * tout ça n'a de sens ici, cette "source" n'est jamais entrée dans la
 * corbeille — c'est un renvoi vers son propre onglet, pas une donnée
 * à sélectionner dans le flux carte/corbeille/arbre radial).
 */
function ExternalSourceCard({ onNavigate, onSourceRegistered }) {
  const { stats, health, error } = useIpamStats(0); // 0 = un seul appel, pas de sondage continu ici
  const [loadStatus, setLoadStatus] = useState(null); // null | "loading" | {ok, rootCount?, error?}

  const unavailable = error || (health && health.status !== "ok");

  async function handleLoadAsSource(e) {
    e.stopPropagation(); // ne déclenche pas aussi la navigation de la carte
    setLoadStatus("loading");
    const result = await loadIpamAsSource();
    if (result.ok) {
      await onSourceRegistered?.(result.name);
      setLoadStatus({ ok: true, rootCount: result.rootCount });
    } else {
      setLoadStatus({ ok: false, error: result.error });
    }
    setTimeout(() => setLoadStatus(null), 5000);
  }

  return (
    <div className="source-card external-source-card" onClick={() => onNavigate?.("ipam")}>
      <div className="source-card-title-row">
        <span className="external-source-icon">📡</span>
        <span className="source-card-title">IPAM</span>
        <span className="external-source-badge">base externe</span>
      </div>
      <div className="source-card-meta">
        {unavailable && "injoignable"}
        {!unavailable && !stats && "chargement…"}
        {!unavailable && stats && `${stats.sectionCount} sections · ${stats.subnetCount} subnets`}
      </div>
      {!unavailable && (
        <div className="external-source-load-row">
          <button
            className="external-source-load-btn"
            onClick={handleLoadAsSource}
            disabled={loadStatus === "loading"}
            title="Récupère TOUTES les racines indépendantes d'IPAM et les enregistre comme une source JSON unique, sélectionnable comme n'importe quel fichier de la liste ci-dessous"
          >
            📥 {loadStatus === "loading" ? "Chargement…" : "Charger comme source"}
          </button>
          {loadStatus?.ok && (
            <span className="external-source-load-status ok">
              ✓ {loadStatus.rootCount} racine{loadStatus.rootCount > 1 ? "s" : ""} chargée{loadStatus.rootCount > 1 ? "s" : ""}
            </span>
          )}
          {loadStatus?.ok === false && (
            <span className="external-source-load-status error">⚠️ {loadStatus.error}</span>
          )}
        </div>
      )}
    </div>
  );
}

function DeletedSourcesPanel({ deletedSources, onRestoreSource }) {
  if (deletedSources.length === 0) {
    return <p className="synthesis-empty">Aucune source supprimée.</p>;
  }

  return (
    <div className="deleted-sources-list">
      {deletedSources.map((d) => (
        <div key={d.source} className="source-card">
          <div className="source-card-title-row">
            <span className="status-dot" style={{ background: "var(--color-text-muted)" }} />
            <span className="source-card-title">{d.source}</span>
          </div>
          <div className="source-card-meta">supprimée {relativeTime(d.deleted_at)}</div>
          <button
            className="source-card"
            style={{ marginTop: "0.5rem", padding: "0.3rem 0.5rem", fontSize: "0.75rem" }}
            onClick={() => onRestoreSource(d.source)}
          >
            ↩️ Restaurer
          </button>
        </div>
      ))}
    </div>
  );
}

export default function SourcesPanel({
  registeredSources,
  proposedSources,
  traySources,
  selectedSource,
  onSelectSource,
  onRegisterSource,
  basketEntries,
  manualSelection,
  onToggleSourceInBasket,
  onInject,
  onDeleteSource,
  deletedSources,
  showDeletedSources,
  onToggleDeletedPanel,
  onRestoreSource,
  onNavigate,
  onSourceRegistered,
  onPourSelectionToTray,
}) {
  const [showInjectForm, setShowInjectForm] = useState(false);

  async function handleDownloadOne(name) {
    const payload = await fetchSourceData(name);
    downloadJson(`${name}.json`, payload);
  }

  function handleDownloadAll() {
    const bundle = {};
    for (const { name, payload } of registeredSources) {
      if (payload) bundle[name] = payload;
    }
    downloadJson(`supervision-si-export-${Date.now()}.json`, bundle);
  }

  // Sélection groupée -- réutilise la case à cocher existante
  // (corbeille) plutôt que d'ajouter un DEUXIÈME mécanisme de
  // sélection qui ferait doublon et prêterait à confusion (cocher une
  // source l'ajoute déjà à la corbeille ; ça inclut naturellement
  // "je veux agir sur ces sources-là", pas besoin d'un choix séparé).
  // Restreint aux sources RÉELLEMENT enregistrées (basketEntries peut
  // contenir d'autres entrées, ex. bannette, où supprimer/télécharger
  // en masse n'a pas le même sens).
  const registeredNamesSet = new Set(registeredSources.map((s) => s.name));
  const selectedRegisteredNames = Object.keys(basketEntries).filter((n) => registeredNamesSet.has(n));

  const [bulkBusy, setBulkBusy] = useState(false);

  async function handleBulkDownload() {
    const bundle = {};
    for (const name of selectedRegisteredNames) {
      const payload = await fetchSourceData(name);
      if (payload) bundle[name] = payload;
    }
    downloadJson(`supervision-si-selection-${Date.now()}.json`, bundle);
  }

  async function handleBulkDelete() {
    if (!window.confirm(`Supprimer ${selectedRegisteredNames.length} source(s) sélectionnée(s) ? (récupérable)`)) return;
    // Strictement SÉQUENTIEL (pas un forEach non attendu) --
    // onDeleteSource refait un fetch complet de la liste à chaque
    // appel côté parent ; plusieurs suppressions concurrentes
    // déclencheraient des requêtes qui se chevauchent inutilement,
    // au mieux redondantes, au pire des mises à jour d'état dans un
    // ordre incohérent.
    setBulkBusy(true);
    for (const name of selectedRegisteredNames) {
      await onDeleteSource(name);
    }
    setBulkBusy(false);
  }

  function handleBulkPourToTray() {
    onPourSelectionToTray?.();
  }

  return (
    <div className="col-sources">
      <div className="sources-header-actions">
        <button className="inject-toggle-btn" onClick={() => setShowInjectForm((v) => !v)}>
          {showInjectForm ? "✕ Fermer" : "➕ Injecter"}
        </button>
        <button
          className="sources-header-btn"
          onClick={handleDownloadAll}
          disabled={registeredSources.length === 0}
          title="Télécharger toutes les sources actives (un seul fichier)"
        >
          ⬇️ Tout
        </button>
        <button className="sources-header-btn" onClick={onToggleDeletedPanel} title="Sources supprimées">
          🗑️ {showDeletedSources ? "▾" : "▸"}
        </button>
      </div>

      {showInjectForm && (
        <InjectForm onInject={onInject} onCancel={() => setShowInjectForm(false)} />
      )}

      {showDeletedSources && (
        <DeletedSourcesPanel deletedSources={deletedSources} onRestoreSource={onRestoreSource} />
      )}

      {manualSelection.size > 0 && (
        <div className="sources-manual-hint">
          {manualSelection.size} source(s) ajoutée(s) à la corbeille manuellement
        </div>
      )}

      <div className="synthesis-title">Sources externes</div>
      <ExternalSourceCard onNavigate={onNavigate} onSourceRegistered={onSourceRegistered} />

      <div className="synthesis-title" style={{ marginTop: "1rem" }}>
        Fichiers JSON
      </div>

      {selectedRegisteredNames.length > 0 && (
        <div className="sources-bulk-toolbar">
          <span className="sources-bulk-count">{selectedRegisteredNames.length} sélectionnée(s)</span>
          <button className="sources-bulk-btn" onClick={handleBulkDownload} disabled={bulkBusy} title="Télécharger les sources sélectionnées (un seul fichier)">
            ⬇️ Télécharger
          </button>
          <button className="sources-bulk-btn" onClick={handleBulkPourToTray} disabled={bulkBusy} title="Verser les sources sélectionnées dans la bannette d'interaction">
            📥 Vers la bannette
          </button>
          <button className="sources-bulk-btn sources-bulk-btn-danger" onClick={handleBulkDelete} disabled={bulkBusy} title="Supprimer les sources sélectionnées (récupérable)">
            {bulkBusy ? "…" : "🗑️ Supprimer"}
          </button>
        </div>
      )}

      {registeredSources.map(({ name, payload }) => {
        const isOk = payload?.status === "ok";
        const featureCount = isOk ? payload.data?.features?.length ?? 0 : 0;

        const basketEntry = basketEntries[name];
        const inBasket = Boolean(basketEntry);
        const fullySelected = inBasket && basketEntry.deselectedPaths.size === 0;
        const indeterminate = inBasket && !fullySelected;

        return (
          <div key={name} className={`source-card source-card-compact ${selectedSource === name ? "active" : ""}`}>
            {/* Ligne UNIQUE par défaut -- se déploie sur 3 lignes au
                survol (celle-ci + méta complète + actions), demandé
                explicitement après test réel : la liste multi-lignes
                systématique prenait trop de place pour naviguer
                rapidement parmi de nombreuses sources. */}
            <div className="source-card-row-main">
              <TriStateCheckbox
                checked={fullySelected}
                indeterminate={indeterminate}
                onChange={(e) => {
                  e.stopPropagation();
                  onToggleSourceInBasket(name);
                }}
                title={
                  inBasket
                    ? "Retirer entièrement de la corbeille"
                    : "Ajouter à la corbeille"
                }
              />
              <button className="source-card-clickzone" onClick={() => onSelectSource(name)}>
                <span className={`status-dot ${isOk ? "ok pulse" : "unavailable"}`} />
                <span className="source-card-title">{name}</span>
              </button>
              <span className="source-card-meta-inline">
                {isOk ? `${featureCount} él.` : "indisponible"}
              </span>
            </div>
            <div className="source-card-hover-reveal">
              <div className="source-card-meta">
                {isOk
                  ? `${featureCount} élément(s) · maj ${relativeTime(payload.updated_at)}`
                  : "aucune donnée disponible"}
              </div>
              {/* Actions sur leur propre ligne, JAMAIS partagée avec le
                  titre -- bug réel rencontré : un nom de source long
                  poussait ces boutons hors de la colonne, les rendant
                  inaccessibles (flex:1 sans min-width:0 sur la zone
                  cliquable = comportement par défaut de flexbox qui
                  refuse de la faire rétrécir sous son contenu). */}
              <div className="source-card-actions-row">
                <button
                  className="source-card-icon-btn"
                  onClick={() => handleDownloadOne(name)}
                  title="Télécharger cette source (JSON)"
                >
                  ⬇️ Télécharger
                </button>
                <button
                  className="source-card-icon-btn source-card-icon-btn-danger"
                  onClick={() => onDeleteSource(name)}
                  title="Supprimer (récupérable)"
                >
                  🗑️ Supprimer
                </button>
              </div>
            </div>
          </div>
        );
      })}

      {registeredSources.length === 0 && (
        <p className="synthesis-empty">Aucune source active pour le moment.</p>
      )}

      {proposedSources.length > 0 && (
        <>
          <div className="synthesis-title" style={{ marginTop: "1rem" }}>
            Propositions
          </div>
          {proposedSources.map((s) => (
            <div className="source-card" key={s.source}>
              <div className="source-card-title-row">
                <span className="status-dot" style={{ background: "var(--color-warn)" }} />
                <span className="source-card-title">{s.source}</span>
              </div>
              <div className="source-card-meta">
                {s.status === "new" ? "nouveau fichier détecté" : "modifié hors du chemin habituel"}
                {" · "}
                {relativeTime(s.updated_at)}
              </div>
              <button
                className="source-card"
                style={{ marginTop: "0.5rem", padding: "0.3rem 0.5rem", fontSize: "0.75rem" }}
                onClick={() => onRegisterSource(s.source)}
              >
                {s.status === "new" ? "Ajouter" : "Prendre en compte"}
              </button>
            </div>
          ))}
        </>
      )}

      {traySources && traySources.length > 0 && (
        <>
          <div className="synthesis-title" style={{ marginTop: "1rem" }}>
            📥 Bannette d'interaction
          </div>
          <p className="synthesis-empty" style={{ marginBottom: "0.5rem" }}>
            Versées depuis une sélection (corbeille, autres modules) —
            pas encore pérennes.
          </p>
          {traySources.map((s) => (
            <div className="source-card tray-source-card" key={s.source}>
              <div className="source-card-title-row">
                <span className="status-dot" style={{ background: "var(--color-select)" }} />
                <span className="source-card-title">{s.source}</span>
              </div>
              <div className="source-card-meta">
                versée {relativeTime(s.updated_at)}
              </div>
              <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.5rem" }}>
                <button
                  className="source-card"
                  style={{ padding: "0.3rem 0.5rem", fontSize: "0.75rem" }}
                  onClick={() => onRegisterSource(s.source)}
                >
                  Rendre pérenne
                </button>
                <button
                  className="source-card"
                  style={{ padding: "0.3rem 0.5rem", fontSize: "0.75rem" }}
                  onClick={() => onDeleteSource(s.source)}
                >
                  Écarter
                </button>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
