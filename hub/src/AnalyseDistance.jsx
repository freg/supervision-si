// #919 : onglet « Analyse à distance » d'un poste -- commandes PowerShell passées par l'agent (lecture seule vérifiée
// sur le poste, ou intervention confirmée), sortie suivie en direct, verdicts matériel / système / viral du central.
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchShellAnalyses, fetchShellJob, fetchShellJobs, runShell, stopShell } from "./siAgentClient.js";
import { AXES, MODES, NIVEAUX, STATUTS, actif, date, duree, libelle, permis, refus } from "./shellDistance.js";
import { hubLink } from "./hubLinks.js";
import BoutonDetail from "./FenetreTexte.jsx";   // #923

function Ton({ table, cle }) {
  const [txt, ton] = libelle(table, cle);
  return <span className={`np-tone ${ton}`}>{txt}</span>;
}

function Interpretation({ it }) {
  if (!it) return null;
  return (
    <div className="sh-interp">
      <p className="sh-synthese">{it.synthese}</p>
      <div className="sh-axes">
        {AXES.map(([cle, titre]) => {
          const a = it.axes?.[cle] || { niveau: "rien", constats: [] };
          return (
            <section key={cle} className="infra-card">
              <h4 style={{ margin: "0 0 6px" }}>{titre} · <Ton table={NIVEAUX} cle={a.niveau} /></h4>
              {a.constats.length === 0 ? <div className="infra-muted">aucun constat</div> : (
                <ul className="sh-constats">{a.constats.map((c, k) => (
                  <li key={k}><span className={`np-tone ${libelle(NIVEAUX, c.niveau)[1]}`}>●</span> {c.texte}</li>))}</ul>)}
            </section>);
        })}
      </div>
    </div>
  );
}

function Detail({ base, agent, id, onRelancer }) {
  const [d, setD] = useState(null);
  const charger = useCallback(() => fetchShellJob(base, agent, id).then(setD), [base, agent, id]);
  useEffect(() => { setD(null); charger(); }, [charger]);
  const enCours = d?.job && actif(d.job.statut);
  useEffect(() => { if (!enCours) return undefined; const t = setInterval(charger, 2500); return () => clearInterval(t); }, [enCours, charger]);
  if (!d) return <p className="infra-muted">lecture…</p>;
  if (d.error) return <p className="np-tone bad">{d.error}</p>;
  const j = d.job;
  const motifs = refus(d.sortie);
  const copier = () => { try { navigator.clipboard.writeText(d.sortie || ""); } catch { /* presse-papiers indisponible */ } };
  return (
    <section className="infra-card sh-detail">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>{j.titre}</h3>
        <Ton table={STATUTS} cle={j.statut} />
        <span className="infra-muted">mode {j.mode} · {duree(j)}{j.par ? ` · par ${j.par}` : ""} · envoyée {date(j.envoye)}</span>
        <span style={{ flex: 1 }} />
        {enCours && <button type="button" className="secondary" onClick={() => stopShell(base, agent, id).then(charger)}>⏹ Interrompre</button>}
        <button type="button" className="secondary" onClick={() => onRelancer(j)}>↻ Relancer</button>
        <button type="button" className="secondary" onClick={copier} title="copier la sortie">Copier</button>
        <button type="button" className="secondary" onClick={charger}>⟳</button>
      </div>
      {j.motif && motifs.length === 0 && <p className={`np-tone ${j.statut === "fini" ? "neutral" : "bad"}`} style={{ margin: "6px 0" }}>{j.motif}</p>}
      {motifs.length > 0 && (
        <div className="sh-refus">
          <b>Refusée par la garde du poste (lecture seule)</b> — rien n'a été exécuté :
          <ul>{motifs.map((m, k) => <li key={k}>{m}</li>)}</ul>
          Pour l'exécuter quand même : mode <b>intervention</b> (à autoriser dans la fiche de l'agent).
        </div>)}
      <Interpretation it={d.interpretation} />
      {j.analyse && j.format === "json" && d.interpretation ? (
        <details><summary className="infra-muted">données brutes</summary><pre className="sh-sortie">{d.sortie}</pre></details>
      ) : (
        <>
          <h4 style={{ margin: "10px 0 4px" }}>Sortie {d.tronque && <span className="infra-muted">(fin seulement)</span>} {enCours && <span className="infra-muted">— en direct</span>}</h4>
          <pre className="sh-sortie">{d.sortie || (enCours ? "en attente de la première sortie…" : "(aucune sortie)")}</pre>
        </>
      )}
      <details><summary className="infra-muted">script envoyé</summary><pre className="sh-sortie">{j.script}</pre></details>
    </section>
  );
}

export default function AnalyseDistance({ agent, base, actor }) {
  const [analyses, setAnalyses] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [reglage, setReglage] = useState(null);
  const [sel, setSel] = useState("");
  const [script, setScript] = useState("");
  const [mode, setMode] = useState("lecture");
  const [delai, setDelai] = useState(300);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { fetchShellAnalyses(base).then((r) => setAnalyses(r?.analyses || [])); }, [base]);
  const charger = useCallback(() => fetchShellJobs(base, agent).then((r) => {
    if (r?.error) { setMsg(r.error); return; }
    setJobs(r.jobs || []); setReglage(r.remote_shell || "off");
  }), [base, agent]);
  useEffect(() => { setSel(""); setJobs([]); charger(); }, [charger]);
  const enCours = useMemo(() => jobs.some((j) => actif(j.statut)), [jobs]);
  useEffect(() => { if (!enCours) return undefined; const t = setInterval(charger, 3000); return () => clearInterval(t); }, [enCours, charger]);

  const lancer = async (body) => {
    if (body.mode === "intervention" && !window.confirm(`Mode INTERVENTION : la commande peut modifier le poste ${agent}. Elle sera journalisée à votre nom. Continuer ?`)) return;
    setBusy(true); setMsg("");
    const r = await runShell(base, agent, { ...body, actor });
    setBusy(false);
    if (r?.error) { setMsg(r.error); return; }
    setMsg("Commande envoyée — l'agent la prend à son prochain relevé (quelques secondes à 1 minute).");
    setSel(r.job); charger();
  };
  const relancer = (j) => (j.analyse ? lancer({ analyse: j.analyse }) : lancer({ script: j.script || script, mode: j.mode, delai: Number(delai) || 300 }));
  const off = reglage === "off";

  return (
    <div className="sh-page">
      <p style={{ margin: "0 0 8px" }}>
        Commandes à distance sur ce poste : {reglage ? <Ton table={MODES} cle={reglage} /> : <span className="infra-muted">…</span>}
        {" "}<span className="infra-muted">— réglage : <a href={hubLink("si-agent", { agent, section: "settings" })}>Agents › {agent} › Réglages</a> › « Commandes à distance ».
          En lecture seule, le poste vérifie lui-même avant d'exécuter que la commande ne modifie rien.</span>
      </p>
      {msg && <p className={`np-tone ${/envoyée/.test(msg) ? "neutral" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}

      <h4 style={{ margin: "10px 0 6px" }}>Analyses en un clic <span className="infra-muted">(lecture seule)</span></h4>
      <div className="sh-catalogue">
        {analyses.map((a) => (
          <div key={a.id} className="infra-card sh-analyse">
            <b>{a.titre}</b>
            <span className="infra-muted">{a.description}</span>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: "auto" }}>
              <button type="button" className="primary" disabled={busy || off || !reglage} onClick={() => lancer({ analyse: a.id })}>▶ Lancer</button>
              <span className="infra-muted">{a.delai >= 120 ? `${Math.round(a.delai / 60)} min max` : `${a.delai} s max`}</span>
            </div>
          </div>))}
      </div>

      <h4 style={{ margin: "14px 0 6px" }}>Commande libre (PowerShell)</h4>
      <textarea className="sh-script" rows={6} value={script} onChange={(e) => setScript(e.target.value)} spellCheck={false}
        placeholder={"Get-WinEvent -LogName System -MaxEvents 20 | Format-Table TimeCreated, Id, ProviderName, Message -Wrap"} />
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", margin: "6px 0" }}>
        <label>Mode <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="lecture">lecture seule</option>
          <option value="intervention" disabled={reglage !== "intervention"}>intervention{reglage !== "intervention" ? " (non autorisé)" : ""}</option>
        </select></label>
        <label>Délai <input type="number" min="5" max="3600" style={{ width: 70 }} value={delai} onChange={(e) => setDelai(e.target.value)} /> s</label>
        <button type="button" className={mode === "intervention" ? "danger" : "primary"} disabled={busy || !script.trim() || !permis(reglage, mode)}
          onClick={() => lancer({ script, mode, delai: Number(delai) || 300 })}>▶ Envoyer</button>
      </div>

      <div className="sh-grille">
        <div className="infra-table-wrap">
          <table className="infra-table">
            <thead><tr><th>Envoyée</th><th>Commande</th><th>Mode</th><th>Statut</th><th>Durée</th></tr></thead>
            <tbody>
              {jobs.length === 0 && <tr><td colSpan={5} className="infra-muted">aucune commande envoyée à ce poste</td></tr>}
              {jobs.map((j) => (
                <tr key={j.id} onClick={() => setSel(j.id)} style={{ cursor: "pointer", fontWeight: j.id === sel ? 600 : 400 }}>
                  <td>{date(j.envoye)}</td><td title={j.motif || ""}>{j.titre}{j.motif && <BoutonDetail titre={`Motif : ${j.titre}`} urgence={["refuse", "refuse_agent", "erreur", "delai"].includes(j.statut) ? "critique" : "alerte"} texte={j.motif} />}</td><td>{j.mode}</td>
                  <td><Ton table={STATUTS} cle={j.statut} /></td><td>{duree(j)}</td>
                </tr>))}
            </tbody>
          </table>
        </div>
        {sel ? <Detail key={sel} base={base} agent={agent} id={sel} onRelancer={relancer} /> : <p className="infra-muted">Choisir une commande pour voir sa sortie et son interprétation.</p>}
      </div>
    </div>
  );
}
