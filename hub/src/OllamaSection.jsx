// Modèles IA (livraison #746) -- section de la fiche d'un agent qui fait tourner Ollama : modèles présents,
// chargés (part GPU), place libre ; télécharger, charger, décharger, tester, supprimer (commande « ollama »).
// Chaque action montre son envoi puis l'acquittement de l'agent (il relève ses commandes toutes les minutes).
import { useState } from "react";
import { sendCommand, fetchCommand } from "./siAgentClient.js";
import { AutoColumns } from "./TableColumns.jsx";
import { gb, MODEL_RE, pullText } from "./ollama.js";

function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }
const TONE = { critical: "bad", warning: "warn" };
const SUGGESTED = ["qwen3:14b", "qwen3:30b-a3b", "qwen3:8b", "gpt-oss:20b", "gemma3:12b", "mistral-small3.2", "qwen3-coder:30b", "bge-m3", "nomic-embed-text"];
async function follow(apiBase, cid) {
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 3000));
    const c = await fetchCommand(apiBase, cid).catch(() => null);
    if (c && (c.status === "done" || c.status === "failed")) return c;
  }
  return null;
}

export default function OllamaSection({ apiBase, agentId, latest, present, when, onRefresh }) {
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);
  const [model, setModel] = useState("");
  const [pull, setPull] = useState(null);
  if (!latest && !present) return null;
  const d = latest?.data || {};

  const run = async (label, params, confirmText) => {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(label); setMsg({ tone: "neutral", text: `${label} : envoyé, en attente de l'agent…` });
    try {
      const r = await sendCommand(apiBase, agentId, "ollama", params);
      const c = await follow(apiBase, r?.command?.id || r?.id);
      const res = c?.result?.result || c?.result || {};
      if (!c) setMsg({ tone: "warn", text: `${label} : pas encore acquitté (l'agent relève ses commandes toutes les minutes)` });
      else if (c.status === "done" && res.ok !== false) {
        setMsg({ tone: "good", text: `${label} : ${res.message || "fait"}` });
        if (res.status) setPull(res.status.pull || null);
        onRefresh && setTimeout(onRefresh, 2000);
      } else setMsg({ tone: "bad", text: `${label} : ${res.error || c.error || "refusé"}` });
    } catch (e) { setMsg({ tone: "bad", text: `${label} : ${e.message}` }); }
    setBusy("");
  };

  const valid = MODEL_RE.test(model.trim()) && !model.includes("..");
  return (
    <>
      <h3 style={{ marginTop: 12 }}>Modèles IA (Ollama) <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>
        {latest ? <>· sonde du {when(latest.at)} · {d.up ? <>v{d.version} · {d.models?.length || 0} modèle(s), {d.loaded || 0} chargé(s)</> : <Tone tone="bad">injoignable</Tone>}</> : "· sonde ollama inactive"}
        {d.models_dir && <> · {gb(d.models_dir.free)} libres dans <code>{d.models_dir.path}</code></>}</span></h3>
      {!latest && (
        <p className="muted">La sonde <code>ollama</code> est livrée avec l'agent mais inactive.{" "}
          <button type="button" className="secondary" disabled={!!busy} onClick={async () => {
            setBusy("sonde"); try { await sendCommand(apiBase, agentId, "enable_plugin", { id: "ollama" }); setMsg({ tone: "good", text: "activation demandée : premier relevé d'ici quelques minutes" }); } catch (e) { setMsg({ tone: "bad", text: e.message }); } setBusy("");
          }}>Activer la sonde</button></p>
      )}
      {(d.alerts || []).length > 0 && <ul>{d.alerts.map((a) => <li key={a.code}><Tone tone={TONE[a.severity]}>{a.severity}</Tone> {a.message}</li>)}</ul>}
      {(d.models || []).length > 0 && (
        <div className="hub-table-scroll"><AutoColumns id="OllamaSection.1"><table>
          <thead><tr><th>Modèle</th><th>Taille</th><th>Paramètres</th><th>Quantif.</th><th>Chargé</th><th>Modifié</th><th className="ups-actions-head"></th></tr></thead>
          <tbody>{d.models.map((m) => (
            <tr key={m.name}>
              <td><strong>{m.name}</strong>{m.family && <div className="muted" style={{ fontSize: 11 }}>{m.family}</div>}</td>
              <td>{gb(m.size)}</td><td>{m.params || "—"}</td><td>{m.quant || "—"}</td>
              <td>{m.loaded ? <Tone tone={m.gpu_pct === 100 ? "good" : "warn"}>{m.gpu_pct ?? "?"} % GPU · {gb(m.loaded_size)}</Tone> : <span className="muted">non</span>}</td>
              <td className="muted">{m.modified ? new Date(m.modified).toLocaleDateString("fr-FR") : "—"}</td>
              <td className="ups-actions">
                {m.loaded
                  ? <button type="button" className="secondary" disabled={!!busy} onClick={() => run(`déchargement de ${m.name}`, { action: "unload", model: m.name })}>Décharger</button>
                  : <button type="button" className="secondary" disabled={!!busy} onClick={() => run(`chargement de ${m.name}`, { action: "load", model: m.name })}>Charger</button>}
                <button type="button" className="secondary" disabled={!!busy} onClick={() => run(`essai de ${m.name}`, { action: "test", model: m.name })}>Tester</button>
                <button type="button" className="secondary" disabled={!!busy} onClick={() => run(`suppression de ${m.name}`, { action: "delete", model: m.name }, `Supprimer ${m.name} (${gb(m.size)}) de ${agentId} ?`)}>Supprimer</button>
              </td>
            </tr>
          ))}</tbody>
        </table></AutoColumns></div>
      )}
      <div className="ups-toolbar" style={{ margin: "6px 0" }}>
        <input list="ollama-suggest" value={model} onChange={(e) => setModel(e.target.value)} placeholder="modèle à déployer, ex. qwen3:14b" style={{ minWidth: 240 }} />
        <datalist id="ollama-suggest">{SUGGESTED.map((s) => <option key={s} value={s} />)}</datalist>
        <button type="button" className="primary" disabled={!!busy || !valid} onClick={() => run(`téléchargement de ${model.trim()}`, { action: "pull", model: model.trim() })}>Déployer</button>
        <button type="button" className="secondary" disabled={!!busy} onClick={() => run("état", { action: "status" })}>État / progression</button>
        <a className="muted" href="https://ollama.com/library" target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>catalogue ollama.com</a>
      </div>
      {pullText(pull) && <p className="muted" style={{ fontSize: 13 }}>{pullText(pull)}</p>}
      {msg && <p style={{ fontSize: 13 }}><Tone tone={msg.tone}>{busy ? "⏳" : "•"}</Tone> {msg.text}</p>}
    </>
  );
}
