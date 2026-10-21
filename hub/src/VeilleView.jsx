// Tuile « Veille cyber » (livraison #814, BACKLOG 130 T1-T2) -- routes /veille de vuln-api.
// Alertes (CERT-FR, CISA KEV et avis), news (IA cyber, générales, France / Europe, règlements ANSSI / RGPD),
// et, propre au hub supervision : ce qui TOUCHE NOTRE SI (CVE présentes dans les constats de vuln-api, par actif),
// publics (RSSI, administrateurs, développeurs), suivi de traitement avec journal, diffusion par notify-api
// (alerte immédiate, synthèse quotidienne par public). Préfiltres python, php, linux, bsd, mikrotik + nos modèles,
// filtres enregistrés, extraction CSV / Markdown / JSON / Atom, explication et synthèse par l'IA locale.
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { basculer, chezNous, dateCourte, fmtEpss, paramsRegle, termes, ton } from "./veilleLib.js";

const ONGLETS = [
  ["alerte", "Alertes"], ["impacts", "Impacts SI"], ["ia", "IA cyber"], ["generale", "Générales"], ["france_europe", "France / Europe"],
  ["reglement", "Règlements ANSSI / RGPD"], ["filtres", "Filtres et extraction"], ["sources", "Sources et préfiltres"], ["journal", "Journal"],
];
const LISTES = new Set(["alerte", "impacts", "ia", "generale", "france_europe", "reglement"]);
const FORMATS = [["csv", "CSV"], ["md", "Markdown"], ["json", "JSON"], ["atom", "Atom"]];
const PERIODES = [[1, "24 h"], [7, "7 jours"], [30, "30 jours"], [90, "90 jours"], [365, "1 an"]];
const REGLE_VIDE = { texte: "", categories: [], niveaux: [], prefiltres: [], publics: [], statuts: [], sources: [], jours: 30, cve: false, nos_modeles: false, non_lus: false, suivis: false, impacts: false };
const SOURCE_VIDE = { nom: "", url: "", format: "flux", categorie: "generale", niveau: "", garder_si: "", periode_min: 60, actif: true };

async function call(base, path, opts = {}) {
  if (!base) throw new Error("VITE_VULN_API_BASE_URL absent du hub : reconstruire le hub");
  let r;
  try {
    r = await fetch(`${base}${path}`, { credentials: "include", ...opts, headers: opts.body ? { "Content-Type": "application/json" } : undefined });
  } catch (e) { throw new Error(`vuln-api injoignable (${e.message})`); }
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.error || (r.status === 404 ? "HTTP 404 : vuln-api sans la veille (#814) -- reconstruire vuln-api" : `HTTP ${r.status}`));
  return j;
}
const COURT = { rssi: "RSSI", adminsys: "Admins", dev: "Dév." };
const corps = (b) => ({ method: "POST", body: JSON.stringify(b) });

function Puces({ valeurs, choix, onChange, libelles = {} }) {
  return <span className="veille-puces">{valeurs.map((v) => <button key={v} type="button" className={choix.includes(v) ? "on" : ""} onClick={() => onChange(basculer(choix, v))}>{libelles[v] || v}</button>)}</span>;
}
function Case({ v, onChange, children }) {
  return <label className="veille-case"><input type="checkbox" checked={!!v} onChange={(e) => onChange(e.target.checked)} />{children}</label>;
}
function Extraire({ base, regle, filtre }) {
  const q = filtre ? `filtre=${filtre}` : paramsRegle(regle);
  return <span className="veille-extraire"><span className="infra-muted">Extraire :</span>{FORMATS.map(([f, l]) => <a key={f} href={`${base}/veille/extraction?${q}&format=${f}`} target={f === "atom" ? "_blank" : undefined} rel="noreferrer">{l}</a>)}</span>;
}

function Articles({ base, liste, total, etat, noms, username, recharger, setErr }) {
  const [ouvert, setOuvert] = useState(null);
  const [ia, setIa] = useState({});
  const statuts = etat?.statuts || {};
  async function maj(a, b) {
    try { await call(base, `/veille/articles/${a.id}`, corps({ ...b, par: username })); recharger(); } catch (x) { setErr(x.message); }
  }
  async function expliquer(a) {
    setIa((m) => ({ ...m, [a.id]: { attente: true } }));
    try { const r = await call(base, `/veille/articles/${a.id}/expliquer`, corps({})); setIa((m) => ({ ...m, [a.id]: r })); }
    catch (x) { setIa((m) => ({ ...m, [a.id]: { erreur: x.message } })); }
  }
  function ouvrir(a) {
    setOuvert(ouvert === a.id ? null : a.id);
    if (!a.lu) call(base, `/veille/articles/${a.id}`, corps({ lu: true })).then(() => { a.lu = 1; }).catch(() => {});
  }
  return (
    <div className="infra-table-wrap infra-scroll veille-table">
      <table className="infra-table veille-articles">
        <thead><tr><th>Date</th><th>Source</th><th>Niveau</th><th>Titre</th><th>Chez nous</th><th>Publics</th><th>Préfiltres · CVE</th><th>Suivi</th><th></th></tr></thead>
        <tbody>
          {liste.map((a) => {
            const x = ia[a.id] || a.ia;
            return (
              <Fragment key={a.id}>
                <tr className={a.lu ? "veille-lu" : "veille-non-lu"}>
                  <td className="infra-muted">{dateCourte(a.publie)}</td>
                  <td className="infra-muted">{noms[a.source_id] || "—"}</td>
                  <td>{a.niveau ? <span className={`np-tone ${a.niveau === "avis" ? "neutral" : a.niveau === "alerte" ? "bad" : "warn"}`}>{etat?.niveaux?.[a.niveau]}</span> : ""}</td>
                  <td><span className="veille-titre" onClick={() => ouvrir(a)}>{a.titre}</span></td>
                  <td>{chezNous(a.impacts) || a.nos_modeles?.length ? <span className={`np-tone ${ton(a)}`} title={(a.impacts?.detail || []).map((d) => `${d.asset} : ${d.package} ${d.version} (${d.cve}, ${d.priority})`).join("\n")}>
                    {chezNous(a.impacts) || `⚑ ${a.nos_modeles.join(", ")}`}</span> : <span className="infra-muted">—</span>}</td>
                  <td className="infra-muted">{(a.publics || []).map((p) => COURT[p] || p).join(", ")}</td>
                  <td><div className="veille-etiq">
                    {(a.tags || []).map((t) => <span key={t} className="np-tone neutral">{t}</span>)}
                    {(a.cves || []).slice(0, 3).map((c) => <a key={c} href={`https://nvd.nist.gov/vuln/detail/${c}`} target="_blank" rel="noreferrer">{c}</a>)}
                    {(a.cves || []).length > 3 && <span className="infra-muted">+{a.cves.length - 3}</span>}
                    {a.kev && <span className="np-tone bad" title="exploitée activement (KEV)">KEV</span>}
                    {a.epss_max != null && <span className="infra-muted" title="probabilité d'exploitation (EPSS) la plus haute des CVE citées">EPSS {fmtEpss(a.epss_max)}</span>}
                  </div></td>
                  <td><select value={a.statut || ""} onChange={(e) => maj(a, { statut: e.target.value || null })} title={a.statut_par ? `${a.statut_par}, ${dateCourte(a.statut_quand)}${a.statut_note ? ` — ${a.statut_note}` : ""}` : ""}>
                    <option value="">—</option>{Object.entries(statuts).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
                  <td><div className="veille-actions">
                    <button type="button" className="secondary" title="suivre (gardé au-delà de la conservation)" onClick={() => maj(a, { suivi: !a.suivi })}>{a.suivi ? "★" : "☆"}</button>
                    <button type="button" className="secondary" title={a.lu ? "marquer non lu" : "marquer lu"} onClick={() => maj(a, { lu: !a.lu })}>{a.lu ? "○" : "●"}</button>
                    {a.url && <a href={a.url} target="_blank" rel="noreferrer" title="ouvrir l'article">↗</a>}
                  </div></td>
                </tr>
                {ouvert === a.id && (
                  <tr className="veille-detail"><td colSpan={9}>
                    <p>{a.resume || <i className="infra-muted">pas de résumé dans le flux</i>}</p>
                    {(a.impacts?.detail || []).length > 0 && <p><b>Constats de vuln-api :</b> {a.impacts.detail.map((d) => `${d.asset} — ${d.package} ${d.version} (${d.cve}, ${d.priority})`).join(" ; ")}</p>}
                    {a.statut && <p className="infra-muted">Suivi : {statuts[a.statut]} par {a.statut_par || "?"} le {dateCourte(a.statut_quand)}{a.statut_note ? ` — ${a.statut_note}` : ""}
                      {" "}<button type="button" className="secondary" onClick={() => { const n = window.prompt("Note de suivi :", a.statut_note || ""); if (n != null) maj(a, { statut: a.statut, note: n }); }}>Note…</button></p>}
                    <div className="veille-ligne">
                      <button type="button" onClick={() => expliquer(a)} disabled={x?.attente}>{x?.attente ? "le modèle réfléchit…" : x?.texte ? "Réexpliquer (IA locale)" : "Expliquer (IA locale)"}</button>
                      {x?.texte && <span className="infra-muted">{x.modele} · {x.duree_s} s</span>}
                    </div>
                    {x?.erreur && <p className="infra-error">{x.erreur}</p>}
                    {x?.texte && <pre className="veille-ia">{x.texte}</pre>}
                  </td></tr>
                )}
              </Fragment>
            );
          })}
          {!liste.length && <tr><td colSpan={9} className="infra-muted">Rien pour ces critères (la relève tourne dans vuln-api, chaque source à sa période).</td></tr>}
        </tbody>
      </table>
      {total > liste.length && <p className="infra-muted">{liste.length} affichés sur {total} — affinez ou extrayez le tout.</p>}
    </div>
  );
}

function ParActif({ base, etat, setErr }) {
  const [liste, setListe] = useState(null);
  useEffect(() => { call(base, "/veille/impacts?jours=90").then(setListe).catch((e) => setErr(e.message)); }, [base, setErr]);
  if (!liste) return null;
  return (
    <div className="veille-bloc">
      <h3>Par actif (90 jours)</h3>
      {!liste.length ? <p className="infra-muted">Aucun article ne cite une CVE présente dans nos constats (déposer des SBOM : tuile Vulnérabilités).</p> : (
        <table className="infra-table"><thead><tr><th>Actif</th><th>Priorité</th><th>Articles</th></tr></thead>
          <tbody>{liste.map((e) => (
            <tr key={e.actif}><td><b>{e.actif}</b></td><td>{e.priorite ? <span className={`np-tone ${e.priorite === "P1" ? "bad" : e.priorite === "P2" ? "warn" : "neutral"}`}>{e.priorite}</span> : "—"}</td>
              <td>{e.articles.map((a) => <div key={a.id}><a href={a.url} target="_blank" rel="noreferrer">{a.titre}</a> <span className="infra-muted">{dateCourte(a.publie)}{a.statut ? ` · ${etat?.statuts?.[a.statut] || a.statut}` : ""}</span></div>)}</td></tr>))}</tbody></table>)}
    </div>
  );
}

function EditeurFiltre({ f, setF, etat, sources, prefiltres, enregistrer }) {
  const r = f.regle;
  const maj = (k, v) => setF({ ...f, regle: { ...r, [k]: v } });
  return (
    <form className="veille-bloc veille-form" onSubmit={enregistrer}>
      <h3>{f.id ? "Modifier le filtre" : "Nouveau filtre"}</h3>
      <label>Nom <input value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} required /></label>
      <label>Texte (mots, "expression exacte", -exclusion, a|b) <input value={r.texte} onChange={(e) => maj("texte", e.target.value)} /></label>
      <div className="veille-ligne"><span className="infra-muted">Catégories</span><Puces valeurs={Object.keys(etat?.categories || {})} choix={r.categories} onChange={(v) => maj("categories", v)} libelles={etat?.categories} /></div>
      <div className="veille-ligne"><span className="infra-muted">Niveaux</span><Puces valeurs={Object.keys(etat?.niveaux || {})} choix={r.niveaux} onChange={(v) => maj("niveaux", v)} libelles={etat?.niveaux} /></div>
      <div className="veille-ligne"><span className="infra-muted">Publics</span><Puces valeurs={Object.keys(etat?.publics || {})} choix={r.publics} onChange={(v) => maj("publics", v)} libelles={etat?.publics} /></div>
      <div className="veille-ligne"><span className="infra-muted">Suivi</span><Puces valeurs={["aucun", ...Object.keys(etat?.statuts || {})]} choix={r.statuts} onChange={(v) => maj("statuts", v)} libelles={{ aucun: "sans suivi", ...etat?.statuts }} /></div>
      <div className="veille-ligne"><span className="infra-muted">Préfiltres</span><Puces valeurs={prefiltres.map((p) => p.nom)} choix={r.prefiltres} onChange={(v) => maj("prefiltres", v)} /></div>
      <label>Sources (aucune = toutes)
        <select multiple size={5} value={r.sources.map(String)} onChange={(e) => maj("sources", [...e.target.selectedOptions].map((o) => Number(o.value)))}>
          {sources.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select></label>
      <div className="veille-ligne">
        <select value={r.jours} onChange={(e) => maj("jours", Number(e.target.value))}>{PERIODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}<option value={3650}>tout</option></select>
        <Case v={r.impacts} onChange={(v) => maj("impacts", v)}>touche notre SI</Case><Case v={r.cve} onChange={(v) => maj("cve", v)}>avec CVE</Case>
        <Case v={r.nos_modeles} onChange={(v) => maj("nos_modeles", v)}>nos modèles</Case><Case v={r.non_lus} onChange={(v) => maj("non_lus", v)}>non lus</Case>
        <Case v={r.suivis} onChange={(v) => maj("suivis", v)}>suivis</Case>
      </div>
      <div className="veille-ligne"><button type="submit">Enregistrer</button><button type="button" className="secondary" onClick={() => setF(null)}>Annuler</button></div>
    </form>
  );
}

function Filtres({ base, etat, sources, noms, prefiltres, username, setErr }) {
  const [liste, setListe] = useState([]);
  const [f, setF] = useState(null);
  const [vu, setVu] = useState(null);
  const [res, setRes] = useState(null);
  const [syn, setSyn] = useState({});
  const charger = useCallback(() => call(base, "/veille/filtres").then(setListe).catch((x) => setErr(x.message)), [base, setErr]);
  useEffect(() => { charger(); }, [charger]);
  const voir = (x) => { setVu(x); call(base, `/veille/articles?${paramsRegle(x.regle)}`).then(setRes).catch((e) => setErr(e.message)); };
  async function enregistrer(e) {
    e.preventDefault();
    try { await call(base, f.id ? `/veille/filtres/${f.id}` : "/veille/filtres", { method: f.id ? "PUT" : "POST", body: JSON.stringify({ nom: f.nom, regle: f.regle, par: username }) }); setF(null); charger(); }
    catch (x) { setErr(x.message); }
  }
  async function supprimer(x) {
    if (!window.confirm(`Supprimer le filtre « ${x.nom} » ?`)) return;
    await call(base, `/veille/filtres/${x.id}`, { method: "DELETE" }).catch((e) => setErr(e.message));
    if (vu?.id === x.id) { setVu(null); setRes(null); }
    charger();
  }
  async function synthese(x) {
    voir(x);
    setSyn((m) => ({ ...m, [x.id]: { attente: true } }));
    try { const r = await call(base, "/veille/synthese", corps({ filtre: x.id })); setSyn((m) => ({ ...m, [x.id]: r })); }
    catch (e) { setSyn((m) => ({ ...m, [x.id]: { erreur: e.message } })); }
  }
  const s = vu && syn[vu.id];
  const lib = (r) => [r.texte && `« ${r.texte} »`, ...(r.categories || []).map((c) => etat?.categories?.[c] || c), ...(r.niveaux || []), ...(r.publics || []), ...(r.statuts || []),
    ...(r.prefiltres || []), r.sources?.length && `${r.sources.length} source(s)`, `${r.jours} j`, r.impacts && "touche le SI", r.cve && "avec CVE", r.nos_modeles && "nos modèles",
    r.non_lus && "non lus", r.suivis && "suivis"].filter(Boolean).join(" · ");
  return (
    <>
      <div className="veille-ligne"><span style={{ flex: 1 }} /><button type="button" onClick={() => setF({ nom: "", regle: { ...REGLE_VIDE } })}>Nouveau filtre</button></div>
      {f && <EditeurFiltre f={f} setF={setF} etat={etat} sources={sources} prefiltres={prefiltres} enregistrer={enregistrer} />}
      <table className="infra-table">
        <thead><tr><th>Filtre</th><th>Critères</th><th>Articles</th><th>Extraction</th><th></th></tr></thead>
        <tbody>{liste.map((x) => (
          <tr key={x.id} className={vu?.id === x.id ? "veille-choisi" : ""}>
            <td><span className="veille-titre" onClick={() => voir(x)}><b>{x.nom}</b></span>{x.par ? <div className="infra-muted">{x.par}</div> : null}</td>
            <td className="infra-muted">{lib(x.regle)}</td><td>{x.nb}</td><td><Extraire base={base} filtre={x.id} /></td>
            <td><div className="veille-actions">
              <button type="button" onClick={() => synthese(x)} disabled={syn[x.id]?.attente}>{syn[x.id]?.attente ? "synthèse…" : "Synthèse IA"}</button>
              <button type="button" className="secondary" onClick={() => setF({ ...x, regle: { ...REGLE_VIDE, ...x.regle } })}>Modifier</button>
              <button type="button" className="secondary" onClick={() => supprimer(x)}>Supprimer</button></div></td>
          </tr>))}
          {!liste.length && <tr><td colSpan={5} className="infra-muted">Aucun filtre : créez-en un, ou réglez une vue puis « Enregistrer comme filtre ».</td></tr>}</tbody>
      </table>
      {vu && <>
        <h3>{vu.nom}</h3>
        {s?.erreur && <p className="infra-error">{s.erreur}</p>}
        {s?.attente && <p className="infra-muted">Synthèse en cours par le modèle local…</p>}
        {s?.texte && <div className="veille-bloc"><span className="infra-muted">{s.modele} · {s.articles} article(s) sur {s.total} · {s.duree_s} s</span><pre className="veille-ia">{s.texte}</pre></div>}
        {res && <Articles base={base} liste={res.articles} total={res.total} etat={etat} noms={noms} username={username} recharger={() => voir(vu)} setErr={setErr} />}
      </>}
    </>
  );
}

function Sources({ base, etat, sources, prefiltres, recharger, setErr }) {
  const [f, setF] = useState(null);
  const [pf, setPf] = useState(null);
  const [test, setTest] = useState({});
  const cats = etat?.categories || {};
  async function enregistrer(e) {
    e.preventDefault();
    try { await call(base, f.id ? `/veille/sources/${f.id}` : "/veille/sources", { method: f.id ? "PUT" : "POST", body: JSON.stringify(f) }); setF(null); recharger(); }
    catch (x) { setErr(x.message); }
  }
  async function relever(s) {
    setTest((m) => ({ ...m, [s.id]: "relève…" }));
    try { const r = await call(base, `/veille/sources/${s.id}/relever`, { method: "POST" }); setTest((m) => ({ ...m, [s.id]: r.ok ? `${r.nouveaux} nouveau(x)${r.signales ? `, ${r.signales} alerte(s) envoyée(s)` : ""}` : r.error })); }
    catch (x) { setTest((m) => ({ ...m, [s.id]: x.message })); }
    recharger();
  }
  const basculerSource = (s) => call(base, `/veille/sources/${s.id}`, { method: "PUT", body: JSON.stringify({ ...s, actif: !s.actif }) }).then(recharger).catch((x) => setErr(x.message));
  async function supprimer(s) {
    if (!window.confirm(`Supprimer la source « ${s.nom} » et ses articles sans suivi ?`)) return;
    await call(base, `/veille/sources/${s.id}`, { method: "DELETE" }).catch((x) => setErr(x.message));
    recharger();
  }
  async function enregistrerPf(e) {
    e.preventDefault();
    try { await call(base, `/veille/prefiltres/${encodeURIComponent(pf.nom)}`, { method: "PUT", body: JSON.stringify({ termes: termes(pf.texte), modeles: pf.modeles, actif: pf.actif }) }); setPf(null); recharger(); }
    catch (x) { setErr(x.message); }
  }
  const supprimerPf = (p) => window.confirm(`Supprimer le préfiltre « ${p.nom} » ?`) && call(base, `/veille/prefiltres/${encodeURIComponent(p.nom)}`, { method: "DELETE" }).then(recharger).catch((x) => setErr(x.message));
  const majModele = (i, k, v) => setPf({ ...pf, modeles: pf.modeles.map((x, j) => (j === i ? { ...x, [k]: v } : x)) });
  return (
    <>
      <h3>Préfiltres</h3>
      <p className="infra-muted">Termes cherchés dans le titre et le résumé (mot entier, sans casse ni accents). Le préfiltre <b>mikrotik</b> porte la liste de nos modèles :
        un article qui cite MikroTik / RouterOS et l'un d'eux est marqué ⚑ (alerte immédiate si c'est une alerte ou une vulnérabilité exploitée). Gardés dans la base de vuln-api, jamais dans le dépôt.</p>
      <div className="veille-grille">
        {prefiltres.map((p) => (
          <div key={p.nom} className={`veille-bloc ${p.actif ? "" : "veille-inactif"}`}>
            <div className="veille-ligne"><b>{p.nom}</b><span style={{ flex: 1 }} />
              <button type="button" className="secondary" onClick={() => setPf({ ...p, texte: (p.termes || []).join(", "), modeles: p.modeles || [] })}>Modifier</button>
              <button type="button" className="secondary" onClick={() => supprimerPf(p)}>×</button></div>
            <div className="infra-muted">{(p.termes || []).join(", ")}</div>
            {(p.modeles || []).length > 0 && <div className="veille-etiq">{p.modeles.map((m) => <span key={m.modele} className="np-tone warn">⚑ {m.modele}{m.version ? ` (${m.version})` : ""}</span>)}</div>}
          </div>))}
        <div className="veille-bloc"><button type="button" className="secondary" onClick={() => setPf({ nom: "", texte: "", modeles: [], actif: true, nouveau: true })}>+ Nouveau préfiltre</button></div>
      </div>
      {pf && (
        <form className="veille-bloc veille-form" onSubmit={enregistrerPf}>
          <h3>Préfiltre {pf.nouveau ? "" : pf.nom}</h3>
          {pf.nouveau && <label>Nom (lettres, chiffres, - ou _) <input value={pf.nom} onChange={(e) => setPf({ ...pf, nom: e.target.value })} required /></label>}
          <label>Termes (séparés par des virgules) <textarea rows={3} value={pf.texte} onChange={(e) => setPf({ ...pf, texte: e.target.value })} /></label>
          <span className="infra-muted">Nos modèles (facultatif)</span>
          {pf.modeles.map((m, i) => (
            <div key={i} className="veille-ligne">
              <input value={m.modele} placeholder="modèle" onChange={(e) => majModele(i, "modele", e.target.value)} />
              <input value={m.version || ""} placeholder="version" onChange={(e) => majModele(i, "version", e.target.value)} />
              <input value={m.note || ""} placeholder="note (rôle, lieu)" onChange={(e) => majModele(i, "note", e.target.value)} />
              <button type="button" className="secondary" onClick={() => setPf({ ...pf, modeles: pf.modeles.filter((_, j) => j !== i) })}>×</button>
            </div>))}
          <div className="veille-ligne">
            <button type="button" className="secondary" onClick={() => setPf({ ...pf, modeles: [...pf.modeles, { modele: "", version: "", note: "" }] })}>+ modèle</button>
            <Case v={pf.actif} onChange={(v) => setPf({ ...pf, actif: v })}>actif</Case>
          </div>
          <div className="veille-ligne"><button type="submit">Enregistrer (réétiquette les articles)</button><button type="button" className="secondary" onClick={() => setPf(null)}>Annuler</button></div>
        </form>)}
      <div className="veille-ligne"><h3>Sources</h3><span style={{ flex: 1 }} /><button type="button" onClick={() => setF({ ...SOURCE_VIDE })}>Nouvelle source</button></div>
      {f && (
        <form className="veille-bloc veille-form" onSubmit={enregistrer}>
          <label>Nom <input value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} required /></label>
          <label>URL du flux (RSS, Atom, RDF ou JSON KEV) <input value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} required /></label>
          <div className="veille-ligne">
            <select value={f.format} onChange={(e) => setF({ ...f, format: e.target.value })}><option value="flux">flux (RSS, Atom, RDF)</option><option value="kev">kev (JSON CISA)</option></select>
            <select value={f.categorie} onChange={(e) => setF({ ...f, categorie: e.target.value })}>{Object.entries(cats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
            {f.categorie === "alerte" && <select value={f.niveau || ""} onChange={(e) => setF({ ...f, niveau: e.target.value })}><option value="">niveau —</option>{Object.entries(etat?.niveaux || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>}
            <label className="veille-case">toutes les <input type="number" min={5} style={{ width: 80 }} value={f.periode_min} onChange={(e) => setF({ ...f, periode_min: Number(e.target.value) })} /> min</label>
          </div>
          <label>Garder seulement si le texte contient (termes séparés par des virgules, vide = tout) <input value={f.garder_si || ""} onChange={(e) => setF({ ...f, garder_si: e.target.value })} /></label>
          <div className="veille-ligne"><Case v={f.actif !== false && f.actif !== 0} onChange={(v) => setF({ ...f, actif: v })}>active</Case>
            <button type="submit">Enregistrer</button><button type="button" className="secondary" onClick={() => setF(null)}>Annuler</button></div>
        </form>)}
      <div className="infra-table-wrap infra-scroll veille-table">
        <table className="infra-table veille-sources">
          <thead><tr><th>Source</th><th>Catégorie</th><th>État</th><th>Dernière relève</th><th>Articles</th><th></th></tr></thead>
          <tbody>{sources.map((s) => (
            <tr key={s.id} className={s.actif ? "" : "veille-inactif"}>
              <td><b>{s.nom}</b><div className="infra-muted"><a href={s.url} target="_blank" rel="noreferrer">{s.url}</a>{s.garder_si ? ` · seulement si : ${s.garder_si}` : ""}</div></td>
              <td className="infra-muted">{cats[s.categorie] || s.categorie}{s.niveau ? ` · ${etat?.niveaux?.[s.niveau]}` : ""} · {s.periode_min} min</td>
              <td>{s.derniere_erreur ? <span className="np-tone bad" title={s.derniere_erreur}>erreur</span> : s.verifiee ? <span className="np-tone good">vérifiée</span> : <span className="np-tone neutral">non vérifiée</span>}
                {s.derniere_erreur && <div className="infra-error">{s.derniere_erreur}</div>}{test[s.id] && <div className="infra-muted">{test[s.id]}</div>}</td>
              <td className="infra-muted">{s.derniere_releve ? dateCourte(s.derniere_releve) : "jamais"}{s.nb_derniere != null ? ` · ${s.nb_derniere} nouveau(x)` : ""}</td>
              <td>{s.articles}</td>
              <td><div className="veille-actions">
                <button type="button" onClick={() => relever(s)}>Relever</button>
                <button type="button" className="secondary" onClick={() => basculerSource(s)}>{s.actif ? "Désactiver" : "Activer"}</button>
                <button type="button" className="secondary" onClick={() => setF({ ...s, niveau: s.niveau || "", garder_si: s.garder_si || "" })}>Modifier</button>
                <button type="button" className="secondary" onClick={() => supprimer(s)}>×</button></div></td>
            </tr>))}</tbody>
        </table>
      </div>
    </>
  );
}

function Journal({ base, etat, setErr }) {
  const [j, setJ] = useState([]);
  useEffect(() => { call(base, "/veille/journal?n=300").then(setJ).catch((e) => setErr(e.message)); }, [base, setErr]);
  return (
    <div className="infra-table-wrap infra-scroll veille-table">
      <table className="infra-table">
        <thead><tr><th>Quand</th><th>Qui</th><th>Suivi</th><th>Article</th><th>Note</th></tr></thead>
        <tbody>{j.map((x) => (
          <tr key={x.id}><td className="infra-muted">{dateCourte(x.quand)}</td><td>{x.par}</td><td>{etat?.statuts?.[x.statut] || x.statut}</td>
            <td>{x.url ? <a href={x.url} target="_blank" rel="noreferrer">{x.titre}</a> : x.titre || `#${x.article_id}`}</td><td>{x.note}</td></tr>))}
          {!j.length && <tr><td colSpan={5} className="infra-muted">Aucun changement de suivi pour l'instant.</td></tr>}</tbody>
      </table>
    </div>
  );
}

export default function VeilleView({ onBack, vulnApiBase, username }) {
  const base = vulnApiBase;
  const [onglet, setOnglet] = useState(() => { try { return localStorage.getItem("veille.onglet") || "alerte"; } catch { return "alerte"; } });
  const [etat, setEtat] = useState(null);
  const [sources, setSources] = useState([]);
  const [prefiltres, setPrefiltres] = useState([]);
  const [vue, setVue] = useState({ ...REGLE_VIDE, jours: 7 });
  const [res, setRes] = useState({ articles: [], total: 0 });
  const [err, setErr] = useState("");
  const [nomFiltre, setNomFiltre] = useState(null);
  const [envoi, setEnvoi] = useState("");
  const noms = useMemo(() => Object.fromEntries(sources.map((s) => [s.id, s.nom])), [sources]);
  const regle = useMemo(() => (onglet === "impacts" ? { ...vue, impacts: true, jours: Math.max(vue.jours, 30) } : { ...vue, categories: [onglet] }), [vue, onglet]);
  const liste = LISTES.has(onglet);
  const chargerFond = useCallback(async () => {
    try {
      const [e, s, p] = await Promise.all([call(base, "/veille/etat"), call(base, "/veille/sources"), call(base, "/veille/prefiltres")]);
      setEtat(e); setSources(s); setPrefiltres(p);
    } catch (x) { setErr(x.message); }
  }, [base]);
  const chargerListe = useCallback(() => {
    if (!liste) return;
    call(base, `/veille/articles?${paramsRegle(regle)}`).then((r) => { setRes(r); setErr(""); }).catch((x) => setErr(x.message));
  }, [base, regle, liste]);
  useEffect(() => { chargerFond(); const t = setInterval(chargerFond, 60000); return () => clearInterval(t); }, [chargerFond]);
  useEffect(() => { chargerListe(); const t = setInterval(chargerListe, 60000); return () => clearInterval(t); }, [chargerListe]);
  useEffect(() => { try { localStorage.setItem("veille.onglet", onglet); } catch { /* navigation privée */ } }, [onglet]);
  const toutLu = () => call(base, "/veille/articles/lus", corps({ ids: res.articles.filter((a) => !a.lu).map((a) => a.id) })).then(chargerListe).catch((x) => setErr(x.message));
  async function enregistrerFiltre(e) {
    e.preventDefault();
    try { await call(base, "/veille/filtres", corps({ nom: nomFiltre, regle, par: username })); setNomFiltre(null); setOnglet("filtres"); } catch (x) { setErr(x.message); }
  }
  async function envoyerSynthese() {
    setEnvoi("envoi…");
    try { const r = await call(base, "/veille/synthese/envoyer", { method: "POST" }); setEnvoi(Object.entries(r.publics).map(([p, n]) => `${etat?.publics?.[p] || p} : ${n}`).join(" · ")); }
    catch (x) { setEnvoi(x.message); }
  }
  const e = etat || {};
  return (
    <div className="infra-root veille">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Veille cyber</h2>
        {etat && <span className="infra-muted">{e.sources_actives} source(s) active(s) · relève {e.derniere_releve ? dateCourte(e.derniere_releve) : "jamais"}</span>}
        {e.sources_en_erreur > 0 && <button type="button" className="secondary" onClick={() => setOnglet("sources")}><span className="np-tone bad">{e.sources_en_erreur} source(s) en erreur</span></button>}
      </div>
      {etat && (
        <div className="infra-kpis"><div className="infra-kpi-group">
          <div className={`infra-kpi ${e.alertes_non_lues ? "warning" : ""}`}><span>alertes non lues / 7 j</span><b>{e.alertes_non_lues}</b><small>{e.alertes_7j} alerte(s)</small></div>
          <div className={`infra-kpi ${e.touchent_si_30j ? "critical" : ""}`}><span>touchent notre SI / 30 j</span><b>{e.touchent_si_30j}</b><small>CVE présentes dans nos constats</small></div>
          <div className={`infra-kpi ${e.a_traiter ? "warning" : ""}`}><span>à traiter / en cours</span><b>{e.a_traiter}</b><small>suivi de traitement</small></div>
          <div className="infra-kpi"><span>nos modèles cités / 30 j</span><b>{e.nos_modeles_30j}</b><small>préfiltre mikrotik…</small></div>
          <div className="infra-kpi"><span>diffusion</span><b>{e.notifications ? "notify-api" : "non branchée"}</b>
            <small>synthèse quotidienne à {e.heure_synthese} h{e.derniere_synthese ? ` (dernière ${e.derniere_synthese})` : ""}{e.notifications ? <> · <button type="button" className="secondary" onClick={envoyerSynthese}>envoyer maintenant</button></> : ""}{envoi ? ` · ${envoi}` : ""}</small></div>
        </div></div>
      )}
      <div className="infra-tabs veille-onglets">{ONGLETS.map(([id, t]) => <button key={id} type="button" className={onglet === id ? "active" : ""} onClick={() => setOnglet(id)}>{t}</button>)}</div>
      {err && <p className="infra-error">{err}</p>}
      <div className="infra-page infra-scroll">
        {liste && <>
          <div className="veille-bloc veille-barre">
            <input value={vue.texte} onChange={(ev) => setVue({ ...vue, texte: ev.target.value })} placeholder='rechercher : mots, "expression", -exclure, a|b, CVE-…' />
            <div className="veille-ligne">
              <span className="infra-muted">Préfiltres</span><Puces valeurs={prefiltres.filter((p) => p.actif).map((p) => p.nom)} choix={vue.prefiltres} onChange={(v) => setVue({ ...vue, prefiltres: v })} />
              <span className="infra-muted">Publics</span><Puces valeurs={Object.keys(e.publics || {})} choix={vue.publics} onChange={(v) => setVue({ ...vue, publics: v })} libelles={COURT} />
              {onglet === "alerte" && <><span className="infra-muted">Niveaux</span><Puces valeurs={Object.keys(e.niveaux || {})} choix={vue.niveaux} onChange={(v) => setVue({ ...vue, niveaux: v })} libelles={e.niveaux} /></>}
            </div>
            <div className="veille-ligne">
              <select value={vue.jours} onChange={(ev) => setVue({ ...vue, jours: Number(ev.target.value) })}>{PERIODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              <select value={vue.statuts[0] || ""} onChange={(ev) => setVue({ ...vue, statuts: ev.target.value ? [ev.target.value] : [] })}><option value="">suivi : tous</option><option value="aucun">sans suivi</option>
                {Object.entries(e.statuts || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
              {onglet !== "impacts" && <Case v={vue.impacts} onChange={(v) => setVue({ ...vue, impacts: v })}>touche notre SI</Case>}
              <Case v={vue.nos_modeles} onChange={(v) => setVue({ ...vue, nos_modeles: v })}>⚑ nos modèles</Case>
              <Case v={vue.cve} onChange={(v) => setVue({ ...vue, cve: v })}>avec CVE</Case>
              <Case v={vue.non_lus} onChange={(v) => setVue({ ...vue, non_lus: v })}>non lus</Case>
              <Case v={vue.suivis} onChange={(v) => setVue({ ...vue, suivis: v })}>★ suivis</Case>
            </div>
            <div className="veille-ligne">
              <span className="infra-muted">{res.total} article(s)</span>
              <button type="button" className="secondary" onClick={toutLu} disabled={!res.articles.some((a) => !a.lu)}>Tout marquer lu</button>
              {nomFiltre == null ? <button type="button" className="secondary" onClick={() => setNomFiltre("")}>Enregistrer comme filtre…</button>
                : <form className="veille-ligne" onSubmit={enregistrerFiltre}><input autoFocus value={nomFiltre} onChange={(ev) => setNomFiltre(ev.target.value)} placeholder="nom du filtre" required /><button type="submit">OK</button><button type="button" className="secondary" onClick={() => setNomFiltre(null)}>×</button></form>}
              <span style={{ flex: 1 }} /><Extraire base={base} regle={regle} />
            </div>
          </div>
          {onglet === "impacts" && <p className="infra-muted">Articles dont une CVE figure dans les constats de vuln-api (SBOM des agents, images, dépôts) — les plus récents d'abord ; vue par actif en dessous.</p>}
          <Articles base={base} liste={res.articles} total={res.total} etat={etat} noms={noms} username={username} recharger={chargerListe} setErr={setErr} />
          {onglet === "impacts" && <ParActif base={base} etat={etat} setErr={setErr} />}
        </>}
        {onglet === "filtres" && <Filtres base={base} etat={etat} sources={sources} noms={noms} prefiltres={prefiltres} username={username} setErr={setErr} />}
        {onglet === "sources" && <Sources base={base} etat={etat} sources={sources} prefiltres={prefiltres} recharger={chargerFond} setErr={setErr} />}
        {onglet === "journal" && <Journal base={base} etat={etat} setErr={setErr} />}
      </div>
    </div>
  );
}
