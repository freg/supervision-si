// Tuile « Migration 2026-2027 » (livraison #774) : suivi et pilotage pas à pas du plan de migration des Proxmox OVH.
// Plan pré-paramétré importé en JSON (hors dépôt : il contient les vrais noms), paramètres modifiables, barre de
// pilotage (Démarrer, Pause, Reprendre, Arrêter, Étape suivante, Auto / Manuel), étape en cours en grand (avancement,
// débit, fin estimée, fin du journal), chaque erreur détaillée avec sa cause et un bouton « Solution » (relance avec
// reprise, ou commande exacte à lancer et où). Données : si-agent-api /migration (sonde « migration » des agents).
// Logique pure : migrationLib.js.
import { useCallback, useEffect, useMemo, useState } from "react";
import MigrationPrepView from "./MigrationPrepView.jsx";
import MigrationCopiesView from "./MigrationCopiesView.jsx";   // #856
import MigrationRisquesView from "./MigrationRisquesView.jsx";   // #856
import EtatDesLieuxView from "./EtatDesLieuxView.jsx";   // #857   // #815
import { viewParams } from "./hubLinks.js";
import { fetchMigration, saveMigrationPlan, saveMigrationVars, migrationControl } from "./siAgentClient.js";
import {
  allSteps, focusStep, progress, phaseProgress, controls, stepActions, ACTION_LABEL, parsePlan, fmtBytes, fmtProgress, fmtRate, fmtDuration, elapsed,
  solutionCommand, missingVars, statusLabel, statusTone, RUN_LABEL, KIND_LABEL, tabsOf, tabView,
} from "./migrationLib.js";

import { etatMemorise, memoriserEtat } from "./navContext.js";   // #874
// #784 : étape à la main -- commande exacte et machine où la lancer
function HandCmd({ s }) {
  if (!s.cmd) return s.where ? <p>À faire sur <b>{s.where}</b>.</p> : null;
  return <div><p>À lancer sur <b>{s.where || "l'hôte indiqué"}</b> :</p><pre className="mig-cmd">{s.cmd}</pre><Copy text={s.cmd} /></div>;
}

function Bar({ pct, tone }) {
  return <div className="mig-bar" role="progressbar" aria-valuenow={pct ?? 0} aria-valuemin={0} aria-valuemax={100}><div className={`mig-bar-fill ${tone || ""}`} style={{ width: `${Math.max(0, Math.min(100, pct ?? 0))}%` }} /></div>;
}

function Copy({ text }) {
  const [ok, setOk] = useState(false);
  return <button className="secondary" onClick={() => { navigator.clipboard?.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); }); }}>{ok ? "copié ✓" : "Copier"}</button>;
}

function ErrorCard({ s, act, busy }) {
  const e = s.error;
  const [show, setShow] = useState(false);
  if (!e) return null;
  const cmd = solutionCommand(e);
  return (
    <div className="mig-error">
      <b>⚠ {e.title}</b>{e.rc != null && <span className="infra-muted"> · code de sortie {e.rc}</span>}
      <p>{e.detail}</p>
      {e.log && <pre className="mig-log">{e.log}</pre>}
      {e.solution && (
        <div className="mig-solution">
          {e.solution.kind === "retry" && <button disabled={busy} onClick={() => act("retry", s.id)}>Solution : {e.solution.label}</button>}
          {e.solution.kind === "command" && (show
            ? <div><p>Solution : {e.solution.label}. À lancer sur <b>{e.solution.where || "l'hôte"}</b> :</p><pre className="mig-cmd">{cmd}</pre>
                <Copy text={cmd} /> <button disabled={busy} onClick={() => act("retry", s.id)}>C'est fait : relancer l'étape</button></div>
            : <button onClick={() => setShow(true)}>Solution : {e.solution.label}</button>)}
          {e.solution.kind === "none" && <p>Solution : {e.solution.label}</p>}
        </div>
      )}
    </div>
  );
}

function Focus({ s, now, act, busy }) {
  if (!s) return <div className="infra-card mig-focus"><b>Rien à faire</b> : toutes les étapes sont faites.</div>;
  const r = s.report || {};
  const el = elapsed(s, now);
  return (
    <div className={`infra-card mig-focus ${statusTone(s.status)}`}>
      <div className="mig-focus-head">
        <span className="infra-muted">{s.phaseTitle} · étape <code>{s.id}</code> · {KIND_LABEL[s.kind] || s.kind}{s.agent && <> · sur <b>{s.agent}</b></>}</span>
        <span className={`infra-status ${statusTone(s.status)}`}>{s.next && s.status === "a_faire" ? "prochaine" : statusLabel(s.status)}</span>
      </div>
      <h3>{s.title}</h3>
      {s.why && <p>{s.why}</p>}
      {s.check && <p className="infra-note">Contrôle attendu : {s.check}</p>}
      {s.kind === "manual" && <HandCmd s={s} />}
      {(s.missing_vars || []).length > 0 && <p className="infra-error">Paramètre(s) à renseigner avant : {s.missing_vars.join(", ")}</p>}
      {["en_cours", "en_pause", "lance"].includes(s.status) && (
        <>
          {r.pct != null && <Bar pct={r.pct} tone="warning" />}
          <div className="infra-kpis">
            {r.total ? <div className="infra-kpi"><span>restant</span><b>{fmtBytes(Math.max(0, r.total - (r.size || 0)))}</b><small>{r.pct} % fait</small></div> : null}
            <div className="infra-kpi"><span>transféré</span><b>{r.scope === "volume" ? "≈ " : ""}{fmtBytes(r.size)}</b>{r.total ? <small>sur {fmtBytes(r.total)}</small> : <small>total de la source inconnu</small>}</div>
            <div className="infra-kpi"><span>débit</span><b>{fmtRate(r.rate_bps)}</b></div>
            <div className="infra-kpi"><span>fin estimée</span><b>{r.eta_s != null ? fmtDuration(r.eta_s) : "—"}</b>{r.eta_s != null && <small>vers {new Date(now + r.eta_s * 1000).toLocaleString("fr-FR", { weekday: "short", hour: "2-digit", minute: "2-digit" })}</small>}</div>
            <div className="infra-kpi"><span>depuis</span><b>{fmtDuration(el)}</b>{s.attempts > 1 && <small>essai {s.attempts}</small>}</div>
          </div>
        </>
      )}
      {s.status === "fait" && <p>Réussie en {fmtDuration(el)}.</p>}
      {s.status === "manuel" && <p><b>À faire à la main</b>, puis cliquer « Fait ». <button disabled={busy} onClick={() => act("done", s.id)}>Fait</button></p>}
      <ErrorCard s={s} act={act} busy={busy} />
      {!s.error && (r.log_tail || []).length > 0 && <details open={s.status === "en_cours"}><summary>fin du journal</summary><pre className="mig-log">{r.log_tail.join("\n")}</pre></details>}
    </div>
  );
}

function StepRow({ s, act, busy, open, onOpen }) {
  const r = s.report || {};
  return (
    <>
      <tr className={`${s.next ? "mig-next" : ""} ${open ? "gu-sel" : ""}`} onClick={onOpen}>
        <td><code>{s.id}</code></td>
        <td>{s.title}{s.error && <small className="mig-err-inline">⚠ {s.error.title}</small>}</td>
        <td className="infra-muted">{s.agent || "—"}</td>
        <td><span className={`infra-status ${statusTone(s.status)}`}>{statusLabel(s.status)}</span>{s.next && s.status === "a_faire" && <small className="infra-muted"> ← prochaine</small>}</td>
        <td title="restant / transféré / total">{fmtProgress(r)}{r.pct != null ? ` · ${r.pct} %` : ""}{r.rate_bps ? ` · ${fmtRate(r.rate_bps)}` : ""}</td>
        <td onClick={(e) => e.stopPropagation()}>{stepActions(s).map((a) => <button key={a} className="secondary mig-small" disabled={busy} onClick={() => act(a, s.id)}>{ACTION_LABEL[a]}</button>)}</td>
      </tr>
      {open && <tr><td colSpan={6}>
        {s.why && <p>{s.why}</p>}
        {s.check && <p className="infra-note">Contrôle attendu : {s.check}</p>}
        {s.kind === "manual" ? <HandCmd s={s} /> : <pre className="mig-log">{JSON.stringify(s.params, null, 1)}</pre>}
        <ErrorCard s={s} act={act} busy={busy} />
        {!s.error && (r.log_tail || []).length > 0 && <pre className="mig-log">{r.log_tail.join("\n")}</pre>}
      </td></tr>}
    </>
  );
}

function PlanImport({ onSave, busy }) {
  const [text, setText] = useState("");
  const [err, setErr] = useState(null);
  const [ok, setOk] = useState(null);
  const file = (e) => { const f = e.target.files?.[0]; if (f) f.text().then(setText); };
  const go = async () => {
    const { plan, error } = parsePlan(text);
    if (error) { setErr(error); return; }
    const r = await onSave(plan);
    setErr(r?.error || null);
    setOk(r?.error ? null : (r?.message || "plan importé"));
    if (!r?.error) setText("");
  };
  return (
    <details className="infra-card"><summary>Importer / remplacer le plan (JSON)</summary>
      <p className="infra-note">Le plan réel (adresses, noms) reste hors dépôt : fichier <code>migration-2026.local.json</code>. L'état des étapes déjà faites et les paramètres saisis sont gardés.</p>
      <input type="file" accept=".json,application/json" onChange={file} />
      <textarea className="mig-plan" rows={8} value={text} onChange={(e) => setText(e.target.value)} placeholder='{"name": "...", "vars": {...}, "phases": [...]}' />
      <button disabled={busy || !text.trim()} onClick={go}>{busy ? "Import en cours…" : "Importer"}</button>{err && <span className="infra-error"> {err}</span>}{ok && <span className="infra-muted"> ✓ {ok}</span>}
    </details>
  );
}

function Vars({ vars, need, onSave, busy }) {
  const [form, setForm] = useState(vars || {});
  useEffect(() => setForm(vars || {}), [JSON.stringify(vars)]);   // eslint-disable-line react-hooks/exhaustive-deps
  const keys = Object.keys(vars || {}).sort();
  if (!keys.length) return null;
  return (
    <details className="infra-card" open={need.length > 0}><summary>Paramètres du plan{need.length > 0 && <span className="infra-error"> · à renseigner : {need.join(", ")}</span>}</summary>
      <div className="mig-vars">{keys.map((k) => <label key={k}><span>{k}</span><input value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className={need.includes(k) ? "mig-need" : ""} /></label>)}</div>
      <button disabled={busy} onClick={() => onSave(form)}>Enregistrer</button>
    </details>
  );
}

export default function MigrationView({ onBack, siAgentApiBase, username }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const [at, setAt] = useState(null);
  const [busy, setBusy] = useState(false);
  const [openStep, setOpenStep] = useState(null);
  const [tab, setTab] = useState(() => viewParams().onglet || "");   // #784 : onglet (Migration, MX…) ; #790 : ?onglet=MX
  const [page, setPage] = useState(() => { const p = viewParams().page || etatMemorise("MigrationView", "page"); return ["prep", "copies", "risques", "etat"].includes(p) ? p : "plan"; });
  useEffect(() => { memoriserEtat("MigrationView", "page", page); }, [page]);   // #874   // #815 : plan | préparation d'une réinstallation ; #856 : copies | risques

  const load = useCallback(() => fetchMigration(siAgentApiBase).then((d) => { setData(d); setErr(d?.error || null); setAt(new Date()); }).catch((e) => setErr(e.message)), [siAgentApiBase]);
  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [load]);

  const act = async (action, step) => {
    setBusy(true);
    try {
      const r = await migrationControl(siAgentApiBase, action, step, username, tab);
      setMsg({ ok: r?.ok, text: r?.message || r?.error || "" });
      await load();
    } finally { setBusy(false); }
  };
  const savePlan = async (plan) => { setBusy(true); try { const r = await saveMigrationPlan(siAgentApiBase, plan, username); await load(); return r; } finally { setBusy(false); } };
  const saveVars = async (vars) => { setBusy(true); try { const r = await saveMigrationVars(siAgentApiBase, vars, username); setMsg({ ok: !r?.error, text: r?.error || "paramètres enregistrés" }); await load(); } finally { setBusy(false); } };

  const now = at ? at.getTime() : Date.now();
  const tabs = useMemo(() => tabsOf(data), [data]);
  useEffect(() => { if (tab && tabs.length && !tabs.some((x) => x.id === tab)) setTab(""); }, [tab, tabs]);   // #790 : ?onglet= inconnu -> onglet principal
  const vdata = useMemo(() => tabView(data, tab), [data, tab]);
  const focus = useMemo(() => (vdata ? focusStep(vdata) : null), [vdata]);
  const prog = progress(vdata);
  const c = controls(vdata);
  const need = missingVars(data);
  const run = data?.run || {};
  const auto = run.mode === "auto";
  const steps = allSteps(vdata);
  const errors = steps.filter((s) => s.error && s.id !== focus?.id);

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Migration 2026-2027</h2>
        {data?.plan && <span className="infra-muted">{data.plan.name} · {prog.done} / {prog.total} étapes · marche {RUN_LABEL[run.state] || run.state}{run.updated_by ? ` (${run.updated_by})` : ""}</span>}
        <span className="infra-muted">{at ? `mis à jour ${at.toLocaleTimeString("fr-FR")}` : "lecture…"}</span>
      </div>
      <div className="mig-controls" role="tablist">
        <button role="tab" aria-selected={page === "plan"} className={page === "plan" ? "" : "secondary"} onClick={() => setPage("plan")}>Plan de migration</button>
        <button role="tab" aria-selected={page === "prep"} className={page === "prep" ? "" : "secondary"} onClick={() => setPage("prep")}>Préparer la réinstallation d'un nœud</button>
        <button role="tab" aria-selected={page === "copies"} className={page === "copies" ? "" : "secondary"} onClick={() => setPage("copies")}>Copies et sauvegardes</button>
        <button role="tab" aria-selected={page === "risques"} className={page === "risques" ? "" : "secondary"} onClick={() => setPage("risques")}>Risques</button>
        <button role="tab" aria-selected={page === "etat"} className={page === "etat" ? "" : "secondary"} onClick={() => setPage("etat")}>État des lieux</button>
      </div>
      {page === "etat" ? <EtatDesLieuxView siAgentApiBase={siAgentApiBase} /> : page === "copies" ? <MigrationCopiesView siAgentApiBase={siAgentApiBase} /> : page === "risques" ? <MigrationRisquesView siAgentApiBase={siAgentApiBase} /> : page === "prep" ? <MigrationPrepView siAgentApiBase={siAgentApiBase} /> : <>
      {err && <p className="infra-error">{err}</p>}
      {data && !data.plan && <p className="infra-card">Aucun plan : importer le fichier <code>migration-2026.local.json</code> ci-dessous (modèle : <code>deploy/migration/plan-exemple.json</code>).</p>}
      {data?.plan && tabs.length > 1 && (
        <div className="mig-controls" role="tablist">
          {tabs.map((t) => <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "" : "secondary"} onClick={() => setTab(t.id)}>
            {t.label} <small>{t.done} / {t.total}</small>{t.bad && " ⚠"}</button>)}
        </div>
      )}
      {data?.plan && (
        <>
          <Bar pct={prog.pct} tone={steps.some((s) => s.status === "erreur") ? "critical" : "ok"} />
          <div className="mig-controls">
            <button disabled={busy || !c.start} onClick={() => act("start")} title="lance la première étape à faire">▶ Démarrer</button>
            <button disabled={busy || !c.next} onClick={() => act("next")} title="lance la prochaine étape (une seule)">⏭ Étape suivante</button>
            <button disabled={busy || !c.pause} onClick={() => act("pause")} title="suspend la copie en cours (reprise sans perte)">⏸ Pause</button>
            <button disabled={busy || !c.resume} onClick={() => act("resume")}>⏯ Reprendre</button>
            <button disabled={busy || !c.stop} className="danger" onClick={() => act("stop")} title="arrête l'étape en cours ; une relance reprend là où elle s'était arrêtée">⏹ Arrêter</button>
            <label className="mig-auto" title="automatique : chaque étape réussie lance la suivante ; une erreur suspend l'enchaînement">
              <input type="checkbox" checked={auto} disabled={busy} onChange={(e) => act(e.target.checked ? "auto" : "manuel")} /> automatique
            </label>
            {msg && <span className={msg.ok ? "infra-muted" : "infra-error"}>{msg.text}</span>}
          </div>
          <Focus s={focus} now={now} act={act} busy={busy} />
          {errors.length > 0 && <div className="infra-card"><b>Autres erreurs</b>{errors.map((s) => <div key={s.id}><p><code>{s.id}</code> {s.title}</p><ErrorCard s={s} act={act} busy={busy} /></div>)}</div>}
          <Vars vars={data.vars} need={need} onSave={saveVars} busy={busy} />
          {vdata.plan.phases.map((ph) => {
            const pp = phaseProgress(ph);
            return (
              <details key={ph.id} className="infra-card" open={pp.d < pp.n}>
                <summary><b>{ph.title}</b> <span className={`infra-status ${pp.tone}`}>{pp.d} / {pp.n}</span>{ph.note && <span className="infra-note"> {ph.note}</span>}</summary>
                <div className="infra-table-wrap"><table className="infra-table gu-table"><thead><tr><th>étape</th><th>titre</th><th>hôte</th><th>état</th><th title="restant / transféré / total · débit">avancement (restant / transféré / total)</th><th></th></tr></thead><tbody>
                  {ph.steps.map((s) => <StepRow key={s.id} s={{ ...s, phaseTitle: ph.title }} act={act} busy={busy} open={openStep === s.id} onOpen={() => setOpenStep(openStep === s.id ? null : s.id)} />)}
                </tbody></table></div>
              </details>
            );
          })}
          <details className="infra-card"><summary>Journal des gestes</summary>
            <table className="infra-table"><tbody>{(data.log || []).map((l, i) => <tr key={i}><td className="infra-muted">{l.at}</td><td>{l.who}</td><td>{l.action}</td><td>{l.step || ""}</td><td className="infra-muted">{l.detail}</td></tr>)}</tbody></table>
          </details>
        </>
      )}
      <PlanImport onSave={savePlan} busy={busy} />
      </>}
    </div>
  );
}
