// #988 : Hermes, atelier de codage et apprentissage des nœuds IA (prodia, preprodia) -- même service que les tuiles du
// hub maison (hermes-web), servi par le nœud et ouvert ici sous /ia/<nœud>/ au seul groupe Keycloak « ia ».
// La passerelle contrôle chaque requête (services-api /ia/acces) ; le hub pose son jeton dans un cookie limité à /ia/.
import { useEffect, useState } from "react";
import { hubLink } from "./hubLinks.js";
import IaDeploiement from "./IaDeploiement.jsx";   // #996
import { PAGES_IA, cheminNoeud, noeudRetenu, pageDeVue, diagnosticNoeud } from "./iaNoeudsLib.js";

const MEMO = "hub.ia.noeud";
const lireMemo = () => { try { return localStorage.getItem(MEMO) || ""; } catch { return ""; } };
const ecrireMemo = (n) => { try { localStorage.setItem(MEMO, n); } catch { /* stockage indisponible */ } };

export default function IaNoeudView({ onBack, servicesApiBase, siAgentApiBase, admin = false, username, vue = "hermes" }) {
  const [page, setPage] = useState(pageDeVue(vue));
  const [rep, setRep] = useState(null);
  const [noeud, setNoeud] = useState("");
  const [haut, setHaut] = useState(() => Math.max(420, window.innerHeight - 190));
  const [deployer, setDeployer] = useState(false);
  const [rev, setRev] = useState(0);
  useEffect(() => { setPage(pageDeVue(vue)); }, [vue]);
  useEffect(() => {
    const f = () => setHaut(Math.max(420, window.innerHeight - 190));
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);
  useEffect(() => {
    fetch(`${servicesApiBase}/ia/noeuds`, { credentials: "include" })
      .then(async (r) => { const j = await r.json().catch(() => ({})); setRep(r.ok ? j : { erreur: j.error || `${r.status}`, statut: r.status, groupes: j.groupes }); })
      .catch((e) => setRep({ erreur: e.message }));
  }, [servicesApiBase, rev]);
  useEffect(() => { if (rep?.noeuds) setNoeud(noeudRetenu(rep.noeuds, lireMemo()) || ""); }, [rep]);
  // #998 : le nœud est-il servi par la passerelle ? (sinon /ia/<nœud>/ retombe sur le hub : réponse HTML, pas JSON)
  const [servi, setServi] = useState(null);
  useEffect(() => {
    if (!noeud) return;
    setServi(null);
    fetch(`${cheminNoeud(noeud, "api/version")}`, { credentials: "include" })
      .then((r) => setServi(diagnosticNoeud(r.status, r.headers.get("content-type"))))
      .catch((e) => setServi({ ok: false, texte: `injoignable : ${e.message}` }));
  }, [noeud, rev]);

  const choisir = (n) => { setNoeud(n); ecrireMemo(n); };
  const base = noeud ? cheminNoeud(noeud, "").replace(/\/$/, "") : "";
  const src = noeud ? cheminNoeud(noeud, page) : null;
  const titre = (PAGES_IA.find((p) => p.id === page) || PAGES_IA[0]).label;

  return (
    <section className="view">
      <header className="view-header" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <h1 style={{ margin: 0 }}>🤖 {titre}</h1>
        {PAGES_IA.map((p) => (
          <button key={p.vue} type="button" className={p.id === page ? "" : "secondary"} title={p.detail} onClick={() => setPage(p.id)}>{p.label}</button>
        ))}
        {rep?.noeuds?.length > 0 && (
          <label style={{ marginLeft: "auto" }}>nœud{" "}
            <select value={noeud} onChange={(e) => choisir(e.target.value)} aria-label="nœud IA">
              {rep.noeuds.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        )}
        {admin && siAgentApiBase && <button type="button" className={deployer ? "" : "secondary"} onClick={() => setDeployer((x) => !x)}>🚀 Déployer…</button>}
        {base && <>
          <a href={src} target="_blank" rel="noreferrer">plein écran ↗</a>
          <a href={`${base}/mobile`} target="_blank" rel="noreferrer">📱 mobile ↗</a>
          <a href={`${base}/api/export`} target="_blank" rel="noreferrer">📄 export ↗</a>
        </>}
      </header>

      {(deployer || (admin && siAgentApiBase && rep?.noeuds?.length === 0)) && (
        <IaDeploiement siAgentApiBase={siAgentApiBase} servicesApiBase={servicesApiBase} username={username} onDeclare={() => setRev((x) => x + 1)} />
      )}
      {!rep && <p className="muted">⏳ nœuds IA…</p>}
      {rep?.erreur && rep.statut === 403 && (
        <p className="error">Accès réservé au groupe Keycloak « ia » ({rep.erreur}). Réglage : <a href={hubLink("accounts")}>Comptes et groupes</a> → ajouter la personne au groupe <strong>ia</strong>, puis se reconnecter.</p>
      )}
      {rep?.erreur && rep.statut === 401 && <p className="error">Session expirée ({rep.erreur}) : se reconnecter au hub.</p>}
      {rep?.erreur && ![401, 403].includes(rep.statut) && (
        <p className="error">Nœuds IA indisponibles : {rep.erreur} (services-api). <a href={hubLink("settings")}>Paramètres (feu tricolore des services)</a></p>
      )}
      {rep?.noeuds && rep.noeuds.length === 0 && (
        <p className="error">Aucun nœud IA déclaré. {admin ? "Le déployer ci-dessus (🚀 Déployer…)." : "Un administrateur le déploie depuis cette tuile (🚀 Déployer…)."}</p>
      )}
      {src && servi && !servi.ok && (
        <p className="error">Nœud {noeud} : {servi.texte} — <a href={hubLink("services", { tab: "deliveries" })}>Tour › Livraisons &amp; jobs</a> (job « nœud IA … : déclaration dans la passerelle »).</p>
      )}
      {src && servi === null && <p className="muted">⏳ vérification du nœud {noeud}…</p>}
      {src && servi?.ok && (
        <iframe key={src} title={`${titre} — ${noeud}`} src={src}
          style={{ width: "100%", height: haut, border: "1px solid var(--border)", borderRadius: 8, background: "var(--panel)" }} />
      )}
    </section>
  );
}
