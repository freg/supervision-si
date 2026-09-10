import React, { useState, useEffect, useCallback } from "react";
import {
  fetchSources,
  browseSource,
  browseItem,
  fetchStats,
} from "./fileManagerClient.js";

// Tuile "Gestionnaire de fichiers" (livraison #396, backlog item 26).
// Trois volets :
//   1. Espace protégé du hub (répertoire hôte, navigation arborescente)
//   2. Documents GED (vue arborescente par dossier/entité liée)
//   3. Partages SSHFS (systèmes de fichiers montés via ssh-tunnels)
//
// Architecture : ce composant agrège les sources existantes (ged-api,
// ssh-tunnels-api) via file-manager-api. Il ne duplique aucune donnée.

function formatSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} Go`;
}

function formatMtime(unixSeconds) {
  if (!unixSeconds) return "";
  try {
    return new Date(unixSeconds * 1000).toLocaleString("fr-FR");
  } catch {
    return "";
  }
}

// Composant d'arbre de fichiers (réutilisable pour espace protégé et SSHFS)
function FileTree({ apiBase, sourceId, groups, onNavigate }) {
  const [node, setNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedPaths, setExpandedPaths] = useState(() => new Set());

  const loadNode = useCallback(async (path = "") => {
    setLoading(true);
    setError(null);
    try {
      const result = await browseSource(apiBase, sourceId, path, groups);
      if (result.status !== 200) {
        setError(result.data.error || "Erreur de chargement");
        setNode(null);
      } else {
        setNode(result.data.node || result.data);
      }
    } catch (exc) {
      setError(exc.message);
      setNode(null);
    }
    setLoading(false);
  }, [apiBase, sourceId, groups]);

  useEffect(() => {
    loadNode("");
  }, [loadNode]);

  function togglePath(path) {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  if (loading && !node) return <p className="muted">Chargement…</p>;
  if (error) return <p className="hub-error">{error}</p>;
  if (!node) return <p className="muted">Aucun contenu.</p>;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <strong>📁 {node.name || "(racine)"}</strong>
        {node.path && <span className="muted" style={{ marginLeft: 8, fontSize: "0.9em" }}>{node.path}</span>}
      </div>
      {node.children && node.children.length > 0 && (
        <table className="hub-table">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Taille</th>
              <th>Modifié</th>
            </tr>
          </thead>
          <tbody>
            {node.children.map((child) => {
              const isFolder = child.type === "folder";
              const isExpanded = expandedPaths.has(child.path);
              return (
                <React.Fragment key={child.path}>
                  <tr>
                    <td>
                      {isFolder ? (
                        <button
                          className="secondary"
                          style={{ marginRight: 4 }}
                          onClick={() => togglePath(child.path)}
                        >
                          {isExpanded ? "▾" : "▸"}
                        </button>
                      ) : (
                        <span style={{ marginLeft: 24 }} />
                      )}
                      {isFolder ? "📁" : "📄"} {child.name || "(sans nom)"}
                    </td>
                    <td>{!isFolder && child.size != null ? formatSize(child.size) : ""}</td>
                    <td>{formatMtime(child.mtime)}</td>
                  </tr>
                  {isFolder && isExpanded && (
                    <tr>
                      <td colSpan={3} style={{ paddingLeft: 32 }}>
                        <FileTree
                          apiBase={apiBase}
                          sourceId={sourceId}
                          groups={groups}
                          onNavigate={onNavigate}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      )}
      {node.truncated && (
        <p className="muted" style={{ marginTop: 8 }}>
          ⚠️ Liste tronquée ({node.totalChildren} éléments au total, {node.children?.length} affichés).
        </p>
      )}
    </div>
  );
}

// Composant de liste plate (GED, montages SSHFS)
function FlatList({ items, onItemClick, renderItem }) {
  if (!items || items.length === 0) {
    return <p className="muted">Aucun élément.</p>;
  }
  return (
    <table className="hub-table">
      <thead>
        <tr>
          <th>Nom</th>
          <th>Type</th>
          <th>Détails</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item, i) => (
          <tr key={item.id || i}>
            <td>
              {onItemClick ? (
                <button className="secondary" onClick={() => onItemClick(item)}>
                  {renderItem ? renderItem(item, true) : (item.name || `#${item.id}`)}
                </button>
              ) : (
                renderItem ? renderItem(item, false) : (item.name || `#${item.id}`)
              )}
            </td>
            <td>{item.type || "—"}</td>
            <td>
              {item.versionCount != null && `${item.versionCount} version(s)`}
              {item.status && ` — ${item.status}`}
              {item.remotePath && ` — ${item.remotePath}`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function FileManagerView({ onBack, fileManagerApiBase, login, groups }) {
  const [sources, setSources] = useState([]);
  const [activeSource, setActiveSource] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [browseResult, setBrowseResult] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchSources(fileManagerApiBase, groups)
      .then((result) => {
        if (result.status === 200) {
          setSources(result.data.sources || []);
        } else {
          setError(result.data.error || "Erreur de chargement des sources");
        }
      })
      .catch((exc) => setError(exc.message))
      .finally(() => setLoading(false));
  }, [fileManagerApiBase, groups]);

  async function selectSource(source) {
    setActiveSource(source);
    setError(null);
    setStats(null);

    try {
      const result = await browseSource(fileManagerApiBase, source.id, "", groups);
      if (result.status === 200) {
        setBrowseResult(result.data);
      } else {
        setError(result.data.error || "Erreur de parcours");
        setBrowseResult(null);
      }

      // Charger les stats en parallèle
      const statsResult = await fetchStats(fileManagerApiBase, source.id, groups);
      if (statsResult.status === 200) {
        setStats(statsResult.data);
      }
    } catch (exc) {
      setError(exc.message);
    }
  }

  function renderContent() {
    if (!activeSource) return null;

    if (activeSource.type === "protected-space") {
      return (
        <FileTree
          apiBase={fileManagerApiBase}
          sourceId={activeSource.id}
          groups={groups}
        />
      );
    }

    if (activeSource.type === "ged") {
      const items = browseResult?.items || [];
      return (
        <FlatList
          items={items}
          renderItem={(item) => (
            <span>
              📄 {item.name}
              {item.links?.length > 0 && (
                <span className="muted"> — {item.links.length} liaison(s)</span>
              )}
            </span>
          )}
        />
      );
    }

    if (activeSource.type === "ssh-mounts") {
      const items = browseResult?.items || [];
      return (
        <FlatList
          items={items}
          renderItem={(item) => (
            <span>
              {item.canBrowse ? "📁" : "🔒"} {item.name}
              {item.status === "mounted" && <span className="muted"> — monté</span>}
            </span>
          )}
          onItemClick={item.canBrowse ? () => handleBrowseMount(item) : null}
        />
      );
    }

    return <p className="muted">Source non supportée.</p>;
  }

  async function handleBrowseMount(mount) {
    try {
      const result = await browseItem(fileManagerApiBase, "ssh-mounts", mount.id, "", groups);
      if (result.status === 200) {
        // Le montage est accessible via ssh-tunnels-api directement
        setBrowseResult({
          type: "flat",
          items: [{
            id: mount.id,
            name: `${mount.name} (via ssh-tunnels)`,
            type: "mount-point",
            browseUrl: result.data.browseUrl,
          }],
        });
      } else {
        setError(result.data.error || "Erreur d'accès au montage");
      }
    } catch (exc) {
      setError(exc.message);
    }
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📂 Gestionnaire de fichiers</h1>
      </div>

      {error && <p className="hub-error">{error}</p>}

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <button
          className={!activeSource ? "" : "secondary"}
          onClick={() => setActiveSource(null)}
        >
          📋 Sources
        </button>
        {sources.map((s) => (
          <button
            key={s.id}
            className={activeSource?.id === s.id ? "" : "secondary"}
            onClick={() => selectSource(s)}
          >
            {s.type === "protected-space" && "🔒 "}
            {s.type === "ged" && "📁 "}
            {s.type === "ssh-mounts" && "🔗 "}
            {s.name}
          </button>
        ))}
      </div>

      {!activeSource ? (
        <div className="hub-card hub-settings-section">
          <h2>Sources disponibles</h2>
          {loading && <p className="muted">Chargement…</p>}
          {!loading && sources.length === 0 && <p className="muted">Aucune source disponible.</p>}
          <ul>
            {sources.map((s) => (
              <li key={s.id} style={{ marginBottom: 8 }}>
                <button className="secondary" onClick={() => selectSource(s)}>
                  {s.type === "protected-space" && "🔒 "}
                  {s.type === "ged" && "📁 "}
                  {s.type === "ssh-mounts" && "🔗 "}
                  <strong>{s.name}</strong>
                </button>
                <p className="muted" style={{ marginTop: 4, marginLeft: 8 }}>
                  {s.description}
                  {s.basePath && ` — ${s.basePath}`}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <>
          <div className="hub-card hub-settings-section">
            <h2>{activeSource.name}</h2>
            <p className="muted">{activeSource.description}</p>
            {renderContent()}
          </div>

          {stats && (
            <div className="hub-card hub-settings-section">
              <h3>Statistiques</h3>
              <pre style={{ fontSize: "0.9em", overflow: "auto" }}>
                {JSON.stringify(stats, null, 2)}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
