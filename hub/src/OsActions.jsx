// #880 : bouton « Actions depuis l'OS » -- partout où un hôte, une VM ou un CT est présenté. Ouvre une fenêtre avec :
// ping (vers l'adresse affichée ou une autre, depuis l'agent choisi), processus (type htop), réseau (type ntop : débit par
// interface, connexions, iftop s'il est installé), journal du système. Exécuté par un agent (gestes encadrés, liste
// fermée, journal d'audit sur l'hôte) : l'hôte lui-même s'il a un agent, sinon son nœud Proxmox (conteneur : pct exec),
// sinon un autre agent pour le seul ping. Les résultats de la session restent dans une liste déroulante.
import { useEffect, useState } from "react";
import { fetchFleet, sendCommand, fetchCommand } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";

const API = import.meta.env.VITE_SI_AGENT_API_BASE_URL || "";
const ACTIONS = [["ping", "Ping"], ["top", "Processus (htop)"], ["net", "Réseau (ntop)"], ["syslog", "Journal"]];
const historique = [];   // résultats de la session (tous hôtes), le plus récent d'abord

async function executer(agentId, params, onWait) {
  const r = await sendCommand(API, agentId, "hostops", params);
  if (r?.error) throw new Error(r.error);
  const cid = r?.command?.id || r?.id, t0 = Date.now();
  while (Date.now() - t0 < 3 * 60 * 1000) {
    await new Promise((ok) => setTimeout(ok, 2000));
    onWait?.(Math.round((Date.now() - t0) / 1000));
    const c = await fetchCommand(API, cid).catch(() => null);
    if (c && (c.status === "done" || c.status === "failed")) {
      const res = c.result?.result || c.result || {};
      if (c.status === "failed" || res.ok === false) throw new Error(res.error || c.result?.error || "refusé par l'agent");
      return res;
    }
  }
  throw new Error("pas de réponse de l'agent en 3 min (hors ligne ? il relève ses commandes toutes les 30 s environ)");
}

/** agent : agent de l'hôte lui-même (s'il en a un) ; node + ct : conteneur d'un nœud Proxmox ; ip : adresse à pinguer. */
export default function OsActions({ label, ip, agent, node, ct, prefer, small = true }) {
  const [ouvert, setOuvert] = useState(false);
  return (
    <>
      <button type="button" className="secondary" title="actions depuis l'OS : ping, processus, réseau, journal"
        style={small ? { fontSize: 11, padding: "0 6px", marginLeft: 4, minHeight: 0, lineHeight: "18px" } : undefined}
        onClick={(e) => { e.stopPropagation(); e.preventDefault(); setOuvert(true); }}>⚙ OS</button>
      {ouvert && <Fenetre label={label} ip={ip} agent={agent} node={node} ct={ct} prefer={prefer} onClose={() => setOuvert(false)} />}
    </>
  );
}

function Fenetre({ label, ip, agent: agentDonne, node, ct, prefer, onClose }) {
  const [agents, setAgents] = useState([]);
  const [agent, setAgent] = useState(agentDonne || null);   // agent de l'hôte lui-même (donné, ou retrouvé par son nom)
  const [depuis, setDepuis] = useState(agentDonne || "");
  const [cible, setCible] = useState(ip || "");
  const [lignes, setLignes] = useState(200);
  const [prio, setPrio] = useState("");
  const [busy, setBusy] = useState("");
  const [sel, setSel] = useState(historique.length ? 0 : -1);
  const [, setTick] = useState(0);
  useEffect(() => {
    fetchFleet(API).then((fl) => {
      const liste = (Array.isArray(fl) ? fl : fl?.agents || []).filter((a) => a.active !== false);
      setAgents(liste);
      if (!agentDonne) {
        const court = (x) => String(x || "").toLowerCase().split(".")[0];
        const parNom = (n) => n && liste.find((a) => court(a.agent_id) === court(n) || court(a.hostname) === court(n));
        const propre = !ct && (parNom(label) || (!label && parNom(node)));
        if (propre) { setAgent(propre.agent_id); setDepuis(propre.agent_id); return; }
        const noeud = parNom(node), pref = prefer && liste.find((a) => a.agent_id === prefer);
        setDepuis((noeud || pref || liste.find((a) => a.online) || liste[0] || {}).agent_id || "");
      }
    }).catch(() => setAgents([]));
    const k = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [agentDonne, node, ct, label, prefer, onClose]);
  // sur l'hôte lui-même : tout ; dans un CT depuis son nœud : tout (pct exec) ; ailleurs : ping seulement
  const surHote = !!agent && depuis === agent;
  const dansCt = !agent && ct && node && agents.some((a) => a.agent_id === depuis && (a.agent_id === node || (a.hostname || "").split(".")[0] === node));
  const possible = (a) => a === "ping" || surHote || dansCt;
  const lancer = async (action) => {
    const params = { action, actor: "hub" };
    if (action === "ping") params.target = cible.trim();
    if (action === "syslog") { params.lines = lignes; if (prio) params.priority = prio; }
    if (dansCt && action !== "ping") params.ct = String(ct);
    setBusy(`${action}…`);
    const ent = { at: new Date().toLocaleTimeString("fr-FR"), label: label || ip || agent, action, depuis, cible: action === "ping" ? params.target : (dansCt ? `CT ${ct}` : agent) };
    try {
      const r = await executer(depuis, params, (s) => setBusy(`${action}… ${s} s`));
      historique.unshift({ ...ent, ok: true, texte: r.output || JSON.stringify(r, null, 2) });
    } catch (e) {
      historique.unshift({ ...ent, ok: false, texte: e.message });
    }
    historique.splice(30);
    setSel(0); setBusy(""); setTick((t) => t + 1);
  };
  const r = sel >= 0 ? historique[sel] : null;
  return (
    <div className="edl-fiche-fond" onClick={onClose}>
      <div className="edl-fiche" role="dialog" aria-label="actions depuis l'OS" onClick={(e) => e.stopPropagation()}>
        <header>
          <div><h3 style={{ margin: 0 }}>Actions depuis l'OS — {label || ip || agent}</h3>
            <span className="infra-muted">{surHote ? "exécutées sur l'hôte par son agent" : dansCt ? `exécutées dans le CT ${ct} par l'agent du nœud ${node}` : "pas d'agent sur cet hôte : ping seulement, depuis l'agent choisi"}</span></div>
          <button type="button" className="secondary" onClick={onClose} title="fermer (Échap)">✕</button>
        </header>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", margin: "8px 0" }}>
          <label>depuis <select value={depuis} onChange={(e) => setDepuis(e.target.value)}>
            {agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.agent_id}{a.online === false ? " (hors ligne)" : ""}</option>)}</select></label>
          <label>ping vers <input value={cible} onChange={(e) => setCible(e.target.value)} placeholder="adresse ou nom" style={{ width: 170 }} /></label>
          <label>journal : <input type="number" min="10" max="1000" value={lignes} onChange={(e) => setLignes(e.target.value)} style={{ width: 64 }} /> lignes
            <select value={prio} onChange={(e) => setPrio(e.target.value)}><option value="">tout</option><option value="warning">avertissements et +</option><option value="err">erreurs</option></select></label>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {ACTIONS.map(([a, l]) => <button key={a} type="button" disabled={!!busy || !depuis || !possible(a) || (a === "ping" && !cible.trim())}
            title={possible(a) ? "" : "nécessite un agent sur cet hôte (ou le nœud Proxmox du conteneur)"} onClick={() => lancer(a)}>{l}</button>)}
          {(surHote || dansCt) && <a href={hubLink("htop")} onClick={(e) => e.stopPropagation()} style={{ alignSelf: "center" }}>htop en direct ↗</a>}
          <span className="infra-muted" style={{ alignSelf: "center" }}>{busy}</span>
        </div>
        <div style={{ marginTop: 10 }}>
          <label>résultats <select value={sel} onChange={(e) => setSel(Number(e.target.value))} style={{ maxWidth: "100%" }}>
            {historique.length === 0 && <option value={-1}>aucun résultat pour l'instant</option>}
            {historique.map((h, i) => <option key={i} value={i}>{h.at} · {h.action} · {h.label}{h.action === "ping" ? ` → ${h.cible}` : ""} · depuis {h.depuis}{h.ok ? "" : " · ÉCHEC"}</option>)}
          </select></label>
          {r && <pre className="osa-sortie" style={{ color: r.ok ? undefined : "var(--danger)" }}>{r.texte}</pre>}
        </div>
      </div>
    </div>
  );
}
