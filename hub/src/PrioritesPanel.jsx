// Page d'accueil du hub (#818) : « Priorités » -- 1. le modèle local prépare la liste détaillée de ce qui est ouvert
// (événements des agents non résolus, veille qui touche notre SI), 2. le décideur classe urgent / non urgent et garde
// les 5 plus urgents, 3. le modèle conversationnel détaille ces urgences et les solutions. Chaque urgence porte le
// lien vers l'écran où agir (règle absolue #817). Données : si-agent-api /priorites (gardé 15 min, « Recalculer »).
import { useCallback, useEffect, useState } from "react";
import { hubLink } from "./hubLinks.js";

const pct = (v) => (v == null ? "—" : `${Math.round(v * 100)} %`);
const quand = (t) => (t ? new Date(t * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "");

export default function PrioritesPanel({ siAgentApiBase }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [ouvert, setOuvert] = useState(() => { try { return localStorage.getItem("priorites.ouvert") !== "0"; } catch { return true; } });
  const [autres, setAutres] = useState(false);
  const charger = useCallback((refresh) => fetch(`${siAgentApiBase}/priorites${refresh ? "?refresh=1" : ""}`, { credentials: "include" })
    .then((r) => r.json()).then((x) => { setD(x); setErr(x?.error || null); }).catch((e) => setErr(e.message)), [siAgentApiBase]);
  useEffect(() => { charger(false); const t = setInterval(() => charger(false), 60000); return () => clearInterval(t); }, [charger]);
  useEffect(() => { try { localStorage.setItem("priorites.ouvert", ouvert ? "1" : "0"); } catch { /* navigation privée */ } }, [ouvert]);
  if (!siAgentApiBase) return null;
  const urg = d?.urgences || [];
  return (
    <section className="priorites">
      <div className="priorites-tete">
        <button type="button" className="secondary" onClick={() => setOuvert(!ouvert)}>{ouvert ? "▾" : "▸"} Priorités</button>
        <b className={urg.length ? "priorites-n" : ""}>{d ? (urg.length ? `${urg.length} urgence(s)` : "aucune urgence") : "…"}</b>
        <span className="infra-muted">{d?.nb != null ? `${d.nb} élément(s) ouverts examinés` : ""}{d?.calcule_le ? ` · calculé à ${quand(d.calcule_le)}` : ""}{d?.duree_s ? ` en ${d.duree_s} s` : ""}{d?.en_cours ? " · calcul en cours…" : ""}</span>
        <button type="button" className="secondary" disabled={d?.en_cours} onClick={() => charger(true)}>Recalculer</button>
      </div>
      {ouvert && <>
        {(err || d?.erreur) && <p className="infra-error">{err || d.erreur}</p>}
        {urg.length > 0 && (
          <ol className="priorites-liste">
            {urg.map((u) => (
              <li key={u.id} className={u.gravite === "critique" ? "critique" : u.gravite === "haute" ? "haute" : ""}>
                <div><b>{u.titre}</b> <span className="infra-muted">· {u.source} · urgence {pct(u.urgence)} · gravité {u.gravite}{u.nb > 1 ? ` · ${u.nb} fois` : ""}</span></div>
                {u.detail && <div>{u.detail}</div>}
                {u.impact && <div className="infra-muted">Impact : {u.impact}</div>}
                {u.lien && <a href={hubLink(u.lien.view, u.lien.params)}>Agir : ouvrir l'écran →</a>}
              </li>
            ))}
          </ol>
        )}
        {d?.explication && <details className="priorites-ia" open><summary>Détail des urgences et solutions proposées (IA)</summary><pre>{d.explication}</pre></details>}
        {(d?.autres || []).length > 0 && (
          <details open={autres} onToggle={(e) => setAutres(e.target.open)}><summary className="infra-muted">{d.autres.length} autre(s) élément(s), non urgents</summary>
            <ul className="priorites-autres">{d.autres.map((u) => <li key={u.id}>{u.titre} <span className="infra-muted">· {u.source} · urgence {pct(u.urgence)}</span>{u.lien && <> · <a href={hubLink(u.lien.view, u.lien.params)}>écran →</a></>}</li>)}</ul>
          </details>
        )}
        {d?.etapes && <p className="infra-muted priorites-etapes">1. préparation : {d.etapes.preparation || "—"} · 2. décision : {d.etapes.decision || "—"} · 3. explication : {d.etapes.explication || "—"}</p>}
        {d?.etapes && <p className="infra-muted priorites-etapes">modèles : {d.modeles && Object.keys(d.modeles).length
          ? Object.entries(d.modeles).map(([u, m]) => `${u} ${m}`).join(" · ") + " (Parc IA › Veille des modèles › Usages)"
          : <>réglage du .env — pour choisir par usage : <a href={hubLink("iapark", { tab: "modeles", onglet: "mes" })}>Parc IA › Veille des modèles › Usages</a> et PRIORITES_LLM_HOTE dans le .env (pas de lien : opération manuelle)</>}</p>}
      </>}
    </section>
  );
}
