// Assistant de rapatriement / nettoyage d'un nœud Proxmox distant (livraison #761) : une campagne en six étapes,
// présentée comme un assistant d'installation (◀ Précédent / Suivant ▶) avec un SYNOPTIQUE en bandeau permanent :
// les étapes, le curseur sur l'étape courante et le pourcentage d'avancement mesuré (plans #750 en cours).
// Données : si-agent-api /repatriation (campagnes) ; chaque CT / VM « à rapatrier » est confié à un plan repatriate.
import { useEffect, useState } from "react";
import DataStatus from "./DataStatus.jsx";   // #763
import { fetchRepatriations, createRepatriation, fetchRepatriation, saveRepatriation, launchRepatriation, repatriationGuest } from "./siAgentClient.js";
import { fmtBytes } from "./infraLib.js";
import { blocker, nextStep, prevStep, cursor, summary, launchesOnNext, STEP_IDS } from "./repaLib.js";

const TONE = { todo: "neutral", export: "warning", verify: "warning", diff: "critical", validate: "warning", destroy: "warning", done: "good", failed: "critical", aborted: "critical" };
const HELP = {
  inventaire: "Les CT / VM du nœud distant, tels que vus par la sonde pve-remote. Décider pour chacun : rapatrier (copie vérifiée puis destruction de l'original), garder sur le nœud distant, ou supprimer (sans copie : à faire à la main, hors assistant).",
  preparation: "Où et comment : stockage du nœud local, débit maximal de l'export, mode (stop = cohérent, l'original est arrêté pendant l'export), plage horaire des destructions. Les contrôles doivent être au vert : « Suivant » lance les rapatriements.",
  rapatriement: "Chaque CT / VM est exporté du nœud distant (vzdump par ssh, débit borné) et restauré sous son nouvel identifiant. L'avancement se met à jour toutes les 10 s.",
  verification: "Comparaison fichier à fichier de l'original et de la copie. Valider une copie (après l'avoir démarrée réseau coupé si besoin) autorise la destruction de son original dans la plage horaire ; « Abandonner » garde l'original.",
  nettoyage: "Les originaux validés sont détruits sur le nœud distant dans la plage horaire, leurs images réduites par tranches (pas de gel des disques). Les CT / VM marqués « supprimer » sont listés pour une suppression manuelle.",
  bilan: "Ce qui a été rapatrié, gardé, supprimé, et la place libérée sur le nœud distant.",
};

function Synoptic({ c }) {
  const cur = cursor(c);
  const steps = c.progress?.steps || [];
  const W = 1000, n = STEP_IDS.length, X = (i) => ((i + 0.5) / n) * W;
  return (
    <div className="infra-card" style={{ position: "sticky", top: 0, zIndex: 2, padding: "6px 12px" }}>
      <svg viewBox={`0 0 ${W} 86`} width="100%" height="86" role="img" aria-label={`avancement ${c.progress?.percent ?? 0} %`}>
        <line x1={X(0)} x2={X(n - 1)} y1="42" y2="42" stroke="var(--viz-grid, #ccc)" strokeWidth="6" strokeLinecap="round" />
        <line x1={X(0)} x2={X(0) + (X(n - 1) - X(0)) * cur.fill} y1="42" y2="42" stroke="var(--accent, #2a78d6)" strokeWidth="6" strokeLinecap="round" />
        {steps.map((s, i) => {
          const tone = s.done >= 1 ? "var(--st-good, #0ca30c)" : s.done > 0 ? "var(--st-warning, #fab219)" : "var(--panel, #fff)";
          return (
            <g key={s.id}>
              <circle cx={X(i)} cy="42" r={i === cur.index ? 13 : 10} fill={tone} stroke={i === cur.index ? "var(--accent, #2a78d6)" : "var(--muted, #888)"} strokeWidth={i === cur.index ? 4 : 2} />
              <text x={X(i)} y="47" textAnchor="middle" fontSize="12" fill="var(--text, #111)">{s.done >= 1 ? "✓" : i + 1}</text>
              <text x={X(i)} y="76" textAnchor="middle" fontSize="13" fontWeight={i === cur.index ? 700 : 400} fill="var(--text, #111)">{s.label}</text>
              <title>{`${s.label} : ${Math.round(s.done * 100)} % (poids ${s.weight} %)`}</title>
            </g>);
        })}
        <path d={`M ${X(cur.index) - 9} 6 L ${X(cur.index) + 9} 6 L ${X(cur.index)} 22 Z`} fill="var(--accent, #2a78d6)" style={{ transition: "all .4s" }} />
        <text x={W - 4} y="16" textAnchor="end" fontSize="16" fontWeight="700" fill="var(--text, #111)">{(c.progress?.percent ?? 0).toFixed(0)} %</text>
      </svg>
    </div>
  );
}

function GuestTable({ guests, cols, actions, empty }) {
  return (
    <div className="infra-table-wrap infra-scroll"><table className="infra-table">
      <thead><tr><th>ID</th><th>Nom</th><th>Type</th><th>Taille</th>{cols.map((c) => <th key={c.h}>{c.h}</th>)}{actions && <th />}</tr></thead>
      <tbody>{guests.map((g) => <tr key={g.vmid} style={g.present === false ? { opacity: 0.55 } : null}>
        <td><b>{g.vmid}</b></td><td>{g.name || "—"}{g.present === false && <div className="infra-muted">absent du nœud distant</div>}</td><td>{g.kind === "lxc" ? "CT" : "VM"}</td><td>{fmtBytes(g.size)}</td>
        {cols.map((c) => <td key={c.h}>{c.v(g)}</td>)}{actions && <td>{actions(g)}</td>}</tr>)}
        {!guests.length && <tr><td colSpan={4 + cols.length + (actions ? 1 : 0)} style={{ color: "var(--danger, #c33)", whiteSpace: "normal" }}>{empty || "aucun CT / VM"}</td></tr>}</tbody>
    </table></div>
  );
}

// #764 : d'où vient l'inventaire du nœud distant (sondes, âge, erreurs)
function InventorySources({ inv }) {
  const r = inv?.reports || [];
  if (!r.length) return null;
  const age = (at) => { const s = (Date.now() - Date.parse(at)) / 1000; return isNaN(s) ? "?" : s < 120 ? `${Math.round(s)} s` : s < 7200 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`; };
  return <div className="infra-muted" style={{ fontSize: 12, marginBottom: 6 }}>Sources : {r.map((x, i) => <span key={i} style={{ marginRight: 12 }}>
    <span className={`infra-dot ${x.ok ? "good" : "bad"}`} /> {x.task.replace("plugin:", "")} via {x.agent}, il y a {age(x.at)}{x.guests != null && ` · ${x.guests} CT/VM`}{x.source && ` (${x.source})`}{x.error && ` · ${x.error}`}{x.warnings?.length > 0 && ` · ${x.warnings.join(" ; ")}`}</span>)}</div>;
}

const Phase = ({ g }) => <><span className={`infra-status ${TONE[g.phase] === "good" ? "" : TONE[g.phase]}`}>{g.phase_label}</span>{g.phase_detail && <div className="infra-muted">{g.phase_detail}</div>}</>;

export default function RepatriationView({ onBack, siAgentApiBase, username }) {
  const base = siAgentApiBase;
  const [list, setList] = useState(null), [cid, setCid] = useState(null), [c, setC] = useState(null), [busy, setBusy] = useState(""), [err, setErr] = useState(null);
  const [draft, setDraft] = useState(null), [ms, setMs] = useState(null), [tick, setTick] = useState(0);
  const hosts = list?.local_agents || [];
  const loadList = () => { const t0 = performance.now(); return fetchRepatriations(base).then((r) => { setMs(Math.round(performance.now() - t0)); if (r?.error) throw new Error(r.error); setList(r); if (!cid && r.campaigns?.[0]) setCid(r.campaigns[0].id); }).catch((e) => setErr(e.message)); };
  useEffect(() => { loadList(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [base]);
  useEffect(() => {
    if (!cid) return undefined;
    let stop = false;
    const load = () => { const t0 = performance.now(); setTick((x) => x + 1); return fetchRepatriation(base, cid).then((r) => { if (!stop) { if (r?.error) setErr(r.error); else setC(r); } }).catch((e) => !stop && setErr(e.message)).finally(() => !stop && setMs(Math.round(performance.now() - t0))); };
    load(); const t = setInterval(load, 10000);
    return () => { stop = true; clearInterval(t); };
  }, [base, cid]);
  const act = async (label, fn) => { setBusy(label); setErr(null); try { const r = await fn(); if (r?.error) throw new Error(r.error); return r; } catch (e) { setErr(e.message); return null; } finally { setBusy(""); } };
  const put = async (body) => { const r = await act("…", () => saveRepatriation(base, cid, body)); if (r) setC(r); return r; };
  const goNext = async () => {
    if (launchesOnNext(c.step)) {
      if (!window.confirm(`Lancer le rapatriement de ${c.guests.filter((g) => g.decision === "rapatrier").length} CT / VM depuis ${c.remote} ?`)) return;
      const r = await act("lancement", () => launchRepatriation(base, cid, username));
      if (r) { setC(r.campaign); if (r.errors?.length) setErr(r.errors.join(" ; ")); }
      return;
    }
    put({ step: nextStep(c.step) });
  };
  const blk = c ? blocker(c) : null;
  const sum = c ? summary(c) : null;
  const sel = c ? c.guests.filter((g) => g.decision === "rapatrier") : [];

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Rapatriement d'un nœud distant</h2>
        <select value={cid || ""} onChange={(e) => setCid(+e.target.value)}><option value="">— campagne —</option>{(list?.campaigns || []).map((x) => <option key={x.id} value={x.id}>{x.name} · {x.percent} %</option>)}</select>
        <button className="secondary" onClick={() => setDraft({ remote: list?.remote_nodes?.[0] || "", pve_agent_id: hosts[0]?.agent_id || "", name: "" })}>+ Nouvelle campagne</button>
        {busy && <span className="infra-muted">⏳ {busy}</span>}
        {err && <span className="infra-status critical">{err}</span>}
      </div>
      <DataStatus base={base} tasks={["plugin:proxmox", "plugin:pve-remote", "plugin:node-activity"]} latencyMs={ms} error={err} refreshKey={tick}
        labels={{ "plugin:proxmox": "nœuds locaux (sonde proxmox)", "plugin:pve-remote": "nœuds distants (sonde pve-remote)", "plugin:node-activity": "activité des nœuds" }}
        extra={list ? [
          { tone: list.remote_nodes?.length ? "good" : "critical", text: `${list.remote_nodes?.length || 0} nœud(s) distant(s) visible(s)`, detail: list.remote_nodes?.length ? list.remote_nodes.join(", ") : "aucun : il faut la sonde pve-remote (ou node-activity) et le nœud déclaré dans /etc/si-agent/pve-remote.json de l'agent qui le joint" },
          { tone: hosts.length ? "good" : "critical", text: `${hosts.length} nœud(s) local(aux)`, detail: hosts.map((h) => `${h.node} (agent ${h.agent_id})`).join(", ") || "aucun agent ne remonte la sonde proxmox" }] : []} />
      {draft && <div className="infra-card"><div className="infra-top" style={{ margin: 0 }}>
        <label>Nœud distant <select value={draft.remote} onChange={(e) => setDraft({ ...draft, remote: e.target.value })}><option value="">—</option>{(list?.remote_nodes || []).map((n) => <option key={n}>{n}</option>)}</select></label>
        <label>Vers le nœud local <select value={draft.pve_agent_id} onChange={(e) => setDraft({ ...draft, pve_agent_id: e.target.value })}><option value="">—</option>{hosts.map((h) => <option key={h.agent_id} value={h.agent_id}>{h.node || h.hostname || h.agent_id}</option>)}</select></label>
        <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder={`Rapatriement ${draft.remote || "…"}`} />
        <button className="primary" disabled={!draft.remote || !draft.pve_agent_id} onClick={async () => { const r = await act("création", () => createRepatriation(base, { ...draft, actor: username })); if (r) { setDraft(null); setC(r); setCid(r.id); loadList(); } }}>Créer</button>
        <button className="secondary" onClick={() => setDraft(null)}>Annuler</button></div>
        <p className="infra-muted">Les nœuds distants sont ceux que voit la sonde pve-remote (tuile Infra). L'agent du nœud local doit avoir le nœud distant dans /etc/si-agent/pve-remote.json (agent ≥ 0.5.58).</p></div>}

      {c && <>
        <Synoptic c={c} />
        <section className="infra-card" style={{ flex: 1, overflow: "auto" }}>
          <h3 style={{ marginTop: 0 }}>Étape {STEP_IDS.indexOf(c.step) + 1} / {STEP_IDS.length} — {c.progress.steps.find((s) => s.id === c.step)?.label} <span className="infra-muted">· {c.name} · {c.remote} → {c.pve_agent_id}</span></h3>
          <p className="infra-muted">{HELP[c.step]}</p>

          {c.step === "inventaire" && <InventorySources inv={c.inventory} />}
          {c.step === "inventaire" && <GuestTable guests={c.guests} empty={c.inventory?.hint} cols={[
            { h: "État", v: (g) => g.status || "—" },
            { h: "Décision", v: (g) => <span style={{ whiteSpace: "nowrap" }}>{[["rapatrier", "rapatrier"], ["garder", "garder"], ["supprimer", "supprimer"]].map(([v, l]) => <label key={v} style={{ marginRight: 8 }}><input type="radio" name={`d${g.vmid}`} checked={g.decision === v} disabled={!!g.run_id} onChange={() => put({ decisions: { [g.vmid]: v } })} /> {l}</label>)}</span> },
            { h: "Nouvel ID", v: (g) => g.decision === "rapatrier" ? <input type="number" defaultValue={g.newid || ""} placeholder={g.vmid < 1000 ? String(9000 + g.vmid) : "auto"} disabled={!!g.run_id} style={{ width: 90 }} onBlur={(e) => e.target.value !== String(g.newid || "") && put({ newids: { [g.vmid]: e.target.value } })} /> : null }]} />}

          {c.step === "preparation" && <>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
              <label>Stockage local <select value={c.storage} onChange={(e) => put({ storage: e.target.value })}><option value="">—</option>{c.local_storages.map((s) => <option key={s}>{s}</option>)}{c.storage && !c.local_storages.includes(c.storage) && <option>{c.storage}</option>}</select></label>
              <label>Débit max <input type="number" min={0} defaultValue={c.settings.bwlimit_mbps} style={{ width: 80 }} onBlur={(e) => put({ settings: { bwlimit_mbps: +e.target.value } })} /> Mbit/s</label>
              <label>Mode <select value={c.settings.mode} onChange={(e) => put({ settings: { mode: e.target.value } })}><option value="stop">stop (cohérent)</option><option value="snapshot">snapshot (à chaud)</option><option value="suspend">suspend</option></select></label>
              <label>Destructions entre <input defaultValue={c.settings.window} style={{ width: 110 }} onBlur={(e) => put({ settings: { window: e.target.value } })} /></label>
              <label>Tranches <input type="number" min={1} defaultValue={c.settings.slice_gb} style={{ width: 60 }} onBlur={(e) => put({ settings: { slice_gb: +e.target.value } })} /> Go</label>
            </div>
            <ul style={{ listStyle: "none", paddingLeft: 0 }}>{c.checks.map((k) => <li key={k.label}><span className={`infra-dot ${k.ok ? "good" : "critical"}`}>{k.ok ? "●" : "■"}</span> {k.label} <span className="infra-muted">— {k.detail}</span></li>)}</ul>
            <p>{sel.length} CT / VM à rapatrier : {sel.map((g) => `${g.vmid} ${g.name}`).join(", ") || "aucun"}.</p>
          </>}

          {c.step === "rapatriement" && <GuestTable guests={sel} cols={[{ h: "Nouvel ID", v: (g) => g.newid || "—" }, { h: "Phase", v: (g) => <Phase g={g} /> },
            { h: "Étapes du plan", v: (g) => <span className="infra-muted">{(g.run?.steps || []).map((s) => `${s.status === "done" ? "✓" : s.status === "sent" ? "…" : s.status === "waiting" ? "⏸" : s.status === "failed" ? "✗" : "·"}`).join(" ")}</span> }]}
            actions={(g) => g.run_id && !["done", "aborted"].includes(g.phase) && <button className="secondary" onClick={() => window.confirm(`Abandonner le rapatriement de ${g.vmid} ? L'original reste en place.`) && act("abandon", () => repatriationGuest(base, cid, g.vmid, "abort", username))}>Abandonner</button>} />}

          {c.step === "verification" && <GuestTable guests={sel} cols={[{ h: "Phase", v: (g) => <Phase g={g} /> },
            { h: "Comparaison", v: (g) => { const v = (g.run?.steps || [])[2]?.result?.outcome; return v ? <span>{v.identical ? "identique" : `${v.missing} absent(s), ${v.extra} en trop, ${v.changed} modifié(s)`} · {v.copy_files} fichiers{v.vzdump_excluded ? ` · ${v.vzdump_excluded} exclus par vzdump` : ""}</span> : "—"; } }]}
            actions={(g) => <>{g.phase === "validate" && <button className="primary" onClick={() => window.confirm(`Copie ${g.newid} validée : détruire l'original ${g.vmid} sur ${c.remote} dans la plage ${c.settings.window} ?`) && act("validation", () => repatriationGuest(base, cid, g.vmid, "validate", username))}>Valider la copie</button>}
              {["validate", "diff"].includes(g.phase) && <button className="secondary" onClick={() => act("abandon", () => repatriationGuest(base, cid, g.vmid, "abort", username))}>Abandonner (garder l'original)</button>}</>} />}

          {c.step === "nettoyage" && <>
            <GuestTable guests={sel} cols={[{ h: "Phase", v: (g) => <Phase g={g} /> }, { h: "Copie locale", v: (g) => g.newid || "—" }]} />
            {c.guests.some((g) => g.decision === "supprimer") && <><h4>À supprimer à la main (sans copie)</h4>
              <pre style={{ fontSize: 12 }}>{c.guests.filter((g) => g.decision === "supprimer").map((g) => `ssh root@${c.remote} '${g.kind === "lxc" ? "pct" : "qm"} status ${g.vmid} && ${g.kind === "lxc" ? "pct" : "qm"} destroy ${g.vmid} --purge 1'`).join("\n")}</pre></>}
          </>}

          {c.step === "bilan" && <ul>
            <li>{sum.done} / {sum.rapatrier} CT / VM rapatrié(s), original détruit — {fmtBytes(sum.freed)} de disques libérés sur {c.remote}</li>
            {sum.failed > 0 && <li className="infra-status critical">{sum.failed} en échec ou abandonné(s) : originaux conservés</li>}
            <li>{sum.garder} gardé(s) sur {c.remote}, {sum.supprimer} à supprimer à la main</li>
          </ul>}
        </section>
        <div className="infra-top" style={{ justifyContent: "space-between" }}>
          <button className="secondary" disabled={c.step === "inventaire" || !!busy} onClick={() => put({ step: prevStep(c.step) })}>◀ Précédent</button>
          <span className="infra-muted">{blk && c.step !== "bilan" ? `Pour continuer : ${blk}` : ""}</span>
          {c.step !== "bilan" && <button className="primary" disabled={!!blk || !!busy} onClick={goNext}>{launchesOnNext(c.step) ? "Lancer le rapatriement ▶" : "Suivant ▶"}</button>}
        </div>
      </>}
    </div>
  );
}
