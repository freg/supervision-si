// #828 Parc IA › Apprentissage : jeu de données du décideur tiré de NOS décisions de veille (statuts posés par une
// personne, rejets), export JSONL train / test, registre des entraînements LoRA (kit si-agent/tools/apprentissage),
// évaluation du modèle produit sur la part test. Aucune mise en service automatique.
import { useCallback, useEffect, useState } from "react";

let BASE = "";
async function api(path, { methode = "GET", corps } = {}) {
  const r = await fetch(`${BASE}${path}`, { method: methode, credentials: "include", headers: corps ? { "Content-Type": "application/json" } : undefined, body: corps ? JSON.stringify(corps) : undefined });
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.error || `HTTP ${r.status}`);
  return j;
}
const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)} %`);
const VIDE = { nom: "", modele_base: "unsloth/Qwen3-4B-Instruct-2507", hote: "", statut: "prevu", modele_produit: "", notes: "" };

export default function ApprentissageSection({ base, username }) {
  BASE = base || "";
  const [jeu, setJeu] = useState(null);
  const [ent, setEnt] = useState(null);
  const [err, setErr] = useState("");
  const [f, setF] = useState(null);
  const charger = useCallback(() => {
    api("/apprentissage/jeu").then(setJeu).catch((x) => setErr(x.message));
    api("/apprentissage/entrainements").then(setEnt).catch((x) => setErr(x.message));
  }, []);
  useEffect(() => { charger(); const t = setInterval(() => api("/apprentissage/entrainements").then(setEnt).catch(() => {}), 15000); return () => clearInterval(t); }, [charger]);
  async function enregistrer() {
    try { await api(f.id ? `/apprentissage/entrainements/${f.id}` : "/apprentissage/entrainements", { methode: f.id ? "PUT" : "POST", corps: { ...f, jeu: f.id ? undefined : jeu?.stats, par: username } }); setF(null); charger(); }
    catch (x) { setErr(x.message); }
  }
  async function evaluer(e, modele) {
    try { const r = await api(`/apprentissage/entrainements/${e.id}/evaluer`, { methode: "POST", corps: modele ? { modele } : {} }); setErr(`évaluation lancée : ${r.exemples} exemples de test avec ${r.modele}`); }
    catch (x) { setErr(x.message); }
  }
  const st = jeu?.stats;
  return (
    <div className="veille">
      {err && <p className="infra-muted" onClick={() => setErr("")}>{err}</p>}
      <div className="veille-bloc">
        <h3>Jeu de données du décideur</h3>
        <p className="infra-muted">Étiquettes tirées de vos décisions dans la Veille cyber : rejet ou « non applicable » posé par une personne → non urgent ;
          « à traiter / en cours / traité » posé par une personne → urgent s'il touche un de nos actifs ou une faille exploitée, gravité d'après la priorité vuln-api.
          Même entrée que la production (consigne du décideur et skill actif).</p>
        {st ? <p>{st.exemples} exemple(s) — entraînement {st.train}, test {st.test} — urgents {st.urgents} — gravités {Object.entries(st.gravites).map(([k, v]) => `${k} ${v}`).join(", ") || "—"}
          {" · "}<a href={`${BASE}/apprentissage/jeu?format=jsonl&part=train`}>JSONL entraînement</a> · <a href={`${BASE}/apprentissage/jeu?format=jsonl&part=test`}>JSONL test</a></p>
          : <p className="infra-muted">lecture…</p>}
        {st && st.exemples < 200 && <p className="infra-muted">Moins de 200 exemples : continuez à décider dans la veille avant d'entraîner (un LoRA sur trop peu d'exemples apprend surtout le bruit).</p>}
        {(jeu?.apercu || []).length > 0 && <details><summary>Aperçu</summary><table className="infra-table"><thead><tr><th>Part</th><th>État (entrée)</th><th>Attendu</th></tr></thead>
          <tbody>{jeu.apercu.map((e) => <tr key={e.id}><td>{e.part}</td><td className="infra-muted">{e.etat}</td><td>{e.attendu.urgent ? "urgent" : "non urgent"} · {e.attendu.gravite}</td></tr>)}</tbody></table></details>}
      </div>
      <div className="veille-bloc">
        <div className="veille-ligne"><h3 style={{ margin: 0 }}>Entraînements</h3><span style={{ flex: 1 }} /><button type="button" onClick={() => setF({ ...VIDE })}>Nouvel entraînement</button></div>
        <p className="infra-muted">Entraîner sur un hôte GPU NVIDIA avec <code>si-agent/tools/apprentissage/lora_unsloth.py</code> puis <code>ollama create</code> (pas de lien : opération manuelle, docs/apprentissage.md) ;
          renseigner ici le modèle produit, « Évaluer », comparer avec le modèle de production, et ne le déclarer dans Usages que s'il fait mieux.</p>
        {f && <div className="veille-ligne">
          <input placeholder="nom" value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} />
          <input placeholder="modèle de base" value={f.modele_base} onChange={(e) => setF({ ...f, modele_base: e.target.value })} />
          <input placeholder="hôte (agent)" value={f.hote} onChange={(e) => setF({ ...f, hote: e.target.value })} />
          <select value={f.statut} onChange={(e) => setF({ ...f, statut: e.target.value })}>{(ent?.statuts || []).map((s) => <option key={s}>{s}</option>)}</select>
          <input placeholder="modèle produit (nom Ollama)" value={f.modele_produit} onChange={(e) => setF({ ...f, modele_produit: e.target.value })} />
          <input placeholder="notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
          <button type="button" onClick={enregistrer}>Enregistrer</button><button type="button" className="secondary" onClick={() => setF(null)}>Annuler</button>
        </div>}
        <div className="infra-table-wrap"><table className="infra-table">
          <thead><tr><th>Nom</th><th>Base</th><th>Hôte</th><th>État</th><th>Modèle produit</th><th>Jeu</th><th>Évaluation (part test)</th><th></th></tr></thead>
          <tbody>{(ent?.entrainements || []).map((e) => (
            <tr key={e.id}><td>{e.nom}</td><td className="infra-muted">{e.modele_base}</td><td className="infra-muted">{e.hote || "—"}</td><td>{e.statut}</td><td>{e.modele_produit || "—"}</td>
              <td className="infra-muted">{e.jeu ? `${e.jeu.train} / ${e.jeu.test}` : "—"}</td>
              <td>{e.evaluation ? (e.evaluation.erreur ? <span className="infra-error">{e.evaluation.erreur}</span>
                : <>{e.evaluation.modele} : urgent {pct(e.evaluation.accord_urgent)}, gravité {pct(e.evaluation.accord_gravite)} <span className="infra-muted">({e.evaluation.valides}/{e.evaluation.n})</span></>) : "—"}</td>
              <td><div className="veille-actions">
                <button type="button" className="secondary" onClick={() => setF({ ...VIDE, ...e })}>Modifier</button>
                <button type="button" disabled={!e.modele_produit} onClick={() => evaluer(e)}>Évaluer</button>
                <button type="button" className="secondary" title="évaluer un autre modèle (ex. celui de production) sur la même part test"
                  onClick={() => { const m = window.prompt("Modèle à évaluer (nom Ollama) :"); if (m) evaluer(e, m); }}>Comparer…</button>
              </div></td></tr>))}
            {ent && !ent.entrainements.length && <tr><td colSpan={8} className="infra-muted">Aucun entraînement.</td></tr>}
          </tbody>
        </table></div>
      </div>
    </div>
  );
}
