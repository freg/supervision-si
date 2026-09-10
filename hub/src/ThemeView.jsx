// Super-tuile thématique (livraison #457) : une thématique de l'accueil
// (hubThemes.js) ouverte = ses outils en onglets. Sans outil choisi, la
// vue d'ensemble liste les outils en cartes ; un outil choisi est rendu
// TEL QUEL par `renderView(viewMode)` (la chaîne de routage de App.jsx),
// sous une barre d'onglets pour passer de l'un à l'autre sans repasser
// par l'accueil. Les fronts externes (portail tickets, coffre-fort,
// consoles) s'ouvrent dans un nouvel onglet du navigateur (↗) -- ou en
// cadre s'ils sont embarquables.
import { useState } from "react";

export default function ThemeView({ theme, entryId, onSelect, renderView, onBack }) {
  const [embedded, setEmbedded] = useState(null); // entrée « link » embarquée
  const entries = theme?.entries || [];
  const active = entries.find((e) => e.id === entryId) || null;

  const open = (e) => {
    if (e.kind === "view") { setEmbedded(null); onSelect(e.id); return; }
    if (e.onClick) { e.onClick(); return; }
    if (e.embeddable) { setEmbedded(e); onSelect(null); return; }
    window.open(e.url, "_blank", "noopener");
  };

  return (
    <div className="hub-theme">
      <div className="hub-theme-bar">
        <button type="button" className="secondary" onClick={onBack}>◀ Accueil</button>
        <strong className="hub-theme-title">{theme?.icon} {theme?.name}</strong>
        <div className="hub-theme-tabs">
          {entries.map((e) => (
            <button key={e.id} type="button" className={`secondary na-section-toggle${active?.id === e.id || embedded?.id === e.id ? " active" : ""}`} onClick={() => open(e)} title={e.kind === "view" ? e.label : `${e.label} (ouvre ${e.embeddable ? "en cadre" : "dans un nouvel onglet"})`}>
              {e.label}{e.kind === "link" && !e.embeddable ? " ↗" : ""}
            </button>
          ))}
        </div>
      </div>
      {active ? (
        renderView(active.view)
      ) : embedded ? (
        <iframe className="hub-theme-frame" src={embedded.url} title={embedded.label} />
      ) : (
        <div className="hub-grid" style={{ padding: "12px 16px" }}>
          {entries.map((e) => (
            <button key={e.id} type="button" className="hub-card hub-front-card hub-front-tile-button" onClick={() => open(e)}>
              <h2>{e.label}{e.kind === "link" && !e.embeddable ? " ↗" : ""}</h2>
              <p className="muted">{e.kind === "view" ? "outil du hub" : e.embeddable ? "front externe (en cadre)" : "front externe (nouvel onglet)"}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
