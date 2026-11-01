// #822 Agents hôtes › Mises à jour › Diffusions en cascade : une règle = une cible (agents qui portent telle sonde,
// tel OS, telle liste) et des étapes ordonnées par leurs dépendances (mise à jour forcée, activer / désactiver une
// sonde, attendre un relevé). Le plan montre, agent par agent, ce qui est fait, en cours, en attente d'une dépendance,
// en échec, ou à faire ; « Exécuter » fait les gestes à faire ; en mode automatique le central les fait toutes les 2 min.
import { Fragment, useCallback, useEffect, useState } from "react";
import { fetchDiffusions, saveDiffusion, deleteDiffusion, runDiffusion } from "./siAgentClient.js";

const TON = { fait: "good", en_cours: "neutral", attente: "neutral", a_faire: "warn", echec: "bad" };
const MOT = { fait: "fait", en_cours: "en cours", attente: "attente", a_faire: "à faire", echec: "échec" };
const cible = (c = {}) => [c.plugins_any?.length && `sonde ${c.plugins_any.join(" ou ")}`, c.plugins_all?.length && `sondes ${c.plugins_all.join(" et ")}`,
  c.os?.length && `OS ${c.os.join(", ")}`, c.agents?.length && `agents ${c.agents.join(", ")}`, c.exclure?.length && `sauf ${c.exclure.join(", ")}`].filter(Boolean).join(" · ");

export default function DiffusionsSection({ base, username }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [edit, setEdit] = useState(null);   // texte JSON en cours d'édition
  const [ouvert, setOuvert] = useState(null);
  const [msg, setMsg] = useState("");
  const load = useCallback(async () => { const r = await fetchDiffusions(base); if (r?.error) setErr(r.error); else { setD(r); setErr(null); } }, [base]);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);
  async function enregistrer() {
    let regle;
    try { regle = JSON.parse(edit); } catch (e) { setErr(`JSON invalide : ${e.message}`); return; }
    const r = await saveDiffusion(base, regle);
    if (r?.error) setErr(r.error); else { setEdit(null); load(); }
  }
  async function basculer(r, k) { const x = await saveDiffusion(base, { ...r, [k]: !r[k] }); if (x?.error) setErr(x.error); else load(); }
  async function executer(r, simulation) {
    const x = await runDiffusion(base, r.id, simulation, username || "hub");
    if (x?.error) { setErr(x.error); return; }
    setMsg(simulation ? `simulation « ${r.nom} » : ${x.gestes.length ? x.gestes.map((g) => `${g.agent_id} → ${g.etape}`).join(", ") : "aucun geste à faire"}`
      : `« ${r.nom} » : ${x.faits.length ? x.faits.map((f) => `${f.agent_id} : ${f.resultat}`).join(" ; ") : "aucun geste à faire"}`);
    load();
  }
  async function supprimer(r) { if (!window.confirm(`Supprimer la diffusion « ${r.nom} » ? (rien n'est défait sur les agents)`)) return; const x = await deleteDiffusion(base, r.id); if (x?.error) setErr(x.error); else load(); }
  if (!d) return <p className="muted">{err || "Chargement des diffusions…"}</p>;
  const nouvelle = () => { const { id, plan, gestes, ...x } = d.exemple; setEdit(JSON.stringify(x, null, 2)); };   // eslint-disable-line no-unused-vars
  return (
    <div className="infra-card" style={{ marginTop: 16 }}>
      <div className="veille-ligne"><h3 style={{ margin: 0 }}>Diffusions en cascade</h3>
        <span className="infra-muted">version servie {d.version_servie || "aucune"} · étapes : {Object.values(d.types).join(", ")}</span>
        <span style={{ flex: 1 }} /><button type="button" onClick={nouvelle}>Nouvelle diffusion</button></div>
      {err && <p className="infra-error">{err}</p>}
      {msg && <p className="infra-muted" onClick={() => setMsg("")}>{msg}</p>}
      {edit != null && (
        <div className="veille-bloc">
          <p className="infra-muted">Règle en JSON : <code>cible</code> (plugins_any, plugins_all, os, agents, exclure) et <code>etapes</code> (id, type, sonde, apres, version_min).
            Sondes connues : {d.sondes.join(", ")}.</p>
          <textarea rows={16} style={{ width: "100%", fontFamily: "monospace" }} value={edit} onChange={(e) => setEdit(e.target.value)} />
          <div className="veille-ligne"><button type="button" onClick={enregistrer}>Enregistrer</button><button type="button" className="secondary" onClick={() => setEdit(null)}>Annuler</button></div>
        </div>)}
      <div className="infra-table-wrap"><table className="infra-table">
        <thead><tr><th>Diffusion</th><th>Cible</th><th>Étapes</th><th>Agents</th><th>Gestes à faire</th><th>Active</th><th>Auto</th><th></th></tr></thead>
        <tbody>
          {d.diffusions.map((r) => (
            <Fragment key={r.id}>
              <tr>
                <td><span className="veille-titre" onClick={() => setOuvert(ouvert === r.id ? null : r.id)}>{r.nom}</span></td>
                <td className="infra-muted">{cible(r.cible)}</td>
                <td className="infra-muted">{r.etapes.map((e) => `${e.id}${e.sonde ? ` (${e.sonde})` : ""}`).join(" → ")}</td>
                <td>{r.plan.filter((l) => l.termine).length} / {r.plan.length} terminés</td>
                <td>{r.gestes ? <span className="np-tone warn">{r.gestes}</span> : "—"}</td>
                <td><input type="checkbox" checked={r.actif} onChange={() => basculer(r, "actif")} /></td>
                <td><input type="checkbox" checked={r.auto} disabled={!r.actif} title="le central fait les gestes toutes les 2 min" onChange={() => basculer(r, "auto")} /></td>
                <td><div className="veille-actions">
                  <button type="button" className="secondary" onClick={() => executer(r, true)}>Simuler</button>
                  <button type="button" disabled={!r.actif || !r.gestes} onClick={() => executer(r, false)}>Exécuter</button>
                  <button type="button" className="secondary" onClick={() => { const { plan, gestes, ...x } = r; setEdit(JSON.stringify(x, null, 2)); }}>Modifier</button>{/* eslint-disable-line no-unused-vars */}
                  <button type="button" className="secondary" onClick={() => supprimer(r)}>✕</button>
                </div></td>
              </tr>
              {ouvert === r.id && (
                <tr><td colSpan={8}>
                  <table className="infra-table"><thead><tr><th>Agent</th><th>Version</th>{r.etapes.map((e) => <th key={e.id}>{e.id}</th>)}</tr></thead>
                    <tbody>{r.plan.map((l) => (
                      <tr key={l.agent_id}><td>{l.agent_id}</td><td className="infra-muted">{l.version || "?"}</td>
                        {l.etapes.map((e) => <td key={e.id}><span className={`np-tone ${TON[e.etat] || "neutral"}`} title={e.detail}>{MOT[e.etat] || e.etat}</span></td>)}</tr>))}
                      {!r.plan.length && <tr><td colSpan={2 + r.etapes.length} className="infra-muted">Aucun agent ne correspond à la cible.</td></tr>}
                    </tbody></table>
                </td></tr>)}
            </Fragment>))}
          {!d.diffusions.length && <tr><td colSpan={8} className="infra-muted">Aucune diffusion. « Nouvelle diffusion » propose l'exemple : mise à jour forcée puis pve-preflight sur les agents qui portent guest-usage ou pve-remote.</td></tr>}
        </tbody>
      </table></div>
    </div>
  );
}
