// « Services du hub » (livraison #584) -- sous-tuile de Paramétrage :
// feu tricolore de toutes les API / fronts / bases du projet et
// redémarrage, via services-api (jeton Keycloak vérifié, utilisateurs
// SERVICES_ADMIN_USERS). Demandé : « une sous-tuile dans paramétrage pour
// redémarrer et vérifier toutes les api/front avec un joli feu tricolore ».
// Règles d'ergonomie : cadre fixe, en-tête de tableau figé, contenu qui
// défile, filtre « début de mot d'abord ».
import { useCallback, useEffect, useMemo, useState } from "react";
import PageFrame from "./PageFrame.jsx";
import { hubLink } from "./hubLinks.js";
import { fetchServices, restartService, restartRed, fetchServiceLogs, rebuildService } from "./servicesClient.js";
import { sortServices, filterServices, summarize, verdictText, uptimeText, LIGHT_LABEL, KIND_LABEL } from "./servicesLights.js";

const REFRESH_MS = 30000;
const COLORS = { red: "#e53935", orange: "#fb8c00", green: "#43a047", grey: "#9e9e9e" };

/** Feu tricolore : trois lampes, chacune allumée si des services sont dans cet état, avec le compte. */
export function TrafficLight({ summary, size = 42 }) {
  const c = summary?.counts || {};
  const lamp = (color, n, label) => {
    const on = n > 0;
    return (
      <div key={color} title={`${n} ${label}`} style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: size, height: size, borderRadius: "50%", background: on ? COLORS[color] : "#2b2b2b", border: "2px solid #111",
          boxShadow: on ? `0 0 ${size / 2}px ${COLORS[color]}` : "inset 0 0 6px #000", display: "flex", alignItems: "center", justifyContent: "center",
          color: on ? "#111" : "#555", fontWeight: 700, fontSize: size / 2.6, transition: "background .3s, box-shadow .3s" }}>{n || ""}</div>
        <span style={{ color: on ? COLORS[color] : "var(--muted)", fontWeight: on ? 600 : 400 }}>{label}</span>
      </div>
    );
  };
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", gap: 8, padding: 12, borderRadius: 14, background: "#1a1a1a", border: "3px solid #333", boxShadow: "0 4px 12px rgba(0,0,0,.4)" }}>
      {lamp("red", c.red || 0, "en panne")}
      {lamp("orange", c.orange || 0, "à surveiller")}
      {lamp("green", c.green || 0, "en marche")}
    </div>
  );
}

function Lamp({ light, title }) {
  return <span title={title} style={{ display: "inline-block", width: 14, height: 14, borderRadius: "50%", background: COLORS[light] || COLORS.grey, boxShadow: `0 0 6px ${COLORS[light] || COLORS.grey}`, verticalAlign: "middle" }} />;
}

/** #586 : cadre allégé quand la vue est un onglet de la tour de contrôle. */
function Embedded({ actions, foot, children }) {
  return (
    <div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginBottom: 8 }}>{actions}</div>
      {children}
      <p className="muted" style={{ fontSize: 12 }}>{foot}</p>
    </div>
  );
}

export default function ServicesView({ apiBase, accessToken, username, onBack, embedded = false, onJob }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [onlyProblems, setOnlyProblems] = useState(false);
  const [busy, setBusy] = useState(null);
  const [notice, setNotice] = useState(null);
  const [logs, setLogs] = useState(null);
  const [now, setNow] = useState(Date.now());

  const load = useCallback(async (refresh = false) => {
    if (!apiBase || !accessToken) return;
    setLoading(true);
    const r = await fetchServices(apiBase, accessToken, refresh);
    setLoading(false);
    if (r.error) { setError(r.error); return; }
    setError(null);
    setData(r);
    setNow(Date.now());
  }, [apiBase, accessToken]);

  useEffect(() => { load(); const id = setInterval(() => load(), REFRESH_MS); return () => clearInterval(id); }, [load]);

  const rows = useMemo(() => sortServices(data?.services), [data]);
  const shown = useMemo(() => filterServices(rows, query, onlyProblems), [rows, query, onlyProblems]);
  const summary = useMemo(() => summarize(rows), [rows]);

  const act = async (label, fn) => {
    setBusy(label);
    const r = await fn();
    setBusy(null);
    if (!r?.error && r?.id && r?.steps) { setNotice(`${label} : job ${r.id} lancé`); onJob?.(r); return; }  // #586 : reconstruction = job de la tour
    setNotice(r?.error ? `${label} : ${r.error}` : `${label} : ${r.action === "start" ? "démarré" : r.restarted ? `${r.restarted.length} redémarré(s)${r.skipped_protected?.length ? `, protégés ignorés : ${r.skipped_protected.join(", ")}` : ""}` : "redémarré"} — nouvelle vérification dans quelques secondes`);
    setTimeout(() => load(true), 4000);
  };

  const showLogs = async (service) => {
    const r = await fetchServiceLogs(apiBase, accessToken, service, 120);
    setLogs(r.error ? { service, lines: [r.error] } : r);
  };

  const Frame = embedded ? Embedded : PageFrame;
  if (!apiBase) return <PageFrame title="🚦 Services du hub" onBack={onBack}><p className="muted">services-api non configurée (<code>VITE_SERVICES_API_BASE_URL</code>).</p></PageFrame>;

  const redCount = summary.counts.red;
  const actions = (
    <>
      <button type="button" className="secondary" disabled={loading} onClick={() => load(true)}>{loading ? "Vérification…" : "↻ Tout vérifier"}</button>
      <button type="button" className="secondary" disabled={!redCount || !!busy} title={redCount ? "redémarre chaque service rouge (sauf passerelle, Keycloak, hub, services-api)" : "aucun service en panne"}
        onClick={() => window.confirm(`Redémarrer les ${redCount} service(s) en panne ?`) && act("Redémarrage des rouges", () => restartRed(apiBase, accessToken))}>⟳ Redémarrer les rouges{redCount ? ` (${redCount})` : ""}</button>
    </>
  );

  return (
    <Frame title="🚦 Services du hub" onBack={onBack} actions={actions}
      foot={<span>{data ? `${data.project} · ${summary.total} conteneurs · vérifié ${new Date((data.at || 0) * 1000).toLocaleTimeString()} (cache ${data.cache_seconds} s, rafraîchi toutes les ${REFRESH_MS / 1000} s)` : "—"} · connecté en tant que {username || "?"}{notice ? ` · ${notice}` : ""}</span>}>
      {error && <p className="hub-error">{error}{/utilisateur|autoris/i.test(error) ? <> — droits : membre d'un groupe admis (<a href={hubLink("accounts")}>Comptes et groupes</a>, groupe <code>administrateurs</code> par défaut) ou <code>SERVICES_ADMIN_USERS</code> / <code>SERVICES_ADMIN_GROUPS</code> dans le <code>.env</code> du hub.</> : null}</p>}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap", marginBottom: 12 }}>
        <TrafficLight summary={summary} />
        <div style={{ flex: 1, minWidth: 260 }}>
          <h2 style={{ margin: "0 0 4px", color: COLORS[summary.verdict] }}>{verdictText(summary)}</h2>
          <p className="muted" style={{ margin: "0 0 10px" }}>
            Chaque conteneur du projet : état Docker, healthcheck s'il existe, puis requête HTTP interne (<code>/health</code> ou <code>/</code>) sur son port.
            Vert = joignable ; orange = lent, dégradé ou en démarrage ; rouge = arrêté, en erreur ou injoignable.
            « Redémarrer » relance le conteneur (démarre s'il est arrêté) ; la passerelle, Keycloak, le hub et cette API sont protégés du redémarrage groupé.
          </p>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input type="search" placeholder="filtrer (nom, rôle, état)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 240 }} />
            <label className="muted"><input type="checkbox" checked={onlyProblems} onChange={(e) => setOnlyProblems(e.target.checked)} /> problèmes seulement</label>
            <span className="muted">{shown.length} / {rows.length}</span>
          </div>
        </div>
      </div>
      <table className="hub-table">
        <thead><tr><th></th><th>Service</th><th>Rôle</th><th>Conteneur</th><th>Depuis</th><th>Vérification</th><th></th></tr></thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.service}>
              <td><Lamp light={r.light} title={LIGHT_LABEL[r.light]} /></td>
              <td><strong>{r.service}</strong>{r.protected && <span className="muted" title="protégé du redémarrage groupé"> 🔒</span>}</td>
              <td className="muted">{KIND_LABEL[r.kind] || r.kind}{r.port ? ` :${r.port}` : ""}</td>
              <td>{r.status}{r.docker_health ? ` (${r.docker_health})` : ""}{r.restart_count ? <span className="muted"> · {r.restart_count} redémarrage(s)</span> : null}</td>
              <td className="muted">{uptimeText(r.started_at, now)}</td>
              <td style={{ color: COLORS[r.light] }}>{r.text}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                <button type="button" className="secondary" disabled={!!busy} onClick={() => (r.protected ? window.confirm(`« ${r.service} » porte le hub ou son entrée : le redémarrer coupe la session en cours. Continuer ?`) : true) && act(`Redémarrage de ${r.service}`, () => restartService(apiBase, accessToken, r.service))}>{r.status === "running" ? "Redémarrer" : "Démarrer"}</button>
                {" "}<button type="button" className="secondary" disabled={!!busy || (/-gateway$/.test(r.project || "") && r.service !== "tls-proxy")} title="reconstruire l'image et relancer (job de la tour, journal dans « Livraisons & jobs »)"
                  onClick={() => window.confirm(`Reconstruire « ${r.service} » (build + relance) ?`) && act(`Reconstruction de ${r.service}`, () => rebuildService(apiBase, accessToken, r.service))}>Reconstruire</button>
                {" "}<button type="button" className="secondary" onClick={() => showLogs(r.service)}>Journal</button>
              </td>
            </tr>
          ))}
          {!shown.length && <tr><td colSpan={7} className="muted">{data ? "aucun service ne correspond" : loading ? "Vérification…" : "—"}</td></tr>}
        </tbody>
      </table>
      {logs && (
        <div className="hub-card" style={{ marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}><h3 style={{ margin: 0 }}>Journal de {logs.service} ({logs.lines?.length || 0} lignes)</h3><span style={{ flex: 1 }} /><button type="button" className="secondary" onClick={() => setLogs(null)}>Fermer</button></div>
          <pre style={{ maxHeight: 320, overflow: "auto", fontSize: 12, margin: "8px 0 0" }}>{(logs.lines || []).join("\n")}</pre>
        </div>
      )}
    </Frame>
  );
}
