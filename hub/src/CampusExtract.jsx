// Extraction de fiches par l'IA interne (livraison #571) : on colle un texte
// (« À propos » Windows, courriel, PV…), le modèle local (assistant-api,
// Ollama sur le SI — rien ne sort) renvoie des fiches structurées et signale
// les champs sensibles ; on relit, on importe en fusion.
import { useState } from "react";
import { hubLink } from "./hubLinks.js";

export function recordsToCsv(records, columns) {
  const esc = (v) => { v = v == null ? "" : String(v); return /[";\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v; };
  return "﻿" + [columns.map(esc).join(";"), ...records.map((r) => columns.map((c) => esc(r[c])).join(";"))].join("\r\n");
}

export default function CampusExtract({ assistantUrl, collection, onImport, onClose }) {
  const [text, setText] = useState("");
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const base = (assistantUrl || "").replace(/\/$/, "");

  async function run() {
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await fetch(`${base}/extract`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, schema: collection === "services" ? "service" : "asset", context }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || j.error) throw new Error(j.error || `${r.status}`);
      const parsed = j.parsed || {};
      const fiches = Array.isArray(parsed.fiches) ? parsed.fiches : Array.isArray(parsed) ? parsed : [];
      if (!fiches.length) throw new Error("le modèle n'a renvoyé aucune fiche (réponse : " + String(j.text || "").slice(0, 200) + ")");
      const columns = [...new Set(fiches.flatMap((f) => Object.keys(f)))];
      setResult({ fiches, columns, sensitive: parsed.sensible || [], remarks: parsed.remarques || [], ms: j.ms, model: j.model });
    } catch (e) { setError(e.message); }
    setBusy(false);
  }

  if (!base) return <p className="muted">L'IA interne n'est pas configurée (<code>VITE_ASSISTANT_URL</code>) : voir <a href={hubLink("assistant")}>la tuile Assistant</a>.</p>;
  return (
    <div className="hub-card" style={{ padding: 10, marginBottom: 10 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
        <strong>Extraire des fiches d'un texte — IA interne</strong>
        <span className="muted">le texte est traité sur le SI (assistant-api / Ollama), il ne sort pas ; l'import reste à valider ici</span>
        <span style={{ flex: 1 }} />
        <button type="button" className="secondary" onClick={onClose}>Fermer</button>
      </div>
      <input placeholder="contexte (facultatif) : ex. postes de contrôle de l'allée immersive, lab X" value={context} onChange={(e) => setContext(e.target.value)} style={{ width: "100%", marginBottom: 6 }} />
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} style={{ width: "100%", fontFamily: "ui-monospace, monospace", fontSize: 12 }} placeholder="Coller ici : « À propos » Windows, courriel de livraison, liste d'équipements…" />
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <button type="button" className="primary" disabled={busy || !text.trim()} onClick={run}>{busy ? "Analyse…" : "Analyser"}</button>
        {result && <span className="muted">{result.fiches.length} fiche{result.fiches.length > 1 ? "s" : ""} · {result.ms ? `${(result.ms / 1000).toFixed(1)} s` : ""} {result.model ? `· ${result.model}` : ""}</span>}
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {result && (
        <div style={{ marginTop: 8 }}>
          {result.sensitive.length > 0 && <p className="muted" style={{ margin: "0 0 4px" }}>Champs signalés sensibles : {result.sensitive.join(", ")} — stockés dans la base du hub (volume du serveur), jamais dans le code ni sur la page publiée.</p>}
          {result.remarks.length > 0 && <ul style={{ margin: "0 0 6px", paddingLeft: 18 }}>{result.remarks.map((r, i) => <li key={i} style={{ color: "var(--warning)" }}>{typeof r === "string" ? r : JSON.stringify(r)}</li>)}</ul>}
          <div style={{ overflow: "auto", maxHeight: 300 }}>
            <table style={{ borderCollapse: "collapse", textAlign: "left", fontSize: 12 }}>
              <thead><tr>{result.columns.map((c) => <th key={c} style={{ color: result.sensitive.includes(c) ? "var(--warning)" : undefined }}>{c}</th>)}</tr></thead>
              <tbody>{result.fiches.map((f, i) => <tr key={i}>{result.columns.map((c) => <td key={c}><input value={f[c] ?? ""} onChange={(e) => { const fiches = result.fiches.slice(); fiches[i] = { ...fiches[i], [c]: e.target.value }; setResult({ ...result, fiches }); }} style={{ width: Math.max(80, Math.min(260, String(f[c] ?? "").length * 7)) }} /></td>)}</tr>)}</tbody>
            </table>
          </div>
          <button type="button" className="primary" style={{ marginTop: 8 }} onClick={() => onImport(new Blob([recordsToCsv(result.fiches, result.columns)], { type: "text/csv" }), "extraction-ia.csv")}>Importer ces fiches (fusion)</button>
        </div>
      )}
    </div>
  );
}
