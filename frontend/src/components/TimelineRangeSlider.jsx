// Curseur de fenêtre glissante générique — deux poignées (début/fin)
// indépendamment glissables, superposées sur un même rail (technique
// classique : deux <input type="range"> empilés, chacun cliquable
// uniquement sur son curseur via pointer-events CSS).
//
// Composant volontairement sans connaissance métier (pas d'import
// d'owncloudLib.js ici) : min/max/start/end sont de simples nombres,
// et `formatValue` est fourni par l'appelant pour l'affichage — libre
// à un futur module de le réutiliser avec une autre unité que le temps.
export default function TimelineRangeSlider({ min, max, start, end, onChange, formatValue }) {
  const allFinite = [min, max, start, end].every((v) => typeof v === "number" && Number.isFinite(v));
  if (!allFinite) {
    // Un <input type="range"> avec min/max/value NaN se comporte mal
    // (attributs invalides, avertissement React sur value contrôlée) —
    // mieux vaut ne rien afficher qu'un curseur à moitié cassé. Ne
    // devrait normalement jamais arriver (les appelants ne rendent ce
    // composant que lorsque leurs bornes existent), mais un module
    // futur ou une donnée réelle imprévue ne doit jamais produire
    // "Invalid Date" à l'écran.
    return null;
  }

  const span = Math.max(max - min, 1);
  const startPct = ((start - min) / span) * 100;
  const endPct = ((end - min) / span) * 100;

  const handleStartChange = (e) => {
    const v = Math.min(Number(e.target.value), end);
    onChange(v, end);
  };
  const handleEndChange = (e) => {
    const v = Math.max(Number(e.target.value), start);
    onChange(start, v);
  };

  const fmt = formatValue || String;

  return (
    <div className="timeline-range">
      <div className="timeline-range-labels">
        <span>{fmt(start)}</span>
        <span>{fmt(end)}</span>
      </div>
      <div className="timeline-range-track-wrap">
        <div className="timeline-range-track" />
        <div
          className="timeline-range-fill"
          style={{ left: `${startPct}%`, width: `${Math.max(endPct - startPct, 0)}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          value={start}
          onChange={handleStartChange}
          className="timeline-range-input"
          aria-label="Début de la fenêtre"
        />
        <input
          type="range"
          min={min}
          max={max}
          value={end}
          onChange={handleEndChange}
          className="timeline-range-input"
          aria-label="Fin de la fenêtre"
        />
      </div>
    </div>
  );
}
