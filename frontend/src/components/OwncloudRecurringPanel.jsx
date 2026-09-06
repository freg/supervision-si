// Dictionnaire des dossiers récurrents -- TROIS catégories bien
// distinctes (retour réel après une première version qui les
// confondait) :
// 1. Structure ownCloud CONNUE (files, cache, thumbnails...) -- sue
//    d'avance, jamais "détectée", toujours affichée.
// 2. Dossiers utilisateur RÉCURRENTS -- découverts dynamiquement,
//    revus sur >= 2 racines différentes (voir owncloudLib.js,
//    splitOccurrencesByThreshold).
// 3. UNIQUES -- vus une seule fois, pas encore prouvés récurrents,
//    liste séparée plutôt que mélangés au-dessus.

function frequencyTier(count) {
  if (count >= 10) return "high";
  if (count >= 3) return "medium";
  return "low";
}

function ToggleItem({ name, count, hidden, onToggle, tier }) {
  return (
    <li className={`owncloud-recurring-item${tier ? ` owncloud-recurring-${tier}` : ""}${hidden ? " owncloud-recurring-hidden" : ""}`}>
      <label>
        <input type="checkbox" checked={hidden} onChange={() => onToggle(name)} />
        <span className="owncloud-recurring-name">{name}</span>
        {count != null && <span className="owncloud-recurring-count">{count}</span>}
      </label>
    </li>
  );
}

export default function OwncloudRecurringPanel({
  knownStructuralNames, recurring, unique, hiddenNames, onToggle, expanded, onToggleExpanded,
}) {
  const totalDetected = recurring.length + unique.length;

  return (
    <div className="owncloud-recurring-panel">
      <button type="button" className="owncloud-recurring-header" onClick={onToggleExpanded}>
        {expanded ? "▾" : "▸"} Dossiers récurrents
        {hiddenNames.size > 0 && ` (${hiddenNames.size} masqué${hiddenNames.size > 1 ? "s" : ""})`}
      </button>
      {expanded && (
        <div className="owncloud-recurring-body">
          <div className="owncloud-recurring-section">
            <div className="owncloud-recurring-section-title">Structure ownCloud connue</div>
            <ul className="owncloud-recurring-list">
              {knownStructuralNames.map((name) => (
                <ToggleItem key={name} name={name} count={null} hidden={hiddenNames.has(name)} onToggle={onToggle} />
              ))}
            </ul>
          </div>

          <div className="owncloud-recurring-section">
            <div className="owncloud-recurring-section-title">
              Dossiers utilisateur récurrents {recurring.length > 0 && `(${recurring.length})`}
            </div>
            {recurring.length === 0 ? (
              <p className="owncloud-recurring-empty">Aucun pour l'instant — apparaît quand un même nom revient sur au moins 2 racines différentes.</p>
            ) : (
              <ul className="owncloud-recurring-list">
                {recurring.map(([name, count]) => (
                  <ToggleItem key={name} name={name} count={count} hidden={hiddenNames.has(name)} onToggle={onToggle} tier={frequencyTier(count)} />
                ))}
              </ul>
            )}
          </div>

          <div className="owncloud-recurring-section">
            <div className="owncloud-recurring-section-title owncloud-recurring-section-title-muted">
              Uniques (vus une seule fois) {unique.length > 0 && `(${unique.length})`}
            </div>
            {unique.length === 0 ? (
              <p className="owncloud-recurring-empty">Rien pour l'instant.</p>
            ) : (
              <ul className="owncloud-recurring-list owncloud-recurring-list-unique">
                {unique.map(([name, count]) => (
                  <ToggleItem key={name} name={name} count={count} hidden={hiddenNames.has(name)} onToggle={onToggle} />
                ))}
              </ul>
            )}
          </div>

          {totalDetected === 0 && (
            <p className="owncloud-recurring-empty">
              Se peuple au fil de l'exploration de plusieurs racines.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
