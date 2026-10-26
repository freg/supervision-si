// Migration › « Copies et sauvegardes » (livraison #856) : état permanent et complet de TOUTES les copies de chaque
// CT / VM (répliques, copies ZFS, instantanés, vzdump, PBS, flux zfs send, rsync, restaurés), où qu'elles soient, et
// leur DISTANCE à la source (octets modifiés depuis, exact quand un instantané est commun ; 0 si la source est arrêtée
// et inchangée), leur VOLUME (correspond-il ?), et si elles survivent à la perte du nœud. Données : /copies/inventaire.
import { Fragment, useCallback, useEffect, useState } from "react";
import { fetchCopies, saveCopiesRegles } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import { fmtOctets } from "./prepLib.js";
import { TYPES, TON, SYMBOLE, filtrer, parType, age, volume, reglesTexte, reglesObjet } from "./copiesLib.js";

const date = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");
const V = ({ v }) => <span className={`np-tone ${TON[v] || "neutral"}`}>{SYMBOLE[v] || "?"} {v}</span>;

function Copies({ copies }) {
  return (
    <table className="infra-table"><thead><tr><th>Type</th><th>Hôte</th><th>Emplacement</th><th>Date</th><th>Taille</th><th>Distance</th><th>Volume</th><th>Survit à la perte du nœud</th><th>Support</th><th>Rattachement</th></tr></thead>
      <tbody>{copies.map((c, i) => (
        <tr key={i}>
          <td>{TYPES[c.type] || c.type}{c.nombre > 1 ? ` (${c.nombre})` : ""}</td><td><b>{c.hote}</b>{c.site ? <span className="infra-muted"> · {c.site}</span> : null}</td>
          <td><code>{c.emplacement}</code>{c.disque && c.disque !== "*" ? <span className="infra-muted"> · {c.disque}</span> : null}</td>
          <td>{date(c.at)} <span className="infra-muted">({age(c.age_h)})</span></td><td>{fmtOctets(c.taille)}</td>
          <td className={c.delta === 0 ? "np-tone good" : ""}>{c.distance}</td>
          <td className={`np-tone ${c.volume === "écart" ? "bad" : c.volume === "inconnu" ? "neutral" : "good"}`}>{volume(c)}</td>
          <td className={`np-tone ${c.survit ? "good" : "warn"}`}>{c.survit ? "oui" : "non"}</td>
          <td className={c.support?.fragile ? "np-tone warn" : "infra-muted"}>{c.support?.fragile || c.support?.type || "—"}</td>
          <td className="infra-muted">{c.rattachement}</td>
        </tr>))}</tbody></table>
  );
}

export default function MigrationCopiesView({ siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [f, setF] = useState({ texte: "", etat: "", noeud: "" });
  const [ouvert, setOuvert] = useState({});
  const [regles, setRegles] = useState(null);
  const [note, setNote] = useState(null);
  const load = useCallback(() => fetchCopies(siAgentApiBase).then((x) => { setD(x); setErr(x?.error || null); }).catch((e) => setErr(e.message)), [siAgentApiBase]);
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, [load]);
  if (!d) return <p className="infra-muted">{err || "lecture de l'inventaire…"}</p>;
  const lignes = filtrer(d.invites, f);
  const noeuds = [...new Set((d.invites || []).map((i) => i.node))];
  const enregistrer = async () => {
    const r = await saveCopiesRegles(siAgentApiBase, { origines: reglesObjet(regles.origines), dans: reglesObjet(regles.dans), sites: reglesObjet(regles.sites) });
    setNote(r?.error ? ["ko", r.error] : ["ok", "Règles enregistrées."]);
    if (!r?.error) { setRegles(null); load(); }
  };
  return (
    <div>
      {err && <p className="infra-error">{err}</p>}
      {(d.liens?.length || d.manuel) && err && (
        <div className="prep-liens">{(d.liens || []).map((l) => <a key={l.label} className="button-link" href={hubLink(l.view, l.params)}>{l.label} →</a>)}
          {!d.liens?.length && d.manuel && <p className="infra-muted">⚠ {d.manuel}</p>}</div>)}
      <div className="infra-card">
        <b>Invités :</b> {Object.entries(d.resume || {}).map(([k, n]) => <span key={k} style={{ marginRight: 12 }}><V v={k} /> {n}</span>)}
        <span className="infra-muted"> · relevé {date(d.at)} · distance 0 = copie identique à la source (source arrêtée et inchangée, ou instantané commun)</span>
      </div>
      <div className="infra-card">
        <b>Hôtes des copies</b>
        <table className="infra-table"><thead><tr><th>Hôte</th><th>Relevé</th><th>Pools ZFS</th><th>Autres supports</th></tr></thead>
          <tbody>{(d.hotes || []).map((h) => (
            <tr key={h.name}><td><b>{h.name}</b>{h.dans ? <span className="infra-muted"> (dans {h.dans})</span> : null}{h.site ? <span className="infra-muted"> · {h.site}</span> : null}</td>
              <td className={h.ok ? "" : "np-tone bad"}>{h.ok ? h.at : `injoignable : ${h.error}`}</td>
              <td>{(h.pools || []).map((p) => <span key={p.name} className={`np-tone ${p.health !== "ONLINE" ? "bad" : p.redondance === "non" ? "warn" : "good"}`} style={{ marginRight: 10 }}>
                {p.name} {p.health}{p.redondance === "non" ? " · sans redondance" : p.redondance === "partielle" ? " · redondance partielle" : ""} · {fmtOctets(p.alloc)} / {fmtOctets(p.size)}</span>)}</td>
              <td className="infra-muted">{Object.entries(h.supports || {}).map(([k, s]) => `${k} (${s.fs} ${s.device}, ${fmtOctets(s.avail)} libres)`).join(" · ") || "—"}</td></tr>))}</tbody></table>
      </div>
      <div className="mig-controls">
        <input placeholder="nom, numéro, nœud" value={f.texte} onChange={(e) => setF({ ...f, texte: e.target.value })} />
        <select value={f.etat} onChange={(e) => setF({ ...f, etat: e.target.value })}><option value="">tous les verdicts</option>{["critique", "attention", "ok", "info"].map((v) => <option key={v}>{v}</option>)}</select>
        <select value={f.noeud} onChange={(e) => setF({ ...f, noeud: e.target.value })}><option value="">tous les nœuds</option>{noeuds.map((n) => <option key={n}>{n}</option>)}</select>
        <button className="secondary" onClick={() => setOuvert(Object.fromEntries(lignes.map((l) => [l.key, true])))}>Tout déplier</button>
        <button className="secondary" onClick={() => setOuvert({})}>Tout replier</button>
      </div>
      <table className="infra-table">
        <thead><tr><th>Verdict</th><th>Invité</th><th>État</th><th>Taille</th><th>Meilleure copie hors du nœud</th><th>Copies (hors du nœud / toutes)</th><th>Raisons</th></tr></thead>
        <tbody>{lignes.map((l) => (
          <Fragment key={l.key}>
            <tr onClick={() => setOuvert({ ...ouvert, [l.key]: !ouvert[l.key] })} style={{ cursor: "pointer" }}>
              <td><V v={l.verdict} /></td>
              <td><b>{l.node}/{l.vmid}</b> {l.name} <span className="infra-muted">{l.type === "lxc" ? "CT" : "VM"}</span></td>
              <td>{l.status}{l.fige_depuis ? <span className="infra-muted"> · figé depuis {date(l.fige_depuis)}</span> : null}</td>
              <td>{fmtOctets(l.taille)}</td>
              <td>{l.meilleure ? <>{TYPES[l.meilleure.type] || l.meilleure.type} sur <b>{l.meilleure.hote}</b> · <span className={l.meilleure.delta === 0 ? "np-tone good" : ""}>{l.meilleure.distance}</span> · volume {volume(l.meilleure)}</> : <span className="np-tone bad">aucune</span>}</td>
              <td>{Object.entries(parType(l.copies, true)).map(([t, n]) => `${TYPES[t] || t} ×${n}`).join(", ") || "—"} <span className="infra-muted">/ {l.copies.length}</span></td>
              <td className="infra-muted">{(l.raisons || []).join(" ; ")}</td>
            </tr>
            {ouvert[l.key] && <tr><td colSpan={7}>{l.copies.length ? <Copies copies={l.copies} /> : <span className="infra-muted">Aucune copie trouvée.</span>}</td></tr>}
          </Fragment>))}</tbody>
      </table>
      {d.orphelines?.length > 0 && (
        <div className="infra-card">
          <b>Copies non rattachées ({d.orphelines.length})</b> <span className="infra-muted">-- source introuvable ou ambiguë : ajouter une règle d'origine ci-dessous</span>
          <table className="infra-table"><thead><tr><th>Hôte</th><th>Type</th><th>Emplacement</th><th>N°</th><th>Taille</th><th>Raison</th></tr></thead>
            <tbody>{d.orphelines.map((o, i) => <tr key={i}><td>{o.hote}</td><td>{TYPES[o.type] || o.type}</td><td><code>{o.emplacement}</code></td><td>{o.vmid}</td><td>{fmtOctets(o.taille)}</td><td className="infra-muted">{o.raison}</td></tr>)}</tbody></table>
        </div>)}
      <div className="infra-card">
        <b>Règles de rattachement</b> {!regles && <button className="secondary" onClick={() => setRegles({ origines: reglesTexte(d.regles?.origines), dans: reglesTexte(d.regles?.dans), sites: reglesTexte(d.regles?.sites) })}>Modifier</button>}
        {note && <span className={`np-tone ${note[0] === "ok" ? "good" : "bad"}`}> {note[1]}</span>}
        {regles ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 8, marginTop: 8 }}>
            {[["origines", "Origine des copies : préfixe de chemin = nœud (ex. ovh/pve2 = pve-2)"], ["dans", "Hôte virtuel = hôte physique (ex. pbs10 = pve10)"], ["sites", "Hôte = site (ex. pve-2 = OVH, pve10 = bureau)"]].map(([k, lib]) => (
              <label key={k}>{lib}<textarea rows={5} style={{ width: "100%" }} value={regles[k]} onChange={(e) => setRegles({ ...regles, [k]: e.target.value })} /></label>))}
            <div><button onClick={enregistrer}>Enregistrer</button> <button className="secondary" onClick={() => setRegles(null)}>Annuler</button></div>
          </div>
        ) : <p className="infra-muted">Sans règle, une copie est rattachée par le nom du nœud écrit dans son chemin (ovh/pve2, data/ovh/pve3, vzdump-lxc-101-pve3-…), puis par le cluster de l'hôte, puis par un numéro unique dans le parc. Un hôte virtuel (pbs10) ne protège pas l'hôte qui le porte.</p>}
      </div>
    </div>
  );
}
