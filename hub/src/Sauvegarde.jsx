// #930 : onglet « Sauvegarde » d'un poste -- sauvegarde des configurations logicielles (registre + dossiers AppData)
// et des montages (lecteurs/partages/imprimantes -> remonter.cmd), en archive écrite sur clé USB et/ou partage réseau.
// La liste des confs ne contient aucun secret ; les identifiants du partage viennent du coffre (nom d'accès seulement).
// La restauration (réimport) sera une opération d'intervention, livrée après.
import { useCallback, useEffect, useState } from "react";
import { fetchSauvegardeReglage, saveSauvegardeReglage, runSauvegarde, fetchSauvegarde } from "./siAgentClient.js";
import { octets, lignes, depuisLignes, resume } from "./sauvegardeLib.js";
import BoutonDetail from "./FenetreTexte.jsx";

function Editeur({ base, actor }) {
  const [reg, setReg] = useState(null);
  const [cat, setCat] = useState([]);
  const [msg, setMsg] = useState("");
  useEffect(() => { fetchSauvegardeReglage(base).then((r) => { if (r && !r.error) { setReg({ confs: r.reglage?.confs || [], inclure_catalogue: r.reglage?.inclure_catalogue !== false, inclure_deduit: !!r.reglage?.inclure_deduit }); setCat(r.catalogue || []); } }); }, [base]);
  if (!reg) return <p className="infra-muted">lecture…</p>;
  const majConf = (i, f) => setReg({ ...reg, confs: reg.confs.map((c, k) => (k === i ? f(c) : c)) });
  const enregistrer = async () => {
    const confs = reg.confs.map((c) => ({ app: (c.app || "").trim(), cles: depuisLignes(c.cles), dossiers: depuisLignes(c.dossiers) })).filter((c) => c.app);
    const r = await saveSauvegardeReglage(base, { confs, inclure_catalogue: reg.inclure_catalogue, inclure_deduit: reg.inclure_deduit, actor });
    setMsg(r?.error ? r.error : `Enregistré (${(r.reglage?.confs || []).length} appli(s) personnalisée(s)).`);
  };
  return (
    <div className="infra-card" style={{ marginTop: 8 }}>
      <b>Que sauvegarder</b>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "6px 0" }}>
        <label className="ups-form-check"><input type="checkbox" checked={reg.inclure_catalogue} onChange={(e) => setReg({ ...reg, inclure_catalogue: e.target.checked })} /> Catalogue par défaut ({cat.length} applis courantes)</label>
        <label className="ups-form-check"><input type="checkbox" checked={reg.inclure_deduit} onChange={(e) => setReg({ ...reg, inclure_deduit: e.target.checked })} /> Déduire des logiciels relevés sur le poste</label>
      </div>
      {msg && <p className={`np-tone ${/Enregistré/.test(msg) ? "good" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}
      <div style={{ maxHeight: 280, overflow: "auto" }}>
        <table className="infra-table">
          <thead><tr><th>Application</th><th>Clés de registre (une par ligne)</th><th>Dossiers de config (une par ligne)</th><th /></tr></thead>
          <tbody>
            {reg.confs.length === 0 && <tr><td colSpan={4} className="infra-muted">Aucune application personnalisée. Le catalogue par défaut suffit souvent ; ajoute ici tes applications maison.</td></tr>}
            {reg.confs.map((c, i) => (
              <tr key={i}>
                <td><input value={c.app || ""} onChange={(e) => majConf(i, (x) => ({ ...x, app: e.target.value }))} style={{ width: 120 }} placeholder="Mon appli" /></td>
                <td><textarea value={typeof c.cles === "string" ? c.cles : lignes(c.cles)} onChange={(e) => majConf(i, (x) => ({ ...x, cles: e.target.value }))} rows={2} style={{ width: 240 }} spellCheck={false} placeholder={"HKCU\\Software\\MonAppli"} /></td>
                <td><textarea value={typeof c.dossiers === "string" ? c.dossiers : lignes(c.dossiers)} onChange={(e) => majConf(i, (x) => ({ ...x, dossiers: e.target.value }))} rows={2} style={{ width: 240 }} spellCheck={false} placeholder={"%APPDATA%\\MonAppli"} /></td>
                <td><button type="button" className="secondary" onClick={() => setReg({ ...reg, confs: reg.confs.filter((_, k) => k !== i) })}>✕</button></td>
              </tr>))}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        <button type="button" className="secondary" onClick={() => setReg({ ...reg, confs: [...reg.confs, { app: "", cles: "", dossiers: "" }] })}>+ une application</button>
        <button type="button" className="primary" onClick={enregistrer}>Enregistrer</button>
      </div>
      <details style={{ marginTop: 8 }}>
        <summary className="infra-muted" style={{ cursor: "pointer" }}>Voir le catalogue par défaut ({cat.length})</summary>
        <table className="infra-table" style={{ marginTop: 4 }}><thead><tr><th>Application</th><th>Clés</th><th>Dossiers</th></tr></thead>
          <tbody>{cat.map((c, i) => <tr key={i}><td>{c.app}</td><td className="infra-muted" style={{ fontSize: 12 }}>{(c.cles || []).join(", ") || "—"}</td><td className="infra-muted" style={{ fontSize: 12 }}>{(c.dossiers || []).join(", ") || "—"}</td></tr>)}</tbody>
        </table>
      </details>
    </div>
  );
}

function Resultat({ resultat, at }) {
  if (!resultat) return <p className="infra-muted">Aucune sauvegarde encore. « Lancer » produit l'archive (confs + montages) et l'écrit sur les destinations choisies.</p>;
  const s = resume(resultat);
  const dest = resultat.destinations || [];
  return (
    <div style={{ marginTop: 8 }}>
      <div className="infra-muted" style={{ marginBottom: 4 }}>Dernière sauvegarde : {at ? new Date(at).toLocaleString("fr-FR") : "—"}</div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 6 }}>
        <span>{s.apps} application(s), {s.cles} clé(s)</span>
        <span>confs {octets(s.octetsConfs)} · dossiers {octets(s.octetsDossiers)}</span>
        {s.archive && <span className="np-tone good">archive {s.archive.nom} ({octets(s.archive.octets)})</span>}
      </div>
      <table className="infra-table">
        <thead><tr><th>Destination</th><th>Cible</th><th>État</th></tr></thead>
        <tbody>
          {dest.length === 0 && <tr><td colSpan={3} className="infra-muted">aucune destination écrite</td></tr>}
          {dest.map((d, i) => (
            <tr key={i}><td>{d.type === "usb" ? "Clé USB" : "Partage réseau"}</td><td><code>{d.cible}</code></td>
              <td>{d.ok ? <span className="np-tone good">écrite</span> : <span className="np-tone bad">échec {d.erreur && <BoutonDetail titre={`Échec écriture ${d.type}`} urgence="critique" texte={d.erreur} />}</span>}</td></tr>))}
        </tbody>
      </table>
      {(resultat.alerts || []).length > 0 && <div style={{ marginTop: 6 }}>{resultat.alerts.map((a, i) => <div key={i} className={`np-tone ${a.severity === "critical" ? "bad" : a.severity === "warning" ? "warn" : "neutral"}`}>• {a.message}</div>)}</div>}
    </div>
  );
}

export default function Sauvegarde({ agent, base, actor }) {
  const [res, setRes] = useState(null);
  const [usb, setUsb] = useState("");
  const [unc, setUnc] = useState("");
  const [acces, setAcces] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [edite, setEdite] = useState(false);
  const charger = useCallback(() => fetchSauvegarde(base, agent).then((r) => { if (r && !r.error) setRes(r); }), [base, agent]);
  useEffect(() => { setRes(null); charger(); }, [charger]);
  const lancer = async () => {
    const destinations = {};
    if (usb.trim()) destinations.usb = usb.trim();
    if (unc.trim()) destinations.unc = { chemin: unc.trim(), acces: acces.trim() };
    setBusy(true); setMsg("");
    const r = await runSauvegarde(base, agent, { destinations, actor });
    setBusy(false);
    if (r?.error) { setMsg(r.error); return; }
    setMsg(`Sauvegarde envoyée : ${r.confs} application(s), ${r.montages.lecteurs} lecteur(s), ${r.montages.partages} partage(s)${r.coffre_indisponible ? " — accès coffre indisponible (partage écrit sans identifiants)" : ""}${r.note_poste_windows ? " — " + r.note_poste_windows : ""}. Résultat dans ~1 min.`);
    let n = 0; const t = setInterval(() => { n += 1; charger(); if (n >= 12) clearInterval(t); }, 6000);
  };
  return (
    <div>
      <p className="infra-muted" style={{ margin: "0 0 8px" }}>
        Sauvegarde, en vue d'une réinstallation, des <b>configurations logicielles</b> (clés de registre + dossiers de config)
        et des <b>montages</b> (lecteurs réseau, partages servis, imprimantes → <code>remonter.cmd</code>), en une archive
        écrite sur une clé USB et/ou un partage réseau. Lecture seule sur le poste ; la restauration viendra après.
      </p>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 6 }}>
        <label>Clé USB (lettre/dossier)<br /><input value={usb} onChange={(e) => setUsb(e.target.value)} placeholder="E:\sauvegardes" style={{ width: 150 }} /></label>
        <label>Partage réseau (UNC)<br /><input value={unc} onChange={(e) => setUnc(e.target.value)} placeholder={"\\\\nas\\sauvegardes"} style={{ width: 200 }} /></label>
        <label title="nom d'un accès du coffre « Accès d'équipements » ; laissé vide = session courante de l'agent">Accès coffre (partage)<br /><input value={acces} onChange={(e) => setAcces(e.target.value)} placeholder="nas-superv" style={{ width: 130 }} disabled={!unc.trim()} /></label>
        <button type="button" className="primary" disabled={busy} onClick={lancer}>▶ Lancer la sauvegarde</button>
        <button type="button" className="secondary" onClick={() => setEdite((v) => !v)}>{edite ? "Masquer « que sauvegarder »" : "Que sauvegarder"}</button>
        <button type="button" className="secondary" onClick={charger}>⟳</button>
      </div>
      {msg && <p className={`np-tone ${/envoyée/.test(msg) ? "neutral" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}
      {edite && <Editeur base={base} actor={actor} />}
      <Resultat resultat={res?.resultat} at={res?.at} />
    </div>
  );
}
