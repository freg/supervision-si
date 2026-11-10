// Liste de surveillance (livraison #1001) : listes déposées (copier-coller d'un tableur : libellé, type, modèle, référence,
// n° de série, MAC -- reconnus à leur forme, dans n'importe quel ordre), repères rapprochés à chaque relève horaire de
// l'historique des clients, concordance élément par élément avec ses preuves, discordances (usurpation possible ou
// changement à apprendre), décisions qui APPRENNENT (la MAC confirmée, même aléatoire, devient connue de l'élément).
// Les listes vivent dans la base du hub, jamais dans le dépôt.
import { useCallback, useEffect, useRef, useState } from "react";
import BoutonDetail from "./FenetreTexte.jsx";
import { hubLink } from "./hubLinks.js";
import { STATUTS, LOT, texteRepere, aTraiter, etatElement, parListe, libelleElement, dateFr, raccordement } from "./surveillanceLib.js";

export default function NebulaSurveillance({ nebulaApiBase, siteId, groups = [], login = "", focus = null }) {
  const base = `${nebulaApiBase}/surveillance`;
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState(null);           // {texte, erreur, reglage}
  const [enCours, setEnCours] = useState(null);   // clé de l'action en cours
  const [depot, setDepot] = useState(false);
  const [liste, setListe] = useState("");
  const [texte, setTexte] = useState("");
  const [apercu, setApercu] = useState(null);
  const [attribution, setAttribution] = useState({});

  const call = useCallback(async (url, methode = "GET", corps = null) => {
    const r = await fetch(url, { method: methode, credentials: "include", headers: corps ? { "Content-Type": "application/json" } : {},
      body: corps ? JSON.stringify({ groups, user: login, ...corps }) : undefined });
    let j = {};
    try { j = await r.json(); } catch { j = { error: `réponse illisible (HTTP ${r.status})` }; }
    if (!r.ok) throw Object.assign(new Error(j.error || `HTTP ${r.status}`), { reglage: j.reglage });
    return j;
  }, [groups, login]);

  // #1005 : aperçu automatique dès qu'un texte est collé (le bouton « Enregistrer » n'apparaissait qu'après un clic sur Aperçu)
  const dernierTexte = useRef("");
  useEffect(() => {
    if (!depot || !texte.trim()) return undefined;
    const t = setTimeout(async () => {
      dernierTexte.current = texte;
      try {
        const r = await call(`${base}/importer`, "POST", { texte, apercu: true });
        if (dernierTexte.current === texte) setApercu(r);
      } catch (e) { setMsg({ erreur: true, texte: `Aperçu impossible : ${e.message}` }); }
    }, 500);
    return () => clearTimeout(t);
  }, [texte, depot, base, call]);

  const charger = useCallback(async () => {
    try { setD(await call(`${base}?jours=60${siteId ? `&site=${encodeURIComponent(siteId)}` : ""}`)); }
    catch (e) { setMsg({ erreur: true, texte: `Lecture impossible : ${e.message}` }); }
  }, [base, siteId, call]);
  useEffect(() => { charger(); }, [charger]);

  async function agir(cle, fn, ok) {
    setEnCours(cle); setMsg(null);
    try { const r = await fn(); if (ok) setMsg({ texte: ok(r) }); await charger(); }
    catch (e) { setMsg({ erreur: true, texte: e.message, reglage: e.reglage }); }
    setEnCours(null);
  }
  const bouton = (cle, libelle, fn, ok, props = {}) => (
    <button type="button" disabled={enCours !== null} onClick={() => agir(cle, fn, ok)} {...props}>{enCours === cle ? "⏳ en cours…" : libelle}</button>);

  const reps = (d && d.reperes) || [];
  const traiter = aTraiter(reps);
  const groupes = parListe((d && d.elements) || []);
  const elementsDe = (li) => groupes[li] || [];

  return (
    <div className="hub-card">
      <h3 style={{ marginTop: 0 }}>🎯 Liste de surveillance</h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Chaque client vu par Nebula est rapproché, à chaque relève horaire, des listes déposées : MAC déclarée ou apprise, nom annoncé
        (n° de série, libellé, modèle), fabricant, système. Une MAC aléatoire n'empêche pas la reconnaissance par les autres éléments ;
        une contradiction alors que la MAC concorde est signalée (usurpation possible, ou changement à apprendre en confirmant).
      </p>

      {msg && (
        <p style={{ color: msg.erreur ? "var(--danger)" : "var(--ok)" }}>
          {msg.texte}
          {msg.reglage && <> — <a href={hubLink(msg.reglage.view)}>régler les droits</a> ({msg.reglage.texte})</>}
        </p>)}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
        <button type="button" onClick={() => setDepot((x) => !x)}>{depot ? "− Fermer le dépôt" : "+ Déposer une liste"}</button>
        {bouton("rapprocher", "🔁 Rapprocher maintenant (7 jours)", () => call(`${base}/rapprocher`, "POST", { site: siteId || null, jours: 7 }),
          (r) => `${r.evenements.length} nouveau(x) repère(s) ou discordance(s).`)}
      </div>

      {depot && (
        <div className="hub-card" style={{ background: "var(--bg)" }}>
          <label>Nom de la liste <input value={liste} onChange={(e) => setListe(e.target.value)} placeholder="ex. tablettes atelier" style={{ minWidth: 260 }} /></label>
          <p className="muted" style={{ margin: "6px 0" }}>Colle les lignes du tableur (tabulations, « ; » ou « , ») : libellé, type, modèle, référence, n° de série, MAC — dans n'importe quel ordre, l'en-tête est ignoré.</p>
          <textarea value={texte} onChange={(e) => { setTexte(e.target.value); setApercu(null); }} rows={8} style={{ width: "100%", fontFamily: "monospace" }} />
          <div style={{ display: "flex", gap: 8, marginTop: 6, alignItems: "center" }}>
            {bouton("enregistrer", apercu && apercu.elements.length ? `✔ Enregistrer ${apercu.elements.length} élément(s)` : "✔ Enregistrer la liste",
              () => call(`${base}/importer`, "POST", { liste, texte }),
              (r) => { setApercu(null); setTexte(""); setDepot(false); return `Liste « ${liste} » : ${r.ajoutes} ajouté(s), ${r.maj} mis à jour, ${r.reperes} repère(s) immédiat(s).`; },
              { disabled: enCours !== null || !liste.trim() || !texte.trim() || (apercu && !apercu.elements.length) })}
            <span className="muted">{!liste.trim() ? "donne un nom à la liste" : !texte.trim() ? "colle les lignes" : apercu ? `aperçu : ${apercu.elements.length} élément(s) reconnu(s), ${apercu.ignorees.length} ligne(s) écartée(s)` : "aperçu…"}</span>
          </div>
          {apercu && (
            <div style={{ maxHeight: 280, overflow: "auto", marginTop: 6 }}>
              <table className="services infra-table" style={{ width: "100%" }}>
                <thead><tr><th>Ligne</th><th>Libellé</th><th>Type</th><th>Modèle</th><th>Référence</th><th>N° de série</th><th>MAC</th><th>Fabricant</th></tr></thead>
                <tbody>
                  {apercu.elements.map((e) => <tr key={e.ligne}><td className="muted">{e.ligne}</td><td>{e.libelle || "—"}</td><td>{e.type || "—"}</td><td>{e.modele || "—"}</td><td>{e.reference || "—"}</td><td>{e.serie || "—"}</td><td><code>{e.mac || "—"}</code></td><td>{e.fabricant || "—"}</td></tr>)}
                  {apercu.ignorees.map((i) => <tr key={`i${i.ligne}`} className="muted"><td>{i.ligne}</td><td colSpan={7}>écartée : {i.raison} — {i.texte}</td></tr>)}
                </tbody>
              </table>
            </div>)}
        </div>)}

      {traiter.length > 0 && (
        <>
          <h4>À traiter ({traiter.length})</h4>
          <table className="services infra-table" style={{ width: "100%" }}>
            <thead><tr><th>Statut</th><th>Élément</th><th>Client vu</th><th>Raccordement</th><th>Vu le</th><th>Décision</th></tr></thead>
            <tbody>{traiter.map((r) => {
              const s = STATUTS[r.statut] || {};
              const c = r.client || {};
              return (
                <tr key={r.id}>
                  <td style={{ color: s.couleur }}><b>{s.libelle}</b> <BoutonDetail titre="Concordance" urgence={s.urgence} texte={texteRepere(r)} /></td>
                  <td>{r.liste} — {r.element_id === LOT ? (
                    <select value={attribution[r.id] || ""} onChange={(e) => setAttribution((a) => ({ ...a, [r.id]: e.target.value }))}>
                      <option value="">choisir l'élément…</option>
                      {elementsDe(r.liste).map((e) => <option key={e.id} value={e.id}>{libelleElement(e)}</option>)}
                    </select>) : <b>{libelleElement(r)}</b>}</td>
                  <td>{c.name || "sans nom"} <code>{r.mac}</code>{c.ip ? ` — ${c.ip}` : ""}</td>
                  <td className="muted">{raccordement(c) || "—"}</td>
                  <td className="muted">{dateFr(r.dernier)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {bouton(`c${r.id}`, "✔ Confirmer", () => call(`${base}/reperes/${r.id}/decision`, "POST", { decision: "confirme", element_id: r.element_id === LOT ? attribution[r.id] : undefined }),
                      () => "Confirmé : la MAC est apprise pour cet élément.", { disabled: enCours !== null || (r.element_id === LOT && !attribution[r.id]) })}{" "}
                    {bouton(`r${r.id}`, "✖ Rejeter", () => call(`${base}/reperes/${r.id}/decision`, "POST", { decision: "rejete" }), () => "Rejeté : ne sera plus proposé.")}
                  </td>
                </tr>);
            })}</tbody>
          </table>
        </>)}

      {!d ? <p className="muted">Chargement…</p> : Object.keys(groupes).length === 0 ? <p className="muted">Aucune liste déposée.</p> : Object.entries(groupes).map(([li, els]) => (
        <div key={li} style={{ marginTop: 12 }}>
          <h4 style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {li} <span className="muted">({els.length} élément(s), {els.filter((e) => e.dernier_repere).length} repéré(s) sur {d.jours} jours)</span>
            {bouton(`L${li}`, "🗑 Supprimer la liste", () => (window.confirm(`Supprimer la liste « ${li} » et ses repères ?`) ? call(`${base}/listes/${encodeURIComponent(li)}`, "DELETE", {}) : Promise.resolve({ annule: true })),
              (r) => (r.annule ? "Suppression annulée." : `Liste « ${li} » supprimée.`))}
          </h4>
          <div style={{ maxHeight: 420, overflow: "auto" }}>
            <table className="services infra-table" style={{ width: "100%" }}>
              <thead><tr><th>Libellé</th><th>Modèle</th><th>N° de série</th><th>MAC</th><th>État</th><th>Dernier raccordement</th><th></th></tr></thead>
              <tbody>{els.map((e) => {
                const st = etatElement(e);
                const r = e.dernier_repere;
                return (
                  <tr key={e.id} style={focus && String(focus) === String(e.id) ? { outline: "2px solid var(--accent)" } : undefined}>
                    <td><b>{libelleElement(e)}</b>{e.type ? <span className="muted"> — {e.type}</span> : null}</td>
                    <td>{[e.modele, e.reference].filter(Boolean).join(" / ") || "—"}</td>
                    <td><code>{e.serie || "—"}</code></td>
                    <td><code>{e.mac || "—"}</code>{(e.macs_apprises || []).length ? <span className="muted"> + {e.macs_apprises.length} apprise(s)</span> : null}</td>
                    <td style={{ color: st.couleur }}>{st.texte}{r ? <> <BoutonDetail titre="Concordance" urgence={(STATUTS[r.statut] || {}).urgence || "info"} texte={texteRepere(r)} /></> : null}</td>
                    <td className="muted">{r ? `${(r.client || {}).name || "sans nom"} — ${raccordement(r.client || {}) || "—"}` : "—"}</td>
                    <td>{bouton(`e${e.id}`, "🗑", () => call(`${base}/elements/${e.id}`, "DELETE", {}), () => `${libelleElement(e)} supprimé.`, { title: "Supprimer cet élément" })}</td>
                  </tr>);
              })}</tbody>
            </table>
          </div>
        </div>))}
    </div>
  );
}
