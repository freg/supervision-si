// Tuile « Latence des IP publiques » (livraison #775) : toutes les IP publiques du SI mesurées depuis plusieurs points
// (agent en place, ou hôte joint par SSH avec un compte personnel + sudo, en direct ou par rebond) -- ping, ouverture TCP,
// HTTPS par l'IP et par le nom (connexion, TLS, premier octet, total), diagnostic, médiane / p95 sur 24 h, erreurs avec
// cause et solution. Configurateur : cibles, points de mesure (comptes de connexion), réglages, import / export JSON.
// Données : si-agent-api /latency (commande `latency` des agents 0.5.73). Logique pure : latencyLib.js.
import { useCallback, useEffect, useState } from "react";
import { fetchLatency, fetchLatencyHistory, saveLatencyTarget, saveLatencyPoint, deleteLatency, saveLatencySettings, runLatency, fetchLatencyConfig, importLatencyConfig } from "./siAgentClient.js";
import IpPing from "./IpPing.jsx";
import {
  MODES, fmtMs, cell, groups, pointsFor, pointLabel, worst, counts, accessCommand, emptyTarget, emptyPoint, targetToForm, formToTarget, formToPoint,
  parseConfig, sparkPoints,
} from "./latencyLib.js";

import { useNavState } from "./navContext.js";   // #874
function Copy({ text }) {
  const [ok, setOk] = useState(false);
  return <button className="secondary mig-small" onClick={() => navigator.clipboard?.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); })}>{ok ? "copié ✓" : "Copier"}</button>;
}

function Cell({ c, onOpen }) {
  if (!c) return <td className="infra-muted">—</td>;
  const m = c.metrics || {};
  return (
    <td className={`lat-cell ${c.level}`} onClick={onOpen} title={(c.notes || []).join("\n") || "rien à signaler"}>
      <b>{fmtMs(m.total_ms)}</b>
      <small>ping {fmtMs(m.ping_ms)}{m.loss ? ` · ${m.loss} % perdus` : ""} · TLS {fmtMs(m.tls_ms)}</small>
      {c.total_p95 != null && <small className="infra-muted">24 h : méd. {fmtMs(c.total_med)} · p95 {fmtMs(c.total_p95)}</small>}
      {(c.notes || []).length > 0 && <small className="lat-note">⚠ {c.notes[0]}{c.notes.length > 1 ? ` (+${c.notes.length - 1})` : ""}</small>}
    </td>
  );
}

function Detail({ api, t, p, c, onClose }) {
  const [h, setH] = useState(null);
  useEffect(() => { fetchLatencyHistory(api, t.id, p.id, 24).then(setH); }, [api, t.id, p.id]);
  const s = h?.series || [];
  return (
    <div className="infra-card lat-detail">
      <div className="mig-focus-head"><b>{t.label} ({t.ip}) vu de {pointLabel(p)}</b><button className="secondary" onClick={onClose}>Fermer</button></div>
      {(c?.notes || []).length ? <ul>{c.notes.map((n) => <li key={n}>{n}</li>)}</ul> : <p>Rien à signaler.</p>}
      <div className="lat-sparks">
        {[["total_ms", "total HTTPS"], ["tls_ms", "poignée TLS"], ["ping_ms", "ping"]].map(([k, l]) => (
          <figure key={k}><figcaption>{l} (24 h, {s.length} mesures)</figcaption>
            <svg width="160" height="28" role="img" aria-label={l}><polyline points={sparkPoints(s, k, 160, 26)} className="lat-spark" /></svg></figure>
        ))}
      </div>
      <details><summary>dernière mesure brute</summary><pre className="mig-log">{JSON.stringify(c?.raw, null, 1)}</pre></details>
    </div>
  );
}

function StateBadge({ st, p, onRun, busy }) {
  if (!st) return null;
  const e = st.error;
  return (
    <div className={`lat-state ${e && !e.warning_only ? "critical" : e ? "warning" : ""}`}>
      <b>{p.label}</b> <span className="infra-muted">{pointLabel(p).slice(p.label.length)}</span>
      <span className="infra-muted"> · {st.status}{st.last_ok ? ` · dernière mesure ${new Date(st.last_ok * 1000).toLocaleString("fr-FR")}` : ""}</span>
      <button className="secondary mig-small" disabled={busy} onClick={() => onRun(p.id)}>Mesurer maintenant</button>
      {e && (
        <div className="mig-error">
          <b>⚠ {e.title}</b><p>{e.detail}</p><pre className="mig-log">{e.error}</pre>
          {e.solution && <div>Solution : {e.solution.label}{e.solution.where && <> · à lancer sur <b>{e.solution.where}</b></>}
            {e.solution.command && <><pre className="mig-cmd">{e.solution.command}</pre><Copy text={e.solution.command} /></>}</div>}
        </div>
      )}
    </div>
  );
}

function TargetForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState(targetToForm(initial));
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <div className="infra-card mig-vars">
      {[["label", "libellé"], ["ip", "IP publique"], ["ports", "ports (443, 22…)"], ["names", "noms HTTPS servis"], ["grp", "groupe"], ["notes", "notes"]].map(([k, l]) =>
        <label key={k}><span>{l}</span><input value={f[k] ?? ""} onChange={set(k)} /></label>)}
      <label><span>active</span><input type="checkbox" checked={!!f.enabled} onChange={set("enabled")} /></label>
      <div><button onClick={async () => { const r = await onSave(formToTarget(f)); setErr(r?.error || null); }}>Enregistrer</button> <button className="secondary" onClick={onCancel}>Annuler</button>{err && <span className="infra-error"> {err}</span>}</div>
    </div>
  );
}

function PointForm({ initial, agents, targets, onSave, onCancel }) {
  const [f, setF] = useState({ ...initial, targets: initial.targets || [] });
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const ssh = f.mode !== "agent";
  return (
    <div className="infra-card">
      <div className="mig-vars">
        <label><span>libellé</span><input value={f.label} onChange={set("label")} /></label>
        <label><span>type d'accès</span><select value={f.mode} onChange={set("mode")}>{MODES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label><span>{ssh ? "agent qui ouvre la connexion" : "agent qui mesure"}</span>
          <select value={f.agent} onChange={set("agent")}><option value="">— choisir —</option>{agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.name}</option>)}</select></label>
        {ssh && <>
          <label><span>compte de connexion</span><input value={f.login} onChange={set("login")} /></label>
          <label><span>hôte (IP ou nom)</span><input value={f.host} onChange={set("host")} /></label>
          <label><span>port SSH</span><input value={f.port} onChange={set("port")} /></label>
          {f.mode === "indirect" && <label><span>rebond (utilisateur@hôte:port)</span><input value={f.jump || ""} onChange={set("jump")} /></label>}
          <label><span>sudo (sans mot de passe)</span><input type="checkbox" checked={!!f.sudo} onChange={set("sudo")} /></label>
          <label><span>clé sur l'agent (facultatif)</span><input value={f.key || ""} onChange={set("key")} placeholder="/root/.ssh/id_ed25519" /></label>
        </>}
        <label><span>cibles mesurées (vide = toutes)</span>
          <select multiple value={f.targets} onChange={(e) => setF({ ...f, targets: [...e.target.selectedOptions].map((o) => o.value) })}>
            {targets.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}</select></label>
        <label><span>actif</span><input type="checkbox" checked={!!f.enabled} onChange={set("enabled")} /></label>
      </div>
      {ssh && f.agent && f.host && <div className="infra-note">Préparer l'accès (une fois, depuis la maison) : clé de l'agent {f.agent} posée dans le compte {f.login}.
        <pre className="mig-cmd">{accessCommand(formToPoint(f))}</pre><Copy text={accessCommand(formToPoint(f))} />
        {f.sudo && <p>Les mesures (ping, curl) n'ont pas besoin de root : décocher sudo évite d'avoir à le configurer sans mot de passe.</p>}</div>}
      <button onClick={async () => { const r = await onSave(formToPoint(f)); setErr(r?.error || null); }}>Enregistrer</button> <button className="secondary" onClick={onCancel}>Annuler</button>{err && <span className="infra-error"> {err}</span>}
    </div>
  );
}

export default function LatencyView({ onBack, siAgentApiBase: api, username }) {
  const [v, setV] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useNavState("LatencyView", "tab", "mesures");   // #874 : gardé au rechargement
  const [open, setOpen] = useState(null);
  const [editT, setEditT] = useState(null);
  const [editP, setEditP] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [cfgText, setCfgText] = useState("");

  const load = useCallback(() => fetchLatency(api).then((d) => { setV(d); setErr(d?.error || null); }), [api]);
  useEffect(() => { load(); const id = setInterval(load, 30000); return () => clearInterval(id); }, [load]);

  const act = async (fn) => { setBusy(true); try { const r = await fn(); setMsg(r?.error ? { ok: false, text: r.error } : r?.message ? { ok: true, text: r.message } : null); await load(); return r; } finally { setBusy(false); } };
  const run = (point) => act(() => runLatency(api, point));
  const pts = v?.points || [];
  const st = Object.fromEntries((v?.states || []).map((s) => [s.id, s]));
  const c = counts(v);
  const openT = open && (v?.targets || []).find((t) => t.id === open.t);
  const openP = open && pts.find((p) => p.id === open.p);

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Latence des IP publiques</h2>
        {["mesures", "cibles", "points", "reglages"].map((k) => <button key={k} className={tab === k ? "" : "secondary"} onClick={() => setTab(k)}>{{ mesures: "Mesures", cibles: "Cibles", points: "Points de mesure (accès)", reglages: "Réglages, import" }[k]}</button>)}
        <button className="secondary" disabled={busy || !pts.length} onClick={() => run()}>Mesurer maintenant</button>
        {msg && <span className={msg.ok ? "infra-muted" : "infra-error"}>{msg.text}</span>}
      </div>
      {err && <p className="infra-error">{err}</p>}
      {v && tab === "mesures" && (
        <>
          <div className="infra-kpis">
            <div className="infra-kpi"><span>IP publiques</span><b>{(v.targets || []).length}</b><small>{pts.length} point(s) de mesure · toutes les {v.settings?.period_minutes} min</small></div>
            <div className="infra-kpi"><span>en défaut</span><b>{c.critical}</b></div>
            <div className="infra-kpi"><span>à surveiller</span><b>{c.warning}</b></div>
            <div className="infra-kpi"><span>sans mesure</span><b>{c.none}</b></div>
          </div>
          {(v.states || []).filter((s) => s.error).map((s) => <StateBadge key={s.id} st={s} p={pts.find((p) => p.id === s.id)} onRun={run} busy={busy} />)}
          {!(v.targets || []).length && <p className="infra-card">Aucune cible : onglet « Cibles » ou import JSON dans « Réglages, import ».</p>}
          {open && openT && openP && <Detail api={api} t={openT} p={openP} c={cell(v, open.t, open.p)} onClose={() => setOpen(null)} />}
          <div className="infra-table-wrap infra-scroll"><table className="infra-table lat-table">
            <thead><tr><th>IP publique</th>{pts.map((p) => <th key={p.id} title={pointLabel(p)}>{p.label}</th>)}</tr></thead>
            <tbody>{groups(v.targets).map((g) => [
              <tr key={`g-${g.grp}`} className="lat-grp"><td colSpan={pts.length + 1}>{g.grp}</td></tr>,
              ...g.targets.map((t) => (
                <tr key={t.id}>
                  <td className={`lat-target ${worst(v, t.id) || ""}`}><b>{t.label}</b><small><IpPing ip={t.ip}>{t.ip}</IpPing>{t.names?.length ? ` · ${t.names.join(", ")}` : ""}</small></td>
                  {pts.map((p) => (pointsFor([p], t.id).length ? <Cell key={p.id} c={cell(v, t.id, p.id)} onOpen={() => setOpen({ t: t.id, p: p.id })} /> : <td key={p.id} className="infra-muted">·</td>))}
                </tr>)),
            ])}</tbody>
          </table></div>
        </>
      )}
      {v && tab === "cibles" && (
        <>
          <button onClick={() => setEditT(emptyTarget())}>+ Ajouter une IP publique</button>
          {editT && <TargetForm initial={editT} onCancel={() => setEditT(null)} onSave={(t) => act(async () => { const r = await saveLatencyTarget(api, t, username); if (!r?.error) setEditT(null); return r; })} />}
          <table className="infra-table"><thead><tr><th>libellé</th><th>IP</th><th>ports</th><th>noms</th><th>groupe</th><th>active</th><th></th></tr></thead><tbody>
            {(v.targets || []).map((t) => <tr key={t.id}><td>{t.label}</td><td><IpPing ip={t.ip}>{t.ip}</IpPing></td><td>{t.ports.join(", ")}</td><td>{t.names.join(", ")}</td><td>{t.grp}</td><td>{t.enabled ? "oui" : "non"}</td>
              <td><button className="secondary mig-small" onClick={() => setEditT(t)}>Modifier</button><button className="secondary mig-small" disabled={busy} onClick={() => act(() => deleteLatency(api, "target", t.id))}>Supprimer</button></td></tr>)}
          </tbody></table>
        </>
      )}
      {v && tab === "points" && (
        <>
          <p className="infra-note">Un point de mesure = l'endroit d'où l'on mesure. Agent en place, ou hôte joint par SSH (compte personnel, par défaut « {v.settings?.default_login} », sudo facultatif) depuis un agent exécutant, en direct ou par un rebond. Aucun mot de passe n'est enregistré.</p>
          <button onClick={() => setEditP(emptyPoint(v.settings?.default_login))}>+ Ajouter un point de mesure</button>
          {editP && <PointForm initial={editP} agents={v.agents || []} targets={v.targets || []} onCancel={() => setEditP(null)}
            onSave={(p) => act(async () => { const r = await saveLatencyPoint(api, p, username); if (!r?.error) setEditP(null); return r; })} />}
          {pts.map((p) => <div key={p.id}><StateBadge st={st[p.id]} p={p} onRun={run} busy={busy} />
            <button className="secondary mig-small" onClick={() => setEditP(p)}>Modifier</button><button className="secondary mig-small" disabled={busy} onClick={() => act(() => deleteLatency(api, "point", p.id))}>Supprimer</button></div>)}
        </>
      )}
      {v && tab === "reglages" && (
        <div className="infra-card">
          <label>Mesure toutes les <input type="number" min={5} max={1440} defaultValue={v.settings?.period_minutes} onBlur={(e) => act(() => saveLatencySettings(api, { period_minutes: Number(e.target.value) }))} /> minutes</label>{" "}
          <label>compte de connexion par défaut <input defaultValue={v.settings?.default_login} onBlur={(e) => act(() => saveLatencySettings(api, { default_login: e.target.value }))} /></label>
          <h3>Import / export</h3>
          <p className="infra-note">La liste réelle (IP, comptes) reste hors dépôt : fichier <code>latence.local.json</code>, importé ici. L'import ajoute ou remplace par identifiant.</p>
          <button className="secondary" onClick={async () => setCfgText(JSON.stringify(await fetchLatencyConfig(api), null, 1))}>Exporter</button>{" "}
          <input type="file" accept=".json,application/json" onChange={(e) => e.target.files?.[0]?.text().then(setCfgText)} />
          <textarea className="mig-plan" rows={10} value={cfgText} onChange={(e) => setCfgText(e.target.value)} placeholder='{"targets": [...], "points": [...], "settings": {...}}' />
          <button disabled={busy || !cfgText.trim()} onClick={() => { const { config, error } = parseConfig(cfgText); if (error) { setMsg({ ok: false, text: error }); return; }
            act(async () => { const r = await importLatencyConfig(api, config, username); return r?.errors?.length ? { error: r.errors.join(" · ") } : { message: `importé : ${r?.imported?.targets} cible(s), ${r?.imported?.points} point(s)` }; }); }}>Importer</button>
        </div>
      )}
    </div>
  );
}
