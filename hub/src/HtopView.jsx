// Tuile « htop » (livraison #800) : tous les hôtes en direct (Proxmox, VM, CT) relevés toutes les 2 s par l'émetteur
// si-htop et rassemblés par le relais UDP -- CPU, cœurs, iowait, steal, mémoire (ARC ZFS à part), swap, charge, disques,
// constats soutenus ; détail d'un hôte (courbes 10 min et 24 h, processus, invités) ; capacité : que devient un nœud
// si on y déplace des CT / VM (pics des 24 dernières heures). Rafraîchie toutes les 3 s. Données : si-agent-api /htop.
import { useEffect, useMemo, useState } from "react";
import { fetchHtop, fetchHtopHote } from "./siAgentClient.js";
import { go, num, pctOf, niveau, niveauHote, grouper, invites, projeter, sparkPath, maxDisque } from "./htopLib.js";

const NAT = { pve: "PVE", vm: "VM", ct: "CT", hote: "hôte" };
const TONE_LABEL = { critical: "critique", warning: "au seuil", near: "proche" };
// #803 : l'ARC ZFS ne compte que pour un Proxmox / un hôte (vu depuis un CT, c'est celui de l'hôte) ; les cœurs d'un CT
// (lxcfs) ne sont pas significatifs
const arcDe = (h) => (h.nature === "pve" || h.nature === "hote" ? (h.memoire || [])[2] || 0 : 0);

function Barre({ v, seuil, critique, texte }) {
  if (v == null) return <span className="infra-muted">—</span>;
  const lv = niveau(v, seuil, critique);
  return (
    <span className="infra-meter-wrap" title={texte || `${num(v)} %`}>
      <span className="infra-meter"><span className={`fill ${lv.tone === "near" ? "" : lv.tone}`} style={{ width: `${Math.min(100, v)}%` }} /></span>
      <em>{texte || `${num(v)} %`}{lv.tone === "critical" ? " ⛔" : lv.tone === "warning" ? " ⚠" : ""}</em>
    </span>
  );
}

function Coeurs({ coeurs }) {
  if (!coeurs?.length) return <span className="infra-muted">—</span>;
  return <span className="infra-cores" title={coeurs.map((c, i) => `${i}: ${c ?? "?"} %`).join("  ")}>{coeurs.map((c, i) => <i key={i} style={{ height: `${Math.max(6, c || 0)}%` }} className={niveau(c, 90, 98).tone} />)}</span>;
}

function Courbe({ titre, series, max = 100, unite = "%" }) {
  const w = 300, h = 60;
  return (
    <figure className="infra-card htop-courbe">
      <figcaption>{titre}</figcaption>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} role="img" aria-label={titre} preserveAspectRatio="none">
        <line x1="0" x2={w} y1={h / 2} y2={h / 2} stroke="var(--viz-grid)" strokeDasharray="3 3" />
        {series.map((s) => <path key={s.nom} d={sparkPath(s.valeurs, w, h, max)} fill="none" stroke={s.couleur} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />)}
      </svg>
      <ul className="infra-legend">{series.map((s) => { const v = s.valeurs.filter((x) => x != null); return <li key={s.nom}><i style={{ background: s.couleur }} />{s.nom}<b>{v.length ? `${num(v[v.length - 1])} ${unite} · pic ${num(Math.max(...v))}` : "—"}</b></li>; })}</ul>
    </figure>
  );
}

function Detail({ base, nom, seuils, onClose }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let stop = false;
    const load = () => fetchHtopHote(base, nom).then((x) => { if (!stop) { if (x?.error) setErr(x.error); else { setD(x); setErr(null); } } }).catch((e) => !stop && setErr(e.message));
    load();
    const id = setInterval(load, 3000);
    return () => { stop = true; clearInterval(id); };
  }, [base, nom]);
  if (err) return <div className="infra-card"><p className="infra-error">{err}</p><button className="secondary" onClick={onClose}>Fermer</button></div>;
  if (!d) return <div className="infra-card infra-muted">lecture de {nom}…</div>;
  const b = d.brut || [], m = d.minutes || [];
  const C = ["var(--viz-1)", "var(--viz-2)", "var(--viz-3)", "var(--viz-4, var(--viz-1))"];
  return (
    <div className="htop-detail">
      <div className="infra-top">
        <h3>{d.nom} <span className="infra-muted">{NAT[d.nature] || d.nature} · {d.ncpu} cœurs · {d.processus} processus · {d.adresse || ""}</span></h3>
        <button className="secondary" onClick={onClose}>Fermer</button>
      </div>
      <div className="infra-grid">
        <Courbe titre="10 dernières minutes (2 s)" series={[{ nom: "CPU", couleur: C[0], valeurs: b.map((x) => x[1]) }, { nom: "mémoire", couleur: C[1], valeurs: b.map((x) => x[2]) },
          { nom: "iowait", couleur: C[2], valeurs: b.map((x) => x[3]) }, { nom: "steal", couleur: C[3], valeurs: b.map((x) => x[4]) }]} />
        <Courbe titre="24 heures (pic par minute)" series={[{ nom: "CPU", couleur: C[0], valeurs: m.map((x) => x[2]) }, { nom: "mémoire", couleur: C[1], valeurs: m.map((x) => x[4]) },
          { nom: "iowait", couleur: C[2], valeurs: m.map((x) => x[5]) }, { nom: "steal", couleur: C[3], valeurs: m.map((x) => x[6]) }]} />
        {d.nature !== "ct" && <figure className="infra-card">
          <figcaption>Cœurs</figcaption>
          <div className="htop-coeurs">{(d.coeurs || []).map((c, i) => <Barre key={i} v={c} seuil={seuils.cpu} critique={98} texte={`${i} · ${num(c)} %`} />)}</div>
        </figure>}
        <figure className="infra-card">
          <figcaption>Mémoire, swap, disques</figcaption>
          <div className="htop-coeurs">
            <Barre v={d.memoire_pct} seuil={seuils.memoire} critique={97} texte={`mémoire ${go((d.memoire || [])[1])} / ${go((d.memoire || [])[0])}${arcDe(d) ? ` dont ARC ${go(arcDe(d))} (${num(d.memoire_pct)} % hors ARC)` : ""}`} />
            {d.swap?.[0] ? <Barre v={d.swap_pct} seuil={seuils.swap} critique={90} texte={`swap ${go(d.swap[1])} / ${go(d.swap[0])}`} /> : null}
            {(d.disques || []).map(([mp, t, u]) => <Barre key={mp} v={pctOf(u, t)} seuil={seuils.disque} critique={97} texte={`${mp} · ${go(u)} / ${go(t)}`} />)}
            {(d.pools || []).map(([n, t, u, st]) => <Barre key={n} v={pctOf(u, t)} seuil={seuils.pool} critique={95} texte={`zfs ${n} · ${go(u)} / ${go(t)} · ${st}`} />)}
          </div>
        </figure>
      </div>
      {(d.invites || []).length > 0 && (
        <div className="infra-table-wrap">
          <table className="infra-table">
            <thead><tr><th>ID</th><th>Invité</th><th>Type</th><th>% du nœud</th><th>Cœurs</th><th>Mémoire</th><th>Hors cache / limite</th></tr></thead>
            <tbody>{d.invites.map((g) => (
              <tr key={g[0]}><td>{g[0]}</td><td>{g[1]}</td><td>{NAT[g[2]] || g[2]}</td><td><Barre v={g[3]} seuil={seuils.cpu} critique={98} /></td><td>{num(g[4])}</td><td>{go(g[5])}</td>
                <td>{g[7] ? <Barre v={pctOf(g[6], g[7])} seuil={seuils.invite_memoire} critique={99} texte={`${go(g[6])} / ${go(g[7])}`} /> : go(g[6])}</td></tr>))}</tbody>
          </table>
        </div>
      )}
      <div className="infra-table-wrap">
        <table className="infra-table">
          <thead><tr><th>PID</th><th>Processus</th><th>CPU %</th><th>Mémoire (RSS)</th><th>Invité</th></tr></thead>
          <tbody>{(d.processus_top || []).map((p) => <tr key={p[0]}><td>{p[0]}</td><td className="infra-mono">{p[1]}</td><td>{num(p[2])}</td><td>{go(p[3])}</td><td>{p[4] || ""}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

function Capacite({ hotes }) {
  const pves = hotes.filter((h) => h.nature === "pve");
  const [cible, setCible] = useState("");
  const [choix, setChoix] = useState([]);
  const c = cible || pves[0]?.nom || "";
  const autres = invites(hotes).filter((g) => g.pve !== c);
  const p = useMemo(() => projeter(hotes, c, choix), [hotes, c, choix]);
  const coche = (g) => choix.some((x) => x.pve === g.pve && String(x.vmid) === String(g.vmid));
  const basculer = (g) => setChoix(coche(g) ? choix.filter((x) => !(x.pve === g.pve && String(x.vmid) === String(g.vmid))) : [...choix, { pve: g.pve, vmid: g.vmid }]);
  if (!pves.length) return <p className="infra-muted">Aucun Proxmox ne remonte encore : installer l'émetteur si-htop sur les nœuds (si-agent/htop/README.md).</p>;
  const V = { ok: ["", "tient la charge"], juste: ["warning", "juste : marge faible"], non: ["critical", "ne tient pas"] };
  return (
    <div className="infra-page">
      <div className="infra-top">
        <label>Nœud d'accueil <select value={c} onChange={(e) => { setCible(e.target.value); setChoix([]); }}>{pves.map((h) => <option key={h.nom}>{h.nom}</option>)}</select></label>
        <span className="infra-muted">Cocher les CT / VM à y déplacer : leurs pics des 24 dernières heures s'ajoutent à ceux du nœud.</span>
      </div>
      <div className="infra-grid">
        <div className="infra-table-wrap">
          <table className="infra-table">
            <thead><tr><th></th><th>Depuis</th><th>ID</th><th>Invité</th><th>Cœurs (pic)</th><th>Mémoire hors cache (pic)</th><th>Limite</th></tr></thead>
            <tbody>{autres.length === 0 ? <tr><td colSpan={7} className="infra-muted">Aucun invité sur les autres Proxmox.</td></tr> : autres.map((g) => (
              <tr key={`${g.pve}:${g.vmid}`} onClick={() => basculer(g)} className="htop-clic">
                <td><input type="checkbox" readOnly checked={coche(g)} aria-label={`déplacer ${g.vmid}`} /></td><td>{g.pve}</td><td>{g.vmid}</td><td>{g.nom}</td>
                <td>{num(g.coeurs)} ({num(g.pic_coeurs)})</td><td>{go(g.mem)} ({go(g.pic_mem)})</td><td>{go(g.limite)}</td></tr>))}</tbody>
          </table>
        </div>
        {p && (
          <figure className="infra-card">
            <figcaption>{c} avec {p.invites.length} invité(s) de plus</figcaption>
            <p className={`infra-status ${V[p.verdict][0]}`}>{p.verdict === "ok" ? "✔" : p.verdict === "juste" ? "⚠" : "⛔"} {V[p.verdict][1]}</p>
            <table className="infra-table">
              <thead><tr><th></th><th>Aujourd'hui</th><th>Après</th></tr></thead>
              <tbody>
                <tr><td>CPU pic 24 h</td><td>{num(p.cpu_pic[0], " %")}</td><td><Barre v={p.cpu_pic[1]} seuil={90} critique={100} /></td></tr>
                <tr><td>CPU p95 24 h</td><td>{num(p.cpu_p95[0], " %")}</td><td><Barre v={p.cpu_p95[1]} seuil={80} critique={90} /></td></tr>
                <tr><td>Mémoire hors ARC, pic</td><td>{num(p.mem_pic[0], " %")}</td><td><Barre v={p.mem_pic[1]} seuil={80} critique={90} /></td></tr>
                <tr><td>Mémoire allouée (limites)</td><td>{num(p.alloue[0], " %")}</td><td><Barre v={p.alloue[1]} seuil={100} critique={150} /></td></tr>
              </tbody>
            </table>
            <p className="infra-muted">+{num(p.coeurs)} cœurs et +{go(p.mem)} au pic. {p.minutes < 1440 ? `Historique du nœud : ${p.minutes} min (moins de 24 h : à confirmer après une journée complète). ` : ""}
              Hypothèses : cœurs de même puissance ; l'ARC ZFS se réduit sous la pression ; un invité déjà répliqué sur ce nœud y occupe déjà sa place disque.</p>
          </figure>
        )}
      </div>
    </div>
  );
}

export default function HtopView({ onBack, siAgentApiBase }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState("hotes");
  const [tri, setTri] = useState({ col: "cpu", dir: -1 });
  const [vu, setVu] = useState(null);
  useEffect(() => {
    let stop = false;
    const load = () => fetchHtop(siAgentApiBase).then((d) => { if (!stop) { if (d?.error) setErr(d.error); else { setData(d); setErr(null); } } }).catch((e) => !stop && setErr(e.message));
    load();
    const id = setInterval(load, 3000);
    return () => { stop = true; clearInterval(id); };
  }, [siAgentApiBase]);
  const S = data?.seuils || {};
  const lignes = useMemo(() => grouper(data?.hotes || [], tri.col, tri.dir), [data, tri]);
  const th = (col, label) => <th onClick={() => setTri({ col, dir: tri.col === col ? -tri.dir : col === "nom" ? 1 : -1 })} className={tri.col === col ? "sorted" : ""}>{label}{tri.col === col ? (tri.dir < 0 ? " ▼" : " ▲") : ""}</th>;
  const constats = data?.constats || [];
  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>htop</h2>
        <div className="infra-tabs">{[["hotes", "Hôtes"], ["capacite", "Capacité"], ["constats", `Constats${constats.length ? ` (${constats.length})` : ""}`]].map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
        <span className="infra-muted">{data ? `${data.hotes.length} hôte(s) · ${data.abonnes} client(s) UDP · ${new Date(data.at * 1000).toLocaleTimeString("fr-FR")}` : "lecture…"}</span>
      </div>
      {err && <p className="infra-error">{err}</p>}
      {constats.some((a) => a.severity === "critical") && <p className="infra-status critical htop-bandeau">⛔ {constats.filter((a) => a.severity === "critical").map((a) => a.message).join(" · ")}</p>}
      {data && tab === "hotes" && (
        <div className="infra-scroll">
          {vu && <Detail base={siAgentApiBase} nom={vu} seuils={S} onClose={() => setVu(null)} />}
          <div className="infra-table-wrap">
            <table className="infra-table">
              <thead><tr>{th("nom", "Hôte")}<th>Type</th>{th("cpu", "CPU")}<th>Cœurs</th>{th("iowait", "iowait")}{th("steal", "steal")}{th("mem", "Mémoire")}{th("swap", "Swap")}{th("charge", "Charge / cœur")}{th("disque", "Disque le plus plein")}{th("age", "Relevé")}</tr></thead>
              <tbody>{lignes.length === 0 ? <tr><td colSpan={11} className="infra-muted">Aucun hôte : installer l'émetteur si-htop (si-agent/htop/README.md) et vérifier les clés et le port UDP du relais.</td></tr>
                : lignes.map(({ ind, h }) => { const lv = niveauHote(h, S); return (
                  <tr key={h.nom} className={`${h.nature === "pve" ? "infra-host" : ""} htop-clic ${vu === h.nom ? "htop-vu" : ""}`} onClick={() => setVu(vu === h.nom ? null : h.nom)}>
                    <td>{ind ? <span className="infra-muted">└ </span> : null}{h.nom}{lv && <span className={`infra-status ${lv === "near" ? "" : lv}`} title={TONE_LABEL[lv]}> {lv === "critical" ? "⛔" : lv === "warning" ? "⚠" : "·"}</span>}</td>
                    <td>{NAT[h.nature] || h.nature}</td>
                    <td><Barre v={h.cpu} seuil={S.cpu} critique={98} texte={h.cpu == null ? "—" : `${num(h.cpu)} % · ${h.ncpu} c.`} /></td><td>{h.nature === "ct" ? <span className="infra-muted">—</span> : <Coeurs coeurs={h.coeurs} />}</td>
                    <td><Barre v={h.iowait} seuil={S.iowait} critique={50} /></td><td><Barre v={h.steal} seuil={S.steal} critique={40} /></td>
                    <td><Barre v={h.memoire_pct} seuil={S.memoire} critique={97} texte={`${go((h.memoire || [])[1] - arcDe(h))} / ${go((h.memoire || [])[0])}`} /></td>
                    <td>{h.swap?.[0] ? <Barre v={h.swap_pct} seuil={S.swap} critique={90} /> : <span className="infra-muted">—</span>}</td>
                    <td>{h.charge_coeur == null ? "—" : <span className={`infra-status ${niveau(h.charge_coeur, S.charge, 4).tone}`}>{num(h.charge_coeur)} <small className="infra-muted">({(h.charge || []).join(" ")})</small></span>}</td>
                    <td><Barre v={maxDisque(h)} seuil={S.disque} critique={97} /></td>
                    <td className={h.muet ? "infra-status critical" : ""}>{h.muet ? `muet ${Math.round(h.age_s)} s` : `${Math.round(h.age_s)} s`}</td>
                  </tr>); })}</tbody>
            </table>
          </div>
        </div>
      )}
      {data && tab === "capacite" && <div className="infra-scroll"><Capacite hotes={data.hotes} /></div>}
      {data && tab === "constats" && (
        <div className="infra-table-wrap infra-scroll">
          <table className="infra-table">
            <thead><tr><th>Gravité</th><th>Constat</th><th>Depuis</th></tr></thead>
            <tbody>{constats.length === 0 ? <tr><td colSpan={3} className="infra-muted">Aucun constat. Seuils : CPU {S.cpu} %, mémoire {S.memoire} %, swap {S.swap} %, iowait {S.iowait} %, steal {S.steal} %, charge {S.charge} par cœur, soutenus {S.duree_s} s.</td></tr>
              : constats.map((a) => <tr key={a.code}><td><span className={`infra-status ${a.severity}`}>{a.severity === "critical" ? "⛔ critique" : "⚠ attention"}</span></td><td>{a.message}</td><td>{new Date(a.depuis * 1000).toLocaleString("fr-FR")}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
