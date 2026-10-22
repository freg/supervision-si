// #827 Parc IA › Skills : consignes versionnées des IA du hub. Les skills « priorites-* » sont branchés sur les Priorités
// (le code impose le format de réponse et les clés du décideur) ; les autres forment la bibliothèque. Essai sur un texte.
import { useCallback, useEffect, useState } from "react";

let BASE = "";
async function api(path, { methode = "GET", corps } = {}) {
  const r = await fetch(`${BASE}${path}`, { method: methode, credentials: "include", headers: corps ? { "Content-Type": "application/json" } : undefined, body: corps ? JSON.stringify(corps) : undefined });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.error || (r.status === 404 ? "HTTP 404 : si-agent-api sans les skills (#827) -- reconstruire si-agent-api" : `HTTP ${r.status}`));
  return j;
}
const quand = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");

export default function SkillsSection({ base, username }) {
  BASE = base || "";
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState(null);      // skill en édition (copie)
  const [hist, setHist] = useState([]);
  const [essai, setEssai] = useState({ texte: "", sortie: null, attente: false });
  const [nouveau, setNouveau] = useState(null);
  const charger = useCallback(() => { api("/skills").then(setD).catch((x) => setErr(x.message)); }, []);
  useEffect(() => { charger(); }, [charger]);
  const ouvrir = (s) => { setSel({ ...s }); setEssai({ texte: "", sortie: null, attente: false }); api(`/skills/${s.id}/historique`).then((h) => setHist(h.versions)).catch(() => setHist([])); };
  async function enregistrer() {
    try { await api(`/skills/${sel.id}`, { methode: "PUT", corps: { texte: sel.texte, actif: sel.actif, notes: sel.notes, par: username } }); charger(); ouvrir({ ...sel }); } catch (x) { setErr(x.message); }
  }
  async function revenir() {
    if (!window.confirm(sel.systeme ? "Revenir au texte du code (l'historique reste) ?" : `Supprimer le skill « ${sel.id} » ?`)) return;
    try { await api(`/skills/${sel.id}`, { methode: "DELETE" }); setSel(null); charger(); } catch (x) { setErr(x.message); }
  }
  async function restaurer(v) { try { await api(`/skills/${sel.id}/restaurer`, { methode: "POST", corps: { version: v, par: username } }); charger(); const s = (await api("/skills")).skills.find((x) => x.id === sel.id); ouvrir(s); } catch (x) { setErr(x.message); } }
  async function essayer() {
    setEssai({ ...essai, attente: true, sortie: null });
    try { const r = await api(`/skills/${sel.id}/essai`, { methode: "POST", corps: { texte: essai.texte, brouillon: sel.texte } }); setEssai({ ...essai, attente: false, sortie: r }); }
    catch (x) { setEssai({ ...essai, attente: false, sortie: { erreur: x.message } }); }
  }
  async function creer() {
    try { await api("/skills", { methode: "POST", corps: { ...nouveau, par: username } }); setNouveau(null); charger(); } catch (x) { setErr(x.message); }
  }
  if (!d) return <p className="infra-muted">{err || "lecture…"}</p>;
  return (
    <div className="veille">
      {err && <p className="infra-error" onClick={() => setErr("")}>{err}</p>}
      <div className="veille-ligne"><span className="infra-muted">Les skills « priorites-* » pilotent les Priorités de la page d'accueil ; personnalisés et actifs, ils remplacent la consigne du code.</span>
        <span style={{ flex: 1 }} /><button type="button" onClick={() => setNouveau({ id: "", nom: "", usage: "assistant", type: "consigne", texte: "" })}>Nouveau skill</button></div>
      {nouveau && <div className="veille-bloc">
        <div className="veille-ligne">
          <input placeholder="identifiant (ex. veille-resume)" value={nouveau.id} onChange={(e) => setNouveau({ ...nouveau, id: e.target.value })} />
          <input placeholder="nom" value={nouveau.nom} onChange={(e) => setNouveau({ ...nouveau, nom: e.target.value })} />
          <select value={nouveau.usage} onChange={(e) => setNouveau({ ...nouveau, usage: e.target.value })}>{d.usages.map((u) => <option key={u}>{u}</option>)}</select>
          <select value={nouveau.type} onChange={(e) => setNouveau({ ...nouveau, type: e.target.value })}>{Object.entries(d.types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        </div>
        <textarea rows={6} style={{ width: "100%" }} value={nouveau.texte} onChange={(e) => setNouveau({ ...nouveau, texte: e.target.value })} placeholder="consigne" />
        <div className="veille-ligne"><button type="button" onClick={creer}>Créer</button><button type="button" className="secondary" onClick={() => setNouveau(null)}>Annuler</button></div>
      </div>}
      <div className="infra-table-wrap"><table className="infra-table">
        <thead><tr><th>Skill</th><th>Usage</th><th>Type</th><th>Version</th><th>État</th><th>Modifié</th></tr></thead>
        <tbody>{d.skills.map((s) => (
          <tr key={s.id} className={sel?.id === s.id ? "veille-non-lu" : ""}>
            <td><span className="veille-titre" onClick={() => ouvrir(s)}>{s.nom}</span> <span className="infra-muted">{s.id}</span></td>
            <td>{s.usage}</td><td className="infra-muted">{s.type}</td><td>{s.version || "code"}</td>
            <td>{!s.personnalise ? <span className="np-tone neutral">texte du code</span> : s.actif ? <span className="np-tone good">actif</span> : <span className="np-tone warn">inactif</span>}</td>
            <td className="infra-muted">{s.maj ? `${quand(s.maj)}${s.par ? ` · ${s.par}` : ""}` : "—"}</td>
          </tr>))}</tbody>
      </table></div>
      {sel && <div className="veille-bloc">
        <div className="veille-ligne"><b>{sel.nom}</b><span className="infra-muted">{sel.id} · {sel.usage} · {sel.type}</span>
          <label><input type="checkbox" checked={sel.actif} onChange={(e) => setSel({ ...sel, actif: e.target.checked })} /> actif</label></div>
        <textarea rows={sel.type === "decision" ? 14 : 8} style={{ width: "100%", fontFamily: sel.type === "decision" ? "monospace" : undefined }} value={sel.texte} onChange={(e) => setSel({ ...sel, texte: e.target.value })} />
        <input style={{ width: "100%" }} placeholder="notes (pourquoi cette version)" value={sel.notes || ""} onChange={(e) => setSel({ ...sel, notes: e.target.value })} />
        <div className="veille-ligne">
          <button type="button" onClick={enregistrer}>Enregistrer (nouvelle version)</button>
          {sel.systeme && sel.defaut && <button type="button" className="secondary" onClick={() => setSel({ ...sel, texte: sel.defaut })}>Reprendre le texte du code</button>}
          {(sel.personnalise || !sel.systeme) && <button type="button" className="secondary" onClick={revenir}>{sel.systeme ? "Revenir au code" : "Supprimer"}</button>}
          <button type="button" className="secondary" onClick={() => setSel(null)}>Fermer</button>
        </div>
        <p className="infra-muted"><b>Essayer</b> le texte affiché (même non enregistré) avec le modèle de l'usage :</p>
        <textarea rows={3} style={{ width: "100%" }} placeholder={sel.type === "decision" ? "un état, ex. : veille cyber | critique | Faille exploitée … | actifs : srv-a" : "texte d'entrée"} value={essai.texte} onChange={(e) => setEssai({ ...essai, texte: e.target.value })} />
        <div className="veille-ligne"><button type="button" disabled={!essai.texte.trim() || essai.attente} onClick={essayer}>{essai.attente ? "le modèle réfléchit…" : "Essayer"}</button>
          {essai.sortie?.modele && <span className="infra-muted">{essai.sortie.modele} · {essai.sortie.duree_s} s</span>}</div>
        {essai.sortie?.erreur && <p className="infra-error">{essai.sortie.erreur}</p>}
        {essai.sortie?.sortie && <pre className="veille-ia">{essai.sortie.sortie}</pre>}
        {hist.length > 0 && <details><summary>Historique ({hist.length} version(s))</summary>
          <table className="infra-table"><thead><tr><th>Version</th><th>Quand</th><th>Par</th><th>Notes</th><th></th></tr></thead>
            <tbody>{hist.map((h) => <tr key={h.version}><td>{h.version}</td><td className="infra-muted">{quand(h.maj)}</td><td className="infra-muted">{h.par || "—"}</td><td className="infra-muted">{h.notes || "—"}</td>
              <td><button type="button" className="secondary" title={h.texte} onClick={() => restaurer(h.version)}>Restaurer</button></td></tr>)}</tbody></table></details>}
      </div>}
    </div>
  );
}
