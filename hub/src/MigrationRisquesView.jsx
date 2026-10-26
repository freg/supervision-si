// Migration › « Risques » (livraison #856) : récapitulatif PERMANENT du risque de chaque CT / VM sur cinq axes --
// sauvegarde (copies hors du nœud, distance, volume), réplication (pvesr), accès aux services (contrôlés toutes les
// 5 min depuis le hub : ports découverts sur les adresses fixes + cibles saisies ici), support (pool : santé,
// redondance), nœud (quorum, nœud à réinstaller). Données : /migration/risques.
import { useCallback, useEffect, useState } from "react";
import { fetchRisques, saveAccesCibles, verifierAcces, saveMigrationCible } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import { fmtOctets } from "./prepLib.js";
import { AXES, TON, SYMBOLE, NIVEAUX, filtrer, cibles } from "./copiesLib.js";

const date = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");

export default function MigrationRisquesView({ siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [f, setF] = useState({ texte: "", etat: "", noeud: "" });
  const [edit, setEdit] = useState(null);     // {key, texte}
  const [note, setNote] = useState(null);
  const load = useCallback(() => fetchRisques(siAgentApiBase).then((x) => { setD(x); setErr(x?.error || null); }).catch((e) => setErr(e.message)), [siAgentApiBase]);
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);
  if (!d) return <p className="infra-muted">{err || "lecture des risques…"}</p>;
  const lignes = filtrer(d.lignes, f);
  const noeuds = (d.noeuds || []).map((n) => n.name);
  const enregistrer = async () => {
    const r = await saveAccesCibles(siAgentApiBase, edit.key, cibles(edit.texte));
    setNote(r?.error ? ["ko", r.error] : ["ok", `Cibles de ${edit.key} enregistrées : contrôle au prochain passage (5 min) ou « Vérifier maintenant ».`]);
    if (!r?.error) { setEdit(null); load(); }
  };
  return (
    <div>
      {err && <p className="infra-error">{err}</p>}
      {err && (d.liens?.length || d.manuel) && (
        <div className="prep-liens">{(d.liens || []).map((l) => <a key={l.label} className="button-link" href={hubLink(l.view, l.params)}>{l.label} →</a>)}
          {!d.liens?.length && d.manuel && <p className="infra-muted">⚠ {d.manuel}</p>}</div>)}
      <div className="infra-card mig-controls">
        <b>Risque :</b> {Object.entries(d.resume || {}).map(([k, n]) => <span key={k} className={`np-tone ${NIVEAUX[k]}`} style={{ marginRight: 12 }}>{k} {n}</span>)}
        <label>Nœud à réinstaller <select value={d.cible || ""} onChange={async (e) => { await saveMigrationCible(siAgentApiBase, e.target.value); load(); }}>
          <option value="">aucun</option>{noeuds.map((n) => <option key={n}>{n}</option>)}</select></label>
        <button className="secondary" onClick={async () => { await verifierAcces(siAgentApiBase); setNote(["ok", "Contrôle d'accès lancé : résultat dans une minute environ."]); setTimeout(load, 45000); }}>Vérifier l'accès maintenant</button>
        <span className="infra-muted">relevé {date(d.at)}</span>
      </div>
      {note && <p className={`np-tone ${note[0] === "ok" ? "good" : "bad"}`}>{note[1]}</p>}
      <div className="infra-card">
        <b>Supports des nœuds :</b> {(d.noeuds || []).map((n) => (
          <span key={n.name} style={{ marginRight: 14 }}>{n.name} : {(n.pools || []).map((p) => (
            <span key={p.name} className={`np-tone ${p.health !== "ONLINE" ? "bad" : p.redondance === "non" ? "warn" : "good"}`}>{p.name} {p.health}{p.redondance === "non" ? " sans redondance" : ""} </span>))}</span>))}
      </div>
      <div className="mig-controls">
        <input placeholder="nom, numéro, nœud" value={f.texte} onChange={(e) => setF({ ...f, texte: e.target.value })} />
        <select value={f.etat} onChange={(e) => setF({ ...f, etat: e.target.value })}><option value="">tous les niveaux</option>{Object.keys(NIVEAUX).map((v) => <option key={v}>{v}</option>)}</select>
        <select value={f.noeud} onChange={(e) => setF({ ...f, noeud: e.target.value })}><option value="">tous les nœuds</option>{noeuds.map((n) => <option key={n}>{n}</option>)}</select>
      </div>
      <table className="infra-table">
        <thead><tr><th>Niveau</th><th>Invité</th><th>État</th>{AXES.map(([k, l]) => <th key={k}>{l}</th>)}</tr></thead>
        <tbody>{lignes.map((l) => (
          <tr key={l.key}>
            <td className={`np-tone ${NIVEAUX[l.niveau]}`}><b>{l.niveau}</b></td>
            <td><b>{l.node}/{l.vmid}</b> {l.name} <span className="infra-muted">{l.type === "lxc" ? "CT" : "VM"} · {fmtOctets(l.taille)}</span></td>
            <td>{l.status}</td>
            {AXES.map(([k]) => {
              const a = l.axes[k] || {};
              return (
                <td key={k} title={a.texte} className={`np-tone ${TON[a.etat] || "neutral"}`} style={{ maxWidth: 260, whiteSpace: "normal", wordBreak: "break-word", verticalAlign: "top" }}>
                  {SYMBOLE[a.etat] || "?"} <small>{a.texte}</small>
                  {k === "acces" && l.status === "running" && (edit?.key === l.key ? (
                    <div><textarea rows={3} style={{ width: "100%" }} placeholder={"https://service.exemple.fr/\ntcp://198.51.100.7:993"} value={edit.texte} onChange={(e) => setEdit({ ...edit, texte: e.target.value })} />
                      <button onClick={enregistrer}>Enregistrer</button> <button className="secondary" onClick={() => setEdit(null)}>Annuler</button></div>
                  ) : <div><button className="secondary" onClick={() => setEdit({ key: l.key, texte: ((d.manuels || {})[l.key] || []).join("\n") })}>Cibles…</button></div>)}
                </td>);
            })}
          </tr>))}</tbody>
      </table>
    </div>
  );
}
