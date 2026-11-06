// Registre des équipements d'un site (#960) : report au bureau des notes de terrain — nom, rôle, IP, MAC, position sur le
// plan, local, prise, étiquettes libres (« clé:valeur » pour les catégories à venir). Rapprochement Nebula (où est branché,
// fabricant, IP/MAC vues) et doublons signalés. API : nebula-api /sites/<site>/reperage/equipements*. Logique : reperageLib.js.
// #973 : plan réduit / étendu à gauche (toujours visible), tableau à droite (en-tête fixe, défilement propre, colonnes
// réglables), fiche de saisie à la demande (panneau), calque du plan (espaces, étiquettes) avec vue symbolique, remontée
// d'un terminal vers ses équipements amont (synoptique Nebula).
import { useCallback, useEffect, useMemo, useState } from "react";
import Plan from "./PlanSite.jsx";
import BoutonDetail from "./FenetreTexte.jsx";
import ParcSite from "./ParcSite.jsx";   // #971
import CalendrierActivite from "./CalendrierActivite.jsx";   // #976
import { useTableColumns, ColumnsMenu, TableColumnsHead } from "./TableColumns.jsx";
import { hubLink } from "./hubLinks.js";
import { KIND_LABEL } from "./nebulaTree.js";
import { SITE_KEY, filtrerEquipements, couleurRole, initiales, suggestionNebula, EQUIPEMENT_VIDE, versFormulaire, chaineAmont } from "./reperageLib.js";
import { TYPES_FORME, TYPES_ETIQUETTE, CALQUE_VIDE, normaliserCalque, cliquerTrace, ajouterForme, ajouterEtiquette, retirer, renommer, espaceDe } from "./planCalqueLib.js";

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
const ch = { width: "100%", boxSizing: "border-box" };
const LARGEURS = { reduit: "34%", etendu: "62%" };

const COLONNES = [
  { id: "nom", label: "Nom", fixed: true },
  { id: "role", label: "Rôle" },
  { id: "categorie", label: "Catégorie", defaultHidden: true },
  { id: "ip", label: "IP" },
  { id: "mac", label: "MAC" },
  { id: "local", label: "Local / prise" },
  { id: "espace", label: "Espace (plan)", defaultHidden: true },
  { id: "lab", label: "Lab", defaultHidden: true },
  { id: "modele", label: "Modèle", defaultHidden: true },
  { id: "serie", label: "N° de série", defaultHidden: true },
  { id: "compte", label: "Compte", defaultHidden: true },
  { id: "tags", label: "Étiquettes" },
  { id: "nebula", label: "Nebula" },
  { id: "plan", label: "Plan" },
];

export default function EquipementsSiteView({ onBack, nebulaApiBase, actor }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(() => store.get(SITE_KEY, ""));
  const [data, setData] = useState(null);           // {equipements, roles, tags, locaux, erreurs}
  const [inv, setInv] = useState(null);             // inventaire Nebula (suggestions de saisie)
  const [form, setForm] = useState(EQUIPEMENT_VIDE);
  const [ficheOuverte, setFicheOuverte] = useState(false);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [sansPos, setSansPos] = useState(false);
  const [importOuvert, setImportOuvert] = useState(false);
  const [importTexte, setImportTexte] = useState("");
  const [parcOuvert, setParcOuvert] = useState(false);   // #971
  // #973 : plan et calque
  const [largeur, setLargeur] = useState(() => store.get("hub.equipements.plan", "reduit"));
  const [symbolique, setSymbolique] = useState(() => store.get("hub.equipements.symbolique", false));
  const [calque, setCalque] = useState(CALQUE_VIDE);
  const [calqueModifie, setCalqueModifie] = useState(false);
  const [outil, setOutil] = useState(null);          // null | espace | etiquette | renommer | gomme
  const [typeForme, setTypeForme] = useState("espace");
  const [typeEtiquette, setTypeEtiquette] = useState("espace");
  const [texte, setTexte] = useState("");
  const [trace, setTrace] = useState([]);
  const [amont, setAmont] = useState(null);         // {id, chaine, erreur}
  const [activite, setActivite] = useState(false);   // #976 : calendrier d'activité de la fiche ouverte
  const t = useTableColumns("equipements-site", COLONNES);
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;

  useEffect(() => {
    getJson(`${nebulaApiBase}/reperage/sites`).then((d) => { const s = d.sites || []; setSites(s); if (!siteId && s[0]) setSiteId(s[0].site_id); }).catch((e) => setMsg({ ok: false, text: "Nebula : " + e.message }));
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [nebulaApiBase]);
  useEffect(() => { if (siteId) store.set(SITE_KEY, siteId); }, [siteId]);
  useEffect(() => { store.set("hub.equipements.plan", largeur); }, [largeur]);
  useEffect(() => { store.set("hub.equipements.symbolique", symbolique); }, [symbolique]);

  const charger = useCallback(async () => {
    if (!siteId) return;
    try { setData(await getJson(`${base}/reperage/equipements`)); } catch (e) { setMsg({ ok: false, text: e.message }); }
    getJson(`${base}/reperage/inventaire?period=1d`).then(setInv).catch(() => setInv(null));
  }, [base, siteId]);
  const chargerCalque = useCallback(() => {
    if (!siteId) return;
    getJson(`${base}/reperage/calque`).then((c) => { setCalque(normaliserCalque(c)); setCalqueModifie(false); }).catch(() => setCalque(CALQUE_VIDE));
  }, [base, siteId]);
  useEffect(() => { setData(null); setForm(EQUIPEMENT_VIDE); setFicheOuverte(false); setAmont(null); charger(); chargerCalque(); }, [charger, chargerCalque]);

  const eqs = data?.equipements || [];
  const roles = data?.roles || [];
  const liste = useMemo(() => filtrerEquipements(eqs, { q, tag, sansPosition: sansPos }), [eqs, q, tag, sansPos]);
  const sugg = useMemo(() => (form.id ? null : suggestionNebula(inv, { mac: form.mac, ip: form.ip })), [inv, form.mac, form.ip, form.id]);
  const courant = form.id ? eqs.find((e) => e.id === form.id) : null;

  const ouvrir = (f) => { setForm(f); setFicheOuverte(true); setAmont(null); };
  const ouvrirId = (id) => { const e = eqs.find((x) => x.id === id); if (e) ouvrir(versFormulaire(e)); };
  const fermer = () => { setFicheOuverte(false); setAmont(null); };

  const enregistrer = async (suivant) => {
    setBusy("enregistrer"); setMsg(null);
    try {
      const e = await getJson(`${base}/reperage/equipements`, corps("PUT", { ...form, par: actor }));
      setMsg({ ok: true, text: `✓ ${e.nom || e.ip || e.mac} enregistré${e.nebula ? ` — Nebula : ${e.nebula.ou || "vu"}` : ""}${e.alertes?.length ? ` — ⚠ ${e.alertes.join(" ; ")}` : ""}` });
      await charger();
      setForm(suivant ? { ...EQUIPEMENT_VIDE, local: form.local, role: form.role, tags: form.tags } : versFormulaire(e));
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(null); }
  };
  const supprimer = async () => {
    if (!form.id || !window.confirm(`Supprimer « ${form.nom || form.ip || form.mac} » du registre ?`)) return;
    setBusy("supprimer");
    try { await getJson(`${base}/reperage/equipements/${form.id}`, { method: "DELETE" }); setForm(EQUIPEMENT_VIDE); setFicheOuverte(false); await charger(); setMsg({ ok: true, text: "✓ supprimé" }); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(null); }
  };
  const importer = async () => {
    setBusy("import"); setMsg(null);
    try {
      const r = await getJson(`${base}/reperage/equipements/import`, corps("POST", { texte: importTexte }));
      setMsg({ ok: !r.erreurs?.length, text: `✓ ${r.ajoutes} ajouté(s), ${r.mis_a_jour} mis à jour${r.erreurs?.length ? ` — ${r.erreurs.length} ligne(s) refusée(s) : ${r.erreurs.join(" ; ")}` : ""}` });
      setImportTexte(""); setImportOuvert(false); await charger();
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(null); }
  };

  // -- #973 : remontée vers l'amont ---------------------------------------------------------------------------------------
  const remonter = async () => {
    if (!courant) return;
    setBusy("amont"); setAmont(null);
    try {
      const tree = await getJson(`${base}/topology?period=1d`);
      let appareil = "";
      const macs = [courant.mac, ...(courant.macs || [])].filter(Boolean);
      if (!(tree.nodes || []).some((n) => (n.clients || []).some((c) => macs.includes(String(c.mac || "").toLowerCase().replace(/-/g, ":"))))) {
        const h = await getJson(`${base}/reperage/parc/terminal/${courant.id}?jours=30`).catch(() => null);   // dernier appareil connu
        appareil = h?.lieux?.length ? h.lieux[h.lieux.length - 1].borne || "" : "";
      }
      const chaine = chaineAmont(tree, { macs, appareil }, eqs);
      setAmont({ id: courant.id, chaine, erreur: chaine.length ? null : "terminal introuvable dans le synoptique ni dans l'historique des clients (jamais vu sur le réseau, ou MAC absente de la fiche)" });
    } catch (err) { setAmont({ id: courant.id, chaine: [], erreur: "synoptique indisponible : " + err.message }); }
    finally { setBusy(null); }
  };
  const chaineIds = new Set((amont?.chaine || []).map((c) => c.fiche?.id).filter(Boolean));
  const liens = [];
  if (amont?.chaine?.length && courant?.x != null) {
    let prec = courant;
    for (const c of amont.chaine) {
      const f = c.fiche && eqs.find((e) => e.id === c.fiche.id);
      if (f?.x != null) { liens.push([prec.x, prec.y, f.x, f.y]); prec = f; }
    }
  }

  // -- #973 : calque du plan ----------------------------------------------------------------------------------------------
  const modifierCalque = (c) => { setCalque(c); setCalqueModifie(true); };
  const clicPlan = (f) => {
    if (outil === "espace") {
      const r = cliquerTrace(trace, [f.x, f.y]);
      if (!r.ferme) { setTrace(r.points); return; }
      modifierCalque(ajouterForme(calque, { type: typeForme, nom: texte, points: r.points }));
      setTrace([]); setTexte("");
      return;
    }
    if (outil === "etiquette") {
      if (!texte.trim()) { setMsg({ ok: false, text: "Étiquette : saisir d'abord son texte dans la barre du calque, puis cliquer le plan." }); return; }
      modifierCalque(ajouterEtiquette(calque, { type: typeEtiquette, texte, x: f.x, y: f.y }));
      setTexte("");
      return;
    }
    if (outil) return;
    if (ficheOuverte) setForm({ ...form, x: f.x, y: f.y });
  };
  const clicElement = outil === "gomme" ? (id) => modifierCalque(retirer(calque, id))
    : outil === "renommer" ? (id) => { if (texte.trim()) { modifierCalque(renommer(calque, id, texte.trim())); setTexte(""); } else setMsg({ ok: false, text: "Renommer : saisir le nouveau nom, puis cliquer l'espace ou l'étiquette." }); }
    : null;
  const enregistrerCalque = async () => {
    setBusy("calque");
    try { setCalque(normaliserCalque(await getJson(`${base}/reperage/calque`, corps("PUT", { ...calque, par: actor })))); setCalqueModifie(false); setMsg({ ok: true, text: "✓ calque du plan enregistré" }); }
    catch (err) { setMsg({ ok: false, text: "Calque : " + err.message }); }
    finally { setBusy(null); }
  };
  const choisirOutil = (o) => { setOutil(outil === o ? null : o); setTrace([]); };

  const champ = (k) => ({ value: form[k] ?? "", onChange: (e) => setForm({ ...form, [k]: e.target.value }), onKeyDown: (e) => { if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") enregistrer(!form.id); } });
  const marqueurs = liste.filter((e) => e.x != null).map((e) => ({
    key: e.id, x: e.x, y: e.y, texte: initiales(e), taille: 26, couleur: couleurRole(e.role, roles),
    titre: `${e.nom || ""} · ${e.role || ""} · ${e.ip || ""} ${e.mac || ""}`, onClick: outil ? null : () => ouvrir(versFormulaire(e)),
  }));
  if (ficheOuverte && form.x != null && !form.id) marqueurs.push({ key: "_nouveau", x: form.x, y: form.y, texte: "+", taille: 26, couleur: "var(--text)", titre: "nouvelle fiche" });
  if (form.id && courant && (form.x !== courant.x || form.y !== courant.y) && form.x != null) {
    const m = marqueurs.find((x) => x.key === form.id); if (m) { m.x = form.x; m.y = form.y; } else marqueurs.push({ key: form.id, x: form.x, y: form.y, texte: "↦", taille: 26, couleur: "var(--text)" });
  }

  const cellule = {
    nom: (e) => <strong>{e.nom || "—"}</strong>,
    role: (e) => <><span style={{ color: couleurRole(e.role, roles) }}>●</span> {e.role || ""}</>,
    categorie: (e) => e.categorie || "",
    ip: (e) => e.ip || "",
    mac: (e) => <><code>{e.mac || ""}</code>{e.macs?.length > 1 && <BoutonDetail texte={e.macs.join("\n")} titre={`MAC de ${e.nom || e.ip}`} urgence="info" libelle={`+${e.macs.length - 1}`} />}</>,
    local: (e) => `${e.local || ""}${e.prise ? ` · ${e.prise}` : ""}`,
    espace: (e) => espaceDe(calque, e.x, e.y) || "",
    lab: (e) => e.lab || "",
    modele: (e) => [e.designation, e.modele].filter(Boolean).join(" · "),
    serie: (e) => e.serie || "",
    compte: (e) => e.compte || "",
    tags: (e) => (e.tags || []).join(", "),
    nebula: (e) => <>{e.nebula ? <small>{e.nebula.ou || "vu"}</small> : <small className="muted">non vu</small>}{" "}
      {e.alertes?.length > 0 && <BoutonDetail texte={e.alertes.join("\n")} titre={`Écarts : ${e.nom || e.ip || e.mac}`} urgence="alerte" libelle="⚠" />}</>,
    plan: (e) => (e.x != null ? "📍" : ""),
  };

  return (
    <section className="view equipements-site">
      <style>{`.eq-defile thead th { position: sticky !important; top: 0; z-index: 3; background: var(--panel); }
        .eq-defile td, .eq-defile th { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }`}</style>
      <header className="view-header" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <h1 style={{ margin: 0 }}>🗂 Équipements du site</h1>
        <select value={siteId} onChange={(e) => setSiteId(e.target.value)} aria-label="site">
          {!siteId && <option value="">— site —</option>}
          {sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.name}</option>)}
        </select>
        <input placeholder="rechercher (nom, IP, MAC, rôle, local…)" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 220 }} />
        <select value={tag} onChange={(e) => setTag(e.target.value)} aria-label="étiquette"><option value="">toutes étiquettes</option>{(data?.tags || []).map((x) => <option key={x} value={x}>{x}</option>)}</select>
        <label><input type="checkbox" checked={sansPos} onChange={(e) => setSansPos(e.target.checked)} /> sans position</label>
        <button type="button" onClick={() => ouvrir(EQUIPEMENT_VIDE)}>＋ Équipement</button>
        <button type="button" className="secondary" onClick={() => setImportOuvert(!importOuvert)}>📥 Importer</button>
        <button type="button" className={parcOuvert ? "" : "secondary"} onClick={() => setParcOuvert(!parcOuvert)}>📊 Parc, baux, déplacements</button>
        <a className="button secondary" href={hubLink("nebula", { tab: "vlan" })} title="Synoptique du réseau (passerelle, commutateurs, bornes, clients)">🗺 Synoptique</a>
        {siteId && <a className="button secondary" href={`${base}/reperage/equipements.csv`} download>⬇ CSV</a>}
      </header>
      {msg && <p className={msg.ok ? "ok" : "error"}>{msg.text}</p>}
      {data?.erreurs?.length > 0 && <p className="muted">Nebula partiel : {data.erreurs.join(" ; ")} (la saisie reste possible)</p>}
      {importOuvert && (
        <div className="panel">
          <p>Coller un tableau (tableur, CSV `;` `,` ou tabulations) avec une ligne d'en-tête : <code>nom ; role ; ip ; mac ; local ; prise ; tags ; note</code>, et pour un inventaire de parc : <code>catégorie ; type ; désignation ; modèle ; n° de série ; lab ; stockage ; compte ; profil ; parcours ; mise en service</code>. Une ligne dont la MAC, l'IP ou le n° de série existe déjà complète la fiche ; sans MAC ni IP, c'est le nom qui fait le lien.</p>
          <textarea rows={6} style={ch} value={importTexte} onChange={(e) => setImportTexte(e.target.value)} />
          <p><input type="file" accept=".csv,.txt,.tsv" onChange={(e) => { const f = e.target.files?.[0]; if (f) f.text().then(setImportTexte); }} />{" "}
            <button type="button" onClick={importer} disabled={!importTexte.trim() || !!busy}>{busy === "import" ? "⏳ import…" : "Importer"}</button></p>
        </div>
      )}

      {parcOuvert && siteId && <ParcSite base={base} actor={actor} selection={form.id} onChange={charger} onOuvrir={ouvrirId} onInscrire={(f) => ouvrir(f)} />}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* plan : réduit / étendu, bord droit étirable, reste visible pendant le défilement du tableau */}
        <div style={{ width: LARGEURS[largeur] || LARGEURS.reduit, minWidth: 260, maxWidth: "100%", flex: "0 0 auto", position: "sticky", top: 8, resize: "horizontal", overflow: "auto" }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 6 }}>
            <button type="button" className="secondary" onClick={() => setLargeur(largeur === "etendu" ? "reduit" : "etendu")} title="Plan réduit / étendu (le bord bas-droit s'étire aussi)">{largeur === "etendu" ? "⤡ Réduire" : "⤢ Étendre"}</button>
            <button type="button" className={symbolique ? "" : "secondary"} onClick={() => setSymbolique(!symbolique)} title="Estompe l'image : ne restent que les espaces, étiquettes et équipements">◱ Symbolique</button>
            <button type="button" className={outil || calqueModifie ? "" : "secondary"} onClick={() => choisirOutil(outil ? null : "espace")}>✏️ Calque</button>
            {calqueModifie && <button type="button" onClick={enregistrerCalque} disabled={!!busy}>{busy === "calque" ? "⏳ enregistrement…" : "💾 Enregistrer le calque"}</button>}
          </div>
          {(outil || calqueModifie) && (
            <div className="panel" style={{ padding: 8, marginBottom: 6, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
              <button type="button" className={outil === "espace" ? "" : "secondary"} onClick={() => choisirOutil("espace")} title="Cliquer les angles ; recliquer le premier point ferme le polygone">▱ Délimiter</button>
              {outil === "espace" && <select value={typeForme} onChange={(e) => setTypeForme(e.target.value)}>{TYPES_FORME.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>}
              <button type="button" className={outil === "etiquette" ? "" : "secondary"} onClick={() => choisirOutil("etiquette")}>🏷 Étiquette</button>
              {outil === "etiquette" && <select value={typeEtiquette} onChange={(e) => setTypeEtiquette(e.target.value)}>{TYPES_ETIQUETTE.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>}
              <button type="button" className={outil === "renommer" ? "" : "secondary"} onClick={() => choisirOutil("renommer")}>✎ Renommer</button>
              <button type="button" className={outil === "gomme" ? "" : "secondary"} onClick={() => choisirOutil("gomme")}>⌫ Effacer</button>
              {(outil === "espace" || outil === "etiquette" || outil === "renommer") && (
                <input value={texte} onChange={(e) => setTexte(e.target.value)} style={{ minWidth: 140 }}
                  placeholder={outil === "espace" ? "nom de l'espace" : outil === "renommer" ? "nouveau nom" : typeEtiquette === "spot" ? "nom de la borne (Nebula)" : "texte"} />)}
              {outil === "espace" && trace.length > 0 && <>
                <button type="button" className="secondary" onClick={() => setTrace(trace.slice(0, -1))}>↶ point</button>
                {trace.length >= 3 && <button type="button" className="secondary" onClick={() => clicPlan({ x: trace[0][0], y: trace[0][1] })}>⟲ fermer</button>}
                <button type="button" className="secondary" onClick={() => setTrace([])}>annuler le tracé</button></>}
              {calqueModifie && <button type="button" className="secondary" onClick={chargerCalque} disabled={!!busy}>↺ abandonner les modifications</button>}
              <small className="muted" style={{ flexBasis: "100%" }}>
                {outil === "espace" ? `Cliquer les angles de l'espace (${trace.length} point${trace.length > 1 ? "s" : ""}) ; recliquer le premier point (ou « fermer ») termine le polygone.`
                  : outil === "etiquette" ? "Saisir le texte, puis cliquer le plan. Un « spot » au nom d'une borne Nebula situe la borne : sa pièce sert aux déplacements."
                    : outil === "renommer" ? "Saisir le nouveau nom, puis cliquer un espace ou une étiquette."
                      : outil === "gomme" ? "Cliquer un espace ou une étiquette pour l'effacer." : "Choisir un outil."}
                {" "}{calque.formes.length} espace(s)/zone(s), {calque.etiquettes.length} étiquette(s){calqueModifie ? " — non enregistré" : ""}.</small>
            </div>
          )}
          <Plan base={base} version={0} marqueurs={marqueurs} selection={ficheOuverte ? form.id || "_nouveau" : null} onPoser={clicPlan}
            calque={calque} symbolique={symbolique} trace={outil === "espace" ? trace : null} liens={liens} surligne={chaineIds}
            onForme={clicElement} onEtiquette={clicElement} />
          <p className="muted" style={{ marginTop: 4, fontSize: 12 }}>
            {outil ? "Mode calque : les clics dessinent." : ficheOuverte ? "Cliquer le plan place la fiche ouverte." : "Cliquer un marqueur ou une ligne ouvre la fiche."}{" "}
            {eqs.filter((e) => e.x != null).length}/{eqs.length} positionné(s).</p>
        </div>

        {/* tableau : en-tête fixe, défilement vertical et horizontal dans son cadre */}
        <div style={{ flex: "1 1 320px", minWidth: 0 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <span className="muted">{liste.length} / {eqs.length} équipement(s)</span>
            <span style={{ marginLeft: "auto" }}><ColumnsMenu t={t} /></span>
          </div>
          <div className="eq-defile" style={{ maxHeight: "calc(100vh - 220px)", minHeight: 240, overflow: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
            <table className="table" style={{ margin: 0, ...(t.tableStyle || {}) }}>
              <TableColumnsHead t={t} />
              <tbody>
                {liste.map((e) => (
                  <tr key={e.id} onClick={() => ouvrir(versFormulaire(e))} style={{ cursor: "pointer", outline: ficheOuverte && form.id === e.id ? "2px solid var(--accent)" : "none" }}>
                    {t.visible.map((c) => <td key={c.id}>{cellule[c.id](e)}</td>)}
                  </tr>
                ))}
                {!liste.length && <tr><td colSpan={t.visible.length} className="muted">{eqs.length ? "aucun équipement avec ces filtres" : "registre vide : « ＋ Équipement » ou « 📥 Importer »"}</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {ficheOuverte && (
        <div className="panel" role="dialog" aria-label="fiche équipement"
          style={{ position: "fixed", right: 16, top: 72, width: "min(380px, calc(100vw - 32px))", maxHeight: "calc(100vh - 96px)", overflow: "auto", zIndex: 40, boxShadow: "0 8px 28px var(--bg)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h3 style={{ margin: 0, flex: 1 }}>{form.id ? `Fiche : ${form.nom || form.ip || form.mac}` : "Nouvel équipement"}</h3>
            <button type="button" className="secondary" onClick={fermer} aria-label="fermer la fiche">✕</button>
          </div>
          <label>Nom<input style={ch} {...champ("nom")} autoFocus placeholder="ex. Écran accueil" /></label>
          <label>Rôle<input style={ch} list="eq-roles" {...champ("role")} placeholder="affichage, caméra, serveur…" /></label>
          <datalist id="eq-roles">{roles.map((r) => <option key={r} value={r} />)}</datalist>
          <label>IP<input style={ch} {...champ("ip")} placeholder="172.16.20.10" inputMode="decimal" /></label>
          <label>MAC<input style={ch} {...champ("mac")} placeholder="aa:bb:cc:dd:ee:ff" /></label>
          {sugg && (sugg.ip !== form.ip || sugg.mac !== form.mac || (!form.nom && sugg.nom)) && (
            <p className="muted">Nebula : {sugg.mac} · {sugg.ip || "sans IP"}{sugg.nom ? ` · ${sugg.nom}` : ""}{sugg.fabricant ? ` · ${sugg.fabricant}` : ""}{" "}
              <button type="button" className="secondary" onClick={() => setForm({ ...form, mac: form.mac && form.mac.replace(/[^0-9a-f]/gi, "").length === 12 ? form.mac : sugg.mac, ip: form.ip || sugg.ip || "", nom: form.nom || sugg.nom || "" })}>compléter</button></p>
          )}
          <label>Local<input style={ch} list="eq-locaux" {...champ("local")} placeholder={espaceDe(calque, form.x, form.y) || "pièce, étage"} /></label>
          <datalist id="eq-locaux">{[...new Set([...(data?.locaux || []), ...calque.formes.map((f) => f.nom).filter(Boolean)])].map((r) => <option key={r} value={r} />)}</datalist>
          <label>Prise<input style={ch} {...champ("prise")} placeholder="B-12" /></label>
          <label>Étiquettes<input style={ch} list="eq-tags" {...champ("tags")} placeholder="critique, vlan:20, propriétaire:sempat" /></label>
          <datalist id="eq-tags">{(data?.tags || []).map((r) => <option key={r} value={r} />)}</datalist>
          <label>Note<textarea style={ch} rows={2} value={form.note || ""} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
          <p className="muted" style={{ margin: "4px 0" }}>Position : {form.x != null ? `posée (${Math.round(form.x * 100)} %, ${Math.round(form.y * 100)} %)${espaceDe(calque, form.x, form.y) ? ` · espace ${espaceDe(calque, form.x, form.y)}` : ""}` : "cliquer sur le plan"}
            {form.x != null && <> <button type="button" className="secondary" onClick={() => setForm({ ...form, x: null, y: null })}>retirer du plan</button></>}</p>
          {courant?.nebula && <p className="muted" style={{ margin: "4px 0" }}>Nebula ({courant.nebula.par === "mac" ? "par MAC" : "par IP"}) : {courant.nebula.ou || "vu"}{courant.nebula.fabricant ? ` · ${courant.nebula.fabricant}` : ""}{courant.nebula.vlan ? ` · VLAN ${courant.nebula.vlan}` : ""}</p>}
          {courant?.alertes?.length > 0 && <p className="error" style={{ margin: "4px 0" }}>⚠ {courant.alertes.join(" ; ")}</p>}
          <p style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {!form.id && <button type="button" onClick={() => enregistrer(true)} disabled={!!busy} title="Entrée : garde local, rôle et étiquettes pour la fiche suivante">{busy === "enregistrer" ? "⏳ enregistrement…" : "Enregistrer et suivant"}</button>}
            <button type="button" className={form.id ? "" : "secondary"} onClick={() => enregistrer(false)} disabled={!!busy}>{busy === "enregistrer" && form.id ? "⏳ enregistrement…" : "Enregistrer"}</button>
            <button type="button" className="secondary" onClick={() => setForm(EQUIPEMENT_VIDE)} disabled={!!busy}>Nouveau</button>
            {form.id && <button type="button" className="secondary" onClick={supprimer} disabled={!!busy}>{busy === "supprimer" ? "⏳" : "Supprimer"}</button>}
          </p>
          {courant && (
            <div style={{ borderTop: "1px solid var(--border)", paddingTop: 6 }}>
              <p style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "4px 0" }}>
                <button type="button" className="secondary" onClick={remonter} disabled={!!busy}>{busy === "amont" ? "⏳ remontée…" : "⬆ Remonter vers l'amont"}</button>
                {courant.mac && <a className="button secondary" href={hubLink("nebula", { tab: "vlan", mac: courant.mac })}>🗺 dans le synoptique</a>}
                <button type="button" className={activite ? "" : "secondary"} onClick={() => setActivite(!activite)}>📅 Activité</button>
              </p>
              {activite && <CalendrierActivite key={courant.id} base={base} eid={courant.id} />}
              {amont?.id === courant.id && amont.erreur && <p className="muted">{amont.erreur}</p>}
              {amont?.id === courant.id && amont.chaine.length > 0 && (
                <ol style={{ margin: "4px 0", paddingLeft: 20 }}>
                  <li><strong>{courant.nom || courant.mac}</strong> <span className="muted">{amont.chaine[0].connecte ? "(connecté)" : "(dernier raccordement connu)"}</span></li>
                  {amont.chaine.map((c) => (
                    <li key={c.id}>
                      {KIND_LABEL[c.type] || c.type}{" "}
                      {c.fiche ? <a href="#fiche" onClick={(ev) => { ev.preventDefault(); ouvrirId(c.fiche.id); }}><strong>{c.nom}</strong></a> : <strong>{c.nom}</strong>}
                      {" "}<span style={{ color: c.etat === "online" ? "var(--ok)" : c.etat === "offline" ? "var(--danger)" : "var(--muted)" }}>●</span>
                      {c.parent && <span className="muted"> — relié à {c.parent}{c.port_parent ? ` port ${c.port_parent}` : ""}</span>}
                      {" "}<a href={hubLink("nebula", { tab: "vlan", name: c.nom })} title="voir dans le synoptique">🗺</a>
                    </li>
                  ))}
                </ol>
              )}
              {amont?.id === courant.id && amont.chaine.length > 0 && <p className="muted" style={{ fontSize: 12 }}>Les équipements amont inscrits au registre et posés sur le plan sont entourés et reliés. Un équipement non inscrit : le créer avec son nom Nebula pour le situer.</p>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
