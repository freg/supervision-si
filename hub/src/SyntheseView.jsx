// Infos synthèse SI (livraison #523) -- la synthèse « DNS ↔ IP OVH ↔ IPAM ↔
// services » générée par synthese/generate.py (données réelles hors dépôt,
// JSON servi par prefs-api /synthese), rendue INTERACTIVE : recherche
// transversale (une IP, un nom, un service), recoupement par adresse (« à
// quoi sert cette IP ? »), liens vers IPAM, la gestion des IP et des zones
// OVH, la console Online, et vers les outils du hub (équipements réseau,
// exploration). Logique pure : syntheseLib.js.
import { useEffect, useMemo, useState } from "react";
import { fetchSynthese } from "./settingsClient.js";
import { filterDoc, fillLink, ipLinks, zoneLink, daysUntil, describeIp } from "./syntheseLib.js";

function Ext({ href, children, title }) {
  if (!href) return null;
  return <a href={href} target="_blank" rel="noopener noreferrer" title={title || href} className="sy-link">{children} ↗</a>;
}

export default function SyntheseView({ onBack, prefsApiBase, onNavigate }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState({ ips: true, zones: true, ipam: true, devices: true, services: true, sources: false });
  useEffect(() => {
    fetchSynthese(prefsApiBase).then((d) => { if (d && d.error) setError(d.error); else setDoc(d); });
  }, [prefsApiBase]);
  const view = useMemo(() => (doc ? filterDoc(doc, q) : null), [doc, q]);
  const links = doc?.links || {};
  const toggle = (k) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  const H = ({ k, children, count }) => (
    <h3 style={{ cursor: "pointer", margin: "14px 0 6px" }} onClick={() => toggle(k)}>{open[k] ? "▾" : "▸"} {children}{count != null && <span className="muted" style={{ fontSize: 13, fontWeight: "normal" }}> ({count})</span>}</h3>
  );
  const IpCell = ({ ip }) => {
    const info = doc?.index?.[ip];
    return (
      <span title={info ? describeIp(ip, info) : ip}>
        <button type="button" className="sy-ip" onClick={() => setQ(ip)}>{ip}</button>
        {info && info.dns.length > 0 && <span className="muted" style={{ fontSize: 11 }}> {info.dns.slice(0, 3).join(", ")}{info.dns.length > 3 ? "…" : ""}</span>}
      </span>
    );
  };

  return (
    <div className="sy-view" style={{ padding: "0 16px 24px" }}>
      <div className="hub-theme-bar">
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <strong className="hub-theme-title">🧾 Infos synthèse SI</strong>
        {doc && <span className="muted" style={{ fontSize: 12 }}>générée le {doc.generated_at?.replace("T", " ")} · {doc.summary?.indexed_ips} adresses recoupées</span>}
      </div>
      {error && <p className="muted">⚠️ {error} — déposer les exports dans <code>synthese/data/</code> et lancer <code>scripts/synthese-si.sh</code> (voir <code>synthese/README.md</code>).</p>}
      {!doc && !error && <p className="muted">Chargement…</p>}
      {doc && (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: "8px 0" }}>
            <input type="search" placeholder="IP, nom, domaine, service, hôte…" value={q} onChange={(e) => setQ(e.target.value)} style={{ flex: "1 1 260px" }} />
            {q && <button type="button" className="secondary" onClick={() => setQ("")}>✕</button>}
            {links.ipam_url && <Ext href={links.ipam_url}>IPAM</Ext>}
            <Ext href={links.ovh_services}>Services OVH</Ext>
            <Ext href={links.online_console}>Console Online</Ext>
            {onNavigate && <button type="button" className="secondary" onClick={() => onNavigate("network-equipment")}>Équipements réseau (hub)</button>}
            {onNavigate && <button type="button" className="secondary" onClick={() => onNavigate("network-agent")}>Exploration (hub)</button>}
          </div>
          {q && doc.index[q.trim()] && (
            <div className="hub-card" style={{ padding: 10, margin: "6px 0" }}>
              <strong>{q.trim()}</strong> — {describeIp(q.trim(), doc.index[q.trim()])}
              {" "}{ipLinks(q.trim(), doc.index[q.trim()], links).map((l) => <Ext key={l.label} href={l.href}>{l.label}</Ext>)}
            </div>
          )}

          <H k="ips" count={view.ovh_ips.length}>IP OVH et services rattachés</H>
          {open.ips && (
            <table><thead><tr><th>IP / bloc</th><th>Type</th><th>Service OVH</th><th>Noms DNS</th><th>IPAM</th><th>Liens</th></tr></thead>
              <tbody>{view.ovh_ips.map((o) => { const info = doc.index[o.ip] || { dns: [], ipam: [], services: [] }; return (
                <tr key={o.block}>
                  <td><IpCell ip={o.ip} /><div className="muted" style={{ fontSize: 11 }}>{o.block}{o.country ? ` · ${o.country}` : ""}</div></td>
                  <td>{o.type}</td>
                  <td style={{ fontSize: 12 }}>{o.service}{info.services.length > 0 && <div className="muted" style={{ fontSize: 11 }}>{info.services.map((s) => `${s.type} ${s.effective || ""}`).join(" · ")}</div>}</td>
                  <td style={{ fontSize: 12 }}>{info.dns.join(", ") || <span className="muted">—</span>}</td>
                  <td style={{ fontSize: 12 }}>{info.ipam.map((h) => `${h.hostname || "?"} (${h.subnet})`).join(", ") || <span className="muted">—</span>}</td>
                  <td style={{ fontSize: 12 }}>{ipLinks(o.ip, info, links).map((l) => <Ext key={l.label} href={l.href}>{l.label}</Ext>)}</td>
                </tr>); })}</tbody></table>
          )}

          <H k="zones" count={view.zones.reduce((n, z) => n + z.records.length, 0)}>Zones DNS</H>
          {open.zones && view.zones.map((z) => (
            <div key={z.zone} style={{ marginBottom: 10 }}>
              <h4 style={{ margin: "6px 0 4px" }}>{z.zone} <span className="muted" style={{ fontSize: 12, fontWeight: "normal" }}>· {z.provider || "?"} · {z.records.length} enregistrements</span> <Ext href={zoneLink(z, links)}>gérer la zone</Ext>{z.provider === "ovh" && <Ext href={fillLink(links.ovh_domain, { zone: z.zone })}>domaine</Ext>}</h4>
              <table><thead><tr><th>Nom</th><th>Type</th><th>Valeur</th><th>TTL</th><th>Note</th></tr></thead>
                <tbody>{z.records.map((r, i) => (
                  <tr key={i}>
                    <td><code>{r.name}</code>{r.name !== "@" && <span className="muted" style={{ fontSize: 11 }}> {r.fqdn}</span>}</td>
                    <td>{r.type}</td>
                    <td style={{ fontSize: 12, wordBreak: "break-all" }}>{(r.type === "A" || r.type === "AAAA") ? <IpCell ip={r.value} /> : r.value}</td>
                    <td className="muted" style={{ fontSize: 12 }}>{r.ttl ?? "—"}</td>
                    <td className="muted" style={{ fontSize: 12 }}>{r.comment || ""}</td>
                  </tr>
                ))}</tbody></table>
            </div>
          ))}

          <H k="ipam" count={view.ipam.subnets.reduce((n, s) => n + s.hosts.length, 0)}>IPAM — sous-réseaux</H>
          {open.ipam && view.ipam.subnets.map((s) => (
            <div key={s.cidr || s.title} style={{ marginBottom: 10 }}>
              <h4 style={{ margin: "6px 0 4px" }}>{s.title || s.cidr} <span className="muted" style={{ fontSize: 12, fontWeight: "normal" }}>· {s.cidr}{s.vlan ? ` · vlan ${s.vlan}` : ""}</span> {links.ipam_url && <Ext href={links.ipam_url}>ouvrir IPAM</Ext>}</h4>
              <table><thead><tr><th>IP</th><th>Hôte</th><th>Description</th><th>MAC</th><th>Équipement / port</th><th>Lieu</th><th>Reverse</th></tr></thead>
                <tbody>{s.hosts.map((h) => (
                  <tr key={h.ip}>
                    <td><IpCell ip={h.ip} /></td>
                    <td>{h.hostname || "—"}</td>
                    <td style={{ fontSize: 12 }}>{h.description || ""}</td>
                    <td className="muted" style={{ fontSize: 11 }}>{h.mac || ""}</td>
                    <td style={{ fontSize: 12 }}>{[h.device, h.port].filter(Boolean).join(" / ")}</td>
                    <td style={{ fontSize: 12 }}>{h.location || ""}</td>
                    <td style={{ fontSize: 12 }}>{h.reverse || ""}</td>
                  </tr>
                ))}</tbody></table>
            </div>
          ))}

          <H k="devices" count={view.ipam.devices.length}>Équipements (IPAM)</H>
          {open.devices && (
            <table><thead><tr><th>Nom</th><th>IP</th><th>Type</th><th>Constructeur</th><th>Modèle</th><th></th></tr></thead>
              <tbody>{view.ipam.devices.map((d) => (
                <tr key={d.name + d.ip}>
                  <td>{d.name}</td><td><IpCell ip={d.ip} /></td><td>{d.type || ""}</td><td>{d.vendor || ""}</td><td>{d.model || ""}</td>
                  <td>{onNavigate && <button type="button" className="secondary" onClick={() => onNavigate("network-equipment")}>fiche hub</button>}</td>
                </tr>
              ))}</tbody></table>
          )}

          <H k="services" count={view.ovh_services.length}>Services OVH — échéances</H>
          {open.services && (
            <table><thead><tr><th>Service</th><th>Type</th><th>Statut</th><th>Renouvellement</th><th>Échéance</th></tr></thead>
              <tbody>{view.ovh_services.map((s, i) => { const d = daysUntil(s.effective_iso); return (
                <tr key={i}>
                  <td>{s.service}{s.ip && <> <IpCell ip={s.ip} /></>}</td><td>{s.type}</td><td>{s.status}</td><td style={{ fontSize: 12 }}>{s.renewal}</td>
                  <td style={{ fontSize: 12 }}>{s.effective}{d != null && <span className={d < 0 ? "sy-late" : d <= 60 ? "sy-soon" : "muted"}> ({d < 0 ? `dépassée de ${-d} j` : `dans ${d} j`})</span>}</td>
                </tr>); })}</tbody></table>
          )}

          <H k="sources" count={doc.sources.length}>Sources de cette synthèse</H>
          {open.sources && (
            <ul className="muted" style={{ fontSize: 12 }}>
              {doc.sources.map((s) => <li key={s.source}>{s.source} — {s.kind || "non reconnu"}{s.count != null ? ` (${s.count})` : ""}</li>)}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
