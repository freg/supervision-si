// Vue « Aujourd'hui » (livraison #544) -- l'écran du responsable non
// technicien : trois questions, des phrases, une action par bloc. Charte
// « Simple » (papier, encre, filets, aucune icône) posée DANS le hub, à
// côté des tuiles techniques qui gardent leur densité. Données : état des
// services du pont (#541/#542), file des tickets, incidents Cortex --
// chaque source absente donne une phrase honnête, jamais une erreur brute.
import { useEffect, useState } from "react";
import { demandeBase } from "./publicLinks.js";
import { fetchIncidents } from "./cortexClient.js";
import { servicesSummary, ticketsSummary, incidentsSummary, overall } from "./today.js";

async function getJson(url) {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function Block({ title, summary, action, onAction }) {
  return (
    <section className={`today-block tone-${summary.tone}`}>
      <p className="today-kicker">{title}</p>
      <p className="today-headline">{summary.headline}</p>
      {summary.lines.length > 0 && <ul className="today-lines">{summary.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>}
      {action && <button type="button" className="today-action" onClick={onAction}>{action}</button>}
    </section>
  );
}

export default function TodayView({ onBack, onNavigate, demandeUrl, ticketsApiBase, cortexApiBase, portalUrl }) {
  const [services, setServices] = useState(undefined);
  const [tickets, setTickets] = useState(undefined);
  const [incidents, setIncidents] = useState(undefined);
  const [at, setAt] = useState(null);
  const base = demandeBase(demandeUrl);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      const [s, t, i] = await Promise.all([
        base ? getJson(base + "etat.json").catch(() => null) : Promise.resolve(null),
        ticketsApiBase ? getJson(`${ticketsApiBase}/queue?state=all&include_archived=true`).then((d) => (Array.isArray(d) ? d : d.tickets || d.items || null)).catch(() => null) : Promise.resolve(null),
        cortexApiBase ? fetchIncidents(cortexApiBase, "open").then((d) => d.incidents || []).catch(() => null) : Promise.resolve(null),
      ]);
      if (!alive) return;
      setServices(s); setTickets(t); setIncidents(i); setAt(new Date());
    };
    load();
    const id = setInterval(load, 60000);
    return () => { alive = false; clearInterval(id); };
  }, [base, ticketsApiBase, cortexApiBase]);

  const blocks = [servicesSummary(services), ticketsSummary(tickets), incidentsSummary(incidents)];
  return (
    <div className="today-view">
      <div className="hub-theme-bar"><button type="button" className="secondary" onClick={onBack}>◀ Retour</button></div>
      <main className="today-paper">
        <p className="today-kicker">Aujourd'hui{at ? ` · ${at.toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" })}` : ""}</p>
        <h1 className="today-title">{overall(blocks)}</h1>
        <Block title="Est-ce que ça marche ?" summary={blocks[0]} action={base ? "Voir l'état des services" : null} onAction={() => window.open(base + "etat", "_blank", "noopener")} />
        <Block title="Où en sont les demandes ?" summary={blocks[1]} action={portalUrl ? "Ouvrir les demandes" : null} onAction={() => window.open(portalUrl, "_blank", "noopener")} />
        <Block title="Y a-t-il des incidents ?" summary={blocks[2]} action={cortexApiBase ? "Voir le détail (Cortex)" : null} onAction={() => onNavigate && onNavigate("cortex")} />
        <p className="today-foot">Cette page se met à jour toute seule. Les outils détaillés restent dans les tuiles.</p>
      </main>
    </div>
  );
}
