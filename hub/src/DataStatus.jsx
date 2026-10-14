// Bandeau « État des données » (#763) : sources de l'écran (sondes des agents), temps de réponse de l'API, erreurs et
// constats propres à l'écran. Replié : une ligne de pastilles ; déplié : le détail et ce qu'il faut faire.
import { useEffect, useState } from "react";
import { sourceState, latencyState } from "./dataStatusLib.js";
import { fetchDiagTasks } from "./siAgentClient.js";

const DOT = { good: "●", warning: "▲", critical: "■" };

export default function DataStatus({ base, tasks = [], labels = {}, extra = [], latencyMs = null, error = null, stale = 1800, refreshKey = 0 }) {
  const [diag, setDiag] = useState(null), [open, setOpen] = useState(false), [diagErr, setDiagErr] = useState(null);
  useEffect(() => {
    if (!tasks.length) return;
    let stop = false;
    fetchDiagTasks(base, tasks).then((d) => { if (stop) return; if (d?.error) setDiagErr(d.error); else { setDiag(d); setDiagErr(null); } });
    return () => { stop = true; };
  }, [base, tasks.join(","), refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const items = [];
  if (error) items.push({ tone: "critical", text: `Erreur : ${error}` });
  if (diagErr) items.push({ tone: "warning", text: `état des sources illisible : ${diagErr}` });
  const lat = latencyState(latencyMs); if (lat) items.push(lat);
  for (const t of diag?.tasks || []) items.push(sourceState(t, labels[t.task] || t.task.replace("plugin:", ""), stale));
  for (const x of extra) items.push(x);
  if (!items.length) return null;
  const worst = items.some((i) => i.tone === "critical") ? "critical" : items.some((i) => i.tone === "warning") ? "warning" : "good";
  return (
    <div className="data-status" role="status">
      <button type="button" className="data-status-toggle" onClick={() => setOpen(!open)} title="État des données de cet écran">
        <span className={`infra-dot ${worst}`}>{DOT[worst]}</span> État des données {open ? "▾" : "▸"}
      </button>
      {!open && items.map((i, k) => <span key={k} className="data-status-chip" title={i.detail || ""}><span className={`infra-dot ${i.tone}`}>{DOT[i.tone]}</span> {i.text}</span>)}
      {open && <ul className="data-status-list">{items.map((i, k) => <li key={k}><span className={`infra-dot ${i.tone}`}>{DOT[i.tone]}</span> {i.text}{i.detail && <div className="infra-muted">{i.detail}</div>}</li>)}</ul>}
    </div>
  );
}
