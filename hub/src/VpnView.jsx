// #884 : onglet « VPN » -- serveurs WireGuard relevés en lecture seule (sonde wireguard) : pairs et état courant,
// historique des connexions reconstitué par le hub (WireGuard ne journalise pas les connexions).
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchVpn, fetchSyslog } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import IpPing from "./IpPing.jsx";
import { operateur, stabilite } from "./vpnLib.js";

const opLib = (s) => { const o = operateur(s.nom_origine, s.origine); return o.operateur ? `${o.operateur}${o.acces ? ` · ${o.acces}` : ""}` : ""; };

const vol = (o) => (!o ? "0" : o >= 1e9 ? `${(o / 1e9).toFixed(1).replace(".", ",")} Go` : o >= 1e6 ? `${Math.round(o / 1e6)} Mo` : `${Math.round(o / 1e3)} Ko`);
const duree = (s) => (s == null ? "—" : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : `${Math.floor(s / 3600)} h ${String(Math.round((s % 3600) / 60)).padStart(2, "0")}`);
const age = (s) => (s == null ? "jamais" : s < 120 ? `${s} s` : s < 7200 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} j`);
const date = (iso) => (iso ? new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const cle = (k) => (k ? `${k.slice(0, 8)}…` : "");
const hote = (ep) => (ep ? ep.replace(/:\d+$/, "").replace(/^\[|\]$/g, "") : "");

// #894 : lignes WireGuard reçues en syslog (routeur MikroTik : sujet « wireguard »), en attendant l'analyse en sessions
function SyslogWireguard({ days }) {
  const [s, setS] = useState(null);
  useEffect(() => {
    let vivant = true;
    const go = () => fetchSyslog({ q: "wireguard", heures: Math.min(days, 30) * 24, limite: 300 }).then((r) => { if (vivant) setS(r); });
    go(); const t = setInterval(go, 60000); return () => { vivant = false; clearInterval(t); };
  }, [days]);
  if (!s) return null;
  const info = s.info || {};
  return (
    <section className="infra-card" style={{ margin: "12px 0" }}>
      <h3 style={{ margin: "0 0 4px" }}>Journal WireGuard reçu en syslog</h3>
      <div className="infra-muted" style={{ fontSize: 12, marginBottom: 6 }}>
        écoute UDP {info.port_udp || 5514} sur le hub · émetteurs autorisés : {(info.autorises || []).join(", ") || "tous (RSYSLOG_ALLOWED vide)"}
        {" · "}reçus de : {(info.emetteurs || []).map((e) => `${e.hote || e.ip} (${e.ip})`).join(", ") || "personne pour l'instant"}
        {(info.refuses || []).length > 0 && <span className="np-tone warn"> · refusés : {info.refuses.map((r) => `${r.ip} (${r.paquets})`).join(", ")}</span>}
        {info.conservation === false && <span className="np-tone bad"> · conservation désactivée</span>}
      </div>
      {s.error ? <div className="np-tone bad">{s.error}</div> : s.messages.length === 0 ? <div className="infra-muted">aucune ligne « wireguard » sur la période (côté routeur : /system logging, sujet wireguard vers l'action distante).</div> : (
        <div style={{ maxHeight: 320, overflow: "auto" }}><table className="infra-table"><thead><tr><th>Date</th><th>Émetteur</th><th>Niveau</th><th>Sujet</th><th>Message</th></tr></thead>
          <tbody>{s.messages.map((m, k) => (
            <tr key={k} className={m.sev <= 3 ? "np-tone bad" : m.sev === 4 ? "np-tone warn" : ""}>
              <td style={{ whiteSpace: "nowrap" }}>{new Date(m.t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td>
              <td>{m.hote || m.ip}</td><td>{m.niveau}</td><td>{m.app}</td><td style={{ fontFamily: "monospace", fontSize: 12 }}>{m.msg}</td>
            </tr>))}</tbody></table></div>)}
    </section>
  );
}

export default function VpnView({ onBack, siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [days, setDays] = useState(30);
  const [q, setQ] = useState("");
  const load = useCallback(() => fetchVpn(siAgentApiBase, days).then(setD), [siAgentApiBase, days]);
  useEffect(() => { load(); const t = setInterval(load, 120000); return () => clearInterval(t); }, [load]);
  const sessions = useMemo(() => {
    const f = q.trim().toLowerCase();
    return (d?.sessions || []).filter((s) => !f || [s.nom, s.public_key, s.origine, s.nom_origine, s.poste, s.protocole, s.interface, ...(s.adresses || [])].join(" ").toLowerCase().includes(f));
  }, [d, q]);
  const stab = useMemo(() => stabilite(sessions), [sessions]);
  return (
    <div className="infra-page">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
        <h2 style={{ margin: 0 }}>VPN</h2>
        <span className="infra-muted">en lecture seule : WireGuard (sonde wireguard, connexions reconstituées) et SoftEther (sonde softether, journaux du serveur)</span>
      </div>
      <SyslogWireguard days={days} />
      {d === null ? <p className="infra-muted">lecture…</p> : d.serveurs.length === 0 ? (
        <div className="infra-muted">
          <p>Aucun serveur VPN relevé. Activer la sonde <b>wireguard</b> (<a href={hubLink("si-agent", { tab: "catalogue" })}>Agents › Sondes</a>) :</p>
          <ul>
            <li><b>SoftEther</b> (ex. r2d2) : sonde <b>softether</b> sur l'agent du serveur, sans argument ni mot de passe (lecture des journaux de sécurité).</li>
            <li><b>WireGuard sur routeur MikroTik</b> : sonde wireguard sur un agent autorisé par le routeur, fichier <code>/etc/si-agent/mikrotik-wg.json</code> pris d'office
              (compte RouterOS du groupe « read », API 8728 / 8729 ; pas de lien : fichier à créer sur l'hôte de l'agent, root seulement).</li>
            <li><b>WireGuard, agent installé sur le serveur VPN</b> : sonde wireguard, aucun argument ; les noms des pairs viennent des commentaires de /etc/wireguard/*.conf.</li>
            <li><b>Serveur géré par un autre administrateur</b> : il installe la commande forcée <code>wg-etat.sh</code> (fournie avec la sonde : lecture seule, clés privées masquées) ;
              arguments <code>--ssh wgetat@&lt;serveur&gt; --ssh-key &lt;clé&gt; [--names noms.json]</code> (pas de lien : opération manuelle sur le serveur VPN).</li>
          </ul>
        </div>
      ) : <>
        {d.serveurs.filter((sv) => sv.type === "softether").map((sv) => (
          <section key={`se-${sv.relais}`} className="infra-card" style={{ margin: "12px 0" }}>
            <h3 style={{ margin: "0 0 6px" }}>SoftEther · {sv.hote || sv.relais} <span className="infra-muted" style={{ fontSize: 13 }}>
              · hubs : {(sv.hubs || []).join(", ") || "—"} · {(sv.en_cours || []).length} session(s) en cours · {date(sv.at)}</span></h3>
            {(sv.alertes || []).map((a, k) => <div key={k} className="np-tone warn">• {a.message}</div>)}
            {(sv.en_cours || []).length > 0 && <table className="infra-table"><thead><tr><th>Utilisateur</th><th>Hub</th><th>Protocole</th><th>Poste</th><th>Origine</th><th>Adresse VPN</th><th>Depuis</th></tr></thead>
              <tbody>{sv.en_cours.map((s) => <tr key={s.sid}><td>{s.utilisateur}</td><td>{s.hub}</td><td>{s.protocole}</td><td>{s.poste || "—"}</td>
                <td title={s.nom_origine}>{s.origine}</td><td>{s.adresse_vpn ? <IpPing ip={s.adresse_vpn} /> : "—"}</td><td>{date(s.debut)} ({duree(s.duree_s)})</td></tr>)}</tbody></table>}
            {(sv.echecs || []).length > 0 && <details style={{ marginTop: 6 }}><summary>{sv.echecs.length} échec(s) d'authentification récents</summary>
              <table className="infra-table"><thead><tr><th>Date</th><th>Hub</th><th>Utilisateur</th><th>Origine</th></tr></thead>
                <tbody>{[...sv.echecs].reverse().slice(0, 100).map((e, k) => <tr key={k}><td>{date(e.at)}</td><td>{e.hub}</td><td>{e.utilisateur || "—"}</td><td>{e.ip || "—"}</td></tr>)}</tbody></table></details>}
          </section>))}
        {d.serveurs.filter((sv) => sv.type !== "softether" && !(sv.interfaces || []).length).map((sv) => (
          <section key={`wg-vide-${sv.relais}`} className="infra-card" style={{ margin: "12px 0" }}>
            <h3 style={{ margin: "0 0 6px" }}>WireGuard · {sv.source && sv.source !== "local" ? sv.source : sv.hote || sv.relais} <span className="infra-muted" style={{ fontSize: 13 }}>
              · relevé par {sv.relais} · {date(sv.at)}</span></h3>
            {(sv.alertes || []).length ? sv.alertes.map((a, k) => <div key={k} className={`np-tone ${a.severity === "info" ? "neutral" : "bad"}`}>• {a.message}</div>)
              : <div className="infra-muted">aucune interface WireGuard lue</div>}
          </section>))}
        {d.serveurs.filter((sv) => sv.type !== "softether").map((sv) => (sv.interfaces || []).map((i) => {
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
        {stab.length > 0 && (
          <section className="infra-card" style={{ margin: "12px 0" }}>
            <h3 style={{ margin: "0 0 4px" }}>Stabilité par utilisateur</h3>
            <div className="infra-muted" style={{ fontSize: 12, marginBottom: 6 }}>sur la période et le filtre choisis ci-dessous · courte : terminée en moins de 5 min · reconnexion : nouvelle session moins de 5 min après la fin de la précédente ; à rapprocher de l'opérateur (satellite, 4G…)</div>
            <div style={{ maxHeight: 260, overflow: "auto" }}><table className="infra-table"><thead><tr><th>Utilisateur / pair</th><th>Opérateur(s)</th><th>Sessions</th><th>Courtes</th><th>Reconnexions</th><th>Durée médiane</th><th>Temps total</th><th>Dernière</th></tr></thead>
              <tbody>{stab.map((u) => (
                <tr key={u.nom} style={{ cursor: "pointer" }} onClick={() => setQ(u.nom)} title="filtrer l'historique sur cet utilisateur">
                  <td>{u.nom}</td><td>{u.operateurs.join(", ") || "—"}</td><td>{u.sessions}</td>
                  <td className={u.courtes ? "np-tone warn" : ""}>{u.courtes}</td><td className={u.reconnexions ? "np-tone warn" : ""}>{u.reconnexions}</td>
                  <td>{duree(u.mediane_s)}</td><td>{duree(u.total_s)}</td><td>{date(u.dernier)}</td>
                </tr>))}</tbody></table></div>
          </section>
        )}
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
            <table className="infra-table"><thead><tr><th>Pair / utilisateur</th><th>Début</th><th>Fin</th><th>Durée</th><th>Origine</th><th>Opérateur</th><th>Protocole · poste</th><th>Reçu / émis</th><th>Serveur</th></tr></thead>
              <tbody>{sessions.map((s, k) => (
                <tr key={k}>
                  <td>{s.nom || <span className="infra-muted">{cle(s.public_key)}</span>}</td><td>{date(s.debut)}</td>
                  <td>{s.en_cours ? <span className="np-tone good">en cours</span> : date(s.fin)}</td><td>{duree(s.duree_s)}</td>
                  <td title={s.nom_origine || ""}>{hote(s.origine) || "—"}</td><td title={s.nom_origine || ""}>{opLib({ ...s, origine: hote(s.origine) }) || "—"}</td><td>{s.type === "softether" ? `${(s.protocole || "").replace("Legacy VPN - ", "")}${s.poste ? ` · ${s.poste}` : ""}` : "WireGuard"}</td>
                  <td>{vol(s.rx)} / {vol(s.tx)}</td><td>{s.relais} · {s.interface}</td>
                </tr>))}</tbody></table>
          </div>
        </section>
      </>}
    </div>
  );
}
