// Migration › « Préparer la réinstallation d'un nœud » (livraison #815) : 1. quorum (et simulation sans le nœud),
// 2. vérification des invités transférés et de ceux du nœud qui reste (charge, erreurs, HTTP 5xx), 3. sauvegardes
// (hors du nœud ? effacées avec la réinstallation ?), 4. PRA estimé CT / VM par CT / VM (scénarios, RPO, RTO, étapes).
// Données : si-agent-api /migration/preparation (sonde pve-preflight + copies au LAN + fiches des invités).
import { Fragment, useCallback, useEffect, useState } from "react";
import { fetchMigrationPrep } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import { HYPOTHESES, SYMBOLE, TON, compte, fmtAgeH, fmtMin, fmtOctets, requete, taux5xx } from "./prepLib.js";

const lire = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } };
const garder = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* navigation privée */ } };
const num = (v, s = "") => (v == null ? "—" : `${Math.round(v * 10) / 10}${s}`);

function Verdict({ v, children }) {
  return <span className={`np-tone ${TON[v] || "neutral"}`}>{SYMBOLE[v] || "?"} {children || v}</span>;
}
// Règle du hub (absolue) : « activer / régler X » donne le lien vers l'endroit où on le fait ; sinon « pas de lien :
// opération manuelle » avec ce qu'il faut faire.
function LiensOuManuel({ liens, manuel }) {
  if (!liens?.length && !manuel) return null;
  return (
    <div className="prep-liens">
      {(liens || []).map((l) => <a key={l.label} className="button-link" href={hubLink(l.view, l.params)}>{l.label} →</a>)}
      {!liens?.length && manuel && <p className="infra-muted">⚠ {manuel}</p>}
    </div>
  );
}

function Copier({ texte }) {
  const [ok, setOk] = useState(false);
  return <button type="button" className="secondary" onClick={() => navigator.clipboard?.writeText(texte).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); })}>{ok ? "copié ✓" : "Copier"}</button>;
}
function Actions({ actions }) {
  if (!actions?.length) return null;
  return (
    <table className="infra-table prep-actions"><thead><tr><th>Quand</th><th>Où</th><th>Commande (une à la fois)</th><th>Pourquoi</th></tr></thead>
      <tbody>{actions.map((a, i) => <tr key={i}><td className="infra-muted">{a.quand}</td><td><b>{a.ou}</b></td><td><code>{a.cmd}</code> <Copier texte={a.cmd} /></td><td className="infra-muted">{a.pourquoi}</td></tr>)}</tbody></table>
  );
}

function Quorum({ q }) {
  const a = q?.actuel;
  return (
    <div className="infra-card">
      <h3>1. Quorum <Verdict v={q?.verdict} /></h3>
      <p>{q?.detail}</p>
      {a && <p className="infra-muted">Maintenant : {a.quorate ? "quorum atteint" : "SANS quorum"} · {a.total} vote(s) sur {a.expected} attendus, quorum {a.quorum}
        {a.qdevice ? " · QDevice" : " · pas de QDevice"} · membres : {(a.membres || []).map((m) => `${m.name}${m.local ? " (relevé)" : ""} ×${m.votes}`).join(", ")}</p>}
      {q?.sans_cible && <p className="infra-muted">Sans le nœud à réinstaller : {q.sans_cible.votes} vote(s) pour un quorum de {q.sans_cible.quorum} → {q.sans_cible.quorate ? "quorum gardé" : "quorum PERDU"}</p>}
      <p className="infra-muted">Versions : {Object.entries(q?.versions || {}).map(([k, v]) => `${k} ${v || "?"}`).join(" · ")}</p>
      <Actions actions={q?.actions} />
    </div>
  );
}

function Controles({ liste }) {
  return (
    <div className="prep-controles">
      {(liste || []).map((c) => (
        <div key={c.id} className={`infra-card prep-controle ${TON[c.verdict]}`}>
          <div><Verdict v={c.verdict} /> <b>{c.titre}</b></div>
          <p className="infra-muted">{c.detail}</p>
          {c.id !== "quorum" && <Actions actions={c.actions} />}
          <LiensOuManuel liens={c.liens} manuel={c.manuel} />
        </div>
      ))}
    </div>
  );
}

export default function MigrationPrepView({ siAgentApiBase }) {
  const [cible, setCible] = useState(() => lire("prep.cible", ""));
  const [accueil, setAccueil] = useState(() => lire("prep.accueil", ""));
  const [params, setParams] = useState(() => lire("prep.params", {}));
  const [transferes, setTransferes] = useState(() => lire("prep.transferes", []));
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [ouvert, setOuvert] = useState(null);
  const [at, setAt] = useState(null);
  const charger = useCallback(() => fetchMigrationPrep(siAgentApiBase, requete({ cible, accueil, params, transferes }))
    .then((r) => { setD(r); setErr(r?.error || null); setAt(new Date()); }).catch((e) => setErr(e.message)), [siAgentApiBase, cible, accueil, params, transferes]);
  useEffect(() => { charger(); const t = setInterval(charger, 60000); return () => clearInterval(t); }, [charger]);
  useEffect(() => { garder("prep.cible", cible); garder("prep.accueil", accueil); garder("prep.params", params); garder("prep.transferes", transferes); }, [cible, accueil, params, transferes]);
  const invites = d?.invites || [];
  const actifs = invites.filter((i) => i.status === "running");
  const basculer = (vmid) => setTransferes(transferes.includes(vmid) ? transferes.filter((x) => x !== vmid) : [...transferes, vmid]);
  const cs = compte(invites, "sante"), cv = compte(actifs, "sauvegardes"), cp = compte(actifs, "pra");
  return (
    <div className="infra-page infra-scroll prep">
      <div className="infra-card prep-choix">
        <label>Nœud à réinstaller <select value={d?.cible || cible} onChange={(e) => setCible(e.target.value)}>{(d?.noeuds || []).map((n) => <option key={n}>{n}</option>)}</select></label>
        <label>Nœud qui reste <select value={d?.accueil || accueil} onChange={(e) => setAccueil(e.target.value)}>{(d?.noeuds || []).map((n) => <option key={n}>{n}</option>)}</select></label>
        {HYPOTHESES.map(([k, l]) => <label key={k}>{l} <input type="number" min="0.1" step="any" value={params[k] ?? d?.params?.[k] ?? ""} onChange={(e) => setParams({ ...params, [k]: e.target.value === "" ? undefined : Number(e.target.value) })} /></label>)}
        <button type="button" className="secondary" onClick={charger}>Actualiser</button>
        <span className="infra-muted">{at ? `lu ${at.toLocaleTimeString("fr-FR")}` : "lecture…"}{d?.releve ? ` · relevés : ${Object.entries(d.releve).map(([k, v]) => `${k} ${v.at || "?"}${v.ok ? "" : " (en échec)"}`).join(" · ")}` : ""}</span>
      </div>
      {err && <p className="infra-error">{err}</p>}
      {err && <LiensOuManuel liens={d?.liens} manuel={d?.manuel} />}
      {d?.verdict && <p className={`prep-bandeau ${TON[d.verdict]}`}><Verdict v={d.verdict}>{d.verdict === "ok" ? `prêt à réinstaller ${d.cible}` : d.verdict === "bloquant" ? `${d.cible} n'est PAS prêt à être réinstallé` : `${d.cible} : points à vérifier avant la réinstallation`}</Verdict></p>}
      {d?.quorum && <Quorum q={d.quorum} />}
      {d?.controles && <Controles liste={d.controles.filter((c) => c.id !== "quorum")} />}

      {invites.length > 0 && <>
        <h3>2. Invités : santé sur 24 h <span className="infra-muted">({cs.ok} sains, {cs.attention} à surveiller, {cs.bloquant} en défaut, {cs.inconnu} non lus)</span></h3>
        <div className="infra-table-wrap prep-table">
          <table className="infra-table">
            <thead><tr><th>Nœud</th><th>CT / VM</th><th>État</th><th title="cocher les invités transférés depuis le nœud à réinstaller">Transféré</th><th>Décision</th><th>CPU moy. / pic</th><th>Mém. pic</th><th>Journal 24 h (err / avert.)</th><th>Unités en échec</th><th>HTTP 5xx</th><th>Verdict</th></tr></thead>
            <tbody>{invites.map((i) => {
              const c = i.checks || {}, k = i.charge || {};
              return (
                <tr key={`${i.noeud}-${i.vmid}`}>
                  <td>{i.noeud}</td><td><b>{i.vmid}</b> {i.name} <span className="infra-muted">{i.type}</span></td><td>{i.status}</td>
                  <td><input type="checkbox" checked={!!i.transfere} onChange={() => basculer(i.vmid)} title={i.migration ? `migration ${i.migration.type} détectée` : ""} />{i.migration ? " (détecté)" : ""}</td>
                  <td className="infra-muted">{i.decision || "—"}</td>
                  <td>{num(k.cpu_avg_pct, " %")} / {num(k.cpu_max_pct, " %")}</td><td>{num(k.mem_max_pct, " %")}</td>
                  <td>{c.err_24h ?? "—"} / {c.warn_24h ?? "—"}{c.src ? <span className="infra-muted"> ({c.src})</span> : null}</td>
                  <td>{c.failed_units ?? "—"}</td>
                  <td>{taux5xx(c) == null ? "—" : `${taux5xx(c)} %`}{c.http_total ? <span className="infra-muted"> / {c.http_total}</span> : null}</td>
                  <td><Verdict v={i.sante?.verdict}>{(i.sante?.raisons || []).join(" ; ") || "sain"}</Verdict></td>
                </tr>);
            })}</tbody>
          </table>
        </div>

        <h3>3. Sauvegardes <span className="infra-muted">(invités actifs : {cv.ok} à jour, {cv.attention} à surveiller, {cv.bloquant} sans copie hors du nœud)</span></h3>
        {d.perdues?.nb > 0 && <p className="infra-error">⚠ {d.perdues.nb} archive(s) vzdump ({fmtOctets(d.perdues.octets)}) sur les stockages non partagés de {d.cible} disparaîtront avec la réinstallation : les copier ailleurs si elles servent encore.</p>}
        <div className="infra-table-wrap prep-table">
          <table className="infra-table">
            <thead><tr><th>CT / VM</th><th>Dernière sauvegarde</th><th>Hors du nœud (survit)</th><th>Dernière tâche vzdump</th><th>Copie au LAN</th><th>Verdict</th></tr></thead>
            <tbody>{invites.map((i) => {
              const s = i.sauvegardes || {};
              return (
                <tr key={`s-${i.noeud}-${i.vmid}`}>
                  <td><b>{i.vmid}</b> {i.name} <span className="infra-muted">{i.noeud} · {i.status}</span></td>
                  <td>{s.locale ? `${fmtAgeH(s.locale.age_h)} · ${s.locale.storage} (${s.locale.noeud})${s.locale.efface ? " · effacée avec la réinstallation" : ""}` : "aucune"}</td>
                  <td>{s.hors_noeud ? `${fmtAgeH(s.hors_noeud.age_h)} · ${s.hors_noeud.storage} (${s.hors_noeud.noeud}${s.hors_noeud.partage ? ", partagé" : ""})` : <span className="infra-error">aucune</span>}</td>
                  <td>{s.tache ? <span className={s.tache.ok ? "" : "infra-error"}>{s.tache.ok ? "réussie" : `échec : ${s.tache.status}`} · {fmtAgeH(s.tache.age_h)}</span> : "—"}</td>
                  <td>{s.lan ? `${fmtAgeH(s.lan.age_h)}${s.lan.ok === false ? " (dernière tentative en échec)" : ""}` : "—"}</td>
                  <td><Verdict v={s.verdict}>{(s.raisons || []).join(" ; ") || "à jour"}</Verdict></td>
                </tr>);
            })}</tbody>
          </table>
        </div>

        <h3>4. PRA estimé par CT / VM <span className="infra-muted">(invités actifs : {cp.ok} couverts, {cp.attention} avec une copie ancienne, {cp.bloquant} sans reprise possible)</span></h3>
        <p className="infra-muted">Si le nœud de l'invité tombe : RPO = données perdues (âge de la copie retenue), RTO = durée de reprise estimée (taille ÷ débits ci-dessus + démarrage + déplacement de l'IP OVH si MAC virtuelle + reprise du quorum si le cluster le perd). Cliquer une ligne pour les étapes.</p>
        <div className="infra-table-wrap prep-table">
          <table className="infra-table">
            <thead><tr><th>CT / VM</th><th>Taille</th><th>Scénario retenu</th><th>RPO</th><th>RTO</th><th>Verdict</th></tr></thead>
            <tbody>{invites.map((i) => {
              const p = i.pra || {}, r = p.retenu, cle = `${i.noeud}-${i.vmid}`;
              return (
                <Fragment key={`p-${cle}`}>
                  <tr className="prep-ligne" onClick={() => setOuvert(ouvert === cle ? null : cle)}>
                    <td><b>{i.vmid}</b> {i.name} <span className="infra-muted">{i.noeud} · {i.status}{i.conf?.vmac ? " · IP OVH" : ""}</span></td>
                    <td>{p.taille_go != null ? `${p.taille_go} Go` : "—"}</td>
                    <td>{r ? r.titre : <span className="infra-error">aucun</span>}</td>
                    <td>{r ? fmtAgeH(r.rpo_h) : "—"}</td><td>{r ? fmtMin(r.rto_min) : "—"}</td>
                    <td><Verdict v={p.verdict} /></td>
                  </tr>
                  {ouvert === cle && (
                    <tr className="prep-detail"><td colSpan={6}>
                      {(p.scenarios || []).map((s, j) => (
                        <div key={j} className="prep-scenario">
                          <b>{s.valide ? "✔" : "✗"} {s.titre}</b> <span className="infra-muted">RPO {fmtAgeH(s.rpo_h)} · RTO {fmtMin(s.rto_min)}{s.remarque ? ` · ${s.remarque}` : ""}</span>
                          {s.etapes?.length > 0 && <ol>{s.etapes.map((e, n) => <li key={n}><code>{e}</code></li>)}</ol>}
                        </div>))}
                      {!(p.scenarios || []).length && <p className="infra-error">Aucune copie de cet invité hors de son nœud : sauvegarde (vzdump vers un autre nœud ou un stockage partagé), réplication (pvesr) ou copie tirée au LAN à mettre en place.</p>}
                    </td></tr>
                  )}
                </Fragment>);
            })}</tbody>
          </table>
        </div>
      </>}
    </div>
  );
}
