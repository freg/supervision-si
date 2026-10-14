// Tuile « Parc IA » (livraison #756) : les hôtes d'IA (Ollama, VM, conteneurs Docker), leurs modèles, leurs tests et
// leur activité, et des gestes encadrés sur l'hôte (liste fermée, motif journalisé -- pas de shell).
//   - Assistant : modèle configuré, joignable, index ; évaluations par modèle (dernier / meilleur passage, critères) ;
//     activité par jour (appels, erreurs, temps moyen, jetons/s) -- relais en lecture si-agent-api /ia/assistant/* ;
//   - Hôtes : en-tête htop, modèles Ollama (déployer, charger, tester : OllamaSection #746), conteneurs, gestes ;
//   - hôtes ajoutés à la main (ex. la VM qui porte l'assistant sous Docker) : /ia/hosts.
import DataStatus from "./DataStatus.jsx";   // #763 : état des données
import { useEffect, useState } from "react";
import OllamaSection from "./OllamaSection.jsx";
import { fetchFleet, sendCommand, fetchCommand, fetchIaOverview, saveIaHosts, fetchIaAssistant } from "./siAgentClient.js";
import { fmtBytes, fmtUptime, fillLevel } from "./infraLib.js";
import { byModel, activityTotals, allowedContainers, gestureParams, scoreTone, ACTION_TARGET } from "./iaParkLib.js";

const TABS = [["hotes", "Hôtes et modèles"], ["tests", "Tests (évaluations)"], ["activite", "Activité"]];
const when = (t) => (t ? new Date(t).toLocaleString("fr-FR") : "—");

function Meter({ p, label }) {
  if (p == null) return <span className="infra-muted">—</span>;
  return <span className="infra-meter-wrap"><span className="infra-meter"><span className={`fill ${fillLevel(p).tone}`} style={{ width: `${Math.min(100, p)}%` }} /></span><em>{label}</em></span>;
}
function Score({ s }) {
  if (s == null) return <span className="infra-muted">—</span>;
  const tone = scoreTone(s);
  return <span className="infra-meter-wrap"><span className="infra-meter"><span className={`fill ${tone === "good" ? "" : tone}`} style={{ width: `${Math.round(s * 100)}%` }} /></span><em>{s.toFixed(2)}</em></span>;
}

async function command(base, agentId, type, params, onWait) {
  const r = await sendCommand(base, agentId, type, params);
  if (r?.error) throw new Error(r.error);
  const cid = r?.command?.id || r?.id, t0 = Date.now();
  while (Date.now() - t0 < 4 * 60 * 1000) {
    await new Promise((ok) => setTimeout(ok, 2500));
    onWait?.(Math.round((Date.now() - t0) / 1000));
    const c = await fetchCommand(base, cid).catch(() => null);
    if (c && (c.status === "done" || c.status === "failed")) {
      const res = c.result?.result || c.result || {};
      if (c.status === "failed" || res.ok === false) throw new Error(res.error || c.result?.error || "refusé");
      return res;
    }
  }
  throw new Error("pas de réponse de l'agent en 4 min (hors ligne ?)");
}

function Gestures({ base, host, username }) {
  const [cat, setCat] = useState(null), [g, setG] = useState({ action: "", lines: 200, reason: "" }), [out, setOut] = useState(null), [busy, setBusy] = useState("");
  const load = async () => { setBusy("catalogue"); try { setCat(await command(base, host.agent_id, "hostops", { action: "catalogue" })); } catch (e) { setOut({ error: e.message }); } setBusy(""); };
  const go = async () => {
    const { params, error, write } = gestureParams(g, cat);
    if (error) { setOut({ error }); return; }
    if (write && !window.confirm(`${cat.labels[g.action]} sur ${host.hostname || host.agent_id} : ${params.unit || params.container || params.dir} ?`)) return;
    setBusy("…"); setOut(null);
    try { setOut(await command(base, host.agent_id, "hostops", { ...params, actor: username }, (s) => setBusy(`${s} s`))); } catch (e) { setOut({ error: e.message }); }
    setBusy("");
  };
  if (!cat) return <p><button className="secondary" onClick={load} disabled={!!busy}>{busy ? "⏳ catalogue…" : "Gestes encadrés…"}</button>{out?.error && <span className="infra-status critical">{out.error}</span>}</p>;
  if (!cat.enabled) return <p className="infra-muted">Gestes encadrés désactivés sur cet hôte (agent.json : hostops.enabled).</p>;
  const target = ACTION_TARGET[g.action];
  const containers = allowedContainers(host.containers || [], cat.containers);
  return (
    <div className="infra-card" style={{ marginTop: 8 }}>
      <div className="infra-top" style={{ margin: 0 }}>
        <select value={g.action} onChange={(e) => setG({ ...g, action: e.target.value })}><option value="">— geste —</option>
          <optgroup label="Lecture">{cat.read.map((a) => <option key={a} value={a}>{cat.labels[a]}</option>)}</optgroup>
          <optgroup label="Action (motif)">{cat.write.map((a) => <option key={a} value={a}>{cat.labels[a]}</option>)}</optgroup></select>
        {target === "unit" && <select value={g.unit || ""} onChange={(e) => setG({ ...g, unit: e.target.value })}><option value="">service…</option>{cat.units.map((u) => <option key={u}>{u}</option>)}</select>}
        {target === "container" && <select value={g.container || ""} onChange={(e) => setG({ ...g, container: e.target.value })}><option value="">conteneur…</option>{containers.map((c) => <option key={c.name}>{c.name}</option>)}</select>}
        {target === "dir" && <select value={g.dir || ""} onChange={(e) => setG({ ...g, dir: e.target.value })}><option value="">{cat.compose_dirs.length ? "dossier…" : "aucun dossier autorisé"}</option>{cat.compose_dirs.map((d) => <option key={d}>{d}</option>)}</select>}
        {["journal", "docker_logs"].includes(g.action) && <input type="number" min={10} max={1000} value={g.lines} onChange={(e) => setG({ ...g, lines: e.target.value })} style={{ width: 80 }} title="lignes" />}
        {cat.write.includes(g.action) && <input value={g.reason} onChange={(e) => setG({ ...g, reason: e.target.value })} placeholder="motif (journalisé sur l'hôte)" style={{ minWidth: 240 }} />}
        <button className="primary" onClick={go} disabled={!!busy || !g.action}>{busy ? `⏳ ${busy}` : "Exécuter"}</button>
      </div>
      <p className="infra-muted" style={{ fontSize: 12 }}>Liste fermée : services {cat.units.join(", ")} ; conteneurs {cat.containers.join(", ")} ; piles compose {cat.compose_dirs.join(", ") || "aucune"} (agent.json, clé hostops). Chaque geste est journalisé sur l'hôte (/var/log/si-agent/hostops-audit.log).</p>
      {out?.error && <p className="infra-status critical">{out.error}</p>}
      {out?.output != null && <pre className="infra-scroll" style={{ maxHeight: "45vh", overflow: "auto", fontSize: 12, whiteSpace: "pre-wrap" }}>{out.output}{out.truncated ? "\n… (début tronqué)" : ""}</pre>}
    </div>
  );
}

function HostCard({ base, h, username, onRefresh }) {
  return (
    <section className="infra-card" style={{ marginBottom: 12 }}>
      <div className="infra-top" style={{ margin: 0 }}>
        <h3 style={{ margin: 0 }}>{h.hostname || h.agent_id}</h3>
        <span className={`infra-status ${h.online === "online" ? "" : "critical"}`}>{h.online === "online" ? "en ligne" : "hors ligne"}</span>
        <span className="infra-muted">{h.os || "—"}{h.virtualization && !["none", "null"].includes(String(h.virtualization)) ? ` · VM (${h.virtualization})` : h.hardware_model ? ` · ${h.hardware_model}` : ""} · agent {h.version || "?"} · uptime {fmtUptime(h.uptime_s)}{h.declared ? " · ajouté à la main" : ""}</span>
      </div>
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", margin: "6px 0" }}>
        <span>CPU <Meter p={h.cpu_pct} label={h.cpu_pct == null ? "—" : `${h.cpu_pct} %`} /></span>
        <span>Mémoire <Meter p={h.mem_pct} label={h.mem_total ? `${h.mem_pct} % de ${fmtBytes(h.mem_total)}` : "—"} /></span>
        <span>Disque <Meter p={h.disk_max_pct} label={h.disks?.[0] ? `${h.disks[0].mount} ${h.disk_max_pct} %` : "—"} /></span>
        <span className="infra-muted">charge {h.load1 ?? "—"} / {h.load5 ?? "—"} / {h.load15 ?? "—"}</span>
      </div>
      {h.ollama_data || (h.models || []).length ? <OllamaSection apiBase={base} agentId={h.agent_id} latest={h.ollama_data ? { data: h.ollama_data, at: h.ollama_at } : null} present when={(t) => when(t)} onRefresh={onRefresh} />
        : <p className="infra-muted">Pas de sonde ollama sur cet hôte.</p>}
      {h.containers ? <><h4 style={{ margin: "8px 0 4px" }}>Conteneurs Docker ({h.containers.length})</h4>
        <div className="infra-table-wrap"><table className="infra-table"><thead><tr><th>Nom</th><th>Image</th><th>État</th><th>Statut</th><th>Ports</th></tr></thead>
          <tbody>{h.containers.map((c) => <tr key={c.name}><td><b>{c.name}</b></td><td className="infra-muted">{c.image}</td><td><span className={`infra-dot ${c.state === "running" ? "good" : "critical"}`}>{c.state === "running" ? "●" : "■"}</span> {c.state}</td><td>{c.status}</td><td className="infra-muted">{c.ports}</td></tr>)}</tbody></table></div></>
        : <p className="infra-muted">Conteneurs : sonde docker-containers inactive{h.containers_error ? ` (${h.containers_error})` : ""}.</p>}
      <Gestures base={base} host={h} username={username} />
    </section>
  );
}

export default function IaParkView({ onBack, siAgentApiBase, username }) {
  const base = siAgentApiBase;
  const [tab, setTab] = useState(() => { try { return localStorage.getItem("iapark.tab") || "hotes"; } catch { return "hotes"; } });
  const [ov, setOv] = useState(null), [status, setStatus] = useState(null), [evals, setEvals] = useState(null), [act, setAct] = useState(null), [days, setDays] = useState(30);
  const [fleet, setFleet] = useState(null), [err, setErr] = useState(null);
  const load = () => {
    fetchIaOverview(base).then(setOv).catch((e) => setErr(e.message));
    fetchIaAssistant(base, "status").then(setStatus).catch((e) => setStatus({ error: e.message }));
  };
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [base]);
  useEffect(() => { try { localStorage.setItem("iapark.tab", tab); } catch { /* stockage indisponible */ }
    if (tab === "tests") fetchIaAssistant(base, "eval/summary").then(setEvals).catch((e) => setEvals({ error: e.message }));
    if (tab === "activite") fetchIaAssistant(base, `journal/stats?days=${days}`).then(setAct).catch((e) => setAct({ error: e.message }));
  }, [tab, base, days]);
  const addHost = async (id) => { if (!id) return; const r = await saveIaHosts(base, [...(ov?.declared || []), id]); if (!r?.error) load(); };
  const removeHost = async (id) => { const r = await saveIaHosts(base, (ov?.declared || []).filter((x) => x !== id)); if (!r?.error) load(); };
  const tot = act?.days ? activityTotals(act.days) : null;

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Parc IA</h2>
        <div className="infra-tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
        <span className="infra-muted">Assistant : {status?.error ? <span className="infra-status critical">injoignable</span> : status ? <>{status.model} {status.llm_reachable ? (status.model_available ? "· modèle présent" : <span className="infra-status warning">⚠ modèle absent du serveur</span>) : <span className="infra-status critical">⛔ serveur de modèles injoignable</span>} · index {status.index?.docs ?? "?"} doc(s){status.eval_running ? " · évaluation en cours" : ""}</> : "…"}</span>
      </div>
      <DataStatus base={base} tasks={["plugin:ollama", "plugin:docker-containers", "host"]} error={err || status?.error}
        labels={{ "plugin:ollama": "modèles (sonde ollama)", "plugin:docker-containers": "conteneurs", host: "relevé des hôtes" }}
        extra={status && !status.error ? [{ tone: status.llm_reachable ? (status.model_available ? "good" : "warning") : "critical", text: `assistant : ${status.model} ${status.llm_reachable ? (status.model_available ? "présent" : "absent du serveur de modèles") : "serveur de modèles injoignable"}`, detail: status.base_url }] : []} />

      {tab === "hotes" && ov && <>
        {ov.hosts.length === 0 && <p className="infra-muted">Aucun hôte d'IA : activer la sonde <code>ollama</code> sur l'agent du poste (fiche de l'agent), ou ajouter un hôte ci-dessous.</p>}
        {ov.hosts.map((h) => <HostCard key={h.agent_id} base={base} h={h} username={username} onRefresh={load} />)}
        <div className="infra-card"><b>Hôtes ajoutés à la main</b> <span className="infra-muted">(ex. la VM qui fait tourner l'assistant sous Docker)</span> :{" "}
          {(ov.declared || []).map((id) => <span key={id} className="infra-kpi" style={{ display: "inline-flex", gap: 4, margin: 2 }}>{id}<button className="secondary" onClick={() => removeHost(id)}>✕</button></span>)}
          {fleet ? <select defaultValue="" onChange={(e) => addHost(e.target.value)}><option value="">+ ajouter un agent…</option>{fleet.filter((a) => !(ov.declared || []).includes(a.agent_id)).map((a) => <option key={a.agent_id} value={a.agent_id}>{a.hostname || a.agent_id}</option>)}</select>
            : <button className="secondary" onClick={() => fetchFleet(base).then(setFleet)}>+ ajouter…</button>}</div>
      </>}

      {tab === "tests" && (evals?.error ? <p className="infra-status critical">{evals.error}</p> : !evals ? <p className="infra-muted">lecture…</p> : <>
        <p className="infra-muted">Évaluations de l'assistant (jeu de cas : classements GED, résumés, questions sur la documentation). Le détail cas par cas — ce qui est fourni au modèle, les indicateurs cibles et le rendu — est dans l'assistant, onglet Évaluation (#754).</p>
        <h3>Par modèle</h3>
        <div className="infra-table-wrap"><table className="infra-table"><thead><tr><th>Modèle</th><th>Serveur</th><th>Passages</th><th>Dernier score</th><th>Meilleur</th><th>Critères (dernier)</th><th>Jetons/s (dernier)</th><th>Dernier passage</th></tr></thead>
          <tbody>{byModel(evals.reports).map((m) => <tr key={m.key}><td><b>{m.model}</b></td><td className="infra-muted">{m.base_url}</td><td>{m.runs}</td><td><Score s={m.last.score} /></td><td><Score s={m.best.score} /></td>
            <td>{m.last.criteria ? `${m.last.criteria_ok}/${m.last.criteria}` : "—"}</td><td>{m.last.tok_s_avg ?? "—"}</td><td>{when(m.last.at)}</td></tr>)}</tbody></table></div>
        <h3>Tous les passages</h3>
        <div className="infra-table-wrap infra-scroll"><table className="infra-table"><thead><tr><th>Date</th><th>Modèle</th><th>Cas</th><th>Score</th><th>Par usage</th><th>Critères</th><th>Jetons/s moy. / min</th><th>Durée</th><th>Erreurs</th></tr></thead>
          <tbody>{evals.reports.map((r) => <tr key={r.name}><td>{when(r.at)}</td><td>{r.model}</td><td>{r.cases}</td><td><Score s={r.score} /></td>
            <td className="infra-muted">{Object.entries(r.by_kind || {}).map(([k, v]) => `${k} ${v.score ?? "—"}`).join(" · ")}</td><td>{r.criteria ? `${r.criteria_ok}/${r.criteria}` : "—"}</td>
            <td>{r.tok_s_avg ?? "—"} / {r.tok_s_min ?? "—"}</td><td>{r.total_s != null ? `${r.total_s} s` : "—"}</td><td>{r.errors || 0}</td></tr>)}</tbody></table></div>
      </>)}

      {tab === "activite" && (act?.error ? <p className="infra-status critical">{act.error}</p> : !act ? <p className="infra-muted">lecture…</p> : <>
        <div className="infra-top" style={{ margin: 0 }}><select value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 30, 90].map((d) => <option key={d} value={d}>{d} jours</option>)}</select>
          <span className="infra-muted">{tot.n} appel(s) au modèle · {tot.errors} erreur(s) · temps moyen {tot.ms_avg != null ? `${(tot.ms_avg / 1000).toFixed(1)} s` : "—"} · {tot.tok_s_avg ?? "—"} jetons/s</span></div>
        <div className="infra-table-wrap infra-scroll"><table className="infra-table"><thead><tr><th>Jour</th><th>Appels</th><th>Erreurs</th><th>Temps moyen</th><th>Jetons/s</th><th>Usages</th></tr></thead>
          <tbody>{[...act.days].reverse().map((d) => <tr key={d.day}><td>{new Date(d.day).toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit", month: "2-digit" })}</td>
            <td><span className="infra-meter-wrap"><span className="infra-meter"><span className="fill" style={{ width: `${(100 * d.n) / tot.max}%` }} /></span><em>{d.n}</em></span></td>
            <td>{d.errors ? <span className="infra-status critical">{d.errors}</span> : 0}</td><td>{d.ms_avg != null ? `${(d.ms_avg / 1000).toFixed(1)} s` : "—"}</td><td>{d.tok_s_avg ?? "—"}</td>
            <td className="infra-muted">{Object.entries(d.by_kind).map(([k, v]) => `${k} ${v}`).join(" · ")}</td></tr>)}</tbody></table></div>
      </>)}
    </div>
  );
}
