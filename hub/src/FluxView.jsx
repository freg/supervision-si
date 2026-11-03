// Supervision des flux sortants exigés par les éditeurs (#962) : un onglet par SI / site, synthèse du dernier passage par
// source (matrice hôte × port), alertes ouvertes / rétablies, historique, analyse Nebula (terminaux mobiles par VLAN, VLAN
// testés), listes de cibles (Google intégrée, Idruide et autres collées depuis la page de l'éditeur), mise en place.
// Les tests tournent SUR LE SITE (nebula/tools/test-flux.sh) et envoient leurs résultats. API : nebula-api /flux*, /sites/<s>/flux*.
import { useCallback, useEffect, useState } from "react";
import BoutonDetail, { FenetreTexte } from "./FenetreTexte.jsx";
import { STATUTS, SITE_KEY, resumeBilan, age, filtrerMatrice, dureeAlerte, commandesSite, exempleListe } from "./fluxLib.js";

const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* stockage indisponible */ } },
};
async function getJson(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}
const corps = (m, body) => ({ method: m, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const ONGLETS = [["synthese", "Synthèse"], ["alertes", "Alertes"], ["historique", "Historique"], ["analyse", "Analyse Nebula"], ["listes", "Listes de cibles"], ["installer", "Mise en place"]];
const Pastille = ({ st, titre }) => {
  const s = STATUTS[st] || STATUTS["?"];
  return <span title={titre || s.libelle} style={{ display: "inline-block", minWidth: 62, textAlign: "center", padding: "1px 6px", borderRadius: 6, background: s.fond, color: s.couleur, fontWeight: 600, fontSize: ".8rem" }}>{st}</span>;
};

export default function FluxView({ onBack, nebulaApiBase, actor }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(() => store.get(SITE_KEY, ""));
  const [onglet, setOnglet] = useState("synthese");
  const [data, setData] = useState(null);
  const [alertes, setAlertes] = useState(null);
  const [analyse, setAnalyse] = useState(null);
  const [listes, setListes] = useState([]);
  const [passage, setPassage] = useState(null);
  const [filtre, setFiltre] = useState({ problemes: true, q: "" });
  const [etatAlertes, setEtatAlertes] = useState("ouvertes");
  const [form, setForm] = useState(null);           // liste en édition {nom, editeur, source, texte}
  const [iface, setIface] = useState("");
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [aide, setAide] = useState(null);
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;
  const hubAbs = nebulaApiBase.startsWith("http") ? nebulaApiBase : `${window.location.origin}${nebulaApiBase}`;

  const chargerSites = useCallback(() => getJson(`${nebulaApiBase}/flux/sites`).then((d) => {
    setSites(d.sites || []);
    if (!siteId && d.sites?.[0]) setSiteId(d.sites[0].site_id);
  }).catch((e) => setMsg({ ok: false, text: e.message })), [nebulaApiBase, siteId]);
  useEffect(() => { chargerSites(); }, [chargerSites]);
  useEffect(() => { if (siteId) store.set(SITE_KEY, siteId); }, [siteId]);
  const chargerListes = useCallback(() => getJson(`${nebulaApiBase}/flux/listes`).then((d) => setListes(d.listes || [])).catch(() => {}), [nebulaApiBase]);
  useEffect(() => { chargerListes(); }, [chargerListes]);

  const charger = useCallback(async () => {
    if (!siteId) return;
    try { setData(await getJson(`${base}/flux`)); } catch (e) { setMsg({ ok: false, text: e.message }); }
  }, [base, siteId]);
  useEffect(() => { setData(null); setAnalyse(null); setPassage(null); charger(); const t = setInterval(charger, 60000); return () => clearInterval(t); }, [charger]);
  useEffect(() => {
    if (!siteId || onglet !== "alertes") return;
    getJson(`${base}/flux/alertes?etat=${etatAlertes}`).then((d) => setAlertes(d.alertes || [])).catch((e) => setMsg({ ok: false, text: e.message }));
  }, [onglet, etatAlertes, base, siteId, data]);
  const lancerAnalyse = async () => {
    setBusy("analyse"); setMsg(null);
    try { setAnalyse(await getJson(`${base}/flux/analyse?jours=7`)); } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  };
  useEffect(() => { if (onglet === "analyse" && siteId && !analyse) lancerAnalyse(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [onglet, siteId]);

  const acquitter = async (a) => {
    const note = window.prompt("Note (cause, décision, qui s'en charge)", a.note || "");
    if (note === null) return;
    setBusy(`acq:${a.id}`);
    try { await getJson(`${base}/flux/alertes/${a.id}/acquitter`, corps("POST", { par: actor, note })); await charger(); setMsg({ ok: true, text: "✓ alerte acquittée" }); }
    catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  };
  const enregistrerListe = async () => {
    setBusy("liste"); setMsg(null);
    try {
      const r = await getJson(`${nebulaApiBase}/flux/listes`, corps("PUT", form));
      setMsg({ ok: !r.erreurs?.length, text: `✓ liste « ${r.id} » : ${r.cibles} cible(s)${r.erreurs?.length ? ` — ${r.erreurs.length} ligne(s) ignorée(s) : ${r.erreurs.join(" ; ")}` : ""}` });
      setForm(null); chargerListes();
    } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  };
  const supprimerListe = async (l) => {
    if (!window.confirm(`Supprimer la liste « ${l.nom} » ?`)) return;
    setBusy(`del:${l.id}`);
    try { await getJson(`${nebulaApiBase}/flux/listes/${l.id}`, { method: "DELETE" }); chargerListes(); } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  };
  const voirPassage = async (p) => {
    setBusy(`p:${p.id}`);
    try { setPassage(await getJson(`${base}/flux/passages/${p.id}`)); } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setBusy(null); }
  };

  const site = sites.find((s) => s.site_id === siteId);
  const Matrice = ({ src }) => {
    const m = filtrerMatrice(src.matrice, filtre);
    return (
      <div style={{ overflowX: "auto" }}>
        <table className="table"><thead><tr><th>Hôte</th><th>Groupe</th>{m.colonnes.map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>
          {m.lignes.map((l) => (
            <tr key={l.hote}><td><code>{l.hote}</code></td><td><small>{l.groupe}</small></td>
              {m.colonnes.map((c) => <td key={c}>{l.cellules[c] ? <Pastille st={l.cellules[c]} titre={l.details[c]} /> : ""}</td>)}</tr>))}
          {!m.lignes.length && <tr><td colSpan={m.colonnes.length + 2} className="muted">{filtre.problemes ? "aucun flux fermé ni inspecté ✓" : "aucune cible"}</td></tr>}
        </tbody></table>
      </div>
    );
  };

  return (
    <section className="view flux-editeurs">
      <header className="view-header" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <h1 style={{ margin: 0 }}>🔓 Flux éditeurs</h1>
        <button type="button" className="secondary" onClick={() => { chargerSites(); charger(); }}>↻</button>
      </header>
      <nav style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "8px 0" }}>
        {sites.map((s) => (
          <button key={s.site_id} type="button" className={s.site_id === siteId ? "" : "secondary"} onClick={() => setSiteId(s.site_id)}>
            {s.nebula ? "📶 " : "🏢 "}{s.nom}{s.alertes ? <span style={{ color: "var(--danger)", fontWeight: 700 }}> · {s.alertes}</span> : ""}
          </button>))}
        {!sites.length && <span className="muted">Aucun site : lancer un premier test (onglet Mise en place).</span>}
      </nav>
      <nav style={{ display: "flex", gap: 4, flexWrap: "wrap", borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
        {ONGLETS.map(([k, l]) => <button key={k} type="button" className={onglet === k ? "" : "secondary"} onClick={() => setOnglet(k)}>{l}{k === "alertes" && data?.alertes_ouvertes?.length ? ` (${data.alertes_ouvertes.length})` : ""}</button>)}
      </nav>
      {msg && <p className={msg.ok ? "ok" : "error"}>{msg.text}</p>}

      {onglet === "synthese" && (
        <div>
          {data && !data.sources.length && <p className="muted">Aucun résultat reçu pour ce site. Onglet « Mise en place » pour lancer le premier test depuis une machine du site.</p>}
          {data?.sources.map((s) => (
            <div key={s.source} className="panel" style={{ marginTop: 10 }}>
              <h3 style={{ marginTop: 0 }}>{s.bilan.etat === "alerte" ? "⚠" : "✓"} {s.source} <small className="muted">— {age(s.at)} · sortie {s.iface || "par défaut"} {s.ip_source || ""} · IP publique {s.ip_publique || "?"}</small></h3>
              <p>{resumeBilan(s.bilan)}{s.bilan.NS ? <> <BoutonDetail texte={"NS = le port est ouvert vers d'autres hôtes de la liste mais celui-ci ne le sert pas (ex. 5228 sur play.google.com alors que mtalk.google.com l'accepte) : ce n'est pas un blocage du pare-feu."} titre="NS : non servi" urgence="info" /></> : null}</p>
              <p><label><input type="checkbox" checked={filtre.problemes} onChange={(e) => setFiltre({ ...filtre, problemes: e.target.checked })} /> seulement les flux fermés ou inspectés</label>{" "}
                <input placeholder="filtrer un hôte" value={filtre.q} onChange={(e) => setFiltre({ ...filtre, q: e.target.value })} /></p>
              <Matrice src={s} />
            </div>))}
        </div>
      )}

      {onglet === "alertes" && (
        <div className="panel" style={{ marginTop: 10 }}>
          <p>{["ouvertes", "retablies", "toutes"].map((e) => <button key={e} type="button" className={etatAlertes === e ? "" : "secondary"} onClick={() => setEtatAlertes(e)} style={{ marginRight: 4 }}>{e === "retablies" ? "rétablies" : e}</button>)}</p>
          <table className="table"><thead><tr><th>État</th><th>Flux</th><th>Source</th><th>Depuis</th><th>Durée</th><th>Détail</th><th>Suivi</th></tr></thead><tbody>
            {(alertes || []).map((a) => (
              <tr key={a.id}>
                <td>{a.fin ? <Pastille st="OK" titre="rétablie" /> : <Pastille st={a.statut} />}</td>
                <td><code>{a.hote}</code> {a.proto}/{a.port}</td><td>{a.source}</td>
                <td>{new Date(a.debut * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}</td><td>{dureeAlerte(a)}</td>
                <td><small>{a.detail}</small></td>
                <td>{a.acquitte_par ? <small>✓ {a.acquitte_par}{a.note ? ` — ${a.note}` : ""}</small> : !a.fin && <button type="button" className="secondary" disabled={!!busy} onClick={() => acquitter(a)}>{busy === `acq:${a.id}` ? "⏳" : "Acquitter"}</button>}</td>
              </tr>))}
            {alertes && !alertes.length && <tr><td colSpan={7} className="muted">aucune alerte</td></tr>}
          </tbody></table>
          <p className="muted">Une alerte s'ouvre quand un flux passe fermé (KO) ou inspecté, et se ferme seule au premier passage où il redevient ouvert. Les notifications utilisent les actions « flux.ferme » / « flux.retabli » du module Notifications.</p>
        </div>
      )}

      {onglet === "historique" && (
        <div className="panel" style={{ marginTop: 10 }}>
          <table className="table"><thead><tr><th>Quand</th><th>Source</th><th>Sortie</th><th>Bilan</th><th /></tr></thead><tbody>
            {(data?.historique || []).map((p) => (
              <tr key={p.id}><td>{new Date(p.at * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" })}</td><td>{p.source}</td>
                <td><small>{p.iface || "défaut"} {p.ip_source || ""}</small></td><td><span style={{ color: p.bilan.etat === "alerte" ? "var(--danger)" : "var(--ok)" }}>●</span> {resumeBilan(p.bilan)}</td>
                <td><button type="button" className="secondary" onClick={() => voirPassage(p)} disabled={!!busy}>{busy === `p:${p.id}` ? "⏳" : "voir"}</button> <a className="button secondary" href={`${base}/flux/passages/${p.id}.csv`} download>CSV</a></td></tr>))}
          </tbody></table>
          {passage && <div className="panel"><h3>Passage du {new Date(passage.at * 1000).toLocaleString("fr-FR")} — {passage.source} <button type="button" className="secondary" onClick={() => setPassage(null)}>✕</button></h3><Matrice src={passage} /></div>}
        </div>
      )}

      {onglet === "analyse" && (
        <div className="panel" style={{ marginTop: 10 }}>
          {!site?.nebula && <p className="muted">Ce site n'est pas un site Nebula : l'analyse croisée (terminaux par VLAN / SSID) n'est disponible que pour les sites gérés dans Nebula.</p>}
          {site?.nebula && <>
            <p><button type="button" onClick={lancerAnalyse} disabled={!!busy}>{busy === "analyse" ? "⏳ analyse en cours…" : "↻ Relancer l'analyse (7 jours d'historique des clients)"}</button></p>
            {analyse && <>
              <p><strong>{analyse.terminaux}</strong> terminal(aux) mobile(s) vus (Android, iOS, tablettes) — {analyse.couverts}/{analyse.a_couvrir} VLAN concerné(s) couvert(s) par un test de flux. <small className="muted">({analyse.clients_lus} clients de l'historique lus)</small></p>
              {analyse.erreurs?.length > 0 && <p className="error">{analyse.erreurs.join(" ; ")}</p>}
              <ul>{analyse.constats.map((c, i) => <li key={i} style={{ color: c.niveau === "critique" ? "var(--danger)" : c.niveau === "alerte" ? "var(--warning)" : "var(--text)" }}>{c.texte}</li>)}</ul>
              <table className="table"><thead><tr><th>VLAN</th><th>Sous-réseau</th><th>SSID</th><th>Terminaux mobiles</th><th>Testé depuis ce VLAN</th><th>Dernier état</th></tr></thead><tbody>
                {analyse.vlans.map((v) => (
                  <tr key={String(v.vlan)}><td>{v.vlan ?? "?"}{v.guest ? " (invité)" : ""}</td><td>{v.subnet || ""}</td><td>{v.ssids.join(", ")}</td>
                    <td>{v.terminaux}{v.fabricants.length ? <small className="muted"> — {v.fabricants.map(([f, n]) => `${f} ×${n}`).join(", ")}</small> : ""}</td>
                    <td>{v.teste ? `✓ ${v.sources.join(", ")}` : v.terminaux ? <span style={{ color: "var(--warning)" }}>non — lancer le script avec IFACE sur ce VLAN</span> : "—"}</td>
                    <td>{v.etat ? <Pastille st={v.etat === "alerte" ? "KO" : "OK"} titre={v.dernier_at ? age(v.dernier_at) : ""} /> : ""}</td></tr>))}
              </tbody></table>
            </>}
          </>}
        </div>
      )}

      {onglet === "listes" && (
        <div className="panel" style={{ marginTop: 10 }}>
          <table className="table"><thead><tr><th>Liste</th><th>Éditeur</th><th>Cibles</th><th>Tests</th><th>Source</th><th /></tr></thead><tbody>
            {listes.map((l) => (
              <tr key={l.id}><td><strong>{l.nom}</strong> <code>-l {l.id}</code></td><td>{l.editeur}</td><td>{l.n_cibles}</td><td>{l.n_tests}</td>
                <td>{l.source ? <a href={l.source} target="_blank" rel="noreferrer">page de l'éditeur ↗</a> : ""}</td>
                <td><a className="button secondary" href={`${nebulaApiBase}/flux/listes/${l.id}.txt`} target="_blank" rel="noreferrer">voir</a>{" "}
                  {!l.integree && <><button type="button" className="secondary" onClick={() => setForm({ id: l.id, nom: l.nom, editeur: l.editeur, source: l.source, texte: l.texte })}>modifier</button>{" "}
                    <button type="button" className="secondary" disabled={!!busy} onClick={() => supprimerListe(l)}>{busy === `del:${l.id}` ? "⏳" : "✕"}</button></>}</td></tr>))}
          </tbody></table>
          {!form && <button type="button" onClick={() => setForm({ nom: "Idruide", editeur: "Idruide", source: "https://aide.idruide.com/s/article/liste-des-ports-reseau-a-ouvrir", texte: "" })}>＋ Nouvelle liste (ex. Idruide)</button>}
          {form && (
            <div className="panel">
              <p><label>Nom <input value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} /></label>{" "}
                <label>Éditeur <input value={form.editeur || ""} onChange={(e) => setForm({ ...form, editeur: e.target.value })} /></label>{" "}
                <label>Page source <input style={{ width: 360 }} value={form.source || ""} onChange={(e) => setForm({ ...form, source: e.target.value })} /></label></p>
              <p className="muted">Coller les domaines et ports de la page de l'éditeur, une cible par ligne : <code>groupe;hôte;proto;ports</code>, ou <code>hôte tcp 443,5223</code>, ou <code>hôte:443</code>. Les adresses https:// sont réduites au nom d'hôte.</p>
              <textarea rows={10} style={{ width: "100%", boxSizing: "border-box", fontFamily: "monospace" }} placeholder={exempleListe(form.nom)} value={form.texte} onChange={(e) => setForm({ ...form, texte: e.target.value })} />
              <p><button type="button" onClick={enregistrerListe} disabled={!!busy || !form.texte.trim()}>{busy === "liste" ? "⏳ enregistrement…" : "Enregistrer"}</button> <button type="button" className="secondary" onClick={() => setForm(null)}>Annuler</button></p>
            </div>
          )}
        </div>
      )}

      {onglet === "installer" && (
        <div className="panel" style={{ marginTop: 10 }}>
          <p>Les tests partent d'une machine <strong>du site</strong> (mini-PC, agent, sonde) : c'est son réseau qui est éprouvé. Lecture seule : DNS, connexion, chiffrement TLS (repère l'inspection SSL), heure NTP.</p>
          <p><label>Interface à tester (vide = route par défaut ; ex. wlp3s0 pour passer par le Wi-Fi des tablettes) <input value={iface} onChange={(e) => setIface(e.target.value.replace(/[^\w.-]/g, ""))} /></label></p>
          <pre className="copiable" style={{ whiteSpace: "pre-wrap" }}>{commandesSite(hubAbs, siteId || "<site>", listes.map((l) => l.id), iface)}</pre>
          <button type="button" className="secondary" onClick={() => setAide({ titre: "Commandes de mise en place", texte: commandesSite(hubAbs, siteId || "<site>", listes.map((l) => l.id), iface) })}>copier dans une fenêtre</button>
          <p className="muted">Un site sans Nebula (ex. le bureau) apparaît en onglet dès son premier envoi : choisir un identifiant court (<code>SITE=bureau</code>).</p>
        </div>
      )}
      {aide && <FenetreTexte titre={aide.titre} texte={aide.texte} onFermer={() => setAide(null)} />}
    </section>
  );
}
