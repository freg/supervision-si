// Console « Bastion » (livraison #455) -- demandé : « une passe sur
// l'ensemble des outils et des tuiles pour mettre dans bastion tout ce qui
// concerne les entrées sorties autorisations partages ». Cinq onglets :
//   - Bastion si-proxy (#454, inchangé, embarqué) ;
//   - Entrées  : exposition du SI (passerelle, ports publiés directement,
//                réseau hôte -- d'après EXPOSURE.json), agents et sondes
//                entrants (si-agent : coupe-circuit de la flotte ; netprobe) ;
//   - Sorties  : tunnels SSH (arrêt/démarrage), montages SSHFS, connecteurs
//                vers des services externes (Nebula, GLPI, IMAP, sauvegardes,
//                ownCloud, GeoIP, notifications) ;
//   - Autorisations : permissions rights-api par type de ressource
//                (révocation), liens externes et leurs rôles, mes groupes ;
//   - Partages : sources du gestionnaire de fichiers (espace protégé, GED,
//                montages), montages SSHFS (démontage).
// Rien n'est dupliqué : on agrège ce que les tuiles exposent déjà et on
// renvoie vers la tuile d'origine pour le détail (onNavigate).
import { useCallback, useEffect, useMemo, useState } from "react";
import SiProxyView from "./SiProxyView.jsx";
import { BASTION_TABS, OUTBOUND_CONNECTORS, summarizeExposure, summarizeInbound, summarizeOutbound, connectorState, summarizeAuthorizations, summarizeShares, attentionCounts } from "./bastionInventory.js";
import { probeHealth, probeBackup, probeImap, fetchExposure } from "./bastionClient.js";
import { fetchSiAgentStatus, fetchFleet, blockFleet, unblockFleet } from "./siAgentClient.js";
import { fetchAgents as fetchProbeAgents } from "./netprobeClient.js";
import { fetchTunnels, fetchConnections, fetchMounts, startTunnel, stopTunnel, unmountAction } from "./sshTunnelsClient.js";
import { fetchPermissions, fetchResourceTypes, revokePermission } from "./rightsClient.js";
import { fetchExternalLinks } from "./settingsClient.js";
import { fetchSources } from "./fileManagerClient.js";
import { fetchDocuments } from "./gedClient.js";

const REFRESH_MS = 30000;

function Tone({ tone, children, title }) {
  return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>;
}
const TONE = { ok: "good", warning: "warn", critical: "bad", info: "neutral", unknown: "neutral" };

export default function BastionView({ onBack, onNavigate, siProxyApiBase, accessToken, username, groups = [], apiBases = {} }) {
  const [tab, setTab] = useState("proxy");
  const [data, setData] = useState(null);
  const [errors, setErrors] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    const errs = [];
    const safe = async (label, fn, fallback) => {
      try { const r = await fn(); if (r && r.error) { errs.push(`${label} : ${r.error}`); return fallback; } return r; } catch (e) { errs.push(`${label} : ${e.message}`); return fallback; }
    };
    const b = apiBases;
    const [exposure, siAgentStatus, siAgentFleet, netprobeAgents, tunnels, connections, mounts, permissions, resourceTypes, externalLinks, fileSources, gedDocs,
      pNebula, pGlpi, pImap, pBackup, pOwncloud] = await Promise.all([
      siProxyApiBase && accessToken ? safe("Exposition", () => fetchExposure(siProxyApiBase, accessToken), null) : null,
      b.siAgent ? safe("Agents hôtes", () => fetchSiAgentStatus(b.siAgent), { error: "injoignable" }) : null,
      b.siAgent ? safe("Agents hôtes (flotte)", () => fetchFleet(b.siAgent), []) : [],
      b.netprobe ? safe("Sondes", () => fetchProbeAgents(b.netprobe), []) : [],
      b.sshTunnels ? safe("Tunnels SSH", () => fetchTunnels(b.sshTunnels), []) : [],
      b.sshTunnels ? safe("Connexions SSH", () => fetchConnections(b.sshTunnels), []) : [],
      b.sshTunnels ? safe("Montages SSHFS", () => fetchMounts(b.sshTunnels), []) : [],
      b.rights ? safe("Droits", () => fetchPermissions(b.rights), []) : [],
      b.rights ? safe("Droits (types)", () => fetchResourceTypes(b.rights), []) : [],
      b.prefs ? safe("Liens externes", () => fetchExternalLinks(b.prefs), []) : [],
      b.fileManager ? safe("Gestionnaire de fichiers", async () => { const r = await fetchSources(b.fileManager, groups); const d = r?.data ?? r; return Array.isArray(d) ? d : Array.isArray(d?.sources) ? d.sources : []; }, []) : [],
      b.ged ? safe("GED", () => fetchDocuments(b.ged), null) : null,
      b.nebula ? probeHealth(b.nebula) : null,
      b.glpi ? probeHealth(b.glpi) : null,
      b.imap ? probeImap(b.imap) : null,
      b.backupRestore ? probeBackup(b.backupRestore) : null,
      b.owncloud ? probeHealth(b.owncloud) : null,
    ]);
    const probes = { nebula: pNebula, glpi: pGlpi, imap: pImap, backup: pBackup, owncloud: pOwncloud,
      geoip: b.pixelGrid ? { text: "via pixel-grid-api (IP publiques seulement)" } : null,
      notify: siAgentStatus?.notifications ? { configured: !!siAgentStatus.notifications.any, text: siAgentStatus.notifications.any ? Object.entries(siAgentStatus.notifications.channels || {}).filter(([, v]) => v).map(([k]) => k).join(", ") : "aucun canal configuré" } : null };
    const connectors = OUTBOUND_CONNECTORS.map((c) => ({ ...c, ...connectorState(c.id, probes[c.id]) }));
    setData({
      exposure: summarizeExposure(exposure),
      inbound: summarizeInbound({ siAgentStatus, siAgentFleet, netprobeAgents }),
      outbound: summarizeOutbound({ tunnels, connections, mounts, connectors }),
      auth: summarizeAuthorizations({ permissions, resourceTypes, externalLinks, groups }),
      shares: summarizeShares({ fileSources, mounts, gedCount: Array.isArray(gedDocs) ? gedDocs.length : null }),
      siAgentFleet, siAgentStatus,
    });
    setErrors(errs);
  }, [siProxyApiBase, accessToken, apiBases, groups]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  const act = async (label, fn) => {
    setBusy(true);
    const r = await fn();
    setBusy(false);
    setNotice(r?.error ? `${label} : ${r.error}` : `${label} : fait`);
    load();
  };

  const attention = useMemo(() => (data ? attentionCounts(data) : {}), [data]);
  const b = apiBases;

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🛡 Bastion</h1>
        <span className="muted">entrées, sorties, autorisations, partages — réservé, connecté en tant que {username || "?"}</span>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "0 0 10px" }}>
        {BASTION_TABS.map((t) => (
          <button key={t.id} type="button" className={`secondary na-section-toggle${tab === t.id ? " active" : ""}`} onClick={() => setTab(t.id)}>
            {t.icon} {t.label}{attention[t.id] ? <> <Tone tone="warn">{attention[t.id]}</Tone></> : null}
          </button>
        ))}
        <button type="button" className="secondary" disabled={busy} onClick={load}>↻</button>
      </div>
      {errors.length > 0 && tab !== "proxy" && <p className="muted" style={{ margin: "0 0 8px" }}>⚠ {errors.length} source(s) injoignable(s) : {errors.join(" · ")}</p>}
      {notice && <p className="muted ups-notice">{notice} <button className="secondary" onClick={() => setNotice(null)}>✕</button></p>}

      {tab === "proxy" && <SiProxyView embedded onBack={onBack} siProxyApiBase={siProxyApiBase} accessToken={accessToken} username={username} />}

      {tab === "entries" && data && (
        <>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Exposition du SI</h2>
            {data.exposure.error && <p className="hub-error">{data.exposure.error}</p>}
            <p className="muted" style={{ margin: "0 0 6px" }}>
              Un seul point d'entrée prévu : la passerelle TLS (port {data.exposure.gatewayPort}, Keycloak devant les portails) — {data.exposure.counts.gateway} route(s) <code>/api/…</code> et portails.
              Ce qui suit <strong>contourne</strong> la passerelle : {data.exposure.counts.critical} critique(s), {data.exposure.counts.warning} avertissement(s), {data.exposure.counts.info} sur la boucle locale.
              Source : <code>docker-compose.yml</code> et <code>tls-proxy</code>, régénéré par <code>run.sh</code> (<code>shared/EXPOSURE.json</code>).
            </p>
            {data.exposure.direct.length > 0 && (
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>Sévérité</th><th>Service</th><th>Port hôte</th><th>Bind</th><th>Pourquoi</th></tr></thead>
                  <tbody>{data.exposure.direct.map((p, i) => (
                    <tr key={i}><td><Tone tone={TONE[p.severity]}>{p.severity}</Tone></td><td>{p.service}</td><td>{p.host_port}/{p.proto} → {p.container_port}</td><td className="muted">{p.bind}</td><td className="muted">{p.why}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}
            {data.exposure.hostNetwork.length > 0 && <p className="muted" style={{ margin: "6px 0 0" }}>Pile réseau de l'hôte (<code>network_mode: host</code>) : {data.exposure.hostNetwork.map((h) => h.service).join(", ")} — accès LAN complet, aucune isolation Docker.</p>}
            <details style={{ marginTop: 6 }}><summary className="muted">Routes de la passerelle ({data.exposure.gateway.length})</summary>
              <div className="hub-table-scroll"><table><thead><tr><th>Chemin</th><th>Service</th><th>Type</th></tr></thead>
                <tbody>{data.exposure.gateway.map((g) => <tr key={g.path}><td><code>{g.path}</code></td><td>{g.service}:{g.container_port}</td><td className="muted">{g.kind}</td></tr>)}</tbody></table></div>
            </details>
          </div>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Agents et sondes qui se connectent au hub</h2>
            {data.inbound.siAgent ? (
              <p style={{ margin: 0 }}>
                <strong>Agents hôtes</strong> (si-agent, HMAC) : {data.inbound.siAgent.total} enrôlé(s), {data.inbound.siAgent.online} en ligne, {data.inbound.siAgent.blocked} bloqué(s)
                {data.inbound.siAgent.insecure.length > 0 && <> · <Tone tone="warn">TLS non vérifié : {data.inbound.siAgent.insecure.join(", ")}</Tone></>}
                {" · "}central : <code>{data.inbound.siAgent.publicUrl || "?"}</code>
                {" · "}{data.inbound.siAgent.fleetBlocked
                  ? <><Tone tone="bad">flotte BLOQUÉE{data.inbound.siAgent.fleetBlockReason ? ` (${data.inbound.siAgent.fleetBlockReason})` : ""}</Tone> <button className="secondary" disabled={busy} onClick={() => act("Déblocage de la flotte", () => unblockFleet(b.siAgent))}>débloquer</button></>
                  : <><Tone tone="good">sondes autorisées</Tone> <input className="ss-search" style={{ width: 180 }} placeholder="motif du blocage" value={reason} onChange={(e) => setReason(e.target.value)} /> <button className="secondary" disabled={busy} onClick={() => act("Blocage de la flotte", () => blockFleet(b.siAgent, reason || "coupe-circuit Bastion"))}>⛔ bloquer toutes les sondes</button></>}
                {" "}<button className="secondary ss-origin" onClick={() => onNavigate?.("si-agent")}>ouvrir la tuile</button>
              </p>
            ) : <p className="muted" style={{ margin: 0 }}>Agents hôtes : {b.siAgent ? "central injoignable" : "non configuré"}.</p>}
            <p style={{ margin: "6px 0 0" }}>
              <strong>Sondes réseau / WiFi</strong> (netprobe, HMAC) : {data.inbound.netprobe.total} agent(s), {data.inbound.netprobe.online} vu(s) récemment
              {Object.keys(data.inbound.netprobe.roles).length > 0 && <> ({Object.entries(data.inbound.netprobe.roles).map(([k, v]) => `${v} ${k}`).join(", ")})</>}
              {" "}<button className="secondary ss-origin" onClick={() => onNavigate?.("netprobe")}>ouvrir la tuile</button>
            </p>
            <p className="muted" style={{ margin: "6px 0 0" }}>Autres entrées : syslog UDP (rsyslog-listener, tuile Logs), relais rétro-ingénierie du poste (jeton dans le relais), Keycloak/LDAP (portails).</p>
          </div>
        </>
      )}

      {tab === "exits" && data && (
        <>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Tunnels SSH sortants ({data.outbound.counts.tunnelsRunning} actif(s) / {data.outbound.counts.tunnels}, {data.outbound.counts.hosts} hôte(s) SSH)</h2>
            {data.outbound.tunnels.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucun tunnel déclaré{b.sshTunnels ? "" : " (ssh-tunnels-api non configuré)"}.</p> : (
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>État</th><th>Tunnel</th><th>Via</th><th>Vers</th><th>Port local</th><th></th></tr></thead>
                  <tbody>{data.outbound.tunnels.map((t) => (
                    <tr key={t.id}>
                      <td><Tone tone={t.running ? "good" : t.lastError ? "bad" : "neutral"} title={t.lastError || ""}>{t.status}</Tone></td>
                      <td>{t.label}</td><td className="muted">{t.via}</td><td>{t.to}</td><td>{t.localPort}</td>
                      <td>{t.running
                        ? <button className="secondary" disabled={busy} onClick={() => act(`Tunnel ${t.label} arrêté`, () => stopTunnel(b.sshTunnels, t.id))}>■ arrêter</button>
                        : <button className="secondary" disabled={busy} onClick={() => act(`Tunnel ${t.label} démarré`, () => startTunnel(b.sshTunnels, t.id))}>▶ démarrer</button>}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
            <p className="muted" style={{ margin: "6px 0 0" }}>Clés, connexions et création : <button className="secondary ss-origin" onClick={() => onNavigate?.("ssh-tunnels")}>tuile Tunnels SSH</button></p>
          </div>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Connecteurs vers des services externes</h2>
            <div className="hub-table-scroll">
              <table>
                <thead><tr><th>État</th><th>Connecteur</th><th>Ce qui sort</th><th>Détail</th><th></th></tr></thead>
                <tbody>{data.outbound.connectors.map((c) => (
                  <tr key={c.id}>
                    <td><Tone tone={TONE[c.state]}>{c.state === "ok" ? "ok" : c.state === "critical" ? "erreur" : c.state === "warning" ? "non configuré" : "absent"}</Tone></td>
                    <td>{c.label}</td><td className="muted">{c.what}</td><td className="muted">{c.text}</td>
                    <td>{c.tile && <button className="secondary ss-origin" onClick={() => onNavigate?.(c.tile)}>ouvrir</button>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === "auth" && data && (
        <>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Permissions par groupe (rights-api) — {data.auth.totalPermissions}</h2>
            <p className="muted" style={{ margin: "0 0 6px" }}>Vos groupes : {data.auth.myGroups.join(", ") || "—"}. Les types de ressource sans permission déclarée restent ouverts (contrôle opt-in par service) : {data.auth.openTypes.length ? data.auth.openTypes.map((t) => (typeof t === "string" ? t : t.id || t.name)).join(", ") : "aucun"}.</p>
            {data.auth.permissions.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucune permission déclarée{b.rights ? "" : " (rights-api non configuré)"}.</p> : data.auth.permissions.map((t) => (
              <details key={t.resourceType} style={{ marginBottom: 4 }}>
                <summary><strong>{t.resourceType}</strong> — {t.count} permission(s), groupes : {t.groups.join(", ")}, actions : {t.actions.join(", ")}</summary>
                <div className="hub-table-scroll"><table><thead><tr><th>Groupe</th><th>Ressource</th><th>Action</th><th></th></tr></thead>
                  <tbody>{t.items.map((p) => <tr key={p.id}><td>{p.group_name}</td><td className="muted">{p.resource_id || "(tous)"}</td><td>{p.action}</td>
                    <td>{groups.includes("admin_hub") && <button className="secondary" disabled={busy} onClick={() => act(`Permission ${p.id} révoquée`, () => revokePermission(b.rights, groups, p.id))}>révoquer</button>}</td></tr>)}</tbody></table></div>
              </details>
            ))}
            <p className="muted" style={{ margin: "6px 0 0" }}>Octroi et inventaire des fichiers : <button className="secondary ss-origin" onClick={() => onNavigate?.("rights")}>tuile Droits</button> (admin_hub).</p>
          </div>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Liens externes du hub ({data.auth.links.length}) — {data.auth.linksForEveryone} visible(s) de tous</h2>
            {data.auth.links.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucun lien externe.</p> : (
              <div className="hub-table-scroll"><table><thead><tr><th>Lien</th><th>URL</th><th>Rôles autorisés</th><th>Keycloak</th></tr></thead>
                <tbody>{data.auth.links.map((l) => <tr key={l.id}><td>{l.name}</td><td className="muted">{l.url}</td><td>{l.everyone ? <Tone tone="warn">tout le monde</Tone> : l.roles.join(", ")}</td><td className="muted">{l.keycloak ? "client OIDC provisionné" : "—"}</td></tr>)}</tbody></table></div>
            )}
            <p className="muted" style={{ margin: "6px 0 0" }}>Édition : <button className="secondary ss-origin" onClick={() => onNavigate?.("external-links")}>liens externes</button>. Coffre-fort (ACL par collection), annuaire (mots de passe) et console Keycloak : portails dédiés, hors de cette console.</p>
          </div>
        </>
      )}

      {tab === "shares" && data && (
        <>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Sources partagées du gestionnaire de fichiers ({data.shares.counts.sources})</h2>
            {data.shares.sources.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucune source{b.fileManager ? "" : " (file-manager-api non configuré)"}.</p> : (
              <ul className="sa-risks">{data.shares.sources.map((s) => (
                <li key={s.id}>{s.protectedSpace ? <Tone tone="warn">🔒 {s.label}</Tone> : <strong>{s.label}</strong>} <span className="muted">— {s.description}{s.protectedSpace ? " · accès gardé par rights-api (file-manager-protected)" : ""}</span></li>
              ))}</ul>
            )}
            {data.shares.gedCount != null && <p className="muted" style={{ margin: "6px 0 0" }}>GED interne : {data.shares.gedCount} document(s) (liaisons entre objets = partage par lien). <button className="secondary ss-origin" onClick={() => onNavigate?.("ged")}>ouvrir</button></p>}
            <p className="muted" style={{ margin: "6px 0 0" }}><button className="secondary ss-origin" onClick={() => onNavigate?.("file-manager")}>tuile Gestionnaire de fichiers</button></p>
          </div>
          <div className="hub-card hub-settings-section">
            <h2 style={{ margin: "0 0 6px" }}>Montages SSHFS ({data.shares.counts.mounted} monté(s) / {data.shares.counts.mounts})</h2>
            {data.shares.mounts.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucun montage déclaré.</p> : (
              <div className="hub-table-scroll"><table><thead><tr><th>État</th><th>Montage</th><th>Distant</th><th>Local</th><th></th></tr></thead>
                <tbody>{data.shares.mounts.map((m) => <tr key={m.id}><td><Tone tone={m.mounted ? "good" : "neutral"}>{m.mounted ? "monté" : "démonté"}</Tone></td><td>{m.label}</td><td className="muted">{m.remotePath}</td><td className="muted">{m.localPath}</td>
                  <td>{m.mounted && <button className="secondary" disabled={busy} onClick={() => act(`Montage ${m.label} démonté`, () => unmountAction(b.sshTunnels, m.id))}>⏏ démonter</button>}</td></tr>)}</tbody></table></div>
            )}
            <p className="muted" style={{ margin: "6px 0 0" }}>Partages ownCloud (table oc_share) : non exploités par le hub à ce jour — noté au backlog.</p>
          </div>
        </>
      )}
      {tab !== "proxy" && !data && <p className="muted">Chargement…</p>}
    </div>
  );
}
