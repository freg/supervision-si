// « Tour de contrôle » du hub (livraison #586) -- demandé : « il faut qu'on
// puisse tout faire par le hub, même l'import de conf json, et que le hub
// fasse quand il faut les update/reload/build : une tour de contrôle
// automatisée ». Onglets : Services (feu tricolore #584, redémarrer,
// reconstruire), Livraisons & jobs (zip → analyse → plan → application
// automatique ou manuelle, journal des jobs en direct), Configurations
// (registres JSON Cisco / MikroTik : édition, import fusion/remplacement,
// export), Automatismes (auto-réparation, application auto, services non
// surveillés), Journal de la tour.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PageFrame from "./PageFrame.jsx";
import TowerNetworkTab from "./TowerNetworkTab.jsx";
import ServicesView from "./ServicesView.jsx";
import { viewParams } from "./hubLinks.js";
import {
  fetchServices, fetchSettings, saveSettings, fetchEvents, fetchConfigs, fetchConfig, saveConfig,
  fetchJobs, fetchJob, fetchDeliveries, uploadDelivery, applyDelivery, reloadGateway, fetchGit, gitUpdate, fetchRepartition, saveRepartition, applyRepartition, migrateCohort, fetchMirror, mirrorAction } from "./servicesClient.js";
import { itemsOf, mergeItems, emptyRow, cleanRow, statsText, deliveryText, JOB_LABEL, JOB_TONE, touchesHub, gitText, gitBlocker, cohortRows, moveCohort, nodeText, mirrorText, mirrorActions } from "./towerLib.js";

const TABS = [
  { id: "services", label: "🚦 Services" },
  { id: "deliveries", label: "📦 Livraisons & jobs" },
  { id: "configs", label: "🗂 Configurations" },
  { id: "auto", label: "⚙ Automatismes" },
  { id: "journal", label: "📜 Journal" },
  { id: "network", label: "🕸 Réseau" },   // #655 : DNS / routage / flux → trafic (lecture seule)
  { id: "repartition", label: "🗺 Répartition" },   // #662 : nœuds / cohortes (#513), migration d'une cohorte
];
const COLORS = { red: "#e53935", orange: "#fb8c00", green: "#43a047", grey: "#9e9e9e" };
const when = (t) => (t ? new Date(typeof t === "number" ? t * 1000 : t).toLocaleString() : "");

function Tone({ tone, children }) {
  return <span style={{ color: COLORS[tone] || "inherit", fontWeight: 600 }}>{children}</span>;
}

// ---------------------------------------------------------------------------
function JobView({ apiBase, token, jobId, onClose }) {
  const [job, setJob] = useState(null);
  const [lost, setLost] = useState(0);
  const pre = useRef(null);
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      const r = await fetchJob(apiBase, token, jobId);
      if (stop) return;
      if (r.error) setLost((n) => n + 1); else { setLost(0); setJob(r); }
      if (r.error || r.status === "running") setTimeout(tick, 3000);
    };
    tick();
    return () => { stop = true; };
  }, [apiBase, token, jobId]);
  useEffect(() => { if (pre.current) pre.current.scrollTop = pre.current.scrollHeight; }, [job?.log?.length]);
  return (
    <div className="hub-card" style={{ marginTop: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Job {jobId} — {job?.label || "…"}</h3>
        {job && <Tone tone={JOB_TONE[job.status]}>{JOB_LABEL[job.status] || job.status}{job.rc != null ? ` (code ${job.rc})` : ""}</Tone>}
        <span style={{ flex: 1 }} />
        {onClose && <button type="button" className="secondary" onClick={onClose}>Fermer</button>}
      </div>
      {lost > 0 && <p className="muted">tour de contrôle momentanément injoignable (reconstruction en cours ?) — nouvelle tentative…</p>}
      {job?.status === "done" && touchesHub(job) && <p><Tone tone="orange">Le hub ou la passerelle ont été relancés : </Tone><button type="button" onClick={() => window.location.reload()}>recharger la page</button></p>}
      <pre ref={pre} style={{ maxHeight: 360, overflow: "auto", fontSize: 12, margin: "8px 0 0" }}>{(job?.log || []).join("\n") || "…"}</pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// #663 : miroir froid (étape 3) -- le primaire envoie ses sauvegardes totales/incrémentales à l'agent de nœud du miroir
// qui les restaure services arrêtés ; bascule = takeover (regenerate + tout démarrer) + rôle « celui qui répond » ;
// retour = sauvegarde du miroir restaurée ici puis miroir en standby. Tout en jobs (deploy/mirror.py).
const MIRROR_LABELS = { sync: "Synchroniser (incrémental)", "sync-full": "Synchroniser (totale)", failover: "⚠ Basculer vers le miroir", failback: "↶ Revenir sur le primaire", prune: "Purger les anciennes sauvegardes" };
function MirrorCard({ apiBase, token, openJob }) {
  const [m, setM] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const load = useCallback(async () => { const r = await fetchMirror(apiBase, token); if (!r.error) setM(r); else setError(r.error); }, [apiBase, token]);
  useEffect(() => { load(); }, [load]);
  const run = async (a) => {
    const warn = { failover: "BASCULER vers le miroir : il régénère ce qui est propre à son hôte, démarre tout, puis le rôle est basculé. Le primaire n'est PAS arrêté par cette action (le faire si l'incident ne l'a pas déjà fait). Continuer ?",
      failback: "REVENIR sur le primaire : sauvegarde du miroir, arrêt du primaire, restauration par-dessus, redémarrage, miroir en standby. Continuer ?", "sync-full": "Synchronisation totale (longue) : continuer ?" }[a];
    if (warn && !window.confirm(warn)) return;
    setBusy(a); setError(null); const r = await mirrorAction(apiBase, token, a); setBusy("");
    if (r.error) { setError(r.error); return; } if (r.job?.id) openJob(r.job.id);
  };
  return (
    <div className="hub-card" style={{ marginTop: 12 }}>
      <h3 style={{ margin: "0 0 6px" }}>🪞 Miroir froid {m?.configured && <span className={m.rpo_ok ? "muted" : "hub-error"}>{m.rpo_ok ? "— RPO respecté" : "— RPO dépassé"}</span>}</h3>
      <p className="muted" style={{ margin: "0 0 6px" }}>{mirrorText(m)}</p>
      {error && <p className="hub-error">{error}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {mirrorActions(m).map((a) => <button key={a} type="button" className={a === "failover" || a === "failback" ? "secondary" : "primary"} disabled={!!busy} onClick={() => run(a)}>{MIRROR_LABELS[a]}</button>)}
        <button type="button" className="secondary" disabled={!!busy} onClick={load}>↻</button>
      </div>
      {m?.configured && <p className="muted" style={{ margin: "6px 0 0" }}>RPO = intervalle entre deux synchronisations (planifier « sync » : cron sur l'hôte ou tâche de la tour) ; RTO = durée du job de bascule. Rôle basculé : {m.config?.role_id ? `n°${m.config.role_id} (candidats ${m.config.primary_candidate ?? 0} → ${m.config.mirror_candidate ?? 1})` : "aucun (basculer DNS / NAT à la main)"}.</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// #662 : répartition -- nœuds du déploiement réparti (#513 : deploy/nodes.json, agents de nœud sur le VPN), cohortes et leur
// nœud, déplacement (nodes.json réécrit puis « Appliquer » = job repartition.py apply) ou migration avec données
// (job repartition.py migrate : arrêt source, copie, apply partout). Étape 2 des items 108-110.
function Repartition({ apiBase, token, openJob }) {
  const [data, setData] = useState(null);
  const [nodes, setNodes] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");
  const [mig, setMig] = useState({ cohort: "", target: "" });
  const load = useCallback(async () => { const d = await fetchRepartition(apiBase, token); if (d.error) setError(d.error); else { setData(d); setNodes(d.nodes); } }, [apiBase, token]);
  useEffect(() => { load(); }, [load]);
  const dirty = data && JSON.stringify(nodes) !== JSON.stringify(data.nodes);
  const rows = cohortRows({ ...(data || {}), nodes: nodes || [] });
  const save = async () => { setBusy("save"); setError(null); const r = await saveRepartition(apiBase, token, nodes); setBusy(""); if (r.error) { setError(r.error); return; } load(); };
  const apply = async (build) => { if (!window.confirm(`Appliquer nodes.json sur tous les nœuds${build ? " (avec reconstruction)" : ""} ? Chaque agent de nœud lance ses services et relais, arrête ce qui n'est plus à lui.`)) return; setBusy("apply"); const r = await applyRepartition(apiBase, token, { build }); setBusy(""); if (r.error) { setError(r.error); return; } if (r.job?.id) openJob(r.job.id); };
  const migrate = async () => {
    if (!mig.cohort || !mig.target) return;
    if (!window.confirm(`Migrer la cohorte « ${mig.cohort} » vers ${mig.target} AVEC ses données (arrêt sur la source, copie, relance) ? Une sauvegarde totale est conseillée avant.`)) return;
    setBusy("migrate"); setError(null); const r = await migrateCohort(apiBase, token, mig.cohort, mig.target); setBusy(""); if (r.error) { setError(r.error); return; } if (r.job?.id) openJob(r.job.id);
  };
  if (!data && !error) return <p className="muted">chargement…</p>;
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Nœud courant : <strong>{data?.me}</strong>. {data?.configured ? <>Déploiement réparti configuré (<code>deploy/nodes.json</code>, VPN {data.wg_subnet || "?"}).</> : <>Pas de <code>deploy/nodes.json</code> : un seul hôte. Pour répartir : copier <code>deploy/nodes.example.json</code>, poser l'agent de nœud sur chaque hôte (<code>deploy/README.md</code>), puis revenir ici.</>}
        {" "}Les plans de livraison et de mise à jour git ne reconstruisent ici que les services des cohortes de ce nœud.
      </p>
      {error && <p className="hub-error">{error}</p>}
      {data?.configured && (<>
        <h3>Nœuds</h3>
        <table className="hub-table"><thead><tr><th>Nœud</th><th>Zone</th><th>VPN</th><th>Rôle</th><th>Cohortes</th><th>État (agent de nœud)</th></tr></thead>
          <tbody>{(nodes || []).map((n) => <tr key={n.name}><td><b>{n.name}</b>{n.name === data.me ? " (ici)" : ""}</td><td>{n.zone}</td><td><code>{n.wg_address}</code></td><td>{n.role}{n.edge ? " · bordure" : ""}</td><td>{(n.cohorts || []).join(", ") || <span className="muted">—</span>}</td><td className={data.status?.[n.name]?.error || (data.status?.[n.name]?.missing || []).length ? "hub-error" : "muted"}>{nodeText(data.status?.[n.name])}</td></tr>)}</tbody></table>
        <h3>Cohortes → nœud</h3>
        <table className="hub-table"><thead><tr><th>Cohorte</th><th>Services</th><th>Zone</th><th>Nœud</th></tr></thead>
          <tbody>{rows.map((c) => <tr key={c.name}><td><b>{c.name}</b>{c.manager ? " · manager" : ""}{c.isolated ? " · isolée" : ""}<div className="muted">{c.title}</div></td><td title={c.services.join(", ")}>{c.count}</td><td>{c.zone || "local"}</td>
            <td><select value={c.node} disabled={!!c.manager} onChange={(e) => setNodes(moveCohort(nodes, c.name, e.target.value))}><option value="">— non affectée —</option>{(nodes || []).map((n) => <option key={n.name} value={n.name}>{n.name}</option>)}</select></td></tr>)}</tbody></table>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
          <button type="button" className="primary" disabled={!dirty || !!busy} onClick={save}>Enregistrer nodes.json</button>
          <button type="button" className="secondary" disabled={dirty || !!busy} onClick={() => apply(false)}>Appliquer partout</button>
          <button type="button" className="secondary" disabled={dirty || !!busy} onClick={() => apply(true)}>Appliquer + reconstruire</button>
          {dirty && <span className="muted">affectation modifiée, non enregistrée (un simple changement d'affectation ne déplace PAS les données : utiliser la migration ci-dessous)</span>}
        </div>
        <h3>Migrer une cohorte avec ses données</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <select value={mig.cohort} onChange={(e) => setMig({ ...mig, cohort: e.target.value })}><option value="">cohorte…</option>{rows.filter((c) => !c.manager).map((c) => <option key={c.name} value={c.name}>{c.name} ({c.node || "non affectée"})</option>)}</select>
          <span className="muted">→</span>
          <select value={mig.target} onChange={(e) => setMig({ ...mig, target: e.target.value })}><option value="">nœud cible…</option>{(nodes || []).filter((n) => n.name !== rows.find((c) => c.name === mig.cohort)?.node).map((n) => <option key={n.name} value={n.name}>{n.name} ({n.zone})</option>)}</select>
          <button type="button" className="secondary" disabled={!mig.cohort || !mig.target || !!busy} onClick={migrate}>Migrer (job)</button>
        </div>
      </>)}
      <MirrorCard apiBase={apiBase} token={token} openJob={openJob} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// #659 : mise à jour depuis le dépôt git (GitHub) -- un bouton pour le central (plan ciblé sur les fichiers changés),
// un pour l'ensemble en cascade (tous les services en marche + passerelle + autres nœuds + agents hôtes).
function GitUpdate({ apiBase, token, openJob }) {
  const [g, setG] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [agents, setAgents] = useState(true);
  const [startNew, setStartNew] = useState({});       // #666 : nouveaux services (jamais démarrés) à lancer avec la mise à jour
  const [last, setLast] = useState(null);
  const refresh = useCallback(async (fetch = true) => { setBusy("fetch"); const r = await fetchGit(apiBase, token, fetch); setBusy(""); setG(r); }, [apiBase, token]);
  useEffect(() => { refresh(false); }, [refresh]);
  const launch = async (mode) => {
    const what = mode === "cascade" ? `TOUT mettre à jour en cascade (git pull, reconstruction de ${(g?.running || []).length} service(s) en marche + passerelle${g?.nodes > 1 ? ` + ${g.nodes - 1} autre(s) nœud(s)` : ""}${agents ? " + agents hôtes" : ""}) ?` : `Mettre à jour le central (git pull puis ${(g?.plan?.steps || []).length} étape(s) ciblée(s)) ?`;
    if (!window.confirm(what + " Le hub et la tour seront momentanément indisponibles.")) return;
    setBusy(mode); setError(null);
    const r = await gitUpdate(apiBase, token, { mode, agents: mode === "cascade" && agents, force: false, start_new: Object.keys(startNew).filter((k) => startNew[k]) });
    setBusy("");
    if (r.error) { setError(r.error); return; }
    setLast(r); if (r.job?.id) openJob(r.job.id);
  };
  const blocker = gitBlocker(g);
  return (
    <div className="hub-card" style={{ marginBottom: 12 }}>
      <h3 style={{ margin: "0 0 6px" }}>⬇️ Mise à jour depuis le git {g?.remote && <code className="muted">{g.remote}</code>}</h3>
      <p className="muted" style={{ margin: "0 0 6px" }}>{busy === "fetch" ? "interrogation du dépôt…" : gitText(g)}{g && !g.fetched && !g.error && <> — <a href="#git" onClick={(e) => { e.preventDefault(); refresh(true); }}>vérifier sur origin</a></>}</p>
      {blocker && <p className="hub-error" style={{ margin: "0 0 6px" }}>{blocker}</p>}
      {(g?.incoming || []).length > 0 && <details style={{ marginBottom: 6 }}><summary className="muted">{g.incoming.length} commit(s) entrant(s)</summary><ul style={{ margin: "4px 0", fontSize: 12 }}>{g.incoming.map((c) => <li key={c.hash}><code>{c.hash}</code> {c.subject}</li>)}</ul></details>}
      {(g?.plan?.steps || []).length > 0 && <details style={{ marginBottom: 6 }}><summary className="muted">plan ciblé du central : {g.plan.steps.length} étape(s){(g.plan.not_running || []).length ? ` (non démarrés ici : ${g.plan.not_running.join(", ")})` : ""}</summary><ol style={{ margin: "4px 0", fontSize: 12 }}>{g.plan.steps.map((s, i) => <li key={i}>{s.label} — <code>{s.cmd}</code></li>)}</ol></details>}
      {(g?.new_services || []).length > 0 && <p className="muted" style={{ margin: "0 0 6px" }}>Nouveaux services dans ces commits, jamais démarrés ici — à lancer avec la mise à jour : {g.new_services.map((s) => <label key={s} style={{ marginRight: 10 }}><input type="checkbox" checked={!!startNew[s]} onChange={(e) => setStartNew({ ...startNew, [s]: e.target.checked })} /> <code>{s}</code></label>)}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="primary" disabled={!!busy || !!blocker || !g?.behind} onClick={() => launch("central")}>⬆️ Mettre à jour le central</button>
        <button type="button" className="secondary" disabled={!!busy || !!blocker} onClick={() => launch("cascade")}>⛓️ Tout mettre à jour en cascade</button>
        <label className="muted"><input type="checkbox" checked={agents} onChange={(e) => setAgents(e.target.checked)} /> agents hôtes aussi (commande <code>update</code> aux agents éligibles, réglages de la tuile Agents hôtes)</label>
        <button type="button" className="secondary" disabled={!!busy} onClick={() => refresh(true)}>↻</button>
      </div>
      {error && <p className="hub-error">{error}</p>}
      {last?.job && <p className="muted">job <a href="#job" onClick={(e) => { e.preventDefault(); openJob(last.job.id); }}>{last.job.id}</a> lancé : {last.steps.length} étape(s). La tour sera injoignable pendant sa propre reconstruction ; le journal reprend ensuite.</p>}
    </div>
  );
}

function Deliveries({ apiBase, token, settings, openJob, jobId }) {
  const [state, setState] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [progress, setProgress] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [d, j] = await Promise.all([fetchDeliveries(apiBase, token), fetchJobs(apiBase, token)]);
    if (!d.error) setState(d);
    if (!j.error) setJobs(j.jobs || []);
  }, [apiBase, token]);
  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id); }, [load]);

  const apply = async (a, allowDowngrade = false) => {
    setBusy(true);
    const r = await applyDelivery(apiBase, token, a.id, allowDowngrade);
    setBusy(false);
    if (r.error) { setError(r.error); return; }
    setAnalysis(r);
    if (r.job) openJob(r.job);
    load();
  };
  const onFile = async (file) => {
    if (!file) return;
    setError(null); setAnalysis(null); setProgress(0);
    const r = await uploadDelivery(apiBase, token, file, setProgress);
    setProgress(null);
    if (r.error) { setError(r.error); return; }
    setAnalysis(r);
    if (settings?.auto_apply && !r.downgrade && !(r.unsafe || []).length) apply(r);
  };
  const a = analysis;
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Version en place : <strong>#{state?.current || "?"}</strong> — dépôt <code>{state?.project_dir || "?"}</code>.
        Déposer le zip d'une livraison : la tour compare chaque fichier, n'écrase jamais <code>.env</code> ni les registres locaux
        (<code>*.local.json</code>), conserve les données locales modifiées, puis calcule le plan : reconstruire les services
        dont une source a changé (COPY de leur Dockerfile), redémarrer ceux dont un fichier monté a changé, appliquer
        <code> docker-compose.yml</code>, recharger la passerelle — <em>seulement parmi les services en marche</em>.
        {settings?.auto_apply ? " Application automatique : activée (onglet Automatismes)." : " Application automatique : désactivée — bouton « Appliquer »."}
      </p>
      <GitUpdate apiBase={apiBase} token={token} openJob={openJob} />
      <label className="primary" style={{ display: "inline-block", padding: "6px 12px", cursor: "pointer" }}>
        📦 Déposer une livraison (.zip)
        <input type="file" accept=".zip" style={{ display: "none" }} onChange={(e) => onFile(e.target.files?.[0])} />
      </label>
      {progress != null && <span className="muted"> envoi {Math.round(progress * 100)} % {progress >= 1 ? "— analyse…" : ""}</span>}
      {error && <p className="hub-error">{error}</p>}
      {a && (
        <div className="hub-card" style={{ marginTop: 12 }}>
          <h3 style={{ margin: 0 }}>{a.name} — {deliveryText(a)}</h3>
          {a.downgrade && <p><Tone tone="orange">Livraison plus ancienne que la version en place.</Tone></p>}
          {(a.unsafe || []).length > 0 && <p><Tone tone="red">{a.unsafe.length} entrée(s) dangereuse(s) ignorée(s)</Tone> : {a.unsafe.slice(0, 5).join(", ")}</p>}
          {(a.protected || []).length > 0 && <p className="muted">Protégés (jamais écrasés) : {a.protected.join(", ")}</p>}
          {(a.kept || []).length > 0 && <p className="muted">Données locales conservées : {a.kept.join(", ")}</p>}
          <h4 style={{ margin: "8px 0 4px" }}>Plan</h4>
          {a.plan?.error && <p className="hub-error">{a.plan.error}</p>}
          {(a.plan?.steps || []).length ? <ol style={{ margin: 0 }}>{a.plan.steps.map((s, i) => <li key={i}>{s.label} — <code>{s.cmd}</code></li>)}</ol> : <p className="muted">rien à reconstruire ni redémarrer (documentation, données…).</p>}
          {(a.plan?.not_running || []).length > 0 && <p className="muted">Modifiés mais non démarrés ici (laissés tels quels) : {a.plan.not_running.join(", ")}</p>}
          <details><summary className="muted">{(a.changed || []).length + (a.added || []).length} fichier(s) à écrire</summary><pre style={{ maxHeight: 200, overflow: "auto", fontSize: 12 }}>{[...(a.changed || []).map((f) => "M " + f), ...(a.added || []).map((f) => "A " + f)].join("\n")}</pre></details>
          {a.applied ? <p><Tone tone="green">Appliquée</Tone> ({a.written} fichier(s) écrit(s)){a.job ? <> — job <a href="#job" onClick={(e) => { e.preventDefault(); openJob(a.job); }}>{a.job}</a></> : " — aucun job nécessaire"}</p>
            : <button type="button" className="primary" disabled={busy} onClick={() => (!a.downgrade || window.confirm("Revenir à une livraison plus ancienne ?")) && apply(a, a.downgrade)}>{busy ? "Application…" : "Appliquer la livraison"}</button>}
        </div>
      )}
      {jobId && <JobView apiBase={apiBase} token={token} jobId={jobId} onClose={() => openJob(null)} />}
      <h3>Jobs récents</h3>
      <table className="hub-table">
        <thead><tr><th>Job</th><th>Quoi</th><th>Par</th><th>Quand</th><th>État</th></tr></thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} style={{ cursor: "pointer" }} onClick={() => openJob(j.id)}>
              <td><code>{j.id}</code></td><td>{j.label}</td><td>{j.user}</td><td className="muted">{when(j.at)}</td>
              <td><Tone tone={JOB_TONE[j.status]}>{JOB_LABEL[j.status] || j.status}</Tone></td>
            </tr>
          ))}
          {!jobs.length && <tr><td colSpan={5} className="muted">aucun job</td></tr>}
        </tbody>
      </table>
      <h3>Livraisons reçues</h3>
      <table className="hub-table">
        <thead><tr><th>Reçue</th><th>Fichier</th><th>Contenu</th><th>État</th></tr></thead>
        <tbody>
          {(state?.deliveries || []).map((d) => (
            <tr key={d.id} style={{ cursor: "pointer" }} onClick={() => setAnalysis(d)}>
              <td className="muted">{when(d.at)}</td><td>{d.name}</td><td>{deliveryText(d)}</td>
              <td>{d.applied ? <Tone tone="green">appliquée</Tone> : <Tone tone="orange">en attente</Tone>}</td>
            </tr>
          ))}
          {!(state?.deliveries || []).length && <tr><td colSpan={4} className="muted">aucune</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Configs({ apiBase, token, initial }) {
  const [list, setList] = useState([]);
  const [cid, setCid] = useState(initial || "cisco");
  const [doc, setDoc] = useState(null);
  const [items, setItems] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [msg, setMsg] = useState(null);
  const [errs, setErrs] = useState([]);
  const [mode, setMode] = useState("merge");
  useEffect(() => { fetchConfigs(apiBase, token).then((r) => !r.error && setList(r.configs || [])); }, [apiBase, token]);
  const spec = useMemo(() => list.find((c) => c.id === cid), [list, cid]);
  const load = useCallback(async () => {
    const r = await fetchConfig(apiBase, token, cid);
    if (r.error) { setMsg(r.error); return; }
    setDoc(r); setItems(r.items || []); setDirty(false); setErrs([]); setMsg(null);
  }, [apiBase, token, cid]);
  useEffect(() => { load(); }, [load]);
  const fields = spec?.fields || [];
  const edit = (i, name, v) => { setItems((xs) => xs.map((x, j) => (j === i ? { ...x, [name]: v } : x))); setDirty(true); };
  const save = async () => {
    const clean = items.map((r) => cleanRow(r, fields));
    const r = await saveConfig(apiBase, token, cid, clean);
    if (r.error) { setErrs(r.errors?.length ? r.errors : [r.error]); setMsg(null); return; }
    setErrs([]); setMsg(`Enregistré : ${r.count} entrée(s) dans ${r.path}${r.warnings?.length ? ` — ${r.warnings.join(" ; ")}` : ""}. Pris en compte immédiatement par ${spec?.consumer || "le module"}.`);
    load();
  };
  const onImport = async (file) => {
    if (!file) return;
    try {
      const incoming = itemsOf(JSON.parse(await file.text()), spec.key);
      const r = mergeItems(items, incoming, "name", mode);
      setItems(r.items); setDirty(true);
      setMsg(`Import de ${file.name} (${mode === "merge" ? "fusion par nom" : "remplacement"}) : ${statsText(r.stats)} — vérifier puis « Enregistrer ».`);
    } catch (e) { setErrs([`import : ${e.message}`]); }
  };
  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ [spec.key]: items.map((r) => cleanRow(r, fields)) }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${cid}-${new Date().toISOString().slice(0, 10)}.json`; a.click();
  };
  return (
    <div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        {list.map((c) => <button key={c.id} type="button" className={`secondary na-section-toggle${c.id === cid ? " active" : ""}`} onClick={() => (!dirty || window.confirm("Modifications non enregistrées : abandonner ?")) && setCid(c.id)}>{c.label}</button>)}
      </div>
      {spec && (
        <p className="muted" style={{ marginTop: 0 }}>
          Fichier <code>{spec.path}</code> (hors dépôt, jamais écrasé par une livraison) — {doc?.source === "exemple" ? <Tone tone="orange">pas encore créé : l'exemple du dépôt est affiché, « Enregistrer » crée le fichier local</Tone> : "fichier local en place"}.
          Les identifiants restent dans le coffre des accès (<a href="/credentials/" target="_top">ouvrir le coffre</a>) : ici seulement le <em>nom</em> de l'accès.
        </p>
      )}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        <button type="button" className="secondary" onClick={() => { setItems((xs) => [...xs, emptyRow(fields)]); setDirty(true); }}>＋ Ajouter</button>
        <label className="secondary" style={{ cursor: "pointer", padding: "4px 10px", border: "1px solid var(--border)", borderRadius: 6 }}>⬆ Importer JSON
          <input type="file" accept=".json,application/json" style={{ display: "none" }} onChange={(e) => { onImport(e.target.files?.[0]); e.target.value = ""; }} />
        </label>
        <select value={mode} onChange={(e) => setMode(e.target.value)}><option value="merge">fusion par nom</option><option value="replace">remplacer tout</option></select>
        <button type="button" className="secondary" onClick={exportJson}>⬇ Exporter JSON</button>
        <span style={{ flex: 1 }} />
        {dirty && <Tone tone="orange">modifié</Tone>}
        <button type="button" className="secondary" disabled={!dirty} onClick={load}>Annuler</button>
        <button type="button" className="primary" disabled={!dirty} onClick={save}>Enregistrer</button>
      </div>
      {msg && <p><Tone tone="green">{msg}</Tone></p>}
      {errs.length > 0 && <div className="hub-error">{errs.map((e, i) => <div key={i}>{e}</div>)}</div>}
      <table className="hub-table">
        <thead><tr>{fields.map((f) => <th key={f.name}>{f.label}{f.required ? " *" : ""}</th>)}<th></th></tr></thead>
        <tbody>
          {items.map((r, i) => (
            <tr key={i}>
              {fields.map((f) => (
                <td key={f.name}>
                  {f.type === "choice"
                    ? <select value={r[f.name] ?? f.default ?? ""} onChange={(e) => edit(i, f.name, e.target.value)}>{f.choices.map((c) => <option key={c} value={c}>{c}</option>)}</select>
                    : <input value={r[f.name] ?? ""} placeholder={f.default != null ? String(f.default) : ""} onChange={(e) => edit(i, f.name, e.target.value)} style={{ width: f.type === "int" ? 70 : f.name === "description" ? 220 : 140 }} />}
                </td>
              ))}
              <td><button type="button" className="secondary" title="retirer" onClick={() => { setItems((xs) => xs.filter((_, j) => j !== i)); setDirty(true); }}>✕</button></td>
            </tr>
          ))}
          {!items.length && <tr><td colSpan={fields.length + 1} className="muted">aucune entrée — « Ajouter » ou « Importer JSON »</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Automations({ apiBase, token, settings, onSaved }) {
  const [s, setS] = useState(settings);
  const [services, setServices] = useState([]);
  const [msg, setMsg] = useState(null);
  useEffect(() => setS(settings), [settings]);
  useEffect(() => { fetchServices(apiBase, token).then((r) => !r.error && setServices((r.services || []).map((x) => x.service).sort())); }, [apiBase, token]);
  if (!s) return <p className="muted">Chargement…</p>;
  const ignored = new Set(s.ignored || []);
  const save = async () => {
    const r = await saveSettings(apiBase, token, s);
    setMsg(r.error ? `Erreur : ${r.error}` : "Réglages enregistrés.");
    if (!r.error) onSaved(r);
  };
  return (
    <div>
      <div className="hub-card">
        <h3 style={{ marginTop: 0 }}>Auto-réparation</h3>
        <label><input type="checkbox" checked={!!s.auto_heal} onChange={(e) => setS({ ...s, auto_heal: e.target.checked })} /> relancer automatiquement un service rouge</label>
        <p className="muted">Après <input type="number" min={1} max={30} value={s.heal_threshold} onChange={(e) => setS({ ...s, heal_threshold: Number(e.target.value) })} style={{ width: 50 }} /> vérifications rouges de suite (une par minute),
          au plus <input type="number" min={0} max={20} value={s.heal_max_per_hour} onChange={(e) => setS({ ...s, heal_max_per_hour: Number(e.target.value) })} style={{ width: 50 }} /> fois par heure et par service ;
          au-delà, abandon signalé dans le journal (intervention requise). Jamais la passerelle, Keycloak, le hub ni la tour elle-même.</p>
      </div>
      <div className="hub-card">
        <h3 style={{ marginTop: 0 }}>Livraisons</h3>
        <label><input type="checkbox" checked={!!s.auto_apply} onChange={(e) => setS({ ...s, auto_apply: e.target.checked })} /> appliquer automatiquement une livraison déposée (écriture des fichiers + plan de reconstruction)</label>
        <p className="muted">Jamais pour une livraison plus ancienne ni une archive contenant des chemins dangereux : confirmation demandée.</p>
      </div>
      <div className="hub-card">
        <h3 style={{ marginTop: 0 }}>Services non surveillés</h3>
        <p className="muted">Cochés : lampe grise, jamais relancés automatiquement (service arrêté volontairement, profil allégé…).</p>
        <div style={{ columns: 3, maxHeight: 260, overflow: "auto" }}>
          {services.map((x) => (
            <label key={x} style={{ display: "block" }}><input type="checkbox" checked={ignored.has(x)} onChange={(e) => {
              const n = new Set(ignored); if (e.target.checked) n.add(x); else n.delete(x); setS({ ...s, ignored: [...n].sort() });
            }} /> {x}</label>
          ))}
        </div>
      </div>
      <button type="button" className="primary" onClick={save}>Enregistrer les réglages</button> {msg && <span className="muted">{msg}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
function Journal({ apiBase, token }) {
  const [ev, setEv] = useState([]);
  useEffect(() => { const f = () => fetchEvents(apiBase, token, 300).then((r) => !r.error && setEv(r.events || [])); f(); const id = setInterval(f, 15000); return () => clearInterval(id); }, [apiBase, token]);
  const tone = (e) => (/gave-up|failed|error/.test(e) ? "red" : /heal|job|delivery/.test(e) ? "orange" : "grey");
  return (
    <table className="hub-table">
      <thead><tr><th>Quand</th><th>Événement</th><th>Détail</th></tr></thead>
      <tbody>
        {ev.map((e, i) => <tr key={i}><td className="muted" style={{ whiteSpace: "nowrap" }}>{when(e.at)}</td><td><Tone tone={tone(e.event)}>{e.event}</Tone></td><td>{e.text}</td></tr>)}
        {!ev.length && <tr><td colSpan={3} className="muted">journal vide</td></tr>}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
export default function ControlTowerView({ apiBase, accessToken, username, onBack, network = {} }) {
  const params = useMemo(() => viewParams(), []);
  const [tab, setTab] = useState(TABS.some((t) => t.id === params.tab) ? params.tab : "services");
  const [settings, setSettings] = useState(null);
  const [jobId, setJobId] = useState(params.job || null);
  const [notice, setNotice] = useState(null);
  useEffect(() => { if (apiBase && accessToken) fetchSettings(apiBase, accessToken).then((r) => !r.error && setSettings(r)); }, [apiBase, accessToken]);
  const openJob = (j) => { setJobId(j ? (typeof j === "string" ? j : j.id) : null); if (j) setTab("deliveries"); };
  if (!apiBase) return <PageFrame title="🗼 Tour de contrôle" onBack={onBack}><p className="muted">services-api non configurée (<code>VITE_SERVICES_API_BASE_URL</code>).</p></PageFrame>;
  const actions = (
    <>
      {TABS.map((t) => <button key={t.id} type="button" className={`secondary na-section-toggle${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>{t.label}</button>)}
      <button type="button" className="secondary" title="re-générer la configuration de la passerelle et relancer tls-proxy (nouvelles routes /api/…)"
        onClick={async () => { if (!window.confirm("Recharger la passerelle ? La page sera coupée quelques secondes.")) return; const r = await reloadGateway(apiBase, accessToken); if (r.error) setNotice(r.error); else openJob(r); }}>↻ Passerelle</button>
    </>
  );
  return (
    <PageFrame title="🗼 Tour de contrôle" onBack={onBack} actions={actions}
      foot={<span>Automatismes : auto-réparation {settings?.auto_heal ? "active" : "coupée"} · application auto des livraisons {settings?.auto_apply ? "active" : "coupée"} · connecté en tant que {username || "?"}{notice ? ` · ${notice}` : ""}</span>}>
      {tab === "services" && <ServicesView embedded apiBase={apiBase} accessToken={accessToken} username={username} onJob={openJob} />}
      {tab === "deliveries" && <Deliveries apiBase={apiBase} token={accessToken} settings={settings} openJob={openJob} jobId={jobId} />}
      {tab === "configs" && <Configs apiBase={apiBase} token={accessToken} initial={params.config} />}
      {tab === "auto" && <Automations apiBase={apiBase} token={accessToken} settings={settings} onSaved={setSettings} />}
      {tab === "journal" && <Journal apiBase={apiBase} token={accessToken} />}
      {tab === "repartition" && <Repartition apiBase={apiBase} token={accessToken} openJob={openJob} />}
      {tab === "network" && <TowerNetworkTab serviceWatchUrl={network.serviceWatchUrl} siAgentApiBase={network.siAgentApiBase} mikrotikApiBase={network.mikrotikApiBase} networkAgentApiBase={network.networkAgentApiBase} dnsApiBase={network.dnsApiBase} ciscoApiBase={network.ciscoApiBase} login={username} />}
    </PageFrame>
  );
}
