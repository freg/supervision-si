import { useCallback, useEffect, useState } from "react";
import { fetchInstances, addInstance, removeInstanceDecl, instanceAction } from "./servicesClient.js";
import { instanceNameError, instanceState } from "./towerLib.js";
import { AutoColumns } from "./TableColumns.jsx";

// Onglet « 🧬 Instances » de la tour de contrôle (#733, item 117 tranche 4) -- « Déploiement d'application » : une
// copie d'une application (portail tickets, GED…) sous un autre nom, sur un AUTRE nœud, avec la configuration et les
// référentiels de la source, jamais ses données métier. Déclaration (registre deploy/instances.json), puis jobs :
// déployer (node_agent.py instance-deploy) / retirer (instance-undeploy, données conservées sur le nœud).
// Non vérifié en navigateur : syntaxe @babel/parser, logique pure (towerLib) testée sous Node.
const TONE = { red: "hub-error", orange: "", green: "", grey: "muted" };

export default function TowerInstances({ apiBase, token, openJob }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");
  const [form, setForm] = useState({ name: "", app: "tickets", node: "", title: "" });
  const load = useCallback(async () => { const d = await fetchInstances(apiBase, token); if (d.error) setError(d.error); else { setData(d); setError(null); } }, [apiBase, token]);
  useEffect(() => { load(); }, [load]);
  const names = (data?.instances || []).map((i) => i.name);
  const nameErr = form.name ? instanceNameError(form.name, names) : "";
  const targets = (data?.nodes || []);

  async function declare() {
    setBusy("add"); const r = await addInstance(apiBase, token, form); setBusy("");
    if (r.error) { setError(r.error); return; }
    setForm({ name: "", app: form.app, node: "", title: "" }); load();
  }
  async function act(i, action) {
    const msg = action === "deploy"
      ? `Déployer l'instance « ${i.name} » sur ${i.node} ? Services clonés construits et lancés, configuration copiée depuis la source (référentiels seulement), passerelles rechargées.`
      : `Retirer l'instance « ${i.name} » ? Ses conteneurs sont arrêtés sur ${i.node} (données CONSERVÉES dans instances/${i.name}/), sa route et sa déclaration sont retirées.`;
    if (!window.confirm(msg)) return;
    setBusy(action + i.name); const r = await instanceAction(apiBase, token, i.name, action, { build: true }); setBusy("");
    if (r.error) { setError(r.error); return; }
    if (r.job?.id) openJob(r.job.id);
  }
  async function forget(i) {
    if (!window.confirm(`Oublier la déclaration « ${i.name} » sans rien arrêter ? (à réserver à une instance jamais déployée)`)) return;
    const r = await removeInstanceDecl(apiBase, token, i.name); if (r.error) setError(r.error); else load();
  }

  if (!data && !error) return <p className="muted">chargement…</p>;
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Déploiement d'application : une copie d'une application sous un autre nom, sur un autre nœud, avec la configuration et les
        référentiels de la source (types, statuts, niveaux, sites, règles…), jamais ses tickets, documents, personnes ni secrets.
        Adresse : <code>/&lt;application&gt;-&lt;nom&gt;/</code>. Suivi des jobs dans « Livraisons & jobs ».
      </p>
      {error && <p className="hub-error">{error}</p>}
      {data && !data.configured && <p className="hub-error">Déploiement réparti non configuré (<code>deploy/nodes.json</code>) : une instance va sur un autre nœud. Voir l'onglet Répartition.</p>}
      {data?.problems?.length > 0 && <p className="hub-error">Registre : {data.problems.join(" ; ")}</p>}
      <h3>Instances ({data?.instances?.length || 0})</h3>
      <AutoColumns id="TowerInstances.1"><table className="hub-table"><thead><tr><th>Nom</th><th>Application</th><th>Nœud</th><th>Adresse</th><th>État</th><th>Données</th><th></th></tr></thead>
        <tbody>{(data?.instances || []).map((i) => { const st = instanceState(i); return (
          <tr key={i.name}><td><b>{i.name}</b>{i.title ? <div className="muted">{i.title}</div> : null}</td>
            <td>{data.apps?.[i.app]?.title || i.app}</td><td>{i.node}</td>
            <td>{i.plan?.front ? <a href={i.plan.front} target="_blank" rel="noreferrer">{i.plan.front}</a> : <code>{Object.values(i.plan?.routes || {})[0] || "—"}</code>}</td>
            <td className={TONE[st.tone]}>{st.text}</td><td className="muted">{(i.plan?.data || []).join(", ")}</td>
            <td style={{ whiteSpace: "nowrap" }}>
              <button type="button" className="primary" disabled={!!busy} onClick={() => act(i, "deploy")}>{busy === "deploy" + i.name ? "…" : "Déployer"}</button>{" "}
              <button type="button" className="secondary" disabled={!!busy} onClick={() => act(i, "undeploy")}>Retirer</button>{" "}
              <button type="button" className="secondary" disabled={!!busy} onClick={() => forget(i)} title="Oublier la déclaration sans rien arrêter">✕</button></td></tr>); })}
          {!data?.instances?.length && <tr><td colSpan={7} className="muted">aucune instance déclarée</td></tr>}</tbody></table></AutoColumns>
      <h3>Nouvelle instance</h3>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <select value={form.app} onChange={(e) => setForm({ ...form, app: e.target.value })}>{Object.entries(data?.apps || {}).map(([k, a]) => <option key={k} value={k}>{a.title}{a.config ? "" : " (sans copie de configuration)"}</option>)}</select>
        <input type="text" value={form.name} placeholder="nom (ex. formation)" onChange={(e) => setForm({ ...form, name: e.target.value.trim().toLowerCase() })} />
        <select value={form.node} onChange={(e) => setForm({ ...form, node: e.target.value })}><option value="">nœud…</option>{targets.map((n) => <option key={n} value={n}>{n}{n === data?.me ? " (ici)" : ""}</option>)}</select>
        <input type="text" value={form.title} placeholder="libellé (facultatif)" onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <button type="button" className="primary" disabled={!form.name || !!nameErr || !form.node || !!busy} onClick={declare}>Déclarer</button>
        {nameErr && <span className="hub-error">{nameErr}</span>}
        {form.name && !nameErr && <span className="muted">→ <code>/{form.app}-{form.name}/</code>, services <code>{form.app}-…-{form.name}</code></span>}
      </div>
    </div>
  );
}
