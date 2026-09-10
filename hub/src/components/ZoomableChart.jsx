import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ZOOM_STEP, VIEW_INITIAL, parseViewBox, zoomAtPoint, zoomAtCenter,
  clientDeltaToViewBox, clientPointToViewBox, viewTransform, isInitialView, zoomPercent,
} from "../chartZoom.js";

// Enveloppe de zoom / déplacement pour TOUT graphique SVG du hub --
// livraison #413 (« options de zoom / loupe … pour tous les graphiques »).
// Le graphique enfant ne sait rien du zoom : il rend ses éléments SVG dans
// le viewBox qu'il connaît, cette enveloppe fournit le <svg>, le groupe
// transformé, la barre d'outils et les gestes :
//
//   boutons + / − / ⟲, pourcentage affiché ;
//   Ctrl (ou ⌘) + molette : zoom ancré sous le curseur -- la molette SEULE
//     continue de faire défiler la page : un graphique sur toute la largeur
//     qui avalerait la molette rendrait la page impossible à parcourir
//     (le graphique du cycle agile, petit et dans un cadre, garde sa
//     molette simple) ; le pincement du pavé tactile envoie ctrlKey ;
//   double-clic : loupe ×2 sur le point cliqué ;
//   glisser : déplacement (gestionnaires sur window le temps du geste,
//     jamais setPointerCapture qui casserait les clics -- piège #399).
//
// Pièges repris de networkCycleGraph (#399) : molette écoutée en NON
// passif ; conversion écran → viewBox avec l'échelle réelle (meet : une
// seule, avec marges ; none : une par axe) ; facteur recalculé après
// bornage pour que le dessin ne glisse pas en butée.

export default function ZoomableChart({
  viewBox,
  preserveAspectRatio = "xMidYMid meet",
  className = "",
  svgStyle,
  label,
  controls,          // contrôles supplémentaires (échelle, etc.) rendus dans la barre
  hint,              // texte d'aide optionnel affiché à droite de la barre
  children,
  role = "img",
}) {
  const vb = useMemo(() => parseViewBox(viewBox), [viewBox]);
  const preserve = preserveAspectRatio === "none" ? "none" : "meet";
  const [view, setView] = useState(VIEW_INITIAL);
  const [panning, setPanning] = useState(false);
  const svgRef = useRef(null);
  const panRef = useRef(null);

  useEffect(() => {
    const el = svgRef.current;
    if (!el || !vb) return undefined;
    const onWheel = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return;   // molette seule : la page défile
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const anchor = clientPointToViewBox(e.clientX - rect.left, e.clientY - rect.top, rect, vb, preserve);
      const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      setView((v) => zoomAtPoint(v, factor, anchor.x, anchor.y));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [vb, preserve]);

  useEffect(() => {
    if (!panning) return undefined;
    const onMove = (e) => {
      const start = panRef.current;
      if (!start || !svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const { dx, dy } = clientDeltaToViewBox(e.clientX - start.x, e.clientY - start.y, rect, vb, preserve);
      setView({ zoom: start.view.zoom, x: start.view.x + dx, y: start.view.y + dy });
    };
    const onUp = () => { panRef.current = null; setPanning(false); };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [panning, vb, preserve]);

  function handlePointerDown(e) {
    if (e.button !== 0) return;
    panRef.current = { x: e.clientX, y: e.clientY, view };
    setPanning(true);
  }

  function handleDoubleClick(e) {
    if (!svgRef.current || !vb) return;
    const rect = svgRef.current.getBoundingClientRect();
    const p = clientPointToViewBox(e.clientX - rect.left, e.clientY - rect.top, rect, vb, preserve);
    setView((v) => zoomAtPoint(v, 2, p.x, p.y));
  }

  if (!vb) return null;

  return (
    <div className={`hub-chart${panning ? " panning" : ""}`}>
      <div className="hub-chart-toolbar">
        {label && <span className="hub-chart-label">{label}</span>}
        {controls}
        <span className="hub-chart-zoom">
          <button type="button" className="nc-graph-btn" onClick={() => setView((v) => zoomAtCenter(v, ZOOM_STEP, vb))} title="Zoom avant (Ctrl + molette, ou double-clic sur le graphique)">+</button>
          <button type="button" className="nc-graph-btn" onClick={() => setView((v) => zoomAtCenter(v, 1 / ZOOM_STEP, vb))} title="Zoom arrière">−</button>
          <button type="button" className="nc-graph-btn" onClick={() => setView(VIEW_INITIAL)} title="Réinitialiser la vue" disabled={isInitialView(view)}>⟲</button>
          <span className="nc-graph-zoom-level">{zoomPercent(view)} %</span>
        </span>
        <span className="hub-chart-hint muted">{hint ?? "Ctrl + molette : loupe · double-clic : ×2 · glisser : déplacer"}</span>
      </div>
      <svg
        ref={svgRef}
        viewBox={viewBox}
        preserveAspectRatio={preserveAspectRatio}
        className={`hub-chart-svg ${className}`}
        style={svgStyle}
        role={role}
        aria-label={label}
        onPointerDown={handlePointerDown}
        onDoubleClick={handleDoubleClick}
      >
        <g transform={viewTransform(view)}>{children}</g>
      </svg>
    </div>
  );
}
