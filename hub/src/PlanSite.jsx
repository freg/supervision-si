// Plan du site (image déposée dans Nebula › Plan) avec marqueurs positionnés en fractions 0..1 (#949, extrait #960).
// Toucher / cliquer le plan appelle onPoser({x, y}) ; un marqueur cliqué appelle son onClick. `selection` entoure un marqueur.
import { useRef, useState } from "react";
import { versFraction } from "./reperageLib.js";
import { hubLink } from "./hubLinks.js";

export default function Plan({ base, version, marqueurs, onPoser, selection }) {
  const img = useRef(null);
  const [ok, setOk] = useState(null);
  return (
    <div style={{ position: "relative", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", background: "var(--panel)" }}>
      <img ref={img} alt="plan du site" src={`${base}/plan?v=${version}`} onLoad={() => setOk(true)} onError={() => setOk(false)}
        style={{ display: ok === false ? "none" : "block", width: "100%", cursor: onPoser ? "crosshair" : "default", touchAction: "manipulation" }}
        onClick={(e) => { if (!onPoser) return; const f = versFraction(e.clientX, e.clientY, img.current.getBoundingClientRect()); if (f) onPoser(f); }} />
      {ok === false && <p className="muted" style={{ padding: 12, margin: 0 }}>Pas de plan pour ce site. Le déposer dans <a href={hubLink("nebula", { tab: "plan" })}>Nebula › Plan</a> (photo du plan d'évacuation).</p>}
      {ok && (marqueurs || []).map((m) => (
        <div key={m.key} title={m.titre} onClick={(e) => { e.stopPropagation(); m.onClick && m.onClick(); }}
          style={{ position: "absolute", left: `${m.x * 100}%`, top: `${m.y * 100}%`, transform: "translate(-50%, -50%)", width: m.taille || 22, height: m.taille || 22, borderRadius: "50%",
            background: m.couleur || "var(--accent)", border: "2px solid var(--bg)", boxShadow: selection && m.key === selection ? "0 0 0 3px var(--text)" : "0 0 0 1px var(--border)", cursor: m.onClick ? "pointer" : "default", zIndex: selection && m.key === selection ? 2 : 1, fontSize: 11, lineHeight: `${(m.taille || 22) - 4}px`, textAlign: "center", color: "var(--bg)", fontWeight: 700 }}>
          {m.texte || ""}
        </div>
      ))}
    </div>
  );
}
