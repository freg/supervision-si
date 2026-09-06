import React, { useState, useEffect } from "react";
import { fetchOwnCloudRoots, fetchOwnCloudChildren, fetchOwnCloudLongPaths } from "./ownCloudClient.js";

// Navigateur d'arbre OwnCloud (livraison #354, backlog items 6/9) --
// LECTURE SEULE par construction (owncloud-api ne propose aucune
// route d'écriture, voir owncloud/api/app.py) -- fil d'ariane +
// liste du dossier courant, plutôt qu'un arbre imbriqué complet :
// l'API ne fournit QUE les enfants DIRECTS d'un nœud (jamais toute
// la sous-arborescence, voir owncloud/api/README.md -- oc_filecache
// compte ~2,5M lignes), un dépliage progressif façon explorateur de
// fichiers colle exactement à ce contrat plutôt que de forcer un
// chargement récursif que l'API ne permettrait pas de toute façon.

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

export default function OwnCloudTreeView({ apiBase, frontendUrl }) {
  const [roots, setRoots] = useState([]);
  const [loadingRoots, setLoadingRoots] = useState(false);
  const [error, setError] = useState(null);
  // Pile du fil d'ariane -- chaque entrée {storage, fileid, name}.
  // Le PREMIER élément est toujours la racine choisie ; les suivants,
  // les dossiers descendus successivement.
  const [pathStack, setPathStack] = useState([]);
  const [currentChildren, setCurrentChildren] = useState([]);
  const [loadingChildren, setLoadingChildren] = useState(false);
  // Chemins trop longs (livraison #354) -- jamais chargé
  // automatiquement (requête coûteuse côté serveur), déclenché
  // explicitement par la personne via le bouton ci-dessous.
  const [longPathThreshold, setLongPathThreshold] = useState(260);
  const [longPathResults, setLongPathResults] = useState(null);
  const [loadingLongPaths, setLoadingLongPaths] = useState(false);
  const [longPathError, setLongPathError] = useState(null);

  useEffect(() => {
    setLoadingRoots(true);
    fetchOwnCloudRoots(apiBase).then((r) => {
      setRoots(r);
      setLoadingRoots(false);
    });
  }, [apiBase]);

  async function openRoot(root) {
    if (root.rootFileId == null) {
      setError(`Racine "${root.name}" sans nœud accessible.`);
      return;
    }
    setError(null);
    setPathStack([{ storage: root.id, fileid: root.rootFileId, name: root.name }]);
    await loadChildren(root.id, root.rootFileId);
  }

  async function openChild(child) {
    if (child.type !== "folder") return;
    setError(null);
    setPathStack((prev) => [...prev, { storage: child.raw.storage, fileid: child.id, name: child.name || "(sans nom)" }]);
    await loadChildren(child.raw.storage, child.id);
  }

  async function openBreadcrumb(index) {
    const entry = pathStack[index];
    setError(null);
    setPathStack((prev) => prev.slice(0, index + 1));
    await loadChildren(entry.storage, entry.fileid);
  }

  async function loadChildren(storage, fileid) {
    setLoadingChildren(true);
    const result = await fetchOwnCloudChildren(apiBase, storage, fileid);
    setLoadingChildren(false);
    if (result.error) {
      setError(result.error);
      setCurrentChildren([]);
      return;
    }
    const children = Array.isArray(result.children) ? result.children : [];
    // Dossiers d'abord, puis fichiers -- tri alphabétique dans
    // chaque groupe, convention déjà établie ailleurs dans ce hub.
    children.sort((a, b) => {
      if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
      return (a.name || "").localeCompare(b.name || "");
    });
    setCurrentChildren(children);
  }

  function backToRoots() {
    setPathStack([]);
    setCurrentChildren([]);
    setError(null);
  }

  async function scanLongPaths() {
    setLoadingLongPaths(true);
    setLongPathError(null);
    const result = await fetchOwnCloudLongPaths(apiBase, longPathThreshold, 200);
    setLoadingLongPaths(false);
    if (result.error) {
      setLongPathError(result.error);
      setLongPathResults(null);
      return;
    }
    setLongPathResults(result);
  }

  // Croisement storage -> nom de racine humain, à partir des racines
  // déjà chargées ci-dessus -- jamais une seconde résolution côté
  // serveur pour la même information (voir owncloud/api/app.py,
  // route /long-paths -- ne renvoie que l'id technique du storage).
  const rootNameByStorage = {};
  roots.forEach((r) => { rootNameByStorage[r.id] = r.name; });

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Navigation en lecture seule dans l'arborescence OwnCloud -- métadonnées uniquement
        (nom, taille, date), aucun contenu de fichier ni action de modification possible ici.
        {frontendUrl && (
          <> Pour une exploration plus riche (arbre radial, chronologie des versions),
          voir <a href={frontendUrl} target="_blank" rel="noreferrer">Supervision SI</a>.</>
        )}
      </p>
      {error && <p className="hub-error">{error}</p>}

      {pathStack.length === 0 ? (
        <div className="hub-card hub-settings-section">
          <h2>Racines ({roots.length})</h2>
          {loadingRoots && <p className="muted">Chargement…</p>}
          {!loadingRoots && roots.length === 0 && <p className="muted">Aucune racine accessible.</p>}
          <ul>
            {roots.map((root) => (
              <li key={root.id} style={{ marginBottom: 6 }}>
                <button className="secondary" onClick={() => openRoot(root)}>
                  📁 {root.name}
                </button>{" "}
                <span className="muted">
                  {root.itemCount != null ? `${root.itemCount} élément(s)` : ""}
                  {root.totalSize != null ? ` — ${formatSize(root.totalSize)}` : ""}
                  {root.description ? ` — ${root.description}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="hub-card hub-settings-section">
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
            <button className="secondary" onClick={backToRoots}>◀ Racines</button>
            {pathStack.map((entry, i) => (
              <span key={i}>
                {" / "}
                <button className="secondary" onClick={() => openBreadcrumb(i)}>
                  {entry.name}
                </button>
              </span>
            ))}
          </div>
          {loadingChildren && <p className="muted">Chargement…</p>}
          {!loadingChildren && currentChildren.length === 0 && <p className="muted">Dossier vide.</p>}
          <table className="hub-table">
            <thead>
              <tr>
                <th>Nom</th>
                <th>Taille</th>
                <th>Modifié</th>
              </tr>
            </thead>
            <tbody>
              {currentChildren.map((child) => (
                <tr key={child.id}>
                  <td>
                    {child.type === "folder" ? (
                      <button className="secondary" onClick={() => openChild(child)}>
                        📁 {child.name || "(sans nom)"}
                      </button>
                    ) : (
                      <span>📄 {child.name || "(sans nom)"}</span>
                    )}
                  </td>
                  <td>{child.type === "file" ? formatSize(child.raw?.size) : ""}</td>
                  <td>{formatMtime(child.raw?.mtime)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <h2>Chemins trop longs (Windows et autres)</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Un chemin complet trop long échoue silencieusement à la synchronisation sur
          certains systèmes (limite classique Windows : 260 caractères). Recherche
          déclenchée manuellement -- balaie l'intégralité de la base OwnCloud, jamais
          lancée automatiquement.
        </p>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 8 }}>
          <div className="hub-settings-row">
            <label>Seuil (caractères)</label>
            <input
              type="number"
              value={longPathThreshold}
              onChange={(e) => setLongPathThreshold(Number(e.target.value) || 260)}
              style={{ width: 100 }}
            />
          </div>
          <button onClick={scanLongPaths} disabled={loadingLongPaths}>
            {loadingLongPaths ? "Recherche…" : "Rechercher"}
          </button>
        </div>
        {longPathError && <p className="hub-error">{longPathError}</p>}
        {longPathResults && (
          <>
            <p className="muted">
              {longPathResults.results.length} chemin(s) dépassant {longPathResults.threshold} caractères
              (200 max affichés).
            </p>
            {longPathResults.results.length > 0 && (
              <table className="hub-table">
                <thead>
                  <tr>
                    <th>Racine</th>
                    <th>Chemin</th>
                    <th>Longueur</th>
                  </tr>
                </thead>
                <tbody>
                  {longPathResults.results.map((r) => (
                    <tr key={r.fileid}>
                      <td>{rootNameByStorage[r.storage] || `storage #${r.storage}`}</td>
                      <td style={{ wordBreak: "break-all", fontFamily: "monospace", fontSize: "0.9em" }}>{r.path}</td>
                      <td>{r.pathLength}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  );
}
