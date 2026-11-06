// #996 : déployer Hermes / atelier / apprentissage (hermes-web) sur un nœud IA DEPUIS LE HUB -- archive déposée ici,
// installée par l'agent du nœud (commande noeud_ia, niveau « intervention »), nœud déclaré dans la passerelle par la tour.
import { useCallback, useEffect, useState } from "react";
import { hubLink } from "./hubLinks.js";
import { CMD_ARCHIVE, nomPropose, verifierFormulaire, etatNoeud, agentAJour, VERSION_AGENT_MIN } from "./iaNoeudsLib.js";

const TON = { ok: "var(--ok)", warn: "var(--warning)", bad: "var(--danger)" };
async function json(r) { const j = await r.json().catch(() => ({})); return r.ok ? j : { ...j, erreur: j.error || `${r.status}`, statut: r.status }; }

function Copier({ texte }) {
  const [ok, setOk] = useState(false);
  return <button type="button" className="secondary" onClick={() => navigator.clipboard?.writeText(texte).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); })}>{ok ? "✓ copié" : "📋 copier"}</button>;
}

export default function IaDeploiement({ siAgentApiBase, servicesApiBase, username, onDeclare }) {
  const [d, setD] = useState(null);
  const [agents, setAgents] = useState([]);
  const [fichier, setFichier] = useState(null);
  const [depot, setDepot] = useState(null);
  const [f, setF] = useState({ agent: "", nom: "", acces: "direct", adresse: "", shim: "campus", port: 8092 });
  const [envoi, setEnvoi] = useState(null);
  const [enEtat, setEnEtat] = useState(null);
  const charger = useCallback(() => {
    fetch(`${siAgentApiBase}/noeud-ia`).then(json).then(setD).catch((e) => setD({ erreur: e.message }));
  }, [siAgentApiBase]);
  useEffect(() => { charger(); fetch(`${siAgentApiBase}/agents`).then(json).then((j) => setAgents(j.agents || [])).catch(() => {}); }, [charger, siAgentApiBase]);
  useEffect(() => { const t = setInterval(charger, 15000); return () => clearInterval(t); }, [charger]);

  const deposer = async () => {
    if (!fichier) return;
    setDepot({ etat: "⏳ envoi de l'archive…" });
    const fd = new FormData(); fd.append("archive", fichier); fd.append("actor", username || "?");
    const r = await fetch(`${siAgentApiBase}/noeud-ia/kit`, { method: "POST", body: fd }).then(json).catch((e) => ({ erreur: e.message }));
    setDepot(r.erreur ? { erreur: r.erreur } : { etat: `✓ hermes-web ${r.version} déposé` });
    charger();
  };

  const choisirAgent = (id) => setF((x) => ({ ...x, agent: id, nom: x.nom || nomPropose(id) }));
  const deployer = async () => {
    const err = verifierFormulaire(f);
    if (err) { setEnvoi({ erreur: err }); return; }
    const ag = agents.find((a) => a.agent_id === f.agent);
    if (!agentAJour(ag?.agent_version)) { setEnvoi({ erreur: `agent ${f.agent} en ${ag?.agent_version || "version inconnue"} : ${VERSION_AGENT_MIN} au moins requise`, maj: true }); return; }
    setEnvoi({ etat: "⏳ commande envoyée à l'agent…" });
    const r = await fetch(`${siAgentApiBase}/agents/${encodeURIComponent(f.agent)}/noeud-ia`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "deployer", nom: f.nom, port: Number(f.port || 8092), actor: username }) }).then(json).catch((e) => ({ erreur: e.message }));
    if (r.erreur) { setEnvoi({ erreur: r.erreur, reglage: r.statut === 403 }); return; }
    setEnvoi({ etat: "⏳ l'agent installe ; déclaration du nœud dans la passerelle…" });
    const j = await fetch(`${servicesApiBase}/ia/declarer`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nom: f.nom, acces: f.acces, adresse: f.adresse, port: Number(f.port || 8092), shim: f.acces === "bastion" ? f.shim : undefined }) }).then(json).catch((e) => ({ erreur: e.message }));
    setEnvoi(j.erreur ? { erreur: `nœud lancé, mais passerelle non mise à jour : ${j.erreur}` } : { etat: "✓ déploiement lancé sur le nœud ; passerelle en cours de rechargement", job: j.job?.id });
    charger(); onDeclare?.();
  };
  const etat = async (aid, port) => {
    setEnEtat(aid);
    await fetch(`${siAgentApiBase}/agents/${encodeURIComponent(aid)}/noeud-ia`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "etat", port, actor: username }) });
    setTimeout(() => { charger(); setEnEtat(null); }, 4000);
  };

  if (!d) return <p className="muted">⏳ déploiements…</p>;
  if (d.erreur) return <p className="error">Déploiements indisponibles : {d.erreur} (si-agent-api)</p>;
  const noeuds = Object.entries(d.noeuds || {});
  return (
    <div className="hub-card" style={{ marginBottom: 12 }}>
      <h3 style={{ marginTop: 0 }}>🚀 Déployer sur un nœud IA</h3>
      <p style={{ margin: "4px 0" }}><strong>1. Archive de hermes-web</strong> : {d.kit ? <>version <strong>{d.kit.version}</strong> déposée le {new Date(d.kit.depose_le).toLocaleString("fr-FR")} par {d.kit.depose_par}</> : <span style={{ color: TON.warn }}>aucune</span>}</p>
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", fontSize: 12 }}>
        <span className="muted">💻 sur le Mac :</span><code style={{ fontSize: 11 }}>{CMD_ARCHIVE}</code><Copier texte={CMD_ARCHIVE} />
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 4 }}>
        <input type="file" accept=".gz,.tgz,application/gzip" onChange={(e) => setFichier(e.target.files?.[0] || null)} />
        <button type="button" disabled={!fichier || depot?.etat?.startsWith("⏳")} onClick={deposer}>{depot?.etat?.startsWith("⏳") ? depot.etat : "Déposer l'archive"}</button>
        {depot?.erreur && <span className="error">{depot.erreur}</span>}
        {depot?.etat && !depot.etat.startsWith("⏳") && <span style={{ color: TON.ok }}>{depot.etat}</span>}
      </div>
      {!d.secret && <p className="error">IA_NOEUDS_SECRET vide sur le serveur du hub. Pas de lien : opération manuelle — sur super, <code>python3 scripts/sync-env.py</code> puis reconstruire si-agent-api.</p>}

      <p style={{ margin: "10px 0 4px" }}><strong>2. Nœud</strong> (l'agent du nœud doit être en « intervention » dans ses Commandes à distance)</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <select value={f.agent} onChange={(e) => choisirAgent(e.target.value)} aria-label="agent du nœud">
          <option value="">agent du nœud…</option>
          {agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.label || a.agent_id} ({a.site} · {a.agent_version || "?"}{agentAJour(a.agent_version) ? "" : " ⚠ trop ancien"}{a.remote_shell === "intervention" ? "" : ` · ${a.remote_shell}`})</option>)}
        </select>
        <label>nom <input value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} style={{ width: 110 }} placeholder="prodia" /></label>
        <select value={f.acces} onChange={(e) => setF({ ...f, acces: e.target.value })} aria-label="accès depuis le hub">
          <option value="direct">joint directement (LAN du hub)</option>
          <option value="bastion">joint par le bastion (site distant)</option>
        </select>
        <label>adresse <input value={f.adresse} onChange={(e) => setF({ ...f, adresse: e.target.value })} style={{ width: 130 }} placeholder="IP du nœud" /></label>
        {f.acces === "bastion" && <label>shim <input value={f.shim} onChange={(e) => setF({ ...f, shim: e.target.value })} style={{ width: 80 }} /></label>}
        <label>port <input type="number" value={f.port} onChange={(e) => setF({ ...f, port: e.target.value })} style={{ width: 70 }} /></label>
        <button type="button" disabled={!d.kit || !d.secret || envoi?.etat?.startsWith("⏳")} onClick={deployer}>{envoi?.etat?.startsWith("⏳") ? envoi.etat : "Déployer / mettre à jour"}</button>
      </div>
      {envoi?.erreur && <p className="error">{envoi.erreur}{envoi.maj && <> — <a href={hubLink("si-agent", { tab: "updates" })}>Agents › Mises à jour</a> : activer la nouvelle version pour cet agent</>}{envoi.reglage && <> — <a href={hubLink("si-agent", { agent: f.agent, section: "distance" })}>Commandes à distance de {f.agent}</a> : choisir <strong>intervention</strong></>}</p>}
      {envoi?.etat && !envoi.etat.startsWith("⏳") && <p style={{ color: TON.ok }}>{envoi.etat}{envoi.job && <> — <a href={hubLink("services", { tab: "deliveries", job: envoi.job })}>job de la passerelle</a></>}</p>}

      {noeuds.length > 0 && (
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>Nœud</th><th>Agent</th><th>Version demandée</th><th>Demandé</th><th>État</th><th /></tr></thead>
          <tbody>
            {noeuds.map(([aid, n]) => {
              const e = etatNoeud(d.etats?.[aid]);
              return (
                <tr key={aid}>
                  <td><strong>{n.nom}</strong> :{n.port}</td>
                  <td><a href={hubLink("si-agent", { agent: aid })}>{aid}</a></td>
                  <td>{n.version}</td>
                  <td>{n.demande_le ? new Date(n.demande_le).toLocaleString("fr-FR") : ""} {n.demande_par}</td>
                  <td style={{ color: TON[e.ton] || "inherit" }}>{e.texte}</td>
                  <td><button type="button" className="secondary" disabled={enEtat === aid} onClick={() => etat(aid, n.port)}>{enEtat === aid ? "⏳ état…" : "↻ état"}</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
