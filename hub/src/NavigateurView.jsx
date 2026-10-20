// Tuile « Navigateur des hôtes » (livraison #798) : un Chromium visible qui tourne SUR l'hôte d'un agent Linux (en priorité
// une VM OVH : nos services vus de l'extérieur), et non dans le navigateur qui consulte le hub. Écran web (noVNC publié
// par le bastion, servi par tls-proxy sous /navigateur/<nom>/) pour le voir et l'utiliser ; automate Playwright local
// (commande « navigateur » de l'agent) pour ouvrir une adresse, capturer, jouer un parcours au format QA -- l'automate
// travaille dans le même navigateur, on le voit faire et on peut reprendre la main. Logique pure : navigateurLib.js.
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchNavigateurs, saveNavigateurs, navCommand, fetchCommand, fetchFleet } from "./siAgentClient.js";
import { ecranUrl, EXEMPLE_ETAPES, lireEtapes, etatCommande, imageDe, trierNavigateurs } from "./navigateurLib.js";

function Registre({ api, liste, username, recharger }) {
  const [ouvert, setOuvert] = useState(false);
  const [agents, setAgents] = useState([]);
  const [f, setF] = useState({ nom: "", agent_id: "", libelle: "", accueil: "" });
  const [msg, setMsg] = useState(null);
  useEffect(() => { if (ouvert) fetchFleet(api).then((a) => setAgents(a.filter((x) => !/windows/i.test(x.os || "")))).catch(() => {}); }, [ouvert, api]);
  async function enregistrer(nouvelle) {
    const r = await saveNavigateurs(api, nouvelle.map(({ nom, agent_id, libelle, accueil }) => ({ nom, agent_id, libelle, accueil })), username);
    if (r?.error) { setMsg({ ok: false, t: r.error }); return; }
    setMsg({ ok: true, t: "enregistré" }); setF({ nom: "", agent_id: "", libelle: "", accueil: "" }); recharger();
  }
  if (!ouvert) return <button className="secondary" onClick={() => setOuvert(true)}>+ Déclarer un navigateur</button>;
  return (
    <div className="infra-card nav-registre">
      <b>Navigateurs déclarés</b>
      {liste.map((n) => (
        <div key={n.nom} className="nav-ligne"><span><b>{n.libelle}</b> <span className="infra-muted">{n.nom} · {n.agent_id}</span></span>
          <button className="secondary" onClick={() => enregistrer(liste.filter((x) => x.nom !== n.nom))}>Retirer</button></div>
      ))}
      <form onSubmit={(e) => { e.preventDefault(); enregistrer([...liste, f]); }}>
        <label>Nom (celui de NAVIGATEURS dans le .env du hub)<input value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value.toLowerCase() })} placeholder="ovh1" required /></label>
        <label>Agent de l'hôte<select value={f.agent_id} onChange={(e) => setF({ ...f, agent_id: e.target.value })} required>
          <option value="">—</option>{agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.label || a.hostname || a.agent_id} ({a.agent_id})</option>)}</select></label>
        <label>Libellé<input value={f.libelle} onChange={(e) => setF({ ...f, libelle: e.target.value })} placeholder="VM OVH -- vue de l'extérieur" /></label>
        <label>Page d'accueil (facultatif)<input value={f.accueil} onChange={(e) => setF({ ...f, accueil: e.target.value })} placeholder="https://…" /></label>
        <div><button type="submit">Ajouter</button> <button type="button" className="secondary" onClick={() => setOuvert(false)}>Fermer</button></div>
      </form>
      {msg && <small className={msg.ok ? "infra-muted" : "infra-error"}>{msg.t}</small>}
      <small className="infra-muted">Installation sur l'hôte : <code>cd supervision-si/navigateur && sudo sh installer.sh</code> ; publication de l'écran : voir navigateur/README.md.</small>
    </div>
  );
}

function useCommande(api) {
  const [cmd, setCmd] = useState(null);       // {id, libelle, debut, c}
  useEffect(() => {
    if (!cmd?.id || (cmd.c && cmd.c.status !== "pending")) return undefined;
    const t = setTimeout(async () => {
      try { const c = await fetchCommand(api, cmd.id); setCmd((x) => (x && x.id === cmd.id ? { ...x, c } : x)); } catch { /* nouvel essai */ }
    }, cmd.c ? 2000 : 800);
    return () => clearTimeout(t);
  }, [api, cmd]);
  const lancer = useCallback(async (agentId, libelle, params) => {
    setCmd({ id: null, libelle, debut: Date.now(), c: null });
    const r = await navCommand(api, agentId, params);
    if (r?.error || !r?.id) { setCmd({ id: null, libelle, debut: Date.now(), c: { status: "failed", result: { error: r?.error || "commande refusée" } } }); return; }
    setCmd({ id: r.id, libelle, debut: Date.now(), c: null });
  }, [api]);
  return [cmd, lancer];
}

export default function NavigateurView({ onBack, siAgentApiBase: api, username }) {
  const [liste, setListe] = useState([]);
  const [err, setErr] = useState(null);
  const [nom, setNom] = useState(null);
  const [url, setUrl] = useState("");
  const [texte, setTexte] = useState(JSON.stringify(EXEMPLE_ETAPES, null, 1));
  const [base, setBase] = useState("");
  const [arret, setArret] = useState(true);
  const [ecranSeul, setEcranSeul] = useState(false);
  const [cmd, lancer] = useCommande(api);
  const [, tic] = useState(0);
  const charger = useCallback(() => fetchNavigateurs(api).then((r) => { setListe(trierNavigateurs(r?.navigateurs)); setErr(r?.error || null); }).catch((e) => setErr(e.message)), [api]);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => { if (!nom && liste.length) setNom(liste[0].nom); }, [liste, nom]);
  useEffect(() => { if (!cmd || cmd.c?.status && cmd.c.status !== "pending") return undefined; const t = setInterval(() => tic((x) => x + 1), 1000); return () => clearInterval(t); }, [cmd]);
  const n = useMemo(() => liste.find((x) => x.nom === nom), [liste, nom]);
  const etat = cmd ? etatCommande(cmd.c) : null;
  const res = cmd?.c?.result?.result || {};
  const etapes = lireEtapes(texte);
  return (
    <div className="infra-root nav-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Navigateur des hôtes</h2>
        <select value={nom || ""} onChange={(e) => setNom(e.target.value)}>
          {!liste.length && <option value="">aucun navigateur déclaré</option>}
          {liste.map((x) => <option key={x.nom} value={x.nom}>{x.libelle}</option>)}
        </select>
        {n && <span className="infra-muted">hôte {n.hostname || n.agent_id} · agent {n.agent_version || "?"}</span>}
        <label className="infra-muted"><input type="checkbox" checked={ecranSeul} onChange={(e) => setEcranSeul(e.target.checked)} /> écran seul</label>
      </div>
      {err && <p className="infra-error">{err}</p>}
      <Registre api={api} liste={liste} username={username} recharger={charger} />
      {n && (
        <div className={`nav-corps ${ecranSeul ? "seul" : ""}`}>
          <section className="nav-ecran">
            <form className="nav-barre" onSubmit={(e) => { e.preventDefault(); if (url) lancer(n.agent_id, `aller à ${url}`, { action: "aller", url }); }}>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={n.accueil || "https://… (ouverte par l'automate dans le navigateur de l'hôte)"} />
              <button type="submit" disabled={!/^https?:\/\//.test(url)}>Aller</button>
              <button type="button" className="secondary" onClick={() => lancer(n.agent_id, "capture", { action: "capture" })}>Capture</button>
              <button type="button" className="secondary" onClick={() => lancer(n.agent_id, "état", { action: "etat" })}>État</button>
              <a className="secondary" href={ecranUrl(n.nom, { scale: false })} target="_blank" rel="noreferrer">plein écran ↗</a>
            </form>
            <iframe key={n.nom} title={`écran ${n.libelle}`} src={ecranUrl(n.nom)} className="nav-iframe" allow="clipboard-read; clipboard-write" />
            <small className="infra-muted">Écran de l'hôte (mot de passe de l'écran demandé à la connexion : il est affiché par navigateur/installer.sh).</small>
          </section>
          {!ecranSeul && (
            <aside className="nav-panneau">
              <b>Parcours (étapes au format QA)</b>
              <label>Adresse de base<input value={base} onChange={(e) => setBase(e.target.value)} placeholder="https://service.example.org" /></label>
              <textarea rows={12} value={texte} onChange={(e) => setTexte(e.target.value)} spellCheck={false} />
              {etapes.erreur && <small className="infra-error">{etapes.erreur}</small>}
              <label className="infra-muted"><input type="checkbox" checked={arret} onChange={(e) => setArret(e.target.checked)} /> s'arrêter avant les étapes marquées <code>"ecrit": true</code> (valider, créer, supprimer)</label>
              <button disabled={!!etapes.erreur} onClick={() => lancer(n.agent_id, "parcours", { action: "etapes", etapes: etapes.etapes, base_url: base || undefined, arret_avant_ecriture: arret })}>Jouer sur l'hôte</button>
              {cmd && (
                <div className={`nav-resultat ${etat.etat}`}>
                  <div><b>{cmd.libelle}</b> · {etat.texte}{etat.etat === "attente" ? ` (${Math.round((Date.now() - cmd.debut) / 1000)} s)` : ""}</div>
                  {(res.resultats || []).map((x) => (
                    <div key={x.index} className={x.ok === false ? "infra-error" : "infra-muted"}>
                      {x.index}. {x.action} {x.ok === false ? `✗ ${x.error}` : x.attente ? "⏸ confirmation attendue" : `✓ ${x.duree_ms} ms`}
                    </div>
                  ))}
                  {res.url && <small className="infra-muted">{res.url}</small>}
                  {imageDe(res.capture) && <img className="nav-capture" src={imageDe(res.capture)} alt="capture de l'hôte" />}
                </div>
              )}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
