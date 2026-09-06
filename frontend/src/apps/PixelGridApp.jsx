import { useEffect, useMemo, useRef, useState } from "react";
import { fetchTypes, fetchMeta, fetchAggregateRange, fetchEvents, fetchDevices } from "./pixelGridApi.js";
import TimelineView from "./TimelineView.jsx";

const LEVELS = ["year", "month", "day", "hour", "minute"];
const NEXT_LEVEL = { year: "month", month: "day", day: "hour", hour: "minute", minute: null };
const LEVEL_LABELS = { year: "Année", month: "Mois", day: "Jour", hour: "Heure", minute: "Minute" };

function addUnit(date, level) {
  const d = new Date(date);
  if (level === "year") d.setUTCFullYear(d.getUTCFullYear() + 1);
  else if (level === "month") d.setUTCMonth(d.getUTCMonth() + 1);
  else if (level === "day") d.setUTCDate(d.getUTCDate() + 1);
  else if (level === "hour") d.setUTCHours(d.getUTCHours() + 1);
  else if (level === "minute") d.setUTCMinutes(d.getUTCMinutes() + 1);
  return d;
}

/**
 * Choisit un niveau + une plage de vue initiale à partir de l'étendue
 * réelle des données — "paramétrage automatique", ajustable ensuite à
 * la main (sélecteur de niveau + clic pour zoomer/dézoomer).
 */
function autoLevelForSpan(spanDays) {
  if (spanDays > 366) return "year";
  if (spanDays > 60) return "month";
  if (spanDays > 3) return "day";
  if (spanDays > 0.2) return "hour";
  return "minute";
}

/**
 * Palier d'activité (livraison #371) -- échelle RELATIVE au maximum
 * observé dans la vue courante (pas un seuil absolu, contrairement
 * aux couleurs serveur) : un même total signifie "beaucoup" sur une
 * vue clairsemée et "peu" sur une vue dense, jamais un chiffre en dur
 * qui n'aurait de sens que pour un seul type de données.
 */
function activityTier(total, maxTotal) {
  if (!total || total === 0) return "none";
  if (!maxTotal || maxTotal <= 0) return "none";
  const ratio = total / maxTotal;
  if (ratio >= 0.66) return "high";
  if (ratio >= 0.33) return "medium";
  return "low";
}

export default function PixelGridApp() {
  const [types, setTypes] = useState([]);
  const [selectedType, setSelectedType] = useState(null);
  const [meta, setMeta] = useState(null);

  const [level, setLevel] = useState(null);
  const [rangeStart, setRangeStart] = useState(null);
  const [rangeEnd, setRangeEnd] = useState(null);
  const [breadcrumb, setBreadcrumb] = useState([]); // [{level, start, end, label}]

  const [buckets, setBuckets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [cellSize, setCellSize] = useState(3);
  const [hovered, setHovered] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null); // { key, start, end, color, value, total }
  const [selectedCellEvents, setSelectedCellEvents] = useState([]);
  const [selectedCellLoading, setSelectedCellLoading] = useState(false);
  const [selectedCellTruncated, setSelectedCellTruncated] = useState(false);
  const [timelineDevice, setTimelineDevice] = useState(null); // { nom } | null
  // Filtrage utilisateur/équipement réel (livraison #371, backlog
  // item 10 -- resté hors portée jusqu'ici, la seule voie existante
  // était de cliquer un événement puis voir SA timeline séparément,
  // jamais filtrer la grille elle-même). Liste des noms distincts
  // rechargée à chaque changement de type -- un "nom" n'a de sens
  // que pour le type où il a été vu (voir /devices, pixel-grid-api).
  const [nomFilter, setNomFilter] = useState(null);
  const [availableNoms, setAvailableNoms] = useState([]);
  // Mode de coloration "activité" (livraison #371, second point resté
  // ouvert de l'item 10 du backlog) -- calculé ENTIÈREMENT côté
  // client à partir de `total` (déjà présent sur chaque bucket, voir
  // pixel-grid-api), jamais un nouveau champ ni un appel serveur
  // supplémentaire. Volontairement une échelle DISTINCTE
  // (bleu/intensité) de celle du serveur (vert/orange/rouge, taux
  // d'erreur) -- même nom de classe CSS aurait mélangé deux
  // sémantiques différentes (sévérité vs volume).
  const [colorMode, setColorMode] = useState("error"); // "error" | "activity"
  const hasInitialized = useRef(false);

  useEffect(() => {
    fetchTypes().then((t) => {
      setTypes(t);
      if (t.length > 0) setSelectedType(t[0].type);
    });
  }, []);

  useEffect(() => {
    if (!selectedType) return;
    let cancelled = false;

    // Réinitialisé à chaque changement de type -- un nom vu pour un
    // type n'a pas de sens pour un autre (voir /devices).
    setNomFilter(null);
    fetchDevices(selectedType).then((devices) => {
      if (cancelled) return;
      setAvailableNoms(devices);
    });

    async function loadMeta() {
      const m = await fetchMeta(selectedType);
      if (cancelled || !m) return;
      setMeta(m);

      // Le paramétrage (niveau, taille, plage) ne se calcule
      // automatiquement qu'à la toute première ouverture — un
      // changement de type ensuite conserve le dernier réglage manuel
      // plutôt que de revenir systématiquement à la vue auto (souvent
      // clairsemée au niveau année).
      if (!hasInitialized.current) {
        hasInitialized.current = true;
        const initialLevel = autoLevelForSpan(m.span_days);
        const start = new Date(m.min_ts * 1000).toISOString();
        const end = new Date((m.max_ts + 1) * 1000).toISOString();
        setLevel(initialLevel);
        setRangeStart(start);
        setRangeEnd(end);
        setBreadcrumb([{ level: initialLevel, start, end, label: "Vue auto" }]);
      }
    }

    loadMeta();
    return () => {
      cancelled = true;
    };
  }, [selectedType]);

  useEffect(() => {
    if (!selectedType || !level || !rangeStart || !rangeEnd) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchAggregateRange(selectedType, level, rangeStart, rangeEnd, nomFilter).then((result) => {
      if (cancelled) return;
      setLoading(false);
      if (!result.ok) {
        setError(result.error);
        setBuckets([]);
        return;
      }
      setBuckets(result.data.buckets);
    });

    return () => {
      cancelled = true;
    };
  }, [selectedType, level, rangeStart, rangeEnd, nomFilter]);

  // Recalculé à chaque changement de vue (buckets) -- échelle
  // toujours relative à ce qui est actuellement affiché.
  const maxTotalInView = useMemo(
    () => buckets.reduce((max, b) => (b.total > max ? b.total : max), 0),
    [buckets]
  );

  function handleTypeChange(type) {
    setSelectedType(type);
    setBuckets([]);
  }

  function handleCellClick(bucket) {
    // La cellule cliquée alimente toujours la colonne de détail (ses
    // événements bruts), qu'on puisse zoomer davantage ou non (déjà au
    // niveau minute).
    const cellEnd = addUnit(bucket.start, level).toISOString();
    setSelectedCell({ ...bucket, rangeEnd: cellEnd });
    setSelectedCellLoading(true);
    fetchEvents(selectedType, bucket.start, cellEnd).then((result) => {
      setSelectedCellEvents(result.events || []);
      setSelectedCellTruncated(Boolean(result.truncated));
      setSelectedCellLoading(false);
    });

    const nextLevel = NEXT_LEVEL[level];
    if (!nextLevel) return; // minute = niveau le plus fin, pas de zoom supplémentaire

    setLevel(nextLevel);
    setRangeStart(bucket.start);
    setRangeEnd(cellEnd);
    setBreadcrumb((prev) => [...prev, { level: nextLevel, start: bucket.start, end: cellEnd, label: bucket.key }]);
  }

  function handleCloseDetail() {
    setSelectedCell(null);
    setSelectedCellEvents([]);
  }

  function handleBreadcrumbClick(index) {
    const entry = breadcrumb[index];
    setLevel(entry.level);
    setRangeStart(entry.start);
    setRangeEnd(entry.end);
    setBreadcrumb((prev) => prev.slice(0, index + 1));
  }

  function handleResetToAuto() {
    if (!meta) return;
    const initialLevel = autoLevelForSpan(meta.span_days);
    const start = new Date(meta.min_ts * 1000).toISOString();
    const end = new Date((meta.max_ts + 1) * 1000).toISOString();
    setLevel(initialLevel);
    setRangeStart(start);
    setRangeEnd(end);
    setBreadcrumb([{ level: initialLevel, start, end, label: "Vue auto" }]);
  }

  function handleManualLevel(newLevel) {
    if (newLevel === level) return;
    setLevel(newLevel);
    setBreadcrumb((prev) => [...prev, { level: newLevel, start: rangeStart, end: rangeEnd, label: `${LEVEL_LABELS[newLevel]} (manuel)` }]);
  }

  if (timelineDevice) {
    return (
      <TimelineView
        type={selectedType}
        nom={timelineDevice}
        onClose={() => setTimelineDevice(null)}
      />
    );
  }

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="pixel-grid-type-select">
          {types.map((t) => (
            <button
              key={t.type}
              className={`pixel-grid-type-btn ${selectedType === t.type ? "active" : ""}`}
              onClick={() => handleTypeChange(t.type)}
            >
              {t.type} <span className="pixel-grid-type-kind">({t.kind})</span>
            </button>
          ))}
          {types.length === 0 && (
            <span className="pixel-grid-empty-hint">
              Aucun type trouvé — génère des données avec pixel-grid/data-generator/generate.sh
            </span>
          )}
        </div>

        <div className="pixel-grid-controls">
          <span className="pixel-grid-controls-label">Niveau :</span>
          {LEVELS.map((l) => (
            <button
              key={l}
              className={`pixel-grid-level-btn ${level === l ? "active" : ""}`}
              onClick={() => handleManualLevel(l)}
              disabled={!selectedType}
            >
              {LEVEL_LABELS[l]}
            </button>
          ))}
          <span className="pixel-grid-controls-label">Taille :</span>
          {[2, 3, 4].map((s) => (
            <button
              key={s}
              className={`pixel-grid-level-btn ${cellSize === s ? "active" : ""}`}
              onClick={() => setCellSize(s)}
            >
              {s}px
            </button>
          ))}
          {availableNoms.length > 0 && (
            <>
              <span className="pixel-grid-controls-label">Filtrer :</span>
              <select
                className="pixel-grid-nom-select"
                value={nomFilter || ""}
                onChange={(e) => setNomFilter(e.target.value || null)}
                title="Filtrer la grille sur un seul équipement/utilisateur"
              >
                <option value="">Tous</option>
                {availableNoms.map((d) => (
                  <option key={d.nom} value={d.nom}>
                    {d.nom} ({d.total})
                  </option>
                ))}
              </select>
            </>
          )}
          <button className="pixel-grid-reset-btn" onClick={handleResetToAuto} disabled={!meta}>
            🏠 Vue auto
          </button>
          <span className="pixel-grid-controls-label">Couleur :</span>
          <button
            className={`pixel-grid-level-btn ${colorMode === "error" ? "active" : ""}`}
            onClick={() => setColorMode("error")}
            title="Colore par taux d'erreur (mode par défaut)"
          >
            Erreurs
          </button>
          <button
            className={`pixel-grid-level-btn ${colorMode === "activity" ? "active" : ""}`}
            onClick={() => setColorMode("activity")}
            title="Colore par volume d'activité (nombre de points), relatif à la vue actuelle -- ignore le taux d'erreur"
          >
            Activité
          </button>
        </div>
      </div>

      {breadcrumb.length > 0 && (
        <div className="pixel-grid-breadcrumb">
          {breadcrumb.map((b, i) => (
            <span key={i}>
              {i > 0 && <span className="pixel-grid-breadcrumb-sep">→</span>}
              <button className="pixel-grid-breadcrumb-btn" onClick={() => handleBreadcrumbClick(i)}>
                {b.label}
              </button>
            </span>
          ))}
        </div>
      )}

      {error && <p className="pixel-grid-error">{error}</p>}

      <div className="pixel-grid-body">
        <div className="pixel-grid-main">
          {loading && <p className="synthesis-empty">Chargement…</p>}

          {!loading && !error && buckets.length > 0 && (
            <div className="pixel-grid-mosaic-wrapper">
              <div className="pixel-grid-mosaic" style={{ "--cell-size": `${cellSize}px` }}>
                {buckets.map((b) => {
                  const displayColor = colorMode === "activity" ? `activity-${activityTier(b.total, maxTotalInView)}` : b.color;
                  return (
                    <div
                      key={b.key}
                      className={`pixel-grid-cell pixel-grid-cell-${displayColor} ${selectedCell?.key === b.key ? "selected" : ""}`}
                      onClick={() => handleCellClick(b)}
                      onMouseEnter={() => setHovered(b)}
                      onMouseLeave={() => setHovered(null)}
                      title={`${b.key} — valeur: ${b.value ?? "n/a"} (${b.total} pt${b.total > 1 ? "s" : ""})`}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {!loading && !error && buckets.length === 0 && selectedType && (
            <p className="synthesis-empty">Aucune donnée sur cette plage.</p>
          )}

          {hovered && (
            <div className="pixel-grid-hover-detail">
              <strong>{hovered.key}</strong> — valeur : {hovered.value ?? "n/a"} — {hovered.total} point(s) — couleur :{" "}
              {colorMode === "activity" ? `activité ${activityTier(hovered.total, maxTotalInView)}` : hovered.color}
            </div>
          )}
        </div>

        {selectedCell && (
          <div className="pixel-grid-detail-col">
            <div className="pixel-grid-detail-header">
              <strong>{selectedCell.key}</strong>
              <button className="calendar-close-btn" onClick={handleCloseDetail}>✕</button>
            </div>
            <div className="pixel-grid-detail-summary">
              {colorMode === "activity" ? (
                <>couleur : <span className={`pixel-grid-detail-color-activity-${activityTier(selectedCell.total, maxTotalInView)}`}>activité {activityTier(selectedCell.total, maxTotalInView)}</span></>
              ) : (
                <>couleur : <span className={`pixel-grid-detail-color-${selectedCell.color}`}>{selectedCell.color}</span></>
              )}
              {" · "}valeur agrégée : {selectedCell.value ?? "n/a"}
              {" · "}{selectedCell.total} point(s) au total
            </div>

            {selectedCellLoading && <p className="synthesis-empty">Chargement…</p>}

            {!selectedCellLoading && selectedCellEvents.length === 0 && (
              <p className="synthesis-empty">Aucun événement individuel trouvé.</p>
            )}

            {!selectedCellLoading && selectedCellEvents.length > 0 && (
              <div className="pixel-grid-detail-events">
                {selectedCellEvents.map((e, i) => (
                  <div key={i} className="pixel-grid-detail-event">
                    <div className="pixel-grid-detail-event-header">
                      <span className="pixel-grid-detail-event-time">{e.iso}</span>
                      <span className={`pixel-grid-detail-event-valeur v-${e.valeur}`}>{e.valeur}</span>
                    </div>
                    <button
                      className="pixel-grid-detail-event-nom pixel-grid-detail-event-nom-btn"
                      onClick={() => setTimelineDevice(e.nom)}
                      title={`${e.nom} — voir la timeline de cet équipement`}
                    >
                      📈 {e.nom}
                    </button>
                    {e.data && (
                      <div className="pixel-grid-detail-event-data">
                        {Object.entries(e.data).map(([k, v]) => (
                          <div key={k} className="synthesis-field-row">
                            <span className="synthesis-field-label">{k}</span>
                            <span>{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {selectedCellTruncated && (
                  <p className="pixel-grid-detail-truncated">Liste tronquée (limite atteinte).</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
