// #975 : bandeau d'alertes sous l'en-tête, sur TOUTES les vues -- un seul rectangle rouge, des étiquettes courtes ; rien
// quand tout va bien. Chaque étiquette mène au détail : écran concerné ou rapport (journal) du défaut.
// - « ⛔ Agents » : événements critiques ou blocage des agents hôtes sur 24 h (remplace le bandeau verbeux de l'accueil, #422) ;
// - défauts majeurs (notify-api /defauts) : un mécanisme du SI de supervision ne fait plus son travail ; le rapport offre
//   « ignorer » (case à cocher, jusqu'à réapparition), la copie / le téléchargement du rapport à transmettre, la vue concernée.
import { useCallback, useEffect, useState } from "react";
import { hubLink } from "./hubLinks.js";
import { fetchEventsSummary } from "./siAgentClient.js";
import { bannerTone, bannerHeadline } from "./siAgent.js";
import { defautsAffiches, ignores, resume, nomFichier, etiquette } from "./defautsLib.js";

async function appel(base, token, chemin, init = {}) {
  const r = await fetch(`${base}${chemin}`, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${token}`, ...(init.body ? { "Content-Type": "application/json" } : {}) } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(j.error || `HTTP ${r.status}`); e.status = r.status; throw e; }
  return j;
}
const lienVue = (l) => (l?.view ? hubLink(l.view, Object.fromEntries(Object.entries(l).filter(([k]) => k !== "view"))) : null);

const ETIQ = { display: "inline-flex", alignItems: "center", gap: 4, background: "var(--danger)", color: "var(--bg)", border: "none", borderRadius: 4,
  padding: "2px 8px", fontSize: 12, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" };

export default function BandeauAlertes({ notifyApiBase, token, siAgentApiBase, onOuvrirAgents }) {
  const [rep, setRep] = useState(null);
  const [panne, setPanne] = useState(null);
  const [agents, setAgents] = useState(null);       // {tone, titre} | {injoignable}
  const [busy, setBusy] = useState(null);
  const [rapport, setRapport] = useState(null);     // {d, texte}
  const [copie, setCopie] = useState(false);

  const charger = useCallback(() => {
    if (notifyApiBase && token) {
      appel(notifyApiBase, token, "/defauts").then((j) => { setRep(j); setPanne(null); })
        .catch((e) => { if (e.status === 401 || e.status === 403) { setRep(null); setPanne(null); } else setPanne(e.message); });
    }
    if (siAgentApiBase) {
      fetchEventsSummary(siAgentApiBase, 24).then((s) => setAgents(s?.error ? { injoignable: true } : { tone: bannerTone(s), titre: bannerHeadline(s) })).catch(() => setAgents({ injoignable: true }));
    }
  }, [notifyApiBase, token, siAgentApiBase]);
  useEffect(() => { charger(); const t = setInterval(charger, 60000); return () => clearInterval(t); }, [charger]);

  const ignorer = async (d, oui) => {
    setBusy(d.id);
    try {
      await appel(notifyApiBase, token, `/defauts/${d.id}/ignorer`, { method: "POST", body: JSON.stringify({ ignorer: oui }) });
      setRapport((r) => (r && r.d.id === d.id ? { ...r, d: { ...r.d, ignore: oui } } : r));
      charger();
    } catch (e) { setPanne(e.message); }
    finally { setBusy(null); }
  };
  const ouvrir = async (d) => {
    setCopie(false);
    if (d.interne || d.panne) { setRapport({ d, texte: `DÉFAUT MAJEUR — ${d.titre}\n\n${d.message}` }); return; }
    setRapport({ d, texte: null });
    try { const j = await appel(notifyApiBase, token, `/defauts/${d.id}/rapport`); setRapport({ d, texte: j.texte }); }
    catch (e) { setRapport({ d, texte: `Rapport indisponible : ${e.message}` }); }
  };
  const copier = async () => { try { await navigator.clipboard.writeText(rapport.texte || ""); setCopie(true); } catch { setCopie(false); } };
  const telecharger = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([rapport.texte || ""], { type: "text/plain;charset=utf-8" }));
    a.download = nomFichier(rapport.d);
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  const ds = defautsAffiches(rep);
  if (panne) ds.unshift({ id: "panne", panne: true, code: "notify.injoignable", titre: "Défauts majeurs invisibles : notify-api ne répond pas",
    message: `notify-api ne répond pas (${panne}). Vérifier le service notify-api (docker ps) et VITE_NOTIFY_API_BASE_URL dans le .env, puis reconstruire le hub.` });
  const ign = ignores(rep?.defauts);
  const agentsRouge = agents && (agents.tone === "bad" || agents.injoignable);
  if (!ds.length && !agentsRouge && !rapport) return null;

  const lv = rapport && lienVue(rapport.d.lien);
  return (
    <>
    {(ds.length > 0 || agentsRouge) && (
    <div role="alert" style={{ flex: "0 0 auto", margin: "4px 12px", padding: "4px 8px", border: "1px solid var(--danger)", background: "var(--danger-bg)", borderRadius: 6,
      display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
      {agentsRouge && (
        <button type="button" style={ETIQ} onClick={onOuvrirAgents} title={agents.injoignable ? "Agents hôtes : central injoignable" : agents.titre}>⛔ Agents</button>
      )}
      {ds.map((d) => (
        <button key={d.id} type="button" style={ETIQ} onClick={() => ouvrir(d)} title={`${d.titre}${d.occurrences ? ` — ${resume(d)}` : ""} · clic : détail et journal`}>
          ⛔ {etiquette(d)}{d.occurrences > 1 ? <span style={{ fontWeight: 400 }}> ×{d.occurrences}</span> : null}
        </button>
      ))}
      {ign.length > 0 && (ds.length > 0 || agentsRouge) && (
        <span className="muted" style={{ fontSize: 11, marginLeft: "auto" }} title={ign.map((d) => d.titre).join("\n")}>
          {ign.length} ignoré{ign.length > 1 ? "s" : ""} :{" "}
          {ign.map((d) => <button key={d.id} type="button" className="secondary" style={{ fontSize: 11, padding: "0 6px", marginLeft: 4 }} onClick={() => ouvrir(d)}>{etiquette(d)}</button>)}
        </span>
      )}
    </div>
    )}

      {rapport && (
        <div role="dialog" aria-label="détail du défaut" onClick={() => setRapport(null)}
          style={{ position: "fixed", inset: 0, background: "var(--bg)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
          <div className="panel" onClick={(e) => e.stopPropagation()} style={{ width: "min(900px, 100%)", maxHeight: "90vh", display: "flex", flexDirection: "column", gap: 8, border: "1px solid var(--danger)" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <h3 style={{ margin: 0, flex: 1 }}>⛔ {rapport.d.titre}</h3>
              {!rapport.d.interne && !rapport.d.panne && (
                <label title="Masquer jusqu'à ce que le défaut réapparaisse après avoir été corrigé" style={{ whiteSpace: "nowrap" }}>
                  <input type="checkbox" checked={!!rapport.d.ignore} disabled={busy === rapport.d.id} onChange={(e) => ignorer(rapport.d, e.target.checked)} /> {busy === rapport.d.id ? "⏳" : "ignorer"}
                </label>
              )}
              <button type="button" onClick={copier} disabled={!rapport.texte}>{copie ? "✓ copié" : "📋 Copier le rapport"}</button>
              <button type="button" className="secondary" onClick={telecharger} disabled={!rapport.texte}>⬇ .txt</button>
              {lv && <a className="button secondary" href={lv}>ouvrir la vue</a>}
              <button type="button" className="secondary" onClick={() => setRapport(null)} aria-label="fermer">✕</button>
            </div>
            <p className="muted" style={{ margin: 0 }}>{rapport.d.occurrences ? `${resume(rapport.d)} · ` : ""}Pour le faire corriger : « Copier le rapport » puis le coller dans la conversation avec Claude.</p>
            <pre style={{ margin: 0, overflow: "auto", flex: 1, whiteSpace: "pre-wrap", userSelect: "text", background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 6, padding: 8, fontSize: 12 }}>
              {rapport.texte ?? "⏳ chargement du rapport…"}
            </pre>
          </div>
        </div>
      )}
    </>
  );
}
