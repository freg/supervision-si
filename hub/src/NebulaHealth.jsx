// Santé du réseau Nebula (livraison #546) -- ce que le sondeur à la minute
// de nebula-api observe : équipements hors ligne, disponibilité sur la
// fenêtre, incidents, dernières transitions. Écrit en phrases pour être
// montré tel quel à un responsable de site (charte « Aujourd'hui »).
import { useEffect, useState } from "react";

async function getJson(url) {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

const when = (ts) => (ts ? new Date(ts * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");
const pct = (v) => (v == null ? "—" : `${(v * 100).toFixed(2)} %`);
const STATUS = { online: "en ligne", offline: "hors ligne", alerting: "en alerte", inconnu: "sans relevé" };

export default function NebulaHealth({ nebulaApiBase }) {
  const [hours, setHours] = useState(24);
  const [data, setData] = useState(null);
  const [transitions, setTransitions] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const d = await getJson(`${nebulaApiBase}/health-board?hours=${hours}`);
        if (!alive) return;
        setData(d); setError(null);
        if (d.sites && d.sites[0]) {
          const t = await getJson(`${nebulaApiBase}/sites/${encodeURIComponent(d.sites[0].site_id)}/transitions?hours=${hours}`);
          if (alive) setTransitions(t.transitions || []);
        }
      } catch (e) { if (alive) setError(e.message); }
    };
    load();
    const id = setInterval(load, 60000);
    return () => { alive = false; clearInterval(id); };
  }, [nebulaApiBase, hours]);

  if (error) return <div className="hub-card"><p className="muted" style={{ margin: 0 }}>Santé du réseau indisponible ({error}). Le sondeur démarre avec la clé API ; voir `GET /poll/status`.</p></div>;
  if (!data) return <p className="muted">Chargement…</p>;
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <span className="muted">Fenêtre :</span>
        {[1, 24, 168].map((h) => <button key={h} type="button" className={hours === h ? "" : "secondary"} onClick={() => setHours(h)}>{h === 1 ? "1 h" : h === 24 ? "24 h" : "7 jours"}</button>)}
        <span className="muted">· relevé toutes les {data.poll_seconds} s · {when(data.at)}</span>
      </div>
      {data.sites.map((s) => (
        <div key={s.site_id} className="today-paper" style={{ maxWidth: "none", marginBottom: 16 }}>
          <p className="today-kicker">{s.site_name}</p>
          <h2 className="today-title" style={{ fontSize: "1.5rem" }}>{s.resume}</h2>
          {s.phrases.length > 0 && <ul className="today-lines">{s.phrases.map((p, i) => <li key={i}>{p}</li>)}</ul>}
          <p>Disponibilité moyenne sur la fenêtre : <strong>{pct(s.availability)}</strong> · incidents : <strong>{s.incidents}</strong> · {s.online} en ligne / {s.total}.</p>
          <table className="services" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr><th style={{ textAlign: "left" }}>Équipement</th><th style={{ textAlign: "left" }}>Modèle</th><th style={{ textAlign: "left" }}>État</th><th style={{ textAlign: "left" }}>Depuis</th><th style={{ textAlign: "right" }}>Disponibilité</th><th style={{ textAlign: "right" }}>Incidents</th></tr></thead>
            <tbody>
              {s.devices.map((d) => (
                <tr key={d.dev_id} style={{ borderTop: "1px solid #ddd" }}>
                  <td>{d.name}</td><td>{d.model}</td>
                  <td><span className={`etat ${d.status === "online" ? "ok" : d.status === "offline" ? "panne" : "degrade"}`} style={{ fontFamily: "system-ui, sans-serif", fontSize: ".85em", textTransform: "uppercase", borderBottom: `3px solid ${d.status === "online" ? "#111" : d.status === "offline" ? "#a00" : "#666"}` }}>{STATUS[d.status] || d.status}</span></td>
                  <td>{when(d.since)}</td><td style={{ textAlign: "right" }}>{pct(d.availability)}</td><td style={{ textAlign: "right" }}>{d.incidents}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {transitions.length > 0 && s.site_id === data.sites[0].site_id && (
            <details style={{ marginTop: 12 }}><summary>Derniers changements d'état ({transitions.length})</summary>
              <ul className="today-lines">{transitions.slice(0, 50).map((t, i) => <li key={i}>{when(t.at)} — {t.name} : {STATUS[t.from_status] || t.from_status || "premier relevé"} → {STATUS[t.to_status] || t.to_status}</li>)}</ul>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
