// #883 : tuile « NAS » -- état et alertes des NAS relevés en SNMP (lecture seule) par la sonde nas-snmp d'un agent :
// volumes (remplissage), disques (état, température, âge, SMART critiques), RAID, ventilateurs, applications, alertes.
// #927 : potentiel d'évolution (baies libres, réserve non allouée, extension jusqu'à, conseils chiffrés).
import { useCallback, useEffect, useState } from "react";
import { fetchNas } from "./siAgentClient.js";
import { hubLink } from "./hubLinks.js";
import IpPing from "./IpPing.jsx";
import { evolution } from "./nasEvolution.js";   // #927
import { conseilsNas } from "./conseilsNas.js";   // #944
import ConseilsListe from "./ConseilsListe.jsx";   // #944

const TON = { critical: "bad", warning: "warn", info: "neutral" };
const to = (o) => (o == null ? "—" : o >= 1e12 ? `${(o / 1e12).toFixed(1).replace(".", ",")} To` : `${Math.round(o / 1e9)} Go`);
const koTo = (k) => (k == null ? "—" : to(k * 1024));
const ans = (h) => (h == null ? "—" : `${h.toLocaleString("fr-FR")} h (${(h / 8766).toFixed(1).replace(".", ",")} ans)`);
const age = (at) => { const s = (Date.now() - Date.parse(at)) / 1000; return s < 3600 ? `il y a ${Math.round(s / 60)} min` : `il y a ${Math.round(s / 3600)} h`; };

// #927 : baies du NAS (occupées : disque dur / SSD ; libres en pointillés) et conseils chiffrés pour agrandir les volumes.
function Baies({ e }) {
  if (!e.baies) return null;
  const par = Object.fromEntries(e.occupees.map((o) => [o.baie, o]));
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap", margin: "4px 0 8px" }}>
      {Array.from({ length: e.baies }, (_, i) => i + 1).map((b) => {
        const o = par[b];
        return <div key={b} title={o ? `baie ${b} : ${o.modele || o.type}` : `baie ${b} : libre`}
          style={{ width: 64, padding: "4px 0", textAlign: "center", borderRadius: 4, fontSize: 12,
            border: o ? "1px solid var(--border)" : "1px dashed var(--muted)", background: o ? (o.type === "SSD" ? "rgba(255,170,0,.18)" : "rgba(80,160,255,.18)") : "transparent",
            color: o ? "inherit" : "var(--muted)" }}>
          {b}<br />{o ? o.type : "libre"}
        </div>;
      })}
    </div>
  );
}

function Evolution({ e }) {
  const TONS = { good: "good", warn: "warn", neutral: "neutral" };
  return (
    <section style={{ margin: "10px 0" }}>
      <h4 style={{ marginBottom: 2 }}>Potentiel d'évolution</h4>
      <div className="infra-muted">
        {e.baies ? `${e.baies} baies (${e.source === "réglage" ? "réglage" : "d'après le modèle"}) · ${e.occupees.length} occupée(s) · ${e.libres.length} libre(s)` : "nombre de baies inconnu"}
        {e.raid ? ` · données en RAID ${e.raid}` : ""}{e.reserve.total ? ` · réserve ${to(e.reserve.total)}, dont ${to(e.reserve.libre)} non alloués` : ""}
      </div>
      <Baies e={e} />
      <ol style={{ margin: "4px 0", paddingLeft: 20 }}>
        {e.conseils.map((c) => (
          <li key={c.cle} style={{ marginBottom: 4 }}>
            <b className={`np-tone ${TONS[c.ton] || "neutral"}`}>{c.titre}</b>{c.gain > 0 ? <span className="infra-muted"> · +{to(c.gain)}</span> : null}
            <div className="infra-muted" style={{ fontSize: 13 }}>{c.detail}</div>
          </li>))}
      </ol>
      <div className="infra-muted" style={{ fontSize: 12 }}>Capacités utiles théoriques (unités des fabricants de disques) ; à valider avant achat avec la liste de compatibilité QNAP du modèle.</div>
    </section>
  );
}

function Barre({ pct }) {
  const c = pct >= 90 ? "var(--danger)" : pct >= 80 ? "var(--warning)" : "var(--ok)";
  return <div style={{ background: "rgba(127,127,127,.25)", borderRadius: 4, height: 10, width: 160, display: "inline-block", verticalAlign: "middle" }}>
    <div style={{ width: `${Math.min(100, pct || 0)}%`, background: c, height: "100%", borderRadius: 4 }} /></div>;
}

export default function NasView({ onBack, siAgentApiBase }) {
  const [nas, setNas] = useState(null);
  const load = useCallback(() => fetchNas(siAgentApiBase).then(setNas), [siAgentApiBase]);
  useEffect(() => { load(); const t = setInterval(load, 120000); return () => clearInterval(t); }, [load]);
  return (
    <div className="infra-page">
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
        <h2 style={{ margin: 0 }}>NAS</h2>
        <span className="infra-muted">relevé SNMP en lecture seule, toutes les 15 min (sonde nas-snmp)</span>
      </div>
      {nas === null ? <p className="infra-muted">lecture…</p> : nas.length === 0 ? (
        <p className="infra-muted">Aucun NAS relevé. Activer la sonde <b>nas-snmp</b> sur un agent du réseau du NAS : <a href={hubLink("si-agent", { tab: "catalogue" })}>Agents › Sondes</a>
          {" "}(pas de lien pour les réglages : opération manuelle -- fichier /etc/si-agent/nas-snmp.json sur l'hôte de l'agent, root seulement :
          {" "}<code>[{`{"name": "nas-1", "host": "<adresse>", "community": "<communauté>", "version": "2c"}`}]</code> ; paquet <code>snmp</code>).</p>
      ) : nas.map((n) => (
        <section key={n.name} className="infra-card" style={{ margin: "12px 0" }}>
          <h3 style={{ margin: "0 0 4px" }}>{n.name} <span className="infra-muted" style={{ fontSize: 13 }}>
            <IpPing ip={n.host} /> · {n.systeme?.modele || ""} {n.systeme?.micrologiciel ? `· système ${n.systeme.micrologiciel}` : ""} · relevé par {n.relais} {n.at ? age(n.at) : ""}</span></h3>
          {!n.ok ? <p className="np-tone bad">injoignable : {n.error}</p> : (() => { const evo = evolution(n); return <>
            {(n.alertes || []).length > 0 && <div style={{ margin: "6px 0" }}>{n.alertes.map((a, i) => <div key={i} className={`np-tone ${TON[a.severity] || "neutral"}`}>• {a.message}</div>)}</div>}
            <ConseilsListe liste={conseilsNas(n, undefined)} titre="Propositions et conseils (SNMP)" note="Déduits du relevé SNMP ; snapshots, Time Machine et connexions : tuile Sauvegardes › NAS QNAP (sonde nas-qnap). Rien n'est modifié sur le NAS." />
            <h4>Volumes</h4>
            <table className="infra-table"><thead><tr><th>Volume</th><th>Remplissage</th><th>Utilisé</th><th>Taille</th><th title="taille + espace non alloué de la réserve">Extensible jusqu'à</th><th>État</th></tr></thead>
              <tbody>{(n.volumes || []).map((v) => <tr key={v._idx}><td>{v.nom}{v.leger ? <span className="infra-muted"> (léger)</span> : null}</td>
                <td><Barre pct={v.pct} /> {v.pct != null ? `${String(v.pct).replace(".", ",")} %` : "—"}</td><td>{koTo(v.ko != null && v.libre_ko != null ? v.ko - v.libre_ko : null)}</td><td>{koTo(v.ko)}</td><td>{to(evo.volumes[v.nom])}</td><td>{v.etat}</td></tr>)}</tbody></table>
            <Evolution e={evo} />
            <h4>Disques</h4>
            <table className="infra-table"><thead><tr><th>Baie</th><th>Modèle</th><th>Capacité</th><th>État</th><th>Temp.</th><th>Fonctionnement</th><th>SMART critiques</th></tr></thead>
              <tbody>{(n.disques || []).map((d) => {
                const smart = Object.entries(d.smart || {}).filter(([, v]) => v > 0);
                return <tr key={d._idx}><td>{d.emplacement}</td><td>{d.modele}</td><td>{to(d.octets)}</td>
                  <td className={`np-tone ${String(d.etat).toLowerCase() === "good" ? "good" : "bad"}`}>{d.etat}</td>
                  <td className={d.temperature >= 50 ? "np-tone warn" : ""}>{d.temperature != null ? `${d.temperature} °C` : "—"}</td>
                  <td className={d.heures >= 50000 ? "np-tone warn" : ""}>{ans(d.heures)}</td>
                  <td className={smart.length ? "np-tone warn" : ""}>{smart.length ? smart.map(([k, v]) => `${v} ${k}`).join(", ") : "aucun"}</td></tr>;
              })}</tbody></table>
            <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
              <div><h4>RAID</h4>{(n.raid || []).map((r) => <div key={r._idx}>{r.dev} : {r.niveau === "Single" ? "simple (sans redondance)" : `RAID ${r.niveau}`} · {r.etat} · {to(r.octets)}</div>)}</div>
              <div><h4>Ventilateurs</h4>{(n.ventilateurs || []).map((f) => <div key={f._idx} className={f.tours === 0 ? "np-tone bad" : ""}>{f.nom} : {f.tours} tr/min</div>)}</div>
              <div><h4>Réserve</h4>{(n.reserves || []).map((r) => <div key={r._idx}>réserve {r.id} : {to(r.octets)}, libre {to(r.libre_octets)}</div>)}</div>
            </div>
            <h4>Applications ({(n.applications || []).length}, dont {(n.applications || []).filter((a) => a.mise_a_jour).length} à mettre à jour)</h4>
            <div style={{ maxHeight: 220, overflow: "auto" }}><table className="infra-table"><thead><tr><th>Application</th><th>Version</th><th>Disponible</th><th>Active</th></tr></thead>
              <tbody>{[...(n.applications || [])].sort((a, b) => (b.mise_a_jour - a.mise_a_jour) || String(a.nom).localeCompare(b.nom)).map((a) =>
                <tr key={a._idx} className={a.mise_a_jour ? "np-tone warn" : ""}><td>{a.nom}</td><td>{a.version}</td><td>{a.mise_a_jour ? a.disponible : "à jour"}</td><td>{a.actif ? "oui" : "non"}</td></tr>)}</tbody></table></div>
          </>; })()}
        </section>
      ))}
    </div>
  );
}
