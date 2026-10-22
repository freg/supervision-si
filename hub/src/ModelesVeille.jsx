import { useCallback, useEffect, useState } from "react";
import { dateCourte } from "./veilleLib.js";

// #821 Parc IA, onglet « Veille des modèles » (même module que la tuile Modèles IA du hub maison) : veille des sorties (Hugging Face, éditeurs suivis) avec historique et alertes (nouveau modèle
// utilisable et pertinent, passage ouvert <-> fermé), usages des modèles des hôtes (cases à cocher, types d'usage), bancs.
const fmtTaille = (o) => (o == null ? "—" : o < 1048576 ? `${Math.round(o / 1024)} ko` : o < 1073741824 ? `${(o / 1048576).toFixed(0)} Mo` : `${(o / 1073741824).toFixed(1).replace(".", ",")} Go`);
let BASE = "";
async function api(path, { methode = "GET", corps } = {}) {
  const r = await fetch(`${BASE}${path}`, { method: methode, credentials: "include", headers: corps ? { "Content-Type": "application/json" } : undefined, body: corps ? JSON.stringify(corps) : undefined });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.error || j?.erreur || (r.status === 404 ? "HTTP 404 : si-agent-api sans la veille des modèles (#821) -- reconstruire si-agent-api" : `HTTP ${r.status}`));
  return j;
}
const ONGLETS = [["alertes", "Alertes"], ["veille", "Veille des sorties"], ["historique", "Historique"], ["mes", "Usages"], ["bancs", "Bancs et benchmarks"], ["reglages", "Réglages"]];
const EVT = { nouveau: "nouveau", ouverture: "↗ ouverture (licence plus libre)", fermeture: "↘ fermeture (licence plus restrictive)", licence: "licence changée",
  acces_restreint: "accès restreint (gated)", acces_libre: "accès libéré", disparu: "disparu / rendu privé", reapparu: "réapparu" };
const OUV = { 2: ["libre", "good"], 1: ["sous conditions", "warn"], 0: ["fermé / inconnu", "bad"] };
const hf = (id) => `https://huggingface.co/${id}`;

function Evenements({ liste, alertes, marquerVu }) {
  if (!liste.length) return <p className="infra-muted">{alertes ? "Aucune alerte : rien de nouveau d'utilisable, aucun passage ouvert / fermé." : "Rien sur la période."}</p>;
  return (
    <table className="infra-table">
      <thead><tr><th>Détecté</th><th>Modèle</th><th>Événement</th><th>Avant → après</th><th>Taille</th>{alertes && <th></th>}</tr></thead>
      <tbody>{liste.map((e) => (
        <tr key={e.id} className={e.alerte && !e.vu ? "veille-non-lu" : "veille-lu"}>
          <td><span className="infra-muted">{dateCourte(e.at)}</span>{e.cree ? <div><span className="infra-muted">publié {dateCourte(e.cree)}</span></div> : null}</td>
          <td><a href={hf(e.modele)} target="_blank" rel="noreferrer">{e.modele}</a> <span className="infra-muted">{e.pipeline || ""}</span></td>
          <td className={/fermeture|restreint|disparu/.test(e.evenement) ? "infra-status critical" : /ouverture|libre/.test(e.evenement) ? "infra-status good" : ""}>{EVT[e.evenement] || e.evenement}</td>
          <td><span className="infra-muted">{e.avant || "—"} → {e.apres || "—"}</span></td>
          <td><span className="infra-muted">{e.params_b ? `${e.params_b} B` : "—"}</span></td>
          {alertes && <td>{!e.vu && <button className="secondary" type="button" onClick={() => marquerVu([e.id])}>vu</button>}</td>}
        </tr>))}</tbody>
    </table>
  );
}

function Veille({ etat, setErr }) {
  const [f, setF] = useState({ jours: 90, utilisables: true, pertinents: true, variantes: false, ecartes: false, auteur: "", ouverture: "" });
  const [d, setD] = useState({ modeles: [], total: 0 });
  const charger = useCallback(() => {
    const p = new URLSearchParams({ jours: f.jours });
    for (const k of ["utilisables", "pertinents", "variantes", "ecartes"]) if (f[k]) p.set(k, "1");
    if (f.auteur) p.set("auteur", f.auteur);
    if (f.ouverture !== "") p.set("ouverture", f.ouverture);
    api(`/modeles/catalogue?${p}`).then(setD).catch((x) => setErr(x.message));
  }, [f, setErr]);
  useEffect(() => { charger(); }, [charger]);
  async function marquer(m, k) { try { await api("/modeles/marquer", { methode: "POST", corps: { id: m.id, [k]: !m[k] } }); charger(); } catch (x) { setErr(x.message); } }
  const case_ = (k, l) => <label key={k}><input type="checkbox" checked={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked })} /> {l}</label>;
  return (
    <div className="veille-bloc">
      <div className="veille-ligne">
        <select  value={f.jours} onChange={(e) => setF({ ...f, jours: Number(e.target.value) })}>{[[7, "7 jours"], [30, "30 jours"], [90, "90 jours"], [365, "1 an"], [3650, "tout"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <select  value={f.auteur} onChange={(e) => setF({ ...f, auteur: e.target.value })}><option value="">tous les éditeurs</option>{(etat?.auteurs || []).map((a) => <option key={a}>{a}</option>)}</select>
        <select  value={f.ouverture} onChange={(e) => setF({ ...f, ouverture: e.target.value })}><option value="">toute licence</option><option value="2">libre</option><option value="1">sous conditions</option><option value="0">fermé / inconnu</option></select>
        {case_("utilisables", "utilisables sur nos machines")}{case_("pertinents", "pertinents")}{case_("variantes", "variantes quantifiées")}{case_("ecartes", "écartés seulement")}
        <span style={{ flex: 1 }} /><span className="infra-muted">{d.total} modèle(s)</span>
      </div>
      <table className="infra-table">
        <thead><tr><th>Publié</th><th>Modèle</th><th>Type</th><th>Taille</th><th>VRAM Q4</th><th>Machines</th><th>Licence</th><th>Téléch.</th><th></th></tr></thead>
        <tbody>{d.modeles.map((m) => (
          <tr key={m.id} className={m.disparu ? "veille-lu" : ""}>
            <td><span className="infra-muted">{dateCourte(m.cree || m.premier_vu)}</span></td>
            <td><a href={hf(m.id)} target="_blank" rel="noreferrer">{m.id}</a>{m.disparu ? <span className="infra-muted"> · disparu</span> : null}{m.gated ? <span className="infra-muted"> · accès restreint</span> : null}</td>
            <td><span className="infra-muted">{m.pipeline || "—"}</span></td>
            <td><span className="infra-muted">{m.params_b ? `${m.params_b} B` : "—"}</span></td>
            <td><span className="infra-muted">{m.vram_q4 ? `${m.vram_q4} Go` : "—"}</span></td>
            <td><span className="infra-muted">{m.machines.join(", ") || "—"}</span></td>
            <td><span className={`np-tone ${OUV[m.ouverture || 0][1]}`} title={m.licence || "licence non déclarée"}>{OUV[m.ouverture || 0][0]}</span> <span className="infra-muted">{m.licence || ""}</span></td>
            <td><span className="infra-muted">{m.telechargements}</span></td>
            <td><div className="veille-actions">
              <button type="button" className="secondary" title="suivre (licence, accès, disparition vérifiés à chaque passage)" onClick={() => marquer(m, "suivi")}>{m.suivi ? "★" : "☆"}</button>
              <button className="secondary" type="button" title={m.ecarte ? "repêcher" : "ne plus présenter"} onClick={() => marquer(m, "ecarte")}>{m.ecarte ? "↺" : "✕"}</button>
            </div></td>
          </tr>))}
          {!d.modeles.length && <tr><td colSpan={9} className="infra-muted">Rien pour ces critères (relève toutes les 6 h par le service « cyber », ou « Relever maintenant » dans Réglages).</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function Mes({ setErr }) {
  const [d, setD] = useState(null);
  const charger = useCallback(() => { api("/modeles/mes").then(setD).catch((x) => setErr(x.message)); }, [setErr]);
  useEffect(() => { charger(); }, [charger]);
  async function regler(m, maj) {
    const x = { ...m, ...maj };
    try { await api("/modeles/mes", { methode: "POST", corps: { nom: x.nom, actif: x.actif, usages: x.usages, note: x.note } }); charger(); } catch (e) { setErr(e.message); }
  }
  if (!d) return <p className="infra-muted">chargement…</p>;
  const U = Object.entries(d.usages || {});
  return (
    <div className="veille-bloc">
      
      <p className="infra-muted">Modèles relevés par la sonde ollama de chaque hôte (« hôte/modèle ») : cochez ceux qui sont actifs et leurs usages. Inventaire déclaratif : les priorités de la page d'accueil gardent leur réglage du .env (branchement automatique : tranche suivante).</p>
      <table className="infra-table">
        <thead><tr><th>Actif</th><th>Modèle</th><th>Taille</th><th>Quantif.</th>{U.map(([k, l]) => <th key={k} title={l}><span className="infra-muted">{l.split(" (")[0]}</span></th>)}<th>Note</th></tr></thead>
        <tbody>{d.modeles.map((m) => (
          <tr key={m.nom} className={m.installe ? "" : "veille-lu"}>
            <td><input type="checkbox" checked={m.actif} onChange={(e) => regler(m, { actif: e.target.checked })} /></td>
            <td>{m.nom}{!m.installe && <span className="infra-muted"> · désinstallé</span>}</td>
            <td><span className="infra-muted">{m.taille ? fmtTaille(m.taille) : "—"}{m.parametres ? ` · ${m.parametres}` : ""}</span></td>
            <td><span className="infra-muted">{m.quantification || "—"}</span></td>
            {U.map(([k]) => <td key={k}><input type="checkbox" checked={m.usages.includes(k)} disabled={!m.actif}
              onChange={(e) => regler(m, { usages: e.target.checked ? [...m.usages, k] : m.usages.filter((u) => u !== k) })} /></td>)}
            <td><input defaultValue={m.note} placeholder="—" onBlur={(e) => e.target.value !== m.note && regler(m, { note: e.target.value })} /></td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

function Bancs({ setErr }) {
  const [d, setD] = useState(null);
  useEffect(() => { api("/modeles/bancs").then(setD).catch((x) => setErr(x.message)); }, [setErr]);
  if (!d) return <p className="infra-muted">chargement…</p>;
  return (
    <div className="veille-bloc">
      <p className="infra-muted">Résultats des bancs comparatifs déposés dans le dossier de données de si-agent-api (banc-*.json) ; les évaluations
        de l'assistant sont dans l'onglet « Tests (évaluations) ».</p>
      {!d.bancs.length && <p className="infra-muted">Aucun banc lancé pour l'instant.</p>}
      {d.bancs.map((b) => (
        <details key={b.fichier} open={b === d.bancs[0]}>
          <summary>{dateCourte(b.at)} — {b.articles} articles, référence {b.reference} <span className="infra-muted">({b.fichier})</span></summary>
          <table className="infra-table">
            <thead><tr><th>Modèle</th><th>Valides</th><th>Urgents</th><th>Accord urgent</th><th>Accord suite</th><th>Suivis gardés</th><th>Rejetés écartés</th><th>Stabilité</th><th>s / article</th></tr></thead>
            <tbody>{Object.entries(b.synthese).map(([m, s]) => (
              <tr key={m}><td>{m}{m === b.reference ? " (réf.)" : ""}</td><td>{s.valides}/{s.n}</td><td>{s.urgents}</td>
                {["accord_urgent", "accord_suite", "suivis_gardes", "rejetes_ecartes", "stabilite"].map((k) => <td key={k}>{s[k] == null ? "—" : `${Math.round(100 * s[k])} %`}</td>)}
                <td>{s.par_article}</td></tr>))}</tbody>
          </table>
        </details>))}
    </div>
  );
}

function Reglages({ etat, recharger, setErr }) {
  const [auteurs, setAuteurs] = useState("");
  const [attente, setAttente] = useState(false);
  useEffect(() => { setAuteurs((etat?.auteurs || []).join("\n")); }, [etat]);
  async function enregistrer() {
    try { await api("/modeles/auteurs", { methode: "PUT", corps: { auteurs: auteurs.split(/[\s,]+/).filter(Boolean) } }); recharger(); } catch (x) { setErr(x.message); }
  }
  async function relever() {
    setAttente(true);
    try { const r = await api("/modeles/relever", { methode: "POST", corps: {} }); if (Object.keys(r.erreurs || {}).length) setErr(`relève : ${Object.entries(r.erreurs).map(([k, v]) => `${k} : ${v}`).join(" ; ")}`); recharger(); } catch (x) { setErr(x.message); }
    setAttente(false);
  }
  const r = etat?.releve;
  return (
    <div className="veille-bloc">
      <div className="veille-ligne"><b>Relève</b><span className="infra-muted">{r ? `dernière ${dateCourte(r.at)} · ${r.evenements} événement(s)${Object.keys(r.erreurs || {}).length ? ` · ${Object.keys(r.erreurs).length} erreur(s)` : ""}` : "jamais"}</span>
        <button type="button" disabled={attente} onClick={relever}>{attente ? "relève…" : "Relever maintenant"}</button></div>
      {r && Object.keys(r.erreurs || {}).length > 0 && <ul>{Object.entries(r.erreurs).map(([k, v]) => <li key={k}><span className="infra-muted">{k} : {v}</span></li>)}</ul>}
      <div className="veille-ligne"><b>Machines</b><span className="infra-muted">{(etat?.machines || []).map((m) => `${m.nom} ${m.vram} Go`).join(" · ")} — réglage MODELES_MACHINES du .env (pas de lien : opération manuelle, éditer le .env puis <code>./scripts/run.sh up -d si-agent-api</code>)</span></div>
      <p><b>Éditeurs suivis</b> <span className="infra-muted">(identifiants Hugging Face, un par ligne)</span></p>
      <textarea rows={8} value={auteurs} onChange={(e) => setAuteurs(e.target.value)} />
      <div className="veille-ligne"><button type="button" onClick={enregistrer}>Enregistrer</button></div>
    </div>
  );
}

export default function ModelesVeille({ base }) {
  BASE = base || "";
  const [onglet, setOnglet] = useState(() => { try { return localStorage.getItem("iapark.modeles.onglet") || "alertes"; } catch { return "alertes"; } });
  const [etat, setEtat] = useState(null);
  const [err, setErr] = useState("");
  const [evts, setEvts] = useState([]);
  const charger = useCallback(() => { api("/modeles/etat").then(setEtat).catch((x) => setErr(x.message)); }, []);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => { try { localStorage.setItem("iapark.modeles.onglet", onglet); } catch { /* navigation privée */ } }, [onglet]);
  const chargerEvts = useCallback(() => {
    if (onglet !== "alertes" && onglet !== "historique") return;
    api(`/modeles/historique?jours=${onglet === "alertes" ? 90 : 3650}${onglet === "alertes" ? "&alertes=1" : ""}`).then((d) => setEvts(d.evenements)).catch((x) => setErr(x.message));
  }, [onglet]);
  useEffect(() => { chargerEvts(); }, [chargerEvts]);
  async function marquerVu(ids) {
    try { await api("/modeles/alertes/vu", { methode: "POST", corps: ids ? { ids } : { tout: true } }); chargerEvts(); charger(); } catch (x) { setErr(x.message); }
  }
  return (
    <div className="veille">
      <h3>Veille des modèles <span className="infra-muted">{etat ? `${etat.nb} modèle(s) en veille · ${etat.alertes} alerte(s) non vue(s)` : ""}</span></h3>
      {err && <p className="infra-error" onClick={() => setErr("")}>{err}</p>}
      <div className="infra-tabs">{ONGLETS.map(([id, t]) => <button key={id} type="button" className={onglet === id ? "active" : ""} onClick={() => setOnglet(id)}>{t}{id === "alertes" && etat?.alertes ? ` (${etat.alertes})` : ""}</button>)}</div>
      {onglet === "alertes" && <div className="veille-bloc"><div className="veille-ligne"><span className="infra-muted">Nouveaux modèles utilisables et pertinents, passages ouvert ↔ fermé, accès restreints, disparitions.</span><span style={{ flex: 1 }} />
        <button className="secondary" type="button" disabled={!evts.some((e) => !e.vu)} onClick={() => marquerVu(null)}>Tout marquer vu</button></div>
        <Evenements liste={evts} alertes marquerVu={marquerVu} /></div>}
      {onglet === "historique" && <div className="veille-bloc"><Evenements liste={evts} /></div>}
      {onglet === "veille" && <Veille etat={etat} setErr={setErr} />}
      {onglet === "mes" && <Mes setErr={setErr} />}
      {onglet === "bancs" && <Bancs setErr={setErr} />}
      {onglet === "reglages" && <Reglages etat={etat} recharger={charger} setErr={setErr} />}
    </div>
  );
}
