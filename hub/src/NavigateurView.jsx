// Tuile « Navigateur des hôtes » (livraison #798) : un Chromium visible qui tourne SUR l'hôte d'un agent Linux (en priorité
// une VM OVH : nos services vus de l'extérieur), et non dans le navigateur qui consulte le hub. Écran web (noVNC publié
// par le bastion, servi par tls-proxy sous /navigateur/<nom>/) pour le voir et l'utiliser ; automate Playwright local
// (commande « navigateur » de l'agent) pour ouvrir une adresse, capturer, jouer un parcours au format QA -- l'automate
// travaille dans le même navigateur, on le voit faire et on peut reprendre la main. #799 : apprentissage d'un parcours
// (les gestes faits dans l'écran deviennent des étapes paramétrées, accès du coffre au moment du jeu) ; #800 : demande en
// langage courant interprétée par l'assistant du hub -> plan montré, joué avec arrêt avant écriture. Logique pure : navigateurLib.js.
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchNavigateurs, saveNavigateurs, navCommand, fetchCommand, fetchFleet, fetchParcours, createParcours, deleteParcours,
  jouerParcours, interpreterDemande } from "./siAgentClient.js";
import { ecranUrl, EXEMPLE_ETAPES, lireEtapes, etatCommande, imageDe, trierNavigateurs, paramsVisibles, valeursInitiales, brouillonDepuis,
  resumeParcours } from "./navigateurLib.js";

function Registre({ api, liste, username, recharger }) {
  const [ouvert, setOuvert] = useState(false);
  const [agents, setAgents] = useState([]);
  const [f, setF] = useState({ nom: "", agent_id: "", libelle: "", accueil: "", usage: "navigateur" });
  const [msg, setMsg] = useState(null);
  useEffect(() => { if (ouvert) fetchFleet(api).then((a) => setAgents(a.filter((x) => !/windows/i.test(x.os || "")))).catch(() => {}); }, [ouvert, api]);
  async function enregistrer(nouvelle) {
    const r = await saveNavigateurs(api, nouvelle.map(({ nom, agent_id, libelle, accueil, usage }) => ({ nom, agent_id, libelle, accueil, usage: usage || "navigateur" })), username);
    if (r?.error) { setMsg({ ok: false, t: r.error }); return; }
    setMsg({ ok: true, t: "enregistré" }); setF({ nom: "", agent_id: "", libelle: "", accueil: "", usage: "navigateur" }); recharger();
  }
  if (!ouvert) return <div><button className="secondary" onClick={() => setOuvert(true)}>+ Déclarer un navigateur</button></div>;
  return (
    <div className="infra-card nav-registre">
      <b>Navigateurs déclarés</b>
      {liste.map((n) => (
        <div key={n.nom} className="nav-ligne"><span><b>{n.libelle}</b> <span className="infra-muted">{n.nom} · {n.agent_id}{n.usage === "emulation" ? " · écrans d'émulation (porte 6899)" : ""}</span></span>
          <button className="secondary" onClick={() => enregistrer(liste.filter((x) => x.nom !== n.nom))}>Retirer</button></div>
      ))}
      <form onSubmit={(e) => { e.preventDefault(); enregistrer([...liste, f]); }}>
        <label>Nom (celui de NAVIGATEURS dans le .env du hub)<input value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value.toLowerCase() })} placeholder="ovh1" required /></label>
        <label>Agent de l'hôte<select value={f.agent_id} onChange={(e) => setF({ ...f, agent_id: e.target.value })} required>
          <option value="">—</option>{agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.label || a.hostname || a.agent_id} ({a.agent_id})</option>)}</select></label>
        <label>Libellé<input value={f.libelle} onChange={(e) => setF({ ...f, libelle: e.target.value })} placeholder="VM OVH -- vue de l'extérieur" /></label>
        <label>Usage<select value={f.usage} onChange={(e) => setF({ ...f, usage: e.target.value })}>
          <option value="navigateur">navigateur de l'hôte (127.0.0.1:6080)</option><option value="emulation">écrans d'émulation (porte 127.0.0.1:6899)</option></select></label>
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
  const suivre = useCallback((id, libelle) => setCmd({ id, libelle, debut: Date.now(), c: null }), []);
  return [cmd, lancer, suivre];
}

function Resultat({ cmd, onConfirmer }) {
  if (!cmd) return null;
  const etat = etatCommande(cmd.c);
  const res = cmd.c?.result?.result || {};
  return (
    <div className={`nav-resultat ${etat.etat}`}>
      <div><b>{cmd.libelle}</b> · {etat.texte}{etat.etat === "attente" ? ` (${Math.round((Date.now() - cmd.debut) / 1000)} s)` : ""}</div>
      {(res.resultats || []).map((x) => (
        <div key={x.index} className={x.ok === false ? "infra-error" : "infra-muted"}>
          {x.index}. {x.action} {x.ok === false ? `✗ ${x.error}` : x.attente ? `⏸ ${x.note || "confirmation attendue"}` : `✓ ${x.duree_ms} ms`}
        </div>
      ))}
      {etat.etat === "confirmation" && onConfirmer && <button onClick={onConfirmer}>Confirmer : rejouer jusqu'au bout (écriture)</button>}
      {res.url && <small className="infra-muted">{res.url}</small>}
      {imageDe(res.capture) && <img className="nav-capture" src={imageDe(res.capture)} alt="capture de l'hôte" />}
    </div>
  );
}

function Apprendre({ api, n, username, lancer, cmd, apresEnregistrement }) {
  const [b, setB] = useState(null);       // brouillon de parcours
  const [texteEt, setTexteEt] = useState("");
  const [msg, setMsg] = useState(null);
  const fin = cmd?.libelle === "fin de l'apprentissage" && cmd.c?.status === "done" ? cmd.c.result?.result : null;
  useEffect(() => { if (fin?.etapes) { const x = brouillonDepuis(fin, n.nom); setB(x); setTexteEt(JSON.stringify(x.etapes, null, 1)); } }, [fin, n.nom]);
  async function enregistrer() {
    const et = lireEtapes(texteEt);
    if (et.erreur) { setMsg({ ok: false, t: et.erreur }); return; }
    const r = await createParcours(api, { ...b, etapes: et.etapes }, username);
    if (r?.error) { setMsg({ ok: false, t: r.error }); return; }
    setMsg({ ok: true, t: `parcours « ${r.parcours.nom} » enregistré` }); setB(null); apresEnregistrement();
  }
  return (
    <div className="nav-onglet">
      <p className="infra-muted">1. Démarrer, 2. faire le parcours à la main dans l'écran (connexion, saisies, clics), 3. Terminer : les gestes
        deviennent des étapes ; mots de passe jamais gardés, identifiant et mot de passe pris dans le coffre au moment du jeu.</p>
      <div className="nav-barre">
        <button onClick={() => lancer(n.agent_id, "début de l'apprentissage", { action: "enregistrer", etape: "debut" })}>● Démarrer</button>
        <button className="secondary" onClick={() => lancer(n.agent_id, "fin de l'apprentissage", { action: "enregistrer", etape: "fin" })}>■ Terminer</button>
      </div>
      {b && (
        <div className="nav-brouillon">
          <label>Nom<input value={b.nom} onChange={(e) => setB({ ...b, nom: e.target.value })} placeholder="Ticket de maintenance GMAO" /></label>
          <label>Description (sert à reconnaître les demandes en langage courant)<textarea rows={2} value={b.description} onChange={(e) => setB({ ...b, description: e.target.value })}
            placeholder="Crée un ticket de maintenance pour un site client (objet, site, urgence)" /></label>
          <label>Adresse de base<input value={b.base_url} onChange={(e) => setB({ ...b, base_url: e.target.value })} /></label>
          <label>Accès du coffre (tuile Accès d'équipements) pour identifiant / mot de passe<input value={b.acces} onChange={(e) => setB({ ...b, acces: e.target.value })} placeholder="gmao-test" /></label>
          <b>Paramètres</b>
          {b.parametres.map((x, i) => (
            <div key={x.nom} className="nav-param">
              <code>{`{{${x.nom}}}`}</code>
              <input value={x.note || ""} placeholder="rôle (pour l'assistant)" onChange={(e) => setB({ ...b, parametres: b.parametres.map((y, j) => (j === i ? { ...y, note: e.target.value } : y)) })} />
              {x.secret ? <span className="infra-muted">secret</span> : <input value={x.defaut || ""} placeholder="défaut" onChange={(e) => setB({ ...b, parametres: b.parametres.map((y, j) => (j === i ? { ...y, defaut: e.target.value } : y)) })} />}
            </div>
          ))}
          <label>Étapes (modifiables)<textarea rows={10} value={texteEt} onChange={(e) => setTexteEt(e.target.value)} spellCheck={false} /></label>
          <button disabled={!b.nom.trim()} onClick={enregistrer}>Enregistrer le parcours</button>
        </div>
      )}
      {msg && <small className={msg.ok ? "infra-muted" : "infra-error"}>{msg.t}</small>}
    </div>
  );
}

function Appris({ api, n, username, liste, recharger, suivre, plan, setPlan }) {
  const [choix, setChoix] = useState(null);
  const [valeurs, setValeurs] = useState({});
  const [msg, setMsg] = useState(null);
  const p = liste.find((x) => x.id === (plan?.parcours_id ?? choix));
  useEffect(() => { if (p) setValeurs(valeursInitiales(p, plan)); }, [p?.id, plan]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function jouer(confirmer) {
    if (confirmer && !window.confirm(`Jouer « ${p.nom} » jusqu'au bout, étapes qui écrivent comprises ?`)) return;
    setMsg(null);
    const r = await jouerParcours(api, p.id, { valeurs, confirmer, navigateur: n.nom, actor: username });
    if (r?.error) { setMsg({ ok: false, t: r.error }); return; }
    suivre(r.commande, `« ${p.nom} »${confirmer ? " (écriture confirmée)" : ""}`); recharger();
  }
  return (
    <div className="nav-onglet">
      {!liste.length && <p className="infra-muted">Aucun parcours appris : onglet « Apprendre ».</p>}
      {liste.map((x) => (
        <div key={x.id} className={`nav-ligne ${p?.id === x.id ? "actif" : ""}`}>
          <span onClick={() => { setPlan(null); setChoix(x.id); }} className="nav-clic"><b>{x.nom}</b> <span className="infra-muted">{resumeParcours(x)} · joué {x.jeux || 0} fois</span></span>
          <button className="secondary" onClick={async () => { if (window.confirm(`Supprimer le parcours « ${x.nom} » ?`)) { await deleteParcours(api, x.id); recharger(); } }}>✕</button>
        </div>
      ))}
      {p && (
        <div className="nav-brouillon">
          {plan && <small className="infra-muted">Proposé par l'assistant{plan.confiance != null ? ` (confiance ${Math.round(plan.confiance * 100)} %)` : ""} : {plan.explication}</small>}
          {p.description && <small className="infra-muted">{p.description}</small>}
          {paramsVisibles(p).map((x) => (
            <label key={x.nom}>{x.note || x.nom}<input value={valeurs[x.nom] || ""} onChange={(e) => setValeurs({ ...valeurs, [x.nom]: e.target.value })}
              className={plan?.manquants?.includes(x.nom) && !valeurs[x.nom] ? "nav-manquant" : ""} /></label>
          ))}
          {p.acces && <small className="infra-muted">identifiant et mot de passe : accès « {p.acces} » du coffre</small>}
          <div className="nav-barre">
            <button onClick={() => jouer(false)}>Jouer (arrêt avant écriture)</button>
            <button className="secondary" onClick={() => jouer(true)}>Jouer jusqu'au bout</button>
          </div>
        </div>
      )}
      {msg && <small className={msg.ok ? "infra-muted" : "infra-error"}>{msg.t}</small>}
    </div>
  );
}

function Demande({ api, versAppris }) {
  const [texte, setTexte] = useState("");
  const [en, setEn] = useState(null);
  const [msg, setMsg] = useState(null);
  const [, tic] = useState(0);
  useEffect(() => { if (!en) return undefined; const t = setInterval(() => tic((x) => x + 1), 1000); return () => clearInterval(t); }, [en]);
  async function interpreter() {
    setEn(Date.now()); setMsg(null);
    const r = await interpreterDemande(api, texte);
    setEn(null);
    if (!r?.ok) { setMsg({ ok: false, t: r?.error || r?.erreur || "pas de parcours correspondant", x: r?.explication }); return; }
    versAppris(r);
  }
  return (
    <div className="nav-onglet">
      <p className="infra-muted">Ex. « ouvre la GMAO, connecte-toi et crée un ticket de maintenance du chauffage chez Alpha, bâtiment B ». L'assistant
        du hub (modèle local) choisit un parcours appris et ses valeurs ; le plan est montré, rien n'est joué sans toi.</p>
      <textarea rows={4} value={texte} onChange={(e) => setTexte(e.target.value)} placeholder="ta demande…" />
      <button disabled={!texte.trim() || !!en} onClick={interpreter}>{en ? `interprétation… ${Math.round((Date.now() - en) / 1000)} s` : "Interpréter"}</button>
      {msg && <small className={msg.ok ? "infra-muted" : "infra-error"}>{msg.t}{msg.x ? ` -- ${msg.x}` : ""}</small>}
    </div>
  );
}

export default function NavigateurView({ onBack, siAgentApiBase: api, username }) {
  const [liste, setListe] = useState([]);
  const [tous, setTous] = useState([]);       // #839 : registre complet (écrans d'émulation compris)
  const [err, setErr] = useState(null);
  const [nom, setNom] = useState(null);
  const [url, setUrl] = useState("");
  const [texte, setTexte] = useState(JSON.stringify(EXEMPLE_ETAPES, null, 1));
  const [base, setBase] = useState("");
  const [arret, setArret] = useState(true);
  const [ecranSeul, setEcranSeul] = useState(false);
  const [cmd, lancer, suivre] = useCommande(api);
  const [onglet, setOnglet] = useState("demande");
  const [parcours, setParcours] = useState([]);
  const [plan, setPlan] = useState(null);
  const chargerParcours = useCallback(() => fetchParcours(api).then((r) => setParcours(r?.parcours || [])).catch(() => {}), [api]);
  useEffect(() => { chargerParcours(); }, [chargerParcours]);
  const [, tic] = useState(0);
  const charger = useCallback(() => fetchNavigateurs(api).then((r) => { setTous(r?.navigateurs || []); setListe(trierNavigateurs((r?.navigateurs || []).filter((x) => x.usage !== "emulation"))); setErr(r?.error || null); }).catch((e) => setErr(e.message)), [api]);
  useEffect(() => { charger(); }, [charger]);
  useEffect(() => { if (!nom && liste.length) setNom(liste[0].nom); }, [liste, nom]);
  useEffect(() => { if (!cmd || cmd.c?.status && cmd.c.status !== "pending") return undefined; const t = setInterval(() => tic((x) => x + 1), 1000); return () => clearInterval(t); }, [cmd]);
  const n = useMemo(() => liste.find((x) => x.nom === nom), [liste, nom]);
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
      <Registre api={api} liste={tous} username={username} recharger={charger} />
      {n && (
        <div className={`nav-corps ${ecranSeul ? "seul" : ""}`}>
          <section className="nav-ecran">
            <form className="nav-barre" onSubmit={(e) => { e.preventDefault(); if (url) lancer(n.agent_id, `aller à ${url}`, { action: "aller", url }); }}>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={n.accueil || "https://… (ouverte par l'automate dans le navigateur de l'hôte)"} />
              <button type="submit" disabled={!/^https?:\/\//.test(url)}>Aller</button>
              <button type="button" className="secondary" onClick={() => lancer(n.agent_id, "capture", { action: "capture" })}>Capture</button>
              <button type="button" className="secondary" onClick={() => lancer(n.agent_id, "état", { action: "etat" })}>État</button>
              <a className="nav-lien" href={ecranUrl(n.nom, { scale: false })} target="_blank" rel="noreferrer">plein écran ↗</a>
            </form>
            <iframe key={n.nom} title={`écran ${n.libelle}`} src={ecranUrl(n.nom)} className="nav-iframe" allow="clipboard-read; clipboard-write" />
            <small className="infra-muted">Écran de l'hôte (mot de passe de l'écran demandé à la connexion : il est affiché par navigateur/installer.sh).</small>
          </section>
          {!ecranSeul && (
            <aside className="nav-panneau">
              <div className="nav-onglets">
                {[["demande", "Demande"], ["appris", `Parcours appris (${parcours.length})`], ["apprendre", "Apprendre"], ["etapes", "Étapes"]].map(([k, l]) => (
                  <button key={k} className={onglet === k ? "" : "secondary"} onClick={() => setOnglet(k)}>{l}</button>))}
              </div>
              {onglet === "demande" && <Demande api={api} versAppris={(pl) => { setPlan(pl); setOnglet("appris"); }} />}
              {onglet === "appris" && <Appris api={api} n={n} username={username} liste={parcours} recharger={chargerParcours} suivre={suivre} plan={plan} setPlan={setPlan} />}
              {onglet === "apprendre" && <Apprendre api={api} n={n} username={username} lancer={lancer} cmd={cmd} apresEnregistrement={() => { chargerParcours(); setOnglet("appris"); }} />}
              {onglet === "etapes" && (
                <div className="nav-onglet">
                  <label>Adresse de base<input value={base} onChange={(e) => setBase(e.target.value)} placeholder="https://service.example.org" /></label>
                  <textarea rows={12} value={texte} onChange={(e) => setTexte(e.target.value)} spellCheck={false} />
                  {etapes.erreur && <small className="infra-error">{etapes.erreur}</small>}
                  <label className="infra-muted"><input type="checkbox" checked={arret} onChange={(e) => setArret(e.target.checked)} /> s'arrêter avant les étapes marquées <code>"ecrit": true</code></label>
                  <button disabled={!!etapes.erreur} onClick={() => lancer(n.agent_id, "parcours", { action: "etapes", etapes: etapes.etapes, base_url: base || undefined, arret_avant_ecriture: arret })}>Jouer sur l'hôte</button>
                </div>
              )}
              <Resultat cmd={cmd} />
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
