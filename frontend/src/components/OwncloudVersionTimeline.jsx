import { fmtBytes, fmtTimelineDate } from "../apps/owncloudLib.js";

/**
 * `entries` : sortie de buildVersionTimeline(nodesById) — voir
 * owncloudLib.js pour la convention de nommage exploitée
 * (files_versions/<chemin>.v<timestamp>) et ses limites (repose sur
 * les nœuds déjà chargés côté client, jamais un appel serveur dédié).
 */
export default function OwncloudVersionTimeline({ entries, onSelectVersion, selectedId }) {
  if (!entries || entries.length === 0) {
    return (
      <p className="owncloud-empty">
        Aucune version détectée parmi les nœuds déjà chargés — dépliez le dossier{" "}
        <code>files_versions</code> (et son contenu) dans l'arbre pour les voir apparaître ici.
      </p>
    );
  }

  const allTimestamps = entries.flatMap((e) => e.versions.map((v) => v.timestamp));
  const min = Math.min(...allTimestamps);
  const max = Math.max(...allTimestamps);
  const span = Math.max(max - min, 1); // évite une division par zéro si une seule date partout

  function positionPercent(ts) {
    return ((ts - min) / span) * 100;
  }

  return (
    <div className="owncloud-version-timeline">
      <p className="owncloud-hint">
        {entries.length} fichier{entries.length > 1 ? "s" : ""} avec historique détecté — axe commun
        du {fmtTimelineDate(min)} au {fmtTimelineDate(max)}.
      </p>
      <div className="owncloud-version-list">
        {entries.map((entry) => (
          <div key={entry.relativePath} className="owncloud-version-row">
            <div className="owncloud-version-row-label" title={entry.relativePath}>
              {entry.relativePath.split("/").pop()}
            </div>
            <div className="owncloud-version-row-track">
              {entry.versions.map((v) => (
                <button
                  key={v.id}
                  className={`owncloud-version-dot${v.id === selectedId ? " selected" : ""}`}
                  style={{ left: `${positionPercent(v.timestamp)}%` }}
                  title={`${fmtTimelineDate(v.timestamp)}${v.size != null ? " · " + fmtBytes(v.size) : ""}`}
                  onClick={() => onSelectVersion(v)}
                />
              ))}
            </div>
            <div className="owncloud-version-row-count">
              {entry.versions.length} version{entry.versions.length > 1 ? "s" : ""}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
