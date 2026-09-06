import { useEffect, useState } from "react";
import { fetchCalendarSummary, fetchPixelSummary } from "../api.js";

const MONTH_LABELS = [
  "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
  "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc",
];

function todayParts() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

/**
 * Détermine la classe de couleur d'une cellule en mode "compteur",
 * selon le schéma décidé côté API (binaire ou tricolore) et les seuils
 * associés.
 */
function pixelCellClass(value, colorScheme, thresholds) {
  if (!value || value <= 0) return "no-match";
  if (colorScheme === "binary") return "match";
  if (value >= thresholds.mid) return "match-high";
  return "match-mid";
}

/**
 * Calendrier de navigation (année → mois) avec deux modes :
 * - "presence" : coloration binaire simple (existant).
 * - "counter" : agrège une étiquette JSON (compteur numérique ou
 *   occurrences "champ=valeur"), coloration binaire ou tricolore selon
 *   le volume, valeur affichée en tout petit dans la cellule.
 * La sélection multi-jours (selectedDates) reste possédée par le parent
 * pour survivre à la navigation et alimenter la corbeille.
 */
export default function CalendarPanel({ selectedDates, onToggleDate, onClearDates, keywordExpr, onChangeKeywords, onClose }) {
  const [level, setLevel] = useState("year"); // "year" | "month"
  const [year, setYear] = useState(todayParts().year);
  const [month, setMonth] = useState(todayParts().month);
  const [keywordsInput, setKeywordsInput] = useState(keywordExpr);

  const [mode, setMode] = useState("presence"); // "presence" | "counter"
  const [pixelLabelInput, setPixelLabelInput] = useState("");
  const [pixelLabel, setPixelLabel] = useState("");

  const [buckets, setBuckets] = useState([]);
  const [pixelMeta, setPixelMeta] = useState({ color_scheme: "binary", thresholds: { max: 0 } });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const period = level === "year" ? String(year) : `${year}-${String(month).padStart(2, "0")}`;

    async function load() {
      if (mode === "presence") {
        const result = await fetchCalendarSummary(level, period, keywordExpr);
        if (!cancelled) {
          setBuckets(result);
          setLoading(false);
        }
      } else {
        if (!pixelLabel) {
          if (!cancelled) {
            setBuckets([]);
            setLoading(false);
          }
          return;
        }
        const result = await fetchPixelSummary(level, period, pixelLabel, keywordExpr);
        if (!cancelled) {
          setBuckets(result?.buckets || []);
          setPixelMeta({
            color_scheme: result?.color_scheme || "binary",
            thresholds: result?.thresholds || { max: 0 },
          });
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [level, year, month, keywordExpr, mode, pixelLabel]);

  function applyKeywords() {
    onChangeKeywords(keywordsInput.trim());
  }

  function applyPixelLabel() {
    setPixelLabel(pixelLabelInput.trim());
  }

  function goToMonth(monthNumber) {
    setMonth(monthNumber);
    setLevel("month");
  }

  function dayDateString(dayNumber) {
    return `${year}-${String(month).padStart(2, "0")}-${String(dayNumber).padStart(2, "0")}`;
  }

  return (
    <div className="calendar-panel">
      <div className="calendar-header">
        <div className="calendar-nav">
          {level === "month" && (
            <button className="calendar-nav-btn" onClick={() => setLevel("year")}>
              ← retour
            </button>
          )}
          <span className="calendar-period-label">
            {level === "year" ? year : `${MONTH_LABELS[month - 1]} ${year}`}
          </span>
          {level === "year" && (
            <span className="calendar-year-controls">
              <button className="calendar-nav-btn" onClick={() => setYear((y) => y - 1)}>‹</button>
              <button className="calendar-nav-btn" onClick={() => setYear((y) => y + 1)}>›</button>
            </span>
          )}
        </div>
        <button className="calendar-close-btn" onClick={onClose}>✕</button>
      </div>

      <div className="calendar-mode-tabs">
        <button
          className={`calendar-mode-tab ${mode === "presence" ? "active" : ""}`}
          onClick={() => setMode("presence")}
        >
          Présence
        </button>
        <button
          className={`calendar-mode-tab ${mode === "counter" ? "active" : ""}`}
          onClick={() => setMode("counter")}
        >
          Compteur
        </button>
      </div>

      {mode === "counter" && (
        <div className="calendar-keywords-row">
          <input
            className="calendar-keywords-input"
            type="text"
            placeholder='étiquette (ex: frequence, ou type=incident)'
            value={pixelLabelInput}
            onChange={(e) => setPixelLabelInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applyPixelLabel()}
          />
          <button className="calendar-nav-btn" onClick={applyPixelLabel}>Appliquer</button>
        </div>
      )}

      <div className="calendar-keywords-row">
        <input
          className="calendar-keywords-input"
          type="text"
          placeholder='ex: incident OR panne AND regions (vide = tout)'
          value={keywordsInput}
          onChange={(e) => setKeywordsInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && applyKeywords()}
        />
        <button className="calendar-nav-btn" onClick={applyKeywords}>Filtrer</button>
      </div>

      <div className="calendar-selection-row">
        <span className="calendar-selection-count">
          {selectedDates.size} date(s) sélectionnée(s)
        </span>
        {selectedDates.size > 0 && (
          <button className="calendar-nav-btn" onClick={onClearDates}>
            Vider la sélection
          </button>
        )}
      </div>

      {mode === "counter" && !pixelLabel && (
        <p className="synthesis-empty">Saisis une étiquette puis « Appliquer » pour voir le compteur.</p>
      )}

      {loading && <p className="synthesis-empty">Chargement…</p>}

      {!loading && level === "year" && (mode === "presence" || pixelLabel) && (
        <div className="calendar-grid calendar-grid-year">
          {buckets.map((b) => {
            const cls =
              mode === "presence"
                ? b.has_match ? "match" : "no-match"
                : pixelCellClass(b.value, pixelMeta.color_scheme, pixelMeta.thresholds);
            return (
              <button key={b.key} className={`calendar-cell ${cls}`} onClick={() => goToMonth(b.key)}>
                {MONTH_LABELS[b.key - 1]}
                {mode === "counter" && b.value > 0 && (
                  <span className="calendar-cell-value">{b.value}</span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {!loading && level === "month" && (mode === "presence" || pixelLabel) && (
        <div className="calendar-grid calendar-grid-month">
          {buckets.map((b) => {
            const dateStr = dayDateString(b.key);
            const isSelected = selectedDates.has(dateStr);
            const cls =
              mode === "presence"
                ? b.has_match ? "match" : "no-match"
                : pixelCellClass(b.value, pixelMeta.color_scheme, pixelMeta.thresholds);
            return (
              <button
                key={b.key}
                className={`calendar-cell ${cls} ${isSelected ? "selected" : ""}`}
                onClick={() => onToggleDate(dateStr)}
                title={isSelected ? "Cliquer pour désélectionner" : "Cliquer pour sélectionner"}
              >
                {b.key}
                {mode === "counter" && b.value > 0 && (
                  <span className="calendar-cell-value">{b.value}</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
