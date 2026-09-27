// Tuile « Données personnelles » (livraison #638) : journal de nos interactions
// de travail (frise catégorisée + comptes-rendus par période, depuis le CHANGELOG
// servi par accounts-api /interactions), et accès au hub (journal de connexions
// Keycloak, accounts-api /events). Réservée aux administrateurs. Aucune donnée
// inventée ni confidentielle client : seulement le CHANGELOG public du projet et
// les connexions au hub. Les durées de conversation ne sont pas journalisées :
// « minutes » = comptes-rendus.
import { useEffect, useState } from "react";
import LoginEventsTab from "./LoginEventsTab.jsx";

async function call(url) {
  const r = await fetch(url, { credentials: "include" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

const CAT_ICON = {
  "Sécurité & accès": "🛡", "IA": "🧠", "Réseau & infra": "🌐",
  "Agent & postes": "🖥", "Hub & ergonomie": "🎛", "Exploitation": "🔧", "Autre": "•",
};

export default function PersonalDataView({ apiBase, me, onBack }) {
  const [tab, setTab] = useState("frise");
  const [by, setBy] = useState("week");
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const p = new URLSearchParams();
    if (cat) p.set("category", cat);
    if (q) p.set("q", q);
    p.set("by", by);
    call(`${apiBase}/interactions?${p}`).then(setData).catch((e) => setErr(e.message));
  }, [apiBase, cat, q, by]);

  return (
    <div className="hub-fill-column">
      <div className="hub-card">
        <button type="button" className="secondary" onClick={onBack}>← retour</button>
        <h1>Données personnelles</h1>
        <p className="muted">Historique de nos interactions de travail (depuis le CHANGELOG du projet) et accès au hub. « Minutes » = comptes-rendus, pas de durée (non journalisée).</p>
        <div className="tabs" style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "8px 0" }}>
          {[["frise", "Frise des interactions"], ["minutes", "Comptes-rendus"], ["acces", "Accès au hub"]].map(([id, label]) => (
            <button key={id} type="button" className={tab === id ? "" : "secondary"} onClick={() => setTab(id)}>{label}</button>
          ))}
        </div>
      </div>

      {tab !== "acces" && err && <div className="hub-card"><p className="hub-error">{err}</p></div>}

      {tab === "frise" && data && (
        <div className="hub-card hub-fill-scroll">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
            <input placeholder="Rechercher…" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 200 }} />
            <select value={cat} onChange={(e) => setCat(e.target.value)}>
              <option value="">toutes catégories</option>
              {(data.categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <span className="muted">{data.total} interaction(s){data.span ? ` · du ${data.span.from} au ${data.span.to}` : ""}</span>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
            {Object.entries(data.by_category || {}).map(([c, n]) => (
              <span key={c} className="pill" style={{ cursor: "pointer" }} onClick={() => setCat(cat === c ? "" : c)}>{CAT_ICON[c] || "•"} {c} : {n}</span>
            ))}
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr><th>date</th><th>#</th><th>catégorie</th><th>interaction</th></tr></thead>
            <tbody>
              {(data.entries || []).map((e, i) => (
                <tr key={`${e.delivery}-${i}`} style={{ borderTop: "1px solid var(--line)" }}>
                  <td style={{ whiteSpace: "nowrap" }}>{e.date}</td>
                  <td className="muted">{e.delivery ? `#${e.delivery}` : "—"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{CAT_ICON[e.category] || "•"} {e.category}</td>
                  <td><strong>{e.title}</strong>{e.summary && <div className="muted" style={{ fontSize: 12 }}>{e.summary}</div>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "minutes" && data && (
        <div className="hub-card hub-fill-scroll">
          <div style={{ marginBottom: 8 }}>
            <span className="muted">Regrouper par : </span>
            {[["day", "jour"], ["week", "semaine"], ["month", "mois"]].map(([id, label]) => (
              <button key={id} type="button" className={by === id ? "" : "secondary"} style={{ marginRight: 4 }} onClick={() => setBy(id)}>{label}</button>
            ))}
          </div>
          {(data.minutes || []).map((m) => (
            <div key={m.period} style={{ borderTop: "1px solid var(--line)", padding: "8px 0" }}>
              <div><strong>{m.period}</strong> <span className="muted">— {m.count} interaction(s){m.deliveries.length ? ` · #${m.deliveries[0]}–#${m.deliveries[m.deliveries.length - 1]}` : ""}</span></div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "4px 0" }}>
                {Object.entries(m.categories).map(([c, n]) => <span key={c} className="pill">{CAT_ICON[c] || "•"} {c} : {n}</span>)}
              </div>
              <div className="muted" style={{ fontSize: 13 }}>{m.summary}</div>
            </div>
          ))}
          {(data.minutes || []).length === 0 && <p className="muted">Aucune interaction sur la période.</p>}
        </div>
      )}

      {tab === "acces" && (
        <div className="hub-card hub-fill-scroll">
          {notice && <p className="muted">{notice}</p>}
          <LoginEventsTab apiBase={apiBase} me={me} notice={(t) => { setErr(""); setNotice(t); }} error={(t) => { setNotice(""); setErr(t); }} />
        </div>
      )}
    </div>
  );
}
