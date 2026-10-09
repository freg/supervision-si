import React, { useState, useEffect } from "react";
import { updateMockup, deleteMockup, renderMockup, decideMockup, shotUrl } from "./qaClient.js";
import { mockupStatus, slideIcon, scoreDelta, firstSlide, shotTriples, ratioPct } from "./qaLib.js";

// Maquette en étapes (#728, item 116 tranche 4) : situation actuelle → proposition → variantes → règles respectées →
// décision. Chaque variante est une feuille CSS injectée dans le navigateur de test (copie isolée, jamais la production).
// Non vérifié en navigateur : syntaxe @babel/parser, logique pure testée sous Node.
function Thumb({ base, rid, name, alt }) {
  if (!rid || !name) return <span className="muted">—</span>;
  const u = shotUrl(base, rid, name);
  return <a href={u} target="_blank" rel="noreferrer"><img className="qa-thumb qa-thumb-lg" src={u} alt={alt} /></a>;
}

export default function QaMockupPanel({ qaApiBase, mockup, login, onChange, onClose, onError }) {
  const [i, setI] = useState(() => firstSlide(mockup.slides));
  const [draft, setDraft] = useState(mockup.variants);
  const [busy, setBusy] = useState("");
  const [choice, setChoice] = useState(0);
  const [comment, setComment] = useState("");
  useEffect(() => { setDraft(mockup.variants); }, [mockup.id, mockup.updated_at]);   // eslint-disable-line react-hooks/exhaustive-deps
  const slides = mockup.slides || []; const s = slides[Math.min(i, slides.length - 1)] || {};
  const locked = mockup.status === "validee" || mockup.status === "integree";
  const dirty = JSON.stringify(draft) !== JSON.stringify(mockup.variants);

  async function call(tag, fn, after) {
    setBusy(tag); const r = await fn(); setBusy("");
    if (r.error) { onError(r.error); return; }
    if (r.warning) onError(r.warning);
    if (r.mockup) { onChange(r.mockup); if (after) after(r.mockup); }
  }
  const save = () => call("save", () => updateMockup(qaApiBase, mockup.id, { variants: draft }));
  const render = (v) => call("render" + (v ?? ""), () => renderMockup(qaApiBase, mockup.id, v, login), () => v !== undefined && setI(v + 1));
  const decide = (status) => call("decide", () => decideMockup(qaApiBase, mockup.id, { status, variant: Number(choice), comment, by_user: login }));
  async function remove() { setBusy("del"); const r = await deleteMockup(qaApiBase, mockup.id); setBusy(""); if (r.error) onError(r.error); else onClose(true); }
  const setVar = (k, f, v) => setDraft((d) => d.map((x, j) => (j === k ? { ...x, [f]: v } : x)));

  return (
    <div className="hub-card hub-settings-section qa-mockup">
      <div className="qa-row-between"><h2 style={{ margin: 0 }}>🎨 {mockup.name} <span className="muted">· {mockupStatus(mockup.status)}{mockup.ticket_id ? ` · ticket n°${mockup.ticket_id}` : ""}</span></h2>
        <div className="qa-inline">
          {!locked && <button className="primary" onClick={() => render()} disabled={!!busy || dirty} title={dirty ? "Enregistrez d'abord les variantes" : ""}>{busy === "render" ? "Captures…" : "▶ Générer les captures"}</button>}
          <button className="secondary" onClick={() => onClose(false)}>Fermer</button>
          <button className="secondary qa-danger" onClick={remove} disabled={!!busy}>Supprimer</button>
        </div></div>
      <p className="muted">Partie de l'exécution n°{mockup.base_run_id}. Les feuilles sont injectées dans le navigateur de test seulement ; le correctif retenu part dans un ticket évolution.</p>

      <details className="qa-details" open={!locked && (mockup.status === "brouillon" || dirty)}>
        <summary>Variantes ({draft.length}){dirty ? " — modifiées, à enregistrer" : ""}</summary>
        {draft.map((v, k) => (
          <div key={k} className="qa-variant">
            <div className="qa-inline"><input type="text" value={v.name} disabled={locked} onChange={(e) => setVar(k, "name", e.target.value)} />
              <span className="muted">{v.origin === "auto" ? "proposée (règles)" : "manuelle"}</span>
              {!locked && <button className="secondary" onClick={() => setDraft((d) => d.filter((_, j) => j !== k))} title="retirer">✕</button>}</div>
            <textarea rows={Math.min(12, Math.max(3, (v.css || "").split("\n").length + 1))} value={v.css} disabled={locked} spellCheck={false} className="qa-css"
              onChange={(e) => setVar(k, "css", e.target.value)} placeholder=":root { --accent: …; }  .hub-card { … }" />
            {(v.notes || []).length > 0 && <ul className="muted">{v.notes.map((n, j) => <li key={j}>{n}</li>)}</ul>}
          </div>))}
        {!locked && <div className="qa-inline"><button className="secondary" onClick={() => setDraft((d) => [...d, { name: `Variante ${d.length + 1}`, css: "", origin: "manuel", notes: [] }])}>+ Variante</button>
          <button className="primary" onClick={save} disabled={!dirty || busy === "save"}>Enregistrer les variantes</button>
          {dirty && <button className="secondary" onClick={() => setDraft(mockup.variants)}>Annuler</button>}</div>}
      </details>

      <div className="qa-steps-nav">
        <button className="secondary" onClick={() => setI(Math.max(0, i - 1))} disabled={i === 0}>◀</button>
        {slides.map((x, k) => <button key={k} className={`qa-mini ${k === i ? "qa-selected" : ""}`} onClick={() => setI(k)} title={x.title}>{slideIcon(x.kind)} {x.kind === "variante" || x.kind === "proposition" ? x.title.replace(/^[^:]+: /, "") : x.title}</button>)}
        <button className="secondary" onClick={() => setI(Math.min(slides.length - 1, i + 1))} disabled={i >= slides.length - 1}>▶</button>
      </div>

      <div className="qa-slide">
        <h3>{slideIcon(s.kind)} {s.title}</h3>
        {s.kind === "avant" && (<>
          <p>Note de conformité : <strong>{s.score ?? "—"}{s.score !== null && s.score !== undefined ? "/100" : ""}</strong>{s.score === null ? <span className="muted"> (aucune étape « audit » dans le scénario : ajoutez-en une pour noter)</span> : null}
            {Object.keys(s.rules || {}).length > 0 && <span className="muted"> · {Object.entries(s.rules).map(([k, n]) => `${k} ×${n}`).join(" · ")}</span>}</p>
          <div className="qa-thumbs">{(s.shots || []).map((x) => <figure key={x.shot}><Thumb base={qaApiBase} rid={s.run_id} name={x.shot} alt={`étape ${x.index}`} /><figcaption>étape {x.index} · {x.action}</figcaption></figure>)}</div>
        </>)}
        {(s.kind === "proposition" || s.kind === "variante") && (!s.rendered ? (
          <p>Pas encore rendue. {!locked && <button className="primary" onClick={() => render(s.variant)} disabled={!!busy || dirty}>{busy === "render" + s.variant ? "Captures…" : "▶ Générer cette variante"}</button>}</p>
        ) : (<>
          <p>Note : <strong>{s.score ?? "—"}/100</strong>{s.delta !== null && s.delta !== undefined && <span className={s.delta > 0 ? "qa-ok" : s.delta < 0 ? "qa-ko" : "muted"}> ({scoreDelta(s.delta)})</span>}
            {s.status !== "ok" && <span className="qa-ko"> · le parcours échoue avec cette feuille</span>}
            {s.diff && <span className="muted"> · {s.diff.significant} capture(s) visiblement changée(s)</span>}
            {!locked && <button className="secondary" onClick={() => render(s.variant)} disabled={!!busy || dirty}>↻ Regénérer</button>}</p>
          <AutoTable rows={shotTriples(s)} base={qaApiBase} rid={s.run_id} />
          <details className="qa-details"><summary>Feuille injectée</summary><pre className="qa-css">{s.css || "(vide)"}</pre></details>
          {(s.notes || []).length > 0 && <ul className="muted">{s.notes.map((n, j) => <li key={j}>{n}</li>)}</ul>}
        </>))}
        {s.kind === "regles" && (s.rows.length === 0 ? <p className="muted">Aucun constat : ajoutez une étape « audit » au scénario.</p> : (
          <div className="qa-scroll"><table className="qa-table"><thead><tr><th>Règle</th><th>Situation actuelle</th>{s.variants.map((v) => <th key={v}>{v}</th>)}</tr></thead>
            <tbody>{s.rows.map((r) => <tr key={r.rule}><td>{r.rule}</td><td>{r.before}</td>{r.after.map((a, k) => <td key={k} className={a === null ? "muted" : a < r.before ? "qa-ok" : a > r.before ? "qa-ko" : ""}>{a === null ? "non rendue" : a === 0 ? "✔ 0" : a}</td>)}</tr>)}</tbody></table></div>))}
        {s.kind === "decision" && (locked || mockup.status === "rejetee" ? (
          <p>{locked ? <>✔ Variante retenue : <strong>{mockup.variants[mockup.chosen]?.name}</strong>{mockup.ticket_id ? ` — ticket évolution n°${mockup.ticket_id}` : " — sans ticket"}</> : "✘ Maquette rejetée"}{s.comment ? <span className="muted"> · {s.comment}</span> : null}
            {locked && <><br /><span className={s.integrated_run_id ? "qa-ok" : "muted"}>{s.integrated_run_id ? `★ Intégrée : exécution n°${s.integrated_run_id} conforme (${(s.integrated_at || "").replace("T", " ")})` : "Cible du scénario : chaque campagne compare le développement à cette variante."}</span></>}</p>
        ) : (<>
          <div className="hub-settings-row"><label>Variante retenue</label>
            <select value={choice} onChange={(e) => setChoice(e.target.value)}>{mockup.variants.map((v, k) => <option key={k} value={k} disabled={!slides.find((x) => x.variant === k)?.rendered}>{v.name}{slides.find((x) => x.variant === k)?.rendered ? "" : " (non rendue)"}</option>)}</select></div>
          <div className="hub-settings-row"><label>Commentaire (joint au ticket)</label><textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} /></div>
          <div className="qa-inline"><button className="primary" onClick={() => decide("validee")} disabled={!!busy}>✔ Valider → ticket évolution</button>
            <button className="secondary" onClick={() => decide("rejetee")} disabled={!!busy}>✘ Rejeter</button></div>
        </>))}
      </div>
    </div>
  );
}

function AutoTable({ rows, base, rid }) {
  if (!rows.length) return <p className="muted">Aucune capture comparable.</p>;
  return (
    <div className="qa-scroll"><table className="qa-table"><thead><tr><th>Étape</th><th>Écart</th><th>Situation actuelle</th><th>Variante</th><th>Différences</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.index}><td>{r.index}</td><td className={r.significant ? "qa-ko" : "muted"}>{ratioPct(r.ratio)}</td>
        <td><Thumb base={base} rid={r.refRun} name={r.refShot} alt="avant" /></td><td><Thumb base={base} rid={rid} name={r.shot} alt="variante" /></td><td><Thumb base={base} rid={rid} name={r.diff} alt="différences" /></td></tr>)}</tbody></table></div>
  );
}
