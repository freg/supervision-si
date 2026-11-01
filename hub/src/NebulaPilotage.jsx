// Pilotage du réseau du campus (livraison #855) -- onglet « Pilotage » de la tuile Nebula@<site>.
// Tableau de bord à deux faces : à gauche les MESURES (bornes, sondes, recommandations, banc en cours, journal),
// à droite les OUTILS d'action (réglages Nebula avec lien direct et chemin du menu, boucles de rétroaction activables
// à chaud, scénarios prêts à installer, bancs de test avec injection de flux dans les sondes = clients simulés).
// API : nebula-api /pilotage/* (pilotage_routes.py) ; logique pure : pilotageLib.js.
import { useEffect, useState } from "react";
import { fmt, conditionTexte, sparkPoints, boucleDepuisForm, formDepuisBoucle, progression, manquants, grouperOutils, lignesSondes, lignesBornes, OPS, MODES } from "./pilotageLib.js";

const when = (ts) => (ts ? new Date(ts * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");
const VEILLE = [["Tout va bien", "var(--ok)"], ["Dégradé", "var(--warn, #e8b84a)"], ["PANNE", "var(--danger)"]];
const col = { display: "flex", flexDirection: "column", gap: 12, minWidth: 0 };
const th = { textAlign: "left", fontWeight: 600, padding: "2px 6px", borderBottom: "1px solid var(--border, #263241)" };
const td = { padding: "2px 6px", borderBottom: "1px solid var(--border, #263241)" };
const FORM0 = { nom: "", metrique: "borne.simultanes", cible: "", op: ">", seuil: 25, duree_min: 5, notifier: true, outil: "", banc: "", mode: "conseil", delai_min: 60, actif: false };

async function call(url, opts) {
  const r = await fetch(url, { credentials: "include", ...opts });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `${r.status}`);
  return d;
}

function Spark({ serie, coul = "var(--accent, #4aa3ff)" }) {
  const pts = sparkPoints(serie, 110, 24);
  if (!pts) return <span className="muted">—</span>;
  return <svg width="110" height="24" style={{ verticalAlign: "middle" }} aria-hidden="true"><polyline points={pts} fill="none" stroke={coul} strokeWidth="1.5" /></svg>;
}

function Section({ titre, children, droite }) {
  return (
    <div className="hub-card" style={{ margin: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 8 }}><h3 style={{ margin: 0 }}>{titre}</h3>{droite}</div>
      {children}
    </div>
  );
}

export default function NebulaPilotage({ nebulaApiBase, groups = [], login = "" }) {
  const base = `${nebulaApiBase}/pilotage`;
  const [t, setT] = useState(null);
  const [cat, setCat] = useState(null);
  const [err, setErr] = useState(null);
  const [note, setNote] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(null);           // boucle en création / édition : { id?, ...champs }
  const [reg, setReg] = useState(null);             // réglages en édition
  const [sondes, setSondes] = useState([]);
  const [detail, setDetail] = useState(null);       // exécution de banc ouverte
  const [planJson, setPlanJson] = useState(null);

  const charger = async () => {
    try { setT(await call(`${base}/tableau`)); setErr(null); } catch (e) { setErr(e.message); }
  };
  const chargerCat = async () => { try { setCat(await call(`${base}/catalogue`)); } catch (e) { setErr(e.message); } };
  useEffect(() => { charger(); chargerCat(); const id = setInterval(charger, 30000); return () => clearInterval(id); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [nebulaApiBase]);

  const agir = async (url, methode = "POST", corps = {}, ok = null) => {
    setBusy(true); setNote(null);
    try {
      const r = await call(`${base}${url}`, { method: methode, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups, user: login, ...corps }) });
      if (ok) setNote(["ok", typeof ok === "function" ? ok(r) : ok]);
      await Promise.all([charger(), chargerCat()]);
      setBusy(false);
      return r;
    } catch (e) { setNote(["ko", e.message]); setBusy(false); return null; }
  };

  const ouvrirReglages = async () => {
    setReg({ ...(t?.reglages || {}), urlsTxt: (t?.reglages?.urls || []).join("\n") });
    try { const s = await call(`${base}/sondes`); setSondes(s.sondes || []); if (s.erreur) setNote(["ko", s.erreur]); } catch (e) { setNote(["ko", e.message]); }
  };
  const enregistrerReglages = async () => {
    const r = await agir("/reglages", "PUT", { reglages: { ...reg, urls: reg.urlsTxt.split(/\s+/).filter(Boolean) } }, "Réglages enregistrés.");
    if (r) setReg(null);
  };
  const enregistrerBoucle = async () => {
    const corps = { boucle: boucleDepuisForm(form) };
    const r = form.id ? await agir(`/boucles/${form.id}`, "PUT", corps, "Boucle modifiée.") : await agir("/boucles", "POST", corps, "Boucle créée (inactive tant qu'elle n'est pas activée).");
    if (r) setForm(null);
  };
  const ouvrirRun = async (id) => { if (detail?.id === id) { setDetail(null); return; } try { setDetail(await call(`${base}/runs/${id}`)); } catch (e) { setNote(["ko", e.message]); } };
  const enregistrerPlan = async () => {
    let plan;
    try { plan = JSON.parse(planJson); } catch (e) { setNote(["ko", "JSON invalide : " + e.message]); return; }
    if (await agir("/plans", "POST", { plan }, "Banc enregistré.")) setPlanJson(null);
  };

  if (err && !t) return <div className="hub-card"><p className="muted" style={{ margin: 0 }}>Pilotage indisponible ({err}).</p></div>;
  if (!t || !cat) return <p className="muted">Chargement du pilotage…</p>;

  const v = t.dernier?.valeurs || {};
  const M = cat.metriques || {};
  const outils = Object.fromEntries((cat.outils || []).map((o) => [o.id, o]));
  const plans = cat.plans || [];
  const planDe = (id) => plans.find((p) => p.id === id);
  const niveau = v["veille.niveau"]?.campus;
  const [vlib, vcoul] = VEILLE[niveau] || ["Veille : pas de relevé", "var(--muted, #8fa1b3)"];
  const prog = progression(t.run, planDe(t.run?.plan_id));
  const recos = Object.entries(t.recommandations || {});
  const s = t.series || {};
  const lienOutil = (o, libelle) => (!o ? <span className="muted">pas de lien : opération manuelle</span>
    : o.type === "lien" ? <a href={o.url} target="_blank" rel="noreferrer">{libelle || "Ouvrir dans Nebula ↗"}</a> : <a href={o.url}>{libelle || "Ouvrir ↗"}</a>);
  const setF = (k, x) => setForm((f) => ({ ...f, [k]: x }));
  const setR = (k, x) => setReg((r) => ({ ...r, [k]: x }));

  return (
    <div className="pilotage">
      <style>{".pilotage a { color: var(--accent, #4a9eda); } .pilotage a:visited { color: var(--accent, #4a9eda); }"}</style>
      <div className="hub-card" style={{ borderLeft: `6px solid ${vcoul}`, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ color: vcoul }}>{vlib}</b>
        <span>Wi-Fi : <b>{fmt(v["site.clients_wifi"]?.site)}</b> clients · <b>{fmt(v["site.debit_wifi_mbps"]?.site, "Mb/s")}</b></span>
        <span>Boucles actives : <b>{(t.boucles || []).filter((b) => b.actif).length}</b> / {(t.boucles || []).length}</span>
        <span>Recommandations : <b style={{ color: recos.length ? "var(--warn, #e8b84a)" : undefined }}>{recos.length}</b></span>
        <span style={{ flex: 1 }} className="muted">Relevé {when(t.dernier?.at)}{t.etat?.erreurs?.length ? ` · sources partielles : ${t.etat.erreurs.join(" ; ")}` : ""}</span>
        <button type="button" disabled={busy} onClick={() => agir("/passer", "POST", {}, (r) => `Relevé fait${r.erreurs?.length ? " (sources partielles)" : ""}.`)}>Relever maintenant</button>
      </div>
      {note && <p style={{ color: note[0] === "ok" ? "var(--ok)" : "var(--danger)" }}>{note[1]}</p>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(440px, 1fr))", gap: 16, alignItems: "start" }}>
        {/* ---------------------------------------------------------------- MESURES */}
        <div style={col}>
          <h2 style={{ margin: "4px 0 0" }}>Mesures</h2>

          {prog && (
            <Section titre={`Banc en cours : ${t.run.nom}`} droite={<button type="button" className="danger" disabled={busy} onClick={() => agir("/runs/arreter", "POST", {}, "Banc arrêté, tâches des sondes restaurées.")}>Arrêter</button>}>
              <div>Étape {prog.etape}/{prog.etapes} « {prog.nom} » · {prog.ecoule_min} / {prog.total_min} min · {t.run.engagees?.length || 0} sonde(s) · lancé ({t.run.origine})</div>
              <div style={{ height: 8, background: "var(--border, #263241)", borderRadius: 4, marginTop: 6 }}><div style={{ width: `${prog.pct}%`, height: 8, background: "var(--accent, #4aa3ff)", borderRadius: 4 }} /></div>
            </Section>
          )}

          <Section titre="Recommandations">
            {!recos.length ? <p className="muted" style={{ margin: 0 }}>Aucune : les boucles actives n'ont rien relevé.</p> : recos.map(([id, r]) => (
              <div key={id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "4px 0", borderBottom: "1px solid var(--border, #263241)" }}>
                <b>{r.boucle}</b><span className="muted" style={{ flex: 1, minWidth: 200 }}>{r.detail} · {when(r.at)}</span>
                {r.outil && <span>{outils[r.outil]?.titre} : {lienOutil(outils[r.outil])}</span>}
                {r.banc && <button type="button" disabled={busy || !!t.run} onClick={() => agir(`/plans/${r.banc}/lancer`, "POST", {}, "Banc lancé.")}>Lancer le banc « {planDe(r.banc)?.nom || r.banc} »</button>}
                <button type="button" className="secondary" disabled={busy} onClick={() => agir(`/recommandations/${encodeURIComponent(id)}/acquitter`)}>Acquitter</button>
              </div>))}
          </Section>

          <Section titre="Bornes Wi-Fi (Nebula, 2 h)">
            {!lignesBornes(v).length ? <p className="muted" style={{ margin: 0 }}>Pas de relevé Nebula (clé API, site, ou premier relevé dans la minute).</p> : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><th style={th}>Borne</th><th style={th}>Simultanés</th><th style={th}>Clients</th><th style={th}>Débit</th><th style={th}>Simultanés (4 h)</th></tr></thead>
                <tbody>{lignesBornes(v).map((b) => (<tr key={b.borne}><td style={td}>{b.borne}</td><td style={td}><b>{fmt(b.simultanes)}</b></td><td style={td}>{fmt(b.clients)}</td><td style={td}>{fmt(b.debit, "Mb/s")}</td>
                  <td style={td}><Spark serie={s["borne.simultanes"]?.[b.borne]} /></td></tr>))}</tbody></table>)}
          </Section>

          <Section titre="Sondes (clients simulés, netprobe)">
            {!lignesSondes(v).length ? <p className="muted" style={{ margin: 0 }}>Aucune mesure de sonde de moins de 15 min. Sondes : <a href="?view=netprobe">netprobe ↗</a></p> : (
              <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr>{["Sonde", "Signal", "Latence", "Pertes", "Gigue cast", "Pertes cast", "Débit", "HTTP", "Latence (4 h)"].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
                <tbody>{lignesSondes(v).map((x) => (<tr key={x.sonde}><td style={td}>{x.sonde}</td><td style={td}>{fmt(x.rssi, "dBm")}</td><td style={td}>{fmt(x.rtt, "ms")}</td><td style={td}>{fmt(x.perte, "%")}</td>
                  <td style={td}>{fmt(x.gigue, "ms")}</td><td style={td}>{fmt(x.perte_udp, "%")}</td><td style={td}>{fmt(x.debit, "Mb/s")}</td><td style={td}>{fmt(x.http, "ms")}</td><td style={td}><Spark serie={s["sonde.rtt_ms"]?.[x.sonde]} /></td></tr>))}</tbody></table></div>)}
          </Section>

          <Section titre="Derniers bancs">
            {!(t.runs || []).length ? <p className="muted" style={{ margin: 0 }}>Aucun banc exécuté.</p> : (t.runs || []).map((r) => (
              <div key={r.id} style={{ borderBottom: "1px solid var(--border, #263241)", padding: "4px 0" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <b style={{ color: r.reussi ? "var(--ok)" : r.reussi === false ? "var(--danger)" : undefined }}>{r.reussi ? "✓" : r.reussi === false ? "✗" : r.statut === "en_cours" ? "…" : "?"}</b>
                  <span style={{ flex: 1 }}>{r.nom} · {when(r.debut)} · {r.statut}{r.motif ? ` (${r.motif})` : ""} · {r.origine}</span>
                  <button type="button" className="secondary" onClick={() => ouvrirRun(r.id)}>{detail?.id === r.id ? "Fermer" : "Détail"}</button>
                </div>
                {detail?.id === r.id && detail.synthese && (
                  <div style={{ marginTop: 6 }}>
                    {(detail.synthese.verdicts || []).map((x) => <div key={x.objectif}>{x.ok ? "✓" : x.ok === false ? "✗" : "?"} {x.objectif} : {fmt(x.mesure)} (seuil {x.seuil})</div>)}
                    {(detail.synthese.etapes || []).map((e) => (
                      <div key={e.nom + e.debut} style={{ marginTop: 6 }}>
                        <b>{e.nom}</b> <span className="muted">· {(e.sondes || []).length} sonde(s) · simultanés Nebula max {fmt(e.nebula_simultanes_max)}</span>
                        <table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr>{["Sonde", "Mesures", "Échecs", "Latence", "Pertes", "Gigue", "Pertes cast", "Débit", "HTTP"].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
                          <tbody>{(e.lignes || []).map((l) => <tr key={l.sonde}><td style={td}>{l.sonde}</td><td style={td}>{l.mesures}</td><td style={td}>{l.echecs}</td><td style={td}>{fmt(l.rtt_ms, "ms")}</td><td style={td}>{fmt(l.perte_pct, "%")}</td>
                            <td style={td}>{fmt(l.gigue_ms, "ms")}</td><td style={td}>{fmt(l.perte_udp_pct, "%")}</td><td style={td}>{fmt(l.debit_mbps, "Mb/s")}</td><td style={td}>{fmt(l.http_ms, "ms")}</td></tr>)}</tbody></table>
                      </div>))}
                  </div>)}
              </div>))}
          </Section>

          <Section titre="Journal">
            <div style={{ maxHeight: 260, overflowY: "auto", fontSize: "0.92em" }}>
              {(t.journal || []).map((j, i) => <div key={i}><span className="muted">{when(j.at)}</span> {j.texte}</div>)}
              {!(t.journal || []).length && <span className="muted">Vide.</span>}
            </div>
          </Section>
        </div>

        {/* ---------------------------------------------------------------- ACTIONS */}
        <div style={col}>
          <h2 style={{ margin: "4px 0 0" }}>Actions</h2>

          <Section titre="Outils">
            {grouperOutils(cat.outils).map(([g, l]) => (
              <div key={g} style={{ marginBottom: 8 }}>
                <div className="muted" style={{ textTransform: "uppercase", fontSize: "0.8em", letterSpacing: 1 }}>{g}</div>
                {l.map((o) => (
                  <div key={o.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border, #263241)" }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}><b style={{ flex: 1 }}>{o.titre}</b>{lienOutil(o)}{o.doc && <a href={o.doc} target="_blank" rel="noreferrer" className="muted">doc ↗</a>}</div>
                    {o.chemin && <div style={{ fontFamily: "monospace", fontSize: "0.85em" }}>{o.chemin}</div>}
                    <div className="muted" style={{ fontSize: "0.9em" }}>{o.description}</div>
                  </div>))}
              </div>))}
          </Section>

          <Section titre="Boucles de rétroaction" droite={<button type="button" disabled={busy} onClick={() => setForm({ ...FORM0 })}>Nouvelle boucle</button>}>
            <p className="muted" style={{ marginTop: 0 }}>Activables et commutables à chaud (pris en compte au relevé suivant, moins d'une minute). Conseil : alerte et recommandation, banc proposé ; auto : banc lancé.</p>
            {!(t.boucles || []).length && <p className="muted">Aucune boucle : installer un scénario ci-dessous ou en créer une.</p>}
            {(t.boucles || []).map((b) => {
              const e = t.etats?.[b.id] || {};
              return (
                <div key={b.id} style={{ padding: "6px 0", borderBottom: "1px solid var(--border, #263241)" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <label style={{ display: "flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={!!b.actif} disabled={busy} onChange={(x) => agir(`/boucles/${b.id}/basculer`, "POST", { actif: x.target.checked })} />active</label>
                    <b style={{ flex: 1, color: e.en_cours ? "var(--warn, #e8b84a)" : undefined }}>{b.nom}{e.en_cours ? ` · déclenchée (${(e.cibles || []).join(", ")})` : ""}</b>
                    <select value={b.mode} disabled={busy} onChange={(x) => agir(`/boucles/${b.id}/basculer`, "POST", { mode: x.target.value })}>
                      {Object.keys(MODES).map((m) => <option key={m} value={m}>{m}</option>)}</select>
                    <button type="button" className="secondary" onClick={() => setForm({ id: b.id, ...formDepuisBoucle(b) })}>Modifier</button>
                    <button type="button" className="secondary" disabled={busy} onClick={() => window.confirm(`Supprimer la boucle « ${b.nom} » ?`) && agir(`/boucles/${b.id}`, "DELETE", {}, "Boucle supprimée.")}>Supprimer</button>
                  </div>
                  <div className="muted" style={{ fontSize: "0.9em" }}>Si {conditionTexte(b.condition, M)} → {b.actions.map((a) => a.type === "recommander" ? `recommander « ${outils[a.outil]?.titre || a.outil} »` : a.type === "banc" ? `banc « ${planDe(a.plan)?.nom || a.plan} »` : "notifier").join(", ")} · au plus une fois toutes les {b.delai_min} min{e.dernier ? ` · dernier déclenchement ${when(e.dernier)}` : ""}</div>
                </div>);
            })}
            {form && (
              <div style={{ marginTop: 10, padding: 10, border: "1px solid var(--border, #263241)", borderRadius: 6, display: "grid", gap: 6 }}>
                <b>{form.id ? "Modifier la boucle" : "Nouvelle boucle"}</b>
                <input placeholder="Nom" value={form.nom} onChange={(x) => setF("nom", x.target.value)} />
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>Si
                  <select value={form.metrique} onChange={(x) => setF("metrique", x.target.value)}>{Object.entries(M).map(([k, m]) => <option key={k} value={k}>{m.libelle}</option>)}</select>
                  <input style={{ width: 120 }} placeholder="cible (toutes)" value={form.cible} onChange={(x) => setF("cible", x.target.value)} />
                  <select value={form.op} onChange={(x) => setF("op", x.target.value)}>{OPS.map((o) => <option key={o}>{o}</option>)}</select>
                  <input style={{ width: 70 }} type="number" value={form.seuil} onChange={(x) => setF("seuil", x.target.value)} /> <span>{M[form.metrique]?.unite}</span>
                  <span>pendant</span> <input style={{ width: 60 }} type="number" min="0" value={form.duree_min} onChange={(x) => setF("duree_min", x.target.value)} /> min
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>alors
                  <label><input type="checkbox" checked={form.notifier} onChange={(x) => setF("notifier", x.target.checked)} /> notifier</label>
                  <select value={form.outil} onChange={(x) => setF("outil", x.target.value)}><option value="">(pas de recommandation)</option>{(cat.outils || []).map((o) => <option key={o.id} value={o.id}>recommander : {o.titre}</option>)}</select>
                  <select value={form.banc} onChange={(x) => setF("banc", x.target.value)}><option value="">(pas de banc)</option>{plans.map((p) => <option key={p.id} value={p.id}>banc : {p.nom}</option>)}</select>
                </div>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                  <select value={form.mode} onChange={(x) => setF("mode", x.target.value)}>{Object.entries(MODES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
                  délai entre déclenchements <input style={{ width: 70 }} type="number" min="5" value={form.delai_min} onChange={(x) => setF("delai_min", x.target.value)} /> min
                  {!form.id && <label><input type="checkbox" checked={form.actif} onChange={(x) => setF("actif", x.target.checked)} /> activer tout de suite</label>}
                </div>
                <div style={{ display: "flex", gap: 8 }}><button type="button" disabled={busy || !form.nom.trim()} onClick={enregistrerBoucle}>Enregistrer</button><button type="button" className="secondary" onClick={() => setForm(null)}>Annuler</button></div>
              </div>)}
          </Section>

          <Section titre="Scénarios prêts à installer">
            <p className="muted" style={{ marginTop: 0 }}>Installés inactifs, en mode conseil : à activer dans les boucles ci-dessus.</p>
            {(cat.scenarios || []).map((sc) => (
              <div key={sc.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0", borderBottom: "1px solid var(--border, #263241)" }}>
                <div style={{ flex: 1 }}><b>{sc.nom}</b><div className="muted" style={{ fontSize: "0.9em" }}>{sc.description}</div></div>
                {sc.installe ? <span className="muted">installé</span> : <button type="button" disabled={busy} onClick={() => agir(`/scenarios/${sc.id}/installer`, "POST", {}, (r) => `Installé : ${[...r.boucles, ...r.plans].join(", ") || "rien de nouveau"}.`)}>Installer</button>}
              </div>))}
          </Section>

          <Section titre="Bancs de test (injection, clients simulés)" droite={<button type="button" className="secondary" onClick={() => setPlanJson(planJson === null ? JSON.stringify({ id: "mon-banc", nom: "Mon banc", description: "", arret_si_panne: true,
            etapes: [{ nom: "Étape 1", duree_min: 5, sondes: "toutes", taches: [{ type: "ping", params: { host: "{cible}", count: 5 }, every: 10 }] }], objectifs: { rtt_ms: 80 } }, null, 2) : null)}>{planJson === null ? "Nouveau banc" : "Fermer"}</button>}>
            <p className="muted" style={{ marginTop: 0 }}>Chaque sonde autorisée devient un client simulé : flux UDP type cast, téléchargements TCP parallèles, navigation HTTP, DNS, ping. Tâches d'origine restaurées à la fin ; arrêt automatique si la veille passe en panne. Plafonds : {cat.plafonds?.duree_totale_min} min, {cat.plafonds?.bitrate_mbit} Mb/s UDP, {cat.plafonds?.parallel} flux TCP par sonde.</p>
            {!plans.length && <p className="muted">Aucun banc : installer un scénario (« Cast dégradé », « Latence », « Bancs de pointe »).</p>}
            {plans.map((p) => {
              const manque = manquants(p, t.reglages);
              return (
                <div key={p.id} style={{ padding: "6px 0", borderBottom: "1px solid var(--border, #263241)" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <b style={{ flex: 1 }}>{p.nom}</b>
                    <button type="button" disabled={busy || !!t.run || manque.length > 0} title={manque.length ? `Réglages manquants : ${manque.join(", ")}` : ""} onClick={() => window.confirm(`Lancer le banc « ${p.nom} » (${p.etapes.reduce((n, e) => n + e.duree_min, 0)} min) ?`) && agir(`/plans/${p.id}/lancer`, "POST", {}, "Banc lancé.")}>Lancer</button>
                    <button type="button" className="secondary" onClick={() => setPlanJson(JSON.stringify(p, null, 2))}>Modifier</button>
                    <button type="button" className="secondary" disabled={busy || t.run?.plan_id === p.id} onClick={() => window.confirm(`Supprimer le banc « ${p.nom} » ?`) && agir(`/plans/${p.id}`, "DELETE", {}, "Banc supprimé.")}>Supprimer</button>
                  </div>
                  <div className="muted" style={{ fontSize: "0.9em" }}>{p.description}</div>
                  <div style={{ fontSize: "0.9em" }}>{p.etapes.map((e) => `${e.nom} (${e.duree_min} min, sondes : ${e.sondes}, ${e.taches.map((x) => x.type + (x.params?.udp ? " UDP" : "")).join(" + ")})`).join(" → ")}
                    {Object.keys(p.objectifs || {}).length > 0 && <span className="muted"> · objectifs : {Object.entries(p.objectifs).map(([k, x]) => `${k} ${x}`).join(", ")}</span>}</div>
                  {manque.length > 0 && <div style={{ color: "var(--warn, #e8b84a)", fontSize: "0.9em" }}>À régler avant de lancer : {manque.join(", ")}</div>}
                </div>);
            })}
            {planJson !== null && (
              <div style={{ marginTop: 8 }}>
                <p className="muted" style={{ margin: "0 0 4px" }}>Banc en JSON : tâches iperf3 (host, port, udp, bitrate_mbit, reverse, parallel, duration), ping (host, count), http (url), dns (name), wifi_link ; paramètres {"{serveur}"} {"{cible}"} {"{url}"} {"{nom}"} pris dans les réglages ; sondes : toutes, moitie, un nombre ou une liste ; objectifs : perte_udp_pct, gigue_ms, rtt_ms, http_ms, debit_min_mbps.</p>
                <textarea rows={14} style={{ width: "100%", fontFamily: "monospace" }} value={planJson} onChange={(x) => setPlanJson(x.target.value)} />
                <button type="button" disabled={busy} onClick={enregistrerPlan}>Enregistrer le banc</button>
              </div>)}
          </Section>

          <Section titre="Réglages" droite={!reg && <button type="button" className="secondary" onClick={ouvrirReglages}>Modifier</button>}>
            {!reg ? (
              <div style={{ fontSize: "0.95em" }}>
                <div>Sondes autorisées pour les bancs : {(t.reglages?.sondes || []).join(", ") || <span style={{ color: "var(--warn, #e8b84a)" }}>aucune</span>}</div>
                <div>Serveur iperf3 : {t.reglages?.serveur_iperf || <span className="muted">non réglé</span>} · cible du ping : {t.reglages?.cible_ping || <span className="muted">non réglée</span>}</div>
                <div>Adresses à charger : {(t.reglages?.urls || []).join(", ") || <span className="muted">aucune</span>}</div>
                <div className="muted">Serveur iperf3 : un « iperf3 -s -p 5201 » et un « iperf3 -s -p 5202 » sur une machine du campus (le banc « pointe » utilise les deux). Pas de lien : opération manuelle.</div>
              </div>
            ) : (
              <div style={{ display: "grid", gap: 6 }}>
                <div>Sondes autorisées (chacune = un client simulé) :
                  {!sondes.length && <span className="muted"> aucune sonde netprobe ; enrôler des sondes : <a href="?view=netprobe">netprobe ↗</a></span>}
                  {sondes.map((x) => <label key={x.agent_id} style={{ display: "block" }}><input type="checkbox" checked={(reg.sondes || []).includes(x.agent_id)}
                    onChange={(e) => setR("sondes", e.target.checked ? [...(reg.sondes || []), x.agent_id] : (reg.sondes || []).filter((a) => a !== x.agent_id))} /> {x.label}{x.site ? ` (${x.site})` : ""}{x.active === false ? " · inactive" : ""}</label>)}
                </div>
                <label>Serveur iperf3 <input value={reg.serveur_iperf || ""} placeholder="192.0.2.10" onChange={(e) => setR("serveur_iperf", e.target.value)} /></label>
                <label>Cible du ping <input value={reg.cible_ping || ""} placeholder="passerelle du VLAN" onChange={(e) => setR("cible_ping", e.target.value)} /></label>
                <label>Adresses à charger (une par ligne)<textarea rows={3} style={{ width: "100%" }} value={reg.urlsTxt} onChange={(e) => setR("urlsTxt", e.target.value)} /></label>
                <div style={{ display: "flex", gap: 8 }}><button type="button" disabled={busy} onClick={enregistrerReglages}>Enregistrer</button><button type="button" className="secondary" onClick={() => setReg(null)}>Annuler</button></div>
              </div>)}
          </Section>
        </div>
      </div>
    </div>
  );
}
