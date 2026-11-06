// Tuile « Démonstrations » (livraison #984) : générer une visite automatisée du hub selon un parcours (Idruide, suivi
// d'un terminal, VLAN et SSID…), suivre la génération, ouvrir le diaporama en ligne ou télécharger le PowerPoint.
// API : services-api /demos (parcours, visites), /demos/lancer (job de la tour), /demos/<dossier>/<fichier>.
import { useCallback, useEffect, useState } from "react";
import BoutonDetail from "./FenetreTexte.jsx";

export default function DemosView({ onBack, apiBase, accessToken }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [vars, setVars] = useState({});           // {parcours: {nom: valeur}}
  const [jobs, setJobs] = useState({});           // {parcours: {id, status, log}}
  const [apercus, setApercus] = useState({});     // {dossier: blobURL}
  const entete = { Authorization: `Bearer ${accessToken}` };

  const charger = useCallback(async () => {
    try {
      const r = await fetch(`${apiBase}/demos`, { headers: { Authorization: `Bearer ${accessToken}` } });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || r.status);
      setD(j); setErr(null);
    } catch (e) { setErr(e.message); }
  }, [apiBase, accessToken]);
  useEffect(() => { charger(); }, [charger]);

  useEffect(() => {   // première capture de chaque visite, en vignette
    (d?.visites || []).slice(0, 12).forEach((v) => {
      if (!v.apercu || apercus[v.dossier]) return;
      fetch(`${apiBase}/demos/${v.dossier}/${v.apercu}`, { headers: entete }).then((r) => (r.ok ? r.blob() : null))
        .then((b) => b && setApercus((a) => ({ ...a, [v.dossier]: URL.createObjectURL(b) }))).catch(() => {});
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d]);

  const suivre = (pid, id) => {
    const t = setInterval(async () => {
      try {
        const r = await fetch(`${apiBase}/jobs/${id}`, { headers: entete });
        const j = await r.json();
        setJobs((x) => ({ ...x, [pid]: { id, status: j.status, log: j.log || [] } }));
        if (j.status && j.status !== "running") { clearInterval(t); charger(); }
      } catch { /* on réessaie au tour suivant */ }
    }, 4000);
  };
  const lancer = async (p) => {
    setJobs((x) => ({ ...x, [p.id]: { status: "envoi" } }));
    try {
      const r = await fetch(`${apiBase}/demos/lancer`, { method: "POST", headers: { ...entete, "Content-Type": "application/json" },
        body: JSON.stringify({ parcours: p.id, variables: { ...p.variables, ...(vars[p.id] || {}) } }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || r.status);
      setJobs((x) => ({ ...x, [p.id]: { id: j.id, status: "running", log: [] } }));
      suivre(p.id, j.id);
    } catch (e) { setJobs((x) => ({ ...x, [p.id]: { status: "failed", log: [String(e.message)] } })); }
  };
  const ouvrir = async (v) => {
    const w = window.open("", "_blank");   // ouvert tout de suite : sinon bloqué comme fenêtre surgissante
    try {
      const r = await fetch(`${apiBase}/demos/${v.dossier}/diaporama.html`, { headers: entete });
      if (!r.ok) throw new Error(r.status);
      const b = await r.blob();
      if (w) w.location = URL.createObjectURL(new Blob([b], { type: "text/html" }));
    } catch (e) { if (w) w.close(); setErr(`diaporama : ${e.message}`); }
  };
  const telecharger = async (v, nom) => {
    const r = await fetch(`${apiBase}/demos/${v.dossier}/${nom}`, { headers: entete });
    if (!r.ok) { setErr(`${nom} : ${r.status}`); return; }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await r.blob()); a.download = nom.endsWith(".pptx") ? nom : `${v.dossier}-${nom}`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };

  const etat = (j) => (!j ? null : j.status === "envoi" ? "⏳ envoi…" : j.status === "running" ? "⏳ visite en cours (1 à 3 min)…" : j.status === "done" ? "✓ terminée" : "✗ échec");

  return (
    <section className="view">
      <header className="view-header" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <h1 style={{ margin: 0 }}>🎞 Démonstrations</h1>
        <button type="button" className="secondary" onClick={charger}>↻</button>
      </header>
      <p className="muted">Visite automatisée des écrans selon un parcours thématique, enregistrée en captures : diaporama en ligne (un fichier autonome) et présentation PowerPoint. À relancer à chaque grande évolution. Compte de démonstration et adresse du hub : <code>DEMO_USER</code>, <code>DEMO_PASSWORD</code>, <code>DEMO_HUB_URL</code> dans le .env du serveur.</p>
      {err && <p className="error">{err}</p>}

      <h3>Parcours</h3>
      <table className="table"><thead><tr><th>Parcours</th><th>Étapes</th><th>Variables</th><th /></tr></thead><tbody>
        {(d?.parcours || []).map((p) => {
          const j = jobs[p.id];
          return (
            <tr key={p.id}>
              <td><strong>{p.titre}</strong><div className="muted" style={{ fontSize: 12 }}>{p.sous_titre}</div></td>
              <td>{p.etapes}</td>
              <td>{Object.entries(p.variables || {}).map(([k, v0]) => (
                <label key={k} style={{ display: "block", fontSize: 12 }}>{k} <input value={vars[p.id]?.[k] ?? v0} onChange={(e) => setVars((x) => ({ ...x, [p.id]: { ...(x[p.id] || {}), [k]: e.target.value } }))} style={{ width: 140 }} /></label>
              ))}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                <button type="button" onClick={() => lancer(p)} disabled={j && ["envoi", "running"].includes(j.status)}>{j && ["envoi", "running"].includes(j.status) ? etat(j) : "▶ Générer"}</button>
                {j && !["envoi", "running"].includes(j.status) && <> <span className={j.status === "done" ? "ok" : "error"}>{etat(j)}</span></>}
                {j?.log?.length > 0 && <> <BoutonDetail texte={j.log.join("\n")} titre={`Journal : ${p.titre}`} urgence={j.status === "failed" ? "alerte" : "info"} libelle="journal" /></>}
              </td>
            </tr>
          );
        })}
        {d && !d.parcours.length && <tr><td colSpan={4} className="muted">aucun parcours dans demo/parcours</td></tr>}
      </tbody></table>

      <h3>Visites générées</h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
        {(d?.visites || []).map((v) => (
          <div key={v.dossier} className="hub-card" style={{ margin: 0, padding: 10 }}>
            {apercus[v.dossier] ? <img src={apercus[v.dossier]} alt="" style={{ width: "100%", borderRadius: 6, cursor: "pointer" }} onClick={() => ouvrir(v)} /> : <div className="muted" style={{ height: 60 }}>…</div>}
            <strong>{v.titre}</strong>
            <div className="muted" style={{ fontSize: 12 }}>{v.date}{v.livraison ? ` · livraison #${v.livraison}` : ""} · {v.etapes} écran(s)
              {v.remarques?.length > 0 && <> <BoutonDetail texte={v.remarques.join("\n")} titre={`Éléments introuvables pendant la visite ${v.dossier}`} urgence="alerte" libelle={`⚠ ${v.remarques.length}`} /></>}</div>
            <p style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "6px 0 0" }}>
              {v.diaporama && <button type="button" onClick={() => ouvrir(v)}>▶ Diaporama</button>}
              {v.pptx && <button type="button" className="secondary" onClick={() => telecharger(v, v.pptx)}>⬇ PowerPoint</button>}
              {v.diaporama && <button type="button" className="secondary" onClick={() => telecharger(v, "diaporama.html")} title="fichier autonome : à envoyer ou ouvrir hors du hub">⬇ HTML</button>}
            </p>
          </div>
        ))}
        {d && !d.visites.length && <p className="muted">aucune visite générée : « ▶ Générer » sur un parcours</p>}
      </div>
    </section>
  );
}
