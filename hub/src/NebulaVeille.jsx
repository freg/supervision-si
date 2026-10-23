// Veille de santé du réseau du campus (livraison #847) -- onglet « Veille » de la tuile Nebula@<site>.
// Deux sources croisées par nebula-api (veille.py) : Nebula (passerelle, commutateurs, bornes, clients) et les agents
// internes du site (poste du campus, Proxmox : sondes « chemin de service » et « annonces réseau »). Silencieuse
// quand tout va bien ; alertes par notify-api (usage interne / créneau d'un organisme extérieur) ; réglages ici.
import { useEffect, useState } from "react";

const ETAT = { ok: ["Tout va bien", "var(--ok)"], degrade: ["Dégradé", "var(--warn, #e8b84a)"], panne: ["PANNE", "var(--danger)"], inconnu: ["Rien d'observable", "var(--muted, #8fa1b3)"] };
const STATUT = { ok: ["✓", "var(--ok)"], ko: ["✗", "var(--danger)"], doute: ["?", "var(--warn, #e8b84a)"], inconnu: ["—", "var(--muted, #8fa1b3)"] };
const FAMILLES = [["agents", "Agents internes"], ["equipements", "Équipements Nebula"], ["vlans", "VLAN suivis"], ["internet", "Liaison Internet"], ["postes", "Postes suivis"]];
const when = (ts) => (ts ? new Date(ts * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");

async function call(url, opts) {
  const r = await fetch(url, { credentials: "include", ...opts });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `${r.status}`);
  return d;
}

/** Créneaux enregistrés -> texte éditable (« 1,2,3,4,5 08:00-12:30 externe ; … »). */
export function creneauxTexte(cr) {
  return (cr || []).map((c) => `${(c.jours || []).join(",")} ${c.debut}-${c.fin} ${c.usage || "interne"}`).join(" ; ");
}

export default function NebulaVeille({ nebulaApiBase, siAgentApiBase = "", groups = [], login = "" }) {
  const base = `${nebulaApiBase}/veille`;
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState(null);
  const [note, setNote] = useState(null);
  const [agents, setAgents] = useState([]);

  const load = async (refresh) => { try { setD(await call(`${base}${refresh ? "?refresh=1" : ""}`)); setErr(null); } catch (e) { setErr(e.message); } };
  useEffect(() => { load(); const id = setInterval(() => load(), 60000); return () => clearInterval(id); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [nebulaApiBase]);
  useEffect(() => {
    if (!edit || !siAgentApiBase || agents.length) return;
    fetch(`${siAgentApiBase}/agents`, { credentials: "include" }).then((r) => r.json()).then((x) => setAgents(x.agents || [])).catch(() => {});
  }, [edit, siAgentApiBase, agents.length]);

  const passer = async () => { setBusy(true); try { setD({ ...(await call(`${base}/passer`, { method: "POST" })), suivi: d?.suivi, retablies_24h: d?.retablies_24h, reglages: d?.reglages }); load(); } catch (e) { setErr(e.message); } setBusy(false); };
  const ouvrir = () => {
    const r = d?.reglages || {};
    setEdit({ ...r, agentsTxt: (r.agents || []).join(", "), vlans: (r.vlans || []).map((v) => ({ ...v, dhcp: (v.dhcp_attendus || []).join(", "), cren: creneauxTexte(v.creneaux) })),
      postes: (r.postes || []).map((p) => ({ ...p, vlan: p.vlan ?? "" })) });
    setNote(null);
  };
  const enregistrer = async () => {
    setBusy(true); setNote(null);
    const e = edit;
    const reglages = { enabled: e.enabled, site_id: e.site_id, agent_site: e.agent_site, agents: e.agentsTxt.split(/[\s,;]+/).filter(Boolean), heures: e.heures,
      agent_silence_min: +e.agent_silence_min, fraicheur_min: +e.fraicheur_min, periode_s: +e.periode_s, alerte: e.alerte,
      vlans: e.vlans.map((v) => ({ id: +v.id, nom: v.nom, connexion: v.connexion, sous_reseau: v.sous_reseau, dhcp_attendus: v.dhcp, creneaux: v.cren, internet: v.internet !== false })),
      postes: e.postes.map((p) => ({ nom: p.nom, mac: p.mac, ip: p.ip, vlan: p.vlan === "" ? null : +p.vlan, attendu: p.attendu })) };
    try { const r = await call(`${base}/reglages`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups, user: login, reglages }) });
      setNote(["ok", "Réglages enregistrés."]); setEdit(null); setD((x) => ({ ...x, ...r.resultat, reglages: r.reglages })); load(); }
    catch (x) { setNote(["ko", x.message]); }
    setBusy(false);
  };
  const setE = (k, v) => setEdit((x) => ({ ...x, [k]: v }));
  const setRow = (k, i, f, v) => setEdit((x) => ({ ...x, [k]: x[k].map((r, j) => (j === i ? { ...r, [f]: v } : r)) }));

  if (err && !d) return <div className="hub-card"><p className="muted" style={{ margin: 0 }}>Veille indisponible ({err}).</p></div>;
  if (!d) return <p className="muted">Chargement de la veille…</p>;
  const [lib, coul] = ETAT[d.etat] || ETAT.inconnu;
  const lien = (v) => (v.lien ? <a href={v.lien}>{v.statut === "inconnu" && v.famille !== "postes" ? "activer la sonde" : "voir"}</a> : <span className="muted">pas de lien : opération manuelle</span>);

  return (
    <div>
      <div className="hub-card" style={{ borderLeft: `6px solid ${coul}`, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ color: coul, fontSize: "1.1em" }}>{lib}</b>
        <span style={{ flex: 1, minWidth: 240 }}>{d.resume}</span>
        <span className="muted">{["ok", "ko", "doute", "inconnu"].map((s) => `${STATUT[s][0]} ${d.compte?.[s] ?? 0}`).join("  ")} · {when(d.at)}</span>
        <button type="button" onClick={passer} disabled={busy}>{busy ? "en cours…" : "Vérifier maintenant"}</button>
        <button type="button" className="secondary" onClick={() => (edit ? setEdit(null) : ouvrir())}>{edit ? "Fermer les réglages" : "Réglages"}</button>
      </div>
      {(d.erreurs || []).length > 0 && <p className="muted">Sources partielles : {d.erreurs.join(" ; ")}</p>}
      {note && <p style={{ color: note[0] === "ok" ? "var(--ok)" : "var(--danger)" }}>{note[1]}</p>}

      {edit && (
        <div className="hub-card">
          <h3 style={{ marginTop: 0 }}>Réglages de la veille</h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            <label><input type="checkbox" checked={!!edit.enabled} onChange={(e) => setE("enabled", e.target.checked)} /> alertes actives</label>
            <label>Agents internes (identifiants)<br /><input value={edit.agentsTxt} onChange={(e) => setE("agentsTxt", e.target.value)} size={40} placeholder="pc-campus, pve-campus" /></label>
            <label>ou tous les agents du site<br /><input value={edit.agent_site} onChange={(e) => setE("agent_site", e.target.value)} placeholder="site-alpha" /></label>
            <label>Heures ouvrées<br /><input value={edit.heures} onChange={(e) => setE("heures", e.target.value)} placeholder="1-5 08:00-18:00" /></label>
            <label>Agent muet après (min)<br /><input type="number" value={edit.agent_silence_min} onChange={(e) => setE("agent_silence_min", e.target.value)} style={{ width: 70 }} /></label>
            <label>Relevé trop vieux après (min)<br /><input type="number" value={edit.fraicheur_min} onChange={(e) => setE("fraicheur_min", e.target.value)} style={{ width: 70 }} /></label>
            <label>Passage toutes les (s)<br /><input type="number" value={edit.periode_s} onChange={(e) => setE("periode_s", e.target.value)} style={{ width: 80 }} /></label>
          </div>
          {agents.length > 0 && <p className="muted">Agents connus : {agents.map((a) => <button key={a.agent_id} type="button" className="secondary" style={{ margin: 2 }} onClick={() => setE("agentsTxt", [...new Set([...edit.agentsTxt.split(/[\s,;]+/).filter(Boolean), a.agent_id])].join(", "))}>{a.agent_id}{a.site ? ` (${a.site})` : ""}</button>)}</p>}

          <h4>VLAN suivis</h4>
          <p className="muted">Un VLAN est vu par la sonde « chemin de service » d'un agent présent dedans : nom de la connexion / du SSID (rotation <code>--connections</code>) ou sous-réseau de l'interface. Créneaux : « 1-5 08:00-12:30 externe ; 1-5 13:30-18:00 interne » (jours 1 = lundi) ; pendant un créneau « externe », l'alerte part sur l'action « nebula.veille-campus-externe ».</p>
          <div style={{ overflowX: "auto" }}><table className="services"><thead><tr><th>VLAN</th><th>Nom</th><th>Connexion / SSID</th><th>Sous-réseau</th><th>DHCP attendus</th><th>Créneaux d'usage</th><th>Internet</th><th></th></tr></thead><tbody>
            {edit.vlans.map((v, i) => (
              <tr key={i}>
                <td><input type="number" value={v.id} onChange={(e) => setRow("vlans", i, "id", e.target.value)} style={{ width: 70 }} /></td>
                <td><input value={v.nom} onChange={(e) => setRow("vlans", i, "nom", e.target.value)} /></td>
                <td><input value={v.connexion} onChange={(e) => setRow("vlans", i, "connexion", e.target.value)} /></td>
                <td><input value={v.sous_reseau} onChange={(e) => setRow("vlans", i, "sous_reseau", e.target.value)} placeholder="192.0.2.0/24" /></td>
                <td><input value={v.dhcp} onChange={(e) => setRow("vlans", i, "dhcp", e.target.value)} placeholder="192.0.2.1" /></td>
                <td><input value={v.cren} onChange={(e) => setRow("vlans", i, "cren", e.target.value)} size={34} /></td>
                <td><input type="checkbox" checked={v.internet !== false} onChange={(e) => setRow("vlans", i, "internet", e.target.checked)} /></td>
                <td><button type="button" className="secondary" onClick={() => setE("vlans", edit.vlans.filter((_x, j) => j !== i))}>×</button></td>
              </tr>))}
          </tbody></table></div>
          <button type="button" className="secondary" onClick={() => setE("vlans", [...edit.vlans, { id: "", nom: "", connexion: "", sous_reseau: "", dhcp: "", cren: "", internet: true }])}>+ VLAN</button>

          <h4>Postes suivis</h4>
          <p className="muted">Présence vue par les clients Nebula et les annonces réseau des agents. « toujours » : absent = alerte ; « heures » : alerte aux heures ouvrées ; « info » : présence affichée sans alerte.</p>
          <div style={{ overflowX: "auto" }}><table className="services"><thead><tr><th>Nom</th><th>MAC</th><th>IP</th><th>VLAN</th><th>Attendu</th><th></th></tr></thead><tbody>
            {edit.postes.map((p, i) => (
              <tr key={i}>
                <td><input value={p.nom} onChange={(e) => setRow("postes", i, "nom", e.target.value)} /></td>
                <td><input value={p.mac} onChange={(e) => setRow("postes", i, "mac", e.target.value)} placeholder="02:00:5e:00:00:01" /></td>
                <td><input value={p.ip} onChange={(e) => setRow("postes", i, "ip", e.target.value)} /></td>
                <td><input type="number" value={p.vlan} onChange={(e) => setRow("postes", i, "vlan", e.target.value)} style={{ width: 70 }} /></td>
                <td><select value={p.attendu} onChange={(e) => setRow("postes", i, "attendu", e.target.value)}><option>toujours</option><option>heures</option><option>info</option></select></td>
                <td><button type="button" className="secondary" onClick={() => setE("postes", edit.postes.filter((_x, j) => j !== i))}>×</button></td>
              </tr>))}
          </tbody></table></div>
          <button type="button" className="secondary" onClick={() => setE("postes", [...edit.postes, { nom: "", mac: "", ip: "", vlan: "", attendu: "toujours" }])}>+ poste</button>

          <h4>Alertes</h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            <label>Délai avant alerte (min)<br /><input type="number" value={edit.alerte.delay_minutes} onChange={(e) => setE("alerte", { ...edit.alerte, delay_minutes: +e.target.value })} style={{ width: 70 }} /></label>
            <label>Rappel (h, 0 = jamais)<br /><input type="number" value={edit.alerte.repeat_hours} onChange={(e) => setE("alerte", { ...edit.alerte, repeat_hours: +e.target.value })} style={{ width: 70 }} /></label>
            <label>Gravité minimale<br /><select value={edit.alerte.min_severity} onChange={(e) => setE("alerte", { ...edit.alerte, min_severity: e.target.value })}><option>haute</option><option>moyenne</option><option>basse</option></select></label>
            <label><input type="checkbox" checked={!!edit.alerte.notify_recovery} onChange={(e) => setE("alerte", { ...edit.alerte, notify_recovery: e.target.checked })} /> prévenir du retour à la normale</label>
          </div>
          <p className="muted">Destinataires : <a href="?view=notifications">tuile Notifications</a>, actions « nebula.veille-campus » (interne), « nebula.veille-campus-externe » (créneau d'un organisme extérieur) et « nebula.veille-campus-retabli ». Veilleur du poste (si-veille) : maillon http sur <code>{nebulaApiBase}/veille/etat?jeton=…</code> (jeton <code>NEBULA_VEILLE_TOKEN</code> du .env) avec <code>"contient": "OK"</code>.</p>
          <button type="button" onClick={enregistrer} disabled={busy}>{busy ? "en cours…" : "Enregistrer"}</button>
        </div>
      )}

      {FAMILLES.map(([f, titre]) => {
        const lst = (d.verifs || []).filter((v) => v.famille === f);
        if (!lst.length) return null;
        return (
          <div key={f} className="hub-card">
            <h3 style={{ marginTop: 0 }}>{titre}</h3>
            <div style={{ maxHeight: 360, overflow: "auto" }}><table className="services infra-table" style={{ width: "100%" }}>
              <thead><tr><th></th><th>Vérification</th><th>Détail</th><th>Source</th><th>Usage</th><th></th></tr></thead>
              <tbody>{lst.map((v) => (
                <tr key={v.id}>
                  <td style={{ color: STATUT[v.statut][1], fontWeight: 700 }} title={v.statut}>{STATUT[v.statut][0]}</td>
                  <td>{v.nom}</td><td>{v.detail}</td><td className="muted">{v.source}</td>
                  <td>{v.usage === "externe" ? <span style={{ color: "var(--warn, #e8b84a)" }}>organisme extérieur</span> : <span className="muted">interne</span>}</td>
                  <td>{lien(v)}</td>
                </tr>))}</tbody>
            </table></div>
          </div>);
      })}

      {((d.suivi || []).length > 0 || (d.retablies_24h || []).length > 0) && (
        <div className="hub-card">
          <h3 style={{ marginTop: 0 }}>Suivi des alertes</h3>
          <table className="services"><thead><tr><th>Élément</th><th>Constat</th><th>Depuis</th><th>Alerté</th><th>Rétabli</th></tr></thead><tbody>
            {(d.suivi || []).map((e) => <tr key={e.id}><td>{e.element}</td><td>{e.message}</td><td>{when(e.first_seen)}</td><td>{when(e.notified_at)}</td><td>—</td></tr>)}
            {(d.retablies_24h || []).map((e, i) => <tr key={"r" + i} className="muted"><td>{e.element}</td><td>{e.message}</td><td>{when(e.first_seen)}</td><td>{when(e.notified_at)}</td><td>{when(e.resolved_at)}</td></tr>)}
          </tbody></table>
        </div>)}
    </div>
  );
}
