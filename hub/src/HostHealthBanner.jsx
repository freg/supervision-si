// Bandeau d'alerte de l'hôte du hub (livraison #593) -- demandé après un
// /var saturé qui coupait les gros fichiers du hub : visible sur toutes les
// pages, sans jeton (lampe + texte), lien vers la tour de contrôle.
import { useEffect, useState } from "react";
import { fetchHostPublic } from "./servicesClient.js";
import { hubLink } from "./hubLinks.js";

const COLORS = { red: "#e53935", orange: "#fb8c00" };

export default function HostHealthBanner({ apiBase }) {
  const [state, setState] = useState(null);
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    if (!apiBase) return undefined;
    let stop = false;
    const tick = async () => { const r = await fetchHostPublic(apiBase); if (!stop && r) { setState(r); if (r.light === "green") setHidden(false); } };
    tick();
    const id = setInterval(tick, 60000);
    return () => { stop = true; clearInterval(id); };
  }, [apiBase]);
  if (!state || state.light === "green" || hidden) return null;
  return (
    <div role="alert" style={{ background: COLORS[state.light] || COLORS.orange, color: "#111", padding: "6px 16px", display: "flex", gap: 12, alignItems: "center", fontWeight: 600, fontSize: 14 }}>
      <span>{state.light === "red" ? "⛔" : "⚠️"} Hôte du hub : {state.text}</span>
      <a href={hubLink("control", { tab: "services" })} style={{ color: "#111", textDecoration: "underline" }}>ouvrir la tour de contrôle</a>
      <span style={{ flex: 1 }} />
      <button type="button" className="secondary" onClick={() => setHidden(true)} title="masquer jusqu'au prochain changement d'état">masquer</button>
    </div>
  );
}
