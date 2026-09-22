// Anomalies de la carte des VLAN en TABLEAU (livraison #556) : pleine
// largeur, aligné à gauche, colonnes Élément · Constat · Gravité · Action
// proposée (depuis rules/) · Masquer · Valider ; « Tout démasquer ». Valider
// applique la correction quand la règle est applicable et que l'écriture est
// autorisée (NEBULA_ALLOW_WRITE), après confirmation ; sinon enregistre la
// validation. Données : /sites/<id>/anomalies.
import { useEffect, useState } from "react";

async function call(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(j.error || `${r.status}`); e.body = j; throw e; }
  return j;
}

const SEV = { haute: { label: "Haute", color: "#c62828" }, moyenne: { label: "Moyenne", color: "#ef6c00" }, basse: { label: "Basse", color: "#1565c0" }, info: { label: "Info", color: "#757575" } };
const STATE_LABEL = { validated: "validée, à appliquer à la main", applied: "appliquée", failed: "échec de l'application", hidden: "masquée" };

export default function NebulaAnomalies({ nebulaApiBase, siteId, groups, login, version }) {
  const [data, setData] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);
  const [open, setOpen] = useState(null);
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/anomalies`;

  const load = async () => {
    if (!siteId) return;
    try { setData(await call(`${base}${showAll ? "?all=1" : ""}`)); setError(null); } catch (e) { setError(e.message); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [siteId, showAll, version]);

  const post = async (path, body) => {
    setBusy(path); setError(null);
    try { const r = await call(`${base}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups, user: login, ...(body || {}) }) }); await load(); return r; }
    catch (e) { setError(e.message); return null; }
    finally { setBusy(null); }
  };
  const validate = async (a) => {
    if (a.can_apply) {
      if (!window.confirm(`Cette validation ÉCRIT la configuration sur Nebula :\n\n${a.action}\n\nConfirmer ?`)) return;
      await post(`/${a.id}/validate`, { confirm: true });
    } else {
      await post(`/${a.id}/validate`, {});
    }
  };

  if (error && !data) return <p style={{ color: "var(--danger)" }}>{error}</p>;
  if (!data) return <p className="muted">Lecture des anomalies…</p>;
  const rows = data.anomalies || [];
  return (
    <div style={{ width: "100%" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: "8px 0" }}>
        <strong>{data.total} anomalie{data.total > 1 ? "s" : ""}</strong>
        {data.hidden_count > 0 && <span className="muted">· {data.hidden_count} masquée{data.hidden_count > 1 ? "s" : ""}</span>}
        <span style={{ flex: 1 }} />
        <label className="muted"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> voir les masquées</label>
        <button type="button" className="secondary" disabled={busy || data.hidden_count === 0} onClick={() => post("/unhide-all")}>Tout démasquer</button>
        {!data.write_allowed && <span className="muted" title="NEBULA_ALLOW_WRITE=1 dans le .env pour appliquer les corrections">écriture Nebula désactivée</span>}
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {data.rules_errors?.length > 0 && <p className="muted">Règles illisibles : {data.rules_errors.join(" · ")}</p>}
      {rows.length === 0 ? <p className="muted">Aucune anomalie : chaque liaison porte les mêmes VLAN des deux côtés et chaque SSID a son VLAN sur les commutateurs.</p> : (
        <table style={{ width: "100%", tableLayout: "auto", textAlign: "left" }}>
          <thead><tr style={{ textAlign: "left" }}><th>Élément</th><th>Constat</th><th>Gravité</th><th>Action proposée</th><th>État</th><th></th><th></th></tr></thead>
          <tbody>
            {rows.map((a) => {
              const sev = SEV[a.severity] || SEV.info;
              const hidden = a.state === "hidden";
              return (
                <tr key={a.id} style={{ opacity: hidden ? 0.5 : 1, verticalAlign: "top", textAlign: "left" }}>
                  <td style={{ whiteSpace: "nowrap" }}>{a.element}</td>
                  <td>{a.message}{a.rule_id && <button type="button" className="secondary" style={{ marginLeft: 6, fontSize: 11 }} onClick={() => setOpen(open === a.id ? null : a.id)} title={a.rule_title}>{open === a.id ? "moins" : "pourquoi ?"}</button>}
                    {open === a.id && <div className="muted" style={{ marginTop: 4, fontSize: 12 }}><div><strong>{a.rule_id}</strong> · {a.rule_title}</div>{a.why && <div>Pourquoi : {a.why}</div>}{a.verify && <div>Vérifier : {a.verify}</div>}</div>}</td>
                  <td style={{ whiteSpace: "nowrap", color: sev.color, fontWeight: 600 }}>{sev.label}</td>
                  <td>{a.action}{a.applicable && <span className="muted" style={{ fontSize: 11 }}> · applicable par l'API{a.can_apply ? "" : " (écriture désactivée)"}</span>}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{a.state ? <span title={a.state_result || ""}>{STATE_LABEL[a.state] || a.state}{a.state_by ? ` (${a.state_by})` : ""}</span> : <span className="muted">—</span>}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{hidden ? <button type="button" className="secondary" disabled={!!busy} onClick={() => post(`/${a.id}/unhide`)}>Démasquer</button> : <button type="button" className="secondary" disabled={!!busy} onClick={() => post(`/${a.id}/hide`)}>Masquer</button>}</td>
                  <td style={{ whiteSpace: "nowrap" }}><button type="button" disabled={!!busy || a.state === "applied"} onClick={() => validate(a)} title={a.can_apply ? "Applique la correction sur Nebula (confirmation demandée)" : "Enregistre la validation ; l'action reste à faire à la main"}>{a.can_apply ? "Valider et appliquer" : "Valider"}</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
