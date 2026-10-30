// #930 : onglet « Sauvegarde » d'un poste -- sauvegarde des configurations logicielles (registre + dossiers AppData)
// et des montages (lecteurs/partages/imprimantes -> remonter.cmd), en archive écrite sur clé USB et/ou partage réseau.
// La liste des confs ne contient aucun secret ; les identifiants du partage viennent du coffre (nom d'accès seulement).
// La restauration (réimport) sera une opération d'intervention, livrée après.
import { useCallback, useEffect, useState } from "react";
import { fetchSauvegardeReglage, saveSauvegardeReglage, runSauvegarde, fetchSauvegarde,
  fetchSauvegardePbsReglage, saveSauvegardePbsReglage, runSauvegardePbs, fetchSauvegardePbs,
  runRestauration, fetchRestauration } from "./siAgentClient.js";
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

// #931 : poussée de l'archive vers Proxmox Backup Server (pbs10), par l'agent du serveur PBS. Réglage partagé
// (pousseur, dépôt, espace de noms, empreinte, nom d'accès du coffre pour le jeton, chemin du partage côté PBS) ;
// le secret du jeton reste au coffre. Préflight en lecture seule avant toute écriture.
function SectionPbs({ agent, base, actor }) {
  const [reg, setReg] = useState(null);
  const [res, setRes] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const charger = useCallback(() => fetchSauvegardePbs(base, agent).then((r) => { if (r && !r.error) setRes(r); }), [base, agent]);
  useEffect(() => { fetchSauvegardePbsReglage(base).then((r) => { if (r && !r.error) setReg(r.reglage); }); charger(); }, [base, charger]);
  if (!reg) return <p className="infra-muted">lecture…</p>;
  const champ = (cle, lib, ph, large) => (
    <label>{lib}<br /><input value={reg[cle] || ""} onChange={(e) => setReg({ ...reg, [cle]: e.target.value })} placeholder={ph} style={{ width: large ? 320 : 150 }} /></label>);
  const enregistrer = async () => { const r = await saveSauvegardePbsReglage(base, { ...reg, actor }); setMsg(r?.error ? r.error : "Réglage PBS enregistré."); };
  const action = async (act) => {
    setBusy(true); setMsg("");
    const r = await runSauvegardePbs(base, agent, { action: act, actor });
    setBusy(false);
    if (r?.error) { setMsg(r.error); return; }
    setMsg(act === "preflight" ? "Préflight envoyé (lecture seule) — résultat dans ~1 min." : `Poussée envoyée (archive ${r.archive}) — résultat dans ~1 min.`);
    let n = 0; const t = setInterval(() => { n += 1; charger(); if (n >= 12) clearInterval(t); }, 6000);
  };
  const d = res?.resultat;
  return (
    <div className="infra-card" style={{ marginTop: 10 }}>
      <b>Pousser vers PBS (pbs10)</b>
      <p className="infra-muted" style={{ margin: "4px 0", fontSize: 12 }}>
        L'archive écrite sur le partage de pbs10 est poussée dans le datastore (un snapshot <code>host/&lt;poste&gt;</code>, espace de noms « postes »)
        par l'agent du serveur PBS. Le secret du jeton d'API reste au coffre « Accès d'équipements » (seul son nom d'accès est réglé ici).
      </p>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        {champ("pousseur", "Agent du serveur PBS", "pbs10")}
        {champ("repository", "Dépôt (repository)", "user@pbs!jeton@pbs10:backup", true)}
        {champ("namespace", "Espace de noms", "postes")}
        {champ("acces", "Accès coffre (jeton)", "pbs-postes")}
        {champ("fingerprint", "Empreinte (fingerprint)", "AB:CD:…")}
        {champ("base_partage", "Chemin du partage côté PBS", "/mnt/sauvegardes", true)}
      </div>
      {msg && <p className={`np-tone ${/enregistré|envoyé/i.test(msg) ? "neutral" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}
      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        <button type="button" className="secondary" onClick={enregistrer}>Enregistrer le réglage</button>
        <button type="button" className="secondary" disabled={busy} onClick={() => action("preflight")} title="vérifie l'accès au PBS sans rien écrire">Préflight (lecture seule)</button>
        <button type="button" className="primary" disabled={busy} onClick={() => action("push")} title="pousse la dernière archive de ce poste vers PBS">▶ Pousser la dernière sauvegarde</button>
        <button type="button" className="secondary" onClick={charger}>⟳</button>
      </div>
      {d && (
        <div style={{ marginTop: 6 }}>
          <span className="infra-muted">Dernière poussée {res.at ? new Date(res.at).toLocaleString("fr-FR") : ""} : </span>
          {d.ok ? <span className="np-tone good">ok{d.snapshot ? ` — ${d.snapshot}` : ""}</span>
            : <span className="np-tone bad">échec {d.erreur && <BoutonDetail titre="Échec poussée PBS" urgence="critique" texte={d.erreur} />}</span>}
        </div>)}
    </div>
  );
}

// #934 : restauration d'une sauvegarde sur le poste. Simulation = lecture seule (liste ce qui serait restauré) ;
// Appliquer = INTERVENTION (réimport du registre avec repli, remise des dossiers, remontage) -- exige l'autorisation
// « intervention » des commandes à distance (fiche de l'agent). La restauration est volontairement séparée et gatée.
function SectionRestauration({ agent, base, actor }) {
  const [chemin, setChemin] = useState("");
  const [opt, setOpt] = useState({ registre: true, appdata: true, montages: false });
  const [res, setRes] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const charger = useCallback(() => fetchRestauration(base, agent).then((r) => { if (r && !r.error) setRes(r); }), [base, agent]);
  useEffect(() => { charger(); }, [charger]);
  const lancer = async (mode) => {
    if (mode === "appliquer" && !window.confirm(`APPLIQUER la restauration sur ${agent} : le registre et les dossiers des applications seront ÉCRASÉS (un repli des clés est fait avant). Continuer ?`)) return;
    setBusy(true); setMsg("");
    const r = await runRestauration(base, agent, { mode, source: { chemin: chemin.trim() }, options: opt, actor });
    setBusy(false);
    if (r?.error) { setMsg(r.error); return; }
    setMsg(mode === "simulation" ? "Simulation envoyée (lecture seule) — résultat dans ~1 min." : "Restauration envoyée (intervention) — résultat dans ~1 min.");
    let n = 0; const t = setInterval(() => { n += 1; charger(); if (n >= 12) clearInterval(t); }, 6000);
  };
  const d = res?.resultat;
  return (
    <div className="infra-card" style={{ marginTop: 10 }}>
      <b>Restaurer une sauvegarde</b> <span className="np-tone warn" style={{ fontSize: 12 }}>opération d'intervention</span>
      <p className="infra-muted" style={{ margin: "4px 0", fontSize: 12 }}>
        Applique une archive de sauvegarde (clé USB ou partage accessible du poste) : réimport des clés de registre
        (avec repli des clés écrasées), remise des dossiers de config, remontage des lecteurs/partages. <b>Simuler</b> ne
        fait que lister ce qui serait restauré. <b>Appliquer</b> exige l'autorisation « intervention » (fiche de l'agent › Commandes à distance).
      </p>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
        <label>Archive (chemin sur le poste)<br /><input value={chemin} onChange={(e) => setChemin(e.target.value)} placeholder={"E:\\sauvegarde-pc-paul.zip"} style={{ width: 280 }} /></label>
        <label className="ups-form-check"><input type="checkbox" checked={opt.registre} onChange={(e) => setOpt({ ...opt, registre: e.target.checked })} /> Registre</label>
        <label className="ups-form-check"><input type="checkbox" checked={opt.appdata} onChange={(e) => setOpt({ ...opt, appdata: e.target.checked })} /> Dossiers AppData</label>
        <label className="ups-form-check"><input type="checkbox" checked={opt.montages} onChange={(e) => setOpt({ ...opt, montages: e.target.checked })} /> Montages</label>
      </div>
      {msg && <p className={`np-tone ${/envoyée/.test(msg) ? "neutral" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}
      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        <button type="button" className="secondary" disabled={busy || !chemin.trim()} onClick={() => lancer("simulation")}>Simuler (lecture seule)</button>
        <button type="button" className="danger" disabled={busy || !chemin.trim()} onClick={() => lancer("appliquer")}>⚠ Appliquer la restauration</button>
        <button type="button" className="secondary" onClick={charger}>⟳</button>
      </div>
      {d && (
        <div style={{ marginTop: 6 }}>
          <div className="infra-muted">Dernier résultat {res.at ? new Date(res.at).toLocaleString("fr-FR") : ""} — {d.simulation ? "simulation" : "application"} :</div>
          {d.simulation ? (
            <div>
              <div>{(d.confs || []).length} clé(s) de registre, {(d.dossiers || []).length} dossier(s), remontage {d.remonter ? "présent" : "absent"} dans l'archive.</div>
              {(d.dossiers || []).length > 0 && <div className="infra-muted" style={{ fontSize: 12 }}>{d.dossiers.map((x) => `${x.app} (${octets(x.octets)})`).join(", ")}</div>}
            </div>
          ) : (
            <div>
              <div>Registre : {(d.registre || []).filter((x) => x.ok).length}/{(d.registre || []).length} importées · Dossiers : {(d.dossiers || []).filter((x) => x.ok).length}/{(d.dossiers || []).length} · Montages : {d.montages ? (d.montages.ok ? "ok" : "échec") : "—"}</div>
              {d.rollback && <div className="infra-muted" style={{ fontSize: 12 }}>Repli des clés écrasées : <code>{d.rollback}</code></div>}
              {(d.alerts || []).map((a, i) => <div key={i} className={`np-tone ${a.severity === "critical" ? "bad" : "warn"}`}>• {a.message} {a.severity === "critical" && <BoutonDetail titre="Détail restauration" urgence="critique" texte={a.message} />}</div>)}
            </div>
          )}
        </div>)}
    </div>
  );
}

// #936 : sauvegarde IMAGE du disque système (scaffold : la capture d'image par l'agent arrive dans une livraison
// suivante -- wbadmin / image bloc vers un partage ou PBS). Explique le périmètre et ce qu'il faut préparer.
function SectionImage({ agent }) {
  return (
    <div className="infra-card" style={{ marginTop: 10 }}>
      <b>Sauvegarde image du disque</b> <span className="np-tone warn" style={{ fontSize: 12 }}>à venir</span>
      <p className="infra-muted" style={{ margin: "4px 0", fontSize: 13 }}>
        Image complète du disque système de <b>{agent}</b> (système + applications + données), restaurable telle quelle sur le même matériel.
        Complément de la sauvegarde « données » (confs + montages, réinstallation propre). Prévu : capture par l'agent
        (image système Windows ou image bloc) vers un partage du NAS ou pbs10, planifiable, avec vérification et conservation.
      </p>
      <p className="infra-muted" style={{ margin: 0, fontSize: 12 }}>Pour l'instant : utilise la sauvegarde « données » ci-dessus ; l'image sera ajoutée ici sans changer le reste.</p>
    </div>
  );
}

// #936 : clé USB de démarrage de secours (scaffold : le préparateur -- image de secours WinPE/Linux + outils de
// restauration, téléchargeable ou écrite sur la clé depuis le poste -- arrive dans une livraison suivante).
function SectionUsb({ agent }) {
  return (
    <div className="infra-card" style={{ marginTop: 10 }}>
      <b>Boot USB d'urgence</b> <span className="np-tone warn" style={{ fontSize: 12 }}>à venir</span>
      <p className="infra-muted" style={{ margin: "4px 0", fontSize: 13 }}>
        Clé USB de démarrage pour dépanner ou réinstaller <b>{agent}</b> quand Windows ne démarre plus : environnement de secours
        (WinPE ou Linux), outils disque/mémoire, et accès à la dernière sauvegarde (données ou image) pour restaurer.
        Prévu : préparation guidée depuis le hub (choix de la clé, écriture, vérification) et mise à jour de la clé quand la sauvegarde change.
      </p>
      <p className="infra-muted" style={{ margin: 0, fontSize: 12 }}>En attendant : garde une clé de secours à jour par poste critique ; je te guiderai pour la préparer à la main si besoin.</p>
    </div>
  );
}

export default function Sauvegarde({ agent, base, actor, mode }) {
  const [res, setRes] = useState(null);
  const [usb, setUsb] = useState("");
  const [unc, setUnc] = useState("");
  const [acces, setAcces] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [edite, setEdite] = useState(false);
  const [pbs, setPbs] = useState(false);
  const [restaure, setRestaure] = useState(false);
  const [image, setImage] = useState(mode === "image");     // #936
  const [secours, setSecours] = useState(mode === "usb");   // #936 : section « Boot USB d'urgence »
  useEffect(() => { setImage(mode === "image"); setSecours(mode === "usb"); }, [mode]);
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
        <button type="button" className="secondary" onClick={() => setPbs((v) => !v)}>{pbs ? "Masquer PBS" : "Pousser vers PBS"}</button>
        <button type="button" className="secondary" onClick={() => setRestaure((v) => !v)}>{restaure ? "Masquer restauration" : "Restaurer"}</button>
        <button type="button" className="secondary" onClick={() => setImage((v) => !v)}>{image ? "Masquer image" : "Sauvegarde image"}</button>
        <button type="button" className="secondary" onClick={() => setSecours((v) => !v)}>{secours ? "Masquer USB" : "Boot USB urgence"}</button>
        <button type="button" className="secondary" onClick={charger}>⟳</button>
      </div>
      {msg && <p className={`np-tone ${/envoyée/.test(msg) ? "neutral" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}
      {edite && <Editeur base={base} actor={actor} />}
      {pbs && <SectionPbs agent={agent} base={base} actor={actor} />}
      {restaure && <SectionRestauration agent={agent} base={base} actor={actor} />}
      {image && <SectionImage agent={agent} />}
      {secours && <SectionUsb agent={agent} />}
      <Resultat resultat={res?.resultat} at={res?.at} />
    </div>
  );
}
