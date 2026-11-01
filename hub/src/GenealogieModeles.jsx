import { useCallback, useEffect, useMemo, useState } from "react";
import { OUVERTURE, cheminOrigine, enfantsDe, filtrer, lignee, moisLisible, parAnnee, valeurs } from "./genealogieLib.js";

// #854 Généalogie des modèles d'IA (même composant dans le hub supervision et le hub maison) : frise depuis le Transformer (2017),
// filiations (succession, affinage, distillation, fusion...), fiche avec dates, auteurs, liens et mode d'emploi ; la base relevée
// à la main est complétée chaque jour par les dérivés Hugging Face et les nouveaux modèles de la veille des sorties.
// props : api(chemin, { methode, corps }) -> Promise<json>, prefixe ("/modeles" ou "/api/modeles").

const STYLE = `
.gen { display: flex; flex-direction: column; gap: 10px; }
.gen-barre { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.gen-barre input[type=search] { flex: 1 1 220px; min-width: 160px; }
.gen-barre input, .gen-barre select, .gen button { background: rgba(127,127,127,.12); color: inherit; border: 1px solid rgba(127,127,127,.35); border-radius: 6px; padding: 4px 8px; font: inherit; }
.gen button { cursor: pointer; }
.gen button:hover { background: rgba(127,127,127,.25); }
.gen-muet { opacity: .7; font-size: .9em; }
.gen-corps { display: grid; grid-template-columns: minmax(0, 1fr) minmax(300px, 420px); gap: 12px; align-items: start; }
@media (max-width: 900px) { .gen-corps { grid-template-columns: 1fr; } }
.gen-annee { margin: 6px 0 4px; font-weight: 600; display: flex; gap: 8px; align-items: baseline; border-bottom: 1px solid rgba(127,127,127,.25); }
.gen-cartes { display: flex; flex-wrap: wrap; gap: 6px; }
.gen-carte { text-align: left; border-left-width: 4px !important; padding: 4px 8px !important; max-width: 220px; line-height: 1.25; }
.gen-carte b { display: block; font-weight: 600; }
.gen-carte small { opacity: .75; }
.gen-carte.sel { outline: 2px solid #4f8df7; }
.gen-carte.lien { outline: 1px dashed #4f8df7; }
.gen-carte.terne { opacity: .45; }
.gen-tag { display: inline-block; font-size: .75em; padding: 0 5px; border-radius: 8px; background: rgba(127,127,127,.25); margin-left: 4px; }
.gen-fiche { position: sticky; top: 8px; border: 1px solid rgba(127,127,127,.3); border-radius: 8px; padding: 10px; background: rgba(127,127,127,.06); display: flex; flex-direction: column; gap: 8px; max-height: calc(100vh - 40px); overflow: auto; }
.gen-fiche h3 { margin: 0; }
.gen-fiche h4 { margin: 6px 0 2px; font-size: .95em; }
.gen-liste { display: flex; flex-wrap: wrap; gap: 4px; }
.gen-liste button { padding: 2px 6px; font-size: .9em; }
.gen-cmd { display: flex; gap: 6px; align-items: center; }
.gen-cmd code { flex: 1; background: rgba(0,0,0,.35); padding: 4px 6px; border-radius: 4px; overflow-x: auto; white-space: nowrap; }
.gen-aide { border: 1px solid rgba(127,127,127,.3); border-radius: 8px; padding: 8px 12px; background: rgba(127,127,127,.06); }
.gen-aide li { margin: 2px 0; }
.gen-erreur { color: #e66; }
.gen a { color: #7fb2ff; margin-right: 10px; }
`;

function Pastille({ o }) {
  const [t, c] = OUVERTURE[o] || [o || "?", "#888"];
  return <span className="gen-tag" style={{ background: c, color: "#fff" }}>{t}</span>;
}

function Copier({ texte }) {
  const [ok, setOk] = useState(false);
  return <button type="button" title="Copier" onClick={() => { try { navigator.clipboard?.writeText(texte); setOk(true); setTimeout(() => setOk(false), 1500); } catch { /* presse-papiers refusé */ } }}>{ok ? "copié" : "copier"}</button>;
}

function Aide({ prefixe }) {
  return <div className="gen-aide">
    <b>Mode d'emploi de la page</b>
    <ul>
      <li><b>Frise</b> : un modèle par carte, rangé par année depuis le Transformer (2017). Couleur du bord : <Pastille o="ouvert" /> <Pastille o="poids" /> <Pastille o="ferme" />. <span className="gen-tag">auto</span> = relevé automatiquement.</li>
      <li><b>Cliquer une carte</b> ouvre sa fiche (date, auteurs, parents, enfants, liens, mode d'emploi) et entoure en pointillé toute sa lignée dans la frise.</li>
      <li><b>Recherche</b> : nom, éditeur, auteurs, année, taille, identifiant Hugging Face ou commande Ollama ; plusieurs mots = tous requis.</li>
      <li><b>Mise à jour</b> : une fois par jour (ou « Relever maintenant »), les dérivés les plus téléchargés de chaque modèle ouvert sont lus sur Hugging Face, et chaque nouveau modèle de la veille des sorties est rattaché à son modèle de base s'il en déclare un. Les quantifications (GGUF, AWQ…) ne comptent pas. Un relevé hors sujet s'écarte depuis sa fiche.</li>
      <li><b>Corriger ou compléter l'histoire</b> : fichier <code>genealogie_base.json</code> à côté du module <code>genealogie.py</code> (un nœud : id, nom, org, date AAAA-MM, types, ouverture, parents avec la relation, auteurs, liens, hf, emploi.ollama) ; la page signale les erreurs (parent inconnu, doublon, cycle). Pas de lien : opération manuelle (édition du fichier puis reconstruction de l'image).</li>
      <li><b>Mode d'emploi d'un modèle</b> : commande Ollama à copier, VRAM estimée en Q4, machines qui le tiennent (variable <code>MODELES_MACHINES</code>). Réglages : <code>GENEALOGIE_DERIVES</code> (dérivés par modèle, 5), <code>GENEALOGIE_AUTO</code> (relève quotidienne, 1). API : <code>GET {prefixe}/genealogie</code>, <code>POST {prefixe}/genealogie/relever</code>.</li>
    </ul>
  </div>;
}

function Fiche({ n, parId, enf, noeuds, choisir, ecarter }) {
  const [tous, setTous] = useState(false);
  const lg = useMemo(() => lignee(noeuds, n.id), [noeuds, n.id]);
  const chemin = useMemo(() => cheminOrigine(noeuds, n.id).slice().reverse(), [noeuds, n.id]);
  const e = n.emploi || {};
  const enfants = (enf[n.id] || []).map((x) => ({ ...x, n: parId[x.id] })).filter((x) => x.n).sort((a, b) => (a.n.date || "").localeCompare(b.n.date || ""));
  const Lien = ({ id, suffixe }) => <button type="button" onClick={() => choisir(id)}>{parId[id]?.nom || id}{suffixe}</button>;
  return <div className="gen-fiche">
    <div><h3>{n.nom} <Pastille o={n.ouverture} />{n.auto && <span className="gen-tag">auto</span>}</h3>
      <div className="gen-muet">{n.org} · {moisLisible(n.date)}{n.tailles ? ` · ${n.tailles}` : n.params_b ? ` · ${n.params_b} B` : ""}{n.licence ? ` · licence ${n.licence}` : ""}</div>
      {n.auteurs && <div><small>Auteurs : {n.auteurs}</small></div>}
      <div><small>Types : {(n.types || []).join(", ") || "?"}{n.telechargements != null ? ` · ${Number(n.telechargements).toLocaleString("fr-FR")} téléchargements` : ""}</small></div>
    </div>
    {chemin.length > 1 && <div><h4>Depuis l'origine</h4><div className="gen-liste">{chemin.map((id, i) => <span key={id}>{i > 0 && "→ "}{id === n.id ? <b>{n.nom}</b> : <Lien id={id} />}</span>)}</div></div>}
    {(n.parents || []).length > 0 && <div><h4>Parents</h4><div className="gen-liste">{n.parents.map((p) => <Lien key={p.id} id={p.id} suffixe={p.relation ? ` (${p.relation})` : ""} />)}</div></div>}
    {enfants.length > 0 && <div><h4>Enfants ({enfants.length})</h4><div className="gen-liste">{enfants.map((x) => <Lien key={x.id} id={x.id} suffixe={` (${x.relation || "?"}${x.n.auto ? ", auto" : ""})`} />)}</div></div>}
    {lg.descendants.length > enfants.length && <div><h4>Descendance complète : {lg.descendants.length} modèles <button type="button" onClick={() => setTous(!tous)}>{tous ? "masquer" : "voir"}</button></h4>
      {tous && <div className="gen-liste">{lg.descendants.map((x) => <Lien key={x.id} id={x.id} suffixe={` · ${x.distance}`} />)}</div>}</div>}
    <div><h4>Liens</h4><div className="gen-liste">
      {n.liens?.article && <a href={n.liens.article} target="_blank" rel="noreferrer">article</a>}
      {n.liens?.hf && <a href={n.liens.hf} target="_blank" rel="noreferrer">Hugging Face</a>}
      {n.liens?.site && <a href={n.liens.site} target="_blank" rel="noreferrer">site / annonce</a>}
      {e.ollama && <a href={`https://ollama.com/library/${e.ollama.split(":")[0]}`} target="_blank" rel="noreferrer">Ollama</a>}
      {!n.liens?.article && !n.liens?.hf && !n.liens?.site && <span className="gen-muet">aucun lien relevé</span>}
    </div></div>
    <div><h4>Mode d'emploi</h4>
      {n.ouverture === "ferme" ? <div className="gen-muet">Modèle fermé : seulement par l'API ou l'application de l'éditeur, pas d'installation locale.</div>
        : <>
          {e.commande ? <div className="gen-cmd"><code>{e.commande}</code><Copier texte={e.commande.split("   #")[0]} /></div>
            : <div className="gen-muet">Pas de commande Ollama relevée (voir la fiche Hugging Face : transformers, vLLM, llama.cpp).</div>}
          {e.vram_q4 != null && <div><small>VRAM estimée en Q4 : ≈ {e.vram_q4} Go · {e.machines?.length ? `tient sur ${e.machines.join(", ")}` : "aucune de nos machines"}</small></div>}
        </>}
      {e.note && <div><small>{e.note}</small></div>}
    </div>
    {n.auto && <div><button type="button" onClick={() => ecarter(n.id)}>Écarter ce relevé</button></div>}
  </div>;
}

export default function GenealogieModeles({ api, prefixe = "/modeles" }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [f, setF] = useState({ texte: "", ouverture: "", type: "", org: "", auto: true });
  const [sel, setSel] = useState(null);
  const [aide, setAide] = useState(false);
  const charger = useCallback(() => api(`${prefixe}/genealogie`).then((x) => { setD(x); setErr(""); }).catch((x) => setErr(x.message)), [api, prefixe]);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => { if (!d?.en_cours) return undefined; const t = setTimeout(charger, 8000); return () => clearTimeout(t); }, [d, charger]);
  const noeuds = useMemo(() => d?.noeuds || [], [d]);
  const parId = useMemo(() => Object.fromEntries(noeuds.map((n) => [n.id, n])), [noeuds]);
  const enf = useMemo(() => enfantsDe(noeuds), [noeuds]);
  const vus = useMemo(() => filtrer(noeuds, f), [noeuds, f]);
  const annees = useMemo(() => parAnnee(vus), [vus]);
  const famille = useMemo(() => { if (!sel || !parId[sel]) return null; const lg = lignee(noeuds, sel); return new Set([...lg.ascendants, ...lg.descendants].map((x) => x.id)); }, [sel, noeuds, parId]);
  const relever = () => api(`${prefixe}/genealogie/relever`, { methode: "POST" }).then(() => setTimeout(charger, 1500)).catch((x) => setErr(x.message));
  const ecarter = (id) => api(`${prefixe}/genealogie/ecarter`, { methode: "POST", corps: { id } }).then(() => { setSel(null); charger(); }).catch((x) => setErr(x.message));
  const choisir = (id) => setSel(id);
  const maj = (k) => (ev) => setF({ ...f, [k]: ev.target.type === "checkbox" ? ev.target.checked : ev.target.value });
  const rel = d?.releve || {};
  return <div className="gen">
    <style>{STYLE}</style>
    <div className="gen-barre">
      <input type="search" placeholder="Rechercher : nom, éditeur, auteur, année, taille, qwen3:8b…" value={f.texte} onChange={maj("texte")} />
      <select value={f.ouverture} onChange={maj("ouverture")}><option value="">toute ouverture</option>{Object.entries(OUVERTURE).map(([k, [t]]) => <option key={k} value={k}>{t}</option>)}</select>
      <select value={f.type} onChange={maj("type")}><option value="">tous types</option>{valeurs(noeuds, "types").map((t) => <option key={t}>{t}</option>)}</select>
      <select value={f.org} onChange={maj("org")}><option value="">tous éditeurs</option>{valeurs(noeuds, "org").map((t) => <option key={t}>{t}</option>)}</select>
      <label><input type="checkbox" checked={f.auto} onChange={maj("auto")} /> relevés auto</label>
      <button type="button" onClick={relever} disabled={d?.en_cours}>{d?.en_cours ? "Relève en cours…" : "Relever maintenant"}</button>
      <button type="button" onClick={() => setAide(!aide)}>{aide ? "Masquer le mode d'emploi" : "Mode d'emploi"}</button>
    </div>
    <div className="gen-muet">
      {d ? <>{vus.length} / {noeuds.length} modèles ({d.compte?.base} relevés à la main, base du {d.base_maj} ; {d.compte?.releves} relevés automatiquement)
        {rel.at ? ` · dernière relève ${new Date(rel.at * 1000).toLocaleString("fr-FR")}` : " · jamais relevé"}
        {rel.erreurs && Object.keys(rel.erreurs).length ? ` · ${Object.keys(rel.erreurs).length} erreur(s) de lecture` : ""}</> : "chargement…"}
    </div>
    {err && <div className="gen-erreur">{err}</div>}
    {d?.erreurs_base?.length > 0 && <div className="gen-erreur">Base à corriger : {d.erreurs_base.join(" · ")}</div>}
    {aide && <Aide prefixe={prefixe} />}
    <div className="gen-corps">
      <div>
        {annees.map(([a, liste]) => <div key={a}>
          <div className="gen-annee">{a}<span className="gen-muet">{liste.length} modèle{liste.length > 1 ? "s" : ""}</span></div>
          <div className="gen-cartes">{liste.map((n) => {
            const cls = n.id === sel ? "sel" : famille?.has(n.id) ? "lien" : famille ? "terne" : "";
            const p = (n.parents || [])[0];
            return <button key={n.id} type="button" className={`gen-carte ${cls}`} style={{ borderLeftColor: (OUVERTURE[n.ouverture] || [])[1] || "#888" }} onClick={() => setSel(n.id === sel ? null : n.id)}
              title={`${n.nom} · ${n.org} · ${moisLisible(n.date)}`}>
              <b>{n.nom}{n.auto && <span className="gen-tag">auto</span>}</b>
              <small>{n.org} · {moisLisible(n.date)}</small>
              {p && <small style={{ display: "block" }}>← {parId[p.id]?.nom || p.id}{n.parents.length > 1 ? ` +${n.parents.length - 1}` : ""}</small>}
            </button>;
          })}</div>
        </div>)}
        {d && !vus.length && <div className="gen-muet">Aucun modèle ne correspond aux filtres.</div>}
      </div>
      {sel && parId[sel] ? <Fiche n={parId[sel]} parId={parId} enf={enf} noeuds={noeuds} choisir={choisir} ecarter={ecarter} />
        : <div className="gen-fiche gen-muet">Cliquer un modèle pour sa fiche : date, auteurs, filiation jusqu'au Transformer, enfants et forks, liens, mode d'emploi (commande Ollama, VRAM, machines).</div>}
    </div>
  </div>;
}
