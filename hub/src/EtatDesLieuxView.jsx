// Migration › « État des lieux » (livraison #857) : systèmes actifs (nœuds, CT, VM) -- système et fin de support,
// dernière mise à jour, correctifs en attente, versions obsolètes, services inclus, usage, exposition, interactions et
// dépendances -> niveau (urgent / à planifier / à surveiller / ok / inactif), raisons, actions. Suivi jour par jour ;
// version Excel pour les décideurs (sans jargon). Données : /etat-des-lieux (sonde pve-preflight, agent 0.6.1+).
import { Fragment, useCallback, useEffect, useState } from "react";
import { fetchEtat, saveEtatLibelles, saveEtatEol, saveEtatManuel, etatExportUrl, etatAuditUrl } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import { NIVEAUX, TON, TON_OS, COULEUR, filtrer, depuis, jour, points, maxTendance, nom } from "./etatLib.js";

function Tendance({ t }) {
  if (!t || t.length < 2) return <span className="infra-muted">Suivi commencé : la courbe apparaît à partir du deuxième jour.</span>;
  const cles = ["urgent", "à planifier", "à surveiller"];
  const m = maxTendance(t, cles);
  return (
    <span><svg width="320" height="64" style={{ verticalAlign: "middle" }} aria-label="évolution">{cles.map((k) => <polyline key={k} points={points(t, k, 320, 64, m)} fill="none" stroke={COULEUR[k]} strokeWidth="2" />)}</svg>
      <span className="infra-muted"> {t[0].jour} → {t[t.length - 1].jour} · {cles.map((k) => <span key={k} style={{ color: COULEUR[k], marginRight: 8 }}>■ {k}</span>)}</span></span>
  );
}

export default function EtatDesLieuxView({ siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [f, setF] = useState({ texte: "", niveau: "", type: "", noeud: "" });
  const [ouvert, setOuvert] = useState({});
  const [lib, setLib] = useState(null);      // {key, texte}
  const [eol, setEol] = useState(null);
  const [decl, setDecl] = useState(null);    // #858 : {key, famille, version, nom, maj, note}
  const [note, setNote] = useState(null);
  const load = useCallback(() => fetchEtat(siAgentApiBase).then((x) => { setD(x); setErr(x?.error || null); }).catch((e) => setErr(e.message)), [siAgentApiBase]);
  useEffect(() => { load(); const id = setInterval(load, 300000); return () => clearInterval(id); }, [load]);
  if (!d) return <p className="infra-muted">{err || "lecture de l'état des lieux…"}</p>;
  const lignes = filtrer(d.systemes, f);
  const noms = Object.fromEntries((d.systemes || []).map((l) => [l.key, nom(l)]));
  const r = d.resume || {};
  const enregistrerLib = async () => {
    const libelles = { ...(d.libelles || {}) };
    if (lib.texte.trim()) libelles[lib.key] = lib.texte.trim(); else delete libelles[lib.key];
    const x = await saveEtatLibelles(siAgentApiBase, libelles);
    setNote(x?.error ? ["ko", x.error] : ["ok", "Libellé enregistré."]);
    setLib(null); load();
  };
  const enregistrerDecl = async (effacer = false) => {
    const { key, ...fiche } = decl;
    const x = await saveEtatManuel(siAgentApiBase, key, effacer ? null : fiche);
    setNote(x?.error ? ["ko", x.error] : ["ok", effacer ? "Déclaration retirée." : `Système de ${key} déclaré.`]);
    if (!x?.error) { setDecl(null); load(); }
  };
  const enregistrerEol = async () => {
    let o; try { o = JSON.parse(eol); } catch (e) { setNote(["ko", `JSON invalide : ${e.message}`]); return; }
    const x = await saveEtatEol(siAgentApiBase, o);
    setNote(x?.error ? ["ko", x.error] : ["ok", "Dates de fin de support enregistrées."]);
    if (!x?.error) { setEol(null); load(); }
  };
  return (
    <div>
      {err && <p className="infra-error">{err}</p>}
      {err && (d.liens?.length || d.manuel) && (
        <div className="prep-liens">{(d.liens || []).map((l) => <a key={l.label} className="button-link" href={hubLink(l.view, l.params)}>{l.label} →</a>)}
          {!d.liens?.length && d.manuel && <p className="infra-muted">⚠ {d.manuel}</p>}</div>)}
      <div className="infra-card mig-controls">
        {NIVEAUX.map((n) => <span key={n} className={`np-tone ${TON[n]}`} style={{ marginRight: 10 }}><b>{r[n] ?? 0}</b> {n}</span>)}
        <span className={r.inconnus ? "np-tone warn" : "infra-muted"}>· {r.inconnus ?? 0} système(s) non identifié(s)</span>
        <span className="infra-muted">· {r.obsoletes ?? 0} système(s) plus maintenu(s) · {r.secu ?? 0} avec correctifs de sécurité en attente · {r.exposes ?? 0} exposé(s) sur Internet</span>
        <a className="button-link" style={{ color: "var(--accent, #4a9eda)" }} href={etatExportUrl(siAgentApiBase)}>Télécharger l'Excel pour les décideurs ↓</a>
        <a className="button-link" style={{ color: "var(--accent, #4a9eda)" }} href={etatAuditUrl(siAgentApiBase)} target="_blank" rel="noreferrer">Audit obsolescence et support (page à imprimer) ↗</a>
      </div>
      <div className="infra-card"><b>Évolution :</b> <Tendance t={d.tendance} /></div>
      {note && <p className={`np-tone ${note[0] === "ok" ? "good" : "bad"}`}>{note[1]}</p>}
      <div className="mig-controls">
        <input placeholder="nom, rôle, système" value={f.texte} onChange={(e) => setF({ ...f, texte: e.target.value })} />
        <select value={f.niveau} onChange={(e) => setF({ ...f, niveau: e.target.value })}><option value="">tous les niveaux</option>{NIVEAUX.map((n) => <option key={n}>{n}</option>)}</select>
        <select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="">tous les types</option>{["nœud", "CT", "VM", "serveur", "poste"].map((n) => <option key={n}>{n}</option>)}</select>
        <select value={f.noeud} onChange={(e) => setF({ ...f, noeud: e.target.value })}><option value="">tous les nœuds</option>{[...new Set((d.systemes || []).map((l) => l.node))].map((n) => <option key={n}>{n}</option>)}</select>
      </div>
      <div style={{ overflowX: "auto" }}><table className="infra-table">
        <thead><tr><th>Niveau</th><th>Système</th><th>Rôle</th><th>Système d'exploitation</th><th>Mise à jour</th><th>Versions clés</th><th>Usage</th><th>Dépendances</th><th>Pourquoi / que faire</th></tr></thead>
        <tbody>{lignes.map((l) => (
          <Fragment key={l.key}>
            <tr style={{ verticalAlign: "top" }}>
              <td className={`np-tone ${TON[l.niveau]}`}><b>{l.niveau}</b>{l.score ? <div className="infra-muted">score {l.score} · impact {l.impact}</div> : null}</td>
              <td><b style={{ cursor: "pointer" }} onClick={() => setOuvert({ ...ouvert, [l.key]: !ouvert[l.key] })}>{l.key}</b> {l.name} <span className="infra-muted">{l.type}</span>
                {lib?.key === l.key ? <div><input value={lib.texte} onChange={(e) => setLib({ ...lib, texte: e.target.value })} placeholder="libellé pour les décideurs" /> <button onClick={enregistrerLib}>OK</button></div>
                  : <div className="infra-muted" style={{ cursor: "pointer" }} onClick={() => setLib({ key: l.key, texte: l.libelle || "" })}>{l.libelle ? `« ${l.libelle} » ✎` : "+ libellé"}</div>}</td>
              <td>{(l.roles || []).join(", ") || "—"}{l.expose ? <div className="np-tone warn">exposé sur Internet</div> : null}</td>
              <td className={`np-tone ${TON_OS[l.os?.statut] || "neutral"}`}>{l.os?.nom || "non relevé"}<div className="infra-muted">{l.os?.fin ? `fin : ${jour(l.os.fin)} (${l.os.statut})` : l.os?.statut}</div>
                {l.source === "lu hors ligne" && <div className="infra-muted">lu hors ligne (disque de la VM arrêtée)</div>}
                {(l.source === "aucune" || l.source === "déclaré") && (decl?.key === l.key ? (
                  <div style={{ display: "grid", gap: 4, marginTop: 4 }}>
                    <select value={decl.famille} onChange={(e) => setDecl({ ...decl, famille: e.target.value })}>{["debian", "ubuntu", "windows", "windows-server", "centos", "rocky", "almalinux", "alpine", "autre"].map((x) => <option key={x}>{x}</option>)}</select>
                    <input placeholder="version (12, 22.04, 2019…)" value={decl.version} onChange={(e) => setDecl({ ...decl, version: e.target.value })} />
                    <input placeholder="nom affiché (facultatif)" value={decl.nom} onChange={(e) => setDecl({ ...decl, nom: e.target.value })} />
                    <label className="infra-muted">dernière mise à jour <input type="date" value={decl.maj} onChange={(e) => setDecl({ ...decl, maj: e.target.value })} /></label>
                    <input placeholder="note (ex. appliance, relevé du 26/10)" value={decl.note} onChange={(e) => setDecl({ ...decl, note: e.target.value })} />
                    <div><button onClick={() => enregistrerDecl()}>Enregistrer</button> {l.source === "déclaré" && <button className="secondary" onClick={() => enregistrerDecl(true)}>Retirer</button>} <button className="secondary" onClick={() => setDecl(null)}>Annuler</button></div>
                  </div>
                ) : <div style={{ cursor: "pointer" }} className="infra-muted" onClick={() => { const m = (d.manuels || {})[l.key] || {}; setDecl({ key: l.key, famille: m.famille || "debian", version: m.version || "", nom: m.nom || "", maj: m.maj || "", note: m.note || "" }); }}>
                  {l.source === "déclaré" ? `déclaré à la main ✎${l.note ? ` · ${l.note}` : ""}` : "+ déclarer le système"}</div>)}</td>
              <td>{l.maj_jours != null ? `il y a ${depuis(l.maj_jours)}` : "—"}<div className={l.attente_secu ? "np-tone bad" : "infra-muted"}>{l.attente != null ? `${l.attente} en attente${l.attente_secu ? `, dont ${l.attente_secu} de sécurité` : ""}` : ""}</div></td>
              <td>{(l.composants || []).map((c) => <div key={c.nom + c.version} className={`np-tone ${TON_OS[c.statut] || "neutral"}`}>{c.nom} {c.version} <small>({c.statut}{c.note ? ` ; ${c.note}` : ""})</small></div>)}</td>
              <td>{l.usage}<div className="infra-muted">{l.usage_detail?.clients ? `${l.usage_detail.clients} client(s)` : ""}{l.usage_detail?.requetes ? ` · ${l.usage_detail.requetes} req.` : ""}{l.usage_detail?.cpu_moy_pct != null ? ` · CPU ${Math.round(l.usage_detail.cpu_moy_pct)} %` : ""}</div></td>
              <td>{l.utilise?.length ? <div>utilise : {l.utilise.map((k) => noms[k] || k).join(", ")}</div> : null}{l.dependants?.length ? <div className="np-tone warn">utilisé par : {l.dependants.map((k) => noms[k] || k).join(", ")}</div> : null}{!l.utilise?.length && !l.dependants?.length ? "—" : null}</td>
              <td style={{ minWidth: 300, maxWidth: 420, whiteSpace: "normal" }}><small>{(l.raisons || []).join(" ; ") || "—"}</small>{l.actions?.length ? <div><b>→</b> {l.actions.join(" ; ")}</div> : null}</td>
            </tr>
            {ouvert[l.key] && <tr><td colSpan={9} className="infra-muted">
              Noyau {l.noyau || "?"} · adresses {(l.ips || []).join(", ") || "?"} · écoute {(l.ecoute || []).map((e) => `${e.port} (${e.proc})`).join(", ") || "—"}
              <div>Services actifs : {(l.services || []).join(", ") || "—"}</div></td></tr>}
          </Fragment>))}</tbody>
      </table></div>
      <div className="infra-card">
        <b>Interactions entre systèmes ({(d.dependances || []).length})</b>
        <table className="infra-table"><thead><tr><th>Système</th><th>utilise</th><th>pour</th><th>Connexions</th></tr></thead>
          <tbody>{(d.dependances || []).map((x, i) => <tr key={i}><td>{noms[x.de] || x.de}</td><td>{noms[x.vers] || x.vers}</td><td>{x.nature}</td><td>{x.n}</td></tr>)}</tbody></table>
        <p className="infra-muted">Relevées à partir des connexions établies au moment du relevé (toutes les 15 min) : une interaction rare peut manquer.</p>
      </div>
      <div className="infra-card">
        <b>Serveurs utilisés mais non suivis ({(d.non_suivis || []).length})</b>
        <table className="infra-table"><thead><tr><th>Adresse</th><th>Services</th><th>Utilisé par</th><th>dont postes</th><th>Connexions</th></tr></thead>
          <tbody>{(d.non_suivis || []).map((x) => <tr key={x.ip}><td><b>{x.ip}</b> <span className="infra-muted">{x.interne ? "réseau interne" : "Internet"}</span></td>
            <td>{x.natures.join(", ")} <span className="infra-muted">({x.ports.join(", ")})</span></td><td>{x.clients} système(s) <span className="infra-muted">{x.utilise_par.map((k) => noms[k] || k).join(", ")}</span></td>
            <td>{x.postes}</td><td>{x.connexions}</td></tr>)}</tbody></table>
        <p className="infra-muted">Relevés à partir des connexions des systèmes et des postes suivis. Un serveur interne de cette liste (serveur de fichiers, NAS…) s'ajoute au suivi dans <code>/etc/si-agent/systemes-remote.json</code> de l'agent qui le joint (sonde systemes) -- pas de lien : opération manuelle.</p>
      </div>
      <div className="infra-card">
        <b>Dates de fin de support (références)</b> {!eol && <button className="secondary" onClick={() => setEol(JSON.stringify({ debian: d.eol?.debian, php: d.eol?.php }, null, 2))}>Corriger une date</button>}
        {eol ? <div><textarea rows={12} style={{ width: "100%", fontFamily: "monospace" }} value={eol} onChange={(e) => setEol(e.target.value)} />
          <button onClick={enregistrerEol}>Enregistrer</button> <button className="secondary" onClick={() => setEol(null)}>Annuler</button></div>
          : <p className="infra-muted">Familles suivies : {Object.keys(d.eol || {}).join(", ")}. Un paquet de la distribution reste « maintenu » tant que le système l'est.</p>}
      </div>
    </div>
  );
}
