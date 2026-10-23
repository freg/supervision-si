// Module d'action sur le réseau (livraison #852) : pour une anomalie, plan (par l'API ou manuel), impact immédiat
// (clients du périmètre actifs, volume récent), exécution surveillée par un chien de garde avec retour arrière
// automatique, plans manuels vérifiés par relecture, journal des actions avec annulation.
import { Fragment, useEffect, useState } from "react";

const ETAT = { surveillance: ["sous surveillance", "var(--warn, #e8b84a)"], verifiee: ["vérifiée", "var(--ok)"], annulee: ["annulée (retour arrière)", "var(--warn, #e8b84a)"],
  echec: ["échec, rien changé", "var(--danger)"], echec_retour: ["RETOUR ARRIÈRE IMPOSSIBLE", "var(--danger)"], attente_manuel: ["à faire à la main", "var(--muted, #8fa1b3)"],
  non_resolue: ["non résolue", "var(--danger)"], en_cours: ["en cours", "var(--warn, #e8b84a)"] };
const NIV = { aucun: "var(--ok)", faible: "var(--warn, #e8b84a)", fort: "var(--danger)", inconnu: "var(--muted, #8fa1b3)" };
const quand = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" }) : "—");
const depuis = (s) => (s == null ? "—" : s < 120 ? `${s} s` : s < 7200 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);

async function call(url, init) {
  const r = await fetch(url, { credentials: "include", ...init });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(d.error || `${r.status}`); e.data = d; e.status = r.status; throw e; }
  return d;
}
const post = (url, body) => call(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function NebulaActionPanel({ nebulaApiBase, siteId, aid, groups = [], login = "", onClose, onDone }) {
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/actions`;
  const [p, setP] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [vu, setVu] = useState(false);
  useEffect(() => { setP(null); setErr(null); setVu(false); call(`${base}/plan/${aid}`).then(setP).catch((e) => setErr(e.message)); }, [base, aid]);

  const executer = async () => {
    setBusy(true); setErr(null);
    try { await post(`${base}/executer`, { aid, confirm: true, confirm_impact: vu, groups, user: login }); onDone && onDone(); onClose && onClose(); }
    catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const manuel = async () => {
    setBusy(true); setErr(null);
    try { await post(`${base}/manuel`, { aid, impact: p.impact, groups, user: login }); onDone && onDone(); onClose && onClose(); }
    catch (e) { setErr(e.message); }
    setBusy(false);
  };

  if (err && !p) return <div className="hub-card"><p style={{ color: "var(--danger)" }}>{err}</p></div>;
  if (!p) return <div className="hub-card"><p className="muted">Préparation du plan et mesure de l'impact (clients et flux du périmètre)…</p></div>;
  const imp = p.impact;
  return (
    <div className="hub-card" style={{ borderLeft: `5px solid ${NIV[imp.niveau] || NIV.inconnu}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><strong>Action : {p.anomalie.element}</strong><button type="button" className="secondary" onClick={onClose}>✕</button></div>
      <p style={{ margin: "4px 0" }}>{p.anomalie.message}</p>
      <h4 style={{ margin: "8px 0 4px" }}>Plan {p.plan.mode === "api" ? "(par l'API Nebula, surveillé)" : "(manuel guidé)"}</h4>
      <ol style={{ margin: 0 }}>{p.plan.etapes.map((e, i) => <li key={i}>{e}</li>)}</ol>
      {p.plan.pourquoi_manuel && <p className="muted" style={{ margin: "4px 0" }}>Manuel : {p.plan.pourquoi_manuel}.</p>}
      <p className="muted" style={{ margin: "4px 0" }}>Retour arrière : {p.plan.retour}.{p.plan.mode === "api" ? ` Contrôles à +${p.surveillance_s.join(" s, +")} s.` : ""}</p>
      <h4 style={{ margin: "8px 0 4px" }}>Impact immédiat <span style={{ color: NIV[imp.niveau] }}>({imp.niveau})</span></h4>
      <p style={{ margin: "4px 0" }}>{imp.texte}</p>
      {imp.erreurs?.length > 0 && <p className="muted">Mesure partielle : {imp.erreurs.join(" ; ")}</p>}
      {imp.clients?.length > 0 && (
        <div style={{ maxHeight: 220, overflow: "auto" }}><table className="services infra-table" style={{ width: "100%" }}>
          <thead><tr><th>Client</th><th>MAC</th><th>IP</th><th>VLAN</th><th>Vu il y a</th><th>Source</th></tr></thead>
          <tbody>{imp.clients.map((c) => <tr key={c.mac} style={{ fontWeight: c.actif ? 600 : 400 }}><td>{c.nom || "—"}</td><td>{c.mac}</td><td>{c.ip || "—"}</td><td>{c.vlan ?? "—"}</td><td>{depuis(c.vu_il_y_a_s)}</td><td className="muted">{c.source}</td></tr>)}</tbody>
        </table></div>)}
      <p className="muted" style={{ margin: "4px 0" }}>Flux actifs : l'API Nebula ne donne pas les flux en cours ; ils sont approchés par les clients vus depuis moins de 10 min et le volume Wi-Fi des 2 dernières heures.</p>
      {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {p.plan.mode === "api" ? (<>
          {imp.niveau === "fort" && <label><input type="checkbox" checked={vu} onChange={(e) => setVu(e.target.checked)} /> j'ai vu l'impact, j'exécute quand même</label>}
          <button type="button" disabled={busy || !p.ecriture_autorisee || (imp.niveau === "fort" && !vu)} onClick={() => { if (window.confirm("L'action ÉCRIT la configuration de Nebula, sous surveillance avec retour arrière automatique. Exécuter ?")) executer(); }}>
            {busy ? "en cours…" : "Exécuter sous surveillance"}</button>
          {!p.ecriture_autorisee && <span className="muted">écriture désactivée : NEBULA_ALLOW_WRITE=1 dans le .env (pas de lien : opération manuelle)</span>}
        </>) : <button type="button" disabled={busy} onClick={manuel}>{busy ? "en cours…" : "Ouvrir l'action manuelle (journalisée)"}</button>}
      </div>
    </div>
  );
}

export function NebulaActionsJournal({ nebulaApiBase, siteId, groups = [], login = "", version = 0 }) {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState(null);
  const [ouvert, setOuvert] = useState(null);
  const load = () => call(`${nebulaApiBase}/actions?site=${encodeURIComponent(siteId)}`).then(setD).catch((e) => setErr(e.message));
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [nebulaApiBase, siteId, version]);
  const enCours = (d?.actions || []).some((a) => a.etat === "surveillance" || a.etat === "en_cours");
  useEffect(() => { if (!enCours) return undefined; const t = setInterval(load, 10000); return () => clearInterval(t); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [enCours]);
  const geste = async (a, g) => {
    if (g === "annuler" && !window.confirm(`Remettre le port dans son état sauvegardé (${a.element}) ?`)) return;
    setBusy(a.id + g); setErr(null);
    try { await post(`${nebulaApiBase}/actions/${a.id}/${g}`, { groups, user: login }); await load(); } catch (e) { setErr(e.message); }
    setBusy(null);
  };
  const lst = d?.actions || [];
  if (!lst.length) return null;
  return (
    <div className="hub-card">
      <h3 style={{ marginTop: 0 }}>Journal des actions ({lst.length})</h3>
      {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
      <div style={{ maxHeight: 420, overflow: "auto" }}><table className="services infra-table" style={{ width: "100%" }}>
        <thead><tr><th>Quand</th><th>Élément</th><th>Mode</th><th>Par</th><th>État</th><th>Contrôles</th><th></th></tr></thead>
        <tbody>{lst.map((a) => { const [l, c] = ETAT[a.etat] || [a.etat, "inherit"]; return (<Fragment key={a.id}>
          <tr key={a.id} style={{ cursor: "pointer" }} onClick={() => setOuvert(ouvert === a.id ? null : a.id)}>
            <td>{quand(a.at)}</td><td>{a.element}</td><td>{a.mode === "api" ? "API" : "manuel"}</td><td>{a.user}</td><td style={{ color: c, fontWeight: 600 }}>{l}</td>
            <td>{(a.controles || []).map((x) => (x.ok ? "✓" : "✗")).join(" ") || "—"}</td>
            <td style={{ whiteSpace: "nowrap" }} onClick={(e) => e.stopPropagation()}>
              {a.mode === "api" && (a.etat === "surveillance" || a.etat === "verifiee") && <button type="button" className="secondary" disabled={!!busy} onClick={() => geste(a, "annuler")}>{busy === a.id + "annuler" ? "en cours…" : "Annuler (retour arrière)"}</button>}
              {a.mode === "manuel" && a.etat !== "verifiee" && <button type="button" className="secondary" disabled={!!busy} onClick={() => geste(a, "verifier")}>{busy === a.id + "verifier" ? "en cours…" : "Fait, vérifier"}</button>}
            </td></tr>
          {ouvert === a.id && <tr key={a.id + "j"}><td colSpan={7}><ul style={{ margin: 0 }}>{(a.journal || []).map((j, i) => <li key={i}><span className="muted">{quand(j.at)}</span> {j.texte}</li>)}</ul>
            {a.mode === "manuel" && <ol style={{ margin: "4px 0" }}>{a.plan.etapes.map((e, i) => <li key={i}>{e}</li>)}</ol>}</td></tr>}
        </Fragment>); })}</tbody>
      </table></div>
    </div>
  );
}
