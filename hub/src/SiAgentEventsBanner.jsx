import React, { useCallback, useEffect, useState } from "react";
import { fetchEventsSummary } from "./siAgentClient.js";
import { bannerTone, bannerHeadline, eventKindLabel } from "./siAgent.js";

// Synthèse des événements des agents hôtes sur l'ACCUEIL du hub (livraison
// #422) : une ligne d'état (blocage général, critiques, avertissements,
// agents hors ligne / bloqués sur 24 h) et les derniers événements
// notables ; clic = ouvrir la tuile « Agents hôtes ». Jamais bloquant :
// central injoignable = bandeau discret.

const REFRESH_MS = 60000;

export default function SiAgentEventsBanner({ siAgentApiBase, onOpen }) {
  const [summary, setSummary] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    const s = await fetchEventsSummary(siAgentApiBase, 24);
    if (s?.error) { setFailed(true); setSummary(null); return; }
    setFailed(false);
    setSummary(s);
  }, [siAgentApiBase]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  if (failed) {
    return <button type="button" className="sa-banner neutral" onClick={onOpen}><span className="muted">Agents hôtes : central injoignable</span></button>;
  }
  if (!summary) return null;
  const tone = bannerTone(summary);
  const notable = (summary.notable || []).slice(0, 3);
  return (
    <button type="button" className={`sa-banner ${tone}`} onClick={onOpen} title="Ouvrir la tuile Agents hôtes">
      <span className="sa-banner-head">{tone === "bad" ? "⛔" : tone === "warn" ? "⚠" : "✔"} {bannerHeadline(summary)}</span>
      {notable.length > 0 && (
        <ul className="sa-banner-items">
          {notable.map((e) => (
            <li key={e.id}>{e.severity === "critical" ? "⛔" : "⚠"} {e.agent_id ? `${e.agent_id} — ` : ""}{eventKindLabel(e.kind)} : {e.message}</li>
          ))}
        </ul>
      )}
    </button>
  );
}
