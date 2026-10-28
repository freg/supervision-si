// #906 : tuile « Sockets » -- relevé netstat -laputen des hôtes agentés (sonde sockets, à la demande, horodaté).
// En écoute et établies, TCP et UDP, avec processus, PID et utilisateur. Base de la future vue inversée « Services du LAN ».
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchSockets } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import IpPing from "./IpPing.jsx";

const date = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");

export default function SocketsView({ onBack, siAgentApiBase }) {
  const [liste, setListe] = useState(null);
  const [agent, setAgent] = useState("");
  const [detail, setDetail] = useState(null);
  const [at, setAt] = useState("");
  const [q, setQ] = useState("");
  const [filtre, setFiltre] = useState("tous");   // tous | ecoute | etablies | exposes
  const [proto, setProto] = useState("tous");
  useEffect(() => { fetchSockets(siAgentApiBase).then((d) => { setListe(d.hotes || []); if ((d.hotes || []).length === 1) setAgent(d.hotes[0].agent); }); }, [siAgentApiBase]);
  const charger = useCallback(() => { if (agent) fetchSockets(siAgentApiBase, agent, at).then(setDetail); }, [siAgentApiBase, agent, at]);
  useEffect(() => { setDetail(null); charger(); }, [charger]);
  const lignes = useMemo(() => {
    const f = q.trim().toLowerCase();
    return (detail?.sockets || []).filter((s) => {
      if (proto !== "tous" && s.proto !== proto) return false;
      if (filtre === "ecoute" && !s.ecoute) return false;
      if (filtre === "etablies" && s.ecoute) return false;
      if (filtre === "exposes" && !s.expose) return false;
      if (f && ![s.process, s.user, s.local_ip, s.remote_ip, s.local_port, s.remote_port, s.pid].join(" ").toLowerCase().includes(f)) return false;
      return true;
    }).sort((a, b) => (b.ecoute - a.ecoute) || (a.local_port - b.local_port));
  }, [detail, q, filtre, proto]);
  return (
    <div className="infra-page">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
        <h2 style={{ margin: 0 }}>Sockets</h2>
        <span className="infra-muted">netstat -laputen des hôtes agentés (sonde sockets, à la demande) : écoute et établies, TCP/UDP, processus, PID, utilisateur</span>
      </div>
      {liste === null ? <p className="infra-muted">lecture…</p> : liste.length === 0 ? (
        <p className="infra-muted">Aucun relevé. Activer et exécuter la sonde <b>sockets</b> sur un agent : <a href={hubLink("si-agent")}>Agents</a> › fiche de l'agent › Commandes › « Activer une sonde », puis Sondes › sockets › Exécuter…</p>
      ) : (<>
        <table className="infra-table" style={{ margin: "10px 0" }}><thead><tr><th>Hôte</th><th>Relevé</th><th>Total</th><th>Écoute</th><th>Établies</th><th>Exposés</th></tr></thead>
          <tbody>{liste.map((h) => (
            <tr key={h.agent} onClick={() => { setAgent(h.agent); setAt(""); }} style={{ cursor: "pointer", fontWeight: h.agent === agent ? 600 : 400 }}>
              <td>{h.hote || h.agent} <span className="infra-muted">({h.agent})</span></td><td>{date(h.at)}</td>
              <td>{h.counts?.total ?? "—"}</td><td>{h.counts?.ecoute ?? "—"}</td><td>{h.counts?.etablies ?? "—"}</td>
              <td className={h.counts?.exposes ? "np-tone warn" : ""}>{h.counts?.exposes ?? "—"}</td>
            </tr>))}</tbody></table>
        {detail && (
          <section className="infra-card">
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <h3 style={{ margin: 0 }}>{agent}</h3>
              {(detail.historique || []).length > 1 && (
                <select value={at || (detail.historique || [])[0] || ""} onChange={(e) => setAt(e.target.value)} title="horodatage du relevé">
                  {(detail.historique || []).map((t) => <option key={t} value={t}>{date(t)}</option>)}
                </select>)}
              <select value={filtre} onChange={(e) => setFiltre(e.target.value)}>
                <option value="tous">toutes</option><option value="ecoute">en écoute</option><option value="etablies">établies</option><option value="exposes">exposées (0.0.0.0)</option>
              </select>
              <select value={proto} onChange={(e) => setProto(e.target.value)}><option value="tous">tcp+udp</option><option value="tcp">tcp</option><option value="udp">udp</option></select>
              <input placeholder="filtrer : processus, utilisateur, ip, port…" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 220 }} />
              <button className="secondary" onClick={charger}>⟳</button>
              <span className="infra-muted">{lignes.length} socket(s)</span>
            </div>
            <div style={{ maxHeight: 460, overflow: "auto", marginTop: 6 }}>
              <table className="infra-table"><thead><tr><th>Proto</th><th>État</th><th>Adresse locale</th><th>Adresse distante</th><th>Processus</th><th>PID</th><th>Utilisateur</th></tr></thead>
                <tbody>{lignes.map((s, k) => (
                  <tr key={k} className={s.expose ? "np-tone warn" : ""}>
                    <td>{s.proto}</td><td>{s.ecoute ? "écoute" : s.etat}</td>
                    <td style={{ fontFamily: "monospace" }}>{s.local_ip}:{s.local_port}</td>
                    <td style={{ fontFamily: "monospace" }}>{s.remote_ip ? <>{/^\d/.test(s.remote_ip) ? <IpPing ip={s.remote_ip} /> : s.remote_ip}:{s.remote_port}</> : "—"}</td>
                    <td>{s.process || "—"}</td><td>{s.pid ?? "—"}</td><td>{s.user || "—"}</td>
                  </tr>))}</tbody></table>
            </div>
          </section>)}
      </>)}
    </div>
  );
}
