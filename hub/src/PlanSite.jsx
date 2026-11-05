// Plan du site (image déposée dans Nebula › Plan) avec marqueurs positionnés en fractions 0..1 (#949, extrait #960).
// Toucher / cliquer le plan appelle onPoser({x, y}) ; un marqueur cliqué appelle son onClick. `selection` entoure un marqueur.
// #973 : calque (espaces délimités, étiquettes typées) dessiné par-dessus ; `symbolique` estompe l'image pour ne garder que
// le calque ; `trace` = polygone en cours de tracé ; `liens` = segments [x1, y1, x2, y2] (remontée vers l'amont) ;
// `surligne` = clés de marqueurs à entourer ; onForme / onEtiquette rendent formes et étiquettes cliquables (édition).
import { useRef, useState } from "react";
import { versFraction } from "./reperageLib.js";
import { centroide } from "./planCalqueLib.js";
import { hubLink } from "./hubLinks.js";

const COULEUR_FORME = { espace: "var(--accent)", zone: "var(--warning)" };
const STYLE_ETIQUETTE = {
  espace: { fontWeight: 700, color: "var(--text)" },
  spot: { color: "var(--accent)", fontWeight: 600 },
  zone: { fontStyle: "italic", color: "var(--warning)" },
  note: { color: "var(--muted)", fontSize: 10 },
};
const PREFIXE = { spot: "((•)) ", note: "✎ " };

export default function Plan({ base, version, marqueurs, onPoser, selection, calque = null, symbolique = false, trace = null, liens = null,
  surligne = null, onForme = null, onEtiquette = null }) {
  const img = useRef(null);
  const [ok, setOk] = useState(null);
  const formes = calque?.formes || [];
  const etiquettes = calque?.etiquettes || [];
  const pts = (p) => p.map(([x, y]) => `${x},${y}`).join(" ");
  const clicCalque = (fn, id) => (fn ? (e) => { e.stopPropagation(); fn(id); } : undefined);
  return (
    <div style={{ position: "relative", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", background: symbolique ? "var(--bg)" : "var(--panel)" }}>
      <img ref={img} alt="plan du site" src={`${base}/plan?v=${version}`} onLoad={() => setOk(true)} onError={() => setOk(false)}
        style={{ display: ok === false ? "none" : "block", width: "100%", cursor: onPoser ? "crosshair" : "default", touchAction: "manipulation", opacity: symbolique ? 0.08 : 1 }}
        onClick={(e) => { if (!onPoser) return; const f = versFraction(e.clientX, e.clientY, img.current.getBoundingClientRect()); if (f) onPoser(f); }} />
      {ok === false && <p className="muted" style={{ padding: 12, margin: 0 }}>Pas de plan pour ce site. Le déposer dans <a href={hubLink("nebula", { tab: "plan" })}>Nebula › Plan</a> (photo du plan d'évacuation).</p>}
      {ok && (formes.length > 0 || trace?.length > 0 || liens?.length > 0) && (
        <svg viewBox="0 0 1 1" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
          {formes.map((f) => (
            <polygon key={f.id} points={pts(f.points)} vectorEffect="non-scaling-stroke" onClick={clicCalque(onForme, f.id)}
              style={{ fill: COULEUR_FORME[f.type] || "var(--accent)", fillOpacity: symbolique ? 0.22 : 0.1, stroke: COULEUR_FORME[f.type] || "var(--accent)", strokeWidth: 2,
                strokeDasharray: f.type === "zone" ? "6 4" : undefined, pointerEvents: onForme ? "auto" : "none", cursor: onForme ? "pointer" : "default" }}>
              <title>{f.nom || "(sans nom)"}</title>
            </polygon>
          ))}
          {trace?.length > 0 && <polyline points={pts(trace)} vectorEffect="non-scaling-stroke" style={{ fill: "none", stroke: "var(--warning)", strokeWidth: 2, strokeDasharray: "4 3" }} />}
          {(liens || []).map((l, i) => <line key={i} x1={l[0]} y1={l[1]} x2={l[2]} y2={l[3]} vectorEffect="non-scaling-stroke" style={{ stroke: "var(--warning)", strokeWidth: 3 }} />)}
        </svg>
      )}
      {ok && formes.filter((f) => f.nom).map((f) => {
        const [x, y] = centroide(f.points);
        return <div key={"n" + f.id} style={{ position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, transform: "translate(-50%, -50%)", pointerEvents: "none",
          fontSize: 11, fontWeight: 700, color: "var(--text)", textShadow: "0 0 3px var(--bg), 0 0 3px var(--bg)", whiteSpace: "nowrap" }}>{f.nom}</div>;
      })}
      {ok && etiquettes.map((t) => (
        <div key={t.id} title={`${t.type} : ${t.texte}`} onClick={clicCalque(onEtiquette, t.id)}
          style={{ position: "absolute", left: `${t.x * 100}%`, top: `${t.y * 100}%`, transform: "translate(-50%, -50%)", fontSize: 11, whiteSpace: "nowrap",
            textShadow: "0 0 3px var(--bg), 0 0 3px var(--bg)", pointerEvents: onEtiquette ? "auto" : "none", cursor: onEtiquette ? "pointer" : "default", ...(STYLE_ETIQUETTE[t.type] || {}) }}>
          {(PREFIXE[t.type] || "") + t.texte}
        </div>
      ))}
      {ok && (trace || []).map(([x, y], i) => (
        <div key={"t" + i} style={{ position: "absolute", left: `${x * 100}%`, top: `${y * 100}%`, transform: "translate(-50%, -50%)", width: i === 0 ? 12 : 7, height: i === 0 ? 12 : 7,
          borderRadius: "50%", background: "var(--warning)", border: "1px solid var(--bg)", pointerEvents: "none" }} />
      ))}
      {ok && (marqueurs || []).map((m) => {
        const sel = selection && m.key === selection;
        const sur = surligne && surligne.has(m.key);
        return (
          <div key={m.key} title={m.titre} onClick={(e) => { e.stopPropagation(); m.onClick && m.onClick(); }}
            style={{ position: "absolute", left: `${m.x * 100}%`, top: `${m.y * 100}%`, transform: "translate(-50%, -50%)", width: m.taille || 22, height: m.taille || 22, borderRadius: "50%",
              background: m.couleur || "var(--accent)", border: "2px solid var(--bg)", boxShadow: sel ? "0 0 0 3px var(--text)" : sur ? "0 0 0 3px var(--warning)" : "0 0 0 1px var(--border)",
              cursor: m.onClick ? "pointer" : "default", zIndex: sel || sur ? 2 : 1, fontSize: 11, lineHeight: `${(m.taille || 22) - 4}px`, textAlign: "center", color: "var(--bg)", fontWeight: 700 }}>
            {m.texte || ""}
          </div>
        );
      })}
    </div>
  );
}
