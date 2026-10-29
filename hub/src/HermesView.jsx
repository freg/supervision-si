import { useCallback, useEffect, useRef, useState } from "react";
// Appel à hermes-web (sous /hermes/api via la passerelle supervision) ; l'erreur du serveur remonte telle quelle.
async function api(chemin, { methode = "GET", corps } = {}) {
  const r = await fetch(chemin, { method: methode, credentials: "include", headers: corps ? { "Content-Type": "application/json" } : {}, body: corps ? JSON.stringify(corps) : undefined });
  let d = null;
  try { d = await r.json(); } catch { d = null; }
  if (!r.ok) throw new Error((d && (d.erreur || d.error)) || `${r.status} ${r.statusText}`);
  return d;
}

// Tuile Hermes : clone navigateur du harnais Hermes (service hermes-web, projet séparé), branché via le proxy du hub
// sous /hermes/api/. Chat en STREAMING (réponse en direct, réflexion <think> séparée et chronométrée) sous garde-fous
// (loi > morale > véracité, lecture seule en prod), log de questions reprenables, console d'activité réglable
// (plus récent en haut, copiable / téléchargeable), rejeu QA (clé de voûte : avancement + régressions). #908+.
const B = "/hermes/api";
const hub = (p, o) => api(B + p, o);
const DEC = { autoriser: ["✓", "ok"], demander: ["⏳ à valider", "warn"], refuser: ["⛔ refusé", "bad"] };
const msHeure = (t) => { const d = new Date((t || Date.now() / 1000) * 1000); return d.toLocaleTimeString("fr-FR") + "." + String(d.getMilliseconds()).padStart(3, "0"); };
const ctxK = (c) => (c ? `${Math.round(c / 1024)}K` : "");
const paramsTxt = (p) => (p ? [p.modele, p.api_mode, p.reasoning, ctxK(p.contexte)].filter(Boolean).join(" · ") : "");
const perfJournal = (e) => e.reflexion_ms != null
  ? `· réflexion ${Math.round(e.reflexion_ms)} ms · réponse ${Math.round(e.reponse_ms || 0)} ms${e.tokens_in != null ? ` · injection ${e.tokens_in} tok` : ""}`
  : (e.chargement_ms != null ? `· chargement ${Math.round(e.chargement_ms)} ms · exécution ${Math.round(e.execution_ms || 0)} ms` : `· ${e.duree_ms || 0} ms`);

function Bulle({ e }) {
  const t = DEC[e.decision];
  return (
    <div className={`hw-msg ${e.role}`}>
      <span className="hw-h">{msHeure(e._t)}</span>
      {(e.role === "agent" && !e.texte && e.attente != null)
        ? <span style={{ color: "var(--warning)" }}>⏳ réflexion… {e.attente} s</span>
        : <span>{e.role === "outil" ? "⚙ " + (e.outil || "") + " " : ""}{e.texte}</span>}
      {t && <span className={`hw-dec ${t[1]}`}> {t[0]}</span>}
      {e.perf && <span className="hw-h" style={{ display: "block", opacity: .7, marginTop: 4 }}>{e.perf}</span>}
    </div>
  );
}

const RAISONS = ["none", "minimal", "low", "medium", "high", "xhigh"];
const CONTEXTES = [["65536", "64 K (défaut qwen3:4b)"], ["98304", "96 K"], ["131072", "128 K"], ["262144", "256 K"]];
function Reglages({ data, onClose, onSave }) {
  const [d, setD] = useState(() => JSON.parse(JSON.stringify(data || {})));
  const [envoi, setEnvoi] = useState(false);
  const prof = d.profil || (d.profil = {}); const eff = prof.effets || (prof.effets = {});
  const pre = d.prechauffage || (d.prechauffage = {}); const her = d.hermes || (d.hermes = {});
  const set = (f) => { f(d); setD({ ...d }); };
  const champ = { background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: "3px 6px" };
  async function enregistrer() {
    setEnvoi(true);
    await onSave({ profil: { lecture_seule: !!prof.lecture_seule, effets: eff }, prechauffage: pre, cahier: d.cahier,
                   hermes: { modele: her.modele, api_mode: her.api_mode, reasoning: her.reasoning, contexte: her.contexte } });
    setEnvoi(false);
  }
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", zIndex: 50, display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "6vh 12px" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 10, padding: 18, width: 520, maxWidth: "95vw", maxHeight: "86vh", overflow: "auto" }}>
        <div style={{ display: "flex", alignItems: "center" }}><b style={{ flex: 1 }}>Réglages — Hermes ({d.hub})</b><button className="secondary petit" onClick={onClose}>✕</button></div>
        {!d.overlay_inscriptible && <p className="bad" style={{ fontSize: ".82rem" }}>⚠ dossier des réglages non inscriptible : les réglages de la tuile ne seront pas conservés.</p>}

        <h4 style={{ marginBottom: 4 }}>Garde-fous</h4>
        <label style={{ display: "block", margin: "4px 0" }}><input type="checkbox" checked={!!prof.lecture_seule} onChange={(e) => set((x) => { x.profil.lecture_seule = e.target.checked; })} /> lecture seule (production : tout sauf la lecture refusé)</label>
        {(d.effets || []).map((f) => (
          <div key={f} style={{ display: "flex", gap: 8, alignItems: "center", margin: "2px 0", fontSize: ".86rem" }}>
            <span style={{ width: 90 }} className="hw-mut">{f}</span>
            <select style={champ} value={eff[f] || "demander"} onChange={(e) => set((x) => { x.profil.effets[f] = e.target.value; })}>
              {(d.decisions || []).map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>))}

        <h4 style={{ margin: "14px 0 4px" }}>Préchauffage (garder le modèle chaud)</h4>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: ".86rem" }}>
          <span className="hw-mut">modèle</span>
          <select style={champ} value={pre.modele || ""} onChange={(e) => set((x) => { x.prechauffage.modele = e.target.value; })}>
            <option value="">— aucun —</option>{(d.ollama_modeles || []).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <span className="hw-mut">intervalle (s)</span>
          <input style={{ ...champ, width: 80 }} type="number" value={pre.intervalle_s || 240} onChange={(e) => set((x) => { x.prechauffage.intervalle_s = Number(e.target.value); })} />
        </div>

        <h4 style={{ margin: "14px 0 4px" }}>Cahier QA</h4>
        <input style={{ ...champ, width: "100%" }} value={d.cahier || ""} onChange={(e) => set((x) => { x.cahier = e.target.value; })} placeholder="config/cahier-....json" />

        <h4 style={{ margin: "14px 0 4px" }}>Moteur Hermes</h4>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: ".86rem", marginBottom: 6 }}>
          <span className="hw-mut">modèle</span>
          <select style={champ} value={her.modele || ""} onChange={(e) => set((x) => { x.hermes.modele = e.target.value; })}>
            {!(d.ollama_modeles || []).includes(her.modele) && her.modele ? <option value={her.modele}>{her.modele}</option> : null}
            {(d.ollama_modeles || []).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <span className="hw-mut">compatibilité API</span>
          <select style={champ} value={her.api_mode || "chat_completions"} onChange={(e) => set((x) => { x.hermes.api_mode = e.target.value; })}>
            {(d.api_modes || ["chat_completions", "codex_responses", "anthropic_messages"]).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: ".86rem" }}>
          <span className="hw-mut">raisonnement</span>
          <select style={champ} value={her.reasoning || "low"} onChange={(e) => set((x) => { x.hermes.reasoning = e.target.value; })}>
            {RAISONS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <span className="hw-mut">contexte</span>
          <select style={champ} value={String(her.contexte || "65536")} onChange={(e) => set((x) => { x.hermes.contexte = e.target.value; })}>
            {CONTEXTES.concat(CONTEXTES.some(([v]) => v === String(her.contexte)) || !her.contexte ? [] : [[String(her.contexte), `${her.contexte} (actuel)`]]).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <p className="hw-mut" style={{ fontSize: ".78rem", marginTop: 4 }}>Pour Ollama : compatibilité <code>chat_completions</code>. Hermes exige un contexte ≥ 64 K et Ollama doit servir au moins autant (OLLAMA_CONTEXT_LENGTH).</p>

        <div style={{ display: "flex", gap: 8, marginTop: 14 }}><button onClick={enregistrer} disabled={envoi}>{envoi ? "…" : "Enregistrer"}</button><button className="secondary" onClick={onClose}>Annuler</button></div>
      </div>
    </div>
  );
}

export default function HermesView({ onBack }) {
  const [profil, setProfil] = useState(null);
  const [err, setErr] = useState("");
  const [fil, setFil] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [envoi, setEnvoi] = useState(false);
  const [journal, setJournal] = useState([]);
  const [qa, setQa] = useState(null);
  const [qaEnCours, setQaEnCours] = useState(false);
  const [reg, setReg] = useState(null);
  const [regCharg, setRegCharg] = useState(false);
  const [consoleH, setConsoleH] = useState(() => { try { return Number(localStorage.getItem("hermesweb.consoleH")) || null; } catch { return null; } });
  const champ = useRef(null);
  const filRef = useRef(null);
  const esRef = useRef(null);

  useEffect(() => { hub("/profil").then(setProfil).catch((x) => setErr(x.message)); }, []);
  const majJournal = useCallback(() => { hub("/journal?n=60").then((d) => setJournal(d.entrees || [])).catch(() => {}); }, []);
  useEffect(() => { majJournal(); const i = setInterval(majJournal, 4000); return () => clearInterval(i); }, [majJournal]);
  useEffect(() => () => { if (esRef.current) esRef.current.close(); }, []);
  useEffect(() => { if (filRef.current) filRef.current.scrollTop = filRef.current.scrollHeight; }, [fil]);

  function lancer(p) {
    if (!p || envoi) return;
    const t0 = Date.now();
    const idA = "a" + t0;
    setEnvoi(true);
    setFil((f) => [...f, { role: "humain", texte: p, _t: t0 / 1000 },
      { role: "agent", id: idA, texte: "", _t: t0 / 1000, attente: 0 }]);
    // Hermes ne diffuse pas la réflexion : on fait vivre le temps d'attente jusqu'au 1er token.
    const tick = setInterval(() => setFil((f) => f.map((m) => (m.id === idA && !m.texte) ? { ...m, attente: Math.floor((Date.now() - t0) / 1000) } : m)), 500);
    const stop = () => { clearInterval(tick); setEnvoi(false); };
    const es = new EventSource(`${B}/chat/stream?prompt=${encodeURIComponent(p)}`);
    esRef.current = es;
    es.onmessage = (ev) => {
      let d; try { d = JSON.parse(ev.data); } catch { return; }
      if (d.kind === "reponse") setFil((f) => f.map((m) => m.id === idA ? { ...m, texte: m.texte + d.delta, attente: null } : m));
      else if (d.kind === "outil") setFil((f) => { const i = f.findIndex((m) => m.id === idA); const n = [...f]; n.splice(i < 0 ? n.length : i, 0, { role: "outil", outil: d.outil, decision: d.decision, texte: "", _t: Date.now() / 1000 }); return n; });
      else if (d.kind === "erreur") setFil((f) => [...f, { role: "erreur", texte: d.texte, _t: Date.now() / 1000 }]);
      else if (d.kind === "clos") { es.close(); stop(); setFil((f) => f.map((m) => m.id === idA ? { ...m, attente: null, perf: `⏱ réflexion ${d.reflexion_ms} ms · réponse ${d.reponse_ms} ms` } : m)); majJournal(); }
    };
    es.onerror = () => { es.close(); stop(); };
  }
  function envoyer(e) { e.preventDefault(); const p = prompt.trim(); if (!p || envoi) return; setPrompt(""); lancer(p); }

  async function rejouer() {
    setQaEnCours(true);
    try {
      let ref = null; try { ref = JSON.parse(localStorage.getItem("hermesweb.ref") || "null"); } catch { /* */ }
      const r = await hub("/qa/rejouer", { methode: "POST", corps: { reference: ref } });
      setQa(r); majJournal();
    } catch (x) { setErr(x.message); }
    setQaEnCours(false);
  }
  const figerRef = () => { if (qa?.avancement) { try { localStorage.setItem("hermesweb.ref", JSON.stringify(qa.avancement)); } catch { /* */ } rejouer(); } };

  function ouvrirReglages() { setRegCharg(true); hub("/reglages").then(setReg).catch((x) => { setErr(x.message); setRegCharg(false); }); }
  const fermerReglages = () => { setReg(null); setRegCharg(false); };
  async function sauverReglages(maj) {
    try { const r = await hub("/reglages", { methode: "PUT", corps: maj }); if (r.messages?.length) setErr(r.messages.join(" ; "));
      hub("/profil").then(setProfil).catch(() => {}); fermerReglages(); }
    catch (x) { setErr(x.message); }
  }
  function journalTexte() {
    return journal.slice().reverse().map((e) => {
      const t = msHeure(e.at);
      if (e.type === "prechauffage") return `${t}  préchauffage ${e.modele || ""} ${e.ok ? "OK" : "ECHEC"}`;
      if (e.type === "qa") return `${t}  QA ${e.cahier || ""} — ${e.pct}% (${e.ok}/${e.total})` + ((e.regressions || []).length ? ` régressions: ${e.regressions.join(", ")}` : "");
      const ou = (e.outils || []).map((o) => `${o.outil || "?"}:${o.decision || ""}`).join(" ");
      return `${t}  Q: ${e.prompt || ""}` + (ou ? `\n    outils: ${ou}` : "") + `\n    [${perfJournal(e).replace(/^· /, "")}${e.params ? " | ⚙ " + paramsTxt(e.params) : ""}]` + (e.reponse ? `\n    R: ${e.reponse}` : "") + ((e.erreurs || []).length ? `\n    ERR: ${e.erreurs.join(" | ")}` : "");
    }).join("\n");
  }
  async function copier() { const txt = journalTexte(); try { await navigator.clipboard.writeText(txt); } catch { const a = document.createElement("textarea"); a.value = txt; document.body.appendChild(a); a.select(); document.execCommand("copy"); a.remove(); } }
  function telecharger() { const b = new Blob([journalTexte()], { type: "text/plain" }); const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = `hermes-journal-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.txt`; a.click(); URL.revokeObjectURL(a.href); }

  function reprendre(p) { setPrompt(p || ""); champ.current?.focus(); }
  function poignee(ev) {
    ev.preventDefault(); const y0 = ev.clientY, h0 = consoleH || Math.round(window.innerHeight / 3);
    const mv = (e) => setConsoleH(Math.min(window.innerHeight * 0.8, Math.max(80, h0 + (y0 - e.clientY))));
    const up = () => { document.removeEventListener("mousemove", mv); document.removeEventListener("mouseup", up); try { localStorage.setItem("hermesweb.consoleH", String(consoleHRef.current)); } catch { /* */ } };
    document.addEventListener("mousemove", mv); document.addEventListener("mouseup", up);
  }
  const consoleHRef = useRef(consoleH); consoleHRef.current = consoleH;

  // questions récentes, uniques, plus récentes d'abord
  const questions = (() => { const out = [], vus = new Set(); for (let i = journal.length - 1; i >= 0; i--) { const e = journal[i]; if (e.type !== "chat" || !e.prompt || vus.has(e.prompt)) continue; vus.add(e.prompt); out.push(e.prompt); } return out.slice(0, 20); })();

  const ro = profil?.profil?.lecture_seule;
  return (
    <div className="hw">
      <div className="hw-bar">
        {onBack && <button type="button" className="secondary petit" onClick={onBack}>← Retour</button>}
        <b>☤ Hermes</b> <span className="hw-mut">{profil?.titre || ""}</span>
        <span className="hw-esp" />
        {profil && <span className={`hw-tag ${ro ? "ro" : "rw"}`}>{ro ? "lecture seule — " : ""}profil {profil.profil.nom}</span>}
        {profil && <span className="hw-mut"> v{profil.version} · moteur {profil.moteur}</span>}
        <button className="secondary petit" style={{ marginLeft: 8 }} title="réglages" onClick={ouvrirReglages} disabled={regCharg && !reg}>{regCharg && !reg ? "…" : "⚙"}</button>
      </div>
      {err && <p className="hw-err" onClick={() => setErr("")}>{err}</p>}
      {regCharg && !reg && <div onClick={fermerReglages} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.5)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}><div style={{ background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 10, padding: 18 }} className="hw-mut">chargement des réglages…</div></div>}
      {reg && <Reglages data={reg} onClose={fermerReglages} onSave={sauverReglages} />}
      <div className="hw-grille">
        <section className="hw-chat">
          <div className="hw-fil" ref={filRef}>{fil.length ? fil.map((e, i) => <Bulle key={e.id || i} e={e} />) : <p className="hw-mut">Demande à l'agent — les actions passent par les garde-fous du hub.</p>}</div>
          <form onSubmit={envoyer} className="hw-saisie">
            <textarea ref={champ} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Demande à l'agent…" rows={2}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) envoyer(e); }} />
            <button disabled={envoi}>{envoi ? "…" : "Envoyer"}</button>
          </form>
        </section>
        <aside className="hw-qa">
          <h4>Rejeu QA <span className="hw-mut">— clé de voûte</span></h4>
          <p className="hw-mut">Rejoue le cahier pour situer l'avancement et repérer les régressions depuis la référence.</p>
          <div className="hw-ligne"><button onClick={rejouer} disabled={qaEnCours}>{qaEnCours ? "rejeu…" : "Rejouer le cahier"}</button>
            <button className="secondary" onClick={figerRef} disabled={!qa}>Figer réf.</button></div>
          {qa?.avancement && (() => { const a = qa.avancement, c = qa.comparaison; return (
            <div className="hw-qares">
              <div><b>{a.pct}%</b> <span className="hw-mut">({a.ok}/{a.total})</span>
                <div className="hw-jauge"><div style={{ width: `${a.pct}%`, background: a.pct >= 80 ? "var(--ok)" : a.pct >= 50 ? "var(--warning)" : "var(--danger)" }} /></div></div>
              {c && <div className="hw-mut">{c.regressions.length ? <span className="bad">▼ {c.regressions.length} régression(s) : {c.regressions.join(", ")}</span> : <span className="ok">✓ aucune régression</span>} · Δ {c.delta_pct > 0 ? "+" : ""}{c.delta_pct} pt</div>}
              {a.criteres.map((x) => <div key={x.id} className="hw-crit"><span className="hw-pt" style={{ background: x.ok ? "var(--ok)" : "var(--danger)" }} /><span><b>{x.id}</b> <span className="hw-mut">[{x.cas}]</span> — {x.detail}</span></div>)}
            </div>); })()}
          <h4 style={{ marginTop: 16 }}>Questions <span className="hw-mut">récentes — clic = reprendre, ▶ = rejouer</span></h4>
          {!questions.length && <p className="hw-mut">—</p>}
          {questions.map((q, i) => (
            <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start", padding: "2px 0", borderBottom: "1px solid var(--border)", fontSize: ".82rem" }}>
              <button className="secondary petit" title="rejouer maintenant" onClick={() => lancer(q)}>▶</button>
              <span style={{ cursor: "pointer" }} title="reprendre dans le champ" onClick={() => reprendre(q)}>{q.slice(0, 70)}</span>
            </div>
          ))}
        </aside>
      </div>
      <div style={{ height: 7, cursor: "ns-resize", background: "var(--border)" }} title="glisser pour régler la hauteur" onMouseDown={poignee} />
      <section className="hw-console" style={consoleH ? { height: consoleH, maxHeight: "none" } : undefined}>
        <h4>Console d'activité Hermes <span className="hw-mut">· {journal.length} dernières</span>
          <span className="hw-esp2"><button className="secondary petit" onClick={copier}>Copier</button> <button className="secondary petit" onClick={telecharger}>⤓</button></span></h4>
        <div className="hw-jl">
          {!journal.length && <p className="hw-mut">Aucune activité pour l'instant.</p>}
          {journal.slice().reverse().map((e, i) => {
            const h = <span className="hw-h">{msHeure(e.at)}</span>;
            if (e.type === "prechauffage") return <div key={i} className="hw-l">{h} <span className="hw-mut">préchauffage {e.modele} {e.ok ? <span className="ok">✓ en VRAM</span> : <span className="bad">✗ échec</span>}</span></div>;
            if (e.type === "qa") return <div key={i} className="hw-l">{h} <span className="acc">QA</span> {e.cahier} — <b>{e.pct}%</b> ({e.ok}/{e.total}){(e.regressions || []).length ? <span className="bad"> ▼ {e.regressions.length}</span> : null}</div>;
            return <div key={i} className="hw-l">{h} <span className="hw-repr" title="reprendre" onClick={() => reprendre(e.prompt)}>↻</span>
              <span className="hw-q" title="reprendre cette question" onClick={() => reprendre(e.prompt)}>{(e.prompt || "").slice(0, 120)}</span>
              {(e.outils || []).map((o, j) => <span key={j} className={DEC[o.decision]?.[1] || "mut"}> ⚙{o.outil}{o.decision ? ":" + o.decision : ""}</span>)}
              <span className="hw-mut"> {perfJournal(e)}</span>
              {e.params && <span className="hw-mut" title="réglage actif pour cette question"> · ⚙ {paramsTxt(e.params)}</span>}
              {e.reponse && <span className="hw-rep">↳ {e.reponse.slice(0, 400)}</span>}
              {(e.erreurs || []).length ? <span className="bad"> ⚠ {e.erreurs[0].slice(0, 80)}</span> : null}</div>;
          })}
        </div>
      </section>
    </div>
  );
}
