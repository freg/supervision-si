// #830 : pied de page PERMANENT du hub -- livraison chargée dans ce navigateur et livraison servie, mise à jour en cours
// (annoncée par scripts/run.sh pendant la construction et le redémarrage), rechargement SANS CACHE quand une
// nouvelle livraison est servie (15 s, « Recharger maintenant » / « Plus tard », bouton ↻ permanent), et ce qui
// travaille : IA (priorités, essais de skills, évaluations), sources consultées (veille des modèles, veille cyber).
import { useCallback, useEffect, useState } from "react";

const ICONE = { ia: "🧠", source: "📡" };
const duree = (s) => (s < 60 ? `${s} s` : `${Math.floor(s / 60)} min${s % 60 ? ` ${s % 60} s` : ""}`);
const depuis = (t) => { if (!t) return "jamais"; const s = Math.max(0, Date.now() / 1000 - t); return s < 60 ? `${Math.round(s)} s` : s < 3600 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`; };
const num = (n) => { const x = parseInt(String(n ?? "").replace(/\D/g, ""), 10); return Number.isFinite(x) ? x : null; };

export async function rechargerSansCache(v) {
  try { await fetch("/index.html", { cache: "reload" }); } catch { /* hors ligne : on recharge quand même */ }
  const u = new URL(window.location.href);
  u.searchParams.set("v", String(v || Date.now()));
  window.location.replace(u.toString());
}
export function nettoyerAdresse() {
  try { const u = new URL(window.location.href); if (u.searchParams.has("v")) { u.searchParams.delete("v"); window.history.replaceState(null, "", u.toString()); } } catch { /* rien */ }
}

async function lire(url) {
  const r = await fetch(url, { credentials: "include", cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export default function BarreEtatHub({ charge, servicesBase, siAgentBase, vulnBase }) {
  const [srv, setSrv] = useState(null);
  const [hs, setHs] = useState(false);
  const [vuMaj, setVuMaj] = useState(null);
  const [act, setAct] = useState(null);
  const [veille, setVeille] = useState(null);
  const [ouvert, setOuvert] = useState(false);
  const [plusTard, setPlusTard] = useState(null);
  const [compte, setCompte] = useState(null);
  const rapide = useCallback(() => {
    if (servicesBase) lire(`${servicesBase}/version-hub`).then((x) => { setSrv(x); setHs(false); if (x.maj) setVuMaj(x.maj); else if (x.delivery_number) setVuMaj(null); }).catch(() => setHs(true));
    if (siAgentBase) lire(`${siAgentBase}/etat-hub`).then(setAct).catch(() => setAct(null));
  }, [servicesBase, siAgentBase]);
  const lent = useCallback(() => { if (vulnBase) lire(`${vulnBase}/veille/etat`).then(setVeille).catch(() => setVeille(null)); }, [vulnBase]);
  useEffect(() => { rapide(); lent(); const a = setInterval(rapide, 5000); const b = setInterval(lent, 60000); return () => { clearInterval(a); clearInterval(b); }; }, [rapide, lent]);
  const servie = num(srv?.delivery_number);
  const nouvelle = servie && num(charge) && servie > num(charge) && !srv?.maj ? servie : null;
  useEffect(() => {
    if (!nouvelle || plusTard === nouvelle) { setCompte(null); return undefined; }
    setCompte(15);
    const t = setInterval(() => setCompte((c) => { if (c <= 1) { clearInterval(t); rechargerSansCache(nouvelle); return 0; } return c - 1; }), 1000);
    return () => clearInterval(t);
  }, [nouvelle, plusTard]);
  const enCours = act?.en_cours || [];
  const m = srv?.maj;
  return (
    <div className={`barre-etat-hub${ouvert ? " ouverte" : ""}`}>
      {m && <div className="barre-maj">⟳ mise à jour en cours{m.numero ? ` vers #${m.numero}` : ""} : {m.sujet || ""} — <b>{m.etape}</b>
        <span className="infra-muted"> · depuis {duree(Math.max(0, Math.round(Date.now() / 1000 - (m.debut || 0))))}{m.commande ? ` · run.sh ${m.commande}` : ""}</span></div>}
      {hs && vuMaj && <div className="barre-maj">⟳ redémarrage des services ({vuMaj.etape}) — reconnexion automatique…</div>}
      {nouvelle && plusTard !== nouvelle && <div className="barre-maj nouvelle">✔ nouvelle livraison #{nouvelle} servie (cet écran : #{charge}) — rechargement sans cache dans {compte ?? 15} s{" "}
        <button type="button" onClick={() => rechargerSansCache(nouvelle)}>Recharger maintenant</button>{" "}
        <button type="button" className="secondary" onClick={() => setPlusTard(nouvelle)}>Plus tard</button></div>}
      <div className="barre-ligne" onClick={() => setOuvert(!ouvert)} title="cliquer : derniers travaux">
        <b title={srv ? `servi : #${srv.delivery_number || "?"} (${srv.git_hash || "?"})` : ""}>Hub supervision #{charge || "?"}</b>
        {servie && servie !== num(charge) && <span className="infra-muted">(servi : #{servie})</span>}
        {hs && !vuMaj && <span className="infra-status critical">services-api injoignable</span>}
        {enCours.map((x) => <span key={x.id} className="barre-tache actif">{ICONE[x.genre] || "⚙"} {x.detail} <span className="infra-muted">{duree(x.depuis_s)}</span></span>)}
        {act && !enCours.length && <span className="infra-muted">aucun travail d'IA en cours</span>}
        <span style={{ flex: 1 }} />
        {veille?.derniere_releve && <span className="infra-muted">veille cyber relevée il y a {depuis(veille.derniere_releve)}{veille.sources_en_erreur ? ` · ${veille.sources_en_erreur} source(s) en erreur` : ""}</span>}
        <button type="button" className="secondary" title="recharger l'interface sans cache (dernière livraison servie)" onClick={(e) => { e.stopPropagation(); rechargerSansCache(servie || charge); }}>↻</button>
      </div>
      {ouvert && <ul className="barre-recentes">
        {(act?.recentes || []).map((x) => <li key={x.id}><span className={x.ok ? "infra-status good" : "infra-status critical"}>{x.ok ? "✔" : "✗"}</span> {ICONE[x.genre] || "⚙"} {x.detail}
          <span className="infra-muted"> · {duree(Math.round(x.duree_s))} · il y a {depuis(x.fin)}{x.erreur ? ` · ${x.erreur}` : ""}</span></li>)}
        {!(act?.recentes || []).length && <li className="infra-muted">aucun travail terminé récemment</li>}
      </ul>}
    </div>
  );
}
