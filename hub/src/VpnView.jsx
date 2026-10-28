// #884 : onglet « VPN » -- serveurs WireGuard relevés en lecture seule (sonde wireguard) : pairs et état courant,
// historique des connexions reconstitué par le hub (WireGuard ne journalise pas les connexions).
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchVpn } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import IpPing from "./IpPing.jsx";

const vol = (o) => (!o ? "0" : o >= 1e9 ? `${(o / 1e9).toFixed(1).replace(".", ",")} Go` : o >= 1e6 ? `${Math.round(o / 1e6)} Mo` : `${Math.round(o / 1e3)} Ko`);
const duree = (s) => (s == null ? "—" : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : `${Math.floor(s / 3600)} h ${String(Math.round((s % 3600) / 60)).padStart(2, "0")}`);
const age = (s) => (s == null ? "jamais" : s < 120 ? `${s} s` : s < 7200 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} j`);
const date = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const cle = (k) => (k ? `${k.slice(0, 8)}…` : "");
const hote = (ep) => (ep ? ep.replace(/:\d+$/, "").replace(/^\[|\]$/g, "") : "");

export default function VpnView({ onBack, siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [days, setDays] = useState(30);
  const [q, setQ] = useState("");
  const load = useCallback(() => fetchVpn(siAgentApiBase, days).then(setD), [siAgentApiBase, days]);
  useEffect(() => { load(); const t = setInterval(load, 120000); return () => clearInterval(t); }, [load]);
  const sessions = useMemo(() => {
    const f = q.trim().toLowerCase();
    return (d?.sessions || []).filter((s) => !f || [s.nom, s.public_key, s.origine, ...(s.adresses || [])].join(" ").toLowerCase().includes(f));
  }, [d, q]);
  return (
    <div className="infra-page">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
        <h2 style={{ margin: 0 }}>VPN</h2>
        <span className="infra-muted">WireGuard en lecture seule (sonde wireguard, toutes les 2 min) ; connexions reconstituées par le hub</span>
      </div>
      {d === null ? <p className="infra-muted">lecture…</p> : d.serveurs.length === 0 ? (
        <div className="infra-muted">
          <p>Aucun serveur VPN relevé. Activer la sonde <b>wireguard</b> (<a href={hubLink("si-agent", { tab: "catalogue" })}>Agents › Sondes</a>) :</p>
          <ul>
            <li><b>Agent installé sur le serveur VPN</b> (ex. r2d2) : aucun argument ; les noms des pairs viennent des commentaires de /etc/wireguard/*.conf.</li>
            <li><b>Serveur géré par un autre administrateur</b> : il installe la commande forcée <code>wg-etat.sh</code> (fournie avec la sonde : lecture seule, clés privées masquées) ;
              arguments <code>--ssh wgetat@&lt;serveur&gt; --ssh-key &lt;clé&gt; [--names noms.json]</code> (pas de lien : opération manuelle sur le serveur VPN).</li>
          </ul>
        </div>
      ) : <>
        {d.serveurs.map((sv) => (sv.interfaces || []).map((i) => {
          const peers = [...(i.peers || [])].sort((a, b) => (b.connected - a.connected) || String(a.name || "~").localeCompare(String(b.name || "~")));
          return (
            <section key={`${sv.relais}-${i.interface}`} className="infra-card" style={{ margin: "12px 0" }}>
              <h3 style={{ margin: "0 0 6px" }}>{i.interface} <span className="infra-muted" style={{ fontSize: 13 }}>
                · port {i.port ?? "?"} · {peers.filter((p) => p.connected).length} connecté(s) sur {peers.length} · relevé par {sv.relais}{sv.source && sv.source !== "local" ? ` via ${sv.source}` : ""} · {date(sv.at)}</span></h3>
              {(sv.alertes || []).map((a, k) => <div key={k} className="np-tone warn">• {a.message}</div>)}
              <table className="infra-table"><thead><tr><th>Pair</th><th>État</th><th>Origine</th><th>Adresses VPN</th><th>Dernière poignée de main</th><th>Reçu / émis</th></tr></thead>
                <tbody>{peers.map((p) => (
                  <tr key={p.public_key}>
                    <td>{p.name || <span className="infra-muted">sans nom</span>} <span className="infra-muted" title={p.public_key}>{cle(p.public_key)}</span></td>
                    <td className={`np-tone ${p.connected ? "good" : "neutral"}`}>{p.connected ? "connecté" : "déconnecté"}</td>
                    <td>{p.endpoint ? hote(p.endpoint) : "—"}</td>
                    <td>{(p.allowed_ips || []).map((a) => <span key={a} style={{ marginRight: 6 }}>{a.endsWith("/32") ? <IpPing ip={a.replace("/32", "")} /> : a}</span>)}</td>
                    <td>{p.handshake_at ? `il y a ${age(p.handshake_age_s)}` : "jamais"}</td>
                    <td>{vol(p.rx)} / {vol(p.tx)}</td>
                  </tr>))}</tbody></table>
            </section>);
        }))}
        <section className="infra-card" style={{ margin: "12px 0" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <h3 style={{ margin: 0 }}>Historique des connexions</h3>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {[1, 7, 30, 90].map((n) => <option key={n} value={n}>{n === 1 ? "24 h" : `${n} jours`}</option>)}
            </select>
            <input placeholder="filtrer : nom, adresse, clé…" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 220 }} />
            <span className="infra-muted">{sessions.length} session(s) · reconstituées à partir des relevés (précision 2 min)</span>
          </div>
          <div style={{ maxHeight: 420, overflow: "auto", marginTop: 6 }}>
            <table className="infra-table"><thead><tr><th>Pair</th><th>Début</th><th>Fin</th><th>Durée</th><th>Origine</th><th>Reçu / émis</th><th>Serveur</th></tr></thead>
              <tbody>{sessions.map((s, k) => (
                <tr key={k}>
                  <td>{s.nom || <span className="infra-muted">{cle(s.public_key)}</span>}</td><td>{date(s.debut)}</td>
                  <td>{s.en_cours ? <span className="np-tone good">en cours</span> : date(s.fin)}</td><td>{duree(s.duree_s)}</td>
                  <td>{hote(s.origine) || "—"}</td><td>{vol(s.rx)} / {vol(s.tx)}</td><td>{s.relais} · {s.interface}</td>
                </tr>))}</tbody></table>
          </div>
        </section>
      </>}
    </div>
  );
}
