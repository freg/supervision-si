// Site publié par un agent, vu depuis le hub (livraison #562) -- note
// design : « le hub doit pouvoir présenter en preview et en réel le site
// d'un agent ». Aperçu = la page calculée par le central (si-agent-api
// /publish/preview, même gabarit et même contenu que sur le site, joignable
// de partout) ; réel = la page servie par l'agent sur le LAN du site (en
// cadre, joignable seulement depuis ce réseau -- sinon lien à ouvrir).
import { useState } from "react";
import PageFrame from "./PageFrame.jsx";

export default function AgentPageView({ pages, initialId, siAgentApiBase, onBack }) {
  const [id, setId] = useState(initialId || (pages[0] && pages[0].id));
  const [mode, setMode] = useState("preview");
  const page = pages.find((p) => p.id === id) || pages[0];
  const agentId = page ? page.id.replace(/^agent-/, "") : "";
  const previewUrl = page && siAgentApiBase ? `${siAgentApiBase}/agents/${encodeURIComponent(agentId)}/publish/preview` : "";
  const src = mode === "real" ? page?.url : previewUrl;
  return (
    <PageFrame
      title="Site publié par un agent" onBack={onBack}
      left={{ title: "Agents", body: pages.length ? pages.map((p) => (
        <button key={p.id} type="button" className={`secondary hub-page-option${p.id === page?.id ? " active" : ""}`} onClick={() => setId(p.id)} title={p.description}>{p.name}<br /><span className="muted" style={{ fontSize: 11 }}>{p.url}</span></button>
      )) : <p className="muted">Aucun agent ne publie de page (réglage « publish » de l'agent).</p> }}
      actions={page && (
        <>
          <button type="button" className={mode === "preview" ? "" : "secondary"} onClick={() => setMode("preview")} title="page calculée par le hub, joignable de partout">Aperçu (hub)</button>
          <button type="button" className={mode === "real" ? "" : "secondary"} onClick={() => setMode("real")} title="page servie par l'agent, joignable depuis le réseau du site">Réel (site)</button>
          <a className="secondary" href={page.url} target="_blank" rel="noopener noreferrer">ouvrir le réel ↗</a>
        </>
      )}
      foot={page && (mode === "real" ? `Réel : ${page.url} — cadre vide si vous n'êtes pas sur le réseau du site (ou si le navigateur refuse http dans une page https : utiliser « ouvrir le réel »).` : `Aperçu : ${previewUrl}`)}
      className="hub-agent-page"
    >
      {page && src ? <iframe key={src} className="hub-agent-frame" src={src} title={page.name} /> : <p className="muted">Sélectionner un agent.</p>}
    </PageFrame>
  );
}
